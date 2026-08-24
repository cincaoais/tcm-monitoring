"""Validation harness — §7.2 test-retest, §7.3 ablation/confabulation, §7.4 convergent check.

§7.2 and §7.3 make real model calls (`tcm selfcheck`). §7.4 (`convergent_check`) is DETERMINISTIC —
no model calls, pure arithmetic over stored data — and runs free via `tcm converge`.
The question both answer: is the narrative layer tethered to the numbers, or decorative?
- ablation (the more important one): scramble the digest; a tethered reading changes materially.
- test-retest: run the same digest n times; a stable layer gives similar readings.

`generate` is injectable so the mechanics are testable offline (tests/test_harness.py) with no calls.
The recovery-polarity score is a COARSE NL heuristic — reported as a signal, never asserted on;
the robust signal is the language-agnostic difflib similarity plus the printed summaries.
"""
import difflib
import json
import statistics
from datetime import date, timedelta

from tcm import baseline, db, digest as digest_mod, reasoning, validator

# advisory recovery-polarity lexicon (leans "less recovered" vs "more recovered"). Not ground truth.
_WORSE = ["不足", "不充分", "亢奋", "偏数", "偏快", "疲", "压力", "负荷", "欠佳", "紧张"]
_BETTER = ["良好", "平和", "放松", "较好", "平稳", "充足", "平衡"]

ABLATION_MAX_SIMILARITY = 0.85  # scrambled vs real must be LESS similar than this to pass


def scramble_featureset(fs):
    """Invert every metric's deviation: reflect today across its median and flip z / % / percentile
    / 7-day direction. Pure (deep-copies via JSON round-trip; fs is JSON-native)."""
    s = json.loads(json.dumps(fs))
    for m in s["metrics"].values():
        if m.get("today") is None or m.get("median") is None:
            continue
        m["today"] = round(2 * m["median"] - m["today"], 4)
        for k in ("z", "pct_delta"):
            if m.get(k) is not None:
                m[k] = -m[k]
        if m.get("percentile") is not None:
            m["percentile"] = 100 - m["percentile"]
        d = m.get("dir7") or {}
        if d.get("z") is not None:
            d["z"] = -d["z"]
        d["slope_sign"] = -d.get("slope_sign", 0)
        if d.get("median7") is not None:
            d["median7"] = round(2 * m["median"] - d["median7"], 4)
    return s


def _polarity(reading):
    text = reading.get("tcm_pattern_summary", "") + " " + reading.get("plain_summary", "")
    return sum(text.count(t) for t in _WORSE) - sum(text.count(t) for t in _BETTER)


def _summary(reading):
    return reading.get("tcm_pattern_summary", "") + "\n" + reading.get("plain_summary", "")


def _advice_cats(reading):
    a = reading.get("advice", {}) or {}
    return tuple(k for k in ("diet", "routine", "rest", "exercise") if a.get(k))


def _similar(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def _gen_valid(digest_text, system_prompt, knowledge, provider, generate):
    """One model call → parsed reading dict, or None if the output failed the validator."""
    raw = generate(digest_text, "", {"cycle_tracking": False}, system_prompt, knowledge, provider)
    ok, _ = validator.validate(raw, digest_text)
    if not ok:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def ablation_check(fs, system_prompt, knowledge, *, provider="claude_code", generate=None):
    """§7.3: real digest vs a scrambled (deviations-inverted) digest. A tethered layer produces
    materially different readings; a decorative one produces near-identical text."""
    generate = generate or reasoning.generate_reading
    real_digest = digest_mod.render_digest(fs)
    scrambled_digest = digest_mod.render_digest(scramble_featureset(fs))
    real = _gen_valid(real_digest, system_prompt, knowledge, provider, generate)
    scr = _gen_valid(scrambled_digest, system_prompt, knowledge, provider, generate)
    if real is None or scr is None:
        return {"verdict": "ERROR", "reason": "a reading failed validation",
                "real_ok": real is not None, "scrambled_ok": scr is not None}
    sim = _similar(_summary(real), _summary(scr))
    pol_real, pol_scr = _polarity(real), _polarity(scr)
    return {
        "verdict": "PASS" if sim < ABLATION_MAX_SIMILARITY else "FAIL(decorative?)",
        "similarity": round(sim, 3),
        "threshold": ABLATION_MAX_SIMILARITY,
        "polarity_real": pol_real,
        "polarity_scrambled": pol_scr,
        "polarity_flipped_toward_worse": (pol_real - pol_scr) > 0,  # advisory
        "real_summary": real.get("tcm_pattern_summary", ""),
        "scrambled_summary": scr.get("tcm_pattern_summary", ""),
    }


# ---------------------------------------------------------------------------
# §7.4 convergent check — deterministic, no model calls
# ---------------------------------------------------------------------------

MIN_CONVERGENT_DAYS = 14  # the plan wants ~6 weeks; below this, report progress instead of a number

# expected sign of each correlation if the system tracks how this person actually feels
_EXPECTED_SIGN = {"energy": "+", "sleep_quality": "+", "stress": "-"}

CONVERGENT_CAVEATS = (
    "Exploratory, n=1, single person. Association only — nothing here shows causation. "
    "Self-ratings are subjective and are logged on days the person chose to log, which is itself "
    "a confound. A null or negative result is informative and is reported, not buried."
)


def _z_on(series_map, day):
    """Robust z of `day`'s value against its own trailing 28-day window. None if not computable."""
    today = series_map.get(day.isoformat())
    if today is None:
        return None
    win = []
    for i in range(1, baseline.WINDOW_DAYS + 1):
        v = series_map.get((day - timedelta(days=i)).isoformat())
        if v is not None:
            win.append(v)
    if len(win) < baseline.MIN_DAYS:
        return None
    return baseline.robust_z(today, baseline.robust_stats(win))


def recovery_score(rhr_map, hrv_map, day):
    """The system's recovery direction for one day: higher = more recovered.

    Uses the per-metric semantics: lower HRV = less recovered, higher resting HR = less recovered.
    """
    z_rhr = _z_on(rhr_map, day)
    z_hrv = _z_on(hrv_map, day)
    if z_rhr is None or z_hrv is None:
        return None
    return z_hrv - z_rhr


def convergent_check(conn, min_days=MIN_CONVERGENT_DAYS):
    """§7.4: Spearman correlation between the system's recovery direction and this person's own
    self-ratings from `tcm log`. Deterministic — no model calls."""
    rhr = dict(db.series(conn, db.RESTING_HR))
    hrv = dict(db.series(conn, db.HRV_SDNN))
    rows = conn.execute(
        "SELECT date, sleep_quality, energy, stress FROM context ORDER BY date").fetchall()

    paired = []
    for r in rows:
        score = recovery_score(rhr, hrv, date.fromisoformat(r["date"]))
        if score is not None:
            paired.append((score, r))

    out = {"n": len(paired), "min_days": min_days}
    if len(paired) < min_days:
        out["verdict"] = "insufficient_data"
        out["message"] = (f"{len(paired)}/{min_days} usable days. Log daily with `tcm log` — "
                          f"{min_days - len(paired)} more needed before a correlation means anything.")
        return out

    out["verdict"] = "reported"
    out["correlations"] = {}
    for field, expected in _EXPECTED_SIGN.items():
        xs = [s for s, r in paired if r[field] is not None]
        ys = [r[field] for s, r in paired if r[field] is not None]
        entry = {"n": len(xs), "expected_sign": expected}
        if len(xs) < min_days:
            entry.update(rho=None, note="not enough ratings logged for this field")
        else:
            try:
                rho = statistics.correlation(xs, ys, method="ranked")
                entry.update(rho=round(rho, 3),
                             matches_expected=(rho > 0) if expected == "+" else (rho < 0))
            except statistics.StatisticsError as e:
                entry.update(rho=None, note=f"undefined ({e}) — ratings or scores are constant")
        out["correlations"][field] = entry
    out["caveats"] = CONVERGENT_CAVEATS
    return out


def test_retest(fs, system_prompt, knowledge, *, n=5, provider="claude_code", generate=None):
    """§7.2: run the SAME digest through the model n times; report output stability."""
    generate = generate or reasoning.generate_reading
    digest_text = digest_mod.render_digest(fs)
    readings = [_gen_valid(digest_text, system_prompt, knowledge, provider, generate) for _ in range(n)]
    ok = [r for r in readings if r is not None]
    if len(ok) < 2:
        return {"verdict": "ERROR", "reason": f"only {len(ok)}/{n} readings passed validation"}
    summaries = [_summary(r) for r in ok]
    sims = [_similar(summaries[i], summaries[j])
            for i in range(len(summaries)) for j in range(i + 1, len(summaries))]
    cats = [_advice_cats(r) for r in ok]
    pols = [_polarity(r) for r in ok]
    return {
        "verdict": "OK",
        "n": n, "valid": len(ok),
        "mean_pairwise_similarity": round(sum(sims) / len(sims), 3),
        "min_pairwise_similarity": round(min(sims), 3),
        "advice_categories_consistent": len(set(cats)) == 1,
        "advice_category_sets": [list(c) for c in cats],
        "polarity_all_same_sign": len({p > 0 for p in pols}) == 1,
        "polarities": pols,
    }
