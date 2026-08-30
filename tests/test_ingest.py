"""Known-value checks for ingest.py. Run: python tests/test_ingest.py"""
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import db, ingest


def rec(type_, value, start, end=None, source="src", unit=""):
    return {"type": type_, "value": value, "unit": unit, "startDate": start,
            "endDate": end or start, "sourceName": source}


def test_resting_hr_and_hrv_median():
    records = [
        rec("HKQuantityTypeIdentifierRestingHeartRate", "70", "2026-01-29 08:00:00 +0800"),
        rec("HKQuantityTypeIdentifierRestingHeartRate", "74", "2026-01-29 20:00:00 +0800"),
        rec("HKQuantityTypeIdentifierRestingHeartRate", "72", "2026-01-29 12:00:00 +0800"),
        rec("HKQuantityTypeIdentifierHeartRateVariabilitySDNN", "40", "2026-01-29 09:00:00 +0800"),
        rec("HKQuantityTypeIdentifierHeartRateVariabilitySDNN", "50", "2026-01-29 21:00:00 +0800"),
    ]
    rows = {(r["date"], r["metric"]): r for r in ingest.aggregate_records(records)}
    assert rows[("2026-01-29", db.RESTING_HR)]["value"] == 72        # median of 70,74,72
    assert rows[("2026-01-29", db.RESTING_HR)]["unit"] == "bpm"
    assert rows[("2026-01-29", db.HRV_SDNN)]["value"] == 45           # median of 40,50


def test_steps_dedup_max_of_per_source_sum():
    records = [
        rec("HKQuantityTypeIdentifierStepCount", "5000", "2026-02-01 08:00:00 +0800", source="…iPhone"),
        rec("HKQuantityTypeIdentifierStepCount", "3000", "2026-02-01 18:00:00 +0800", source="…iPhone"),
        rec("HKQuantityTypeIdentifierStepCount", "9500", "2026-02-01 09:00:00 +0800", source="…Apple Watch"),
    ]
    rows = ingest.aggregate_records(records)
    steps = [r for r in rows if r["metric"] == db.STEPS]
    assert len(steps) == 1
    assert steps[0]["value"] == 9500          # max(8000 iPhone-sum, 9500 watch), not 17500
    assert steps[0]["source"] == "…Apple Watch"


def test_sleep_across_midnight():
    records = [
        rec("HKCategoryTypeIdentifierSleepAnalysis", "HKCategoryValueSleepAnalysisAsleepCore",
            "2026-08-12 23:10:00 +0800", "2026-08-12 23:59:00 +0800"),
        rec("HKCategoryTypeIdentifierSleepAnalysis", "HKCategoryValueSleepAnalysisAsleepDeep",
            "2026-08-13 00:30:00 +0800", "2026-08-13 06:40:00 +0800"),
        # Awake segment must be excluded entirely
        rec("HKCategoryTypeIdentifierSleepAnalysis", "HKCategoryValueSleepAnalysisAwake",
            "2026-08-13 03:00:00 +0800", "2026-08-13 03:05:00 +0800"),
    ]
    rows = {r["metric"]: r for r in ingest.aggregate_records(records)}
    assert rows[db.SLEEP_ASLEEP]["date"] == "2026-08-13"
    assert rows[db.SLEEP_ASLEEP]["value"] == 49 + 370   # 23:10-23:59 + 00:30-06:40
    assert rows[db.SLEEP_ONSET]["value"] == 310         # minutes_after_18 of 23:10 start


def test_tiny_real_format_xml_end_to_end():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
<ExportDate value="2026-07-24 11:05:35 +0800"/>
<Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="johannes's Apple Watch"
 unit="count/min" startDate="2026-01-29 20:17:55 +0800" endDate="2026-01-29 23:16:38 +0800" value="70"/>
</HealthData>"""
    rows = ingest.aggregate_records(ingest.iter_records(io.BytesIO(xml)))
    assert rows == [{"date": "2026-01-29", "metric": db.RESTING_HR, "value": 70.0,
                      "unit": "bpm", "source": "johannes's Apple Watch"}]


def test_empty_and_no_target_types_raise():
    try:
        ingest.aggregate_records([])
        assert False, "expected ValueError on empty input"
    except ValueError:
        pass
    try:
        ingest.aggregate_records([rec("HKQuantityTypeIdentifierBodyMass", "70", "2026-01-01 00:00:00 +0800")])
        assert False, "expected ValueError when no target types present"
    except ValueError:
        pass


def test_ingest_path_idempotent_via_directory():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
<ExportDate value="2026-07-24 11:05:35 +0800"/>
<Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Watch"
 unit="count/min" startDate="2026-01-29 20:17:55 +0800" endDate="2026-01-29 23:16:38 +0800" value="70"/>
<Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone"
 unit="count" startDate="2026-01-29 08:00:00 +0800" endDate="2026-01-29 08:10:00 +0800" value="1200"/>
</HealthData>"""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp) / "apple_health_export"
        export_dir.mkdir()
        (export_dir / "export.xml").write_bytes(xml)

        conn = db.connect(":memory:")
        summary1 = ingest.ingest_path(conn, export_dir)
        assert summary1["rows"] == 2
        assert summary1["days"] == 1
        assert summary1["metrics"] == 2
        assert summary1["export_date"] == "2026-07-24 11:05"

        count1 = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        assert count1 == 2

        summary2 = ingest.ingest_path(conn, export_dir)   # re-ingest same export
        count2 = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        assert count2 == count1 == 2                       # idempotent, no duplicate rows
        assert summary2["rows"] == 2


def _zip_with_export_date(path, export_date, value="70"):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
<ExportDate value="{export_date}"/>
<Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Watch"
 unit="count/min" startDate="2026-01-29 20:17:55 +0800" endDate="2026-01-29 23:16:38 +0800" value="{value}"/>
</HealthData>""".encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("apple_health_export/export.xml", xml)


def test_archive_source_keys_zip_by_export_date_not_filename():
    """Apple always names the download export.zip. Keying the archive by basename made every
    later export collide with the first, so ingest silently re-read the OLD export."""
    from tcm import cli
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw"
        raw.mkdir()
        old_src = Path(tmp) / "a" / "export.zip"
        new_src = Path(tmp) / "b" / "export.zip"
        old_src.parent.mkdir()
        new_src.parent.mkdir()
        _zip_with_export_date(old_src, "2026-08-10 00:44:11 +0800")
        _zip_with_export_date(new_src, "2026-08-30 22:49:52 +0800", value="61")

        orig = cli.RAW_DIR
        cli.RAW_DIR = str(raw)
        try:
            a1 = cli._archive_source(str(old_src))
            a2 = cli._archive_source(str(new_src))
        finally:
            cli.RAW_DIR = orig

        assert a1 != a2, f"two different exports shared one archive path: {a1}"
        got = ingest.read_export_date(a2)
        assert got.startswith("2026-08-30"), f"new export archived as {got!r} (stale archive returned)"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} ingest tests passed")
