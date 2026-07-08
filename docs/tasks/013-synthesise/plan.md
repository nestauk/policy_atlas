# Implementation Plan: 013-synthesise

> **Status:** drafted (rev 1) — plan-stage adversarial review next, then
> the plan 🛑.
> Contract: [contract.md](contract.md) (approved rev 8, 2026-07-08 ·
> Shabeer Rauf; contract-stage adversarial findings 9/9 adjudicated; the
> two ⚑ lead-adapted remedies — B2 row-per-spanned-chunk citations, M4
> appraised-docs chunk gating — user-confirmed 2026-07-08).
> ADRs: [0009](../../adr/0009-capability-composes-synthesise-terminus.md) +
> [0010](../../adr/0010-intent-led-synthesis-sections.md) — Accepted,
> consolidated; **no step-4 ADR is due** (the architecture record is
> complete; a build-time design change would reopen that call).

## Overview

The terminus component, the trust invariant's landing slice, on
`task/013-synthesise`:

1. **Schema** — `synthesis_result` (migration 13; tables 24 → 25).
2. **Tools + loop layer** — `search_chunks` (staged retrieval:
   content-only hybrid → soft priors → pass-through reranker → caps),
   `query_findings`, `lookup`, and the bounded tool-calling **loop
   runner** (the repo's first agent loop; scripted-stub drivable).
3. **Backends + prompts** — `SynthesisBackend`
   (`synthesise_sections_v1` + `synthesise_section_v1` incl. tool
   schemas) and `GroundingJudgeBackend` (`grounding_judge_v1`), all
   lead-authored; the traced-call helper factored into `tracing.py`
   (the 012-deferred trigger).
4. **`synthesise.py`** — reference/substrate resolution → artefact mint
   → section proposal → per-section loop → per-type claim validation →
   judge → bounded repair → block/unit/annotation/citation writes →
   roll-up row last → summary in `component.completed`.
5. **Wiring + test suites + deferred.md/knowledge records +
   verification with a four-profile live check.**

Bigger than 011 (four prompt-adjacent surfaces counting tool schemas,
the first loop runner, six claim validators) but with more reusable
machinery than any prior slice: `QuoteMatcher`/`build_basis` (011),
`EmbeddingBackend` + stub vectors (009), the backend pattern
(009–012), the directive-parsing pattern (010/012), the 001 substrate.
The stub path is the suite; the live path is the skeleton with
`OPENAI_API_KEY`.

## Executor routing (plan-time decision, per harness.md ladder)

| Task | Executor | Why |
|---|---|---|
| 1 (schema + migration 13 + helpers delete order) | `lead` | gated surface; four FK targets verified against as-built unique constraints; small |
| 2 (three prompts + tool JSON schemas + judge rubric + `SynthesisBackend`/`GroundingJudgeBackend`/`ChunkRerankerBackend` protocol signatures + the normative directive-parse spec) | `lead` | prompt-bearing (judge rubric included) + seam design — lead-only per AGENTS.md |
| 3 (`synthesis_tools.py`: retrieval helper [hybrid scoring, RRF fusion, priors, boosts, reranker stage, caps, `RETRIEVAL_UNIT_CAP` guard], `query_findings`, `lookup`, the loop runner [turn accounting, budgets, unknown-tool rejection, cap-exhaustion forcing, scripted-stub drive]) | `codex` | subtle deterministic logic with exact pass conditions; done = the tool/loop/ranking test blocks green |
| 4 (`synthesis_backend.py` + `grounding_judge.py`: OpenAI + stub implementations of the Task-2 protocols; `tracing.py` traced-call factoring across all five OpenAI backends) | `codex` | implementation of lead-designed seams against schema-constrained I/O (the standing pattern); done = backend/stub/factoring tests + suite green |
| 5 (`synthesise.py`: resolution → mint → proposal → loop orchestration → six per-type validators → judge → repair → substrate writes → roll-up) | `codex` | judgment-bearing execution with a fully pinned spec (validators specified below); done = the invariant/edge/flag test blocks |
| 6 (registry/Config/harness/skeleton wiring) | `fast-worker` | mechanical from the 004–012 precedent + the exact spec below |
| 7 (contract-bulk test suite) | `fast-worker` | transcription of the contract's named-test list |
| 8 (judgment test suite: loop semantics, injection doubles, claim-validation edges, repair/regression guards, caps-bind, socket-deny) | `codex` | subtle-but-specified; each has an exact pass condition |
| 9 (deferred.md updates + knowledge concepts) | `lead` | living-doc text, user-facing wording |
| 10 (verification.md + four-profile live run) | `lead` | operator keys, cost judgment, trace inspection |

## Plan-pinned constants (the contract's plan-gate items — binding)

| Constant | Value | Note |
|---|---|---|
| `SECTION_CAP` | 8 | proposal validation ceiling |
| `SECTION_TURN_CAP` | 6 | generation turns per section loop (tool calls + the claims emission) |
| `REPAIR_ROUND_CAP` | 1 | one loop-free reword-down + one re-judge |
| `SYNTH_CHUNK_TOP_K` | 8 | per `search_chunks` call |
| `SYNTH_CHUNK_CHAR_BUDGET` | 24_000 | gathered chunk-text budget per section |
| `RETRIEVAL_UNIT_CAP` | 50_000 | in-memory ceiling over screened-corpus embedding units; fail-closed `retrieval_unit_cap_exceeded` |
| `REASONING_CLAIMS_MAX` | 3 | per block |
| `ARTEFACT_TITLE_MAX` | 300 | chars; verbatim intent, control chars stripped, truncated with `…` |
| Budget maximum | 2 + `SECTION_CAP` × (`SECTION_TURN_CAP` + 3) generation calls | rev 8 B1; test-asserted as the *binding* cap (caps-bind) |
| Models | `SYNTHESIS_MODEL = JUDGE_MODEL = "gpt-5-mini"` | contracted floor; both recorded per-surface in provenance |
| Embeddings | existing `text-embedding-3-small` via `EmbeddingBackend` | tool-query embedding; one call per `search_chunks` invocation, memoised per (section, query) |
| Fusion | Reciprocal Rank Fusion, k = 60, over (cosine rank, lexical rank) | lexical = casefolded token-overlap score against unit text (stdlib) |
| Selection prior | ×2.0 multiplicative on fused score for chunks of selected docs | recorded in provenance; a prior, never a filter |
| Boost clamp | [0.1, 10] | contract grammar (rev 8 M5) |
| Envelope | `synthesis_envelope_v1` = the cited chunks' full frozen text, no neighbours | + per-chunk `segmentation_policy` persisted (rev 8 M7) |
| Prompt/schema versions | `synthesise_sections_v1` · `synthesise_section_v1` (system prompt + the three tool JSON schemas version as one unit) · `grounding_judge_v1` | module constants, provenance-recorded |

**`lookup` vocabulary v1 (closed):** `appraisal_by_doc` ·
`classification_by_doc` · `selection_rationale` · `coverage_records` ·
`characterisation_summary` · `grouping_groups` · `tags_by_doc` ·
`docs_by_tag` · `tag_aggregate` (by type/asserter). Identifier/filter
args validated; unknown kind → tool-level validation error (never
executed); all queries scoped to `project_id` + the resolved run
references.

**Module layout:** `synthesis_tools.py` (tools + retrieval helper +
loop runner + `ChunkRerankerBackend` + stubs) ·
`synthesis_backend.py` (`SynthesisBackend` protocol, OpenAI + stub,
both writer prompts + tool schemas) · `grounding_judge.py`
(`GroundingJudgeBackend`, OpenAI + stub, judge prompt + envelope
assembly) · `synthesise.py` (`SynthesiseContext`, `synthesise_scope`,
the six validators, writes) · `tracing.py` gains the factored
traced-call helper (all five OpenAI backends migrate).

**Reference/substrate resolution spec (Task 5, binding):** deepest
given reference wins; `grouping_result.extraction_run_id` and
`extraction_result.selection_run_id` resolve via columns;
`selection_provenance["characterisation_run_id"]` resolves via
validated JSONB (rev 8 M3 — absent/malformed/mismatching an explicit
reference → structural failure). Substrate profile =
`{characterisation, selection, extraction, grouping, screened_docs,
appraised_docs}` booleans + ids, recorded in provenance. ≥ 1 groundable
substrate else `no_groundable_substrate` structural failure (no
artefact, no row). Chunk-claim/`search_chunks` gate additionally
requires the screened docs to carry appraisals (rev 8 M4; the skeleton
always satisfies this — appraise is deterministic).

**Per-type validator spec (Task 5, binding):** finding — cited ids ⊆
seed ∪ this-section `query_findings` returns; anchors resolved,
presence re-checked, abstract-basis re-located; unlocatable/`failed` →
`quote_unverified` + weakly-grounded cap. chunk — ids ⊆ this-section
`search_chunks` returns; `QuoteMatcher` against the whole doc basis;
verified spans → one citation row per spanned chunk + offsets in the
annotation payload (rev 8 B2); presence failure → reject → repair →
exclude + count. pattern — exact equality with the computed
value/spread. theme — ids ⊆ the referenced clustering. gap — grade +
base required; corpus-grade requires the non-`inadequate` coverage
record + boundary/adequacy payload fields (rev 8 M8) else degrade +
count; sparsity-grade requires characterisation coverage. reasoning —
≤ `REASONING_CLAIMS_MAX`, visibly labelled, judge strict-routed.
Content-scan-shaped assertions (cross-corpus shape, no computable
value) → reject (rev 8 M9). Substrate-ungated types reject with one
repair.

## Tasks & phases (each phase ends with a commit; `make verify-fast`
green at intermediate commits, full `make verify` at phase 1, phase 4+
and step-6 exit per the tiered gate)

**Phase 1 — substrate (Task 1, lead).** Migration 13 (`synthesis_result`
per the contract's binding DDL; four composite FK guards; downgrade
drops); `tests/helpers.py` delete order; roundtrip 24 ↔ 25 both DBs
(the 011 post-open lesson: roundtrip dev AND test).

**Phase 2 — prompts + seams (Task 2, lead).** The three prompt surfaces
with negative rules exactly as contracted; tool JSON schemas; protocol
signatures (`SynthesisBackend.propose_sections/write_section`,
`GroundingJudgeBackend.judge_block`, `ChunkRerankerBackend.rerank` —
pass-through default); the directive parser spec handed to Task 3/5 as
code-ready rules. Committed as module skeletons with prompts + tests
asserting the negative rules on built prompts.

**Phase 3 — tools + loop (Task 3, codex) then backends + factoring
(Task 4, codex).** Retrieval helper (deterministic on stub vectors),
three tools, loop runner (scripted-stub drivable), then OpenAI/stub
backends and the `tracing.py` traced-call factoring across
`extraction_backend.py`, `ranking.py`, `facet_grouping.py`,
`synthesis_backend.py`, `grounding_judge.py`. Codex sandbox cannot
reach localhost Postgres (012 lesson) — the lead runs DB-backed suites
on every codex drop.

**Phase 4 — the component (Task 5, codex).** `synthesise.py` per the
resolution + validator specs; writes ordered blocks → units →
annotations → citations → roll-up last; failure payload names prior
blocks. Full `make verify` at this commit.

**Phase 5 — wiring (Task 6, fast-worker).** `"synthesise"` registry
entry (requires `evidence_scope_id`; four optional refs), Config
fields, `run_harness(synthesis_backend=…, grounding_judge_backend=…)`
stub defaults, skeleton extension (threading the run ids; stub/live
switch on `OPENAI_API_KEY`).

**Phase 6 — tests (Task 7 fast-worker · Task 8 codex).** Contract-bulk
suite transcribing the contract's named-test list; judgment suite (loop
caps/budgets bind, unknown tool, scope guards, injection doubles incl.
tool-returned text and tag labels, sibling-repair regression guard,
fabricated-quote exclusion + never-persisted, ledger
context-not-evidence, determinism with fixed intent).

**Phase 7 — records + verification (Tasks 9–10, lead).** deferred.md
updates exactly as the contract's list (incl. closing `query-findings`
as landed, re-scoping composition, the content-scan and reranker
seams); knowledge concepts if earned; verification.md; the
**four-profile live check** (rapid [screen+classify+appraise] ·
characterisation-only · characterisation+selection-no-extract · full
chain) with Langfuse evidence, per-run counts, honest cost note, key
audit.

## Test strategy

Deterministic suite only (stub backends, stub vectors, scripted loop);
zero egress (socket-deny covers both content modes). The contract's
"Verification evidence expected" named-test list is the checklist;
judgment cases live in `test_synthesise_judgment.py`, bulk in
`test_synthesise.py` + `test_synthesis_tools.py`. Quality (prose,
sections, retrieval, judge calibration) is eval territory — asserted
nowhere, stated in verification.md.

## Review-stack sizing (step 7, for conversation C)

Per the review-economy notes: `/code-review` medium with per-angle
diff scoping (this will be a large product diff — scope angles to
`src/policy_atlas/synthes*`/`grounding_judge.py`/`tracing.py` vs
tests vs wiring); one security lane with the loop as headline target;
contract-verifier (Opus, pinned); Codex adversarial. ≤ 250K reasoning /
≤ 500K fast-worker budgets.

## Risks & mitigations

- **Loop-runner novelty** (first agent loop): mitigated by the
  scripted-stub design (the real runner driven by fixture-declared
  turns) and code-enforced caps; the security lane targets it.
- **Large diff at review**: phase commits are the review packets;
  per-angle scoping pinned above.
- **Codex/Postgres gap** (012 lesson): lead runs DB suites on drops.
- **Live-run cost**: four profiles ≈ 2 + 8×(6+3) worst case per deep
  run at gpt-5-mini — expect single-digit dollars; budget note in
  verification.md; `SECTION_CAP`/`SECTION_TURN_CAP` can be demo-lowered
  via plan-pinned constants only if the fixture corpus proposal comes
  in small (record actuals honestly).
