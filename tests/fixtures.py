"""The FeatureSet contract, frozen as a fixture.

`features.build_featureset()` MUST produce exactly this SHAPE (same keys/types).
`digest.render_digest()` consumes it. `memory.py` reads visit rows, not this, but shares the
per-metric dict shape. This file is the single source of truth for the seam between those modules.

FeatureSet top-level keys:
    as_of        str   "YYYY-MM-DD" — the day being read (yesterday)
    export_ts    str   "YYYY-MM-DD HH:MM" — when the export was produced (from newest metric row / passed in)
    window       dict  {"days": int, "end": "YYYY-MM-DD", "present": int}
    ready        bool  all readiness gates passed
    gate_failures list[str]  human-readable reasons; empty iff ready
    metrics      dict  metric_key -> metric dict (only metrics that have any data appear)
    context      dict|None  {"date","note","sleep_quality","energy","stress"} (None if none logged)
    quality      dict  {"yesterday_present": [keys], "yesterday_missing": [keys],
                        "gaps_7d": int, "gaps_28d": int}

Each metric dict = baseline.metric_stats(...) output PLUS:
    label        str   e.g. "Resting heart rate"
    unit         str   e.g. "bpm"
    recovery_dir str|None   "higher_worse" | "lower_worse" | None
(so: today, n_window, insufficient, median, scale, spread_degenerate, z, pct_delta,
 percentile, band, dir7{median7,z,slope_sign}, label, unit, recovery_dir)
"""


def _metric(today, n_window, median, z, pct_delta, percentile, band, dir7_z, dir7_slope,
            label, unit, recovery_dir, insufficient=False, spread_degenerate=False):
    return {
        "today": today, "n_window": n_window, "insufficient": insufficient,
        "median": median, "scale": None if spread_degenerate else 3.0,
        "spread_degenerate": spread_degenerate, "z": z, "pct_delta": pct_delta,
        "percentile": percentile, "band": band,
        "dir7": {"median7": None, "z": dir7_z, "slope_sign": dir7_slope},
        "label": label, "unit": unit, "recovery_dir": recovery_dir,
    }


# A ready reading with all six metrics present, one logged context day, 2 gaps in the window.
FIXTURE_FEATURESET = {
    "as_of": "2026-08-13",
    "export_ts": "2026-08-14 06:12",
    "window": {"days": 28, "end": "2026-08-13", "present": 26},
    "ready": True,
    "gate_failures": [],
    "metrics": {
        "resting_hr":       _metric(61, 26, 58, 1.3, 5.17, 82, "modest", 0.8, 1,
                                    "Resting heart rate", "bpm", "higher_worse"),
        "hrv_sdnn":         _metric(38, 26, 48, -1.9, -20.83, 7, "modest", -1.1, -1,
                                    "Overnight HRV (SDNN)", "ms", "lower_worse"),
        "sleep_asleep_min": _metric(342, 26, 420, -1.6, -18.57, 4, "modest", None, -1,
                                    "Sleep", "min", "lower_worse"),
        "sleep_onset_min":  _metric(460, 26, 333, 1.5, None, 90, "modest", None, 1,
                                    "Sleep timing", "min_after_18", None),
        "steps":            _metric(4120, 26, 4500, -0.2, -8.44, 45, "within", None, 0,
                                    "Steps", "count", None),
        "active_energy":    _metric(310, 26, 340, -0.3, -8.82, 38, "within", None, 0,
                                    "Active energy", "kcal", None),
    },
    "context": {"date": "2026-08-13", "note": "late work, two drinks",
                "sleep_quality": 2, "energy": 2, "stress": 4},
    "quality": {
        "yesterday_present": ["resting_hr", "hrv_sdnn", "sleep_asleep_min",
                              "sleep_onset_min", "steps", "active_energy"],
        "yesterday_missing": [],
        "gaps_7d": 0,
        "gaps_28d": 2,
    },
}


# A cold-start / not-ready FeatureSet: insufficient history, gates failed.
FIXTURE_NOT_READY = {
    "as_of": "2026-02-10",
    "export_ts": "2026-02-11 07:00",
    "window": {"days": 28, "end": "2026-02-10", "present": 9},
    "ready": False,
    "gate_failures": ["resting_hr: 9/14 days present (need 5 more)",
                      "hrv_sdnn: 9/14 days present (need 5 more)"],
    "metrics": {
        "resting_hr": _metric(59, 9, 59, None, None, None, "unknown", None, 0,
                              "Resting heart rate", "bpm", "higher_worse", insufficient=True,
                              spread_degenerate=False),
        "hrv_sdnn":   _metric(52, 9, 52, None, None, None, "unknown", None, 0,
                              "Overnight HRV (SDNN)", "ms", "lower_worse", insufficient=True),
    },
    "context": None,
    "quality": {"yesterday_present": ["resting_hr", "hrv_sdnn"],
                "yesterday_missing": ["sleep_asleep_min", "steps"],
                "gaps_7d": 1, "gaps_28d": 19},
}
