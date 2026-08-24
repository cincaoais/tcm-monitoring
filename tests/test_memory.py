"""Known-value + property checks for memory.py. Run: python tests/test_memory.py"""
import json
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import db
from tcm import memory


DAY0 = date(2026, 5, 1)          # data start
END = date(2026, 6, 30)          # data end (~61 days, ~2 months)
SHIFT = date(2026, 6, 5)         # deliberate downward shift from this date on
AS_OF = date(2026, 6, 29)        # the "now" window [06-02..06-29] is almost entirely post-shift
VISIT1 = date(2026, 6, 1)        # "then" window [05-05..06-01] is entirely pre-shift
VISIT2 = date(2026, 6, 15)


def _seed_series(conn):
    """resting_hr + hrv_sdnn daily, both step down by a fixed amount from SHIFT onward."""
    d = DAY0
    i = 0
    while d <= END:
        noise = (i % 3) - 1                      # -1, 0, 1 repeating: keeps MAD > 0
        hr = 62 + noise + (-8 if d >= SHIFT else 0)
        hrv = 45 + noise + (-10 if d >= SHIFT else 0)
        db.upsert_metric(conn, d.isoformat(), db.RESTING_HR, hr, "bpm", "test")
        db.upsert_metric(conn, d.isoformat(), db.HRV_SDNN, hrv, "ms", "test")
        d += timedelta(days=1)
        i += 1


def _insert_visit(conn, visit_date, summary, advice):
    conn.execute(
        "INSERT INTO visits(ts, digest, reading_json, validator_status, violations, provider, model) "
        "VALUES (?,?,?,?,?,?,?)",
        (f"{visit_date.isoformat()} 08:00:00", "digest text",
         json.dumps({"tcm_pattern_summary": summary,
                     "advice": {"diet": advice[0], "routine": advice[1],
                                "rest": advice[2], "exercise": advice[3]}}),
         "ok", "[]", "test-provider", "test-model"))


def _seeded_conn():
    conn = db.connect(":memory:")
    _seed_series(conn)
    _insert_visit(conn, VISIT1, "气虚证候，脉细弱",
                   (["温补食材，如姜枣茶"], ["早睡，23点前入睡"], ["午间小憩15分钟"], ["八段锦"]))
    _insert_visit(conn, VISIT2, "阴虚内热",
                   (["少辛辣"], ["规律作息"], ["避免熬夜"], ["散步"]))
    return conn


def _z_for(digest_text, visit_date, label):
    """Pull the signed z (or 'n/a') off the metric line for a given visit block."""
    block = digest_text.split(visit_date.isoformat())[1]
    line = [l for l in block.splitlines() if label in l][0]
    m = re.search(r"\(([+-][\d.]+|n/a) z\)", line)
    return m.group(1)


def test_empty_db_returns_empty_string():
    conn = db.connect(":memory:")
    assert memory.history_digest(conn, AS_OF, n=3) == ""


def test_history_digest_shape():
    conn = _seeded_conn()
    text = memory.history_digest(conn, AS_OF, n=3)

    assert text.startswith("[Prior visits]")
    assert VISIT1.isoformat() in text
    assert VISIT2.isoformat() in text
    assert "days ago" in text
    assert "Since that visit (measured, not reported)" in text
    assert "association only" in text

    hr_label = db.METRIC_META[db.RESTING_HR]["label"]
    hrv_label = db.METRIC_META[db.HRV_SDNN]["label"]
    assert hr_label in text and hrv_label in text
    assert "→" in text
    assert re.search(r"\([+-][\d.]+ z\)", text)          # at least one real (non-n/a) z shown


def test_advice_and_summary_rendered():
    conn = _seeded_conn()
    text = memory.history_digest(conn, AS_OF, n=3)
    assert "气虚证候，脉细弱" in text
    assert "温补食材，如姜枣茶" in text


def test_z_delta_sign_matches_injected_shift():
    conn = _seeded_conn()
    text = memory.history_digest(conn, AS_OF, n=3)
    hr_label = db.METRIC_META[db.RESTING_HR]["label"]
    hrv_label = db.METRIC_META[db.HRV_SDNN]["label"]

    # VISIT1's "then" window is fully pre-shift; AS_OF's "now" window is almost fully post-shift.
    # Both metrics were shifted DOWN, so the now-median sits below the then-baseline -> z < 0.
    z_hr = _z_for(text, VISIT1, hr_label)
    z_hrv = _z_for(text, VISIT1, hrv_label)
    assert z_hr != "n/a" and float(z_hr) < 0
    assert z_hrv != "n/a" and float(z_hrv) < 0


def test_limits_to_n_visits():
    conn = _seeded_conn()
    text = memory.history_digest(conn, AS_OF, n=1)
    assert VISIT2.isoformat() in text            # most recent
    assert VISIT1.isoformat() not in text


def test_malformed_reading_json_falls_back():
    conn = db.connect(":memory:")
    _seed_series(conn)
    conn.execute(
        "INSERT INTO visits(ts, digest, reading_json, validator_status, violations, provider, model) "
        "VALUES (?,?,?,?,?,?,?)",
        (f"{VISIT1.isoformat()} 08:00:00", "d", "not json {{{", "ok", "[]", "p", "m"))
    text = memory.history_digest(conn, AS_OF, n=3)
    assert "(no summary)" in text
    assert "(no advice recorded)" in text


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # Windows console cp1252 can't print CJK/— by default
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} memory tests passed")

    print("\n--- sample rendered block ---\n")
    print(memory.history_digest(_seeded_conn(), AS_OF, n=3))
