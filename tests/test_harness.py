"""Offline mechanics for the validation harness — zero model calls (injected fake generate).
The live version runs via `tcm selfcheck`. Run: python tests/test_harness.py
"""
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import db, harness
from tests.fixtures import FIXTURE_FEATURESET


def _valid_reading(pattern="整体平和倾向", plain="根据你的数据给出的趋势参考，仅供参考。"):
    return json.dumps({
        "reading_title": "Trend Check",
        "tcm_pattern_summary": pattern,
        "plain_summary": plain,
        "basis": ["趋势参考，无具体数值"],           # no numbers -> grounding trivially passes
        "confidence_note": "n",
        "advice": {"diet": ["规律三餐"], "routine": ["固定作息"],
                   "rest": ["午间小憩"], "exercise": ["饭后散步"]},
        "followup": {"what_to_watch": ["静息心率"], "recheck_in_days": 7},
        "flags": [],
        "disclaimer": db.DISCLAIMER,
    }, ensure_ascii=False)


def test_scramble_inverts_deviations():
    s = harness.scramble_featureset(FIXTURE_FEATURESET)
    r0 = FIXTURE_FEATURESET["metrics"]["resting_hr"]
    r1 = s["metrics"]["resting_hr"]
    assert r1["z"] == -r0["z"]
    assert r1["pct_delta"] == -r0["pct_delta"]
    assert r1["percentile"] == 100 - r0["percentile"]
    assert r1["today"] == round(2 * r0["median"] - r0["today"], 4)
    assert r1["dir7"]["slope_sign"] == -r0["dir7"]["slope_sign"]
    assert FIXTURE_FEATURESET["metrics"]["resting_hr"]["z"] == r0["z"]  # original untouched


def test_ablation_detects_tethered_reading():
    # a tethered fake: BOTH the pattern and the plain summary flip with the digest's direction
    def gen(digest, hist, profile, sysp, kn, provider):
        worse = digest.count("above") >= digest.count("below")
        if worse:
            return _valid_reading("整体偏亢奋倾向", "近期各项偏离提示恢复偏不足，宜多加留意与调养。")
        return _valid_reading("整体偏平和放松倾向", "近期各项数值平稳良好，状态整体安定，可继续保持。")
    rep = harness.ablation_check(FIXTURE_FEATURESET, "sys", "kn", generate=gen)
    assert rep["verdict"] == "PASS", rep
    assert rep["real_summary"] != rep["scrambled_summary"]


def test_ablation_flags_decorative_reading():
    def gen(*a, **k):                       # constant output, ignores the digest -> decorative
        return _valid_reading("整体平和倾向")
    rep = harness.ablation_check(FIXTURE_FEATURESET, "sys", "kn", generate=gen)
    assert rep["verdict"].startswith("FAIL"), rep
    assert rep["similarity"] == 1.0


def test_retest_reports_stability():
    def gen(*a, **k):
        return _valid_reading("整体平和倾向")
    rep = harness.test_retest(FIXTURE_FEATURESET, "sys", "kn", n=4, generate=gen)
    assert rep["verdict"] == "OK"
    assert rep["valid"] == 4
    assert rep["mean_pairwise_similarity"] == 1.0
    assert rep["advice_categories_consistent"] is True


def test_harness_reports_error_when_reading_blocked():
    def gen(*a, **k):                       # always emits a texture-pulse -> validator blocks it
        return _valid_reading("脉弦有力")
    rep = harness.ablation_check(FIXTURE_FEATURESET, "sys", "kn", generate=gen)
    assert rep["verdict"] == "ERROR"


# ---------------------------------------------------------------------------
# §7.4 convergent check (deterministic, no model calls)
# ---------------------------------------------------------------------------

def _seed(conn, days=60, rated=20, correlated=True):
    """60 days of metrics; the last `rated` days ramp recovery upward with matching self-ratings."""
    start = date(2026, 1, 1)
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        wig = (i * 7) % 5                      # deterministic wiggle so MAD > 0
        db.upsert_metric(conn, d, db.RESTING_HR, 60 + wig, "bpm", "t")
        db.upsert_metric(conn, d, db.HRV_SDNN, 50 + wig, "ms", "t")
    for k in range(rated):
        d = (start + timedelta(days=days - rated + k)).isoformat()
        db.upsert_metric(conn, d, db.RESTING_HR, 60 - k * 0.4, "bpm", "t")   # falling = more recovered
        db.upsert_metric(conn, d, db.HRV_SDNN, 50 + k * 1.5, "ms", "t")      # rising  = more recovered
        energy = (1 + k // 5) if correlated else (5 - k // 5)
        conn.execute("INSERT INTO context(date,note,sleep_quality,energy,stress) VALUES(?,?,?,?,?)",
                     (d, "", 1 + k // 7, energy, 5 - k // 5))
    conn.commit()


def test_convergent_insufficient_data_reports_progress():
    conn = db.connect(":memory:")
    rep = harness.convergent_check(conn)
    assert rep["verdict"] == "insufficient_data"
    assert rep["n"] == 0
    assert "0/14" in rep["message"]


def test_convergent_detects_positive_correlation():
    conn = db.connect(":memory:")
    _seed(conn)
    rep = harness.convergent_check(conn)
    assert rep["verdict"] == "reported", rep
    assert rep["n"] == 20
    energy = rep["correlations"]["energy"]
    assert energy["rho"] > 0, energy               # recovery up, energy up
    assert energy["matches_expected"] is True
    stress = rep["correlations"]["stress"]
    assert stress["rho"] < 0, stress               # recovery up, stress down
    assert stress["matches_expected"] is True
    assert "n=1" in rep["caveats"]                 # the null-result / confound caveat is mandatory


def test_convergent_reports_null_result_without_burying_it():
    conn = db.connect(":memory:")
    _seed(conn, correlated=False)                  # energy ramps AGAINST recovery
    rep = harness.convergent_check(conn)
    energy = rep["correlations"]["energy"]
    assert energy["rho"] < 0                       # the contrary result is still reported...
    assert energy["matches_expected"] is False     # ...and honestly flagged as not tracking


def test_recovery_score_direction():
    # higher HRV and lower resting HR both mean MORE recovered -> higher score
    conn = db.connect(":memory:")
    _seed(conn)
    rhr = dict(db.series(conn, db.RESTING_HR))
    hrv = dict(db.series(conn, db.HRV_SDNN))
    early = harness.recovery_score(rhr, hrv, date(2026, 1, 1) + timedelta(days=40))
    late = harness.recovery_score(rhr, hrv, date(2026, 1, 1) + timedelta(days=59))
    assert early is not None and late is not None
    assert late > early


if __name__ == "__main__":
    fns = [fn for k, fn in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} harness tests passed")
