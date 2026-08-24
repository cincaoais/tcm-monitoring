"""Safety-enforcement corpus for validator.py. Plain asserts, no framework.
Run: python tests/test_validator.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import db
from tcm import validator as v

DIGEST = (
    "Resting heart rate: today 61 bpm, 28-day median 58 bpm (+5.17%). "
    "Overnight HRV (SDNN): today 38 ms, 28-day median 48 ms (-20.83%). "
    "Sleep: today 342 min, 28-day median 420 min. "
    "Steps: today 4120, 28-day median 4500."
)


def _valid_reading():
    return {
        "reading_title": "Weekly Trend Note",
        "tcm_pattern_summary": (
            "Signals lean toward reduced overnight recovery; read as a loose "
            "tendency, not a fixed pattern."
        ),
        "plain_summary": (
            "Over the past month your resting heart rate has been a little higher "
            "than usual and your overnight recovery signal has dipped, which often "
            "shows up together during a stretch of poor sleep or extra stress. "
            "Nothing here points to a specific problem -- these are just patterns "
            "worth keeping an eye on."
        ),
        "basis": [
            "Resting heart rate is up about 5.17% versus the 28-day median (61 vs 58 bpm).",
            "Overnight HRV is down about 20.83% versus the 28-day median (38 vs 48 ms).",
        ],
        "confidence_note": "Based on 26 of the last 28 days of data; individual variation is normal.",
        "advice": {
            "diet": ["Keep meals regular and include vegetables at most meals."],
            "routine": ["Aim for a consistent wake time, even on weekends."],
            "rest": ["Wind down screens for the last hour before bed."],
            "exercise": ["A daily walk or other light activity you enjoy."],
        },
        "followup": {
            "what_to_watch": ["Whether resting heart rate stays elevated next week."],
            "recheck_in_days": 7,
        },
        "flags": [],
        "disclaimer": db.DISCLAIMER,
    }


def _dumps(reading):
    return json.dumps(reading, ensure_ascii=False)


# ---------------------------------------------------------------------------
# MUST-PASS
# ---------------------------------------------------------------------------

def test_valid_reading_passes():
    ok, violations = v.validate(_dumps(_valid_reading()), DIGEST)
    assert ok is True
    assert violations == []


def test_pass_texture_pulse_innocent_words():
    r = _valid_reading()
    r["plain_summary"] += " 仔细看看：沉睡、浮躁、滑雪、散步都只是日常词汇。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is True, violations
    assert violations == []


def test_pass_herb_innocent_word():
    r = _valid_reading()
    r["advice"]["exercise"].append("晚饭后散步十五分钟。")
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is True, violations


def test_pass_derived_percentage():
    # 9% is not written anywhere in DIGEST, but round(100*(4500-4120)/4120) == 9.
    r = _valid_reading()
    r["basis"].append("Steps were about 9% below the recent baseline (4120 vs 4500).")
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is True, violations


def test_near_miss_logged_not_rejected():
    before = len(v.NEAR_MISSES)
    r = _valid_reading()
    r["basis"].append("Overnight HRV averaged 38.4 ms recently.")
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is True, violations
    assert len(v.NEAR_MISSES) > before


# ---------------------------------------------------------------------------
# MUST-BLOCK
# ---------------------------------------------------------------------------

def test_block_texture_pulse_bigram():
    r = _valid_reading()
    r["tcm_pattern_summary"] = "脉象偏弦脉，仅供趋势参考。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "texture_pulse" in violations


def test_block_texture_pulse_context_term():
    r = _valid_reading()
    r["plain_summary"] += " 寸关尺细节仅供参考。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "texture_pulse" in violations


def test_block_disease_diabetes_zh():
    r = _valid_reading()
    r["plain_summary"] += " 需警惕糖尿病风险。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "disease" in violations


def test_block_disease_afib_zh():
    r = _valid_reading()
    r["plain_summary"] += " 类似房颤的表现。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "disease" in violations


def test_block_disease_en():
    r = _valid_reading()
    r["plain_summary"] += " This could suggest diabetes."
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "disease" in violations


def test_block_herb_dose():
    r = _valid_reading()
    r["advice"]["diet"].append("每日服用黄芪10克。")
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "herb" in violations


def test_block_herb_formula():
    r = _valid_reading()
    r["advice"]["diet"].append("建议服用四物汤。")
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "herb" in violations


def test_block_excluded_pregnancy():
    r = _valid_reading()
    r["plain_summary"] += " 若怀孕请勿参考本报告。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "excluded_topic" in violations


def test_block_excluded_mortality():
    r = _valid_reading()
    r["plain_summary"] += " 与猝死无关。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "excluded_topic" in violations


def test_block_excluded_shanghuo():
    r = _valid_reading()
    r["tcm_pattern_summary"] += " 上火"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "excluded_topic" in violations


def test_block_excluded_tanshi():
    r = _valid_reading()
    r["tcm_pattern_summary"] += " 痰湿"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "excluded_topic" in violations


def test_block_ungrounded_number():
    r = _valid_reading()
    r["basis"].append("Resting heart rate spiked to 133 bpm overnight.")
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "ungrounded_number" in violations


def test_block_missing_disclaimer():
    r = _valid_reading()
    del r["disclaimer"]
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "disclaimer" in violations


def test_block_wrong_disclaimer():
    r = _valid_reading()
    r["disclaimer"] = "This is not the real disclaimer."
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "disclaimer" in violations
    assert "schema" not in violations


def test_block_empty_plain_summary():
    r = _valid_reading()
    r["plain_summary"] = ""
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "empty_summary" in violations
    assert "schema" not in violations


def test_block_unparseable_json():
    ok, violations = v.validate("{not valid json", DIGEST)
    assert ok is False
    assert violations == ["schema:unparseable"]


def test_block_missing_required_key():
    r = _valid_reading()
    del r["flags"]
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "schema" in violations


def test_block_reading_title_too_long():
    r = _valid_reading()
    r["reading_title"] = "x" * 30
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "schema" in violations


def test_block_unknown_top_level_key():
    r = _valid_reading()
    r["extra_field"] = "not allowed"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "schema" in violations


def test_multiple_violations_collected():
    # Checks must all run and accumulate -- no early return once JSON parses.
    r = _valid_reading()
    r["tcm_pattern_summary"] = "偏弦脉"
    r["plain_summary"] += " 需警惕糖尿病。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert ok is False
    assert "texture_pulse" in violations
    assert "disease" in violations


# ---------------------------------------------------------------------------
# render_fallback
# ---------------------------------------------------------------------------

def test_render_fallback():
    text = v.render_fallback(DIGEST, ["disease", "herb"])
    assert db.DISCLAIMER in text
    assert "narrative layer was withheld" in text
    # db.DISCLAIMER itself legitimately contains 数/代 (it says "not a medical diagnosis"
    # using 历史数据/替代) -- the no-TCM-vocab guarantee is about our OWN template prose,
    # so check everything outside the mandatory disclaimer string.
    template_only = text.replace(db.DISCLAIMER, "")
    for ch in "数迟结代弦滑":
        assert ch not in template_only, ch


# ---------------------------------------------------------------------------
# cycle-tracking hard gate (only active when profile.cycle_tracking is True)
# ---------------------------------------------------------------------------

def test_disease_hedge_diagnosis_allowed():
    # the model's own honest disclaiming must NOT read as a disease claim
    r = _valid_reading()
    r["confidence_note"] = "本次仅为个人趋势参考，非医学诊断，也不能替代专业治疗与就医。"
    ok, violations = v.validate(_dumps(r), DIGEST)
    assert "disease" not in violations, violations


def test_disease_claim_diagnosis_blocked():
    # 诊断/治疗 used as an actual claim (no negation) is still caught
    for phrase in ("综合来看可诊断为某种失衡", "建议尽快开始治疗"):
        r = _valid_reading()
        r["tcm_pattern_summary"] = phrase
        ok, violations = v.validate(_dumps(r), DIGEST)
        assert "disease" in violations, (phrase, violations)


def test_thousands_comma_number_is_grounded():
    # digest prints "3,120" (human-readable); model writes "3120" -> must still count as grounded
    digest = "Steps 3,120 today, median 4,500."
    r = _valid_reading()
    r["basis"] = ["Steps were 3120 today versus a median of 4500."]
    r["plain_summary"] = "Your step count of 3120 was below your usual 4500."
    ok, violations = v.validate(_dumps(r), digest)
    assert "ungrounded_number" not in violations, violations


def test_cycle_gate_blocks_zh_stress_framing_when_on():
    r = _valid_reading()
    r["tcm_pattern_summary"] = "近期偏于压力偏高的倾向，仅供参考"  # contains 压力
    ok, violations = v.validate(_dumps(r), DIGEST, profile={"cycle_tracking": True})
    assert ok is False and "cycle_gated" in violations


def test_cycle_gate_blocks_en_stress_framing_when_on():
    # the base valid reading's plain_summary says "extra stress" -- gated when cycle tracking is on
    ok, violations = v.validate(_dumps(_valid_reading()), DIGEST, profile={"cycle_tracking": True})
    assert ok is False and "cycle_gated" in violations


def test_cycle_gate_inactive_by_default():
    r = _valid_reading()
    r["tcm_pattern_summary"] = "近期偏于压力偏高的倾向，仅供参考"
    _, viol_none = v.validate(_dumps(r), DIGEST)                              # no profile
    _, viol_off = v.validate(_dumps(r), DIGEST, profile={"cycle_tracking": False})
    assert "cycle_gated" not in viol_none
    assert "cycle_gated" not in viol_off


def test_cycle_gate_clean_reading_passes_when_on():
    r = _valid_reading()
    r["plain_summary"] = ("Over the past month your resting heart rate has been a little higher "
                          "than usual and your overnight recovery signal has dipped; gentle trends "
                          "worth keeping an eye on, nothing pointing to a specific problem.")
    ok, violations = v.validate(_dumps(r), DIGEST, profile={"cycle_tracking": True})
    assert ok, violations


if __name__ == "__main__":
    fns = [v_ for k, v_ in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} validator tests passed")
