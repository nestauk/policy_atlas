# Implementation Plan: 011-extract

> **Status:** **confirmed — 2026-07-07 · Shabeer Rauf** (rev 2, after the
> plan-stage adversarial review was adjudicated: Codex, 10 findings —
> 2 blockers · 8 majors, 10/10 adopted; § Findings & adjudication).
> ADR 0007 written and Accepted at this gate (Task 9b).
> Contract: [contract.md](contract.md) (approved 2026-07-07 · Shabeer Rauf,
> rev 1.4; contract-stage adversarial findings adjudicated at rev 1.5).

## Overview

One component and the repo's first findings-layer write, on `task/011-extract`:
1. **Schema** — `source_extraction_record` · `intervention_outcome_finding` ·
   `extraction_result` (migration 11; tables 20 → 23).
2. **Record models + prompt + quote verifier** — the pydantic IOF record set
   (single source of truth for API schema and prompt), the lead-authored
   `extract_iof_v1` prompt with pre-flight example validation, and the
   deterministic quote-verification module (normalise, ordered cursor, graded
   status, raw-offset recording).
3. **Extraction layer** — `ExtractionBackend` seam (live OpenAI structured
   outputs + sentinel stub), Langfuse tracing inside the live backend.
4. **`extract.py`** — selection-row load (explicit `selection_run_id`) → basis
   assembly (chunks or envelope abstract) → memo check → windowed per-source
   fan-out → verify/validate/dedup → durable finding + record writes → run
   roll-up written last → extraction summary.
5. **Wiring + tests + the approved data-model flow-back** (stratum qualifiers ·
   comparator · estimate level · τ²).

Same size class as 010 (three tables instead of one, but one prompt, one
backend seam, no new dependency, no new event types). The stub is the suite
path; the live path is the skeleton with `OPENAI_API_KEY`.

## Executor routing (plan-time decision, per harness.md ladder)

| Task | Executor | Why |
|---|---|---|
| 1 (schema + migration 11) | `lead` | gated surface; partial unique index + composite-FK targets verified against as-built uniques (the adjudicator owns migration subtleties) |
| 2 (IOF pydantic record set + `extract_iof_v1` prompt + few-shot example) | `lead` | prompt-bearing — lead-only per AGENTS.md; the record model is the schema's single source of truth, i.e. seam design |
| 3 (`quote_verify.py`: normalisation, cursor, status, offsets; field rules; dedup canonicaliser) | `codex` | subtle deterministic logic with exact pass conditions per contract decision 4; done = the verification/validation/dedup test blocks |
| 4 (`extraction_backend.py`: protocol + OpenAI + stub + tracing) | `codex` | implementation of a lead-designed seam against schema-constrained I/O (the `RankingBackend` pattern); done = backend construction/stub/no-op tests |
| 5 (`extract.py`: selection load → basis → memo → fan-out → verify → writes → roll-up → summary) | `codex` | judgment-bearing execution with a fully pinned spec (contract decisions 1–9); done = the memo/coverage/status test blocks |
| 6 (registry/harness/skeleton/helpers wiring) | `fast-worker` | mechanical from the 004–010 precedent + the exact spec below |
| 7 (test suite: contract bulk) | `fast-worker` | transcription of the contract's named-test list |
| 8 (test suite: judgment cases — injection double, memo/retry semantics, cursor/dedup edge fixtures, windowing double, socket-deny) | `codex` | subtle-but-specified; each has an exact pass condition |
| 9 (data-model flow-back + log.md + deferred.md entries) | `lead` | living-spec text, user-approved wording |
| 9b (ADR 0007) | `lead` | design record, written at plan confirmation before the build |
| 10 (verification.md + live manual run) | `lead` | needs operator keys, cost judgment, trace inspection |

Lead marks carry their justification inline; the burden sits on keeping work,
not delegating it. Codex briefs are one-concern, self-checkable; anything
failing the brief test at build time is a plan deviation to flag.

## Plan-pinned details (the contract's named "plan gate" items)

- **Model**: `EXTRACTION_MODEL = "gpt-5-mini"` (the contracted floor; the 009
  nano lesson binding). The live run evaluates yield qualitatively and records
  an honest cost note; a step-up is a recorded option, not a silent switch.
- **Windowing**: `WINDOW_CHAR_BUDGET = 150_000` chars of segment content per
  call (~37K tokens — nearly every fixture document is a single call; the
  10 real full-text docs range well under this); windows are ordered chunk runs
  with **overlap = 1 chunk** (the previous window's last chunk repeats).
  **Oversize-segment policy** (adversarial finding 8 — 008 recorded PDFs
  collapsing to 2–3 giant chunks): a single chunk exceeding the window budget
  is **deterministically char-split into subsegments** carrying the original
  `chunk_id` plus a part index (`{chunk_id}#p{i}`) and local offsets — the
  full-read guarantee holds (never `extraction_failed` merely for parser
  chunking); quote verification is unaffected (it runs against chunk content
  + the offset map, not window payload ids); fixture required. Overlap
  between subsegments of one giant chunk = `1_000` chars;
  `EXTRACT_MAX_OUTPUT_TOKENS = 8192` (explicit — V2's uncapped calls truncated
  mid-JSON); `EXTRACT_RETRY_CAP = 1` per window; `MAX_CONCURRENT_EXTRACT = 4`
  (global executor across docs and windows; **writes in selected-set order in
  the parent**, the ingest determinism pattern). Call budget: baseline
  `Σ_docs ceil(windows)`, enforced max `baseline × (1 + retry_cap)`, checked
  before any live call.
- **Fingerprint**: **full** `sha256` hex over the canonical JSON of
  `{profile: "eb_iof_base_v1", schema: "iof_v1" (covers wire AND stored
  models), prompt: "extract_iof_v1", model, mode, field_rules: "iof_rules_v1",
  verifier: "qv_v1", window: {char_budget, overlap, oversize_policy},
  max_output_tokens, retry_cap}` (adversarial finding 3: every
  output-affecting knob, no truncation — the column is TEXT); the full
  component map recorded in `extraction_provenance`, and a test asserts each
  component version appears there. Any output-affecting change bumps a
  component version and thus the digest.
- **Quote verifier (`qv_v1`)**: normalisation = casefold · collapse whitespace
  runs to one space · fold `""''` → straight quotes · `–—` → `-` · NBSP →
  space · strip soft hyphens. Matching runs on a normalised copy carrying an
  **index map back to raw offsets**; recorded intervals are always raw
  (half-open `[start, end)`, asserted). **Ordered cursor per (document, quote
  string)**: the n-th use of an identical quote matches the n-th occurrence.
  Match status per anchor: `exact` (raw substring) | `normalised` | `failed`.
  Basis text: concatenated chunk contents (with a chunk-boundary offset table
  mapping doc-offsets → (chunk_id, chunk-local interval)) or the envelope
  abstract (chunk_id null). The normalised copy + offset map are built **once
  per document** and reused across all quotes.
- **Field rules (`iof_rules_v1`)**: `p_value ∈ [0,1]` · `ci_lower ≤ ci_upper` ·
  `n ≥ 1` integer · `k ≥ 1` integer · `i_squared ∈ [0,100]` · `tau2 ≥ 0` ·
  effect size finite · estimate-level coherence (pooled ⇢ k expected, study ⇢ N
  expected — the *incoherent* field flags `unclear`) · null-like strings
  (`{"null","none","n/a","na","unknown",""}`, case-insensitive) in nullable
  text/numeric fields → real null + coverage marker; **closed enums exempt**.
  Violations flag the field `unclear`, never reject the finding.
  **`not_applicable` rules** (adversarial finding 4): `estimate_level=study` →
  absent {k, i_squared, tau2} mark `not_applicable`;
  `estimate_level=claim` → all absent numeric statistics mark
  `not_applicable`; every other absent nullable field marks `not_extracted`
  (present-but-incoherent stays `unclear` per the coherence rule). Fixtures
  for all three estimate levels required.
- **Stratum canonicalisation**: closed type vocabulary `timepoint` |
  `subgroup` | `setting`; values stored as emitted (whitespace-normalised);
  canonical comparison form = sorted `(type, casefold(value))` pairs — used by
  dedup and recorded alongside.
- **Dedup key** (claim dimensions, per contract rev 1.5): casefolded,
  whitespace-normalised tuple of (intervention, outcome, effect_direction,
  effect_size, effect_size_type, comparator, estimate_level, canonical
  stratum). Identical → one finding, anchors concatenated in emission order,
  collapse counted per doc in the roll-up.
- **Record model set — wire vs stored split** (Task 2; `extra="forbid"`
  everywhere; adversarial finding 1, blocker): strict structured outputs
  enforce the wire schema at the API, which would make the contract's
  null-coercion and invalid-candidate rules **unreachable** if the wire model
  were the final shape. So two model layers, one truth chain:
  - **Wire** (`IOFRecordWire` etc., drives `response_format`): grain fields
    (`intervention`, `outcome`) **nullable**, numeric statistics as
    `float | str | None` unions (so "null"-strings and unparseable values
    arrive and are *coerced/flagged by our rules*, not silently rejected or
    model-conformed), enums closed at the wire (exempt from coercion by
    construction), anchors as emitted.
  - **Stored** (`IOFRecord` etc.): the final typed shape after grain
    validation + `iof_rules_v1` — NOT NULLs enforced, numerics real.
  `IOFStatistics` (effect_size, effect_size_type, ci_lower, ci_upper,
  standard_error, p_value, n, k, i_squared, tau2), `IOFAnchor` (segment_id
  nullable, quote), `IOFRecord` (intervention, outcome, population,
  comparator, effect_direction, estimate_level, study_design,
  stratum_qualifiers, statistics, causality_by_design, is_primary,
  is_prevalence_only, anchors ≥ 1), `ExtractionResponse` (findings list —
  possibly empty, explicitly legal). The prompt's field documentation is
  generated from the wire models; the schema fingerprint component covers
  both layers.
- **`causality_by_design` closed set**: `attributable` | `plausibly_causal` |
  `associational` | `descriptive` (derived from the reported design; the
  prompt maps design families to values; `unclear` handled by field coverage,
  not an enum value).
- **Prompt shape** (`extract_iof_v1`, lead-authored): system = role + task +
  the negative rules (no question-relative judgements · no cross-source claims
  · nothing the document doesn't report · never force effect fields ·
  verbatim quotes only, no paraphrase) + evidence-type-conditioned guidance
  (SR ⇢ pooled estimates per outcome × stratum with k/I²/τ²; primary study ⇢
  study-level with N; policy/qualitative ⇢ empty list is the expected honest
  answer) + the prevalence-only skip/extract examples (V2's, reworded) +
  outcome-⊥-stratum rule; user = envelope block (title + abstract) +
  `primary_evidence_type` + id-keyed segment records under the standing
  data/instructions separation. **One few-shot example** (compact, in-schema,
  its quotes verbatim in its own example text — pre-flight validated by the
  Task-3 verifier at import; a failing example is a loud startup error, never
  a warning).
- **Stub backend**: sentinel-driven per the repo convention — pss metadata
  `_stub_iof: [record-dicts]` returned as parsed records; `_stub_extract_failed`
  → raised backend error (exercises `extraction_failed`); no sentinel → empty
  findings (`no_findings` path). Fixture records' quotes must genuinely occur
  in their seeded chunk text so the verification path runs for real. Stub mode
  string `"stub"` enters the fingerprint.
- **Document loader** (adversarial finding 6 — `selection_result.selected`
  records carry `pss_id` + `text_basis` but **not** `primary_evidence_type`):
  extract's loader query joins selected `pss_id`s → `project_source_snapshot`
  → envelope snapshot metadata (title/abstract) + `full_text_snapshot_id` →
  `chunk`s, **and** `source_classification_result` for
  `primary_evidence_type` (the `screened_sources` join precedent,
  characterise.py:188–220). Null/unclassified → the prompt receives
  `"Unclassified"` and the generic guidance branch (no SR/study conditioning);
  prompt-payload test asserts the joined value lands in the built prompt.
  **Basis rules** (adversarial findings 9–10): basis full_text ⇢ chunks of
  `full_text_snapshot_id`; abstract_only ⇢ envelope abstract; the selected
  record's `text_basis` vs current pss state mismatch → **structural
  per-doc failure, loud** (`extraction_failed(basis_mismatch)`); an empty
  basis (no abstract text, or an ingested snapshot with zero chunks) →
  **`extraction_failed(empty_basis)`, never `no_findings`** (a false absence
  otherwise — screen explicitly admits title-only documents).
- **Memo semantics**: lookup `(project_id, source_snapshot_id, fingerprint)`
  with `status IN ('extracted','no_findings')` (matching the partial unique
  index); hit → no call, no new rows, roll-up `docs[]` entry carries
  `reused: true` + the existing `extraction_record_id`. Failed rows insert
  freely (attempt history) and never match.
- **Roll-up row**: written **once, at success, as the last statement** after
  all fallible work (the 010 finding-2 pattern; `_run_scope_component`
  catches without rollback). Empty selection (`selected == []`) →
  `empty_selection` flag and a roll-up row recording the zero-doc run
  (contract decision 8 — unlike select's no-row rule, group needs this row as
  its reference). `UNIQUE (evidence_scope_id, run_id)` makes same-run re-runs
  loud.
- **Extraction summary shape** (frozen in Task 5, asserted by the payload
  test; adversarial finding 2 — per-doc statuses, not just aggregates):
  `{docs: [{pss_id, status, basis, finding_count, reused, error,
  extraction_record_id}], counts: {selected, extracted, no_findings, failed,
  fresh, reused}, findings: {total, quote_unverified, dedup_collapsed,
  invalid_dropped}, basis: {full_text, abstract_only, shares},
  field_coverage: {per-field marker counts}, selection_run_id, flags: [...],
  provenance: {fingerprint, components…}}` — the per-doc list makes the
  exact-coverage invariant checkable at the payload boundary.
- **Langfuse**: generation spans open **inside `OpenAIExtractionBackend`**
  (usage lives there — the 010 finding-8 precedent), named
  `extract:{pss_short}:w{j}`; metadata = doc/window ids, model, prompt
  version, token counts, parse outcome. Run-level scores via the 009
  `score_summary` pattern: `quote_verified_share`, `no_findings_share`,
  `extraction_failure_count`, `dedup_collapsed_count`. Full I/O per the
  settled posture (full text in traces — approved at the contract gate). No-op
  without keys; the stub is never traced.
- **Skeleton chain**: … select → **extract**, its own run;
  `selection_run_id` = the select step's returned run id (the
  `characterisation_run_id` thread-through precedent, skeleton.py:443–488);
  live backend iff `OPENAI_API_KEY`; logs the call budget before live calls;
  renders the extraction summary. The demo directive's budget 8 (010) keeps
  the live extract run at ~8 docs — and to **guarantee** the mixed-basis
  live check (adversarial finding 7: budget + tag boost alone can't), the
  skeleton pins `must_include_ids` to one known full-text and one known
  abstract-only fixture doc (resolved by backend record id at seed time),
  then asserts both bases occur in the selected set before the live extract
  step.
- **`ExtractContext`** carries `(scope_id, intent, context, selection_run_id)`
  for wiring uniformity — **`intent` is not consumed by extraction** (contract
  rev 1.5; a code comment states this so no reviewer re-flags it).
- **Delete order** (`tests/helpers.py`): `intervention_outcome_finding` →
  `source_extraction_record` → `extraction_result`, inserted before the
  existing 009/010 rows in `delete_project_data`.

## Architecture decisions (all fixed in the approved contract)

- Findings durable + memoised; run roll-up run-scoped; per-doc records carry
  the memo key (partial unique over success states). Coverage invariants:
  statuses cover exactly the selected set;
  `selected == extracted + no_findings + extraction_failed`; fresh/reused
  orthogonal; every finding → exactly one record → a selected doc.
- Full-read extraction; windows independent/parallel; per-window retry once
  then doc `extraction_failed` (reason-coded, retryable in a new run); no
  partial per-doc finding sets; extraction failure never fails the component.
- Anchors verified deterministically (no LLM repair); `quote_unverified`
  flag-not-drop; abstract-basis anchors use envelope-abstract intervals.
- Doc-status rules: valid-empty → `no_findings`; all-grain-invalid →
  `extraction_failed(invalid_records)`; mixed → `extracted` +
  dropped-and-counted invalids.
- Egress: env-only keys; stub default; skeleton live on configured key;
  pre-call budget; socket-deny on the suite path; **no intent in the prompt**.

## Dependency graph

```
Task 1 (schema + migration 11)
   ├─→ Task 2 (record models + prompt, lead)
   │        ├─→ Task 3 (quote_verify.py + rules + dedup)
   │        └─→ Task 4 (extraction_backend.py)
   │                 └─→ Task 5 (extract.py)  ←─ Task 3
   └──────────────────────┴─→ Task 6 (wiring) ─→ Tasks 7+8 (tests)
        Task 9 (flow-back/deferred) · Task 9b (ADR 0007, at plan 🛑) · Task 10 (verification)
```

---

## Phase 1 — Schema (separable commit)

### Task 1: three tables + migration 11 — `lead`

**Files:** `src/policy_atlas/schema.py`, `alembic/versions/<hash>_extract.py`.

- Tables exactly per the contract's Schema block: `source_extraction_record`
  (partial unique index `(project_id, source_snapshot_id,
  extraction_fingerprint) WHERE status IN ('extracted','no_findings')`;
  composite FKs `(run_id, project_id)`, `(project_source_snapshot_id,
  project_id)`; **plus `UniqueConstraint("extraction_record_id",
  "project_id", name="uq_ser_id_project")` — the composite-FK target for the
  finding table, per the repo's parent pattern (adversarial finding 5:
  `uq_runs_run_project`/`uq_pss_id_project`/`uq_evidence_scope_id_project`
  precedents)**; CHECKs on status/basis), `intervention_outcome_finding`
  (NOT NULLs per DDL; CHECKs on effect_direction/estimate_level; composite FK
  `(extraction_record_id, project_id)`), `extraction_result` (composite FKs,
  `UNIQUE (evidence_scope_id, run_id)`, NOT NULL JSONBs). FK targets verified
  against as-built composite uniques (verify, don't assume).
- Module docstring: "twenty-three tables, eleven alembic migrations".
- No dependency changes (assert, don't add).

**Acceptance:** migration roundtrips 20→23→20→23; `make verify` green (nothing
reads the tables yet). **Commit.** Scope: M.

## Phase 2 — Record models, prompt, verifier, backend

### Task 2: IOF record set + `extract_iof_v1` — `lead` (prompt-bearing)

The pydantic models (pinned set above) and the prompt (pinned shape above),
committed as constants with the version strings; prompt field docs generated
from the models. Includes the one few-shot example.

### Task 3: `quote_verify.py` — `codex`

Normalised matcher with raw-offset index map, ordered cursor, graded status,
chunk-boundary mapping; `iof_rules_v1` field validation; null-like coercion;
stratum canonicaliser; claim-key dedup. Pure functions, no I/O. Done = the
verification/validation/dedup unit-test blocks (boundary-spanning quote,
repeated quote, smart-quote fold, offset fidelity vs raw text, rule
violations, enum exemption, dedup merge vs distinct-effect split). Scope: M.

### Task 4: `extraction_backend.py` — `codex`

`ExtractionBackend` protocol (`extract(window_payload) -> ExtractionResponse`,
`mode`) · `OpenAIExtractionBackend` (strict structured outputs from the Task-2
models, per-call timeout, explicit max output tokens, internal Langfuse spans
per the pinned spec) · sentinel stub per the pinned spec. Done = construction/
failure/stub-determinism/no-keys-no-op tests. Scope: S–M.
**Commit** after Phase 2 verify green.

## Phase 3 — The component

### Task 5: `extract.py` — `codex`

Selection-row load by `(scope, selection_run_id)` (missing → structured
failure) → per-doc loading via the pinned **document loader** (classification
join; basis rules; `basis_mismatch`/`empty_basis` per-doc failures) → memo
lookup → window assembly (char budget, 1-chunk overlap) → budget check →
fan-out (bounded executor; parent-ordered writes) → parse → within-doc
pipeline: grain validation (invalid-candidate rules) → field rules → dedup →
quote verification → finding + record writes → roll-up row **last** →
summary in `component.completed`. Empty selection branch per the pinned spec.
Done = memo/coverage/status/invariant test blocks. Scope: L (~450 lines).
**Commit** after Phase 3 verify green.

## Phase 4 — Wiring

### Task 6: Registry/harness/skeleton/helpers — `fast-worker`

- `plan.py`: `"extract": {"requires": ["evidence_scope_id",
  "selection_run_id"]}`; `Plan`/`_ValidatedRunSpec`/`Config` gain optional
  `selection_run_id` (required-by-registry for extract; compile fails closed —
  the 010 `characterisation_run_id` clone).
- `harness.py`: `extraction_backend: ExtractionBackend | None = None` on
  `run_harness` (stub resolved inside), threaded through `HarnessState`;
  `_run_extract` via `_run_scope_component` with
  `functools.partial(ExtractContext, selection_run_id=…)`; node + conditional
  edge + edge to finish.
- `skeleton.py`: extract step after select per the pinned spec; live/stub
  switch; summary rendering.
- `tests/helpers.py`: delete order per the pinned spec; `test_compile.py`:
  registry case. Scope: S–M. **Commit** with Phase 4.

## Phase 5 — Tests

### Task 7: Contract bulk — `fast-worker` (the contract's named-test list is the brief)

Migration roundtrip + 23 tables + constraint/CHECK/partial-unique rejections ·
memo semantics (hit/reuse/no-call; stub-vs-live fingerprints; `no_findings`
memoised; **failed never blocks retry**) · coverage invariants · quote
verification (verbatim, boundary-spanning, fabricated → flagged) ·
abstract-basis end-to-end · match-location fidelity · field rules (each rule +
coercion + enum exemption) · claim-keyed dedup + distinct-effect split ·
doc-status rules · windowing (multi-window fixture; budget arithmetic;
window-failure → doc failed, others proceed; **oversize-chunk subsegment
fixture** — finding 8) · basis rules (full-text ⇢ full_text_snapshot chunks;
abstract ⇢ envelope; **basis-mismatch loud** · **empty basis →
`extraction_failed(empty_basis)`, never `no_findings`** — findings 9–10;
title-only and zero-chunk fixtures) · `not_applicable` markers per estimate
level (finding 4 fixtures) · schema line (enrichment absent;
negative rules asserted on the built prompt) · field coverage markers · edge
scopes (empty selection row + flag; missing selection row; same-run loud) ·
determinism (two stub runs byte-identical payload columns; parallel-vs-serial
write order) · delete-order integrity · summary payload shape.

### Task 8: Judgment cases — `codex`

Injection double (a prompt-injection-shaped chunk lands as inert data — no
instruction-following, asserted on output) · prompt-structure assertion
(id-keyed records; envelope/evidence-type under data — including the
classification-join value; **no intent anywhere in the built prompt**) ·
counting double asserting exactly the selected fresh
docs are sent (reused/memo docs never) · misbehaving backend doubles
(duplicate findings → dedup; grain-invalid wire records → status rules —
reachable through the tolerant wire model, finding 1; null-string numerics
coerced; oversized output) · fingerprint completeness (every pinned component
version present in provenance; two configs differing in any one component →
distinct fingerprints) · repeated-quote cursor fixture (same sentence quoted twice →
successive occurrences) · pre-flight example validation (a doctored
non-verbatim example fails at import) · socket-deny around an extract
round-trip · key hygiene against captured output. Scope: M–L. **Commit**
(tests).

## Phase 6 — Flow-back + verification

### Task 9: Data-model flow-back + log.md + deferred.md — `lead`

- data-model findings-layer base-field list: stratum qualifiers · comparator ·
  estimate level · τ² (the approved candidate flow-back); `log.md` entry.
- `docs/deferred.md`: the contract's full seam list (extraction service +
  dataset snapshots · hybrid-indexing pointer · multi-pass recall ·
  reason-then-constrain · retrieval-augmented extraction · retrieval-scoped
  declined · generic container declined · LangExtract declined ·
  per-intervention decomposition · fuzzy fallback · CFIR → second schema ·
  mixed/unclear first-class requirement on group · failed-extraction recovery
  loop · parse-quality escalation pointer · extraction-quality evals, noting
  it unblocks 010's rerank-quality seam). `make okf-validate` green.

### Task 9b: ADR 0007 — `lead` — **at plan confirmation, NOT a build task**

`docs/adr/0007-findings-layer-extraction.md`: durable findings vs run-local
results (the two-lifetime split) · the memo fingerprint over output-affecting
versions + partial-unique success-state semantics · deterministic quote
anchoring (normalise/cursor/status/raw offsets; no LLM repair) ·
question-agnostic extraction (no intent; the V2 lesson) · the three-table
shape and why not a generic container · full-read over retrieval-scoped.
**Written and Accepted at the plan 🛑, before the build conversation opens.**

### Task 10: `verification.md` + live manual run — `lead`

Per the contract's evidence list: `make verify` table; migration roundtrip +
23 tables; the named test results; live skeleton run (`OPENAI_API_KEY` +
`LANGFUSE_*` dev): findings written with verified quotes across both bases,
memo second-run demonstration (zero fresh calls), extraction summary,
grounding scores in the dev trace, honest cost note; public-safety
confirmation (fixture full text only; no intent egress; keys clean).
**Commit** (flow-back + verification).

### Review stack (rubric box 8 — owned by conversation C, not this plan)

Per the task-cycle spine: fresh conversation, Tier-3 lanes sized per the
review-economy notes (≈6K-line diff expected → ~5 finder angles or src-subset
scoping, per the 010 retro).

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Extraction quality on real full text at mini-class | Thin/wrong findings | The live run's grounding scores + cost note make it visible; model step-up is a recorded option; quality bar for this slice is machinery correctness (contract) |
| Long-doc windows split a finding's evidence | Missed/partial findings | 1-chunk overlap; most docs single-call; multi-pass + retrieval-augmented seams recorded with triggers |
| Quote verification false-negatives on parser artifacts (hyphenation, ligatures) | Inflated `quote_unverified` | qv_v1 folds the known classes; graded status separates exact/normalised; live-run share monitored via the Langfuse score |
| Model emits near-duplicate (not exact-dup) findings | Inflated counts | Exact claim-key dedup catches the deterministic class; near-dup is the eval seam (recorded); `dedup_collapsed`/finding counts visible per doc |
| Memo reuse across scopes surprises a future reader | Confusion over provenance | Reuse is the *point* (findings layer); records carry creating run + fingerprint; roll-up marks reused explicitly |
| Fingerprint components drift from actual behaviour | Stale reuse | Fingerprint digest built from the same constants the code executes; test asserts each component version appears in provenance |
| Partial unique index unsupported by naive ORM patterns | Migration/test friction | Alembic `op.create_index(..., postgresql_where=...)`; lookup queries filter status explicitly; roundtrip test covers it |
| Concurrent windows + DB writes nondeterminism | Flaky suite | All writes in the parent, selected-set order (ingest pattern); parallel-vs-serial determinism test |
| Cost runaway on live run | Spend | Pre-call enforced budget; demo selection ≈ 8 docs; cost note required in verification.md |
| Injection via full document text | Hijacked extraction output | Schema-constrained output, no tools; negative rules; injection-double test; a hijacked model can at worst emit wrong findings for its own document — flagged-or-verified data |

## Plan-phase adversarial review — findings & adjudication (Codex, 2026-07-07)

Ten findings, verified against the repo before adoption; **10/10 adopted**:

1. Strict structured outputs make the contract's coercion/invalid-candidate
   rules unreachable (blocker): **adopted** — wire vs stored model split;
   grain fields nullable and numerics string-tolerant on the wire, final shape
   enforced post-rules (Task 2 pin).
2. Summary `docs` was aggregate-only vs the contract's per-doc statuses:
   **adopted** — per-doc list + `counts` object (payload-boundary invariant).
3. Fingerprint omitted max-output-tokens/retry/oversize policy and truncated
   the digest: **adopted** — full sha256 hex, all output-affecting knobs in
   the canonical map, completeness test.
4. `not_applicable` rules unpinned/untested: **adopted** — per-estimate-level
   rules + fixtures.
5. Composite-FK target missing its composite unique on
   `source_extraction_record` (blocker): **adopted** — `uq_ser_id_project`
   per the repo's parent pattern.
6. `primary_evidence_type` not on selection records; loader join unpinned:
   **adopted** — document-loader pin (classification join, `"Unclassified"`
   null policy, prompt-payload test).
7. Budget-8 directive can't guarantee the mixed-basis live check: **adopted**
   — demo `must_include_ids` pin one full-text + one abstract-only fixture
   doc; skeleton asserts both bases pre-extract.
8. Oversize single chunk (the 008 giant-chunk PDFs) undefined vs the window
   budget: **adopted** — deterministic subsegment split (`{chunk_id}#p{i}`,
   1K-char overlap), full-read guarantee preserved, fixture required.
9. Snapshot-consistency rule untested: **adopted** — basis-rule tests incl.
   `basis_mismatch` loud failure.
10. Empty basis (no abstract / zero chunks) could read as `no_findings`
    (false absence): **adopted** — `extraction_failed(empty_basis)`, never
    `no_findings`; title-only and zero-chunk fixtures.

## Open questions

None blocking — all design decisions are fixed in the approved contract
(rev 1.5). The plan-stage adversarial review runs before the 🛑.
