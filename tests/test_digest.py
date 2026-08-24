"""Known-value + property checks for digest.py. Run: python tests/test_digest.py"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))   # repo root, for `tcm`
sys.path.insert(0, _HERE)                    # tests/, for `fixtures`

from tcm import digest
from fixtures import FIXTURE_FEATURESET, FIXTURE_NOT_READY

# The 24 TCM-vocabulary characters that must never appear in a rendered digest.
TCM_CHARS = "数迟结代促浮沉弦紧滑涩细洪微弱脉证气血阴阳痰湿火"

GOLDEN_DIGEST = """[Provenance] Daily aggregates recorded by Apple Watch, read from HealthKit, exported 2026-08-14 06:12.
Baseline window: 28 days ending 2026-08-13, 26 of 28 days present.
These are overnight and daily summary values. No live measurement was taken for this reading.
The HRV figure is SDNN derived from the optical sensor (pulse-rate variability), not from an ECG.

[Yesterday vs this person's own baseline]
- Resting heart rate 61bpm — 5% above their 28-day median of 58bpm; robust z +1.3; 82nd percentile of their own range. Modestly above their usual. Higher = less recovered.
- Overnight HRV (SDNN) 38ms — 21% below their 28-day median of 48ms; robust z -1.9; 7th percentile of their own range. Modestly below their usual. Lower = less recovered.
- Sleep 5h42m — 1h18m below their 28-day median of 7h00m; 4th percentile. Modestly below their usual.
- Sleep timing: asleep 01:40, 2h07m later than their median sleep onset of 23:33.
- Steps 4,120 — 45th percentile; within their usual range.
- Active energy 310kcal — 38th percentile; within their usual range.

[7-day direction]
Resting heart rate: 7-day median robust z +0.8, trending up.
Overnight HRV (SDNN): 7-day median robust z -1.1, trending down.

[Context this person logged]
2026-08-13: "late work, two drinks". Self-rated sleep quality 2/5, energy 2/5, stress 4/5.

[Data quality]
All 6 metrics present for yesterday.
0 gap(s) in the trailing 7 days. 2 gap(s) in the 28-day window."""


# --- helpers for small synthetic FeatureSets (band boundaries, no-context, insufficient) ---

def _metric(today, median, z, pct_delta, percentile, band, label="Resting heart rate", unit="bpm",
            recovery_dir="higher_worse", insufficient=False, dir7_z=None, dir7_slope=0):
    return {
        "today": today, "n_window": 20, "insufficient": insufficient,
        "median": median, "scale": 3.0, "spread_degenerate": False,
        "z": z, "pct_delta": pct_delta, "percentile": percentile, "band": band,
        "dir7": {"median7": None, "z": dir7_z, "slope_sign": dir7_slope},
        "label": label, "unit": unit, "recovery_dir": recovery_dir,
    }


def _fs(metrics, context=None, gate_failures=None):
    return {
        "as_of": "2026-01-01", "export_ts": "2026-01-02 06:00",
        "window": {"days": 28, "end": "2026-01-01", "present": 26},
        "ready": True, "gate_failures": gate_failures or [],
        "metrics": metrics, "context": context,
        "quality": {"yesterday_present": list(metrics), "yesterday_missing": [],
                    "gaps_7d": 0, "gaps_28d": 0},
    }


def test_golden_digest():
    out = digest.render_digest(FIXTURE_FEATURESET)
    assert out == GOLDEN_DIGEST
    assert "[Provenance] Daily aggregates recorded by Apple Watch, read from HealthKit, exported" in out
    for header in ("[Provenance]", "[Yesterday vs this person's own baseline]",
                   "[7-day direction]", "[Context this person logged]", "[Data quality]"):
        assert header in out


def test_no_tcm_vocab():
    out1 = digest.render_digest(FIXTURE_FEATURESET)
    out2 = digest.render_status(FIXTURE_NOT_READY)
    for ch in TCM_CHARS:
        assert ch not in out1, f"found banned char {ch!r} in render_digest output"
        assert ch not in out2, f"found banned char {ch!r} in render_status output"


def test_band_within():
    fs = _fs({"resting_hr": _metric(60, 60, 0.2, 0.0, 55, "within")})
    out = digest.render_digest(fs)
    assert "Within their usual range" in out


def test_band_modest():
    fs = _fs({"resting_hr": _metric(65, 60, 1.3, 8.3, 82, "modest")})
    out = digest.render_digest(fs)
    assert "Modestly above their usual" in out


def test_band_marked():
    fs = _fs({"resting_hr": _metric(75, 60, 2.5, 25.0, 99, "marked")})
    out = digest.render_digest(fs)
    assert "Well outside their usual range" in out


def test_no_context():
    fs = _fs({"resting_hr": _metric(60, 60, 0.2, 0.0, 55, "within")}, context=None)
    out = digest.render_digest(fs)
    assert "[Context" not in out


def test_insufficient_metric():
    fs = _fs({"resting_hr": _metric(60, 60, None, None, None, "unknown", insufficient=True)})
    out = digest.render_digest(fs)
    assert "no baseline comparison available for this metric yet" in out
    assert "robust z" not in out


def test_render_status_not_ready():
    out = digest.render_status(FIXTURE_NOT_READY)
    assert "14 days" in out
    assert "robust z" not in out


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} digest tests passed")
