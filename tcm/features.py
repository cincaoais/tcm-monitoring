"""Build the FeatureSet dict that digest.py consumes. Pure read + stats glue, no writes.

Windowing: `window` = the 28 days strictly BEFORE as_of (the baseline excludes the day under
evaluation). `recent7` = the 7 trailing days INCLUDING as_of. See tests/fixtures.py for the
frozen output shape this must match.
"""
from datetime import timedelta

from . import baseline, db


def _dates(as_of, start, end):
    """as_of-start .. as_of-end inclusive, ascending. e.g. _dates(d, 28, 1) is the 28-day window."""
    return [(as_of - timedelta(days=n)).isoformat() for n in range(start, end - 1, -1)]


def build_featureset(conn, as_of, export_ts="") -> dict:
    """as_of: datetime.date. export_ts: 'YYYY-MM-DD HH:MM' string from the export (cli passes it)."""
    as_of_str = as_of.isoformat()
    window_dates = _dates(as_of, 28, 1)   # as_of-28 .. as_of-1 (excludes as_of)
    recent7_dates = _dates(as_of, 6, 0)   # as_of-6 .. as_of (includes as_of)

    metrics, n_recent7 = {}, {}
    yesterday_present, yesterday_missing = [], []
    resting_hr_window_present = 0

    for metric in db.ALL_METRICS:
        smap = {d: v for d, v in db.series(conn, metric)}
        today = smap.get(as_of_str)
        window_vals = [smap[d] for d in window_dates if d in smap]
        recent7_vals = [smap[d] for d in recent7_dates if d in smap]
        n_recent7[metric] = len(recent7_vals)

        if today is not None:
            yesterday_present.append(metric)
        elif smap:   # has history somewhere, just not on as_of
            yesterday_missing.append(metric)

        if metric == db.RESTING_HR:
            resting_hr_window_present = len(window_vals)

        if today is not None or window_vals:
            ms = baseline.metric_stats(today, window_vals, recent7_vals)
            meta = db.METRIC_META[metric]
            ms.update(label=meta["label"], unit=meta["unit"], recovery_dir=meta["recovery_dir"])
            metrics[metric] = ms

    empty = baseline.metric_stats(None, [], [])
    gate_failures = []
    for m in db.CORE_METRICS:
        ms = metrics.get(m, empty)
        n = ms["n_window"]
        if n < baseline.MIN_DAYS:
            gate_failures.append(f"{m}: {n}/{baseline.MIN_DAYS} days present "
                                  f"(need {baseline.MIN_DAYS - n} more)")
        if ms["today"] is None:
            gate_failures.append(f"{m}: yesterday's value missing")
        gaps7 = 7 - n_recent7.get(m, 0)
        if gaps7 > 2:
            gate_failures.append(f"{m}: {gaps7} gap(s) in the last 7 days (max 2)")

    return {
        "as_of": as_of_str,
        "export_ts": export_ts,
        "window": {"days": 28, "end": as_of_str, "present": resting_hr_window_present},
        "ready": gate_failures == [],
        "gate_failures": gate_failures,
        "metrics": metrics,
        "context": db.get_context(conn, as_of_str),
        "quality": {
            "yesterday_present": yesterday_present,
            "yesterday_missing": yesterday_missing,
            "gaps_7d": 7 - n_recent7.get(db.RESTING_HR, 0),
            "gaps_28d": 28 - resting_hr_window_present,
        },
    }
