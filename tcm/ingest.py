"""Parse Apple Health `export.xml` -> one value per day per metric -> upsert into db. stdlib only.

`aggregate_records` is the pure dict-in/dict-out core (no XML, no I/O) so a future JSON export
adapter can reuse it. Everything XML-specific (streaming, zip/dir lookup, ExportDate) lives around it.
"""
import statistics
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from tcm import db

# type -> (metric key, stored unit); median-per-day metrics
MEDIAN_TYPES = {
    "HKQuantityTypeIdentifierRestingHeartRate": (db.RESTING_HR, "bpm"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": (db.HRV_SDNN, "ms"),
    "HKQuantityTypeIdentifierRespiratoryRate": (db.RESP_RATE, "count/min"),
    "HKQuantityTypeIdentifierAppleSleepingWristTemperature": (db.WRIST_TEMP, "degC"),
}
# type -> (metric key, stored unit); sum-per-source-per-day, then max-across-sources (dedup multi-device)
DEDUP_TYPES = {
    "HKQuantityTypeIdentifierStepCount": (db.STEPS, "count"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": (db.ACTIVE_ENERGY, "kcal"),
}
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
TARGET_TYPES = set(MEDIAN_TYPES) | set(DEDUP_TYPES) | {SLEEP_TYPE}


def _parse_dt(s):
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")


def aggregate_records(records):
    """records: iterable of dicts (type,value,unit,startDate,endDate,sourceName[optional]).
    Returns list of {"date","metric","value","unit","source"} rows, one per (date, metric)."""
    medians = {}   # (date, metric) -> {"values":[...], "unit", "source"}
    dedup = {}     # (date, metric) -> {"sums": {source: total}, "unit"}
    nights = {}    # night_date iso -> {"asleep_min", "onset", "source"}
    seen = False

    for r in records:
        rtype = r.get("type")
        if rtype not in TARGET_TYPES:
            continue
        seen = True
        source = r.get("sourceName", "")

        if rtype in MEDIAN_TYPES:
            metric, unit = MEDIAN_TYPES[rtype]
            key = (r["startDate"][:10], metric)
            slot = medians.setdefault(key, {"values": [], "unit": unit, "source": source})
            slot["values"].append(float(r["value"]))
            slot["source"] = source
        elif rtype in DEDUP_TYPES:
            metric, unit = DEDUP_TYPES[rtype]
            key = (r["startDate"][:10], metric)
            slot = dedup.setdefault(key, {"sums": {}, "unit": unit})
            slot["sums"][source] = slot["sums"].get(source, 0.0) + float(r["value"])
        else:  # sleep
            value = r.get("value", "")
            if not value.startswith("HKCategoryValueSleepAnalysisAsleep"):
                continue
            start, end = _parse_dt(r["startDate"]), _parse_dt(r["endDate"])
            night = start.date() + timedelta(days=1) if start.hour >= 12 else start.date()
            onset = ((start.hour - 18) % 24) * 60 + start.minute
            slot = nights.setdefault(night.isoformat(), {"asleep_min": 0.0, "onset": None, "source": source})
            slot["asleep_min"] += (end - start).total_seconds() / 60
            slot["onset"] = onset if slot["onset"] is None else min(slot["onset"], onset)
            slot["source"] = source

    if not seen:
        raise ValueError("export has no records of the target HealthKit types (empty or wrong export)")

    rows = []
    for (d, metric), s in medians.items():
        rows.append({"date": d, "metric": metric, "value": statistics.median(s["values"]),
                     "unit": s["unit"], "source": s["source"]})
    for (d, metric), s in dedup.items():
        src, value = max(s["sums"].items(), key=lambda kv: kv[1])
        rows.append({"date": d, "metric": metric, "value": value, "unit": s["unit"], "source": src})
    for night, s in nights.items():
        rows.append({"date": night, "metric": db.SLEEP_ASLEEP, "value": s["asleep_min"],
                     "unit": "min", "source": s["source"]})
        rows.append({"date": night, "metric": db.SLEEP_ONSET, "value": s["onset"],
                     "unit": "min_after_18", "source": s["source"]})
    return rows


def iter_records(xml_fileobj):
    """Stream <Record> elements via ET.iterparse; yield attrib dicts. Clears the root's finished
    children after each Record so accumulated siblings don't pile up on a 175MB file."""
    context = ET.iterparse(xml_fileobj, events=("start", "end"))
    _, root = next(context)  # root = <HealthData>, from its start event
    for event, elem in context:
        if event == "end" and elem.tag == "Record":
            yield elem.attrib
            root.clear()


def read_export_date(path):
    """Return the ExportDate value trimmed to 'YYYY-MM-DD HH:MM', or None if absent."""
    with open_export(path) as f:
        for _, elem in ET.iterparse(f, events=("end",)):
            if elem.tag == "ExportDate":
                v = elem.attrib.get("value")
                return v[:16] if v else None
            elem.clear()
    return None


def open_export(path):
    """path: a .zip, a directory (export.xml directly inside or nested), or a direct export.xml path.
    Returns an open binary file object (context-manager) positioned at export.xml."""
    path = Path(path)
    if path.is_dir():
        direct = path / "export.xml"
        found = direct if direct.exists() else next(path.rglob("export.xml"), None)
        if found is None:
            raise FileNotFoundError(f"no export.xml under {path}")
        return open(found, "rb")
    if path.suffix.lower() == ".zip":
        zf = zipfile.ZipFile(path)
        name = next((n for n in zf.namelist() if n.rsplit("/", 1)[-1] == "export.xml"), None)
        if name is None:
            zf.close()
            raise FileNotFoundError(f"no export.xml in {path}")
        stream = zf.open(name)
        # closing the member stream must also release the archive handle, or the zip stays
        # locked on Windows
        orig_close = stream.close
        def _close():
            orig_close()
            zf.close()
        stream.close = _close
        return stream
    return open(path, "rb")


def ingest_path(conn, path):
    """Open the export, stream records, aggregate, upsert via db.upsert_metric. Idempotent (PK
    on (date, metric)). Returns {"rows","days","metrics","export_date"}."""
    export_date = read_export_date(path)
    with open_export(path) as f:
        rows = aggregate_records(iter_records(f))
    for row in rows:
        db.upsert_metric(conn, row["date"], row["metric"], row["value"], row["unit"], row["source"])
    conn.commit()
    return {
        "rows": len(rows),
        "days": len({r["date"] for r in rows}),
        "metrics": len({r["metric"] for r in rows}),
        "export_date": export_date,
    }
