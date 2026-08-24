# Phase 2 — Research Capture: Apple Watch as a TCM 把脉 Doctor

> Deliverable of the RESEARCH session (2026-07-23). Companion to `RESEARCH-PROMPT.md`.
> No code, no implementation plan — this is the *understanding* Phase 3 (R&D planning) builds on.
> Method: six parallel research streams (A, B, C1, C2, D, E) on Sonnet, synthesized here, then
> attacked by two adversarial skeptic agents. Every conclusion below carries its skeptic verdict.
> Where the skeptic dented something, it says so and the claim is stated in its downgraded form.

---

## 0. Read this first — the one-paragraph verdict

An Apple Watch can honestly power a **personal-baseline wellness tracker that speaks TCM-flavoured
language** — and nothing more. It can measure the **rate / rhythm / heart-rate-variability family**
well; it **cannot** measure the pulse *texture* dimensions (弦/滑/涩, depth, width, force, tension)
that classical 把脉 actually reads, because those need controlled finger pressure the device never
applies and a raw optical waveform Apple never hands to a hobbyist. There is **no credible science**
mapping the signals it *can* get (HRV) onto specific TCM constitutions or syndromes — that bridge is
decorative the moment it names a 证型. And there is **no ground truth**: nobody can tell you a reading
was *correct* rather than merely *plausible*, because even licensed practitioners agree with each
other on pulse diagnosis only at κ≈0.34. So the defensible product is **narrow and true**: track how
*your own* resting HR, HRV and rhythm move against *your own* history, narrate it in TCM wellness
vocabulary offered for reflection, and never diagnose. The impressive-but-fake product — "your pulse
says you're pregnant / 痰湿 / about to die" — is out, and two of those are hard-excluded on safety
grounds, not just softened.

**What this means for the dream:** the "wrist as the doctor's fingers" metaphor is the part that
doesn't survive. The fingers of a TCM doctor sense *pressure and texture*; the watch senses *timing*.
What genuinely survives is the *other* half of a good doctor — the one who already knows your history,
notices when today is off from your normal, and gives lifestyle advice. Build that.

---

## 1. The honest scope + per-claim ratings

**Scope in one sentence:** an on-demand ~30-second reading can honestly yield **heart rate, a rhythm/
irregularity check, and RMSSD (short-term HRV)**; passive background data adds **resting-HR, HRV,
sleep and activity trends**; everything TCM-diagnostic beyond "here is how your own autonomic/rhythm
pattern compares to your baseline, in TCM-flavoured language" is unsupported by evidence or unsafe.

| Target claim | Rating | Skeptic verdict | Why |
|---|---|---|---|
| **Poor sleep** | PLAUSIBLE WELLNESS SIGNAL (at *trend* level) | DOWNGRADED | HRV suppression + resting-HR rise track sleep debt at the group/trend level, but a *single night* is noisy and confounded (REM swings; one controlled study found no HRV change after total sleep deprivation; wearables disagree on nocturnal HRV). Keep it — but as a multi-day trend signal, not a one-shot verdict. |
| **Fever** | WEAK PROXY | SURVIVED (reinforced) | Elevated resting HR + suppressed HRV is a real infection signature (Mount Sinai Warrior Watch flagged COVID up to 7 days early) but non-specific — stress, alcohol, travel, exercise, dehydration all mimic it. One alerting model hit only 43% sensitivity at 95% specificity. Never say "fever"; say "possible physiological stress consistent with early illness." Note Apple's own wrist-temp sensor is explicitly *not* validated for fever. |
| **上火 (heaty)** | NOT SUPPORTED | SURVIVED | Its defining symptoms (sore throat, mouth ulcers, acne, constipation) are not cardiovascular; no study links the cluster to any HRV/autonomic marker. At most a very loose "higher-arousal state" framing, which is not 上火. |
| **痰湿 (damp/phlegm)** | WEAK INDIRECT PROXY (was: NOT SUPPORTED) | DOWNGRADED | A real but two-hop, fully confounded chain exists: 痰湿质 is the dominant constitution in metabolic syndrome, and metabolic syndrome correlates with reduced HRV. No study measures HRV in 痰湿-diagnosed subjects directly, and obesity/age confound the whole path. Not a clean signal — a weak statistical lean at best. |
| **Pregnancy** | DANGEROUS TO CLAIM → exclude the feature | SURVIVED | Even purpose-built 3-channel pressure hardware reaches only 80–91% on tiny samples; a single reading cannot separate early pregnancy from luteal-phase resting-HR rise (~3.5 bpm, same direction). *Nuance:* multi-week wearable **trend** monitoring genuinely does pick up pre-missed-period pregnancy signal (WHOOP/Apple Women's Health) — but that is a different feature shape (weeks of personal baseline), and asserting pregnancy status is a diagnostic/life-state claim that violates the wellness constraint regardless. Do not build a "pregnancy" output. |
| **Critical illness / "about to die"** | DANGEROUS TO CLAIM → hard-exclude at the output layer | SURVIVED (case strengthened) | HRV→mortality is real, decades-old *clinical* science — but always in diseased populations, on hours-to-days of clinical-grade ECG, physician-interpreted, calibrated. A hobbyist app that surfaces "mortality risk" borrows that credibility while discarding the calibration that makes it safe. This should be *structurally impossible for the system to emit* (output filter), not merely discouraged. |

---

## 2. The measurability matrix

Verdict scale: **MEASURABLE** / **PROXY-PARTIAL** / **NOT MEASURABLE** — from the perspective of a
hobbyist using only HealthKit (derived HR/HRV numbers) plus the readable 30s single-lead ECG.

| Pulse dimension | TCM term | Physical property | Verdict | Does the 30s ECG change it? |
|---|---|---|---|---|
| Rate | 数/迟 | Beats per unit time | **MEASURABLE** | No (redundant) |
| Rhythm / irregularity | 结/代/促 | Beat-to-beat timing regularity, ectopy | **MEASURABLE** ("is it irregular"); weaker for classifying *which* classical irregularity | **Yes — improves it.** ECG's clean electrical signal is the basis of Apple's validated AFib detection |
| HRV (autonomic tone) | (modern proxy, not a classical 脉) | Beat-interval variability → vagal/sympathetic modulation | **MEASURABLE**, with caveats (Watch SDNN underestimates vs chest-strap; passive HRV is PPG-derived PRV, not true RR) | Marginal — ECG gives more accurate RR for a single window |
| Depth | 浮/中/沉 | Where the pulse is felt across a *sweep of applied pressure* | **NOT MEASURABLE** | No — voltage carries no pressure information. *(This is the one texture claim the skeptic left fully intact.)* |
| Width | — | Perceived vessel diameter/spread under the fingerpad | **NOT MEASURABLE** (single site, no spatial extent) | No |
| Length | — | Span across cun/guan/chi (寸/关/尺) | **NOT MEASURABLE** (single sensing site) | No |
| Force | 虚/实 | Forcefulness *in response to changing applied pressure* | **PROXY-PARTIAL, weak & uncontrolled** (PPG amplitude/perfusion index is confounded by strap tightness, motion, skin tone) | No |
| Tension | 弦/紧 | Arterial wall stiffness/tautness | **NOT MEASURABLE in practice** (see note) | No |
| Fluency | 滑/涩 | Smooth-rolling vs hesitant flow | **NOT MEASURABLE as defined** (only the "irregular" sub-component overlaps rhythm) | No |

**Important skeptic correction to the tension/texture rows.** The original "these are *physically*
unmeasurable" framing was **too absolute and is downgraded**. Apple's own FDA-cleared **Hypertension
Notification Feature** (Sept 2025) extracts vascular-response information from the *same* wrist optical
sensor with no tonometry — so the arterial-stiffness signal genuinely *exists* in the hardware. The
honest statement is: **it is an access/engineering limit, not a physics impossibility.** Apple reaches
it with a proprietary algorithm over the *raw PPG waveform* across 30-day windows; a hobbyist gets only
derived HR/HRV numbers, and uncontrolled wrist contact pressure adds real noise on top. For *this
project's accessible data*, the texture pulses stay out of reach — but state the reason correctly
(no API + noise), because it changes what a future native/research path could unlock (see §4, §9).

---

## 3. The feature-extraction verdict — THE CENTREPIECE (Stream C)

This is the layer the original plan skipped: turning numbers into TCM meaning. Verdict, in order.

### 3a. Is the signal→TCM-meaning bridge real or decorative? — **Decorative beyond coarse arousal.** (SURVIVED skeptic attack, reinforced.)

- There is **no credible, replicated, adequately-powered literature** mapping HRV onto the nine Wang Qi
  constitutions (中医体质九分法) or syndrome patterns (证型). The closest systematic review (20
  Eight-Constitution-Medicine HRV studies) returns a **negative** verdict; the Chinese nine-constitution
  literature is **thinner still** — scattered small (N=24–192), single-site, unreplicated, sometimes
  circular studies (the "TCM label" is just a re-labeling of the LF/HF number). The skeptic went looking
  for 2020–2026 Chinese-language work that would overturn this and found none stronger.
- The **autonomic bridge** (sympathetic≈阳 / parasympathetic≈阴) is legitimate only as a **coarse
  arousal-state analogy** (Layer 1). It becomes decoration the moment it (a) leans on LF/HF specifically
  — a discredited sympathovagal index (Billman 2013, corroborated by Shaffer & Ginsberg 2017), (b)
  assumes a clean reciprocal balance axis (mainstream physiology shows sympathetic/parasympathetic
  often co-activate), or (c) resolves into discrete 证型/体质 labels.
- **Legitimate to say:** "your HRV this session leans toward a higher-arousal / lower-recovery state."
  **Not legitimate:** outputting a specific 阳虚/阴虚/nine-constitution label from HRV and implying it's
  evidence-based.

### 3b. What's computable, and the 30-second wall. (SURVIVED, minor wording fix.)

On a genuine **~30-second** window, only these are scientifically defensible (Munoz et al. 2015,
N=3,387; the standard ultra-short reference):
- **Mean HR / instantaneous rate** — valid.
- **RMSSD** (= Poincaré SD1) — valid (r=0.932 vs gold standard at 30s).
- **SDNN, pNN50** — *borderline* (SDNN Cohen's d=0.516; computable but 5-min normative meaning does not apply).
- **Everything frequency-domain (LF, HF, LF/HF, VLF) and every nonlinear metric beyond SD1 (SampEn,
  DFA α1) — INVALID at 30s.** They need 1–5+ minutes. Do not compute or show them for the on-demand session.

### 3c. The on-demand data problem that reshapes the product. (Engineering fact from Stream B; SURVIVED.)

**A third-party app cannot obtain true on-demand beat-to-beat RR intervals.** `HKHeartbeatSeriesSample`
is system-triggered only (an Apple DTS engineer confirmed there is no API to trigger it or read raw
beats), and a live workout session gives only ~5-second HR samples — far too coarse for RMSSD. So:

> **The only honest on-demand path to a real HRV reading is the ECG flow:** the user manually opens
> Apple's own ECG app for 30 s → the app reads the voltage series (`HKElectrocardiogramQuery`, ~512 Hz)
> → derive R-peaks → RR intervals → RMSSD + rhythm classification.

Consequences that must shape Phase 3:
- A literal one-tap "把脉 button that captures a fresh reading" **is not possible** — ECG can't be
  started programmatically. The realistic UX is "tap → you're guided into the ECG app → return."
- The *passive* numbers (resting HR, system-logged HRV SDNN — which is **PPG-derived PRV, not ECG RR**)
  are fine for baseline/trend context but are **not** a fresh capture and shouldn't be narrated as one.
- A pure-Shortcuts "reading" that just grabs the latest already-logged numbers is trivial to build but
  is a *snapshot of old passive data*, not a 把脉 moment. Be honest about which one you're shipping.

### 3d. The ground-truth problem — the single most important finding. (SURVIVED; every escape route collapsed.)

- There are **no labels**. An LLM's fluent TCM paragraph is evidence of *fluency*, not *correctness* —
  fluency and truth are orthogonal, and nothing in the model was ever trained on a validated RR→证 map.
- The human "gold standard" **isn't one**: TCM pulse-diagnosis inter-rater agreement is **κ≈0.34**
  (Jacobson et al. 2019 meta-analysis: mean 0.34, range 0.07–0.59; no study clears "substantial"
  κ=0.6). You cannot exceed the reliability of your own labels, and these labels are barely better than
  chance-corrected guessing.
- The skeptic tried every escape and all failed: the headline "99.47% ML constitution accuracy" study
  is **circular** (classifying a questionnaire's own items) and collapses to 67–68% on real external
  validation; pulse-wave ML at 80–90% uses *real clinical* ground truth (BP, ultrasound), not TCM
  labels; structured protocols lift κ only to 0.56.
- **Therefore the product can only ever claim to be self-consistent and personalized, never correct.**
  This is not a legal fig leaf — it is the only epistemics the evidence supports, and it *is* what
  "wellness, not diagnosis" has to mean. *(Minor nuance: if a "soft label" is ever wanted, self-reported
  constitution via the CCMQ questionnaire — α 0.7–0.86 — is more reliable than any sensor-inferred label.
  That still does not rescue an HRV→TCM classifier.)*

### 3e. Architecture: three options, one recommendation. (SURVIVED.)

- **(a) Rule-based** — transparent, but per 3a the rules would be grounded in analogy, not evidence;
  auditable groundlessness is still groundless.
- **(b) ML classifier** — **non-starter.** No trustworthy labels (3d), no dataset, and a ~3–5-feature
  input trying to learn an 8–14-way fuzzy classification from κ≈0.34 labels will under- or over-fit.
- **(c) LLM-does-it-all on raw numbers** — cheap, but indistinguishable from confabulation; LLMs also
  fail at multi-step numeric aggregation, and an ablation (fed scrambled features) would still produce a
  confident reading.
- **➡ Recommended: HYBRID** — deterministic, auditable, **personal-baseline-relative** feature
  computation, feeding a **constrained LLM** that narrates and personalizes but is **forbidden from
  inventing** any texture/quality it has no data for (no 弦/滑/涩, no tongue, no depth). Rule-based *for
  facts*, LLM *for voice*. This doesn't solve the ground-truth problem (nothing does) — it minimizes the
  surface area for confident fabrication. State openly that it's the *least-bad* option, not a triumphant one.

### 3f. Personal baseline, and the onboarding consequence. (SURVIVED.)

- Absolute HRV spans ~11× within a single age-and-sex band, so **population thresholds are near-useless**;
  only **deviation from the person's own rolling baseline** is informative.
- A usable personal baseline needs **~2–3 weeks** of repeated same-condition readings (converging
  guidance from HRV4Training, Garmin, HRV-training literature), improving for 1–2 months. This is a
  property of physiological variance — no algorithm shortcuts it.
- **Onboarding implication (load-bearing):** there is **no honest day-one 把脉 reading.** The first ~2–3
  weeks are an explicit "building your baseline" phase with no TCM interpretation (or only heavily
  caveated placeholder). Say so — it's good epistemics *and* good trust-building UX for free.

### 3g. What the LLM should receive. (SURVIVED.)

Not raw RR (forces the LLM to do error-prone arithmetic), not bare feature numbers (invites silent
population-norm reasoning). **Give it pre-digested, personal-baseline-relative facts in natural
language** — e.g. *"resting HR is 12% above your 14-day baseline; RMSSD is in your lower quartile."*
All computation, comparison and significance-thresholding happens deterministically *before* the model,
in code that can be tested. The LLM's job shrinks to what it's reliably good at: turning already-true,
already-hedged facts into readable, personalized, appropriately-uncertain prose, weaving in history.

**Tooling:** use **NeuroKit2** (MIT, peer-reviewed, actively maintained, and can also handle the raw ECG
QRS detection). `hrv-analysis` (GPL-3.0) is a lighter RR-only alternative — check license fit before
adopting. Avoid **pyHRV** (stale, documented R-peak bug).

---

## 4. Recommended data pipeline (Path 1 vs 1b vs 2)

| | Path 1 — Shortcuts + Health Auto Export | Path 1b — apple-health-mcp-server / Open Wearables | Path 2 — native watchOS/iOS app |
|---|---|---|---|
| Custom app? | No | No (MCP server) / effectively yes (Open Wearables SDK) | Yes |
| On-demand fresh reading | Weak — grabs latest *existing* passive numbers; for a real reading, still needs the ECG-app hop | **No** — batch XML export, minutes of latency; unusable live | Best — guided ECG flow + own backend; still can't auto-start ECG |
| Passive history/trends | Good — scheduled JSON/CSV/webhook export of RHR, HRV, sleep, respiration | Good — loads `export.xml` into DuckDB for LLM querying | Good — background delivery (throttled ~4 wake-ups/hr) |
| ECG voltage (needed for RR→RMSSD) | Health Auto Export **does** list ECG among exports — *verify it includes the full voltage series, not just classification* (§9) | **No** — parses only `export.xml`, not the `electrocardiograms/*.csv` voltage files | Yes — `HKElectrocardiogramQuery` reads per-sample voltage |
| Cost / friction | Free-ish (app may have a subscription tier); zero code | MIT, free; a Python/DuckDB service to run | $99/yr Apple Developer for ad-hoc family install (bypasses App Store review); free 7-day sideload for solo use |

**Recommendation for the first prototype: Path 1 (Apple Shortcuts as glue), no custom app.**
- *Passive trends:* Health Auto Export on a daily schedule → webhook → your store, feeding the personal
  baseline and the LLM history digest.
- *On-demand reading:* a Shortcut that guides the user through Apple's ECG app, then pulls the new ECG +
  latest passive numbers. Accept that this is a two-step flow, not one tap.
- **Skip the MCP server / Open Wearables for v1** — they add a service (or an embedded SDK = Path 2 in
  disguise) for interactive historical querying the prototype doesn't need; a periodic JSON digest gives
  the LLM equivalent trend context with fewer moving parts. Revisit the MCP server only if you later want
  Claude to run ad-hoc SQL over full history.

**What a native app (Path 2) actually adds:** a real one-tap UI (vs a Shortcut), denser HR sampling
during the window, your own backend, and near-real-time background pushes. **What it does NOT add:** raw
PPG, programmatic ECG start, or on-demand true RR — those three ceilings are enforced by watchOS itself,
identical whether native or not. So building native is a UX/control upgrade, **not** a data-access
upgrade. Don't build it expecting new signal.

**Gotchas to carry into planning:** HealthKit hides read-denial from your app (a zero result = "denied"
or "no data", indistinguishable); background delivery is throttled; Watch→iPhone→export sync lags
seconds-to-an-hour; automations need the phone unlocked. Design the "30-second reading" around "grab the
freshest data HealthKit already has + a fresh ECG", never "capture live sensor data this instant."

---

## 5. Repo verdicts + build-fresh-vs-reuse

| Repo | What it is | License | Verdict |
|---|---|---|---|
| QLU-NLP/**BianCang** | Fine-tuned TCM diagnosis LLM (Qwen2.5, 7B/14B), published, weights work | none/"academic only" | **REFERENCE** for the reasoning layer (see §6 — a raw fine-tune is *not* the recommended runtime) |
| jangviktor-web/**nihaixia** | Claude Agent Skill; distilled classical TCM texts incl. pulse/tongue theory | MulanPSL-2.0 (clear OSS) | **REUSE** — best-fit *knowledge source* for grounding the reasoning layer's phrasing |
| TCMAI-BJTU/**LingdanLLM** | TCM LLM (Baichuan2-13B), JAMIA-published; HF weights gated | none/gated | **REFERENCE** (paper/architecture; more friction than BianCang) |
| JuneYaooo/**nihaisha-nishi-tcm** | Claude Agent Skill, TCM course-notes retrieval | none declared | **REFERENCE** (overlaps nihaixia, no clear license) |
| yasenstar/**Chinese_Medicine** | TCM ontology/knowledge graph | GPL-3.0 | **SKIP** |
| the-momentum/**apple-health-mcp-server** | MCP server: Apple Health XML → DuckDB → LLM-queryable | MIT | **REUSE as passive-history infra only** (not for v1; §4) |

**The key judgment (confirmed, not refuted):** every TCM repo is **text-in / text-out** syndrome
differentiation (辨证) or a knowledge package. **None ingests RR intervals, HRV, or any numeric signal;
none maps signal → TCM feature.** So **the hard signal layer has no existing solution to borrow — it must
be built fresh** (the hybrid of §3e). What *is* reusable is the **reasoning/knowledge layer**: keep
**nihaixia** (clear license, distilled classical pulse-quality knowledge, already Claude-pluggable) as
retrieval grounding, and **BianCang** as a reference/comparison.

---

## 6. The LLM verdict + swappable architecture

**Is Claude load-bearing, or a commodity slot? — Task-dependent; "commodity" was overstated. (DOWNGRADED.)**

The original clean answer was "commodity — any frontier model with a good prompt beats a small TCM
fine-tune." The skeptic dented this hardest and it's the honest split:
- **Against "commodity":** on *TCM syndrome differentiation* (case → 证型, close to this app's reasoning),
  **BianCang-Qwen2.5-7B scored 78.9% vs DeepSeek-R1 (671B) at 37.2%** — a small fine-tune beating a
  frontier general model >2× on exactly that task type. Fine-tuning genuinely helps *produce the
  standardized TCM label from a case*.
- **For "commodity":** on *open-ended diagnostic-suggestion generation* (closest to this app's hedged
  narrative output), **GPT-4 (78.2) beat BianCang (69.6)**, and a **RAG-augmented general model beat both**
  on all tasks. On broad knowledge/exams, general models win and fine-tuning *degrades* base reasoning.
- **"Any frontier model" is also false** — DeepSeek-R1 vs GPT-4o swing ±17–26 points across TCM task
  types, so model choice matters as much as the fine-tune question.
- **No benchmark tests this app's actual shape** (numeric HRV/ECG parsing + a hedged structured-output
  contract). So the central claim is an untested inference in both directions.

**Practical recommendation (unchanged by the downgrade):** start with **Claude on the Pro/Max
subscription** — zero marginal cost, most mature agentic/memory tooling — and pursue **frontier-model +
RAG grounding on curated TCM knowledge (e.g. nihaixia)** rather than either a raw ungrounded general
model *or* a raw fine-tune. RAG-beats-both is the reconciling finding between Streams D and E. Keep the
option to route a first-visit "deep read" to a stronger model and routine re-reads to a cheaper one.

**Swappable adapter (build it now, even while 100% on Claude):**
```
interface TCMReasoningAdapter:
  generate_reading(features, history_digest, profile, system_prompt) -> TCMReading
    # features: personal-baseline-relative, natural-language (per §3g)
    # history_digest: app-built summary of prior visits/advice/corrections — NOT a raw chat log
    # system_prompt: provider-agnostic TCM framing + safety rules (no Claude-only XML/MCP in the contract)

struct TCMReading:  # a fixed JSON schema via each provider's structured-output mode
  tcm_pattern_summary   # hedged pattern language only ("脉象偏气虚倾向"), never a diagnosis
  confidence_note       # explicit "wellness pattern read, not a diagnosis"
  advice { diet[], routine[], rest[], exercise[] }   # 食疗/作息/休息/运动
  flags[]               # e.g. "resting-HR trend outside your usual — consider seeing a doctor"
  provider_metadata { provider, model_id, latency, cost }
```
**Memory lives app-side** (your DB, keyed by person), and the adapter receives a *summarized* digest — so
DeepSeek/Qwen can be swapped in with no knowledge of prior "conversations." Model choice becomes a config
value. Skip a plugin marketplace / multi-provider fallback orchestration (YAGNI).

**Privacy (the biggest caveat):** the cheapest tier — Claude **consumer Pro/Max** — now has a
"help improve Claude" training toggle that **ships pre-set to on** (retention up to 5 years if left on;
30 days if off), and it applies to Claude Code under a Pro/Max login. **Go turn it off** before any real
family health data flows through it. When this becomes something others depend on, move to the **API**
(no training by default; Zero-Data-Retention available). DeepSeek trains by default and is China-hosted
with state-access obligations; Qwen consumer terms are silently permissive (Alibaba's enterprise Bailian
claims no-training — verify contractually). For *your own* data this is low-stakes; for *family* data it
is not.

**Regulatory posture (one line):** stay on the FDA/EU-MDR/NMPA **general-wellness** side by never emitting
a diagnosis, prognosis, or treatment tied to a named disease. FDA's Jan-2026 general-wellness guidance and
Anthropic's own Usage Policy both explicitly carve out wellness/sleep/stress/nutrition/exercise advice as
*not* high-risk — which is exactly this framing. Required scope-limiting language: "not a medical device;
does not diagnose, treat, cure or prevent disease," shown persistently; an AI-disclosure each session; a
no-emergency-reliance clause; a hard output-level block on named-disease phrasing; and a per-person,
consult-a-professional close on every reading. **Prior art exists and is crowded** (思尔 AI 脉诊手表,
知脉/MaiWatch, WATCH2CARE; Huawei/Xiaomi reportedly entering) — most lean on purpose-built pressure
sensors and aggressive "AI 老中医" branding already drawing state-media scrutiny. This project differs by
starting from *validated HRV/HR metrics* and *honest hedging*, not a doctor-replacement claim — a genuine
differentiator only if the wellness-only line holds.

---

## 7. The self-improvement verdict

**Is a real self-learning layer worth building, or is record-keeping enough? — Record-keeping (+ the 复诊
memory digest) for v1; a self-learning layer is premature *at this data density*, not impossible. (DOWNGRADED.)**

- The original "epistemically unsupported — you can't define 'improved' without ground truth" reasoning is
  **wrong**, and the skeptic refuted it: RCT-validated closed loops define the reward as the person's *own*
  trajectory, no external ground truth needed — **DIAMANTE** (+19% steps vs 3.9%), **REINFORCE** (+13.6%
  adherence), and most on-point **AddHRVr/JITAI**, which literally triggers interventions when RMSSD drops
  >0.5 SD below the *individual's* baseline and measures the rebound. "Move toward your own baseline" is a
  validated, publishable target.
- **But** every one of those runs on **high-frequency, short-horizon** data — dozens–hundreds of
  micro-decisions per person, reward observed within minutes. The **复诊 loop yields one point per visit,
  weeks apart** — orders of magnitude sparser and heavily confounded. No evidence shows adaptive
  personalization working at visit-scale density.
- **➡ Verdict:** build **record-keeping** (advice given → subsequent personal-baseline-relative trend →
  surface the correlation to the user for reflection) and feed that history into the **LLM memory digest**
  for the 复诊 loop. That is the whole v1. A genuine adaptive/RL self-improvement layer is a *later* option
  that becomes worthwhile **only if** you move to high-frequency passive triggers (JITAI-style on daily
  HRV) rather than sparse visits — note that as a future direction, not v1 scope.

---

## 8. What the skeptic pass killed or downgraded (explicit)

**Downgraded (stated above in their softened form):**
1. **"Texture pulses are *physically* unmeasurable"** → **access/engineering limit, not physics.** Apple's
   own hypertension feature proves the stiffness signal exists in the wrist sensor; hobbyists just have no
   API to the raw waveform and face contact-pressure noise. *Depth (浮/沉) remains genuinely unmeasurable.*
2. **"Poor sleep reliably tracks sleep debt"** → reliable at *trend* level, **noisy/confounded for a single
   night.** Reinforces the baseline/trend framing.
3. **"痰湿 NOT SUPPORTED"** → **weak indirect proxy** via the 痰湿质→metabolic-syndrome→low-HRV chain
   (two hops, fully confounded). Still not a clean signal.
4. **"The LLM is a commodity slot / any frontier model beats a TCM fine-tune"** → **task-dependent and
   untested on this app's shape.** Fine-tunes win at syndrome-labeling; general models win at hedged
   open-ended advice; RAG beats both. Practical rec (start on Claude, RAG-ground it) unchanged.
5. **"A self-learning layer is epistemically unsupported"** → the target *is* definable (personal-baseline
   deviation, RCT-validated); it's **premature at visit-scale data density**, not impossible.

**Killed (did not survive, do not carry forward):**
- The specific idea that raw PPG is *fundamentally* out of reach — it's *API*-out-of-reach for hobbyists
  (SensorKit exists for IRB-approved research). Correct the reasoning even though the practical
  conclusion (hobbyist can't get it) stands.

**Survived intact (some reinforced by the attack):** the no-credible-HRV→TCM-literature finding; the 30s
metric-validity split (mean HR + RMSSD only); the no-on-demand-RR engineering fact; the ground-truth /
κ≈0.34 verdict and the abandon-diagnosis pivot; the ML-classifier-is-a-non-starter call; the hybrid
architecture; the ~2–3-week baseline requirement; the pregnancy and mortality hard-exclusions; and the
signal-layer-must-be-built-fresh repo judgment.

---

## 9. Open questions & risks for Phase 3 (R&D planning)

1. **ECG voltage export path.** Confirm whether **Health Auto Export** exports the *full 512 Hz voltage
   series* (required to derive RR → RMSSD without a native app), or only classification + average HR. This
   decides whether the on-demand reading is buildable on Path 1 or forces Path 2. **Highest-priority unknown.**
2. **Deriving RR from single-lead ECG.** Validate an R-peak → RR → RMSSD pipeline on real Apple Watch ECG
   exports (NeuroKit2). How clean is 30 s of Apple ECG for RMSSD in practice, on wrist, with motion?
3. **Baseline onboarding UX.** How to make the ~2–3-week "no reading yet" phase feel like progress, not a
   broken product. What minimal, honest feedback is allowed pre-baseline?
4. **The narrative-honesty boundary.** Exactly how to constrain the LLM so it produces engaging
   TCM-flavoured prose *without* over-claiming or inventing textures — this is a prompt+output-schema+guardrail
   design problem, and the main product-quality risk. Consider an output validator that hard-blocks named
   diseases and unmeasured pulse qualities.
5. **RAG grounding source.** Decide how to use nihaixia's classical pulse knowledge as retrieval context
   without letting it license 弦/滑/涩 claims the sensor can't support.
6. **Which "reading" ships first.** The trivial passive-snapshot Shortcut, or the real ECG-flow reading?
   They're very different products; pick deliberately.
7. **Caregiver/family multi-user model.** Per-person baselines, data separation, and non-transferable
   readings — plus the privacy toggle discipline — before anyone but you uses it.
8. **Provider privacy discipline.** Confirm the Claude training toggle is off before family data flows;
   plan the API migration trigger.

---

## 10. Things you may have wrong, and things you didn't ask

- **The core metaphor is the weak point.** "Apple Watch = the doctor's fingers" is the part that breaks —
  fingers sense pressure/texture, the watch senses timing. The half that *does* survive is the doctor who
  knows your history and watches your trends. Lead the product with *that*, and the TCM framing becomes
  honest flavour rather than a false claim.
- **"~30-second reading" quietly assumed you get beat-to-beat data on demand. You don't** (§3c). This is the
  biggest gap between the original mental model and reality — the reading is really "guided ECG + your
  existing trends," and there's no honest reading at all until a baseline exists (~2–3 weeks).
- **You didn't ask how you'd know it works.** The ground-truth problem (§3d) is the deepest issue in the
  whole project and it has no clean answer — plan around "self-consistent + convergent with your own sleep/
  self-report," never "correct."
- **You didn't ask about menstrual-cycle confounding.** For any female user, luteal-phase resting-HR/HRV
  shifts mimic both "fever/stress" and "early pregnancy" signals — a real source of false readings that
  needs cycle-awareness or explicit caveating.
- **Consider dropping "把脉" from the user-facing framing** and keeping it as internal inspiration. The AI
  把脉 space is already drawing regulatory/state-media scrutiny; "personal TCM-flavoured wellness trends"
  is both more honest and safer than "AI takes your pulse like a 老中医."
- **The most valuable thing you could add is boring:** cycle/sleep/context tagging and a clean personal
  baseline, not a cleverer model. The model is the commodity; the honest, well-grounded, personalized
  *data layer* is the moat.
