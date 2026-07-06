# Implementation Plan: 009-characterise

> **Status:** drafted — awaiting plan-phase adversarial review + human confirmation.
> Contract: [contract.md](contract.md) (approved 2026-07-06 · Shabeer Rauf, rev 9;
> contract-stage adversarial findings adjudicated at revs 6–6.1).

## Overview

One component plus the two egress seams it opens, on `task/009-characterise`:
1. **Schema** — three new tables (`chunk_embedding` · `characterisation_result` ·
   `source_tag`) + the `open_tags` retirement (migration 9; tables 16 → 19).
2. **Embedding layer** — `EmbeddingBackend` seam (live OpenAI + stub), the
   embedding-unit derivation, and the eager-and-uniform embed pass wired into all
   three ingestion paths.
3. **Grouping layer** — `GroupingBackend` seam (live two-stage OpenAI + stub), the
   lead-authored prompt pair, code-owned validation + targeted repair.
4. **`characterise.py`** — coverage pass over columns + the tag layer, grouping
   orchestration, tags, characterisation row, landscape summary.
5. **Provider-tag materialisation** in acquire; **Langfuse tracing** on the two live
   backends; **wiring + tests + three spec flow-backs**.

Unlike 008 (which upgraded corpus documents in place), this slice adds a downstream
reader component plus cross-cutting substrate (vectors, tags, traces) that earlier
components now also write.

## Executor routing (plan-time decision, per harness.md ladder)

| Task | Executor | Why |
|---|---|---|
| 1 (schema + migration 9 + deps) | `lead` | gated surface; composite-FK targets must be verified against as-built unique constraints; the adjudicator owns migration subtleties (008 precedent) |
| 2 (embeddings.py: seam + units + embed pass) | `codex` | judgment-bearing execution, precise contract spec, machine-verifiable done (unit/idempotency tests) |
| 3 (embed wiring into 3 ingestion paths + provider-tag materialisation in acquire) | `codex` | multi-file coherence against a pinned normalisation table; test-verifiable |
| 4 (grouping prompt pair) | `lead` | prompt-bearing — lead-only per AGENTS.md, no exceptions |
| 5 (GroupingBackend: protocol impls, live two-stage + stub) | `codex` | implementation of a lead-designed seam against schema-constrained I/O; test-verifiable |
| 6 (characterise.py: coverage + orchestration + validation/repair + tags + row + summary) | `codex` | the contract's decision-4 case table is a precise brief; done = the grouping test block |
| 7 (Langfuse tracing wiring) | `codex` | new-SDK integration judgment, but bounded (two wrap points, span/score spec below); verifiable by the no-keys-no-op tests + live trace check |
| 8 (registry/harness/skeleton/helpers wiring) | `fast-worker` | mechanical from 004–008 precedent + exact spec below |
| 9 (test suite: contract bulk) | `fast-worker` | transcription of the contract's test list |
| 10 (test suite: judgment cases — socket-deny scoping, injection shapes, budget double, unit determinism) | `codex` | subtle-but-specified; each has an exact pass condition |
| 11 (spec flow-backs ×3 + log.md) | `lead` | living-spec text, user-approved wording |
| 12 (verification.md + live manual run) | `lead` | needs the operator keys (OpenAI + Langfuse dev), cost judgment, trace inspection |

Lead marks carry their justification inline (routing retro, 2026-07-05: the burden
sits on keeping work, not delegating it). Codex briefs are one-concern,
self-checkable; anything failing the brief test at build time is a plan deviation to
flag, not silently absorb.

## Plan-pinned details (the contract's named "plan detail" items)

- **Models**: discovery `gpt-5-mini`; assignment `gpt-5-nano` (constants in
  `grouping.py`; recorded in `grouping_provenance`).
- **Batching**: assignment batch size **40**; concurrency = bounded gather over
  batches (cap 4 in flight); retry caps `discovery_retry_cap = 1`,
  `assignment_repair_cap = 1` (one targeted residue call per batch).
- **Theme bounds**: 3–12 (small-n: `1..min(n, 12)`).
- **Theme-name constraints**: name ≤ 80 chars, description ≤ 240 chars, printable
  unicode minus control chars; violations = invalid discovery output (retry once).
- **Embedding units**: token target 512 ≈ **2,000-char budget** (conservative ~3.9
  chars/token); split at sentence boundaries (fallback: paragraph, then hard split);
  ~10% overlap (200 chars); empty/whitespace chunks yield no unit.
- **Embed pass**: 128 texts per API call; `max_chunks` guard default 20,000 units
  per pass; embed dimension 1536 (validated per row).
- **`asserted_by` vocabulary**: `openalex` · `overton` · `overton_llm` ·
  `characterise` (closed in code, additive later).
- **Provider-tag normalisation table** (finding 13 discharge; mixed shapes are
  fixture-tested):
  - OpenAlex: `primary_topic.display_name`; `topics[].display_name`;
    `sustainable_development_goals[].display_name` → asserted_by `openalex`.
  - Overton: `topics` (string **or** list — both handled); `classifications[]`
    (name field); `sdgcategories[]` → `overton`; `llm_document_theme` (single
    string) → `overton_llm`.
  - Normalisation: strip, collapse internal whitespace, preserve case for display,
    dedupe per (document × tag_type × asserted_by) case-insensitively; missing/
    non-string values skipped silently (they are absent, not errors).
- **Langfuse**: `langfuse` SDK ≥ 3; one trace per run named `run:{run_id}`; spans
  `component:{name}` → `embed:batch{i}` / `discover` / `assign:batch{i}` /
  `repair:batch{i}`; metadata = ids, profile/prompt versions, models, token counts,
  validation outcome; validation outcomes also as scores
  (`assignment_batch_valid` 0/1, `unclustered_share`); full I/O on spans (settled).
- **Landscape summary shape**: `{coverage: {…, base}, themes: [{name, description,
  size}], unclustered: {count, share}, flags: [...], provenance: {...}}` — exact keys
  frozen in Task 6 and asserted by the payload test.

## Architecture decisions (all fixed in the approved contract)

- Two-stage grouping: discover (whole corpus, one call) → assign (fixed theme list,
  batched); budget baseline `1 + ceil(n/40)`, enforced maximum
  `(1 + 1) + ceil(n/40) × (1 + 1)`; validation by case (invented → drop in code;
  dup-same → dedupe in code; missing ∪ conflicting → one targeted residue call);
  `unclustered` counted; `screened_in == grouped + unclustered`; empty scope →
  skip + `empty_scope` flag.
- Embedding units at unit grain, one vector per unit, offsets into canonical chunks;
  chunks immutable; JSONB vectors, no pgvector.
- Tags: `source_tag` is the single tag home (`open_tags` retired); assertion
  provenance (`asserted_by`, `created_by_run_id` NOT NULL); insert-if-absent;
  provider classes never mix with ours.
- Coverage: deterministic distributions over columns + `(tag_type, asserted_by)`;
  base ladder visible; no absence claims (test-asserted).
- Run-local grouping in `characterisation_result` (unique per scope × run);
  `grouping_provenance` required keys.
- Egress: env-only keys; stubs default; skeleton live on configured key; budget
  guards; Langfuse full-I/O tracing on live backends only, no-op without keys.

## Dependency graph

```
Task 1 (schema + migration 9 + deps openai/langfuse)
   ├─→ Task 2 (embeddings.py)  ─→ Task 3 (ingest wiring + provider tags)
   ├─→ Task 4 (prompts, lead) ─→ Task 5 (GroupingBackend) ─→ Task 6 (characterise.py)
   │                                                            ├─→ Task 7 (Langfuse)
   │                                                            ├─→ Task 8 (wiring)
   └────────────────────────────────────────────────────────────┴─→ Tasks 9+10 (tests)
                                                     Task 11 (flow-backs) · Task 12 (verification)
```

---

## Phase 1 — Schema + dependencies (separable commit)

### Task 1: Tables + migration 9 + deps — `lead`

**Files:** `src/policy_atlas/schema.py`, `alembic/versions/<hash>_characterise.py`,
`pyproject.toml` (+ `uv.lock`).

- Three tables exactly per the contract's schema block; composite FK targets
  verified against as-built unique constraints (`evidence_scope`, `runs`,
  `project_source_snapshot` — add the referenced composite uniques only if they
  don't already exist from the screening-result precedent; any addition is within
  gate 1 and noted in verification.md).
- Drop `source_classification_result.open_tags` + `ck_scr_open_tags_array`
  (downgrade restores); `classify.py` stops emitting the field.
- Module docstring: "nineteen tables, nine alembic migrations".
- `pyproject.toml`: `openai` + `langfuse` (pin minimums); `uv lock`.

**Acceptance:** migration roundtrips; `make verify` green (nothing reads the new
tables yet). **Commit.** Scope: S–M.

## Phase 2 — Embedding layer

### Task 2: `embeddings.py` — `codex`

Protocol + `OpenAIEmbeddingBackend` (timeouts, retry/backoff, 128-text batches) +
`StubEmbeddingBackend` (content-hash vectors, 1536-dim) + unit derivation
(2,000-char sentence-boundary units, 200-char overlap, offsets) +
`embed_pending_chunks` (anti-join over units, deterministic order, honest counts,
`max_chunks` guard). Vector validation on insert. Done = the embed-pass test block.
Scope: M (~250 lines).

### Task 3: Ingestion wiring + provider tags — `codex`

`ingest.py` / `acquire.py` / `ingest_full_text.py` call `embed_pending_chunks`
post-chunk-write (counts into their payloads). `acquire.py` materialises provider
tags per the pinned normalisation table (insert-if-absent, provenance classes).
Done = eager-uniform + tag-materialisation test blocks. Scope: M. **Commit** after
Phase 2 verify green.

## Phase 3 — Grouping layer

### Task 4: Prompt pair — `lead` (prompt-bearing, lead-only)

`characterise_grouping_v1`: discovery prompt (intent-anchored, MECE-oriented,
affirmative evidence-grounded labels; id-keyed data records under explicit
data/instructions separation) + assignment prompt (fixed theme list, per-doc
`theme | unclustered`, decline-to-force-fit legitimised). Committed as constants
with the version string.

### Task 5: `GroupingBackend` — `codex`

Protocol (`discover`, `assign`, `mode`) + `OpenAIGroupingBackend` (strict structured
outputs; two models; per-call timeouts; the schemas from the contract) +
deterministic stub (groups by a metadata key; honours theme bounds). Done = backend
construction/failure tests + stub determinism. Scope: S–M.

### Task 6: `characterise.py` — `codex`

Coverage pass (deterministic SQL/python over columns + tag layer; base ladder; no
absence-claim fields) → grouping orchestration (budget check → discover → validate →
batched concurrent assign → per-batch validation/repair by the decision-4 case
table) → theme tags (`asserted_by="characterise"`) → characterisation row
(`grouping_provenance` required keys) → landscape summary (frozen shape). Honest
failure per decision 11. Done = the grouping + coverage + summary test blocks.
Scope: L (~350 lines). **Commit** after Phase 3 verify green.

## Phase 4 — Tracing + wiring

### Task 7: Langfuse tracing — `codex`

Wrap the two live backends per the pinned span/score spec; env-driven init; no-op
without keys (asserted); full I/O on spans. Scope: S–M.

### Task 8: Registry/harness/skeleton/helpers — `fast-worker`

- `plan.py`: `"characterise": {"requires": ["evidence_scope_id"]}`.
- `harness.py`: `embedding_backend` + `grouping_backend` params (stub defaults
  resolved inside `run_harness`), `HarnessState`, `_run_characterise` via
  `_run_scope_component`, node + conditional edge.
- `skeleton.py`: characterise after ingest_full_text; render the landscape summary;
  live backends iff `OPENAI_API_KEY` set; log baseline budget before live calls.
- `tests/helpers.py`: three tables in FK-safe delete order.
- `test_compile.py`: registry case. Scope: S–M. **Commit** with Phase 4.

## Phase 5 — Tests

### Task 9: Contract bulk — `fast-worker` (the contract's test list is the brief)

Everything in the contract's Tests section except the Task-10 cases: migration
roundtrip + 19 tables + constraint/FK rejections + `open_tags` gone · embed-pass
idempotency/batching/failure-isolation · eager-uniform across snapshot classes ·
coverage distributions vs hand-computed + bases + mixed provider shapes · grouping
happy path + counting invariant + edge scopes + `grouping_provenance` keys · tags
(both writers, provenance classes, accretion, `provider_fields` untouched) · failure
semantics · landscape payload shape · idempotent re-run · harness round-trip ·
`delete_project_data` · downstream untouched.

### Task 10: Judgment cases — `codex`

Validation/repair by case (no-LLM-call assertions for code-side fixes; residue-only
repair; repair exhaustion → honest failure; placeholder unrepresentable) · budget
maximum vs counting double · unit-derivation determinism + no-mean-pooling-path ·
socket-deny scoped around the characterise run (008's Postgres-connection lesson) ·
tracing no-op without keys · key-hygiene against captured output · injection-shaped
abstract and theme-name as inert data · prompt structure assertion (id-keyed data
records). Scope: L combined (~400 lines). **Commit** (tests).

## Phase 6 — Flow-backs + verification

### Task 11: Spec flow-backs — `lead`

components §5 ×2 (content-vs-artefact; thematic mechanism + vectorisation-with-gate
exception) + data-model tag-layer provenance clarification + `log.md` entries;
`make okf-validate` green.

### Task 12: `verification.md` + live manual run — `lead`

Per the contract's evidence list, including the live skeleton run with
`OPENAI_API_KEY` + `LANGFUSE_*` (dev instance): rendered landscape summary, themes
over the fixture corpus, embed/grouping counts, cost note, dev-instance trace
(span structure, prompt version, tokens); determinism evidence (two stub runs
byte-identical). **Commit** (flow-backs + verification).

### Step-8 obligations (after the review stack, in the PR)

`docs/deferred.md` per the contract's list (composition · very-large-corpus
grouping · grouping-quality + adversarial evals · TopicGPT refinement +
quotation-verified assignment · contextual retrieval/late chunking/exact-token ·
steer-point pause · dual-view · pgvector/retrieval · Bedrock swaps ·
provider-signal prompt enrichment · `group`-seam v2 lessons · tag consolidation ·
Langfuse follow-ons) · revise the existing `open_tags` entries · mark the class-1
vectorisation entry discharged-ahead-of-reader · point-in-time claims sweep.

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| OpenAI strict structured outputs with a per-run dynamic theme list | Assignment schema can't enumerate themes statically | Assignment output uses `theme_index: int` validated in code against the list (no dynamic enum needed); invalid index = invented-id case |
| Rate limits on the concurrent assignment wave | 429s mid-run | Concurrency cap 4 + bounded backoff inside the backend; batches are independent |
| Char-budget heuristic misestimates tokens on dense text | Oversized embed input rejected by API | Conservative 2,000-char target ≈ half the 8K window; API-side length error → that unit fails honestly and retries next pass |
| Stub grouper too clean to exercise repair paths | Repair logic untested | Task 10 uses purpose-built misbehaving doubles (invented ids, dups, missing) — the stub is for happy paths only |
| Langfuse SDK behaviour when keys absent | Suite egress attempts | Init guarded by explicit config check (not SDK auto-init); asserted by the no-keys test + socket-deny |
| Composite-FK targets missing unique constraints | Migration fails | Task 1 verifies as-built uniques first; adds referenced uniques within gate 1 if absent, noted in verification.md |
| Overton `topics` shape variance beyond string-or-list | Materialisation drops tags silently | Normalisation skips non-strings by rule (absent, not error) + mixed-shape fixture tests pin behaviour |
| Live discovery themes disappoint on fixture corpus | Verification looks weak | The bar is machinery correctness (contract); theme quality is the eval seam — note honestly in verification.md |
| Cost runaway on a mis-scoped run | Spend | Budget maximum checked pre-call; embed `max_chunks` guard; skeleton logs baseline budget before live calls |

## Open questions

None blocking — all design decisions fixed in the approved contract. Optional: exact
`langfuse` SDK pin verified at Task 1 against the user's instance versions.
