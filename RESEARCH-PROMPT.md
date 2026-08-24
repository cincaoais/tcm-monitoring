# Handoff Prompt — Phase 2: Research & Knowledge Capture

> Copy everything below the line into a fresh Claude session (any account).
> Run `/snapclaude:orchestrate` first, then paste this.
> This is the RESEARCH phase prompt. It does not ask for code or a plan.

---

## Role and phase

You are running **Phase 2 (RESEARCH)** of a staged SOP. The phases are:

```
BRAINSTORM CONCEPT  ->  RESEARCH HOW IT REALLY WORKS  ->  LOCK THE DIRECTION
    (done)                    (you are here)              (end of this session)
      ->  R&D PLANNING  ->  CODING EXECUTION
          (next session)      (later session)
```

**Do not write code, scaffold a project, or produce an implementation plan.** The only output
of this session is *understanding*: research findings, a feasibility verdict, and a clear
picture of what the system and its workflow actually look like. Phase 1 already happened — its
results are the "Locked decisions" below, so do not re-open them unless your research proves
one is impossible.

Ask me questions whenever the direction is genuinely ambiguous. Do not guess and move on.

---

## How to run this session — orchestrate it

I am running the `orchestrate` skill in this session deliberately. **Use it hard.** This is a
wide, shallow-dependency research job across five mostly-independent domains, which is close to
the ideal shape for parallel agents. Do not research all five yourself in sequence — that
wastes both time and expensive reasoning on work a cheaper model does just as well.

**Phase 1 — plan here.** Read this whole brief, decide the exact briefs for each research
stream, and note any ambiguity worth asking me about *before* dispatching. Do not let an agent
discover a direction question three levels down.

**Phase 2 — fan out.** Dispatch the five research streams below as **parallel subagents with
`model: "sonnet"` explicitly set**, all in a single message so they run concurrently. Give each
one a self-contained brief: the questions, the specific URLs already listed here, what "done"
looks like, and an instruction to cite sources. Do not make an agent re-derive context this
document already gives it.

Two rules for the agents:

- **They gather; you judge.** Agents return findings and evidence. Feasibility verdicts,
  scope decisions, and anything that shapes the product are yours to make in Phase 3.
- **Stream C is the hard one.** If you only give one stream extra depth or a second agent,
  make it C. See the note on it below.

**Phase 3 — synthesize, then attack your own conclusions.** Read what the agents actually
returned, not just their summaries. Then run one more adversarial pass: dispatch a skeptic
agent whose only job is to **refute** your feasibility conclusions — especially the claim
ratings in stream A and the feature-extraction viability in stream C. A pleasant, confident,
wrong research capture is worse than no research, because Phase 3 planning and Phase 4 coding
both get built on top of it. Anything that survives the skeptic goes in the final document;
anything that does not gets downgraded or dropped, and you tell me it was downgraded.

Beyond that, use every research tool you have — web search, fetch, whatever is available —
freely and thoroughly.

---

## The concept

Build a pulse-monitoring system that works the way a traditional Chinese medicine doctor works.
A TCM doctor takes your pulse (把脉) by pressing fingers on the wrist and reading what they
feel. I want to replicate that loop with hardware I already own:

**Apple Watch (the fingers) → my system (the transport) → an LLM (the doctor's brain) →
feedback and improvement advice back to the user → and back into the system itself.**

The user sits still, triggers a short reading (~30 seconds), the pulse data reaches an LLM
along with their history, and the LLM returns a TCM-framed reading plus concrete advice.

```
┌─ Apple Watch ─────────────┐   ┌─ Feature layer ─┐   ┌─ LLM "The Doctor" ───────────┐
│ (1) On-demand 把脉 session │   │ (2) signal ->   │   │ (3) features                  │
│     ~30s still, HR +      ├──▶│     TCM-mean-   ├──▶│     + history + past advice   │
│     beat-to-beat data     │   │     ingful      │   │     -> TCM reading            │
│ (1) Passive background    │   │     features    │   └──────┬───────────────┬────────┘
│     resting HR, HRV,      │   │  ** STREAM C ** │         (4)             (6)
│     sleep, activity       │   │  the hard part  │          ▼               ▼
└───────────────────────────┘   └─────────────────┘  ┌─ Patient ────┐  ┌─ System ─────────┐
                                                     │ TCM reading +│  │ outcome records: │
                                                     │ advice: 食疗,│  │ advice -> did the│
                                                     │ 作息, rest,  │  │ readings improve?│
                                                     │ exercise     │  └─────┬────────────┘
                                                     └──────┬───────┘        │
                                                        (5) 复诊 loop         └─ self-improve
                                                            ▼                    (need it?)
                                                     next reading judged
                                                     against previous advice
```

---

## Locked decisions (from Phase 1 — treat as given)

1. **Who uses it** — me, my family (caregiver angle), and as a prototype anyone with a
   smartwatch using my system/plan. Not a clinical product for real patients under care.
2. **Interaction** — *both* modes. An on-demand 把脉 session is the core experience, but the
   LLM also receives passive background trends (resting HR, HRV, sleep, activity) as context,
   like a doctor who already knows your history before touching your wrist.
3. **Feedback loop** — three parts, all wanted:
   - a TCM-framed reading plus concrete advice (食疗 diet, 作息 routine, rest, exercise);
   - a **复诊 follow-up loop** — the system remembers what advice it gave and judges the next
     reading against it, so advice adapts per person over time;
   - **system self-improvement** — outcome records (advice given → did later readings improve?)
     accumulate. *Whether a real self-learning layer beyond record-keeping is worth building is
     an open research question for you to answer — "need or no need, you find out."*
4. **LLM** — start with Claude on an existing Pro/Max subscription (no per-token API bill).
   Multi-provider (DeepSeek, Qwen, others) is a deliberate future concern, not now. But see
   stream E: I want to know how much Claude specifically matters versus any LLM.
5. **Framing** — wellness and education, not medical diagnosis. This is a hard constraint.

---

## What I want it to be able to say

The system should give readings along the lines of: **heaty (上火), fever, poor sleep,
damp/oily (痰湿), pregnancy, and in the extreme, critical illness ("about to die")** — and
potentially more.

**I know this list is the risky part, and I want you to be blunt with me about it.** Some of
these may be defensible wellness signals, some are weak proxies, and some may be impossible or
dangerous to claim from wrist data. Sort them honestly. I would rather ship something narrow
and true than something impressive and fake.

---

## Research streams

Five streams. Dispatch A, B, C, D, E as parallel Sonnet agents.

### Stream A — TCM pulse diagnosis, and what a wrist sensor can honestly measure

- The fundamentals: the 28 classic pulse types (28脉), the three positions (寸/关/尺), the
  three pressure depths (浮/中/沉), and the dimensions a pulse is read on — rate (数/迟),
  rhythm (结/代/促), depth (浮/沉), width, length, force (虚/实), tension (弦/紧), fluency
  (滑/涩).
- **Build a measurability matrix.** For each dimension, classify it as MEASURABLE from an
  Apple Watch, PROXY/PARTIAL, or NOT MEASURABLE — and explain physiologically why. My working
  assumption, which you should verify or destroy: the watch gives rate, rhythm and heart-rate
  variability, but *cannot* sense arterial wall tension, pulse width, or depth, because those
  require varying finger pressure against the artery. If that assumption holds, the texture
  pulses (弦/滑/涩) are out of reach and the honest scope is the rate/rhythm/HRV family.
- **Rate every claim in the list above** as PLAUSIBLE WELLNESS SIGNAL / WEAK PROXY /
  NOT SUPPORTED / DANGEROUS TO CLAIM. Be especially hard on pregnancy (the classic 滑脉 claim)
  and on any mortality or critical-illness claim.
- Prior art: peer-reviewed or commercial work on PPG-based TCM pulse classification. How do
  dedicated pulse-diagnosis instruments (脉象仪, typically multi-sensor with controlled
  pressure) differ from a consumer smartwatch, and what does that gap tell us?

### Stream B — Getting the data off the Apple Watch

- Exactly which heart-related data HealthKit exposes: heart rate, resting HR, heart-rate
  variability (SDNN), high/low/irregular-rhythm notifications, the 30-second single-lead ECG
  (`HKElectrocardiogram`), beat-to-beat interval series (`HKHeartbeatSeriesSample`), blood
  oxygen, respiratory rate, sleep stages.
- **The critical distinction:** confirm whether developers can access the raw continuous PPG
  optical waveform (I believe not) versus ECG voltage samples (I believe yes). This single fact
  shapes everything stream C can do.
- **What is my "30-second reading" actually?** Two candidates: the ECG app's 30s single-lead
  recording, or a short workout/heart-rate session. Compare what each yields, and determine
  whether a third-party app can *programmatically start* an ECG reading or whether it must be
  user-initiated in Apple's own app.
- Export paths, with pros and cons for each:
  - **Path 1 (no custom app):** third-party exporters such as "Health Auto Export – JSON/CSV",
    Apple Shortcuts health actions, auto-export to a webhook or server.
  - **Path 1b (MCP shortcut, investigate carefully):**
    `https://github.com/the-momentum/apple-health-mcp-server` — an MIT-licensed Python/FastMCP
    server that loads exported Apple Health XML into DuckDB and exposes MCP tools for querying
    it, so Claude can query health data directly over MCP. **This may save a lot of pipeline
    work.** Determine: does it handle the ECG voltage CSVs that ship inside Apple's export
    bundle, or only the main `export.xml` records? Is XML-export-only (batch, manual) good
    enough for the 把脉 session experience, or is the latency fatal? The README points to a
    successor platform called "Open Wearables" offering continuous sync — evaluate that too.
    My current read is that this may serve the passive-history half well and the on-demand
    session half badly; confirm or refute.
  - **Path 2 (native app):** a SwiftUI watchOS + iOS app with a 把脉 button running a workout
    session for live beat-to-beat capture, posting to my own server. What entitlements, what
    Apple Developer account cost, what App Store review implications, and what does this unlock
    that Path 1 cannot deliver?
- Gotchas: HealthKit permissions, background delivery limits, on-device storage and iCloud
  sync, latency, and what is realistic without App Store distribution.
- **Deliverable:** a recommended minimal pipeline for a first prototype — which data, exported
  how, to where — plus a clear statement of what the native-app version adds.

### Stream C — Signal to TCM meaning: THE HARDEST LAYER

**Give this stream the most depth. It is the part my original plan skipped entirely.**

My earlier thinking jumped straight from "get data from the Apple Watch" to "send prompts to
the LLM." The gap between those two is the whole novel problem, and the whole risk. A heart-rate
series is not a pulse reading. Something has to turn numbers into TCM-meaningful features, and
that something does not exist yet.

- **What features are computable** from beat-to-beat (RR) intervals: time-domain HRV (SDNN,
  RMSSD, pNN50), frequency-domain (LF, HF, LF/HF ratio, VLF), non-linear (Poincaré SD1/SD2,
  sample entropy, DFA α1), rate statistics, rhythm irregularity and ectopic-beat detection.
  And separately, what richer morphology becomes available *if* ECG voltage samples are
  accessible (intervals, waveform shape).
- **The mapping problem — the core question.** Is there any literature mapping HRV or
  pulse-wave metrics onto TCM constructs: the nine TCM constitutions (中医体质九分法, Wang Qi's
  classification), syndrome patterns (证型) such as 阴虚/阳虚/气虚/痰湿, or the classical pulse
  types? Assess the quality of that literature honestly — sample sizes, replication, whether it
  is credible science or wishful correlation. The common bridge argument is autonomic:
  sympathetic/parasympathetic balance mapped onto 阳/阴. Evaluate how far that analogy can
  legitimately be pushed before it becomes decoration.
- **Three architectural options — compare them:**
  1. *Rule-based:* hand-written thresholds mapping features to TCM descriptors. Transparent,
     auditable, but only as good as the rules.
  2. *ML classifier:* train a model on features → TCM labels. Runs headfirst into the ground
     truth problem below.
  3. *LLM does it all:* hand the LLM the computed features and let it reason. Cheapest to
     build, but is it doing real inference or fluent improvisation?
  Recommend one for the first prototype, with reasoning.
- **Personal baseline versus absolute values.** Absolute HRV varies enormously between
  individuals by age, sex and fitness, so a population threshold may be near-meaningless while
  deviation from a person's own rolling baseline may be quite informative. Investigate how much
  this changes the design, and how long a baseline period a new user would need before their
  first reading means anything. This directly affects the onboarding experience.
- **The ground truth problem — be blunt.** There are no labels. Nobody is standing behind this
  system telling us the reading was right. How would we ever know whether a reading is correct
  rather than merely plausible? Is there any validation strategy short of a licensed TCM
  practitioner reading the same wrists — and if not, what does that imply about what the system
  is allowed to claim? This may be the single most important finding of the whole session.
- Existing tooling: `neurokit2`, `pyHRV`, `hrv-analysis`, `biosppy` and equivalents. What is
  mature, what is well-validated, what would we actually use.
- **What exactly should the LLM receive?** Raw numbers, computed features, percentiles against
  the personal baseline, or natural-language descriptions of the features? This is a prompt
  design question with real consequences and it belongs to this stream.

### Stream D — Existing repos: reuse, reference, or skip

Evaluate each. For each: what it actually is, stack and base model, license, maturity and
whether weights or data are truly available, and relevance *to this project specifically*.
Verdict of REUSE / REFERENCE / SKIP.

- https://github.com/yasenstar/Chinese_Medicine
- https://github.com/JuneYaooo/nihaisha-nishi-tcm
- https://github.com/QLU-NLP/BianCang
- https://github.com/TCMAI-BJTU/LingdanLLM
- https://github.com/jangviktor-web/nihaixia
- https://github.com/the-momentum/apple-health-mcp-server *(pipeline; also assessed in stream B)*

**The judgment I need:** my input is a numeric pulse *signal*, not a text description of
symptoms. My suspicion is that the TCM repos are text-in/text-out syndrome-differentiation
(辨证) models — useful for the reasoning and knowledge-grounding layer, useless for stream C's
signal layer. If so, the hardest part of this project has no existing solution to borrow.
Confirm or refute that, then say plainly whether I should build fresh, modify, or reuse, and
for which layer.

### Stream E — LLM choice, privacy, and safety framing

- Compare, for *this* task (reasoning over structured heart features plus patient history to
  produce a TCM-framed explanation and lifestyle advice, with memory across visits): Claude on
  a Pro/Max subscription via Claude Code or the Agent SDK, Claude API, DeepSeek, Qwen, and
  TCM-finetuned open models such as BianCang, HuatuoGPT, or Zhongjing.
- Axes that matter: Chinese-language and TCM domain fluency, reasoning quality, cost model,
  privacy of health data, agentic memory and tool use, and how easily a provider swaps later.
- **Answer directly: is Claude load-bearing here, or is the LLM a commodity slot?** Recommend
  an architecture where the LLM sits behind an adapter so DeepSeek or others can be added later
  without rework.
- Privacy: what to know about sending someone's health data to a cloud LLM, and whether any
  provider offers zero-retention or no-training modes.
- Safety and regulation: the line between a *wellness/educational* framing and a *medical
  diagnosis* framing, the latter triggering medical-device regulation. Recommend the disclaimers
  and scope-limiting language this system should adopt, given family members will use it.
- Prior art: does any consumer product already do smartwatch-based TCM pulse reading? Search
  脉诊 智能手表, AI 把脉, TCM pulse smartwatch. How would this differ?

---

## What to hand back

One research capture document containing:

1. **The honest scope** — one paragraph stating what this system can and cannot legitimately
   claim, with the per-claim ratings behind it. Put this first; everything else depends on it.
2. **The measurability matrix** as a table.
3. **The feature-extraction verdict (stream C)** — is there a credible path from smartwatch
   signal to TCM-meaningful features, or is that bridge decorative? Which architecture for the
   first prototype, and what the ground-truth problem means for the product's claims. Treat
   this as the centrepiece of the document.
4. **The recommended data pipeline** — Path 1 vs 1b vs 2, with a recommendation and reasoning.
5. **Repo verdicts** and a build-fresh-versus-reuse recommendation per system layer.
6. **The LLM verdict** — Claude-specific or commodity, plus the swappable architecture sketch.
7. **The self-improvement verdict** — is that layer worth building, or is record-keeping enough?
8. **What the skeptic pass killed or downgraded** — list it explicitly. I want to see what did
   not survive scrutiny, not only what did.
9. **Open questions and risks** that Phase 3 (R&D planning) must resolve.

Before you finish, tell me anything you think I have wrong, and anything I should have asked
about but did not. If at any point the direction is unclear, stop and ask me rather than
assuming — I would rather answer a question now than unwind a wrong direction in Phase 3.
