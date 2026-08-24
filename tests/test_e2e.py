"""M7 end-to-end: full pipeline with a stub provider, plus the forced-violation fallback path.

Run: python tests/test_e2e.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import db, cli
from tcm import db as _db
from tests.fixtures import FIXTURE_FEATURESET


def test_happy_path_stub_records_ok_visit():
    conn = db.connect(":memory:")
    out = cli.run_reading(conn, FIXTURE_FEATURESET, provider="stub")
    assert out["status"] == "ok", out
    reading = out["reading"]
    assert reading["disclaimer"] == _db.DISCLAIMER
    assert reading["plain_summary"]
    row = conn.execute("SELECT validator_status, provider FROM visits").fetchone()
    assert row["validator_status"] == "ok"
    assert row["provider"] == "stub"


def test_forced_violation_lands_on_template_fallback():
    conn = db.connect(":memory:")

    bad = json.dumps({  # a texture-pulse claim — must be blocked every attempt
        "reading_title": "测试",
        "tcm_pattern_summary": "脉弦有力，肝气偏旺",
        "plain_summary": "你的数据显示偏离。",
        "basis": ["resting heart rate 61"],
        "confidence_note": "n",
        "advice": {"diet": ["a"], "routine": ["b"], "rest": ["c"], "exercise": ["d"]},
        "followup": {"what_to_watch": ["x"], "recheck_in_days": 7},
        "flags": [],
        "disclaimer": _db.DISCLAIMER,
    })

    def always_bad(digest, hist, profile, system_prompt, knowledge, provider):
        return bad

    out = cli.run_reading(conn, FIXTURE_FEATURESET, provider="stub", generate=always_bad)
    assert out["status"] == "blocked", out
    assert "texture_pulse" in out["violations"]
    # The invalid narrative must NEVER surface — fallback carries the disclaimer, not the bad text.
    assert _db.DISCLAIMER in out["fallback"]
    assert "脉弦" not in out["fallback"]
    row = conn.execute("SELECT validator_status, violations FROM visits").fetchone()
    assert row["validator_status"] == "blocked"
    assert "texture_pulse" in row["violations"]


def test_history_numbers_count_as_grounded():
    """Regression: numbers quoted from the 复诊 history block (e.g. the prior visit's date) are
    things the model WAS given — they must not trip the ungrounded_number check."""
    conn = db.connect(":memory:")
    conn.execute(
        "INSERT INTO visits(ts,digest,reading_json,validator_status,violations,provider,model) "
        "VALUES('2026-07-24T16:15:23','d','{\"tcm_pattern_summary\":\"平和\",\"advice\":{}}','ok','','stub','x')")
    conn.commit()

    seen = {}

    def echo_history(digest, hist, profile, system_prompt, knowledge, provider):
        seen["hist"] = hist
        reading = json.loads(cli.reasoning.generate_reading(
            digest, hist, profile, system_prompt, knowledge, "stub"))
        reading["basis"].append("上次问诊为2026-07-24，记录为平和。")  # date exists only in history
        return json.dumps(reading, ensure_ascii=False)

    out = cli.run_reading(conn, FIXTURE_FEATURESET, provider="stub", generate=echo_history)
    assert "2026-07-24" in seen["hist"], "test setup: prior visit must appear in history digest"
    assert out["status"] == "ok", out.get("violations")


def test_resolve_export_ts_prefers_newest_raw_zip():
    """Regression: with zips in data/raw/, resolve_export_ts must read the NEWEST zip — falling
    back to a stale ./export folder once pinned as_of to an old export and re-read an old day."""
    import io
    import tempfile
    import time
    import zipfile

    def make_zip(path, export_date):
        xml = (f'<?xml version="1.0"?><HealthData><ExportDate value="{export_date} +0800"/>'
               f'</HealthData>')
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("export.xml", xml)

    with tempfile.TemporaryDirectory() as tmp:
        old_raw, old_export = cli.RAW_DIR, cli.DEFAULT_EXPORT
        try:
            cli.RAW_DIR = tmp
            cli.DEFAULT_EXPORT = os.path.join(tmp, "nonexistent")
            make_zip(os.path.join(tmp, "a.zip"), "2026-07-24 11:05:35")
            time.sleep(0.05)  # ensure distinct mtimes
            make_zip(os.path.join(tmp, "b.zip"), "2026-08-02 22:59:01")
            assert cli.resolve_export_ts() == "2026-08-02 22:59"
        finally:
            cli.RAW_DIR, cli.DEFAULT_EXPORT = old_raw, old_export


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} e2e tests passed")
