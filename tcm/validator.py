"""Safety-enforcement layer for model-emitted TCM readings. Pure functions, stdlib only.

`validate(raw, digest)` runs 7 independent checks against a raw JSON string (the model's
claimed output) and the digest string it was generated from, and returns every violation
found -- it never short-circuits, except when the JSON itself won't parse (the one
documented early return). `render_fallback(digest, codes)` is the deterministic,
TCM-vocabulary-free template used when the model fails validation twice in a row
(see cli.run_reading, MAX_ATTEMPTS).

Deny-lists here are deliberately literal and NOT to be trimmed for "simplicity" -- each term
targets a specific class of unsafe output (naming a disease, inventing a pulse texture,
prescribing a herb dose, ...). Removing an entry removes the thing it was catching.
"""
import json
import re

from . import db

# ---------------------------------------------------------------------------
# 1. schema
# ---------------------------------------------------------------------------

REQUIRED_TOP_KEYS = {
    "reading_title", "tcm_pattern_summary", "plain_summary", "basis",
    "confidence_note", "advice", "followup", "flags", "disclaimer",
}
ADVICE_KEYS = {"diet", "routine", "rest", "exercise"}
FOLLOWUP_KEYS = {"what_to_watch", "recheck_in_days"}
TITLE_MAX = 24
PATTERN_SUMMARY_MAX = 120


def _str_list(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _check_schema(reading):
    """List of detail strings; empty means the schema check passed."""
    if not isinstance(reading, dict):
        return [f"not_an_object:{type(reading).__name__}"]

    errs = []
    keys = set(reading)
    missing = REQUIRED_TOP_KEYS - keys
    extra = keys - REQUIRED_TOP_KEYS
    if missing:
        errs.append(f"missing_keys:{sorted(missing)}")
    if extra:
        errs.append(f"unknown_keys:{sorted(extra)}")

    def _check_str(key, maxlen=None):
        if key not in reading:
            return
        v = reading[key]
        if not isinstance(v, str):
            errs.append(f"{key}_type")
        elif maxlen is not None and len(v) > maxlen:
            errs.append(f"{key}_too_long:{len(v)}")

    _check_str("reading_title", TITLE_MAX)
    _check_str("tcm_pattern_summary", PATTERN_SUMMARY_MAX)
    _check_str("plain_summary")
    _check_str("confidence_note")
    _check_str("disclaimer")

    if "basis" in reading and not _str_list(reading["basis"]):
        errs.append("basis_type")
    if "flags" in reading and not _str_list(reading["flags"]):
        errs.append("flags_type")

    if "advice" in reading:
        advice = reading["advice"]
        if not isinstance(advice, dict):
            errs.append("advice_type")
        else:
            akeys = set(advice)
            amissing = ADVICE_KEYS - akeys
            aextra = akeys - ADVICE_KEYS
            if amissing:
                errs.append(f"advice_missing_keys:{sorted(amissing)}")
            if aextra:
                errs.append(f"advice_unknown_keys:{sorted(aextra)}")
            for k in ADVICE_KEYS & akeys:
                if not _str_list(advice[k]):
                    errs.append(f"advice.{k}_type")

    if "followup" in reading:
        followup = reading["followup"]
        if not isinstance(followup, dict):
            errs.append("followup_type")
        else:
            fkeys = set(followup)
            fmissing = FOLLOWUP_KEYS - fkeys
            fextra = fkeys - FOLLOWUP_KEYS
            if fmissing:
                errs.append(f"followup_missing_keys:{sorted(fmissing)}")
            if fextra:
                errs.append(f"followup_unknown_keys:{sorted(fextra)}")
            if "what_to_watch" in followup and not _str_list(followup["what_to_watch"]):
                errs.append("followup.what_to_watch_type")
            if "recheck_in_days" in followup:
                rid = followup["recheck_in_days"]
                if isinstance(rid, bool) or not isinstance(rid, int):
                    errs.append("followup.recheck_in_days_type")

    return errs


# ---------------------------------------------------------------------------
# 2. texture_pulse -- pulse-context bigrams/terms only, never bare characters.
#    A naive single-char list would wrongly reject 仔细/沉睡/浮躁/滑雪.
# ---------------------------------------------------------------------------

TEXTURE_PULSE_TERMS = [
    "弦脉", "脉弦", "滑脉", "脉滑", "涩脉", "脉涩", "浮脉", "脉浮", "沉脉", "脉沉",
    "细脉", "脉细", "紧脉", "脉紧", "洪脉", "脉洪", "虚脉", "实脉",
    "指下", "脉位", "脉力", "脉体", "举按", "寸关尺",
]

# ---------------------------------------------------------------------------
# 3. disease -- named conditions + diagnostic verbs, zh and en
# ---------------------------------------------------------------------------

DISEASE_TERMS_ZH = [
    "糖尿病", "高血压", "冠心病", "心脏病", "房颤", "心律失常", "甲亢", "贫血",
    "肺炎", "感冒", "发烧", "发热", "抑郁症", "焦虑症", "癌",
]
# unambiguous diagnosis/treatment CLAIMS -- always blocked
DISEASE_VERBS_ZH = ["确诊", "患有", "病因", "疗程"]
# 诊断 and 治疗 also appear in honest DISCLAIMERS the model is asked to write ("非医学诊断",
# "不能替代治疗"). Flag them only as CLAIMS -- i.e. when NOT preceded by a negation/hedge within
# a short window. This stops the model's own hedging from being read as a diagnosis.
DISEASE_HEDGE_PRONE = ["诊断", "治疗"]
_DISEASE_NEGATORS = ("非", "不", "未", "无", "勿", "别", "替代")
_DISEASE_NEG_WINDOW = 10
DISEASE_EN_RE = re.compile(
    r"\b(?:diabetes|hypertension|arrhythmia|diagnos(?:e|is|ed|es|ing)?|disease)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 4. excluded_topic -- pregnancy, mortality/critical illness, v1 bans
# ---------------------------------------------------------------------------

PREGNANCY_TERMS_ZH = ["怀孕", "妊娠", "早孕"]
PREGNANCY_EN_RE = re.compile(r"\bpregnan\w*", re.IGNORECASE)
MORTALITY_TERMS_ZH = ["死亡", "猝死", "危重", "寿命"]
MORTALITY_EN_RE = re.compile(r"\b(?:mortality|life expectancy)\b", re.IGNORECASE)
V1_BANNED_ZH = ["上火", "痰湿"]

# ---------------------------------------------------------------------------
# 4b. cycle-tracking gate (only active when profile.cycle_tracking is True)
#     The luteal-phase resting-HR rise (~3.5 bpm) is the same direction and size as the
#     "physiological stress" signal and is indistinguishable without cycle-phase tagging. So
#     when cycle tracking is on, stress/illness-adjacent framing is BLOCKED (structural, not
#     merely discouraged) until phase tagging exists. Prerequisite for family expansion.
# ---------------------------------------------------------------------------

CYCLE_GATED_TERMS = ["压力", "应激", "炎症", "发炎", "生病", "过劳", "劳累"]
CYCLE_GATED_EN_RE = re.compile(r"\b(?:stress|illness|inflammation|infection)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# 5. herb -- formula/prep words + dosage patterns
# ---------------------------------------------------------------------------

HERB_FORMULA_WORDS = ["方剂", "冲剂"]
HERB_SINGLE_CHARS = "汤丸散膏"
# ponytail: hardcoded whitelist so single herb chars inside common non-TCM daily words
# (散步 "take a walk", 煲汤 "make soup") don't trip the check -- the ban on 汤/丸/散/膏 is
# deliberately strict (v1, no NLP), so it needs this small escape hatch. Ceiling: only
# covers words seen in practice; add more here if a new false positive shows up. Formula
# names (e.g. 四物汤) and dosage patterns are unaffected and still caught below.
HERB_SAFE_WORDS = ("散步", "煲汤")
DOSAGE_RE = re.compile(r"\d+\s*(?:克|g|钱)", re.IGNORECASE)


def _in_safe_word(text, i, ch):
    for w in HERB_SAFE_WORDS:
        if ch not in w:
            continue
        off = w.index(ch)
        start = i - off
        if start >= 0 and text[start:start + len(w)] == w:
            return True
    return False


def _find_herb(text):
    hits = [w for w in HERB_FORMULA_WORDS if w in text]
    for ch in HERB_SINGLE_CHARS:
        for m in re.finditer(re.escape(ch), text):
            if not _in_safe_word(text, m.start(), ch):
                hits.append(ch)
    hits += DOSAGE_RE.findall(text)
    return hits


def _find_terms(text, terms):
    return [t for t in terms if t in text]


def _find_texture_pulse(text):
    return _find_terms(text, TEXTURE_PULSE_TERMS)


def _find_disease(text):
    hits = _find_terms(text, DISEASE_TERMS_ZH) + _find_terms(text, DISEASE_VERBS_ZH)
    for w in DISEASE_HEDGE_PRONE:
        for m in re.finditer(re.escape(w), text):
            window = text[max(0, m.start() - _DISEASE_NEG_WINDOW):m.start()]
            if not any(neg in window for neg in _DISEASE_NEGATORS):
                hits.append(w)  # unhedged -> a claim
    hits += DISEASE_EN_RE.findall(text)
    return hits


def _find_excluded_topic(text):
    hits = _find_terms(text, PREGNANCY_TERMS_ZH)
    hits += PREGNANCY_EN_RE.findall(text)
    hits += _find_terms(text, MORTALITY_TERMS_ZH)
    hits += MORTALITY_EN_RE.findall(text)
    hits += _find_terms(text, V1_BANNED_ZH)
    return hits


def _all_strings(obj):
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        out = []
        for v in obj.values():
            out.extend(_all_strings(v))
        return out
    if isinstance(obj, list):
        out = []
        for v in obj:
            out.extend(_all_strings(v))
        return out
    return []


def _scannable_strings(reading):
    """All string values EXCEPT the top-level disclaimer.

    db.DISCLAIMER is fixed, pre-approved boilerplate checked separately (and exactly) by
    check 7 -- it is not model narrative. It also isn't vocabulary-clean by accident: it
    literally says "并非医疗诊断" (not a medical diagnosis), which contains 诊断, one of the
    check-3 diagnostic verbs. Scanning it here would make every valid reading unvalidatable.
    """
    if not isinstance(reading, dict):
        return _all_strings(reading)
    out = []
    for k, v in reading.items():
        if k == "disclaimer":
            continue
        out.extend(_all_strings(v))
    return out


# ---------------------------------------------------------------------------
# 6. ungrounded_number
# ---------------------------------------------------------------------------

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?%?")
# thousands separators only (digit,digit) — so the digest's "3,120" and a model's "3120" match.
# List commas ("58, 60") have a space and are left alone.
_THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d)")


def _strip_thousands(s):
    return _THOUSANDS_RE.sub("", s)

# Numbers that are close-but-not-grounded get logged here instead of rejected, so the
# near-miss tolerance can be tuned from real data without touching the deny logic.
NEAR_MISSES = []


def _digest_numbers(digest):
    out = []
    for tok in NUMBER_RE.findall(digest):
        try:
            out.append(float(tok.rstrip("%")))
        except ValueError:
            pass
    return out


def _is_derived_pct(val, digest_nums):
    """val is OK if it equals round(100*(a-b)/b) for some a,b already present in the digest."""
    target = round(val)
    for a in digest_nums:
        for b in digest_nums:
            if b == 0:
                continue
            if round(100 * (a - b) / b) == target:
                return True
    return False


def _is_near_miss(val, digest_nums):
    return any(abs(val - dn) <= max(1.0, abs(dn) * 0.03) for dn in digest_nums)


def _check_ungrounded_numbers(basis, plain_summary, digest):
    digest = _strip_thousands(digest)          # so "3,120" grounds a model's "3120"
    digest_nums = _digest_numbers(digest)
    hits = []
    for field in list(basis) + [plain_summary]:
        field = _strip_thousands(field)
        for tok in NUMBER_RE.findall(field):
            if tok in digest:
                continue
            val = float(tok.rstrip("%"))
            if tok.endswith("%") and _is_derived_pct(val, digest_nums):
                continue
            if _is_near_miss(val, digest_nums):
                NEAR_MISSES.append({"token": tok, "field": field})
                continue
            hits.append(tok)
    return hits


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def validate(raw: str, digest: str, profile=None) -> tuple[bool, list[str]]:
    """Run all safety checks against a model-emitted reading. Never raises on bad input.

    Returns (ok, violations). Every failed check contributes its bare code (e.g. "disease");
    schema also appends "schema:<detail>" debug entries alongside the bare "schema" code.
    ok is True iff violations is empty. The only early return is unparseable JSON.

    `profile` is optional. If profile["cycle_tracking"] is True, an extra hard gate blocks
    stress/illness-adjacent framing (see CYCLE_GATED_TERMS) -- code "cycle_gated".
    """
    try:
        reading = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False, ["schema:unparseable"]

    violations = []

    schema_errs = _check_schema(reading)
    if schema_errs:
        violations.append("schema")
        violations.extend(f"schema:{e}" for e in schema_errs)

    joined = "\n".join(_scannable_strings(reading))

    if _find_texture_pulse(joined):
        violations.append("texture_pulse")
    if _find_disease(joined):
        violations.append("disease")
    if _find_excluded_topic(joined):
        violations.append("excluded_topic")
    if _find_herb(joined):
        violations.append("herb")
    if profile and profile.get("cycle_tracking") and (
            _find_terms(joined, CYCLE_GATED_TERMS) or CYCLE_GATED_EN_RE.search(joined)):
        violations.append("cycle_gated")

    basis = reading.get("basis") if isinstance(reading, dict) else None
    basis = basis if _str_list(basis) else []
    plain_summary = reading.get("plain_summary") if isinstance(reading, dict) else None
    plain_summary = plain_summary if isinstance(plain_summary, str) else ""

    if _check_ungrounded_numbers(basis, plain_summary, digest):
        violations.append("ungrounded_number")

    disclaimer = reading.get("disclaimer") if isinstance(reading, dict) else None
    if disclaimer != db.DISCLAIMER:
        violations.append("disclaimer")
    if not plain_summary.strip():
        violations.append("empty_summary")

    return (violations == []), violations


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------

def render_fallback(digest: str, codes: list[str]) -> str:
    """Deterministic template reading used when the model output is discarded after 2 failed
    validate() attempts: the digest's facts restated + generic non-personalised wellness
    advice (diet/routine/rest/exercise, everyday & low-risk) + the withheld-narrative line +
    db.DISCLAIMER. Contains no TCM vocabulary and no personalised claims -- the rejected
    model text is never included.
    """
    lines = [
        "Your recent data, restated plainly:",
        digest.strip(),
        "",
        "General wellness suggestions (not personalised to the above):",
        "- Diet: regular meals, plenty of water and vegetables, go easy on late-night snacking.",
        "- Routine: keep a consistent sleep and wake time, even on weekends.",
        "- Rest: wind down screens for the last hour before bed.",
        "- Exercise: a daily walk or other light activity you enjoy.",
        "",
        f"The narrative layer was withheld for this reading (validator: {', '.join(codes)}).",
        "",
        db.DISCLAIMER,
    ]
    return "\n".join(lines)
