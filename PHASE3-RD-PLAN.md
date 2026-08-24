# Phase 3 — R&D Plan / Implementation Blueprint

> Deliverable of the R&D PLANNING session (2026-07-23). Builds on `PHASE2-RESEARCH-CAPTURE.md`
> and the locked decisions in `PHASE3-PLANNING-PROMPT.md`. **No production code was written.**
> Phase 4 (coding execution) is a separate session; its handoff prompt is `PHASE4-CODING-PROMPT.md`.
>
> Read §12 (problems found in the locked decisions) before building — two of them change scope.

---

## 0. What v1 actually is, in one paragraph

A **local command-line tool on the Windows PC** that ingests daily Apple Watch aggregates
(resting HR, overnight HRV SDNN, sleep, activity) exported off the iPhone, computes how today
compares to **the user's own rolling baseline** using auditable arithmetic, renders those
comparisons as a **TCM-free natural-language digest of facts**, hands that digest to Claude
behind a swappable adapter with a curated measurable-pulse knowledge file, and prints a
**TCM-flavoured wellness reading plus 食疗/作息/休息/运动 advice** that has been forced through a
deterministic output validator. Each reading is recorded; the next reading is given a
deterministically-computed 复诊 summary of prior advice and what the numbers did since. It is
branded 把脉; it never claims to have palpated anything.

**Not in v1:** ECG, RR intervals, RMSSD, live capture, multi-user, any web/mobile UI, any
adaptive/learning layer, any vector database.

---

## 1. System architecture

Seven units, each independently testable, each a plain Python module with pure functions at its
core and I/O pushed to the edges. Data flows one direction; nothing calls backwards.

```
 iPhone/Watch                          Windows PC (all local)
┌─────────────┐  native Export All   ┌──────────────────────────────────────────────┐
│ HealthKit   │  Health Data → zip   │ data/raw/*.zip    (append-only archive)      │
│  ↑ Watch    │ ───────────────────▶ │        │                                     │
└─────────────┘   (cloud folder /    │        ▼  ingest.py  (export.xml → daily)   │
                   AirDrop / cable)   │                                              │
                                     │   tcm.db  metrics / visits / context         │
                                     │        │                                     │
                                     │        ▼  baseline.py → features.py          │
                                     │   FeatureSet (numbers + deviations + gates)  │
                                     │        │                                     │
                                     │        ▼  digest.py                          │
                                     │   digest: str   ← TCM-FREE, facts only       │
                                     │        │                                     │
                                     │        │  + memory.py → history_digest: str  │
                                     │        │  + knowledge/measurable_pulses.md   │
                                     │        ▼  reasoning.py  (TCMReasoningAdapter)│
                                     │   raw model JSON                             │
                                     │        │                                     │
                                     │        ▼  validator.py  ── FAIL ──▶ template │
                                     │   TCMReading (validated)          fallback   │
                                     │        │                                     │
                                     │        ▼  cli.py → printed reading + visit   │
                                     └──────────────────────────────────────────────┘
```

| Unit | Does | Consumes | Produces | Depends on |
|---|---|---|---|---|
| `ingest.py` | Parse `export.xml` from the zip → daily metric rows; upsert | raw `export.zip` | rows in `metrics` | stdlib only |
| `baseline.py` | Rolling-window robust statistics. **Pure, no I/O.** | list of (date, value) | median / MAD / robust-z / percentile / 7-day slope | stdlib only |
| `features.py` | Assemble today's feature set; apply readiness gates | db | `FeatureSet` dict | `baseline` |
| `digest.py` | Render facts as natural language. **Pure.** | `FeatureSet` | digest string | stdlib only |
| `memory.py` | 复诊 summary of prior visits + measured change since | db | history digest string | `baseline` |
| `reasoning.py` | The `TCMReasoningAdapter`; calls the model | digest, history, prompt, knowledge | raw JSON string | subprocess / provider |
| `validator.py` | Schema + deny-lists + basis-grounding. **Pure.** | raw JSON, digest | `(ok, violations[])` | stdlib only |
| `cli.py` | Commands, printing, orchestration | — | — | all of the above |

**Design rule that makes this testable:** the four units marked *pure* (`baseline`, `digest`,
`validator`, and the parsing core of `ingest`) take data in and return data out with no database,
no network, no clock. They are where the logic lives and where every self-check points.

**The load-bearing separation:** the digest contains **no TCM vocabulary at all**. It is a
neutral statement of facts about numbers. All TCM framing lives in the system prompt and the
knowledge file. Consequence: swapping the provider, or changing the framing entirely, never
touches the signal layer — and the signal layer can be verified by someone who knows nothing
about TCM.

### Dependency policy

`ponytail:` v1 is **Python 3.12+, standard library only** — `sqlite3`, `statistics`, `bisect`,
`json`, `datetime`, `subprocess`, `re`, `argparse`. No numpy, no pandas, no scipy, no vector DB, no
web framework, no ORM. NeuroKit2 enters only at the gated ECG milestone (§10), and only inside that
one module, in its own virtual environment. Rationale in §12.2 and §3.1.

*Why 3.12 specifically:* `statistics.linear_regression` (the 7-day slope) needs 3.10, and
`statistics.correlation(method='ranked')` — Spearman, which §7.4's convergent check needs — needs
3.12. Both otherwise cost hand-rolled code for no benefit.

---

## 2. The v1 data pipeline, concretely

### 2.1 What is collected

Daily aggregates only. Sample-level data is not needed for v1 and is not stored.

| Metric | HealthKit type | Why | Notes |
|---|---|---|---|
| Resting heart rate | `HKQuantityTypeIdentifierRestingHeartRate` | Core deviation signal | One value/day, Apple-computed |
| HRV SDNN | `HKQuantityTypeIdentifierHeartRateVariabilitySDNN` | Core autonomic signal | **PPG-derived PRV, mostly overnight — not ECG RR.** Label as such everywhere |
| Sleep duration + stages | `HKCategoryTypeIdentifierSleepAnalysis` | Trend signal per rule 15 | Derive: total asleep, bedtime, wake time |
| Step count | `HKQuantityTypeIdentifierStepCount` | Activity confound control | |
| Active energy | `HKQuantityTypeIdentifierActiveEnergyBurned` | Activity confound control | |
| Respiratory rate | `HKQuantityTypeIdentifierRespiratoryRate` | Secondary, optional | Include if exporter provides it |
| Wrist temperature | `HKQuantityTypeIdentifierAppleSleepingWristTemperature` | Secondary, optional | **Never framed as fever** (rule 15) |

Explicitly **not** collected in v1: blood oxygen, workout detail, location, cycle tracking. ECG is
not collected in v1 either, but Apple's native export bundles its voltage CSVs at no extra cost —
which is why the later ECG milestone needs no new transport (§10).

### 2.2 Transport — decided (revised 2026-07-24: free native export primary)

**Apple's built-in "Export All Health Data" → zip onto the PC → `ingest.py` parses
`export.xml` directly.** Free, no third-party app on the phone, and the same export bundles the
ECG voltage CSVs for the later milestone. This replaces the earlier plan to pay for Health Auto
Export up front; see §12.9 for the reasoning and the tradeoff accepted.

- **How the zip reaches the PC:** AirDrop to a Mac then copy, or a cable copy, or drop it in any
  cloud-synced folder (Dropbox / Google Drive / OneDrive). The tool watches a folder and ingests
  any new `export.zip`.
- **What's in it:** `export.xml` (every HealthKit record, including resting HR, HRV SDNN, sleep
  analysis, steps, active energy, respiratory rate, wrist temperature) plus an
  `electrocardiograms/` folder of per-ECG CSVs carrying the full ~512 Hz voltage series. So a
  single free mechanism covers both v1 and the ECG milestone.
- **The parser:** streaming `xml.etree.ElementTree.iterparse` over `export.xml`, filtering to the
  handful of `HKQuantityTypeIdentifier*` / `HKCategoryTypeIdentifierSleepAnalysis` types in §2.1
  and upserting daily aggregates. Apple's export is sample-level, so `ingest.py` aggregates to one
  value per day per metric (resting HR and HRV are already daily-ish; steps/energy sum per day;
  sleep rolls up to total-asleep + onset + wake). This is ~40–60 lines. `apple-health-pro`
  (MIT, a desktop CSV splitter for the same zip) is a fine offline inspection aid, but it is **not
  a pipeline dependency** — adding a second manual GUI step is more friction than parsing the zip
  directly.

*The cost of "free" — stated plainly:* Apple's export is **manual and whole-database**. Every
export re-dumps the entire history (can be hundreds of MB and take minutes to build on-device).
That is ideal, once, for the backfill; it is heavy to repeat daily. v1 accepts this because
readings are on-demand and the user is present anyway — see §2.4.

*Paid upgrade, deferred not designed-out:* if manual re-export friction becomes real, buy **Health
Auto Export – JSON+CSV** ($24.99 lifetime) for automated incremental JSON to a synced folder, or
build a free Apple Shortcut that pushes just the daily aggregates. Both are convenience upgrades to
the *ongoing* leg only, and both feed the same `ingest.py` (it takes a dict / a row stream, so the
source is interchangeable). Decide after feeling the pain, not before. §12.9 records the confirmed
Health Auto Export JSON schema so this swap needs no fresh research.

### 2.3 Backfill — done once, first

The native export is at its best here: one export yields the **entire** history of resting HR, HRV,
sleep and activity in a single file, free, with no date-range ceiling to fight. That is what makes
a personal baseline exist on day one instead of in three weeks (§12.1). Do this before writing any
baseline code — it is also Spike 0, the file whose real field names the parser is written against.

### 2.4 Timing and the sync-latency reality

Three confirmed iOS constraints, all pointing the same way:

- **HealthKit is unreadable while the phone is locked.** Health data is in iOS's "Protected Unless
  Open" class — access is relinquished ~10 minutes after lock and does not return until the next
  unlock. (This bites any *automated* exporter; a manual native export, done with the phone in
  hand and unlocked, sidesteps it entirely — a quiet point in the free path's favour.)
- **iOS decides when a background automation actually runs**, not the app; no guaranteed fixed-time
  execution, and Low Power Mode degrades it further.
- **Watch→iPhone sync is opportunistic**, with no API to hurry it.

So an unattended daily export at an exact time is **not** reliably achievable by any tool, paid or
free. The design does not need it:

1. **Readings read *yesterday*, not today.** Export in the morning after the phone has been unlocked
   and had time to reconcile last night's sleep and HRV. Nothing depends on last night's data being
   present within minutes.
2. **Ingest is idempotent and additive.** Every export is re-parsed and upserted by `(date,
   metric)`. Because Apple's export is the whole database each time, re-ingesting is *entirely*
   overlapping data — which the upsert absorbs for free. A missed period is fixed by simply
   exporting again; there is no catch-up logic, no state machine, no "last successful sync" pointer
   to get wrong.
3. **Missing data is reported, never imputed.** `features.py` counts present days; the digest
   states completeness; readings are gated on it.
4. **Raw files are the source of truth**, kept forever in `data/raw/`. `tcm.db` is a derived cache
   that `cli.py rebuild` can reconstruct from scratch. Any ingest bug is fixable retroactively.

### 2.5 Store

One SQLite file, `tcm.db`, via stdlib `sqlite3`. Three tables, `CREATE TABLE IF NOT EXISTS`, no
migration framework.

```sql
metrics (date TEXT, metric TEXT, value REAL, unit TEXT, source TEXT,
         PRIMARY KEY (date, metric))          -- upsert target; one row per metric per day

visits  (id INTEGER PRIMARY KEY, ts TEXT, digest TEXT, reading_json TEXT,
         validator_status TEXT, violations TEXT, provider TEXT, model TEXT)

context (date TEXT PRIMARY KEY, note TEXT, sleep_quality INTEGER,
         energy INTEGER, stress INTEGER)      -- user-logged, optional; the convergent-check data
```

`context` is the cheapest high-value table in the system: it is both the confound annotation
("two drinks, late work") that keeps the reading honest and the self-report series that §7's
convergent validation needs. Phase 2 §10 called this the actual moat. It is three integers and a
string.

---

## 3. Feature computation and the digest

### 3.1 Baseline math

All in `baseline.py`, all pure functions, all stdlib.

- **Window:** trailing 28 days ending yesterday, excluding the day under evaluation.
- **Minimum data:** ≥14 days present in the window, else the metric is marked `insufficient` and
  is reported as a bare number with no deviation claim.
- **Centre:** median (`statistics.median`). Robust to the travel/illness/alcohol outliers that
  will absolutely occur.
- **Spread:** MAD × 1.4826 (normal-consistent scaling), so `robust_z = (x − median) / (1.4826·MAD)`.
  - If MAD == 0 (rare, low-variance metrics), fall back to IQR/1.349 via
    `statistics.quantiles`; if that is also 0, report the raw delta only and set
    `spread_degenerate = True`. **Never divide by zero, never silently emit an infinite z.**
- **Percentile rank:** position of today's value among the window's values. Reported alongside z
  because a percentile is intuitive where a z-score is not.
- **Percent delta vs median:** the readable form the digest leads with ("12% above your usual").
- **7-day direction:** median of the trailing 7 days expressed as a robust-z against the 28-day
  window. Reported as direction + magnitude band only. `statistics.linear_regression` slope is
  computed but reported only as a sign — a slope on 7 noisy points does not deserve a number.
- **Language bands** (the only place thresholds live):

  | \|robust z\| | Band | Digest wording |
  |---|---|---|
  | < 1.0 | within | "within your usual range" |
  | 1.0 – 2.0 | modest | "modestly above/below your usual" |
  | > 2.0 | marked | "well outside your usual range" |

- **Direction semantics are per-metric**, not global: for HRV, lower = less recovered; for resting
  HR, higher = less recovered. `features.py` owns this mapping so the digest never has to reason.

**Why stdlib is enough:** median, quantiles, mean, stdev, correlation and linear_regression are
all in `statistics`. MAD and percentile-rank are three lines each. The dataset is ~30 floats.
Importing pandas to take a median of 28 numbers is the exact over-engineering this project can
least afford, because every added dependency is another thing between the user and an auditable
number.

### 3.2 Readiness gates (`features.py`)

A reading is produced only when **all** hold; otherwise `cli.py reading` refuses and prints
`status` instead:

1. ≥14 days present in the 28-day window for **both** resting HR and HRV SDNN (the two core
   metrics).
2. Yesterday's resting HR and HRV are present.
3. The window is not >40% gaps in the trailing 7 days.

Failing gate → explicit message naming what is missing and how many days remain. Never a
degraded-but-presented reading.

### 3.3 The digest — exact format handed to the model

Deterministic templates. **No TCM vocabulary. No interpretation. No advice.** Numbers, comparisons,
provenance, gaps.

```
[Provenance] Daily aggregates recorded by Apple Watch, read from HealthKit, exported 2026-08-14 06:12.
Baseline window: 28 days ending 2026-08-13, 26 of 28 days present.
These are overnight and daily summary values. No live measurement was taken for this reading.
The HRV figure is SDNN derived from the optical sensor (pulse-rate variability), not from an ECG.

[Yesterday vs this person's own baseline]
- Resting heart rate 61 bpm — 8% above their 28-day median of 58 bpm; robust z +1.3;
  82nd percentile of their own range. Modestly above their usual. Higher = less recovered.
- Overnight HRV (SDNN) 38 ms — 21% below their 28-day median of 48 ms; robust z -1.9;
  7th percentile. Well outside their usual range. Lower = less recovered.
- Sleep 5h42m — 1h18m below their 28-day median of 7h00m; 4th percentile. Well outside usual.
- Sleep timing: asleep 01:40, 2h07m later than their median sleep onset of 23:33.
- Steps 4,120 — 45th percentile; within their usual range.
- Active energy 310 kcal — 38th percentile; within their usual range.

[7-day direction]
Resting heart rate trending up (7-day median +0.8 z vs the 28-day window).
Overnight HRV trending down (7-day median -1.1 z). Sleep duration trending down.

[Context this person logged]
2026-08-13: "late work, two drinks". Self-rated sleep quality 2/5, energy 2/5, stress 4/5.

[Data quality]
All six metrics present for yesterday. No gaps in the trailing 7 days. 2 gaps in the 28-day window.
```

Rules the digest generator must obey, each with a self-check:
- Every number that appears is one the code computed. No rounding that changes a band.
- A metric with `insufficient` history appears as a bare value with an explicit
  "no baseline comparison available for this metric yet".
- The provenance block is **mandatory and unconditional** — it is what keeps the 把脉 branding
  honest (§4.4).
- Absent context or self-ratings → the section is omitted, never filled with a guess.

---

## 4. The LLM layer

### 4.1 The adapter

```python
# reasoning.py — the TCMReasoningAdapter, per locked decision 13
def generate_reading(digest: str,
                     history_digest: str,
                     profile: dict,
                     system_prompt: str,
                     knowledge: str,
                     provider: str = "claude_code") -> str:
    """Returns the raw model response text. Never interprets it — validator.py does that."""
```

**The Claude implementation — confirmed viable on the subscription.** Shell out to the `claude`
binary in headless mode; it authenticates with the existing Pro/Max OAuth login and draws on
subscription usage rather than API credits:

```
claude -p <digest+history>
  --append-system-prompt-file prompts/system_v1.md
  --output-format json
  --json-schema schema/reading.json        # returns a validated `structured_output` field
  --model claude-sonnet-5
  --disallowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Agent"
```

Notes that shape the code:
- `--json-schema` gives schema-validated structured output *at the CLI level*, so `validator.py`'s
  check 1 (parse and schema) becomes a cheap second line of defence rather than the only one.
  Checks 2–7 are still entirely ours — no provider validates semantics.
- **There is no single "no tools" flag.** Tools must be disabled explicitly by name, and this
  should be asserted in `test_reasoning.py`, because a reasoning call that can read the filesystem
  is a different and much larger thing than the one this design describes.
- **Do not use the Claude Agent SDK here.** It requires `ANTHROPIC_API_KEY` (its own docs state
  Anthropic does not support claude.ai login for SDK-built products), and everything it adds — the
  agent loop, built-in tools, sessions, hooks — is precisely what this call must not have.
- **Handle the rate-limit failure path.** Pro/Max enforces a rolling 5-hour session window plus a
  weekly cap. One or two short calls a day will realistically never approach it, but the script
  must treat a non-zero exit as a normal outcome: retry with backoff, then fail visibly without
  recording a visit. Exact headless-mode behaviour on limit-hit is undocumented — find out by
  handling it, not by assuming it.

`ponytail:` the adapter is a **function signature plus a provider string**, not a class hierarchy
— one implementation exists, and an abstract base class with one subclass is the abstraction the
Phase 2 sketch was warning against, not the one it was asking for. The swap requirement is fully
satisfied: adding DeepSeek means adding one function and one `elif`, and nothing upstream of
`reasoning.py` knows a provider exists. Upgrade path if a third provider ever lands: a dict of
`{name: callable}`.

The contract that makes providers interchangeable:
- Input is **plain text** (digest + history + prompt + knowledge). No Claude-specific XML, no MCP,
  no tool definitions, no multi-turn state.
- Output is **one JSON object**. Nothing else.
- **Memory is app-side.** The model receives `history_digest`, a deterministically-composed
  summary. It never sees a chat log and has no session continuity. A provider swap loses nothing.

### 4.2 Knowledge grounding — **changed after firsthand inspection of the repo**

A single curated file, `knowledge/measurable_pulses.md` (~1–2 KB), injected wholesale into the
system prompt. It covers only pulse concepts defined by **beat rate or beat timing** — 数 (rapid),
迟 (slow), 结 (irregular pauses), 代 (regular intermittent pauses), 促 (rapid with pauses). Texture
pulses, compound pulses containing a texture component, and all tongue material are absent by
construction.

*This is the strongest guardrail in the system:* the model is not asked to avoid texture
vocabulary it has been shown — it is never shown it. §12.2 explains why this replaces the planned
vector store.

**The plan's source for this file has changed, and this matters.** Locked decision 13 names
`jangviktor-web/nihaixia`'s 「脉舌速查」 pulse table as the asset to extract. A direct read of the
repo (commit `ec03c59`) found:

- 「脉舌速查」 **is not a section heading** — it is loose prose shorthand. The cited line range
  6097–6545 is the `## 六经辨证诊断公式·临床速查` section. The actual pulse content is
  `### 脉诊速查` at **lines 6378–6404**, plus a tongue section and a pulse/tongue conflict table —
  **59 lines, ~2.1 KB total**, not a 450-line reference.
- The 8 + 8 entry count is correct, but each "entry" is a **three-cell table row of 10–25
  characters**, not a prose entry.
- **All 16 rows are texture pulses**: 浮, 浮缓, 浮紧, 大/洪大, 弦, 浮缓/弱, 微细/沉, 微浮, 浮弦, 沉细,
  弦数, 沉弦, 浮大, 弦缓, 浮紧有力, 微细欲绝. Applying the mandated measurability filter to this
  asset yields **an empty file**. 数 appears only fused to a texture character (弦数); 迟, 结, 代 and
  促 do not appear in the section at all.
- **No `LICENSE` file ships in the repo.** MulanPSL-2.0 is asserted in the README footer prose and
  by a badge linking to a file that does not exist. It is a claim, not a grant artifact.

**Resolution — write the file ourselves, informed by the source, citing it.** Do not copy text.
The genuinely measurable material does exist in the repo, but as scattered prose in
`modules/04_jingui.md` (the only place with numeric rate definitions — 数脉×7, 迟脉×3, 代脉×3) and
`modules/03_yian.md` (arrhythmia case discussion) — roughly 30 lines across six files. Read those
passages, then hand-author ~1–2 KB of original description of the five measurable pulse concepts.
This is simultaneously the laziest and the safest option:

| | Extract-and-filter (planned) | Hand-author from reading (chosen) |
|---|---|---|
| Output after filtering | Empty — the asset is all texture | The five concepts that actually apply |
| Parser needed | Yes, for a table that yields nothing usable | No |
| Licence exposure | Verbatim Chinese prose under an unevidenced grant | Our own words; ideas are not copyrightable |
| Texture leak risk | Filter must be right at extraction | Nothing to leak — written from a clean sheet |

Attribution stays: `knowledge/NOTICE.md` records nihaixia as the consulted source, the commit SHA,
the specific files read, and the licence ambiguity found. The project's own wellness disclaimer
layers on top.

**One classical passage is worth the trip on its own.** The 代脉 description in
`modules/04_jingui.md` defines the pulse by *counting beats between pauses* ("允许心脏跳五十四下，
停一下" — 54 beats then one pause is normal; every 5th beat pausing is not). That is a
beats-between-pauses ratio — a rhythm statistic that beat-interval data can genuinely compute. It
is the one place where a classical pulse concept and this project's measurable data actually meet,
and it is a natural fit for the ECG milestone (§10). Note it; do not build on it in v1, which has
no beat-level data.

### 4.3 System prompt — structure

Provider-agnostic plain text, versioned in `prompts/system_v1.md`, hashed into each visit record
so a reading can always be traced to the prompt that produced it.

Sections, in order:
1. **Role.** A TCM-informed wellness companion writing for one person about their own trends.
2. **What you have been given** — an explicit, closed list: rate/rhythm/HRV-family daily
   aggregates, compared to this person's own baseline. Nothing else exists.
3. **What you do not have** — enumerated so the absence is salient: no pulse palpation, no
   pressure/depth/width/tension/texture, no tongue, no complexion, no inquiry beyond what is in
   the digest, no lab values, no history you were not handed.
4. **Hard prohibitions.** No named disease. No diagnosis, prognosis or treatment. No 证型 label
   asserted as fact. No texture pulse. No tongue. No herb, formula, or dosage. No pregnancy. No
   mortality/critical-illness framing. No claim that a measurement was taken live.
5. **Permitted register.** TCM wellness vocabulary and the rate/rhythm pulse terms in the
   knowledge file, used as *tendency* language ("偏…倾向"), always hedged, always attached to a
   specific number from the digest.
6. **Grounding rule.** Every item in `basis[]` must restate a fact from the digest. Inventing or
   extrapolating a number is the single worst failure mode.
7. **Advice constraints.** 食疗 / 作息 / 休息 / 运动 only. Everyday, low-risk, reversible actions.
   No supplements, no herbs, no fasting, no medical instruction. 2–4 items per category, concrete
   and specific to the digest.
8. **复诊.** Reference the history digest explicitly: acknowledge what was advised, state what the
   numbers did since, without claiming the advice caused it.
9. **Output.** The JSON schema, verbatim, with the instruction to emit that object and nothing else.

### 4.4 Output schema

```json
{
  "reading_title": "string, ≤ 24 chars",
  "tcm_pattern_summary": "string, hedged tendency language, ≤ 120 chars",
  "plain_summary": "string, one paragraph, no TCM vocabulary — the same claim in plain words",
  "basis": ["string, each restating one fact from the digest", "..."],
  "confidence_note": "string — what this reading is and is not based on",
  "advice": {
    "diet":     ["string", "..."],
    "routine":  ["string", "..."],
    "rest":     ["string", "..."],
    "exercise": ["string", "..."]
  },
  "followup": {
    "what_to_watch": ["string", "..."],
    "recheck_in_days": 7
  },
  "flags": ["string — e.g. a trend worth raising with a doctor"],
  "disclaimer": "fixed verbatim string, checked by the validator"
}
```

`plain_summary` exists as a **honesty forcing function**: any claim that cannot survive being
restated without TCM vocabulary was never a claim about the data. It is also what a family member
would read.

### 4.5 The output validator — the enforcement layer

`validator.py`, pure function, `validate(raw: str, digest: str) -> (ok, violations)`. Seven checks,
in order, all deterministic:

1. **Parse & schema.** Valid JSON, all required keys, correct types, string-length and array-length
   caps. Reject unknown top-level keys.
2. **Texture-pulse deny-list.** Reject any pulse-texture reference. **Match on pulse-context
   bigrams, not bare characters** — `弦脉`/`脉弦`/`脉象弦`, `滑脉`/`脉滑`, `涩脉`/`脉涩`, `浮脉`/`脉浮`,
   `沉脉`/`脉沉`, `细脉`/`脉细`, `紧脉`/`脉紧`, `洪脉`/`脉洪`, `虚脉`, `实脉`, plus `指下`, `脉位`,
   `脉力`, `脉体`, `举按`, `寸关尺`. A naive single-character deny-list would reject the innocent
   `仔细`, `沉睡`, `浮躁`, `滑雪` — the test corpus must contain those as must-pass cases.
3. **Disease / diagnosis deny-list.** Named conditions (糖尿病, 高血压, 冠心病, 心脏病, 房颤, 心律失常,
   甲亢, 贫血, 肺炎, 感冒, 发烧/发热, 抑郁症, 焦虑症, 癌 …, and the English equivalents) and
   diagnostic verbs (诊断, 确诊, 患有, 病因, 治疗, 疗程).
4. **Hard-excluded topics** (rule 15, structurally impossible rather than discouraged):
   pregnancy (怀孕/妊娠/早孕/pregnan*), mortality and critical illness (死亡/猝死/危重/寿命/
   mortality/life expectancy), and — as a v1 tightening — `上火` (rated unsupported) and `痰湿`
   (weak indirect proxy only). See §12.8.
5. **Herb / prescription ban.** Formula and preparation words (方剂, 汤, 丸, 散, 膏, 冲剂), herb
   names, and any dosage pattern `\d+\s*(克|g|钱)`. This is the LingdanLLM line, and it is not
   close to it — it is the line itself.
6. **Basis grounding.** Extract every number from `basis[]` and `plain_summary`; assert each
   appears in the digest text. A number the model was not given is a fabrication, and this catch is
   nearly free. Percentages computed *from* given numbers are the one allowed exception — permit a
   short whitelist of derived forms, and log rather than reject on near-misses so the rule can be
   tuned against real output.
7. **Disclaimer present, verbatim**, and `plain_summary` non-empty.

**Failure policy — the part that makes rule 15 structural:**

```
attempt 1 → violations → retry once, appending the exact violations to the prompt
attempt 2 → violations → DISCARD the model output entirely.
            Print the deterministic template reading: the digest's facts, restated,
            plus generic non-personalised wellness advice, plus:
            "The narrative layer was withheld for this reading (validator: <codes>)."
            Record both attempts in `visits` with validator_status='blocked'.
```

The invalid text is **never displayed**, not even marked as invalid. A blocked reading is a
visible, logged event — if it happens often, the prompt is wrong and the counter says so.

### 4.6 How the 把脉 hook and honest output coexist (unknown #4)

Locked decision 18 keeps 把脉 as branding. Four independent layers hold the line, and the
branding touches none of them:

| Layer | What it does | Can it be talked out of? |
|---|---|---|
| Corpus filter | The model never sees texture-pulse vocabulary (§4.2) | No — it is absent |
| System prompt | Enumerates what it does not have; prohibits the rest (§4.3) | Yes, in principle |
| Validator | Blocks texture, disease, excluded topics, ungrounded numbers (§4.5) | No — deterministic |
| Mandatory provenance | Every reading states it is based on overnight and daily summary values, not a live capture | No — generated by code, not the model |

So 把脉 survives as **ritual, register, and a permitted vocabulary subset** (数/迟/结/代/促 are
genuinely measurable and genuinely classical). What it never becomes is a claim.

The residual risk is not the model — it is the user. See §12.4.

---

## 5. Onboarding and the baseline period

Two paths, chosen automatically by how much history the backfill import produced.

**Path A — backfill succeeded (≥14 days present in the 28-day window).** There is no waiting
period. The first run produces a real reading. See §12.1 — this is a change from the assumption
in locked decision 11, and it is the single biggest schedule win available.

**Path B — cold start.** `cli.py status` is the entire pre-baseline product:

```
Baseline: ████████░░░░░░  9 / 14 days     (5 more days of data needed)

What is here so far
  Resting heart rate   57–63 bpm over 9 days (median 59)
  Overnight HRV SDNN   41–66 ms over 9 days (median 52)
  Sleep                6h10m–8h05m (median 7h12m)
  Gaps                 2 days missing: 2026-08-04, 2026-08-07

No reading yet. With 9 days there is not enough of your own history to say what is normal
for you, and normal varies about elevenfold between people — so a reading now would be
comparing you to strangers. Ranges above are facts, not interpretation.

  tcm log --sleep 3 --energy 4 --stress 2 --note "..."     (30 seconds, improves every future reading)
  tcm demo                                                  (see a sample reading on fake data)
```

What makes the wait tolerable, in order of effect:
1. **A progress bar with a real number.** The wait is finite and visible.
2. **Facts are still shown.** Ranges and medians are honest with 9 days; interpretation is not.
3. **`tcm log` gives the user something to do daily** that measurably improves the eventual
   output — and is the convergent-validation data (§7.4).
4. **`tcm demo`** renders a full sample reading on synthetic data, watermarked `DEMO — fabricated
   data`, so the destination is concrete from day one.
5. **The refusal is explained**, in one honest sentence. This is the trust-building moment: a
   product that declines to guess is more credible at day 30 than one that guessed on day 1.

Pre-baseline, the permitted output is exactly: raw values, ranges, medians, gaps, streaks. No
deviation language, no TCM vocabulary, no advice.

---

## 6. The 复诊 memory loop and record-keeping

**Memory is app-side, deterministic, and computed — not remembered.** `memory.py` composes the
history digest from the `visits` and `metrics` tables. The model gets a summary; it never gets a
transcript, and there is no summarisation model call to drift.

For each of the last 3 visits:

```
[Prior visits]
2026-08-01, 13 days ago — read as: 气机偏于亢奋倾向 (resting HR modestly up, HRV modestly down).
  Advised: earlier bedtime; reduce evening caffeine; light walking instead of hard training;
           20-minute wind-down.
  Since that visit (measured, not reported):
    Resting heart rate  median 58 bpm → 60 bpm   (+0.4 z)
    Overnight HRV SDNN  median 51 ms  → 44 ms    (-0.9 z)
    Sleep duration      median 7h05m  → 6h20m    (-1.1 z)
    Sleep onset         median 23:20  → 00:55    (95 min later)
  Note: association only. Nothing here shows the advice caused the change, and days with
  logged context (2 of 13) are confounded.

2026-07-18, 27 days ago — ...
```

The "since that visit" block is **computed by `baseline.py`** from stored daily values — the model
cannot get it wrong, and it is what turns a chat feature into a record. The caveat line is
generated by code and is not optional.

**Outcome records.** `tcm history` prints the same thing for the user: every reading, the advice
given, and what the numbers did after. That, plus reflection, is the whole self-improvement layer
for v1 — per Phase 2 §7, adaptive/RL personalisation is not merely unbuilt but *contraindicated*
at one-data-point-per-visit density. Noted as a future direction if the system ever moves to
daily JITAI-style triggers.

---

## 7. Validation without ground truth

There is no correctness to measure (κ≈0.34, no labels). These five checks measure the things that
*can* be measured, and the `status` output states the epistemics in one line so the user is never
misled about which is which.

1. **Deterministic-layer correctness.** Golden-file tests on `digest.py`; property tests on
   `baseline.py` against synthetic series with known median/MAD/percentile; a ~25-case corpus for
   `validator.py` containing both must-block outputs (invented 弦脉, a named disease, a herb dose,
   a fabricated number, a pregnancy hint) and must-pass ones (the innocent `仔细`/`沉睡`/`滑雪`
   false-positive traps). This layer *does* have ground truth and must be exactly right.

2. **Test–retest self-consistency.** Run one fixed digest through the model 5×. Compare the
   direction of `tcm_pattern_summary`, the advice categories, and the flags. Report agreement.
   Run at build time and after **every** prompt change — a prompt edit that halves consistency
   should be visible immediately.

3. **Ablation / confabulation check** — *the most important one, and cheap.* Feed a **scrambled**
   digest (deviations inverted: HRV high instead of low, resting HR down instead of up). The
   reading must change materially and in the correct direction. If a scrambled digest produces a
   similar reading, the narrative is untethered from the data and the whole layer is decorative —
   exactly the failure Phase 2 §3e warned about. This is the single strongest available evidence
   that the system is doing anything at all. Automate it; run it on every prompt change.

4. **Convergent check (weeks, n=1).** `tcm log` collects sleep-quality / energy / stress 1–5 daily.
   After ~6 weeks, compute Spearman correlation (`statistics.correlation` on ranks, no scipy)
   between the system's recovery-direction score and self-rated energy. Report as exploratory,
   n=1, with the confounds named. A positive correlation is encouraging; a null result is
   informative and must be reported, not buried.

5. **What is never claimed.** No accuracy figure, no diagnostic performance, no comparison to a
   practitioner. The `status` line: *"This system can be self-consistent and personal to you. It
   cannot be correct, because there is nothing to be correct against."*

**Menstrual-cycle confounding (unknown #6).** Not applicable to the v1 solo user, and building
cycle logic for a user who does not need it is speculative work. What v1 does instead, in ~10
lines: a `profile.cycle_tracking` flag defaulting to false, and a **hard gate** — if it is ever
set true, illness/stress-adjacent framing is disabled until cycle-phase tagging exists. The
luteal-phase resting-HR rise (~3.5 bpm) is the same direction and magnitude as the "physiological
stress" signal and is genuinely indistinguishable from it without phase information. This gate is
a prerequisite for family expansion, listed in §9 as such.

---

## 8. Privacy

- **Before any real data flows** (M0, a gate not a task): turn the Claude consumer "help improve
  Claude" training toggle **off**. It ships on, applies to Claude Code under a Pro/Max login, and
  the difference is 5-year retention versus 30 days. Verify it, do not assume it.
- All health data stays on the local machine: `data/raw/`, `tcm.db`. Nothing is uploaded except
  the digest text sent to the model — which is deliberately just numbers and comparisons, with no
  name, no identifiers, no location, no raw timeseries.
- The cloud-synced transport folder holds health exports. Acceptable for solo use; note it as a
  third party holding the data.
- **API + Zero-Data-Retention migration trigger — decide once, act automatically:** the moment a
  second person's data enters the system, or a reading is shared outside the household. Family use
  is the trigger, not a later reconsideration. On the API, training-off is the default and ZDR is
  available; the cost is small (§9 handoff) and the discipline is not negotiable for someone else's
  health data.

---

## 9. Build sequence, milestones, and test plan

**Sequencing principle: the baseline is wall-clock-gated only if the backfill fails, so do the
backfill first and the question resolves on day one.** A dense native-export backfill (§12.1)
removes the wait entirely; a sparse one starts the clock. Either way, run it before writing
baseline code.

| # | Milestone | Done when | Self-check left behind |
|---|---|---|---|
| **M0** | Privacy + transport | Training toggle verified off; **one real native `export.zip` on the PC**; full-history backfill export done | — (a gate, not code) |
| **M1** | Ingest + store | `tcm ingest` parses `export.xml` from the real zip and aggregates to daily rows; `tcm rebuild` reconstructs the DB from `data/raw/` | `test_ingest.py` — real `export.xml` sample → expected daily rows; malformed/empty input rejected loudly |
| **M2** | Baseline + features | `tcm status` prints the §5 view from real data | `test_baseline.py` — synthetic series with known median/MAD/percentile; MAD==0 and short-window paths |
| **M3** | Digest | `tcm digest` prints the §3.3 block | `test_digest.py` — golden file; every band boundary; missing-metric and no-context paths |
| **M4** | Knowledge file | `knowledge/measurable_pulses.md` hand-authored per §4.2, `NOTICE.md` present | `test_knowledge.py` — asserts **no texture character appears in the file at all** |
| **M5** | Reasoning adapter | `tcm reading --dry-run` shows the exact assembled prompt; a live call returns JSON | `test_reasoning.py` — a stub provider; asserts the digest is passed through unmodified |
| **M6** | Validator | Blocks every case in the corpus, passes every clean one | `test_validator.py` — the ~25-case corpus of §7.1 including false-positive traps |
| **M7** | End-to-end reading + visits | `tcm reading` produces a validated reading and records a visit | `test_e2e.py` — stubbed provider, fixed digest → recorded visit; forced-violation path lands on the template fallback |
| **M8** | 复诊 loop | Second reading includes the §6 history block with computed deltas | `test_memory.py` — two synthetic visits → expected deltas |
| **M9** | Validation harness | Test–retest and ablation scripts runnable on demand | The ablation check itself (§7.3) |
| **M10** | *(gated, later)* Guided ECG | §10 — only after Spikes 1 and 2 succeed (voltage present, RMSSD stable) | — |

Test-plan rule (`ponytail`): every non-trivial unit leaves **one runnable check** — plain
`assert`-based, no framework, no fixtures. The three that must be genuinely thorough are
`baseline`, `digest`, and `validator`, because they are what the honesty claim rests on. A stub
provider makes the whole pipeline testable offline with zero model calls; only M9 needs live calls.

**Prerequisites before any second user (family):** per-person keying on every table, the
`cycle_tracking` gate implemented rather than stubbed, and the API/ZDR migration of §8. Not v1.

---

## 10. The guided-ECG reading — designed, gated, not built

This is the "real reading" and it stays out of v1 by locked decision 16. Design so that Phase 5
is assembly, not rethinking:

**The blocking unknown is resolved, and the answer is yes — for free.** Apple's native "Export All
Health Data" (the v1 transport, §2.2) ships an `electrocardiograms/` folder of per-ECG CSVs
carrying the **full raw voltage series**, not just the classification, at the watch's native
sampling rate. So the ECG milestone reuses the exact transport v1 already uses — no new export
path, no paid app, no native app. *(Read the sampling rate from the CSV header rather than
hard-coding ~512 Hz; it is a hardware characteristic Apple reports, not a constant to assume.)*
*(Health Auto Export's JSON `ecg` array carries the same `voltageMeasurements` if the ongoing leg
is ever upgraded to it — recorded in §12.9 — but v1's free native export already reaches ECG, so
nothing is gated on that purchase.)*

**Flow.** `tcm reading --live` → prompts the user to open Apple's ECG app and sit still for 30 s →
user returns and re-runs the native export → the tool finds the new ECG CSV in the export bundle →
parses the voltage column → NeuroKit2 → RR intervals → **RMSSD and mean HR only** (rule 7:
SDNN/pNN50 borderline, all frequency-domain and nonlinear-beyond-SD1 invalid at 30 s — do not
compute them) → an irregularity flag → these join the digest as a *live capture* block, and the
provenance line changes accordingly.

**The pipeline, concretely** (confirmed current API):

```python
cleaned      = nk.ecg_clean(voltages, sampling_rate=fs, method="neurokit")
quality      = nk.ecg_quality(cleaned, sampling_rate=fs)          # gate on this BEFORE trusting anything
_, info      = nk.ecg_peaks(cleaned, sampling_rate=fs)
info         = nk.signal_fixpeaks(info, sampling_rate=fs, method="Kubios")  # ectopic/missed-beat correction
rmssd        = nk.hrv_time(info, sampling_rate=fs)["HRV_RMSSD"].iloc[0]
```

`nk.ecg_quality` and `nk.signal_fixpeaks(method="Kubios")` are not optional polish — wrist ECG is
noisy, and a missed or spurious R-peak corrupts RMSSD far more than it corrupts a mean. A quality
gate that refuses a bad capture is the difference between an honest reading and a confident wrong
one. `hrv_time` does not fail at 30 s (RMSSD is usable from ~10 s of clean beats); only the
frequency-domain functions warn, and those are never called.

**Dependency isolation.** NeuroKit2 drags in numpy, scipy, pandas, scikit-learn, matplotlib and
PyWavelets — several hundred MB. Install it in **its own virtual environment**, imported only by
the ECG module. v1's stdlib-only core must not acquire a transitive dependency on a plotting
library.

**What changes elsewhere:** almost nothing. The digest gains a section; the system prompt gains a
sentence; the validator is untouched; `baseline.py` gains an RMSSD series with its own (separate,
same-condition-only) baseline. This is the payoff of the digest being a string.

**Gates, in order:**
1. Spike 1 (§11) confirms on-device what third-party sources report — the export bundle contains
   the ECG voltage CSVs. A confirmation, not a fork.
2. Spike 2 confirms RMSSD from 30 s of real wrist ECG is stable enough to be worth reporting. This
   is the *actual* gate, and it is an empirical question no documentation can answer.
3. Only then build.

**Non-negotiable even here:** ECG gives cleaner rhythm and true RR. It gives **no** texture, **no**
depth, and **no** pressure information. The validator does not relax by one entry.

---

## 11. Spikes

| # | Question | Effort | Needs the device | Success criterion |
|---|---|---|---|---|
| **0** | What does the native `export.xml` look like, and how much history does the backfill hold? | 30 min | Yes | An `export.zip` on the PC; the real element names/attributes for resting HR, HRV SDNN, sleep, steps, energy recorded; ≥60 days of resting HR and HRV present. **Do this first — the parser and the whole §12.1 question depend on it.** Also clock how long the export takes to build and how large the zip is — that number decides §2.2's manual-cadence tolerance. |
| **1** | Does the export bundle contain the ECG voltage CSVs? *(Third-party sources say yes; confirm on device.)* | 30 min | Yes | One `electrocardiograms/*.csv` with ≥10,000 voltage samples and a readable sampling-rate header. Gates §10 only. |
| **2** | Is RMSSD from 30 s of real wrist ECG stable in practice? **The real ECG gate.** | 2 h | Yes | Two back-to-back captures agree within a stated tolerance; `nk.ecg_quality` scores recorded for still vs slight-motion captures; peak count survives a visual check |
| **3** | Is the manual native-export cadence tolerable in daily use, or is a paid/Shortcut automation warranted? | 1 week, real use | Yes | After a week of on-demand readings, a judgement call: is tapping through "Export All Health Data" before a reading fine, or annoying enough to justify §2.2's paid/Shortcut upgrade? **This is the decision that spends (or saves) the $25 — make it from experience, not up front.** |
| **4** | Author `knowledge/measurable_pulses.md` | 1–2 h | No | Reads the named nihaixia passages (`modules/04_jingui.md`, `modules/03_yian.md`), then writes ~1–2 KB of original text covering 数/迟/结/代/促; the M4 test (no texture character present anywhere in the file) passes; `NOTICE.md` records the source and its licence ambiguity |
| **5** | Does headless `claude -p` return schema-valid JSON on the subscription, and what happens at a rate limit? | 30 min | No | One real call returns a `structured_output` object matching `schema/reading.json`; the tool-disabling flags verified; limit-hit behaviour observed or explicitly noted as untested |

Spike 0 runs first, on day one. Spike 3 is a week of lived experience, not a setup task — it
decides the ongoing-transport question deliberately. Spikes 4 and 5 need no device. Spikes 1 and 2
are not on the v1 path.

---

## 12. Problems found in the locked decisions

Surfaced, not worked around, as instructed.

**12.1 — The 2–3-week baseline wait is probably unnecessary for v1, and the plan should not be
built around it.** Locked decision 11 states there is no honest day-one reading. That is correct
for *on-demand same-condition readings* — the ECG flow, where each reading is an event the user
must repeat under matched conditions. But v1's signals are **passive daily aggregates that Apple
has already been recording**: resting HR and overnight HRV are logged automatically, under
naturally consistent conditions (at rest, asleep), for as long as the watch has been worn. If a
backfill export yields 90 days of history, the personal baseline **exists before the first run**.
The 11× between-person variance argument that makes a personal baseline necessary is fully
satisfied by historical data — it does not care whether the data was collected before or after the
tool was installed.

*Now confirmed:* Apple's native "Export All Health Data" dumps the entire history in one free file
(§2.2), so the backfill mechanism exists and costs nothing. What remains unknown is only whether
**this watch has been worn consistently enough** for the history to be dense — a fact about the
user, not the tooling. Spike 0 settles it in 30 minutes. Both paths are designed (§5). If the
backfill is dense, v1 ships with a real reading on day one and the onboarding problem largely
disappears.

**12.2 — "RAG grounding" is over-specified for a corpus this small.** Unknown #5 asks for a
vector/keyword store. After filtering nihaixia to the measurable rate/rhythm pulses, the corpus is
a handful of short entries — small enough to inject wholesale into the system prompt. A retrieval
layer over it would add embeddings, a store, a query path and a similarity threshold, in exchange
for *worse* guarantees: retrieval is probabilistic, and a filter enforced at query time can leak
where a filter enforced at extraction time cannot. Inlining preserves both stated intents —
provider-portability (it is a text file) and the measurability filter (enforced once, at build,
and unit-tested). *Recommendation: inline a curated file; no vector store in v1.* Revisit only if
the corpus grows past what fits comfortably in the prompt. §12.7 makes this considerably more
clear-cut: the corpus is not merely small, it has to be written from scratch.

**12.3 — `TCMReasoningAdapter` as a formal interface is a one-implementation abstraction.**
Keeping it, because locked decision 13's underlying requirement (nothing upstream knows the
provider; memory is app-side; the contract is provider-neutral text) is real and valuable. But it
is implemented as a function signature plus a provider string, not an ABC with one subclass. Full
compliance, ~10 lines. Flagging so the choice is visible rather than discovered in review.

**12.4 — The 把脉 hook's residual risk is the user, and no validator fixes it.** Locked decision 18
is respected and §4.6's four layers stop the *model* from over-claiming. None of them stop the
*user* from seeing 把脉 on the launch screen and forming the belief that the device palpated his
pulse — the belief the whole Phase 2 research says is false. The mandatory provenance line is the
mitigation, and it is a real one, but it is a sentence competing with a brand name. Recorded as an
**accepted risk**, per the locked decision. It becomes materially more serious the moment a family
member uses the system, because they will not have read the research. Revisit the naming at
family expansion, not before.

**12.5 — v1's "reading" is the passive snapshot Phase 2 §3c explicitly called "not a 把脉 moment."**
This follows correctly from locked decision 16 and is the right call — but it means the headline
v1 experience is *trend commentary on yesterday's numbers*, not a session. Worth internalising
now: if the first run feels underwhelming, that is the design working, not a bug, and the fix is
the §10 milestone rather than loosening v1's output.

**12.6 — "No per-token bill" (locked decision 4) holds, but it was never load-bearing and should
stop being treated as a constraint.** Confirmed: headless `claude -p` authenticates with the
Pro/Max OAuth login and draws on subscription usage, and it even provides schema-validated
structured output. So the decision stands as written. But the more useful finding is the cost of
*not* having it: at ~1,500 input and ~800 output tokens, a reading costs about **$0.011 on Sonnet 5
or $0.0055 on Haiku 4.5** — roughly **20–60 cents a month** at one or two readings a day. The
"avoid the API bill" requirement is shaping an architecture for a rounding error. Keep the
subscription path because it is genuinely free and the adapter makes it swappable, but do not let
it veto anything: if the API's structured outputs, or a batch of 50 test calls for §7.2 and §7.3,
would be easier on an API key, spend the dollar. The one place this matters more than money is
§8 — the API's default is training-off, which is a privacy upgrade, not just a billing change.

**12.7 — The nihaixia pulse asset named in locked decision 13 does not contain what the decision
says it contains. This is the largest correction in this document.** Decision 13 instructs: use
nihaixia's 「脉舌速查」 (8 single + 8 complex pulses, `SKILL.md` lines 6097–6545) as the retrieval
grounding source, filtered to the measurable rate/rhythm subset. Reading the repo directly
(commit `ec03c59`):

- 「脉舌速查」 is not a heading; it is prose shorthand. The cited range is a different, much larger
  section. Real pulse content: **lines 6378–6404, ~2.1 KB**, plus a tongue table.
- The 8 + 8 count is right, but the entries are **three-cell table rows of 10–25 characters**, not
  reference entries.
- **Every one of the 16 is a texture pulse** (浮/沉/弦/紧/大/洪/细/微/弱 and compounds). 数 appears only
  fused to a texture character; 迟, 结, 代, 促 are absent from the section entirely.
- **Consequence: applying the mandated measurability filter to this asset produces an empty file.**
  The decision's own safety constraint — "the extraction MUST filter to the rate/rhythm subset" —
  deletes the entire asset. The two halves of decision 13 are mutually exclusive.
- Separately: **the repo ships no `LICENSE` file.** MulanPSL-2.0 is asserted in README prose and by
  a badge pointing at a file that does not exist. The Phase 2 verdict "MulanPSL-2.0 (permissive),
  clean to reuse" rests on a claim, not an artifact.

*Resolution (§4.2):* hand-author the knowledge file from a reading of the passages that genuinely
do discuss rate and rhythm — `modules/04_jingui.md` and `modules/03_yian.md`, ~30 lines across the
repo. This is less work than the parser the decision anticipated, carries no licence exposure since
it copies no text, and cannot leak texture vocabulary because none is ever transcribed. nihaixia
remains a legitimate and useful *consulted source*; it is not the drop-in grounding corpus the
decision assumed. **Accepted by the user, 2026-07-23** — this supersedes the extraction step in
locked decision 13 and open unknown #5. **The 复诊-relevant find:** its 代脉 passage defines the pulse by counting beats
between pauses — the one classical pulse concept in the repo that beat-interval data can actually
compute, and a natural fit for §10.

**12.8 — 上火 and 痰湿 are banned outright in v1, which is slightly stricter than rule 15.** Rule 15
rates 上火 unsupported and 痰湿 a weak indirect proxy. A "weak indirect proxy, heavily hedged" is
hard to express in generated prose without it reading as a claim, and impossible for a deny-list
to police halfway. Banning both is one line and reversible; permitting them safely is a prompt
engineering problem with a bad failure mode.

**Decided by the user, 2026-07-23: the tightening stands.** Both terms are banned in v1. This is no
longer an open question — Phase 4 implements the ban and does not relitigate it. If a future
reading feels sterile because of it, the relaxation path is to enforce the hedge in the schema
(a required `evidence_strength: "weak_indirect"` field) rather than trusting it to the prose.

**12.9 — The transport was switched from a paid exporter to Apple's free native export (decided
2026-07-24).** The original plan paid $24.99 for Health Auto Export up front. Investigating two
free candidates the user found reframed the decision:

- **`leecdiang/Apple-Health-Pro`** (MIT, free) is *not* an exporter — it is a desktop PyQt6 app
  that splits an already-produced Apple `export.zip` into CSVs. No HealthKit, no automation, no
  network, no ECG. It sits downstream of the real export step, so it cannot replace the paid app;
  it can only replace part of `ingest.py`, and adding a GUI step is more friction than parsing the
  zip directly. Noted as an optional inspection aid, not a dependency.
- **The Claude iOS Apple Health integration** (consumer iPhone app, read-only, beta, Pro/Max-only,
  US-only, shipped Jan 2026) is architecturally incompatible with this project. It is on-demand
  chat narration of raw HealthKit data on Anthropic's servers — no deterministic baseline, no
  validator, no structured output, no scheduling, no path to the PC. It is precisely the
  "LLM-reads-raw-numbers" architecture Phase 2 §3e rejected. Not usable as a pipeline; at most a
  phone-side toy.
- **The real free path is Apple's own "Export All Health Data"** — free, complete, and it bundles
  the ECG voltage CSVs, so it covers v1 *and* the ECG milestone (§10) with no paid app and no
  native app. It is strictly better than the paid app for the backfill (whole history in one file).

**The tradeoff accepted:** the native export is manual and whole-database, so it is heavy to repeat
daily. v1 tolerates this because readings are on-demand — the user is present anyway. The paid
Health Auto Export ($24.99 lifetime) and a free Apple Shortcut remain designed-in as *convenience*
upgrades to the ongoing leg only (§2.2), to be chosen from experience via Spike 3, not up front.
**Net: the project's hard cost is now $0** beyond the existing Claude subscription.

**Health Auto Export's confirmed JSON schema, preserved here so the upgrade needs no re-research:**
envelope `{"data": {"metrics": [], "ecg": [], ...}}`; common metric shape
`{"name", "units", "data": [{"qty", "date": "yyyy-MM-dd HH:mm:ss Z"}]}` (resting HR, HRV SDNN,
steps, active energy, respiratory rate, wrist temperature); heart rate as `{"date","Min","Avg",
"Max"}`; sleep aggregated as `totalSleep, asleep, core, deep, rem, sleepStart, sleepEnd, inBed…`;
ECG as `{classification, averageHeartRate, numberOfVoltageMeasurements, samplingFrequency,
voltageMeasurements: [{date, voltage, units}]}`. Cost: Basic $2.99 (manual), Premium $6.99/yr or
$24.99 lifetime (automations). `ingest.py` should keep its parsing core dict-shaped so this JSON
and the native `export.xml` are two thin adapters onto the same aggregator.
