# ADR 0011 — Two-stage consensus screening + live classify (first product reads of third-party text)

**Status:** Accepted — 2026-07-08 (Shabeer Rauf; task 014 contract rev 1.10 + plan rev 5).
The round-by-round decision trail lives in the task 014 contract's revision history
(revs 1–1.10, ten adjudicated rounds: five user gate challenges, a /last30days field
scan, the V2 screen/classify autopsy, two Codex adversarial reviews and a scoped delta
review).

## Context

Tasks 004/005 shipped `screen` and `classify` as deterministic stubs; the live-demo
sequencing (adjudicated 2026-07-08) makes them the first slice of the path to a live
demo. This slice opens the product's first LLM reads of acquired third-party text
(envelope and full text), so the injection posture recorded at task 007 (decision 9)
comes due here.

## Decisions

1. **Consensus screening at the envelope** — each stage-1 screen decision is
   `SCREEN_REPS = 3` independent samples of one surface (`screen_v1`, gpt-5-mini):
   majority vote with a recall-preserving ladder (three-way wire vocabulary; `unsure`
   counts relevant in the vote; ties → relevant; title-only exclusion requires
   unanimity; quorum ≥ 2 surviving reps, else the doc fails retryably). Persisted
   confidence is a **consensus probability over all surviving reps** (dissent lowers it
   in proportion to the dissenter's conviction; `unsure` contributes a directionless
   0.5). Vote and probability may diverge — kept-in-but-shaky is the honest
   recall-first outcome. Field-grounded: LLM4SCREENLIT's referred-back-positives rule,
   OLIVER's weak single-model calibration, the dual-model-ensemble sensitivity result,
   V2's own `SCREENING_RUNS=5` tooling and 0.400 worst-corpus recall.
2. **Two-stage screening as ONE stage-parameterised component** — the plan's
   thoroughness directive (`context["screening"]["stage"]`, fail-closed) selects; a
   deep run = two runs of the component (the 012 group-twice precedent; facade
   principle), mirroring systematic-review practice. Stage 2 (`screen_fulltext_v1`,
   single-rep, windowed full text, text-availability-scoped) is **demote-only,
   enforced as a write invariant** — recall is won at stage 1 or not at all. Both
   stages persist (`screen_stage` provenance; stage-1/stage-2 pairs are an eval
   dataset by construction).
3. **Effective-screen helper as the universal read rule** — highest-stage non-failed
   row per (scope, source); raw `status='relevant'` joins are structurally wrong under
   two-stage rows (demotion leak / double-read — delta-review blocker). Select reads
   the effective row wholesale (**select = stage-3 of the screening cascade**, ranking
   on the most-informed per-doc judgment, `screen_stage` carried into its rationale).
   The asymmetric-demotion survivorship question (abstract-only docs are unejectable
   past stage 1) is a named eval-seam measurement.
4. **Failures never block retry** — `uq_ssr_scope_source` becomes a partial unique
   index over (scope, source, stage) excluding `failed` (011 extraction-memo
   precedent); screen failures persist as attempt history; classify failures write no
   row (an API failure is not a classification claim).
5. **Live classify on the judgment tier** — single-call, closed 9-value label +
   bounded methodological/structural tags into `source_tag`
   (`tag_type='methodological_structural'`, helper API change) + payload-only
   confidence/reason; `CLASSIFY_MODEL = "gpt-5.5"` (V2's human-labelled eval: mini-class
   ≈ 50% vs judgment-class ≈ 76% on the identical taxonomy; the lesson generalises to
   the tier, not the checkpoint — mini swap-down is eval-gated). Explicit
   Unknown-vs-Other prompt boundary (Other excludes from select/extract; Unknown is
   kept-and-eligible).
6. **Injection posture enforcement** — titles/abstracts/provider fields enter prompts
   as id-keyed data records via closed allowlists with per-field caps and control-char
   stripping; outputs schema-constrained and code-validated; **paired clean/adversarial
   fixtures assert semantic invariance** (a valid-but-steered label fails the test);
   NUL scrub at the backend boundary.

## Rejected

- Separate `screen_fulltext` registry component (spec has one screen; parameterise it).
- Banding for the (seam-recorded) screen-confidence retrieval boost — clamped
  functional multiplier chosen (cliff effects).
- Mean-of-majority consensus confidence (2/3 indistinguishable from 3/3).
- `unsure` as a status value (downstream relevant-filters would make it silent
  exclusion) and reuse of unsure's own confidence in the probability (a
  0.9-confident-unsure would outvote a 0.8-confident-relevant).
- Stage-1-only confidence in select (made select the sole hybrid reader).
- Borderline-band-only stage-2 (two-regime confidence scale; uniform-or-nothing).
- Classify consensus voting (9-label votes splinter; tie-breaks inflate Unknown) and
  the stub-era classify-failure→Unknown fallback.
- Building classify Unknown-resolution / two-stage appraisal now (recorded seams; the
  appraisal pass carries an unsettled rubric design).
