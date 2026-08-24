"""SQLite store + shared constants. stdlib only.

`data/raw/` is the source of truth; this DB is a derived cache `tcm rebuild` can recreate.
"""
import sqlite3

# --- canonical metric keys (one row per (date, metric) in the metrics table) ---
RESTING_HR = "resting_hr"
HRV_SDNN = "hrv_sdnn"
SLEEP_ASLEEP = "sleep_asleep_min"      # total asleep, minutes
SLEEP_ONSET = "sleep_onset_min"        # onset clock time, minutes after 18:00 local (monotonic across a normal night)
STEPS = "steps"
ACTIVE_ENERGY = "active_energy"
RESP_RATE = "resp_rate"
WRIST_TEMP = "wrist_temp"

CORE_METRICS = (RESTING_HR, HRV_SDNN)   # the two that gate a reading
ALL_METRICS = (RESTING_HR, HRV_SDNN, SLEEP_ASLEEP, SLEEP_ONSET, STEPS,
               ACTIVE_ENERGY, RESP_RATE, WRIST_TEMP)

# display metadata + per-metric recovery direction (features.py owns the semantics; this is the table)
METRIC_META = {
    RESTING_HR:    {"label": "Resting heart rate",   "unit": "bpm",          "recovery_dir": "higher_worse"},
    HRV_SDNN:      {"label": "Overnight HRV (SDNN)",  "unit": "ms",           "recovery_dir": "lower_worse"},
    SLEEP_ASLEEP:  {"label": "Sleep",                 "unit": "min",          "recovery_dir": "lower_worse"},
    SLEEP_ONSET:   {"label": "Sleep timing",          "unit": "min_after_18", "recovery_dir": None},
    STEPS:         {"label": "Steps",                 "unit": "count",        "recovery_dir": None},
    ACTIVE_ENERGY: {"label": "Active energy",         "unit": "kcal",         "recovery_dir": None},
    RESP_RATE:     {"label": "Respiratory rate",      "unit": "count/min",    "recovery_dir": None},
    WRIST_TEMP:    {"label": "Wrist temperature",     "unit": "degC",         "recovery_dir": None},
}

# The verbatim wellness disclaimer. Emitted by the model, checked by validator, and used in the
# deterministic template fallback. Shared here so all three reference one string.
DISCLAIMER = ("本内容基于你自己的历史数据做趋势参考，属个人健康科普，"
              "并非医疗诊断，不能替代专业医疗意见；如有不适请就医。")

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    date TEXT, metric TEXT, value REAL, unit TEXT, source TEXT,
    PRIMARY KEY (date, metric)
);
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY, ts TEXT, digest TEXT, reading_json TEXT,
    validator_status TEXT, violations TEXT, provider TEXT, model TEXT
);
CREATE TABLE IF NOT EXISTS context (
    date TEXT PRIMARY KEY, note TEXT, sleep_quality INTEGER,
    energy INTEGER, stress INTEGER
);
"""


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_metric(conn, date, metric, value, unit, source):
    """Idempotent by (date, metric) — re-ingesting the whole export is absorbed for free."""
    conn.execute(
        "INSERT INTO metrics(date, metric, value, unit, source) VALUES (?,?,?,?,?) "
        "ON CONFLICT(date, metric) DO UPDATE SET "
        "value=excluded.value, unit=excluded.unit, source=excluded.source",
        (date, metric, value, unit, source))


def series(conn, metric):
    """All (date, value) rows for a metric, ascending by date."""
    return [(r["date"], r["value"]) for r in conn.execute(
        "SELECT date, value FROM metrics WHERE metric=? ORDER BY date", (metric,))]


def get_context(conn, date):
    r = conn.execute("SELECT * FROM context WHERE date=?", (date,)).fetchone()
    return dict(r) if r else None
