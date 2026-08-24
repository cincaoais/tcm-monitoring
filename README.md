# 把脉 — personal Apple Watch wellness trends (v1)

A local command-line tool. It reads your own Apple Watch daily aggregates (resting heart rate,
overnight HRV SDNN, sleep, activity), compares **yesterday to your own rolling baseline** with
auditable arithmetic, renders those facts as a **TCM-free digest**, hands that to Claude behind a
swappable adapter, and prints a **把脉-flavoured wellness reading + 食疗/作息/休息/运动 advice** that
is forced through a deterministic output validator.

**Wellness and education only — never diagnosis.** It never claims to have palpated a pulse; the
watch measures rate, rhythm and the HRV family, nothing else. Single user, local only, stdlib-only
Python 3.12+ (tested on 3.13). No paid app, no server, no ML classifier.

## M0 — do this ONCE before any real reading (not code, a gate)
1. **Turn OFF the Claude "help improve Claude" training toggle** (claude.ai → Settings → Privacy).
   It ships **on**; on = up to 5-year retention, off = 30 days. Only the digest text (numbers and
   comparisons — no name, no identifiers, no raw series) ever leaves the machine.
2. Put an Apple **"Export All Health Data"** `export.zip` (or the extracted folder) where the tool
   can read it — default `./export`, or pass a path to `tcm ingest`.

## Commands
```
python -m tcm.cli ingest [PATH]     # parse export.xml/zip → daily rows (idempotent)
python -m tcm.cli rebuild           # wipe tcm.db and re-ingest from data/raw/ (raw is source of truth)
python -m tcm.cli status            # baseline progress / cold-start view (facts only)
python -m tcm.cli digest            # the TCM-free facts digest handed to the model
python -m tcm.cli reading           # full 把脉 reading (default provider: claude_code)
python -m tcm.cli reading --dry-run # show the assembled model input, make no call
python -m tcm.cli reading --provider stub   # full pipeline offline, zero model calls
python -m tcm.cli demo              # sample reading on fabricated data (watermarked)
python -m tcm.cli log --sleep 3 --energy 2 --stress 4 --note "..."   # daily self-ratings
python -m tcm.cli history           # prior visits + what the numbers did since (复诊)
python -m tcm.cli selfcheck         # live validation harness — ablation + test-retest (makes model calls)
python -m tcm.cli converge          # §7.4 convergent check vs your own self-ratings (free, no model calls)
```
Readings read **yesterday** (the export day is partial and is excluded automatically).

`tcm ingest` archives the export into `data/raw/` (as a compressed zip, the append-only source of
truth) and ingests from there; `tcm rebuild` reconstructs `tcm.db` from `data/raw/` alone, so any
ingest bug is retroactively fixable.

**`tcm selfcheck`** is the on-demand validation harness (§7.2/§7.3), not part of the offline test
suite because it calls the model. *Ablation* feeds a scrambled digest and checks the reading changes
materially (proves the narrative is tethered to your numbers, not decorative); *test-retest* runs one
digest N times and reports stability. `--ablation` / `--retest` / `--n K` to scope it.

**`tcm converge`** is the §7.4 convergent check: the Spearman correlation between the system's
recovery direction (HRV z minus resting-HR z) and your own `tcm log` self-ratings — the only check
that tests the readings against *how you actually felt*. Free and deterministic. It needs ~14+ logged
days before it reports a number, and it reports a null or contrary result plainly rather than burying
it. Exploratory, n=1, association only.

A `cycle_tracking` profile flag (default false) gates a hard validator rule: if ever set true,
stress/illness-adjacent framing is blocked until cycle-phase tagging exists (a prerequisite before
any second/family user, since the luteal resting-HR rise mimics the stress signal).

## Layout
`tcm/` — `ingest baseline features digest memory reasoning validator cli` (pure cores, I/O at the
edges). `knowledge/measurable_pulses.md` (+ `NOTICE.md`) — hand-authored rate/rhythm pulse notes,
no texture vocabulary. `prompts/system_v1.md`, `schema/reading.json`. `tests/` — plain-assert
checks, no framework: `python tests/run_all.py`.

`data/raw/*.zip` is kept forever as the source of truth; `tcm.db` is a derived cache `rebuild`
recreates. Out of scope for v1: ECG/RR intervals, live capture, export automation, multi-user, any
web/mobile UI, any adaptive/ML layer.
