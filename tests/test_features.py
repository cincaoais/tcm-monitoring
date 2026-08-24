"""Tests for features.py. Run: python tests/test_features.py"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import db, features
from tests.fixtures import FIXTURE_FEATURESET

TOP_KEYS = set(FIXTURE_FEATURESET)
METRIC_KEYS = {"today", "n_window", "insufficient", "median", "scale", "spread_degenerate",
               "z", "pct_delta", "percentile", "band", "dir7", "label", "unit", "recovery_dir"}
SEED_METRICS = (db.RESTING_HR, db.HRV_SDNN, db.SLEEP_ASLEEP, db.STEPS)
BASE = {db.RESTING_HR: 60, db.HRV_SDNN: 50, db.SLEEP_ASLEEP: 400, db.STEPS: 5000}


def _seed(conn, as_of, n_days, include_today=True):
    """Insert n_days of consecutive synthetic rows ending at as_of (or as_of-1)."""
    end = as_of if include_today else as_of - timedelta(days=1)
    for i in range(n_days):
        d = (end - timedelta(days=i)).isoformat()
        for m in SEED_METRICS:
            db.upsert_metric(conn, d, m, BASE[m] + (i % 5) - 2, "", "test")


def test_ready():
    conn = db.connect(":memory:")
    as_of = date(2026, 3, 15)
    _seed(conn, as_of, 20)
    fs = features.build_featureset(conn, as_of, export_ts="2026-03-16 06:00")

    assert fs["ready"] is True
    assert fs["gate_failures"] == []
    assert TOP_KEYS <= set(fs)
    for m in (db.RESTING_HR, db.HRV_SDNN):
        ms = fs["metrics"][m]
        assert ms["insufficient"] is False
        assert ms["z"] is not None
        assert set(ms) == METRIC_KEYS
    conn.close()


def test_not_ready_sparse_history():
    conn = db.connect(":memory:")
    as_of = date(2026, 3, 15)
    _seed(conn, as_of, 9)
    fs = features.build_featureset(conn, as_of)

    assert fs["ready"] is False
    assert fs["gate_failures"] != []
    conn.close()


def test_not_ready_yesterday_missing():
    conn = db.connect(":memory:")
    as_of = date(2026, 3, 15)
    _seed(conn, as_of, 9, include_today=False)   # as_of's own row never written
    fs = features.build_featureset(conn, as_of)

    assert fs["ready"] is False
    assert any("yesterday's value missing" in g for g in fs["gate_failures"])
    conn.close()


def test_context():
    conn = db.connect(":memory:")
    as_of = date(2026, 3, 15)
    _seed(conn, as_of, 20)
    assert features.build_featureset(conn, as_of)["context"] is None

    conn.execute("INSERT INTO context(date, note, sleep_quality, energy, stress) VALUES (?,?,?,?,?)",
                 (as_of.isoformat(), "test note", 3, 3, 3))
    fs = features.build_featureset(conn, as_of)
    assert fs["context"] == {"date": as_of.isoformat(), "note": "test note",
                              "sleep_quality": 3, "energy": 3, "stress": 3}
    conn.close()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} features tests passed")
