# Plan: 014-llm-screen-classify

> **Status:** **rev 4** — scoped delta review adjudicated (Codex on
> the stage-2 amendment: 2 blockers · 7 majors, 9/9 adopted):
> effective-screen helper replaces the abolished "relevant-only =
> safe" reader class; select = stage-1 confidence only; no-rescue
> write invariant; text-availability predicate; generic window
> helper; wiring consolidated in task 8; three-prompt/four-change
> wording fixed. Awaiting the reopened 🛑 (contract rev 1.9 + this).
> Rev 3: contract rev 1.7/1.8 amendment folded in (stage-2 screen,
> single-component design, tasks 2b/5b). Rev 2 base: plan-stage
> adversarial review adjudicated (Codex, 9 findings, 9/9 adopted). Contract: [contract.md](contract.md) **approved rev 1.5.1,
> adjudicated rev 1.6 (Codex 10/10), ⚑ remedies user-confirmed
> 2026-07-08**. ADR due at plan confirmation (step 4): injection
> posture + consensus screening are capability-class decisions.
>
> **Rev 2 adoptions:** classify `confidence`/`reason` into
> `source.classified` payload with task owner (task 6) + payload
> tests (tasks 9/10) · `screen_basis` computed in code BEFORE backend
> calls, owner pinned in task 5, title-only behaviour tested
> independent of model output · `skeleton.py` reclassified UNSAFE in
> the reader table (raw attempt-row logs at l.660/949) with a concrete
> fix action · **Phase-4 gate fix**: `screen_sources`/
> `classify_sources` take optional backend params with stub defaults
> so Phase 4 stays green before Phase-5 harness wiring · reader table
> revised to exact per-file actions (task 7 stays fast-worker;
> ambiguous discoveries escalate to lead) · borderline band pinned:
> sorted non-failed docs by persisted confidence,
> `max(1, ceil(0.10*n))` incl. ties at cutoff, ∪ all non-unanimous ·
> per-doc `aggregation_flags` on `source.screened` (e.g.
> `["tie_broken"]`, `["title_only_unanimity_applied"]`), test-asserted
> · test-only `ScriptedScreeningBackend`/`ScriptedClassificationBackend`
> in task 10 (013 scripted-loop precedent; production stubs stay
> sentinel-pure) · **classify model pin RESOLVED**: `CLASSIFY_MODEL =
> "gpt-5.5"` exactly — if unavailable at build start that is a
> stop-condition escalation, never a silent substitution.

Executor routing per harness.md § Agent-side model routing: default =
delegate; every `lead` mark carries a justification.

## Plan-pinned constants

- `SCREEN_REPS = 3` · quorum ≥ 2 surviving reps · unsure → vote
  relevant / probability 0.5 · title-only exclusion requires unanimity
- Stage 2 (rev 3): `STAGE2_REPS = 1` · retry cap 1 ·
  `STAGE2_WINDOW_CHAR_BUDGET = 60_000` first-window over canonical
  chunks (extract's windowing helper; ponytail ceiling — heading-map
  sampling at the eval seam) · stage-2 budget ≤ full-text docs × 2
  calls · unsure → relevant at stage-2 confidence · demote-only
- Screen model `gpt-5-mini`; **`CLASSIFY_MODEL = "gpt-5.5"`** (exact
  pin, rev 2 — assessed vs `gpt-5.6-terra` and resolved at this gate;
  unavailability at build start = stop-condition escalation, never
  silent substitution; the mini swap-down stays eval-gated)
- Retry cap 1 per call · screen call budget ≤ docs × 3 × 2 ·
  classify budget ≤ docs × 2 · doc-level concurrency 4, reps
  concurrent within doc (≤ 12 calls in flight)
- `reason` ≤ 240 chars · classify tags ≤ 10/doc, ≤ 100 chars each,
  control-char-rejected (009 provider-tag bounds)
- Provider-prior allowlist into `classify_v1`: `record_type`,
  Overton `source.type`, `organisation_type`, provider topic labels
  (≤ 10, each ≤ 100 chars); every field ≤ 500 chars,
  control-char-stripped at prompt assembly. Screen prompt data
  fields: title, abstract, `abstract_source`, scope intent
  (id-keyed data records, never instructions)
- Wire models (pydantic, strict): screen rep
  `{decision: relevant|not_relevant|unsure, confidence: 0..1,
  reason}`; classify `{primary_evidence_type: <9 closed values>,
  tags: [..], confidence: 0..1, reason}`
- Persisted screen confidence = consensus probability (decision 3);
  event payloads carry per-rep records + agreement count
- PROMPT_VERSIONs: `screen_v1` · `classify_v1` · `screen_fulltext_v1`
  (8th/9th/10th product prompts, lead-authored; rev 4 fix)
- Stage-2 availability predicate (rev 4, 013 text-availability
  lesson): `full_text_status = 'ingested'` OR envelope
  `text_basis = 'full_text'`
- Select stage rule (rev 5, user call): select reads the **effective
  row wholesale** — candidate set, status AND confidence from the one
  effective-screen helper row (select = stage-3 of the cascade);
  `ScreenedSource.screen_stage` carried + recorded in the selection
  rationale; estimator-difference calibration → eval seam
- Migration 14 (rev 4 fix — FOUR changes): `screen_stage` column
  (1|2, NOT NULL default 1) · `screen_basis` CHECK gains `full_text` ·
  partial unique over (scope, source, stage) WHERE status<>'failed' ·
  `ck_stag_tag_type` widen to
  (`topic_theme`,`methodological_structural`); table count
  stays 25; roundtrip BOTH DBs (011 lesson 13f909c)

## Reader enumeration (contract decision 5, rev 1.6 M7)

Verified by grep over `source_screening_result` consumers:

| Reader | Class | Action |
|---|---|---|
**Rev 4 (delta-review blocker): the "relevant-only = safe" class is
ABOLISHED** — under two-stage rows a raw `status='relevant'` join
includes demoted docs and double-reads confirmed ones. ONE shared
**effective-screen helper** (highest-stage non-failed per
(scope, source); authored in task 5, codex) is the read rule for
EVERY reader below; task 7 applies it mechanically + regression
tests per reader (demoted · confirmed · failed-stage-2 ·
failed-then-retried cases each):

| Reader | Action (all via the helper) |
|---|---|
| `screen.py` NOT-EXISTS guards | stage-1: no non-failed stage-1 row; stage-2: candidate = effective stage-1 relevant + text-available + no non-failed stage-2 row (task 5/5b) |
| `classify.py` relevant join + `total_relevant` + `skipped` | effective-relevant join; effective-status distinct-source counts (task 6) |
| `characterise.py` `_base_counts` + relevant join | effective-stage-and-status (task 7) |
| `select.py` `ScreenedSource` (l.484-488, l.972-981, l.1509) | effective row wholesale (status + confidence) + `screen_stage` carried into rationale (rev 5; task 7 + task 8 wiring) |
| `synthesise.py` (l.720-723) + `synthesis_tools.py` (l.691-697) screened-in scope | effective-relevant (task 7) |
| `ingest_full_text.py` relevant read | effective stage-1 relevant (stage 2 runs post-ingestion — fetch must not consult stage-2 rows; task 7) |
| `skeleton.py` summaries (l.660, l.750-752, l.949) | effective-stage-and-status distinct-source; attempt/stage history split into its own log line (task 7) |
| `appraise.py` | verify + effective join + regression test (task 7) |

## Tasks

**Phase 1 — schema (full `make verify` gate)**
1. Migration 14 (both changes) + `schema.py`
   `METHODOLOGICAL_STRUCTURAL` constant; roundtrip 25↔25 both DBs.
   — **lead** *(gated schema surface; migration authorship lead on
   every slice since 001)*

**Phase 2 — prompts + wire models**
2. `screen_v1` + `classify_v1` prompt surfaces + strict wire models +
   prompt module. Pins from contract: holistic-probability elicitation
   (never additive facet rubrics — V2 root cause), missing-abstract
   rule, Unknown-vs-Other boundary definitions, data-record framing.
   — **lead** *(prompt-bearing work is lead-only, AGENTS.md)*
2b. `screen_fulltext_v1` prompt (10th surface, rev 3): precision
   posture (stage 1 already protected recall; stage 2 asks "does the
   full text confirm relevance to the scope intent?"), windowed-text
   payload framing (id-keyed data), unsure→relevant rule restated.
   — **lead** *(prompt-bearing)*

**Phase 3 — backends + helper**
3. `screening_backend.py` + `classification_backend.py`: protocols
   (`mode`), OpenAI impls (traced_call spans, in-span validity scores,
   NUL scrub, retry cap 1, provider-prior allowlist serializer with
   caps + control-char strip), stub impls preserving `_stub_screen` /
   `_stub_classify` sentinel behaviour verbatim. — **codex**
   *(judgment-bearing implementation, machine-verifiable done)*
4. `tags.insert_source_tags` API change (`tag_type` param, default
   `TOPIC_THEME`; tests both types, existing callers untouched).
   — **fast-worker** *(mechanical, exact spec)*

**Phase 4 — component reworks (full `make verify` gate)**
5. `screen.py` consensus rework: **optional `screening_backend` param,
   stub default (rev 2 — keeps the Phase-4 gate green before Phase-5
   wiring)**; `screen_basis` computed IN CODE from abstract presence
   BEFORE any backend call, persisted + in the event payload,
   title-only behaviour tested independent of model output (rev 2);
   3 concurrent reps, vote (unsure→relevant, quorum ≥2, title-only
   unanimity, 1-1 tie→relevant flagged), consensus-probability
   confidence, per-rep event payload + agreement count + per-doc
   `aggregation_flags` (rev 2), non-failed NOT-EXISTS, summary
   counts (unsure · non-unanimous · rep_failures · tie_broken).
   — **codex**
5b. Stage-2 path inside `screen.py` (rev 3; single-component design
   rev 1.8 — NO new registry entry): fail-closed
   `context["screening"]["stage"]` directive parse (1 default · 2;
   unknown → structural failure); stage-2 candidate set = effective
   stage-1 relevant docs with ingested full text AND no non-failed
   stage-2 row; windowed payload via extract's helper; single rep,
   demote-only persistence (stage-2 row, `screen_stage=2`,
   `screen_basis='full_text'`), stage-1-stands-on-failure, counts
   (`stage2_screened/confirmed/demoted/failed/skipped_no_fulltext`);
   `screen_stage` in every `source.screened` payload (rev 4, owner
   pinned); the **no-rescue WRITE invariant** (stage-2 insert
   transaction proves effective stage-1 relevant; regression:
   stage-1-exclude + attempted stage-2-include fails); the
   **effective-screen helper** authored here (used by every reader,
   task 7); the **generic chunk-window helper** extracted with
   explicit budget/overlap params + `ScreenFullTextPayload`
   (extract's `_window_payloads` is coupled to
   `ExtractionWindowPayload`/module-global budget — extraction keeps
   a wrapper, behaviour test-pinned unchanged). Skeleton/harness
   wiring is task 8's (rev 4 consolidation). Reuses the task-3
   `ScreeningBackend` protocol (a second method or a payload-typed
   call — codex proposes, lead reviews the seam shape at drop
   review). — **codex**
6. `classify.py` rework: optional `classification_backend` param, stub
   default (rev 2); backend call, no-row-on-failure, provider
   priors assembly, tag writes via helper, **`confidence` + `reason`
   written into the `source.classified` payload (rev 2 — payload-only,
   never columns)**, `skipped` effective-status fix. — **codex**
7. Effective-**stage-and-status** sweep (widened rev 3) per the reader
   table: every reader resolves highest-stage non-failed;
   `_base_counts` fix + verify/fix the "verify" readers + regression
   tests per reader. — **fast-worker** *(enumerated sweep; ambiguous
   discoveries escalate to lead)*

**Phase 5 — wiring**
8. `harness.py` + `skeleton.py` (rev 4, consolidated wiring owner):
   two backend params (stub defaults), stage-directive threading
   through the screen node, skeleton deep profile = second `screen`
   run with the stage-2 directive + rapid profile provably skipping
   it, `ScreenedSource.screen_stage` threading into select,
   `live = bool(OPENAI_API_KEY)` extension, score summaries.
   — **fast-worker** *(exact pattern; the judgment calls are already
   pinned above)*

**Phase 6 — tests (full `make verify` gate)**
9. Bulk suites from the contract's Acceptance enumeration (aggregation
   matrix, failure/retry/idempotency, tag bounds, migration
   roundtrip). — **fast-worker**
10. Judgment suites: test-only `ScriptedScreeningBackend` /
    `ScriptedClassificationBackend` (rev 2 — per-doc scripted rep
    sequences; production stubs stay sentinel-pure), paired
    clean/adversarial injection fixtures (semantic invariance),
    quorum + title-only unanimity + tie cases, Unknown-vs-Other
    boundary fixtures, event-payload shape assertions (per-rep
    records · agreement count · `aggregation_flags` · **`screen_stage`
    on every screened event (rev 4)** · classify
    confidence/reason present, no columns), select stage-tests
    (effective-row confidence in composite/thin_base with
    `screen_stage` in rationale; demotion removes from candidate
    set), no-rescue invariant test, wire-model
    validation/NUL/oversize-field cases. — **codex**

**Phase 7 — records + live check**
11. `deferred.md` (discharged entries rewritten + the rev-1.2/1.3/1.5
    /1.6 seams) + knowledge concepts + `verification.md` + the live
    manual check (operator-run: e2e over fixtures, agreement
    distribution, borderline review, classify face-validity ~10,
    paired injection probe, non-English record, tag samples, Langfuse
    API verification, cost, key audit). — **lead** *(live-run
    adjudication + records; per-slice precedent)*

## Review-stack sizing (for conversation C)

Per [[review-stack-economy]]: /code-review medium with per-angle diff
scoping (exclude any fixture data), one security lane (headline: first
third-party text into product prompts — injection posture),
contract-verifier Opus, Codex adversarial, live-trace CONTENT review
lane (013 process install). ≤ 250K reasoning / ≤ 500K fast-worker.

## Live-check script (task 11 detail)

Fixture corpus e2e (skeleton, live backends): screen spread sanity ·
agreement distribution (unanimous / 2-of-3 / tie) · borderline review
— band pinned (rev 2): non-failed docs sorted by persisted
confidence, take `max(1, ceil(0.10 * n))` including ties at the
cutoff, union all non-unanimous docs; reasons coherent · **stage-2
leg (rev 3)**: deep-profile run exercises `screen_fulltext`; stage
distribution reported; **demotion review** — every demoted doc's
`reason` read (false exclusion = the dangerous outcome); rapid
profile shown skipping stage 2 ·
classification by_type distribution not-all-Unknown + face-validity 10
· Unknown-vs-Other spot check · paired injection probe (2 pairs) ·
non-English record · tags within bounds · Langfuse traces + scores via
public API · cost recorded · `rg -i "sk-|api_key"` audit. Dev DB needs
`alembic upgrade head` first (012 lesson).
