"""Render a FeatureSet into the plain-English artefact handed to the LLM.

Pure functions: dict in, str out. No DB, no clock, no network, stdlib only.
MUST NOT contain or emit any TCM vocabulary — this is a neutral statement of facts about
numbers (see tests/test_digest.py for the banned-character check).
"""

MIN_DAYS = 14  # mirrors baseline.MIN_DAYS; digest doesn't import baseline to stay dependency-free
BAR_LEN = 14


def _num(value):
    """Round a raw metric float for display: whole numbers show as ints, else 1 decimal."""
    r = round(float(value), 1)
    return str(int(r)) if r == int(r) else str(r)


def _fmt_value(unit, value):
    """'{value}{unit}', except unit "count" gets thousands-comma with no unit suffix."""
    if value is None:
        return "no data"
    if unit == "count":
        return f"{int(round(value)):,}"
    return f"{_num(value)}{unit}"


def _duration_str(minutes):
    h, m = divmod(int(minutes), 60)
    return f"{h}h{m:02d}m"


def _clock_str(min_after_18):
    total = (18 * 60 + int(min_after_18)) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


def _direction(delta):
    return "above" if delta >= 0 else "below"


def _ord(n):
    """Percentile with a correct ordinal suffix: 82 -> '82nd', 7 -> '7th', 11 -> '11th'."""
    n = round(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _band_phrase(band, direction):
    if band == "within":
        return "Within their usual range"
    if band == "modest":
        return f"Modestly {direction} their usual"
    if band == "marked":
        return "Well outside their usual range"
    return None  # "unknown" -> no deviation language


def _recovery_hint(recovery_dir):
    if recovery_dir == "higher_worse":
        return "Higher = less recovered"
    if recovery_dir == "lower_worse":
        return "Lower = less recovered"
    return None


def _insufficient_bullet(m):
    return f"- {m['label']} {_fmt_value(m['unit'], m['today'])} — no baseline comparison available for this metric yet."


def _sleep_asleep_bullet(m):
    delta = m["median"] - m["today"]
    direction = _direction(-delta)  # today below median -> delta>0 -> "below"
    s = (f"- Sleep {_duration_str(m['today'])} — {_duration_str(abs(delta))} {direction} their "
         f"28-day median of {_duration_str(m['median'])}; {_ord(m['percentile'])} percentile.")
    phrase = _band_phrase(m["band"], direction)
    if phrase:
        s += f" {phrase}."
    return s


def _sleep_onset_bullet(m):
    delta = m["today"] - m["median"]
    direction = "later" if delta > 0 else "earlier"
    return (f"- Sleep timing: asleep {_clock_str(m['today'])}, {_duration_str(abs(delta))} {direction} than "
            f"their median sleep onset of {_clock_str(m['median'])}.")


def _simple_bullet(m):
    """recovery_dir is None and not a sleep_* special case: value + percentile + band phrase only."""
    phrase = _band_phrase(m["band"], _direction(m["pct_delta"] if m["pct_delta"] is not None else 0))
    phrase = phrase[0].lower() + phrase[1:] if phrase else "no usual-range comparison available"
    return f"- {m['label']} {_fmt_value(m['unit'], m['today'])} — {_ord(m['percentile'])} percentile; {phrase}."


def _generic_bullet(m):
    direction = _direction(m["pct_delta"])
    pct = round(abs(m["pct_delta"]))
    line = (f"- {m['label']} {_fmt_value(m['unit'], m['today'])} — {pct}% {direction} their 28-day median of "
            f"{_fmt_value(m['unit'], m['median'])}; robust z {m['z']:+.1f}; {_ord(m['percentile'])} percentile "
            f"of their own range.")
    phrase = _band_phrase(m["band"], direction)
    if phrase:
        line += f" {phrase}."
    hint = _recovery_hint(m["recovery_dir"])
    if hint:
        line += f" {hint}."
    return line


def _bullet(key, m):
    if m["today"] is None:
        return f"- {m['label']}: no value recorded for yesterday."
    if m["insufficient"]:
        return _insufficient_bullet(m)
    if key == "sleep_asleep_min":
        return _sleep_asleep_bullet(m)
    if key == "sleep_onset_min":
        return _sleep_onset_bullet(m)
    if m["recovery_dir"] is None:
        return _simple_bullet(m)
    return _generic_bullet(m)


def _dir7_sentence(m):
    trend = {1: "up", -1: "down", 0: "flat"}[m["dir7"]["slope_sign"]]
    return f"{m['label']}: 7-day median robust z {m['dir7']['z']:+.1f}, trending {trend}."


def _provenance(fs):
    w = fs["window"]
    return (
        f"[Provenance] Daily aggregates recorded by Apple Watch, read from HealthKit, exported {fs['export_ts']}.\n"
        f"Baseline window: {w['days']} days ending {w['end']}, {w['present']} of {w['days']} days present.\n"
        "These are overnight and daily summary values. No live measurement was taken for this reading.\n"
        "The HRV figure is SDNN derived from the optical sensor (pulse-rate variability), not from an ECG."
    )


def _baseline_section(fs):
    lines = ["[Yesterday vs this person's own baseline]"]
    lines += [_bullet(key, m) for key, m in fs["metrics"].items()]
    return "\n".join(lines)


def _dir7_section(fs):
    lines = ["[7-day direction]"]
    lines += [_dir7_sentence(m) for m in fs["metrics"].values() if m["dir7"]["z"] is not None]
    return "\n".join(lines)


def _context_section(fs):
    c = fs["context"]
    return (
        "[Context this person logged]\n"
        f'{c["date"]}: "{c["note"]}". Self-rated sleep quality {c["sleep_quality"]}/5, '
        f'energy {c["energy"]}/5, stress {c["stress"]}/5.'
    )


def _quality_section(fs):
    q = fs["quality"]
    if q["yesterday_missing"]:
        present_line = "Missing for yesterday: " + ", ".join(q["yesterday_missing"]) + "."
    else:
        present_line = f"All {len(q['yesterday_present'])} metrics present for yesterday."
    return (
        "[Data quality]\n"
        f"{present_line}\n"
        f"{q['gaps_7d']} gap(s) in the trailing 7 days. {q['gaps_28d']} gap(s) in the 28-day window."
    )


def render_digest(fs):
    """A READY FeatureSet -> the plain-English digest handed to the LLM. See module docstring."""
    sections = [_provenance(fs), _baseline_section(fs), _dir7_section(fs)]
    if fs["context"] is not None:
        sections.append(_context_section(fs))
    sections.append(_quality_section(fs))
    return "\n\n".join(sections)


def render_status(fs):
    """A NOT-READY / cold-start FeatureSet -> an onboarding progress view. Facts only, no
    deviation language, no advice."""
    present = fs["window"]["present"]
    filled = min(present, BAR_LEN)
    bar = "#" * filled + "-" * (BAR_LEN - filled)
    lines = [f"Baseline: {bar}  {present} / {MIN_DAYS} days", "", "What is here so far"]
    for m in fs["metrics"].values():
        median_str = _fmt_value(m["unit"], m["median"])
        lines.append(f"- {m['label']}: {m['n_window']} day(s) recorded so far, most recent "
                     f"{_fmt_value(m['unit'], m['today'])}, median so far {median_str}.")
    q = fs["quality"]
    if q["yesterday_missing"]:
        lines.append("Missing for yesterday: " + ", ".join(q["yesterday_missing"]) + ".")
    lines.append(f"{q['gaps_7d']} gap(s) in the trailing 7 days. {q['gaps_28d']} gap(s) in the 28-day window.")
    if not fs["ready"]:
        lines.append("")
        lines.append("Not enough of this person's own history has been recorded yet to compare "
                      "yesterday against a baseline.")
    if fs["gate_failures"]:
        lines.append("")
        lines.append("Why not ready yet:")
        lines += [f"- {g}" for g in fs["gate_failures"]]
    return "\n".join(lines)
