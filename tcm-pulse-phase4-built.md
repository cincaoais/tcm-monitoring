---
name: tcm-pulse-phase4-built
description: TCM pulse v1 CLI is built and tested (95/95), real backfill ingested, baseline ready — only data collection remains
metadata:
  node_type: memory
  type: project
  originSessionId: 420cee18-6da0-4013-ba54-9fa3d05df32a
  modified: 2026-08-05T06:17:41.000Z
---

Phase 4 (coding) is **built and verified** on 2026-08-05. See [[tcm-pulse-project]] for the
locked decisions that led here and [[tcm-pulse-resources]] for the external repos.

## Verified state (as of 2026-08-05)

- **Offline test suite: 95/95 pass** (`python tests/run_all.py`) — plain-assert, no framework.
- **Ingest + backfill: done.** Two real Apple "Export All Health Data" bundles in `data/raw/`:
  `export-2026-07-24_1105.zip` and `export-2026-08-02_2259.zip` (raw is the append-only source
  of truth; `tcm.db` is a derived cache rebuilt by `tcm rebuild`).
- **Baseline: ready.** `tcm status` reports **27/14 baseline days** (28 days of rows for most
  metrics; wrist temperature 20 days). Reading is possible for 2026-08-01+.
- **Full pipeline works offline:** `tcm reading --provider stub` produces a validated 把脉 reading
  with 食疗/作息/休息/运动 advice and the wellness/no-diagnosis disclaimer.
- **Knowledge file (Spike 4): done** — `knowledge/measurable_pulses.md` + `NOTICE.md`,
  rate/rhythm/HRV only, no texture vocabulary.
- **Git:** repo exists on GitHub (`tcm-monitor`) but `main` has **no commits yet** — everything
  is untracked. Health data (`data/`, `export.zip`, `tcm.db`) is gitignored, never to be pushed.

## What remains: data collection only

Per the user (2026-08-05): "Most of them are done. Only left for the data collection."

- **Convergent check needs self-ratings.** `tcm converge` reports **4/14 usable days** — log
  daily with `tcm log --sleep N --energy N --stress N` until ≥14 usable days, then the Spearman
  check of system recovery direction vs. how the user actually felt means something.
- **Spike 3 (export cadence)** is a real-use judgment: after ~a week of use, decide whether
  manually tapping "Export All Health Data" before a reading is fine, or whether the $24.99
  Health Auto Export / a Shortcut is worth it. **Do not build automation into v1.**
- He will be back once the data has finished collecting; the next session should pick up with
  the logged self-ratings and the convergent check.

## Noted

- MEMORY.md's earlier "77/77" count is stale — the suite now runs 95 checks.
- Spike 0 (native export shape, ≥60 days history) and Spike 5 (headless `claude -p`) status was
  not re-verified in this session; the reading pipeline is confirmed via the stub provider.
