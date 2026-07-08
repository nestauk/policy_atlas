# Implementation Plan: 013-synthesise

> **Status:** **approved rev 2** (2026-07-08 · Shabeer Rauf — approval
> given as the explicit build directive opening conversation B) —
> plan-stage adversarial review adjudicated
> (5 majors · 5 minors, 0 blockers — 9 adopted, 1 adopted-as-clarification
> [m7: `chunk.segmentation_policy` exists in the as-built schema; the
> reviewer's premise was wrong — the source is now pinned]).
> **Lane deviation, recorded:** the Codex adversarial lane was capped at
> this gate (session limit, resets 05:30) and its rescue agent died before
> registering a job; the review ran on the **fresh-context deep-reasoner
> substitute** (the 011 fallback pattern) with the same read-only brief.
> The reviewer positively verified the plan's load-bearing code-grounding
> (transitive resolution incl. the JSONB hop; B2 row-per-chunk
> expressibility; the five-backend factoring list; stub-vector
> determinism; four-profile skeleton feasibility). Option open at the
> gate: additionally re-run the Codex pass after reset.
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
| 5 (`synthesise.py`: resolution → mint → proposal → loop orchestration → six per-type validators → judge → repair → substrate writes → roll-up; **+ the bespoke `_run_synthesise` harness node** — review M1) | `codex` | judgment-bearing execution with a fully pinned spec (validators + the node spec below); done = the invariant/edge/flag test blocks |
| 6 (registry/Config/harness/skeleton wiring **+ `synthesis_score_summary`** — review M2/m8; exact enumeration below) | `fast-worker` | mechanical against the explicit enumeration (the generic-precedent trap is closed by the Task-5 node spec) |
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
| `RETRIEVAL_UNIT_CAP` | 20_000 | in-memory ceiling over screened-corpus embedding units; fail-closed `retrieval_unit_cap_exceeded` (lowered from a 50K draft — review M5: pure-Python cosine realism; the true ceiling is eval/calibration territory) |
| `CANDIDATE_POOL_PER_LEG` | 200 | top-N per relevance leg **before** fusion (review M5): boosts/priors/reranker operate on this bounded candidate set, and "zero-relevance never surfaced by boost alone" is defined as *not in either leg's pool → not a candidate* |
| `REASONING_CLAIMS_MAX` | 3 | per block |
| `ARTEFACT_TITLE_MAX` | 300 | chars; verbatim intent, control chars stripped, truncated with `…` |
| Budget maximum | 2 + `SECTION_CAP` × (`SECTION_TURN_CAP` + 3) generation calls | rev 8 B1; test-asserted as the *binding* cap (caps-bind) |
| Models | `SYNTHESIS_MODEL = JUDGE_MODEL = "gpt-5-mini"` | contracted floor; both recorded per-surface in provenance |
| Embeddings | existing `text-embedding-3-small` via `EmbeddingBackend` | tool-query embedding; one call per `search_chunks` invocation, memoised per (section, query) |
| Fusion | Reciprocal Rank Fusion, k = 60, over (cosine rank, lexical rank) within the candidate pool | lexical = casefolded token-overlap score against unit text (stdlib); **ties break on `str(unit_id)` lexicographic** (review m10, the codebase convention) |
| Vector loading | **once per run** — the resolved scope's unit vectors are loaded/parsed into one memoised matrix at first `search_chunks` call and reused across all sections/turns (review M5); query embeddings memoised per (section, query) | never re-loaded per call |
| Turn accounting | **the forced emission IS the `SECTION_TURN_CAP`-th turn** (review M4): the last turn is reserved for the claims emission, so at most `SECTION_TURN_CAP − 1` tool calls occur and the budget maximum is exact, never exceeded — the caps-bind test asserts the precise ceiling | |
| Selection prior | ×2.0 multiplicative on fused score for chunks of selected docs | recorded in provenance; a prior, never a filter |
| Boost clamp | [0.1, 10] | contract grammar (rev 8 M5). **Divergence from the select precedent, deliberate** (review m6): select *rejects* out-of-range weights; synthesise **clamps** them — the contract grammar wins; a builder must not copy `_float_in_clamp`'s raise |
| Envelope | `synthesis_envelope_v1` = the cited chunks' full frozen text, no neighbours | + per-chunk `segmentation_policy` persisted (rev 8 M7) — **source: the `chunk.segmentation_policy` column** (exists in the as-built schema; review m7 clarified) |
| Prompt/schema versions | `synthesise_sections_v1` · `synthesise_section_v1` (system prompt + the three tool JSON schemas version as one unit) · `grounding_judge_v1` | module constants, provenance-recorded |

**`lookup` vocabulary v1 (closed):** `appraisal_by_doc` ·
`classification_by_doc` · `selection_rationale` · `coverage_records` ·
`characterisation_summary` · `grouping_groups` · `tags_by_doc` ·
`docs_by_tag` · `tag_aggregate` (by type/asserter). Identifier/filter
args validated; unknown kind → tool-level validation error (never
executed); all queries scoped to `project_id` + the resolved run
references.

**Directive parser — single owner (review M3):** one
`parse_synthesis_directive(context) -> SynthesisDirective` function in
`synthesis_tools.py`, built in **Task 3** against the Task-2 normative
grammar, owning the whole top-level validation (object; keys exactly
`{sections, retrieval_boosts}`; malformed-vs-unknown semantics). Task 5
consumes its validated output for `sections`; the retrieval helper
consumes it for `retrieval_boosts`. No second parse anywhere.

**Module layout:** `synthesis_tools.py` (tools + retrieval helper +
loop runner + directive parser + `ChunkRerankerBackend` + stubs) ·
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
`synthesis_backend.py`, `grounding_judge.py`. The factored helper's
signature must accommodate the heterogeneous call-sites (review m9):
`ranking`'s in-span extra score + `facet_grouping`'s parametrised span
names/error strings — no lowest-common-denominator flattening. Codex
sandbox cannot reach localhost Postgres (012 lesson) — the lead runs
DB-backed suites on every codex drop, **plus a keyed-Langfuse smoke of
one traced call after the factoring lands** (tracing is a no-op
without keys, so the suite exercises the traced path shallowly).

**Phase 4 — the component (Task 5, codex).** `synthesise.py` per the
resolution + validator specs; writes ordered blocks → units →
annotations → citations → roll-up last. **Includes the bespoke harness
node (review M1):** synthesise does NOT route through the generic
`_run_scope_component` — a `_run_synthesise` node modelled exactly on
009's `_run_characterise` precedent, with a structured
`SynthesiseFailure(blocks_written=[...])` exception so
`component.failed` names the prior blocks (the generic node's
`{component, error}` payload cannot). Full `make verify` at this
commit.

**Phase 5 — wiring (Task 6, fast-worker; exact enumeration — review
M2).** (a) `plan.py`: `grouping_run_id` added to **both**
`_ValidatedRunSpec` and `compile()` (the field a copy-from-precedent
sweep misses — a dropped field fails silently); `"synthesise"` registry
entry requiring `evidence_scope_id` with all four refs optional. (b)
`harness.py`: `synthesis_backend` + `grounding_judge_backend` threaded
through `HarnessState` and `run_harness` (stub defaults); the Task-5
node registered. (c) `skeleton.py`: synthesise invocation threading
the run ids (stub/live switch on `OPENAI_API_KEY`); **the four-profile
demo = four `synthesise` invocations varying which resolved refs are
passed** (the reviewer verified feasibility on the existing
single-scope skeleton). (d) `tracing.py`:
**`synthesis_score_summary`** mirroring `grouping_score_summary`
(review m8) — scores: claims-valid share, citation-verified share,
unsupported share, chunk-rejection share.

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
