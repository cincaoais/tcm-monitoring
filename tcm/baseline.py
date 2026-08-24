"""Rolling-window robust statistics. Pure functions, stdlib only, no I/O, no clock.

Every deviation claim in the system is computed here and nowhere else. The three-thorough-tests
rule points at this module: if the arithmetic is wrong, the honesty claim is wrong.
"""
import bisect
import statistics

WINDOW_DAYS = 28
MIN_DAYS = 14
MAD_SCALE = 1.4826       # normal-consistency scaling for MAD
IQR_SCALE = 1.349        # normal-consistency scaling for IQR

# language bands — the ONLY place deviation thresholds live
BAND_MODEST = 1.0
BAND_MARKED = 2.0


def robust_stats(window):
    """window: list[float], len>=1, any order. Returns centre + scale with degenerate-safe fallback."""
    n = len(window)
    med = statistics.median(window)
    mad = statistics.median([abs(x - med) for x in window])
    scale = MAD_SCALE * mad
    source = "mad"
    if scale == 0:
        # low-variance metric: fall back to IQR/1.349
        if n >= 2:
            q = statistics.quantiles(window, n=4)  # [Q1, Q2, Q3]
            iqr = q[2] - q[0]
            scale = iqr / IQR_SCALE
            source = "iqr"
        if scale == 0:
            source = "none"
    return {
        "n": n,
        "median": med,
        "mad": mad,
        "scale": scale,
        "spread_degenerate": scale == 0,
        "spread_source": source,
    }


def robust_z(x, stats):
    """(x - median)/scale, or None if spread is degenerate (never an infinite z)."""
    if x is None or stats["spread_degenerate"]:
        return None
    return (x - stats["median"]) / stats["scale"]


def percentile_rank(x, window):
    """0..100: percentage of window values <= x (bisect over a sorted copy)."""
    if x is None or not window:
        return None
    s = sorted(window)
    return 100.0 * bisect.bisect_right(s, x) / len(s)


def pct_delta(x, median):
    """100*(x-median)/median, or None if median==0 or x is None."""
    if x is None or median == 0:
        return None
    return 100.0 * (x - median) / median


def band(z):
    """'within' | 'modest' | 'marked' | 'unknown'. |z|<1 within; 1..2 modest; >2 marked."""
    if z is None:
        return "unknown"
    a = abs(z)
    if a < BAND_MODEST:
        return "within"
    if a <= BAND_MARKED:
        return "modest"
    return "marked"


def direction_7d(recent7, stats28):
    """7-day median expressed as a robust-z against the 28-day window; slope reported as sign only.

    recent7: up to 7 recent daily values (may be shorter). Returns median7, its z, and slope sign.
    A slope on 7 noisy points never gets a number — only -1/0/1.
    """
    if not recent7:
        return {"median7": None, "z": None, "slope_sign": 0}
    m7 = statistics.median(recent7)
    z = robust_z(m7, stats28)
    slope_sign = 0
    if len(recent7) >= 2:
        try:
            slope = statistics.linear_regression(range(len(recent7)), recent7).slope
            slope_sign = (slope > 0) - (slope < 0)
        except statistics.StatisticsError:
            slope_sign = 0
    return {"median7": m7, "z": z, "slope_sign": slope_sign}


def metric_stats(today, window, recent7):
    """Full per-metric computation. `window` excludes the day under evaluation (`today`).

    Returns a dict with today, n_window, insufficient (n<MIN_DAYS), median, scale,
    spread_degenerate, z, pct_delta, percentile, band, dir7.
    An insufficient metric still reports median/range (for the status view) but band='unknown'
    and downstream code suppresses deviation language for it.
    """
    n = len(window)
    insufficient = n < MIN_DAYS
    if n == 0:
        return {
            "today": today, "n_window": 0, "insufficient": True,
            "median": None, "scale": None, "spread_degenerate": True,
            "z": None, "pct_delta": None, "percentile": None, "band": "unknown",
            "dir7": {"median7": None, "z": None, "slope_sign": 0},
        }
    st = robust_stats(window)
    z = robust_z(today, st)
    return {
        "today": today,
        "n_window": n,
        "insufficient": insufficient,
        "median": st["median"],
        "scale": st["scale"],
        "spread_degenerate": st["spread_degenerate"],
        "z": z,
        "pct_delta": pct_delta(today, st["median"]),
        "percentile": percentile_rank(today, window),
        "band": "unknown" if insufficient else band(z),
        "dir7": direction_7d(recent7, st),
    }
