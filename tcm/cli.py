"""把脉 — command-line orchestration. I/O at the edge; all logic lives in the pure modules.

Commands: ingest, rebuild, status, digest, reading, log, history, demo.
"""
import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import date, datetime

from tcm import db, ingest, features, digest as digest_mod, memory, reasoning, validator, harness

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "tcm.db")
RAW_DIR = os.path.join(ROOT, "data", "raw")
DEFAULT_EXPORT = os.path.join(ROOT, "export")  # the extracted native export lives here
SYSTEM_PROMPT = os.path.join(ROOT, "prompts", "system_v1.md")
KNOWLEDGE = os.path.join(ROOT, "knowledge", "measurable_pulses.md")

MAX_ATTEMPTS = 2  # attempt 1 + one correction retry, then deterministic fallback


# ---------- helpers ----------

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def default_as_of(conn, export_date=None):
    """The day being read = the most recent COMPLETE day, i.e. the latest resting-HR date strictly
    before the export day. The export day itself is partial (data dumped mid-day) and must never be
    read — this is the plan's 'read yesterday, not today' rule."""
    if export_date:
        row = conn.execute("SELECT MAX(date) d FROM metrics WHERE metric=? AND date<?",
                           (db.RESTING_HR, export_date)).fetchone()
    else:
        row = conn.execute("SELECT MAX(date) d FROM metrics WHERE metric=?",
                           (db.RESTING_HR,)).fetchone()
    return date.fromisoformat(row["d"]) if row and row["d"] else None


def resolve_export_ts():
    """Best-effort export timestamp for provenance; '' if not resolvable.

    data/raw/ holds zip ARCHIVES, so read the newest zip there (by mtime) — falling back to a
    stale ./export folder was a real bug: it pinned as_of to the old export's date and silently
    re-read an old day.
    """
    candidates = []
    if os.path.isdir(RAW_DIR):
        zips = [os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR) if f.lower().endswith(".zip")]
        if zips:
            candidates.append(max(zips, key=os.path.getmtime))
    candidates.append(DEFAULT_EXPORT)
    for p in candidates:
        try:
            ts = ingest.read_export_date(p)
            if ts:
                return ts
        except Exception:
            pass
    return ""


def build_fs(conn, as_of=None):
    export_ts = resolve_export_ts()
    export_date = export_ts[:10] if export_ts else None
    as_of = as_of or default_as_of(conn, export_date)
    if as_of is None:
        return None, None
    return features.build_featureset(conn, as_of, export_ts=export_ts), as_of


# ---------- the reading pipeline (testable core) ----------

def run_reading(conn, fs, *, provider="claude_code", generate=None, profile=None, record=True):
    """Deterministic-facts → LLM → validator → (reading | template fallback). Records a visit.

    `generate` is injectable for tests (defaults to reasoning.generate_reading). Returns a dict
    describing the outcome. The invalid model output is NEVER returned as the reading.
    """
    generate = generate or reasoning.generate_reading
    profile = profile or {"cycle_tracking": False}
    dgst = digest_mod.render_digest(fs)
    hist = memory.history_digest(conn, date.fromisoformat(fs["as_of"]))
    system_prompt = _read(SYSTEM_PROMPT)
    knowledge = _read(KNOWLEDGE)
    prompt_ver = reasoning.prompt_hash(system_prompt)

    violations = []
    raw = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        # On retry, append the exact violations to the digest so the model can correct itself.
        grounded = dgst
        if violations:
            grounded = dgst + "\n\n[Corrections required — the previous answer violated these and was rejected]\n- " \
                       + "\n- ".join(violations)
        raw = generate(grounded, hist, profile, system_prompt, knowledge, provider)
        # ground against EVERYTHING the model was given: digest + 复诊 history. A number from the
        # history block (e.g. the prior visit's date or medians) is not a fabrication.
        ok, violations = validator.validate(raw, dgst + ("\n\n" + hist if hist else ""), profile)
        if ok:
            reading = json.loads(raw)
            if record:
                _record_visit(conn, dgst, raw, "ok", [], provider, prompt_ver)
            return {"status": "ok", "reading": reading, "digest": dgst}

    # Two failures → discard model output entirely, print the deterministic template.
    fallback = validator.render_fallback(dgst, violations)
    if record:
        _record_visit(conn, dgst, raw, "blocked", violations, provider, prompt_ver)
    return {"status": "blocked", "fallback": fallback, "violations": violations, "digest": dgst}


def _record_visit(conn, dgst, reading_json, status, violations, provider, model):
    conn.execute(
        "INSERT INTO visits(ts,digest,reading_json,validator_status,violations,provider,model) "
        "VALUES(?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), dgst, reading_json, status,
         ",".join(violations), provider, model))
    conn.commit()


# ---------- rendering a reading for the terminal ----------

def format_reading(reading):
    a = reading.get("advice", {})
    lines = [
        f"  把脉 · {reading.get('reading_title', '')}",
        "",
        f"  {reading.get('tcm_pattern_summary', '')}",
        "",
        f"  {reading.get('plain_summary', '')}",
        "",
        "  依据:",
    ]
    lines += [f"    - {b}" for b in reading.get("basis", [])]
    for key, label in (("diet", "食疗"), ("routine", "作息"), ("rest", "休息"), ("exercise", "运动")):
        items = a.get(key, [])
        if items:
            lines.append(f"  {label}:")
            lines += [f"    - {it}" for it in items]
    fu = reading.get("followup", {})
    if fu.get("what_to_watch"):
        lines.append("  留意:")
        lines += [f"    - {w}" for w in fu["what_to_watch"]]
        lines.append(f"  复诊建议: {fu.get('recheck_in_days', 7)} 天后")
    if reading.get("flags"):
        lines.append("  提示:")
        lines += [f"    - {fl}" for fl in reading["flags"]]
    lines += ["", f"  {reading.get('disclaimer', '')}"]
    return "\n".join(lines)


# ---------- command handlers ----------

def _archive_source(path):
    """Copy/zip the export into data/raw/ as the append-only source of truth. Best-effort; returns
    the archive path or None. Skips work if an archive for this export already exists (keyed by the
    export date), so re-ingesting the same export doesn't re-zip 175 MB."""
    os.makedirs(RAW_DIR, exist_ok=True)
    stamp = (ingest.read_export_date(path) or "").replace(":", "").replace(" ", "_").replace("+", "")
    if str(path).lower().endswith(".zip"):
        # Key by EXPORT DATE, never by basename. Apple always names the download export.zip, so
        # keying by filename made every export after the first collide with data/raw/export.zip;
        # the exists-check then skipped the copy and ingest silently re-read the OLD archive.
        if not stamp:
            return None          # unidentifiable — ingest the source directly rather than guess
        dest = os.path.join(RAW_DIR, f"export-{stamp}.zip")
        if os.path.abspath(path) != os.path.abspath(dest) and not os.path.exists(dest):
            shutil.copy2(path, dest)
        return dest
    dest = os.path.join(RAW_DIR, f"export-{stamp or 'unknown'}.zip")
    if os.path.exists(dest):
        return dest
    xml = path
    if os.path.isdir(path):
        xml = next((os.path.join(r, "export.xml") for r, _, fs in os.walk(path)
                    if "export.xml" in fs), None)
    if not (xml and os.path.isfile(xml) and str(xml).endswith(".xml")):
        return None
    print("  archiving export.xml → data/raw/ (compressing, one moment)...")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(xml, arcname="export.xml")
    return dest


def cmd_ingest(args):
    conn = db.connect(DB_PATH)
    path = args.path or DEFAULT_EXPORT
    archive = None
    try:
        archive = _archive_source(path)
    except Exception as e:
        print(f"  (could not archive to data/raw, ingesting from source anyway: {e})")
    summary = ingest.ingest_path(conn, archive or path)  # ingest exactly what's archived
    conn.commit()
    if archive:
        print(f"archived → {os.path.relpath(archive, ROOT)}")
    print(f"ingested {summary['rows']} rows across {summary['days']} days, "
          f"{summary['metrics']} metrics (export {summary.get('export_date')})")


def cmd_rebuild(args):
    """Rebuild tcm.db purely from data/raw/ — the source of truth. Any ingest bug is retroactively
    fixable because the raw exports are kept forever."""
    sources = sorted(os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR)) if os.path.isdir(RAW_DIR) else []
    if not sources:
        print("data/raw/ is empty — run `tcm ingest <export>` first (it archives the export there).")
        return
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = db.connect(DB_PATH)
    total = 0
    for s in sources:
        try:
            total += ingest.ingest_path(conn, s)["rows"]
        except Exception as e:
            print(f"  skipped {os.path.basename(s)}: {e}")
    conn.commit()
    print(f"rebuilt tcm.db from {len(sources)} archive(s) in data/raw/, {total} rows")


def cmd_status(args):
    conn = db.connect(DB_PATH)
    fs, as_of = build_fs(conn)
    if fs is None:
        print("No data yet. Run `tcm ingest` on an Apple Health export first.")
        return
    if fs["ready"]:
        print(f"Baseline ready for {as_of}. Run `tcm reading` for a full 把脉 reading.\n")
    print(digest_mod.render_status(fs))


def cmd_digest(args):
    conn = db.connect(DB_PATH)
    fs, as_of = build_fs(conn, _opt_date(args))
    if fs is None:
        print("No data yet. Run `tcm ingest`.")
        return
    if not fs["ready"]:
        print(digest_mod.render_status(fs))
        return
    print(digest_mod.render_digest(fs))


def cmd_reading(args):
    conn = db.connect(DB_PATH)
    fs, as_of = build_fs(conn, _opt_date(args))
    if fs is None:
        print("No data yet. Run `tcm ingest`.")
        return
    if not fs["ready"]:
        print("No reading yet — not enough of your own history.\n")
        print(digest_mod.render_status(fs))
        return
    if args.dry_run:
        dgst = digest_mod.render_digest(fs)
        hist = memory.history_digest(conn, as_of)
        user_text = reasoning.build_user_text(dgst, hist, {"cycle_tracking": False})
        print("=== assembled model input (dry run — no call made) ===\n")
        print(user_text)
        return
    try:
        out = run_reading(conn, fs, provider=args.provider)
    except reasoning.ReasoningError as e:
        print(f"Model call failed (no visit recorded): {e}")
        return
    if out["status"] == "ok":
        print(format_reading(out["reading"]))
    else:
        print(out["fallback"])
        print(f"\n(The narrative layer was withheld for this reading — validator: "
              f"{','.join(out['violations'])}.)")


def cmd_log(args):
    conn = db.connect(DB_PATH)
    d = args.date or date.today().isoformat()
    conn.execute(
        "INSERT INTO context(date,note,sleep_quality,energy,stress) VALUES(?,?,?,?,?) "
        "ON CONFLICT(date) DO UPDATE SET note=excluded.note, sleep_quality=excluded.sleep_quality, "
        "energy=excluded.energy, stress=excluded.stress",
        (d, args.note, args.sleep, args.energy, args.stress))
    conn.commit()
    print(f"logged context for {d}")


def cmd_history(args):
    conn = db.connect(DB_PATH)
    as_of = default_as_of(conn) or date.today()
    block = memory.history_digest(conn, as_of)
    print(block or "No prior visits recorded yet.")


def cmd_demo(args):
    """Full sample reading on synthetic data, watermarked as fabricated."""
    from tests.fixtures import FIXTURE_FEATURESET
    conn = db.connect(":memory:")
    out = run_reading(conn, FIXTURE_FEATURESET, provider="stub", record=False)
    print("  ┌─────────────────────────────────────────┐")
    print("  │  DEMO — fabricated data, not a real read │")
    print("  └─────────────────────────────────────────┘\n")
    if out["status"] == "ok":
        print(format_reading(out["reading"]))
    else:
        print(out["fallback"])


def _print_report(rep):
    for k, v in rep.items():
        print(f"   {k}: {v}")


def cmd_selfcheck(args):
    conn = db.connect(DB_PATH)
    fs, as_of = build_fs(conn, _opt_date(args))
    if fs is None or not fs["ready"]:
        print("Need a ready baseline to run the harness. Try `tcm status`.")
        return
    system_prompt = _read(SYSTEM_PROMPT)
    knowledge = _read(KNOWLEDGE)
    run_ablation = args.ablation or not args.retest
    run_retest = args.retest or not args.ablation
    if run_ablation:
        print("== Ablation / confabulation (§7.3): a scrambled digest must change the reading ==")
        print(f"   (2 model calls, provider={args.provider})")
        _print_report(harness.ablation_check(fs, system_prompt, knowledge, provider=args.provider))
    if run_retest:
        print(f"\n== Test-retest (§7.2): {args.n} readings from one digest, measure stability ==")
        print(f"   ({args.n} model calls, provider={args.provider})")
        _print_report(harness.test_retest(fs, system_prompt, knowledge, n=args.n, provider=args.provider))


def cmd_converge(args):
    """§7.4 convergent check — free, deterministic, no model calls."""
    conn = db.connect(DB_PATH)
    rep = harness.convergent_check(conn)
    if rep["verdict"] == "insufficient_data":
        print(f"Convergent check: {rep['message']}")
        print("\nIt compares the system's recovery direction against how you actually rated your")
        print("energy, sleep and stress — the only check here that tests the readings against you.")
        return
    print(f"Convergent check (§7.4) — exploratory, n=1, {rep['n']} usable days\n")
    for field, e in rep["correlations"].items():
        if e.get("rho") is None:
            print(f"  {field:14} rho: n/a   ({e.get('note', '')})")
            continue
        verdict = "tracks expectation" if e["matches_expected"] else "does NOT track expectation"
        print(f"  {field:14} rho: {e['rho']:+.3f}  (n={e['n']}, expected {e['expected_sign']}) — {verdict}")
    print(f"\n  {rep['caveats']}")


def _opt_date(args):
    return date.fromisoformat(args.date) if getattr(args, "date", None) else None


# ---------- argparse ----------

def build_parser():
    p = argparse.ArgumentParser(prog="tcm", description="把脉 — personal Apple Watch wellness trends")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="ingest an Apple Health export (zip / dir / export.xml)")
    pi.add_argument("path", nargs="?", help="path to export (default: ./export)")
    pi.set_defaults(func=cmd_ingest)

    sub.add_parser("rebuild", help="rebuild tcm.db from data/raw/").set_defaults(func=cmd_rebuild)
    sub.add_parser("status", help="onboarding / baseline progress view").set_defaults(func=cmd_status)
    sub.add_parser("history", help="prior visits and what the numbers did since").set_defaults(func=cmd_history)
    sub.add_parser("demo", help="sample reading on fabricated data").set_defaults(func=cmd_demo)
    sub.add_parser("converge", help="§7.4 convergent check vs your own self-ratings (free, no model calls)"
                   ).set_defaults(func=cmd_converge)

    pd = sub.add_parser("digest", help="print the TCM-free facts digest")
    pd.add_argument("--date", help="read as of this date (YYYY-MM-DD)")
    pd.set_defaults(func=cmd_digest)

    pr = sub.add_parser("reading", help="full 把脉 reading")
    pr.add_argument("--date", help="read as of this date (YYYY-MM-DD)")
    pr.add_argument("--dry-run", action="store_true", help="show the assembled prompt, make no call")
    pr.add_argument("--provider", default="claude_code", help="claude_code (default) | stub")
    pr.set_defaults(func=cmd_reading)

    psc = sub.add_parser("selfcheck", help="live validation harness: ablation + test-retest (makes model calls)")
    psc.add_argument("--ablation", action="store_true", help="run only the ablation/confabulation check")
    psc.add_argument("--retest", action="store_true", help="run only the test-retest check")
    psc.add_argument("--n", type=int, default=5, help="test-retest sample size (default 5)")
    psc.add_argument("--provider", default="claude_code", help="claude_code (default) | stub")
    psc.add_argument("--date", help="run as of this date (YYYY-MM-DD)")
    psc.set_defaults(func=cmd_selfcheck)

    pl = sub.add_parser("log", help="log today's self-ratings (1-5) and a note")
    pl.add_argument("--sleep", type=int, dest="sleep")
    pl.add_argument("--energy", type=int)
    pl.add_argument("--stress", type=int)
    pl.add_argument("--note", default="")
    pl.add_argument("--date", help="date to log (default: today)")
    pl.set_defaults(func=cmd_log)
    return p


def main(argv=None):
    # This tool's output is Chinese + em-dashes; the Windows console defaults to cp1252 and mangles
    # both. Force UTF-8 so readings render correctly.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
