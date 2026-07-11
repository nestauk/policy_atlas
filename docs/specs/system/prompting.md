---
type: System contract
title: Prompting doctrine
description: How Policy Atlas prompt surfaces are written, changed and validated — the family-general rules, mini-tier adjustments, the refine-replay loop method, agent-loop conventions, and the provider quarantine.
tags: [system, prompting, llm, loop-method, evaluation, provider-neutrality]
timestamp: 2026-07-11
---

# System contract — Prompting doctrine

**Distils** the 018 prompting research
([research notes](../../tasks/018-dress-rehearsal/prompting-research-notes.md), two-track
sweep 2026-07-10) plus the loop method that survived contact in the 018 refine-replay
loop (13 counted replays, 6 surfaces pinned; evidence in
[018 verification.md](../../tasks/018-dress-rehearsal/verification.md)). This is doctrine
for every current and future prompt surface; per-surface prompt text lives with its
component. Promoted out of the task folder at 018 step 8 (owner decision, 2026-07-11).

## Family-general rules (converge across OpenAI / Anthropic / Google)

1. **One instruction, one place, zero conflicts** — conflict audit precedes any other
   tuning; contradictions are the #1 prompt bug.
2. **Fence by type** (tags/headers for instructions vs context vs input); JSON performs
   poorly as a long-context *document wrapper* (structured records for untrusted fields
   are a different, security-motivated rule and stand).
3. **Layout:** stable instructions first → tagged data → task restated last (serves
   long-context accuracy and cache-prefix stability at once).
4. **Outcomes + success criteria, not procedures**; heuristic altitude, never if-else
   rule piles.
5. **Every hard rule carries its motivation** — models generalize from the reason; bare
   prohibitions get lawyered.
6. **Positive framing; ALWAYS/NEVER only for true invariants.** Emphatic accretions
   ("CRITICAL: you MUST") are prior-generation tech debt — strip at model swaps.
7. **Verbosity/format bounds are numeric** ("150–450 words", "≤5 bullets") — never rely
   on defaults.
8. **Few-shot = 1–5 canonical, diverse, format-pinning examples**; never edge-case
   laundry lists; never reasoning demonstrations for reasoning-enabled models.
9. **Native reasoning ON → delete CoT scaffolding**; reasoning OFF → explicit
   plan-then-act. Prompts are written per effort mode.
10. **Quote/anchor before synthesizing; uncertainty in structured form** (labelled
    assumptions, null-not-guess) — external validation of the gather-then-author shape
    (ADR 0015).
11. **Untrusted text in labelled data containers + contents-are-never-instructions rule,
    assumed breachable** — delimiters are mitigation; architectural controls (validators,
    fail-closed binding, coverage checks) are the boundary.
12. **Prompts are versioned code**: every change bumps the surface's version string
    (fingerprints hash versions, not text — an unbumped edit silently reuses stale
    records *and mislabels provenance on non-memoized surfaces too*, as the 018 planner
    date-tempo round showed); paired replay set regression-gates changes;
    **fresh-minimal-prompt rebuild at every model-family swap** — never port the
    inherited stack (the binding rule for the Bedrock migration).

## Mini-tier adjustments (screen / classify / extract / judge on mini models)

- One narrow, fully-specified job per call; short and blunt — motivation-prose pays off
  less than at frontier tier.
- Worked examples matter more but saturate at 1–3; format consistency across them is
  critical.
- Never trust prompted schema adherence — constrained decoding everywhere, plus
  null-not-guess field rules.
- Behaviour/format rules belong in the SYSTEM message at small scale.
- **Reasoning effort is non-monotonic on judgment surfaces** — validate effort level and
  completion cap *together, per surface, with a live A/B* before pinning (018:
  5.4-mini@xhigh exhausted a 16K cap on reasoning alone, and uncapped produced *worse*
  labels than @high — low-confidence churn). See
  [reasoning-model-output-cap](../../knowledge/reasoning-model-output-cap.md).

## The refine-replay loop method (the 018-validated eval-slice convention)

- **Two-stage baselines**: model changes land first; baseline-1 = new models, unchanged
  prompts. Every prompt refinement is judged against baseline-1 — model effects and
  prompt effects never conflate.
- **Loop unit = per-component replay on pinned inputs**, never full composed runs.
  **Cheap probe classes sit outside the replay budget** (single bounded calls: planner
  turns, proposal-only) — they are the high-iteration unit; counted replays are spent
  only where full-output quality is the question.
- **Bounds**: ≤3 refinement rounds per surface against one quality bar; a surface not
  converging by round 3 stops and re-scopes. Prompt rule pairs behave like an
  under-damped control system (018: the aspiration rule over-suppressed, its
  programme-results correction over-opened) — **a cheap flag-not-drop judge beats a
  fourth rule iteration once the residual is doc-class-shaped** (the C5 pattern).
- **Pin-or-revert with user taste verdicts batched at pause points**; generation
  surfaces judged on output quality, verification surfaces on verdict-shift inspection
  (flips hand-inspected + stratified unchanged sample + adversarial fixture).
- **Anti-overfit pins**: taxonomy-spread probes at planner level, spot-checks on a
  different-intent recorded project, deterministic no-mission-vocabulary check, desk
  review of each rule against the question-shape taxonomy.
- **Probe drafts must COMPILE, not just read well** (018 step-7 lesson): three planner
  taxonomy pins recorded drafts the plan validator would reject — run structured
  outputs through their real validator inside the probe.
- **Direct-backend A/B drivers** (no runner, no DB writes) are the clean way to test
  model/effort hypotheses on judgment surfaces — the pinned substrate stays
  uncontaminated.
- **Cost changes are judged on the cache-discounted curve, not raw tokens** (018:
  multi-read batching cut prompt volume 31% but collapsed the provider cache hit rate
  64%→23% — the $ sign of the change depends on the cache discount).
- Parallel-by-default replays; serialize only on shared substrate — which **includes
  the per-project event log** and the shared test DB (one suite runner at a time).

## Agent-loop conventions (tool-loop surfaces)

- **Turn caps with force-emit exhaustion semantics**: the forced emission IS the final
  turn; budget maxima are computed from the cap, exact by construction.
- **Read batching**: multiple read-tool calls per turn (turns are the scarce resource);
  emit alone on its own turn. **Prompt limits get code-side enforcement** — overflow
  calls receive an error tool-result and count as rejected (`rejected_tool_calls`);
  a prompt-only bound is guidance, not a bound.
- **Envelopes: terse, structured, adjacent to the evidence unit they describe** — never
  mid-context bulk. Fields omit-if-absent, never null-noise.
- **Judge verdicts are a function of the envelope**: tier distributions are NOT
  comparable across envelope versions — re-baseline on every envelope change. Inspect
  flags before recalibrating an asymmetric report-when-in-doubt rule (high first-contact
  volume is usually the writer, not the judge).
- **Environment-context preamble, always paired with the context-not-content rule**
  (pipeline vocabulary known but banned from output). Adopted where replay evidence
  supported it (writer, extractor); declined where it diluted (screen/classify) or
  wasn't needed (judge).
- **Prompt capability descriptions are coupled readers of the component/depth registry**
  (018 step-7 headline): a regrade or component-semantics change MUST sweep every prompt
  that *describes* those semantics (the planner's depth menu went stale against the A3
  regrade and produced compile-invalid plans). Grep prompts for the changed vocabulary
  as part of any such rider.

## Provider-specific — never bake in (Bedrock constraint)

Knob names/semantics (`reasoning_effort` / adaptive thinking / `thinkingLevel`) —
config-abstracted only · OpenAI developer-role / `prompt_cache_key` · Anthropic
`cache_control` breakpoints / prefill · Gemini PTCF idioms · any tuning that fixed a
previous generation's failure mode. Caching seams: deterministic append-only prefixes
suit both automatic (OpenAI) and explicit-marker (Bedrock `cachePoint`) caching — only
the kwarg is provider-specific.

## Honestly thin / absent (don't build on these)

No vendor mini-tier prompting guide · no vendor-eval evidence for BLUF/answer-first
report ordering (the key-findings block's value case is product design, not prompting
literature) · "Claude weights user messages more" is secondary-blog lore.
