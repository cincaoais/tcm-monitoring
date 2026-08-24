---
name: tcm-pulse-project
description: The TCM pulse-monitoring project (Apple Watch as 把脉 doctor) — concept and the design decisions locked during brainstorming on 2026-07-23
metadata: 
  node_type: memory
  type: project
  originSessionId: 420cee18-6da0-4013-ba54-9fa3d05df32a
  modified: 2026-07-23T09:07:10.540Z
---

Monopoly is building a pulse-monitoring system that mimics how a traditional Chinese
medicine doctor works: the Apple Watch plays the doctor's fingers (把脉), an LLM plays the
doctor's brain, and the loop closes as consultation → advice → 复诊 → refinement.
Working directory: `/Users/snapdec/Documents/workspace/brainstorming`.

Decisions locked during Phase 1 brainstorming (2026-07-23) — treat as given, not open:

- **Users:** himself, family members (caregiver angle), and prototype users — anyone with a
  smartwatch running on his system/plan. Explicitly *not* a clinical product.
- **Interaction:** both modes. On-demand ~30s 把脉 session is the core experience, plus
  passive background trends (resting HR, HRV, sleep, activity) as history context.
- **Feedback:** TCM reading + concrete advice (食疗, 作息, rest, exercise); a 复诊 follow-up
  loop where past advice is remembered and the next reading is judged against it; and outcome
  records for system self-improvement — whether that last layer is worth building is an open
  research question, not a commitment.
- **LLM:** Claude on his existing Pro/Max subscription first (no per-token API bill, he already
  pays for the plan). Multi-provider (DeepSeek, Qwen) is a deliberate *future* concern.
- **Platform:** lean pipeline first (existing HealthKit exporter or the apple-health-mcp-server,
  no custom app); a native watchOS/iOS app with a 把脉 button is a parallel curiosity, and both
  paths are carried into R&D planning rather than decided now.
- **Framing:** wellness and education, never medical diagnosis. Hard constraint.

The known physical constraint: Apple exposes no raw PPG waveform, so TCM texture pulses
(弦/滑/涩) are likely unmeasurable — the honest scope is probably the rate/rhythm/HRV family.
He wants readings like heaty (上火), fever, poor sleep, damp (痰湿), pregnancy, critical illness,
and has explicitly accepted blunt pushback on which of those are defensible. He prefers
"narrow and true" over "impressive and fake."

**The hardest layer**, identified on 2026-07-23 and missing from his original brief: nothing
yet bridges "raw heart-rate samples" to "TCM-meaningful features." His plan jumped straight
from Apple Watch data to LLM prompt. That bridge — HRV metrics, personal-baseline versus
absolute values, and the ground-truth problem (no labels, so how would anyone know a reading
is correct rather than merely plausible) — is the novel work and the main risk. It is stream C
of the research prompt and he wants it researched with the most depth.

The Phase 2 research handoff prompt lives at `RESEARCH-PROMPT.md` in the project directory. It
is written to be run under the `orchestrate` skill with five parallel Sonnet research agents
plus an adversarial skeptic pass. See [[staged-session-sop]] for how he runs these phases and
[[tcm-pulse-resources]] for the repos he has already found.

**Phase 2 was executed on 2026-07-23.** The research capture lives at
`PHASE2-RESEARCH-CAPTURE.md` (six Sonnet streams A/B/C1/C2/D/E + two skeptic passes). Headline
verdict: the honest product is a **personal-baseline wellness tracker in TCM-flavoured language**,
not a diagnostic 把脉 device. Load-bearing findings for Phase 3: (1) the watch measures only the
rate/rhythm/HRV family — texture pulses (弦/滑/涩, depth/width/force/tension) are unreachable, and
this is an *access/engineering* limit, not physics (Apple's own hypertension feature proves the
signal is in the sensor; hobbyists just have no raw-PPG API); (2) on a 30s window only mean HR
and RMSSD are defensible, and a third-party app **cannot** get on-demand beat-to-beat RR — the
only honest reading path is deriving RR from the manually-launched Apple ECG app's voltage series,
so a literal one-tap 把脉 button is impossible; (3) the ground-truth problem is fatal to any
correctness claim (TCM pulse inter-rater agreement is only κ≈0.34), forcing "self-consistent +
personalized, never correct"; (4) recommended architecture is a **hybrid** — deterministic
personal-baseline feature computation + a constrained LLM that narrates but may not invent
textures; (5) the signal→TCM-feature layer must be **built fresh** (no repo does it); (6) start on
Claude Pro/Max but RAG-ground it and hide the LLM behind an adapter — RAG-on-a-general-model beat
both raw general models and TCM fine-tunes; (7) hard-exclude pregnancy and mortality claims at the
output layer. Pregnancy/上火/痰湿 target claims were rated unsupported or dangerous. No day-one
reading is possible — a ~2–3-week baseline period is required first.

**Direction locked at end of Phase 2 (2026-07-23):** (1) v1 builds the **passive-baseline loop
first** (resting HR/HRV/sleep → personal baseline → TCM-flavoured commentary + advice + 复诊 memory),
with the guided-ECG "real reading" layered on later — so v1 is *not* blocked on the ECG-export
unknown; (2) v1 is **solo (just him)** — free sideload/Shortcuts, family later; (3) **keep 把脉 as the
user-facing hook**, but as *branding only* — the output still holds the wellness/no-diagnosis line,
claims no pulse texture, and passes an output validator (he overrode the recommendation to reframe
away from 把脉). The **Phase 3 R&D planning handoff prompt** is written at `PHASE3-PLANNING-PROMPT.md`,
self-contained for a fresh session; it says PLAN only, no code (coding is Phase 4, a later session).

**Phase 3 was executed on 2026-07-23.** The blueprint is `PHASE3-RD-PLAN.md` and the Phase 4 build
handoff is `PHASE4-CODING-PROMPT.md`. v1 is a local Windows CLI, Python 3.12 stdlib only, eight
modules, SQLite; the digest handed to the LLM deliberately contains no TCM vocabulary so the signal
layer stays provider- and framing-independent. Four Phase-2 assumptions were corrected by firsthand
checking, each written up in `PHASE3-RD-PLAN.md` §12: (1) the ECG-voltage unknown — the top-rated
risk — is **resolved yes**, Health Auto Export ships the full `voltageMeasurements` array, so the
guided-ECG milestone never needs a native app; (2) the ~2–3-week baseline wait is probably
avoidable, since a historical backfill export can supply the baseline on day one; (3) the nihaixia
「脉舌速查」 asset named in the locked decisions is **entirely texture pulses**, so the mandated
measurability filter empties it, and the repo ships no LICENSE file despite claiming MulanPSL-2.0 —
the knowledge file gets hand-authored instead; (4) the "no per-token bill" constraint holds
(headless `claude -p` runs on the Pro/Max login) but is worth ~30¢/month, so it should stop vetoing
design choices. Two open questions were closed by him at the end of the session: the outright ban
on 上火/痰湿 stands (he accepted the tightening beyond what the research strictly required), and the
knowledge file is hand-authored rather than extracted from nihaixia. Next session is Phase 4,
coding execution, run from `PHASE4-CODING-PROMPT.md`.

**Transport decided 2026-07-24 (PHASE3-RD-PLAN §12.9):** v1 uses Apple's **free built-in "Export
All Health Data"** (zip → `export.xml` parsed by `ingest.py`), not a paid exporter — hard cost is
now **$0**. The same zip bundles the ECG voltage CSVs, so the later ECG milestone reuses it. Two
free alternatives he found were investigated and rejected as the primary path: `Apple-Health-Pro`
is only a desktop CSV splitter of an already-exported zip (not an exporter), and the Claude iOS
Apple Health integration is chat-only, on-server, no structured output / no path to the PC — the
"LLM reads raw numbers" architecture the whole design avoids. The tradeoff: native export is manual
and whole-database, so v1 does no automation (readings are on-demand). Health Auto Export ($24.99
lifetime, JSON schema recorded in the plan) or a free Shortcut stay as **deferred convenience
upgrades** to the ongoing leg only — buy from experience (Spike 3), not up front.

**Phase 3 closed 2026-07-24. M0 setup gate already satisfied:** he turned the Claude "help improve
Claude" training toggle **off** (2026-07-24), and stored one Apple "Export All Health Data" bundle
in the project directory. So when Phase 4 starts, M0's privacy gate and first-export step are done;
the only remaining M0 item is checking the backfill's history depth (Spike 0), which is Phase 4's
first task and must not be pre-done in a planning session. Both planning docs are internally
consistent (final coherence pass done). Next action: open a **fresh session** in this repo and run
`PHASE4-CODING-PROMPT.md`.
