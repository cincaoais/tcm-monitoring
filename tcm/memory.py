"""Deterministic 复诊 (follow-up) memory. No model call — this is computed, not summarised.

`history_digest` reads the `visits` and `metrics` tables and renders a plain-text
"[Prior visits]" block (via baseline.robust_stats/robust_z, the same math the reading itself
uses) that gets prepended to the next reading's model input.
"""
import json
from datetime import date, timedelta

from . import baseline
from . import db

_ADVICE_KEYS = ("diet", "routine", "rest", "exercise")


def _advice_text(advice, limit=3):
    """First item of each advice category, up to `limit`, joined with '; '."""
    if not isinstance(advice, dict):
        return "(no advice recorded)"
    items = []
    for key in _ADVICE_KEYS:
        v = advice.get(key)
        item = v[0] if isinstance(v, list) and v else (v if isinstance(v, str) and v else None)
        if item:
            items.append(str(item))
        if len(items) >= limit:
            break
    return "; ".join(items) if items else "(no advice recorded)"


def _window_stats(dated_values, end):
    """robust_stats over values dated in [end-27, end], or None if the window has no data."""
    start = end - timedelta(days=baseline.WINDOW_DAYS - 1)
    values = [v for d, v in dated_values if start <= d <= end]
    return baseline.robust_stats(values) if values else None


def _fmt_z(z):
    return "n/a" if z is None else f"{z:+.1f}"


def history_digest(conn, as_of, n: int = 3) -> str:
    """as_of: datetime.date (the day being read now). Returns a '[Prior visits]' text block for
    the last n visits (most recent first), or '' if there are no prior visits."""
    rows = conn.execute(
        "SELECT ts, reading_json FROM visits ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
    if not rows:
        return ""

    # Parse each core metric's series once; reused as both a "then" and "now" window source.
    series = {m: [(date.fromisoformat(d), v) for d, v in db.series(conn, m)]
              for m in db.CORE_METRICS}
    now_stats = {m: _window_stats(series[m], as_of) for m in db.CORE_METRICS}

    lines = ["[Prior visits]"]
    for row in rows:
        visit_date = date.fromisoformat(row["ts"][:10])
        k = (as_of - visit_date).days

        try:
            reading = json.loads(row["reading_json"])
            if not isinstance(reading, dict):
                reading = {}
        except (TypeError, ValueError):
            reading = {}

        summary = reading.get("tcm_pattern_summary") or "(no summary)"
        advice = _advice_text(reading.get("advice"))

        lines.append(f"{visit_date.isoformat()}, {k} days ago — read as: {summary}.")
        lines.append(f"  Advised: {advice}.")
        lines.append("  Since that visit (measured, not reported):")
        for metric in db.CORE_METRICS:
            then_stats = _window_stats(series[metric], visit_date)
            if then_stats is None or now_stats[metric] is None:
                continue
            meta = db.METRIC_META[metric]
            z_delta = baseline.robust_z(now_stats[metric]["median"], then_stats)
            lines.append(
                f"    {meta['label']}  median {then_stats['median']:.1f}{meta['unit']} "
                f"→ {now_stats[metric]['median']:.1f}{meta['unit']}   ({_fmt_z(z_delta)} z)")
        lines.append("  Note: association only. Nothing here shows the advice caused the change, "
                      "and days with logged")
        lines.append("  context are confounded.")

    return "\n".join(lines)
