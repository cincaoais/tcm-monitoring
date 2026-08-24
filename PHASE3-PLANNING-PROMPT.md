# Handoff Prompt — Phase 3: R&D Planning

> Copy everything below the line into a fresh Claude session (any account).
> Run `/snapclaude:orchestrate` first if you want fan-out for the technical spikes, then paste this.
> This is the PLANNING phase prompt. It asks for an R&D plan and a build blueprint — **not code.**
> The full evidence base is in `PHASE2-RESEARCH-CAPTURE.md` in this repo; this prompt is written to
> stand alone if that file isn't reachable, but read it first if it is.

---

## Role and phase

You are running **Phase 3 (R&D PLANNING)** of a staged SOP:

```
BRAINSTORM CONCEPT  ->  RESEARCH HOW IT REALLY WORKS  ->  LOCK THE DIRECTION
   (done)                    (done)                        (done)
   ->  R&D PLANNING  ->  CODING EXECUTION
       (you are here)      (later session)
```

**Do not write production code, scaffold the app, or start building.** The output of this session is
a **concrete R&D plan / implementation blueprint** plus a Phase 4 coding handoff prompt. Phase 4
(coding execution) is a separate later session. You *may* dispatch a small number of agents to
resolve the specific technical unknowns listed at the end (e.g., confirm an export format from docs),
and you *may* design proof-of-concept spikes — but plan them, don't execute the build.

Ask the user when direction is genuinely ambiguous. Do not guess and move on. He works strictly by
phase and does not want a session racing into work that belongs to a later phase.

---

## The concept (one paragraph)

A pulse-monitoring system that works the way a TCM doctor works: **Apple Watch (the fingers) → the
system (transport) → an LLM (the doctor's brain) → a TCM-framed wellness reading + concrete advice
(食疗 diet, 作息 routine, rest, exercise) → a 复诊 follow-up loop that remembers past advice and judges
the next reading against it → outcome records.** Users sit still, trigger a short reading, and get a
TCM-flavoured reading plus advice, informed by their history. Framing is **wellness and education,
never medical diagnosis** — a hard constraint.

---

## Locked decisions — treat as GIVEN, do not reopen

**From Phase 1 (brainstorm):**
1. Users: himself, family (caregiver angle), and prototype users. Not a clinical product.
2. Both interaction modes: on-demand ~30s session + passive background trends as history context.
3. Three-part feedback: TCM reading + advice; a 复诊 follow-up loop; outcome records.
4. LLM: start with **Claude on the existing Pro/Max subscription** (no per-token bill). Multi-provider is a future concern.
5. Framing: wellness/education, never diagnosis. Hard constraint.

**From Phase 2 (research) — the verdicts that CONSTRAIN the plan (evidence in `PHASE2-RESEARCH-CAPTURE.md`):**
6. **Measurement ceiling:** the watch honestly measures only the **rate / rhythm / HRV family**. The TCM
   texture pulses (弦/滑/涩) and dimensions depth/width/force/tension are **out of reach** — this is an
   *access/engineering* limit (no raw-PPG API for hobbyists) plus wrist contact-pressure noise, not a
   physics impossibility, but for this project's accessible data they are unreachable. Depth (浮/沉) is
   genuinely unmeasurable at any level. **The plan must not design any feature that claims pulse texture.**
7. **The 30-second window:** only **mean HR** and **RMSSD** (= Poincaré SD1) are scientifically defensible.
   SDNN/pNN50 are borderline; all frequency-domain (LF/HF/VLF) and nonlinear-beyond-SD1 metrics are INVALID
   at 30s. Don't compute or show them for the on-demand session.
8. **No on-demand beat-to-beat RR via API.** A third-party app cannot trigger `HKHeartbeatSeriesSample`
   or read raw beats; workout sessions give only ~5s HR samples. The **only** honest path to a real HRV
   reading is: user manually opens Apple's ECG app → app reads the voltage series (`HKElectrocardiogramQuery`,
   ~512 Hz) → derive R-peaks → RR → RMSSD. **A literal one-tap 把脉 capture button is impossible.**
9. **The ground-truth problem (deepest issue):** there are no labels, and TCM pulse inter-rater agreement
   is only κ≈0.34. The system can only ever be **self-consistent and personalized, never correct.** No
   diagnostic claim is defensible. Plan validation around convergent checks (does a "poor sleep" read track
   the user's own sleep data / self-report) and test-retest self-consistency — never "correctness."
10. **Architecture = HYBRID:** deterministic, personal-baseline-relative feature computation (auditable code)
    feeding a **constrained LLM** that narrates and personalizes but is **forbidden from inventing** any
    texture/quality it has no data for. Rule-based for facts, LLM for voice. An ML classifier
    (features→TCM labels) is a non-starter (no trustworthy labels) — do not plan one.
11. **Personal baseline required.** Absolute HRV varies ~11× between people; only deviation from the person's
    own rolling baseline is informative. A usable baseline needs **~2–3 weeks** of repeated same-condition
    readings. **There is no honest day-one reading.**
12. **What the LLM receives:** pre-digested, personal-baseline-relative facts in **natural language**
    (e.g. "resting HR is 12% above your 14-day baseline; RMSSD is in your lower quartile") — not raw RR,
    not bare numbers. All computation/thresholding happens deterministically before the model.
13. **LLM behind an adapter; memory lives app-side.** Start on Claude, but hide it behind a
    provider-agnostic `TCMReasoningAdapter` (interface sketch in the capture §6) so DeepSeek/Qwen swap in
    later via config. **RAG-ground a general model on curated TCM knowledge** rather than using a raw TCM
    fine-tune — RAG-on-general beat both raw general models and TCM fine-tunes.
    **Repo decisions (firsthand-read 2026-07-23), for the knowledge/reasoning layer only — none touch the signal layer:**
    - **`jangviktor-web/nihaixia` — USE as the retrieval grounding source.** MulanPSL-2.0 (permissive).
      It is a markdown Claude Agent Skill (`SKILL.md` ~840 KB + `modules/` + 245 `cases/`); its v2.1.0
      「脉舌速查」 pulse-tongue quick-reference (**8 single pulses + 8 complex pulses**, ~`SKILL.md` lines
      6097–6545) is the specific asset. **Critical constraint:** most of those are texture pulses (弦/滑/涩)
      the watch cannot measure — the extraction MUST filter to the rate/rhythm subset (数/迟/结/代/促) and
      withhold the texture entries, or the store will hand the model vocabulary to over-claim. See open
      unknown #5. No structured export exists (markdown only), so parsing/tagging is a build task.
    - **`QLU-NLP/BianCang` — REFERENCE only** (academic-use, text-in/text-out, no numeric input). Study its
      output *reasoning structure* — observation → pattern → pathophysiology → syndrome, with justification
      (see its 辨病/辨证 inference examples) — as a template for how our reading narrates. But our input is
      honestly truncated (rate/rhythm/HRV only; no tongue, no texture pulse, no full 四诊/inquiry unless the
      user supplies it), so the template must be adapted, not copied.
    - **`TCMAI-BJTU/LingdanLLM` — SKIP as dependency; note as a CAUTION.** Its Lingdan-PR component outputs
      herb formulas with dosages (e.g. 当归 15.0, 黄连 6.0). That is a treatment/prescription claim — the exact
      line this system must NOT cross. Do NOT model the 食疗/作息 advice layer on herb-formula prescription;
      keep advice to food/routine/rest/exercise wellness suggestions.
    - **`JuneYaooo/nihaisha-nishi-tcm` — SKIP.** Overlaps nihaixia (also 倪海厦 teachings), worse license
      (non-commercial, rights-holder copyright), ~3.68 GB, no highlighted pulse content. nihaixia is the
      better-licensed, pulse-explicit, far smaller pick.
    - **`yasenstar/Chinese_Medicine` — SKIP.** GPL-3.0 copyleft (poor fit as a dependency); a herb/formula
      ontology irrelevant to a rate/rhythm/HRV tool that does not prescribe herbs.
14. **The signal→TCM-feature layer must be built fresh** — no repo does it. Use **NeuroKit2** (MIT) for the
    RR→HRV math.
15. **Hard-exclude at the output layer:** pregnancy and critical-illness/mortality claims must be
    *structurally impossible for the system to emit* (an output validator), not merely discouraged. Claim
    ratings to encode: poor sleep = a trend signal (not single-reading); fever = weak, non-specific proxy
    ("possible physiological stress," never "fever"); 上火 = unsupported; 痰湿 = weak indirect proxy only.

**From Phase 2 (direction lock, decided by the user this session):**
16. **v1 target = the passive-baseline loop first.** Ship resting-HR/HRV/sleep/activity → personal baseline →
    TCM-flavoured wellness commentary + advice + 复诊 memory first. Layer the guided-ECG "real reading" on
    **later**, once the baseline loop works. Consequence: v1 is **not blocked** on the ECG-export unknown.
17. **v1 users = just him.** Solo prototype — free 7-day sideload / Apple Shortcuts, single baseline, no
    multi-user or extra privacy scaffolding yet. Expand to family in a later iteration.
18. **Framing = keep 把脉 as the user-facing hook** — BUT this is a *branding/naming* choice only. It does
    **not** relax any output discipline: the reading output still holds the wellness/no-diagnosis line, must
    not claim pulse textures, and passes the output validator (rule 15). Evocative name, disciplined output.
    Plan the guardrails so the 把脉 hook and the honest-output constraint coexist.

---

## What the Phase 3 plan must produce

A concrete R&D plan the coding session can execute from. Cover, scaled to complexity:

1. **System architecture** — the layers and how data flows: data ingest (Path 1: Apple Shortcuts + Health
   Auto Export webhook) → deterministic feature computation + personal-baseline store → natural-language
   digest builder → `TCMReasoningAdapter` (Claude + RAG grounding) → reading/advice output + output validator
   → app-side memory / 复诊 loop → outcome record-keeping. Break into isolated, independently-testable units
   with clear interfaces (what each does, how it's used, what it depends on).
2. **The v1 data pipeline, concretely** — exactly which HealthKit metrics, exported how (Shortcut schedule +
   on-demand), to where (a minimal store — decide: local file / SQLite / tiny server). Resolve the
   phone-unlocked / sync-latency realities into a workable design.
3. **The feature-computation spec** — which features for the passive loop (resting HR, HRV SDNN trend, sleep,
   activity), the personal-baseline math (rolling window length, z-score/percentile approach), and the exact
   natural-language digest format handed to the LLM (rule 12).
4. **The LLM layer** — the `TCMReasoningAdapter` interface, the provider-agnostic system prompt (TCM framing
   + safety rules), the output JSON schema, and the **output validator** that hard-blocks named diseases,
   invented pulse textures, and the excluded claims (rules 10, 15, 18).
5. **Onboarding / baseline-building UX** — how the ~2–3 week "building your baseline, no reading yet" phase
   is made to feel like progress, and what minimal honest feedback is allowed pre-baseline (rule 11).
6. **The 复诊 memory loop + record-keeping** — app-side memory digest (summarized prior visits/advice/
   corrections), how advice→subsequent-personal-baseline-trend is recorded and surfaced for reflection. No
   adaptive/RL self-learning layer in v1 (premature at visit-scale density — note it as a future direction).
7. **Validation strategy given no ground truth** — convergent checks (does the reading track the user's own
   sleep/self-report), test-retest self-consistency, menstrual-cycle confounding handling. Not "correctness."
8. **Privacy setup** — the Claude consumer training toggle OFF before real data flows; note the API/ZDR
   migration trigger for when family use begins.
9. **Build sequence / milestones for Phase 4**, and a short **test plan** (the ponytail rule: each non-trivial
   piece — the baseline math, the digest builder, the output validator — leaves one runnable self-check).
10. **The guided-ECG reading as a planned LATER milestone** — designed but gated behind resolving the
    ECG-export unknown (below). Do not build it into v1.

---

## Open technical unknowns to resolve during planning

Resolve what you can from docs/experiments-design; flag what needs the user's own device to test.

1. **(Gates the later ECG milestone, NOT v1)** Does **Health Auto Export** ship the full 512 Hz ECG voltage
   series, or only the classification + average HR? If only the latter, the guided-ECG reading forces a
   native app (Path 2). Design a spike to confirm this before the ECG milestone.
2. **R-peak → RR → RMSSD pipeline** — how clean is 30 s of real Apple Watch ECG for RMSSD in practice, on
   the wrist, with motion? Plan a validation spike with NeuroKit2.
3. **Baseline onboarding honesty** — the pre-baseline UX (rule 11).
4. **LLM narrative guardrail** — the prompt + schema + validator design that keeps the 把脉 hook while
   blocking over-claiming and invented textures (rules 15, 18). This is the main product-quality risk.
5. **RAG grounding (concrete).** Clone `jangviktor-web/nihaixia`; extract the 「脉舌速查」 section
   (~`SKILL.md` lines 6097–6545 — verify against the current version) and any rate/rhythm pulse entries
   from `modules/`. **Tag each pulse entry with a measurability flag and load ONLY the measurable
   rate/rhythm pulses (数/迟/结/代/促) into the retrieval store; exclude the texture pulses (弦/滑/涩) and the
   tongue entries** so the model cannot cite what the watch can't sense. Markdown has no structured export,
   so plan a small parse-and-tag step. Decide the integration shape: install nihaixia as a Claude Skill
   as-is vs extract the filtered subset into your own vector/keyword store (the latter is portable across
   providers and enforces the measurability filter — prefer it). Carry the MulanPSL-2.0 attribution and add
   your own wellness disclaimer layer on top.
6. **Menstrual-cycle confounding** — luteal-phase resting-HR/HRV shifts mimic both "fever/stress" and "early
   pregnancy" for any female user; plan cycle-awareness or explicit caveating.

---

## What to hand back

1. The **R&D plan / implementation blueprint** (the sections above).
2. A **Phase 4 (coding execution) handoff prompt**, self-contained, carrying the plan forward so a fresh
   session with zero context can build v1.
3. A short list of anything in the locked decisions that your planning found to be a problem — surface it,
   don't silently work around it.

Before you finish, tell the user anything you think is still wrong or risky, and anything he should decide
now rather than discovering mid-build. If direction is unclear, stop and ask rather than assuming.
