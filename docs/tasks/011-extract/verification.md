# Verification: 011-extract

Evidence for the extract slice (EB component 7 — Tier-1 extraction, the findings
layer's first write: three tables, the `ExtractionBackend` seam, the
`extract_iof_v1` prompt over full document text). Build sections filled at step
6; **Review findings** + **Rubric status** to be added by the step-7 review
stack (fresh conversation).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | **428 passed** (321 pre-slice → +32 `test_quote_verify.py` + 10 `test_extraction_backend.py` + 9 `test_extract.py` + 37 `test_extract_contract.py` + 15 `test_extract_judgment.py` + 4 registry cases in `test_compile.py`; six table-count assertions bumped 20 → 23). Stub/double backends throughout — deterministic, zero egress |
| `make typecheck` | pass | mypy strict, 53 source files |
| `make lint` | pass | ruff |
| `make build` | pass | sdist + wheel |
| `make okf-validate` | pass | 24 concepts, 0 violations (one data-model flow-back this slice) |
| migration roundtrip | pass | `alembic upgrade head` → 23 tables (inspector) → `downgrade -1` → 20 → `upgrade head` → 23, clean (revision `d4e9b2f7a1c5`); downgrade drops exactly the three new tables; the partial unique memo index (`uq_ser_memo`, `WHERE status IN ('extracted','no_findings')`) verified present via inspector |

Socket-deny result (named per the contract): `test_socket_deny_extract_round_trip`
denies `socket.socket` around a full 2-doc mixed-basis `extract_scope` round trip
— pass. Composite-FK note (plan Task 1): the new `uq_ser_id_project` composite
unique was added as the finding table's FK target per the repo's parent pattern;
the other composite-FK targets (`uq_runs_run_project`, `uq_pss_id_project`,
`uq_evidence_scope_id_project`) pre-existed — verified, not assumed. No
dependency changes (`openai`/`langfuse`/`pydantic` already present — asserted,
not added).

## Checks beyond the build

All suite checks are deterministic (sentinel-driven stub + misbehaving /
recording / hijacked doubles for the judgment paths). Named results per the
contract's evidence list:

- **Memo semantics** — `test_memo_reuse_second_run` (hit → reuse, no call, no
  new finding rows, the first run's `extraction_record_id` returned);
  `test_fingerprint_stub_vs_live_distinct` (stub and live fingerprints are
  distinct full sha256 hexes); `test_no_findings_memoised` (a `no_findings` doc
  is memoised and not re-paid); `test_failed_record_never_blocks_or_satisfies_memo`
  (a failed record inserts freely, never matches the memo, and a retry in a new
  run extracts fresh — two records coexist under the partial unique index).
- **Coverage invariants** — `test_coverage_invariants_at_payload_boundary`
  (statuses cover exactly the selected set; `selected == extracted +
  no_findings + failed == fresh + reused`; every finding row joins to a record
  of a selected doc); also asserted in code before the roll-up write
  (`_assert_invariants`, violation → `ExtractError`).
- **Quote verification** — verbatim hit passes (`exact`); boundary-spanning
  quote across two chunks passes with ≥2 chunk-local spans; fabricated quote →
  finding kept, flagged `quote_unverified`, counted in the roll-up. Unit level:
  32 tests in `test_quote_verify.py` (smart-quote/em-dash/NBSP/soft-hyphen
  folds, raw-offset fidelity `basis.raw_text[start:end] == quote`, half-open
  intervals, empty-quote failure).
- **Abstract-basis extraction** — end-to-end: no chunks, anchors verified
  against the envelope abstract, `chunk_id` null in grounding, basis recorded
  on record + roll-up.
- **Verified-quote match location** — verified anchors carry non-empty
  `spans` (chunk id + raw char interval) and a graded `match_status`
  (`exact` | `normalised`); unverified anchors carry `failed` + empty spans.
- **Field-rule validation** — out-of-bounds p-value / inverted CI /
  non-positive N / I² > 100 / negative τ² / NaN effect size → field nulled +
  flagged `unclear`, finding kept; null-like strings (`"null"`, `"n/a"`, …) in
  nullable text/numeric fields → real null + `not_extracted` marker; closed
  enums exempt (`no_effect` survives untouched); estimate-level coherence
  (study + k present → `unclear`; study + absent pooled stats →
  `not_applicable`; claim + any present numeric → `unclear`; pooled + absent →
  `not_extracted`) with fixtures for all three estimate levels.
- **Repeated-quote cursor** — the same sentence quoted twice grounds to
  successive occurrences (distinct span starts), unit + component level.
- **Within-doc claim-keyed dedup** — same claim, two quotes → one finding with
  merged anchors, collapse flagged and counted; different effect sizes →
  distinct findings. Reached both via the stub sentinel and via a misbehaving
  backend double.
- **Doc-status rules** — valid-empty → `no_findings`; every candidate
  grain-invalid → `extraction_failed(invalid_records)` (retryable); mixed →
  `extracted` with invalids dropped-and-counted.
- **Pre-flight example validation** — a doctored non-verbatim few-shot example
  fails `_preflight_validate_example` with a loud `RuntimeError` (and the real
  example validates at every import).
- **Empty-findings-is-legal** — a doc with no IOF content yields `no_findings`,
  no forced statistics anywhere.
- **Windowing** — multi-window fixture with budget arithmetic asserted
  (`call_budget.baseline` = greedy 1-segment-overlap window count); window
  failure → the whole doc `extraction_failed (window_failed: <ExcType>)`,
  sibling docs proceed, component completes; oversize single chunk →
  deterministic `{chunk_id}#p{i}` subsegment split, full-read guarantee holds,
  verification unaffected (runs against original chunk content).
- **Schema line** — enrichment fields (`normalised_magnitude`, `causal_weight`,
  `is_beneficial`) test-asserted absent from the table columns; the negative
  rules test-asserted present on the built prompt.
- **Field coverage** — absent nullable fields carry markers
  (`not_extracted` | `unclear` | `not_applicable`), never fabricated values;
  aggregated per-field marker counts in the roll-up.
- **Edge scopes** — empty selection → honest zero-doc roll-up row +
  `empty_selection` flag (group's reference row exists); missing selection row
  → structural `ExtractError`; same-run re-execution → loud `IntegrityError`
  (`uq_exr_scope_run`).
- **Determinism** — two identically-seeded projects → equal summaries (counts,
  findings, basis, flags, provenance, per-doc sequences);
  `MAX_CONCURRENT_EXTRACT` 1 vs 4 → identical DB write order (parent-ordered
  writes, physical row order compared).
- **Injection posture** — injection-shaped chunk lands only inside the
  segments-JSON data block (system prompt byte-identical); inert at component
  level (`no_findings`); a hijacked backend echoing the injection verbatim
  stores it as flagged-or-verified *data*, never instruction-following. Intent
  canary (`INTENT-CANARY-9Z`) appears in no backend payload and not in the
  system prompt — **no intent crosses the wire** (contract rev 1.5).
- **Counting double** — exactly the fresh docs are sent to the backend;
  memo-reused docs never; calls == `call_budget.used`.
- **Fingerprint completeness** — every pinned component version appears in
  `extraction_provenance`; monkeypatching any single component (prompt, schema,
  field rules, verifier, model, window budget, max output tokens, retry cap)
  changes the digest; stub ≠ live.
- **Key hygiene** — an `OPENAI_API_KEY` canary appears nowhere in the summary,
  roll-up row, records or findings.
- **Delete-order integrity** — `delete_project_data` removes findings →
  records → roll-up before their ancestors, no FK errors, zero rows remain.

Deterministic vs AI eval (named per the contract): all suite checks are
deterministic. Extraction *quality* (are the findings right/complete?) is eval
territory — finding-level ground truth belongs to the eval workstream
(recorded in `docs/deferred.md`). This slice's bar is machinery correctness,
schema fidelity, honest coverage accounting and verified anchoring; the review
stack should not mistake the machinery tests for a quality claim.

## End-to-end command

```bash
set -a; source .env; set +a   # OPENAI_API_KEY + LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST + DATABASE_URL (dev)
uv run python -m policy_atlas.skeleton
```

Stub end-to-end (deterministic, zero egress — also driven):

```bash
set -a; source .env; set +a
env -u OPENAI_API_KEY -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY uv run python -m policy_atlas.skeleton
```

Memo second-run demonstration (same project/scope/selection, new run id, live
backend — zero fresh calls):

```bash
set -a; source .env; set +a
uv run python <scratchpad>/memo_second_run.py <project_id-from-the-live-run>
```

## Live-run evidence

Three live runs (dev DB, fixture corpus, `OPENAI_API_KEY` + `LANGFUSE_*` from
`.env`); the first two surfaced real defects — recorded under Diff summary —
and the third is the clean evidence run. Each run is a fresh project (the memo
is project-scoped), so the memo demonstration is a second extract run inside
run 3's project.

**Run 1** (8192 output cap): honest per-doc failures — 4 extracted
(30 findings), 1 `no_findings`, 5 `extraction_failed (window_failed:
LengthFinishReasonError)`; component completed, failures counted and flagged;
retries consumed budget exactly as designed (baseline 14, max 28). → cap
raised (deviation 2). **Run 2**: aborted on a model-emitted NUL at write time;
the outer transaction rolled back atomically (no partial state). → scrub
(deviation 3).

**Run 3** (clean, project `216b9338-92f0-4599-970a-57f1827f4288`,
fingerprint `417b32f1…f8168d`, mode `live`, model `gpt-5-mini`, prompt
`extract_iof_v1`):

- Selected 10 (budget 8 + 2 mixed-basis must-include pins, both bases
  asserted pre-extract): **7 full-text `extracted` · 3 abstract-only
  `no_findings` · 0 failed**; `selected == extracted + no_findings + failed`
  and `fresh == 10, reused == 0` hold in the rendered summary.
- **168 findings written** (per-doc 1–104; the 104 is a food-policy review
  with many intervention–outcome tables), `dedup_collapsed` 7,
  `invalid_dropped` 0.
- **Anchors: 181 total — 49 `exact`, 64 `normalised`, 68 `failed`** (62.4%
  verified); `quote_unverified` findings 61/168. Spans ⟺ verified consistency
  holds on every anchor (DB-audited). Spot-checked failed anchors are genuine
  non-verbatim emissions (the model re-serialised *table* content with
  bullets/pipes that don't occur in the parsed text) — honest flags, not
  verifier misses; this is exactly the recorded bounded-fuzzy-fallback /
  extraction-quality-eval seam, and the abstract-only docs' honest zero yield
  is the expected thin-basis behaviour.
- **Call budget**: logged pre-run (baseline 14, max 28); extraction wall time
  ~5 min at concurrency 4.
- **Memo second run** (same scope + `selection_run_id`, new run id, live
  backend): **all 10 docs `reused: true`, zero calls** (budget
  baseline/max/used = 0/0/0), the first run's `extraction_record_id`s
  returned, same fingerprint; no new finding rows.
- **Langfuse (dev instance)**: `extract:{pss}:w0` generation spans present
  with prompt version + token usage; run-level scores present:
  `quote_verified_share`, `no_findings_share`, `extraction_failure_count`,
  `dedup_collapsed_count` (API-verified). Known wart: the generation spans
  surface as detached traces — same capability-run-seam symptom already
  recorded for 009/010 in `docs/deferred.md`.
- **Cost note (honest)**: extract step of run 3 = 14 calls, 309,601 prompt +
  93,755 completion = 403,356 tokens on `gpt-5-mini` ≈ **$0.27** at published
  rates ($0.25/M in, $2.00/M out); all three live runs' extraction ≈ $0.8
  total. Extraction is the deliberately-expensive Tier-1 step: full-document
  prompts plus reasoning tokens dominate wall time (single calls run minutes).
  Model step-up remains a recorded option, not taken: yield at mini-class was
  substantive (168 findings; the quality bar is eval territory).
- Keys absent from all captured output (scripted audit over the three run
  logs against the live key values — clean).

## Diff summary

Data files excluded per the 007 retro (none changed this slice).

- **Schema** (`schema.py`, migration `d4e9b2f7a1c5`): `source_extraction_record`
  (durable memo: partial unique over success states; `uq_ser_id_project`
  composite-FK target; failed ⟺ reason-coded CHECK),
  `intervention_outcome_finding` (source-named references; closed
  effect/estimate/causality vocabularies; strata/statistics/coverage/grounding
  JSONB), `extraction_result` (run roll-up, `uq_exr_scope_run`). Tables 20 → 23.
- **Models + prompt** (`extraction_records.py`, `extract_prompt.py`): wire vs
  stored model split (`extra="forbid"`; tolerant wire so iof_rules_v1 coerces,
  never the API); prompt field docs generated from the wire models (one source
  of truth); `extract_iof_v1` with negative rules, direction-not-desirability
  semantics, evidence-type conditioning, prevalence guard, one pre-flight-
  validated few-shot example; no intent anywhere.
- **Verifier** (`quote_verify.py`): qv_v1 normalisation with raw-offset index
  map, ordered occurrence cursor, graded status, chunk-local spans;
  iof_rules_v1; stratum canonicaliser; claim-keyed dedup.
- **Backend seam** (`extraction_backend.py`): protocol + OpenAI structured
  outputs (internal Langfuse generation spans, full I/O per the settled
  posture) + sentinel stub.
- **Component** (`extract.py`): the pipeline per plan; roll-up written last;
  invariants asserted pre-write; fingerprint = full sha256 over every
  output-affecting version.
- **Wiring** (`plan.py`, `harness.py`, `skeleton.py`, `tracing.py`,
  `tests/helpers.py`): registry entry, `selection_run_id` compile-fails-closed,
  `extraction_backend` stub default, skeleton extract step + mixed-basis
  must-include pins + extraction score summary, FK-safe delete order.
- **Docs**: data-model flow-back (approved rev-1.4 ⚑), `docs/specs/log.md`
  entry, `docs/deferred.md` task-011 seam section.

**Flagged deviations (minor, resolved within the contract's vocabulary):**

1. **Uploaded full-text docs extract from envelope chunks.** The contract's
   basis rule ("basis full_text ⇢ chunks of `full_text_snapshot_id`") missed
   the 008 corpus model's *uploaded* path, where the frozen full text lives on
   the envelope snapshot and `full_text_snapshot_id` stays NULL. As written it
   falsely failed every uploaded full-text doc with `basis_mismatch` (caught
   driving the stub skeleton). Resolution: the basis snapshot is
   `full_text_snapshot_id` when ingested, else the envelope snapshot; the
   memo/record key follows. Regression test
   `test_uploaded_full_text_doc_extracts_from_envelope_chunks`.
2. **`EXTRACT_MAX_OUTPUT_TOKENS` raised 8192 → 32768.** The plan pinned 8192;
   gpt-5-mini is a reasoning model, so `max_completion_tokens` covers
   reasoning + output, and the first live run truncated 5 of 9 full-text docs
   (honest `window_failed: LengthFinishReasonError` per-doc failures — the
   machinery behaved exactly as designed, but the pin was tuned for a
   non-reasoning model). The contract's discipline is an *explicit* cap
   (V2's lesson), not the number; the cap is a fingerprint component, so the
   change creates records alongside, never stale reuse.
3. **NUL scrub at the backend boundary.** The second live run aborted on
   `psycopg UntranslatableCharacter`: the model emitted a string containing
   `\u0000`, which Postgres rejects in TEXT/JSONB; the whole run rolled back
   atomically (no partial writes — the outer transaction held). Model output
   is untrusted data, so NUL characters are now stripped from wire records as
   they come off the backend, before validation/verification. Regression test
   `test_nul_bearing_model_output_is_scrubbed` (via a misbehaving backend — a
   NUL cannot ride the DB-stored stub sentinel for the same reason).
4. **Zero-anchor wire records are grain-invalid.** The contract defines
   grain-invalid as missing intervention/outcome; a record with zero anchors
   cannot satisfy the anchors ≥ 1 design and is treated as the same class of
   malformed emission (dropped-and-counted), rather than inventing a new
   status.
5. **`thin_extraction` flag not computed.** The contract lists it "where
   computed"; no definition was ever pinned, so v1 deliberately omits it
   (recorded in `docs/deferred.md`).
6. **Executor rerouting (process, not code).** Codex hit its session cap at
   build start (reset 7:50am next day), so the plan's four `codex` marks were
   rerouted per the harness ladder: Tasks 3/5/8 → `deep-reasoner` (Opus),
   Task 4 → `fast-worker` (Sonnet). All delegated output was lead-reviewed
   before landing; the family-flip review benefit is partly recovered by the
   fresh-conversation review stack (step 7).

## Intent & assumptions

- The stub is a test seam, not a strategy: there is no non-LLM production
  extraction path; suite and library defaults are stub + socket-deny.
- `ExtractContext.intent` is carried for wiring uniformity only and is not
  consumed (code comment per plan; judgment test asserts no intent egress).
- Reused docs contribute to `findings.total` but not to the fresh-run
  counters (`quote_unverified`/`dedup_collapsed`/`invalid_dropped`).

## Known unverified items

- **Extraction quality** (right/complete findings) — deliberately out of scope;
  eval-gated (see Checks beyond the build).
- **A single transient suite failure** was observed once during the phase-5
  gate (`make verify`: 1 failed / 426 passed) and did not reproduce: the
  immediately following full run and two further full runs were green, and the
  five extract-related files passed 3 consecutive targeted runs (102 tests).
  The failing test's name was not captured. Flagged for the review stack
  rather than silently dropped.
- **Intra-run shared-basis-snapshot memo collision** — impossible with the
  current corpus, recorded in `docs/deferred.md` with the upgrade path.
- Write-time DB errors other than the scrubbed NUL class fail the component
  (not per-doc) — structural by design; the outer transaction guarantees no
  partial state.

## Public safety

- Full-text egress was the openly-licensed fixture corpus only (the
  sanitized-fixtures policy's full-text amendment); the live path is
  opt-in-by-key on the demo entrypoint.
- Full-I/O traces (document text, findings) went to the user-operated dev
  Langfuse instance only (host pinned via `LANGFUSE_HOST`; the tracing module
  refuses the SaaS default).
- Keys are env-only; the key-hygiene test asserts no key material in any
  captured output; this file contains counts and ids only, no raw source text.
- Finding rows are source-derived text by construction — public-safe for this
  fixture corpus, private-by-default posture recorded for arbitrary corpora.

## Deferred work

Seams recorded in [docs/deferred.md](../../deferred.md) § "Extract / findings
layer (task 011 seams)": extraction service + evidence dataset snapshots ·
extraction-quality evals (also unblocks 010's rerank-quality seam) ·
multi-pass recall · retrieval-augmented extraction · retrieval-scoped
extraction (declined) · generic finding container (declined) ·
reason-then-constrain · LangExtract dependency (declined) · per-intervention
decomposition · bounded fuzzy quote fallback · failed-extraction recovery
loop · cross-window dedup · hybrid-indexing pointer · mixed/unclear
first-class requirement on group/synthesise · intra-run shared-snapshot memo ·
`thin_extraction` · CFIR fields → `implementation_context_finding` (entry
extended) · parse-quality escalation pointer (docling entry extended).

## Review findings

Added after the review stack (step 7):

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review** (Tier 3):
- **`/simplify`:**
- **`/okf validate`:**

## Rubric status

To be completed at step 7 against `rubric.md`.
