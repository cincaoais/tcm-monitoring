"""Known-value + property checks for baseline.py. Run: python tests/test_baseline.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import baseline as b


def close(a, x):
    return math.isclose(a, x, rel_tol=1e-9, abs_tol=1e-9)


def test_robust_stats_known():
    st = b.robust_stats([10, 12, 14, 16, 18])
    assert st["median"] == 14
    assert close(st["mad"], 2.0)                 # median(|dev|) of [4,2,0,2,4]
    assert close(st["scale"], 1.4826 * 2)
    assert st["spread_degenerate"] is False
    assert st["spread_source"] == "mad"


def test_robust_z_and_band():
    st = b.robust_stats([10, 12, 14, 16, 18])
    assert close(b.robust_z(20, st), 6 / (1.4826 * 2))
    assert b.robust_z(None, st) is None
    assert b.band(0.5) == "within"
    assert b.band(1.0) == "modest"               # boundary: 1.0 is modest
    assert b.band(1.9) == "modest"
    assert b.band(2.0) == "modest"               # boundary: 2.0 is still modest
    assert b.band(2.1) == "marked"
    assert b.band(None) == "unknown"


def test_percentile_rank():
    w = [10, 12, 14, 16, 18]
    assert close(b.percentile_rank(14, w), 60.0)
    assert close(b.percentile_rank(18, w), 100.0)
    assert close(b.percentile_rank(9, w), 0.0)
    assert b.percentile_rank(None, w) is None


def test_pct_delta():
    assert close(b.pct_delta(20, 14), 100 * 6 / 14)
    assert b.pct_delta(5, 0) is None
    assert b.pct_delta(None, 14) is None


def test_mad_zero_fully_degenerate():
    st = b.robust_stats([5, 5, 5, 5])
    assert st["spread_degenerate"] is True
    assert st["spread_source"] == "none"
    assert b.robust_z(9, st) is None             # never an infinite z


def test_mad_zero_iqr_fallback():
    st = b.robust_stats([1, 5, 5, 5, 9])         # MAD==0 but IQR>0
    assert st["spread_degenerate"] is False
    assert st["spread_source"] == "iqr"
    assert st["scale"] > 0
    assert b.robust_z(9, st) is not None


def test_metric_stats_insufficient():
    ms = b.metric_stats(60, list(range(50, 60)), [58, 59, 60])   # 10-day window < 14
    assert ms["insufficient"] is True
    assert ms["band"] == "unknown"
    assert ms["median"] is not None              # still reports centre for the status view


def test_metric_stats_empty_window():
    ms = b.metric_stats(60, [], [])
    assert ms["n_window"] == 0
    assert ms["insufficient"] is True
    assert ms["median"] is None and ms["z"] is None


def test_metric_stats_full():
    window = [58, 57, 59, 60, 58, 56, 61, 59, 58, 57, 60, 59, 58, 57, 59, 58]  # 16 days
    ms = b.metric_stats(64, window, [64, 60, 59, 58, 59, 60, 61])
    assert ms["insufficient"] is False
    assert ms["z"] is not None
    assert ms["band"] in ("within", "modest", "marked")
    assert ms["dir7"]["z"] is not None


def test_direction_7d_sign():
    st = b.robust_stats([1, 2, 3, 4, 5, 6, 7, 8])
    assert b.direction_7d([1, 2, 3, 4, 5, 6, 7], st)["slope_sign"] == 1
    assert b.direction_7d([7, 6, 5, 4, 3, 2, 1], st)["slope_sign"] == -1
    assert b.direction_7d([3, 3, 3], st)["slope_sign"] == 0
    assert b.direction_7d([], st) == {"median7": None, "z": None, "slope_sign": 0}


def test_property_median_matches_stdlib():
    import statistics
    for seed in range(20):
        w = [((seed * 7 + i * 13) % 37) + 40 for i in range(28)]  # deterministic pseudo-series
        assert b.robust_stats(w)["median"] == statistics.median(w)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} baseline tests passed")
