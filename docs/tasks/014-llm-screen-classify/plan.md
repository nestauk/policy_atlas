# Plan: 014-llm-screen-classify

> **Status:** drafted (rev 1), awaiting plan-stage adversarial review →
> plan 🛑. Contract: [contract.md](contract.md) **approved rev 1.5.1,
> adjudicated rev 1.6 (Codex 10/10), ⚑ remedies user-confirmed
> 2026-07-08**. ADR due at plan confirmation (step 4): injection
> posture + consensus screening are capability-class decisions.

Executor routing per harness.md § Agent-side model routing: default =
delegate; every `lead` mark carries a justification.

## Plan-pinned constants

- `SCREEN_REPS = 3` · quorum ≥ 2 surviving reps · unsure → vote
  relevant / probability 0.5 · title-only exclusion requires unanimity
- Screen model `gpt-5-mini`; classify model **plan pin:
  `gpt-5.5`** (assessed vs `gpt-5.6-terra` at this gate — pin the id
  actually available via the API at build start; record in
  verification.md; the mini swap-down stays eval-gated)
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
- PROMPT_VERSIONs: `screen_v1` · `classify_v1` (8th/9th product
  prompts, lead-authored)
- Migration 14: `ck_stag_tag_type` widen to
  (`topic_theme`,`methodological_structural`) + `uq_ssr_scope_source`
  → partial unique index `WHERE status <> 'failed'`; table count
  stays 25; roundtrip BOTH DBs (011 lesson 13f909c)

## Reader enumeration (contract decision 5, rev 1.6 M7)

Verified by grep over `source_screening_result` consumers:

| Reader | Class | Action |
|---|---|---|
| `screen.py` NOT-EXISTS guard (l.70) | eligibility | becomes "no **non-failed** row exists" (task 5) |
| `classify.py` relevant join (l.77-103) + `total_relevant` (l.116) | relevant-only — safe | regression test only |
| `classify.py` `skipped` count (l.109) | raw rows — UNSAFE | effective-status distinct-source fix (task 6) |
| `characterise.py` `_base_counts` (l.162-179) | raw rows — UNSAFE (negative `unscreened`) | effective-status fix (task 7) |
| `characterise.py` relevant join (l.217+) | relevant-only — safe | regression test only |
| `appraise.py`, `ingest_full_text.py`, `synthesis_tools.py`, `synthesise.py`, `skeleton.py` | verify relevant-only in task 7 | test each; fix any raw-count found |

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
5. `screen.py` consensus rework: backend injection, 3 concurrent reps,
   vote (unsure→relevant, quorum ≥2, title-only unanimity, 1-1
   tie→relevant flagged), consensus-probability confidence, per-rep
   event payload + agreement counts, non-failed NOT-EXISTS, summary
   counts (unsure · non-unanimous · rep_failures · tie_broken).
   — **codex**
6. `classify.py` rework: backend call, no-row-on-failure, provider
   priors assembly, tag writes via helper, `skipped` effective-status
   fix. — **codex**
7. Effective-status sweep per the reader table: `_base_counts` fix +
   verify/fix the five "verify" readers + regression tests per reader.
   — **fast-worker** *(enumerated sweep from the table above)*

**Phase 5 — wiring**
8. `harness.py` + `skeleton.py`: two backend params (stub defaults),
   skeleton `live = bool(OPENAI_API_KEY)` extension, score summaries.
   — **fast-worker** *(exact pattern from seven precedents)*

**Phase 6 — tests (full `make verify` gate)**
9. Bulk suites from the contract's Acceptance enumeration (aggregation
   matrix, failure/retry/idempotency, tag bounds, migration
   roundtrip). — **fast-worker**
10. Judgment suites: paired clean/adversarial injection fixtures
    (semantic invariance), quorum + title-only unanimity cases,
    Unknown-vs-Other boundary fixtures, wire-model
    validation/NUL/oversize-field cases (scripted stub backends).
    — **codex**

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
(lowest-confidence decile + all non-unanimous, reasons coherent) ·
classification by_type distribution not-all-Unknown + face-validity 10
· Unknown-vs-Other spot check · paired injection probe (2 pairs) ·
non-English record · tags within bounds · Langfuse traces + scores via
public API · cost recorded · `rg -i "sk-|api_key"` audit. Dev DB needs
`alembic upgrade head` first (012 lesson).
