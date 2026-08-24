# Handoff Prompt — Phase 4: Coding Execution

> Copy everything below the line into a fresh Claude session (any account).
> The full blueprint is `PHASE3-RD-PLAN.md` in this repo — **read it first if it is reachable.**
> This prompt is written to stand alone if it is not.
> This is the BUILD phase. Code is expected. Planning is done — do not redesign it.

---

## Role and phase

You are running **Phase 4 (CODING EXECUTION)** of a staged SOP:

```
BRAINSTORM  ->  RESEARCH  ->  LOCK DIRECTION  ->  R&D PLANNING  ->  CODING EXECUTION
  (done)        (done)          (done)              (done)          (you are here)
```

Phases 1–3 are complete and their conclusions are **given**. Your job is to build v1 from the
blueprint, not to revisit whether it is the right blueprint. Where the plan is genuinely
underspecified, decide and note it. Where you think the plan is *wrong*, say so before building
that part — but do not silently substitute your own design.

**Two questions were left open at the end of Phase 3 and both were decided by the user on
2026-07-23. They are closed — implement them, do not reopen them:**

1. **The 上火 / 痰湿 ban stands.** Phase 3 banned both outright, slightly stricter than the earlier
   research required (上火 rated unsupported, 痰湿 a weak indirect proxy). The user confirmed the
   tightening. Both go in the validator deny-list.
2. **The knowledge file is hand-authored, not extracted.** The user accepted the finding that the
   `nihaixia` pulse asset is entirely texture pulses and therefore empties under the required
   measurability filter. This supersedes the extraction step in the original locked decisions.

**The user works strictly by phase and does not want a session racing ahead.** He asks direct
questions and wants direct answers, including blunt pushback on weak parts of his own plan.

---

## What you are building, in one paragraph

A **local command-line tool on a Windows PC** that ingests daily Apple Watch aggregates (resting
heart rate, overnight HRV SDNN, sleep, activity) exported off an iPhone, computes how yesterday
compares to **the user's own rolling baseline** using auditable arithmetic, renders those
comparisons as a **TCM-free natural-language digest of facts**, hands that digest to Claude behind
a swappable adapter with a small curated knowledge file, and prints a **TCM-flavoured wellness
reading plus 食疗/作息/休息/运动 advice** that has been forced through a deterministic output
validator. Each reading is recorded; the next one is given a computed 复诊 summary of prior advice
and what the numbers did since. It is branded 把脉; it never claims to have palpated anything.

**Single user (the developer himself). Local only. No web UI, no mobile app, no server.**

---

## Non-negotiable constraints — these are the product

Violating any of these is a build failure, not a style disagreement.

1. **Wellness and education, never medical diagnosis.** No named disease, no diagnosis, prognosis,
   or treatment. This is a hard constraint carried from Phase 1.
2. **Never claim pulse texture.** The watch measures rate, rhythm and the HRV family — nothing
   else. The classical texture pulses (弦/滑/涩), and the dimensions depth/width/force/tension, are
   unreachable with this data. Depth (浮/沉) is unmeasurable at any level. The system must be
   structurally incapable of claiming them.
3. **Hard-excluded, structurally not merely discouraged:** pregnancy claims and
   critical-illness/mortality claims. An output validator must make them impossible to emit.
   Also banned in v1: 上火 (unsupported), 痰湿 (weak proxy only), and any herb, formula or dosage.
4. **No correctness claims, ever.** There is no ground truth — TCM pulse inter-rater agreement
   among practitioners is only κ≈0.34, and no validated map from HRV to TCM syndromes exists. The
   system can be *self-consistent and personal*; it cannot be *correct*. Never state an accuracy
   figure or compare to a practitioner.
5. **Personal baseline only.** Absolute HRV varies ~11× between people, so population thresholds
   are meaningless. Every claim is relative to this person's own rolling history.
6. **Deterministic facts, LLM voice.** All computation, comparison and thresholding happens in
   testable code *before* the model. The model receives pre-digested natural-language facts and
   narrates them. It never does arithmetic and never sees raw series.
7. **No ML classifier.** Features→TCM-label classification is a non-starter (no trustworthy
   labels). Do not build one, do not suggest one.
8. **Privacy gate before any real data flows:** the Claude consumer "help improve Claude" training
   toggle must be verified **off** (claude.ai → Settings → Privacy). It ships on; on means up to
   5-year retention, off means 30 days.

---

## Architecture — build exactly this shape

Eight small Python modules. Pure functions at the core, I/O at the edges, data flowing one way.

```
native "Export All Health Data" → synced folder → data/raw/*.zip  (append-only, source of truth)
                                 │
                    ingest.py    ▼  (export.xml → daily rows)
                            tcm.db  (metrics / visits / context)
                                 │
        baseline.py → features.py ▼
                            FeatureSet (values + deviations + readiness gates)
                                 │
                    digest.py    ▼
                            digest: str   ← contains NO TCM vocabulary
                                 │
      + memory.py (复诊 history)  │  + knowledge/measurable_pulses.md
                    reasoning.py ▼   (TCMReasoningAdapter → claude -p)
                            raw model JSON
                                 │
                   validator.py  ▼ ── FAIL ──▶ deterministic template fallback
                            validated reading → printed, visit recorded
```

| Module | Responsibility | Purity |
|---|---|---|
| `ingest.py` | Parse exporter payload → metric rows; idempotent upsert | Parsing core is pure |
| `baseline.py` | Rolling-window robust statistics | **Pure** |
| `features.py` | Assemble today's feature set; apply readiness gates; own the per-metric direction semantics | Pure given rows |
| `digest.py` | Render facts as natural language | **Pure** |
| `memory.py` | 复诊 summary: prior advice + computed change since | Pure given rows |
| `reasoning.py` | The adapter; calls the model; returns raw text | I/O |
| `validator.py` | Schema + deny-lists + basis-grounding | **Pure** |
| `cli.py` | Commands, printing, orchestration | I/O |

**The load-bearing separation:** the digest contains no TCM vocabulary at all — it is a neutral
statement of facts about numbers. All TCM framing lives in the system prompt and the knowledge
file. This is what lets the signal layer be verified by someone who knows nothing about TCM, and
what lets the provider or the framing change without touching it. Do not leak TCM language
downward into `digest.py`.

**Dependencies: Python 3.12+, standard library only.** `sqlite3`, `statistics`, `bisect`, `json`,
`datetime`, `subprocess`, `re`, `argparse`. No numpy, pandas, scipy, ORM, web framework, or vector
database. The dataset is roughly thirty floats; importing pandas to take a median of it is the
exact over-engineering this project cannot afford, because every dependency is one more thing
between the user and an auditable number. (3.12 specifically: `statistics.linear_regression` needs
3.10, `statistics.correlation(method='ranked')` needs 3.12.)

---

## Data

**Metrics (daily aggregates only):** resting heart rate, HRV SDNN, sleep (duration + stages +
bedtime), step count, active energy; respiratory rate and wrist temperature if present. Not
collected: blood oxygen, workouts, location, cycle tracking. ECG is not in v1 either, but the same
free export bundles its voltage CSVs for the later milestone.

**HRV caveat that must appear in output provenance:** Apple's SDNN is PPG-derived pulse-rate
variability, mostly measured overnight — *not* ECG-derived RR. Label it as such everywhere.

**Transport: Apple's built-in "Export All Health Data" (free) → `export.zip` onto the PC →
`ingest.py` parses `export.xml` directly.** No third-party app on the phone, no paid exporter, no
server. The zip reaches the PC via a cloud-synced folder (Dropbox / Google Drive / OneDrive),
AirDrop, or cable; the tool watches a folder and ingests any new zip. This same bundle carries an
`electrocardiograms/` folder of per-ECG voltage CSVs, so the later ECG milestone needs no new
transport.

- **Parser:** streaming `xml.etree.ElementTree.iterparse` over `export.xml`, filtering to the
  record types for the metrics listed above (`HKQuantityTypeIdentifierRestingHeartRate`,
  `HKQuantityTypeIdentifierHeartRateVariabilitySDNN`, `HKCategoryTypeIdentifierSleepAnalysis`,
  `HKQuantityTypeIdentifierStepCount`, `HKQuantityTypeIdentifierActiveEnergyBurned`, and the two
  optional ones).
  Apple's export is *sample-level*, so `ingest.py` **aggregates to one value per day per metric**
  (resting HR and HRV are already daily-ish; sum steps/energy per day; roll sleep up to
  total-asleep + onset + wake). ~40–60 lines. **Confirm the real element/attribute names against
  an actual `export.xml` before writing the parser — that is Spike 0.**
- **Keep the parsing core dict-shaped.** A later optional upgrade to Health Auto Export's JSON
  (see below) should be a second thin adapter onto the same aggregator, not a rewrite.

**The cost of free, and the deferred paid upgrade:** Apple's export is manual and dumps the whole
database each time (heavy to repeat daily, ideal once for backfill). v1 accepts this because
readings are on-demand and the user is present anyway. *Do not build automation into v1.* If the
manual cadence proves annoying (Spike 3 decides this from a week of real use), the ongoing leg can
be upgraded to either a free Apple Shortcut pushing just the daily aggregates, or the paid **Health
Auto Export – JSON+CSV** ($24.99 lifetime) for automated incremental JSON. Its confirmed schema,
for that day: envelope `{"data": {"metrics": [...], "ecg": [...]}}`; common metric
`{"name","units","data":[{"qty","date":"yyyy-MM-dd HH:mm:ss Z"}]}`; heart rate `{Min,Avg,Max}`;
sleep aggregated `{totalSleep, core, deep, rem, sleepStart, sleepEnd, …}`; ECG
`{classification, samplingFrequency, voltageMeasurements:[{date,voltage,units}]}`.

**Two free alternatives were investigated and rejected as the primary path, for the record:**
`leecdiang/Apple-Health-Pro` is a desktop CSV *splitter* for an already-exported zip, not an
exporter (no HealthKit, no automation, no ECG) — an optional inspection aid, not a dependency. The
Claude iOS Apple Health integration is a consumer-app, read-only, chat-only, on-Anthropic-servers
feature with no structured output, no scheduling, and no path to the PC — architecturally the
"LLM reads raw numbers" pattern this whole design exists to avoid. Do not route the pipeline
through either.

**Three confirmed iOS constraints the design absorbs rather than fights:** HealthKit is unreadable
while the phone is locked (a manual export, phone in hand, sidesteps this — a point for the free
path); iOS decides when any background automation runs, so no fixed-time guarantee exists;
Watch→iPhone sync is opportunistic. Therefore: **readings read *yesterday*, export in the morning
after the phone has unlocked and reconciled, and ingest is idempotent by `(date, metric)`.**
Because Apple's export is the whole database every time, re-ingest is entirely overlapping data the
upsert absorbs for free — no catch-up logic, no sync-state pointer.

**Store:** one SQLite file, stdlib `sqlite3`, three tables, `CREATE TABLE IF NOT EXISTS`, no
migration framework.

```sql
metrics (date TEXT, metric TEXT, value REAL, unit TEXT, source TEXT, PRIMARY KEY (date, metric))
visits  (id INTEGER PRIMARY KEY, ts TEXT, digest TEXT, reading_json TEXT,
         validator_status TEXT, violations TEXT, provider TEXT, model TEXT)
context (date TEXT PRIMARY KEY, note TEXT, sleep_quality INTEGER, energy INTEGER, stress INTEGER)
```

`data/raw/` is the source of truth and is kept forever; `tcm.db` is a derived cache that
`tcm rebuild` reconstructs from scratch. Any ingest bug is therefore fixable retroactively.

---

## The baseline math

- Trailing **28 days** ending yesterday; **≥14 days present** or the metric is `insufficient` and
  gets no deviation claim.
- Centre = **median**. Spread = **MAD × 1.4826**. `robust_z = (x − median) / (1.4826·MAD)`.
- If MAD == 0, fall back to IQR/1.349 (`statistics.quantiles`); if that is also 0, report the raw
  delta and set `spread_degenerate`. **Never divide by zero, never emit an infinite z.**
- Percentile rank via `bisect` over the sorted window; percent delta vs median for readability.
- 7-day direction: the 7-day median expressed as a robust-z against the 28-day window. A slope on
  seven noisy points is reported as a **sign only**, never a number.
- Language bands, the only place thresholds live: `|z| < 1.0` → "within your usual range";
  `1.0–2.0` → "modestly above/below"; `> 2.0` → "well outside your usual range".
- Direction semantics are **per metric** (`features.py` owns this): higher resting HR = less
  recovered; lower HRV = less recovered.
- **Missing data is reported, never imputed.**

**Readiness gates — a reading is produced only when all hold**, else `tcm status` runs instead:
≥14 days present for both resting HR and HRV; yesterday's values present for both; trailing 7 days
not more than 40% gaps. Failing a gate prints what is missing and how many days remain. Never a
degraded-but-presented reading.

---

## The digest — the exact artefact handed to the model

Deterministic templates. Numbers, comparisons, provenance, gaps. **No interpretation, no advice,
no TCM vocabulary.**

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
- Sleep 5h42m — 1h18m below their 28-day median of 7h00m; 4th percentile.
- Sleep timing: asleep 01:40, 2h07m later than their median sleep onset of 23:33.
- Steps 4,120 — 45th percentile; within their usual range.

[7-day direction]
Resting heart rate trending up (7-day median +0.8 z). Overnight HRV trending down (-1.1 z).

[Context this person logged]
2026-08-13: "late work, two drinks". Self-rated sleep quality 2/5, energy 2/5, stress 4/5.

[Data quality]
All six metrics present for yesterday. No gaps in the trailing 7 days. 2 gaps in the 28-day window.
```

The provenance block is **mandatory and unconditional** — it is generated by code, not the model,
and it is what keeps the 把脉 branding honest. Absent context sections are omitted, never guessed.

---

## The LLM layer

### Adapter

```python
def generate_reading(digest, history_digest, profile, system_prompt, knowledge,
                     provider="claude_code") -> str:
    """Returns raw model response text. Never interprets it — validator.py does that."""
```

A function signature plus a provider string — **not** an abstract base class with one subclass.
Adding a provider later means one function and one `elif`. Nothing upstream knows a provider
exists. Memory is app-side: the model gets a composed `history_digest`, never a chat log, and has
no session continuity, so a provider swap loses nothing.

**Confirmed working invocation** (authenticates with the existing Pro/Max login, draws on the
subscription rather than API credits):

```
claude -p <digest+history>
  --append-system-prompt-file prompts/system_v1.md
  --output-format json
  --json-schema schema/reading.json
  --model claude-sonnet-5
  --disallowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Agent"
```

- `--json-schema` yields a validated `structured_output` field, so the validator's schema check is
  a second line of defence rather than the only one. Checks 2–7 below are still entirely ours.
- **There is no single "no tools" flag** — disable them explicitly by name, and assert it in the
  test. A reasoning call that can read the filesystem is a different thing from what this design
  describes.
- **Do not use the Claude Agent SDK.** It requires an API key, and everything it adds (agent loop,
  built-in tools, sessions) is what this call must not have.
- Handle rate limits: a rolling 5-hour session window plus a weekly cap exist. One or two short
  calls a day will not approach them, but treat a non-zero exit as a normal outcome — retry with
  backoff, then fail visibly without recording a visit.

### System prompt (`prompts/system_v1.md`, versioned, hashed into each visit record)

Sections in order: **role** (a TCM-informed wellness companion writing for one person about their
own trends); **what you have been given** (a closed list); **what you do not have** (enumerated so
the absence is salient — no palpation, no pressure/depth/width/tension/texture, no tongue, no
complexion, no inquiry beyond the digest); **hard prohibitions** (per the constraints above);
**permitted register** (TCM wellness vocabulary and the rate/rhythm pulse terms only, as hedged
tendency language, always attached to a specific number from the digest); **grounding rule**
(every `basis[]` item restates a digest fact; inventing a number is the worst failure mode);
**advice constraints** (食疗/作息/休息/运动 only; everyday, low-risk, reversible; 2–4 concrete items
per category); **复诊** (reference the history digest; acknowledge prior advice and what the
numbers did, without claiming causation); **output** (the schema, verbatim, and nothing else).

### Output schema

```json
{
  "reading_title": "string ≤24 chars",
  "tcm_pattern_summary": "hedged tendency language, ≤120 chars",
  "plain_summary": "one paragraph, NO TCM vocabulary — the same claim in plain words",
  "basis": ["each item restates one fact from the digest"],
  "confidence_note": "what this reading is and is not based on",
  "advice": {"diet": [], "routine": [], "rest": [], "exercise": []},
  "followup": {"what_to_watch": [], "recheck_in_days": 7},
  "flags": ["e.g. a trend worth raising with a doctor"],
  "disclaimer": "fixed verbatim string, checked by the validator"
}
```

`plain_summary` is an honesty forcing function: a claim that cannot survive restatement without
TCM vocabulary was never a claim about the data.

### The output validator — the enforcement layer

`validate(raw, digest) -> (ok, violations)`. Seven deterministic checks:

1. **Parse and schema** — valid JSON, required keys, types, length caps, no unknown top-level keys.
2. **Texture-pulse deny-list.** Match on **pulse-context bigrams, not bare characters**: `弦脉`,
   `脉弦`, `滑脉`, `脉滑`, `涩脉`, `脉涩`, `浮脉`, `脉浮`, `沉脉`, `脉沉`, `细脉`, `脉细`, `紧脉`, `脉紧`,
   `洪脉`, `虚脉`, `实脉`, plus `指下`, `脉位`, `脉力`, `脉体`, `举按`, `寸关尺`. A naive
   single-character list would reject innocent words like `仔细`, `沉睡`, `浮躁`, `滑雪` — **the test
   corpus must include those as must-pass cases.**
3. **Disease and diagnosis deny-list** — named conditions (糖尿病, 高血压, 冠心病, 房颤, 心律失常, 甲亢,
   贫血, 肺炎, 感冒, 发烧/发热, 抑郁症, 癌 … and English equivalents) and diagnostic verbs (诊断, 确诊,
   患有, 治疗, 疗程).
4. **Hard-excluded topics** — pregnancy (怀孕/妊娠/早孕/pregnan\*), mortality and critical illness
   (死亡/猝死/危重/寿命/mortality), plus 上火 and 痰湿.
5. **Herb and prescription ban** — 方剂, 汤, 丸, 散, 膏, 冲剂, herb names, and any dosage pattern
   `\d+\s*(克|g|钱)`.
6. **Basis grounding** — extract every number from `basis[]` and `plain_summary`; assert each
   appears in the digest. A number the model was not given is a fabrication, and this catch is
   nearly free. Allow a short whitelist of derived forms (percentages computed from given numbers);
   log rather than reject on near-misses so the rule can be tuned against real output.
7. **Disclaimer present verbatim**, `plain_summary` non-empty.

**Failure policy — this is what makes the exclusion structural:**

```
attempt 1 → violations → retry once, appending the exact violations to the prompt
attempt 2 → violations → DISCARD the model output entirely. Never display it, not even
            marked as invalid. Print the deterministic template reading (digest facts,
            restated, plus generic non-personalised advice) with:
            "The narrative layer was withheld for this reading (validator: <codes>)."
            Record both attempts with validator_status='blocked'.
```

A blocked reading is a visible, counted event. If it happens often, the prompt is wrong.

### Knowledge file

`knowledge/measurable_pulses.md`, ~1–2 KB, injected wholesale into the system prompt. Covers only
pulses defined by beat rate or beat timing: 数 (rapid), 迟 (slow), 结 (irregular pauses), 代 (regular
intermittent pauses), 促 (rapid with pauses). No texture pulses, no compounds containing a texture
component, no tongue material — the model is never *shown* the vocabulary it must not use, which is
a stronger guarantee than instructing it to avoid vocabulary it has seen.

**Write this file yourself.** Phase 3 planned to extract it from `jangviktor-web/nihaixia`, then
read the repo and found the named asset is **entirely texture pulses** (all 16 rows: 浮/沉/弦/紧/
大/洪/细/微/弱 and compounds), so filtering it for measurability yields nothing — and the repo ships
**no LICENSE file** despite claiming MulanPSL-2.0 in README prose. Instead: read the passages that
genuinely discuss rate and rhythm — `modules/04_jingui.md` (the only numeric rate definitions) and
`modules/03_yian.md` (arrhythmia cases), about 30 lines across the repo — then write original
description. No parser, no copied text, no licence exposure. Record the consultation, the commit
SHA, and the licence ambiguity in `knowledge/NOTICE.md`.

*(Worth reading for its own sake: nihaixia's 代脉 passage defines the pulse by counting beats
between pauses — "54 beats then a pause is normal, every 5th beat pausing is not". That is a
beats-between-pauses ratio, the one classical pulse concept in the repo that beat-interval data
could actually compute. Not usable in v1, which has no beat-level data — note it for the ECG
milestone.)*

---

## Onboarding

Two paths, chosen automatically by how much history the backfill produced.

**Path A — backfill dense (≥14 days in the 28-day window):** no waiting period; the first run
produces a real reading. Likely, since Apple has been logging resting HR and overnight HRV
automatically for as long as the watch has been worn.

**Path B — cold start:** `tcm status` is the whole pre-baseline product — a progress bar with a
real number (`9 / 14 days`), the honest facts that *are* available (ranges, medians, gaps), a
one-sentence explanation of why no reading is given yet, `tcm log` to record daily self-ratings,
and `tcm demo` to render a full sample reading on synthetic data watermarked `DEMO — fabricated
data`. Pre-baseline the permitted output is exactly: raw values, ranges, medians, gaps, streaks.
No deviation language, no TCM vocabulary, no advice.

A product that declines to guess on day one is more credible on day thirty than one that guessed.

---

## The 复诊 loop

`memory.py` composes the history digest from `visits` and `metrics` — deterministic, computed, no
summarisation model call. For each of the last 3 visits: date, how it read, the advice given, and
**"since that visit (measured, not reported)"** — the median shift and z-delta of each metric
between then and now, computed by `baseline.py`. Plus a code-generated, non-optional caveat that
this is association only and that logged-context days are confounded.

`tcm history` shows the user the same thing. That, plus reflection, is the entire self-improvement
layer. **Do not build an adaptive or RL layer** — at one data point per visit, weeks apart, it is
contraindicated, not merely unbuilt.

---

## Validation, given there is no ground truth

1. **Deterministic-layer correctness** — golden-file tests on `digest.py`; property tests on
   `baseline.py` against synthetic series with known median/MAD/percentile; a ~25-case corpus for
   `validator.py` with both must-block outputs (invented 弦脉, a named disease, a herb dose, a
   fabricated number, a pregnancy hint) and must-pass ones (the innocent-character traps). This
   layer *does* have ground truth and must be exactly right.
2. **Test–retest self-consistency** — one fixed digest through the model 5×; compare pattern
   direction, advice categories, flags. Run after every prompt change.
3. **Ablation / confabulation check — the most important one.** Feed a **scrambled** digest
   (deviations inverted). The reading must change materially and in the right direction. If a
   scrambled digest produces a similar reading, the narrative is untethered and the layer is
   decorative. Automate it; run it on every prompt change.
4. **Convergent check (n=1, weeks)** — `tcm log` collects sleep-quality/energy/stress 1–5 daily;
   after ~6 weeks compute Spearman correlation (`statistics.correlation(method='ranked')`) against
   the system's recovery direction. Report as exploratory with confounds named. **A null result
   must be reported, not buried.**
5. **Never claimed:** accuracy, diagnostic performance, comparison to a practitioner.

**Menstrual-cycle confounding:** not applicable to the solo v1 user, and building it now is
speculative. Implement ~10 lines: a `profile.cycle_tracking` flag defaulting false, and a hard gate
disabling illness/stress-adjacent framing if it is ever set true, until phase tagging exists. The
luteal-phase resting-HR rise (~3.5 bpm) is the same direction and size as the "physiological
stress" signal and is indistinguishable without phase information. This gate is a **prerequisite
for family expansion**.

---

## Build sequence

Do the spikes first — they are cheap and two of them change what you write.

| Spike | Question | Effort | Success criterion |
|---|---|---|---|
| **0** | Native `export.xml` shape + how much history the backfill holds? | 30 min, on device | An `export.zip` on the PC; real element/attribute names for resting HR, HRV SDNN, sleep, steps, energy recorded; ≥60 days present. Also note how long the export takes to build and the zip size — that feeds Spike 3. **Everything in the parser depends on this.** |
| **3** | Is the manual native-export cadence tolerable, or is a paid/Shortcut automation worth it? | 1 week of real use | A judgement from experience: is tapping "Export All Health Data" before a reading fine, or annoying enough to justify the $24.99 Health Auto Export / a free Shortcut? **This is the decision that spends or saves the $25 — make it from use, not up front. Do not build automation into v1.** |
| **4** | Author the knowledge file | 1–2 h | Passes the no-texture-character test |
| **5** | Does headless `claude -p` return schema-valid JSON on the subscription? | 30 min | One real call returns a conforming `structured_output`; tool-disabling verified |

Then:

| # | Milestone | Done when | Self-check left behind |
|---|---|---|---|
| **M0** | Privacy + transport | Training toggle verified **off**; a real native `export.zip` on the PC; full-history backfill done. **Cost: $0** — Apple's built-in export, no paid app | a gate, not code |
| **M1** | Ingest + store | `tcm ingest` parses `export.xml` from the zip and aggregates to daily rows; `tcm rebuild` reconstructs from `data/raw/` | `test_ingest.py` — real `export.xml` sample → expected daily rows; malformed/empty input rejected loudly |
| **M2** | Baseline + features | `tcm status` prints the onboarding view from real data | `test_baseline.py` — known median/MAD/percentile; MAD==0 and short-window paths |
| **M3** | Digest | `tcm digest` prints the block above | `test_digest.py` — golden file; every band boundary; missing-metric and no-context paths |
| **M4** | Knowledge file | Written, with `NOTICE.md` | `test_knowledge.py` — **no texture character appears in the file at all** |
| **M5** | Reasoning adapter | `tcm reading --dry-run` shows the assembled prompt; a live call returns JSON | `test_reasoning.py` — stub provider; digest passed through unmodified; tools disabled |
| **M6** | Validator | Blocks every bad case, passes every clean one | `test_validator.py` — the ~25-case corpus incl. false-positive traps |
| **M7** | End-to-end | `tcm reading` produces a validated reading and records a visit | `test_e2e.py` — stubbed provider; forced-violation path lands on the template fallback |
| **M8** | 复诊 loop | Second reading includes the history block with computed deltas | `test_memory.py` — two synthetic visits → expected deltas |
| **M9** | Validation harness | Test–retest and ablation runnable on demand | the ablation check itself |

**Sequencing principle: do the backfill first and the wait question resolves on day one.** A dense
native-export backfill removes the 2–3-week baseline wait entirely; a sparse one starts the clock.
Run it (Spike 0 / M0) before writing baseline code.

**Test-plan rule:** every non-trivial unit leaves **one runnable check** — plain `assert`-based, no
framework, no fixtures, no per-function suites. The three that must be genuinely thorough are
`baseline`, `digest` and `validator`, because they are what the honesty claim rests on. A stub
provider makes the whole pipeline testable offline with zero model calls.

---

## Explicitly out of scope for v1

ECG, RR intervals, RMSSD, live capture (designed as a later milestone — Apple's native export
*already* bundles the ECG voltage CSVs, so it is buildable on the same free transport when the time
comes, using NeuroKit2 in its own virtualenv with `nk.ecg_quality` and
`nk.signal_fixpeaks(method="Kubios")` as non-optional quality gates). Also out: **any export
automation** (v1 is manual native export — see the transport section), multi-user, per-person
keying, any web or mobile UI, any adaptive/learning layer, any vector database, any ML classifier,
multi-provider orchestration.

---

## Style

The user runs a "lazy senior developer" discipline: the shortest working diff, standard library
over dependencies, no speculative abstraction, no scaffolding for later, deletion over addition.
Mark deliberate simplifications with a `ponytail:` comment naming the ceiling and the upgrade path.
This never applies to input validation, error handling that prevents data loss, or the safety
constraints above — those are built properly the first time.

## Before you finish

Tell him what you think is still wrong or risky, and what he should decide now rather than discover
mid-build. If direction is genuinely unclear, stop and ask rather than assuming.
