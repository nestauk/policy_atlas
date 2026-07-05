# Task contract: 009-characterise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted — awaiting contract approval.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: 0005 (embed seam / first
> product egress) — to be written at step 4.
> User-settled before drafting (2026-07-05): **whole characterise in one slice** (coverage
> + embed seam + clustering — no split) · **live provider embeddings** (this slice opens
> the runtime-egress/inference gate; stub/local-model alternatives considered and
> declined) · **no artefact/blocks at characterise** (option A: the single EB artefact is
> composed once at the run terminus — a later composition slice; characterise persists
> content, not presentation) · **intermediate user feedback matters** (v3.0
> steerability vs monolithic v2) — the landscape summary is designed as a relay surface,
> decision 8.

## Goal

Add **characterise** — the EB shallow terminus (component 5). After the cheap envelope
passes and full-text ingestion, characterise produces the **evidence landscape content**
for a scope: (a) **deterministic coverage distributions** over Tier-0 columns — the
hardest pattern grade, exactly reproducible, resting on the **screened base**,
flag-not-block — and (b) **topic-level thematic shape**: clustering over document
embeddings, labelled per cluster, honest about being the **softest grade** (an
interpretive shape, not a count — recomputable, never a deterministic fact).

Because clustering is the system's **first vector reader**, the 008 deferral comes due
here: **vectorisation lands eager-and-uniform at ingest** (EB components §4 — the
discipline restated by task 008's decision 1, now honoured). This is also, by user
decision, the slice that **opens the runtime-egress gate**: embeddings come from a live
provider (OpenAI `text-embedding-3-small`) behind an `EmbeddingBackend` seam — the first
product code path that reaches the outside world carrying project data. The spec accepts
this as a documented v3.0 posture (inference via the configured route, first pass OpenAI →
target Bedrock, behind the routing seam); the gate exists so it is opened deliberately,
here, with the controls named below.

Characterise writes **content, not presentation**: a run-scoped characterisation record +
topic/theme tags. It does **not** mint an artefact — EB produces **one** artefact,
composed at the run terminus by the orchestrator (capability.md); an intermediate
"landscape artefact" at characterise would violate that shape (user clarification,
2026-07-05). The artefact-composition step is a recorded seam.

## Deliverable

A PR on `task/009-characterise` → `dev` that:
- Ships `embeddings.py`: `EmbeddingBackend` (protocol), `OpenAIEmbeddingBackend` (live),
  `StubEmbeddingBackend` (deterministic, test/default), a named versioned **embedding
  profile**, and `embed_pending_chunks()` — the eager-and-uniform, idempotent embed pass.
- Adds three tables — `chunk_embedding`, `characterisation_result`, `source_tag` — via one
  Alembic migration (gated change 1; table count 16 → 19).
- Wires the embed pass into every ingestion path (upload ingest, acquire envelope
  snapshots, full-text ingest) and as an ensure-step at characterise start.
- Ships `characterise.py`: deterministic Tier-0 coverage distributions; document-level
  embedding derivation; seeded deterministic k-means (numpy); deterministic term-based
  cluster labels; tag persistence; the run-scoped characterisation row; the structured
  landscape summary returned into `component.completed`.
- Adds `openai` and `numpy` as runtime dependencies (gated change 2).
- Registers `"characterise"` in `COMPONENT_REGISTRY`; wires `_run_characterise`;
  `run_harness` gains optional `embedding_backend` (gated change 3).
- Extends `skeleton.py`: … appraise → ingest_full_text → **characterise**, rendering the
  landscape summary (the intermediate-feedback surface, decision 8).
- Spec clarification in EB components §5 (content vs artefact — decision 7) + `log.md`.
- Records the deferred seams in `docs/deferred.md`; updates `tests/helpers.py`
  delete order for the new tables.
- Passes `make verify` — all green, **deterministic and egress-free** (live path exercised
  manually, evidence in verification.md).

## Read first

- [EB components §5 — characterise](../../specs/capabilities/evidence-base/components.md)
  (coverage over Tier-0 columns, flag-not-block, screened base; topic clustering over
  embeddings, LLM-labelled lightly; labels persist as topic/theme tags; cluster grouping
  run-local) and **§4's embed discipline** (eager-and-uniform at ingest, lazy/on-demand
  rejected; this slice is the first vector reader task 008 deferred to).
- [EB capability](../../specs/capabilities/evidence-base/capability.md) — **one artefact**;
  orchestrator composes sections; cluster persistence rules (run-local execution state,
  never canonical, reflected in durable artefact blocks *at composition*); the
  landscape→synthesis mode-governed steer-point (decision 8's reader).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) +
  [system provenance-grounding § Patterns](../../specs/system/provenance-grounding.md) —
  the three pattern grades, never conflated: deterministic metadata patterns (hardest) vs
  thematic clustering (softest, interpretive); coverage claims carry their base.
- [System data-model](../../specs/system/data-model.md) — tag layer (item × tag,
  **typed**, open vocabulary, created by capabilities, never orchestrator); acquired
  substrate key = content hash × parse-profile × segmentation-policy × **embedding-model
  version**; whole-item organisation is columns + tags + scoping.
- [System execution-orchestration](../../specs/system/execution-orchestration.md) —
  Tier-0 retrieval contract (pgvector is the committed *retrieval* direction — **not**
  built here, decision 3); `search` is the only *agent-invocable* egress verb (embedding
  egress is mechanical infrastructure, decision 6); characterise realisation =
  "procedure + agent".
- [docs/deferred.md](../../deferred.md) — "vectorisation at the first vector reader"
  (class-1, discharged by this slice); chunk-volume-bias + token-budgeted re-chunking
  notes (008); the `open_tags` namespace-consolidation seam.
- [008-full-text contract](../008-full-text/contract.md) — pattern precedent (seam +
  gated `run_harness` parameter; decision structure).

**Code grounding (surveyed 2026-07-05):** 16 tables; no vector/embedding/pgvector
anything; no numpy/scikit; no tag table (`open_tags` is a JSONB column on
classification); chunks live in `chunk` (`sequence`, `content`, `content_hash`,
`locator JSONB`, `segmentation_policy`); chunk writes happen at exactly three sites
(upload ingest, acquire envelope, full-text ingest parent-side write loop);
`run_harness(conn, *, config, project_id, run_id, provider, search_backends=None,
document_fetcher=None)` is the injection precedent; Overton's retained `source` field
(geography/publisher) was kept *for characterise*; the walking skeleton's
artefact/block/annotation machinery exists but nothing here writes to it (decision 7).

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **Embedding backend: live OpenAI `text-embedding-3-small` behind an `EmbeddingBackend`
   seam (user decision, 2026-07-05) — the first product egress.** Protocol:
   `embed_texts(list[str]) -> list[list[float]]` + a `mode` marker (`"live"` | `"stub"`),
   mirroring `SearchBackend`/`DocumentFetcher`. `OpenAIEmbeddingBackend` (the `openai`
   SDK, `OPENAI_API_KEY` from the environment via the existing dotenv wiring) is the
   production implementation; `StubEmbeddingBackend` (deterministic content-hash-derived
   vectors, same dimensionality) keeps `make verify` egress-free and deterministic.
   `run_harness` defaults to the stub — live is wired explicitly (skeleton uses live when
   `OPENAI_API_KEY` is present, stub otherwise), so no test or default path ever leaves
   the machine. The **embedding profile** is named and versioned
   (`openai_text_embedding_3_small_v1`: provider, model, dimensions, distance convention)
   and stamped on every embedding row — the substrate key leg data-model reserves for
   embedding-model version. Bedrock is the target route; the seam is where it swaps in
   (recorded, with the routing-seam note). Alternatives declined at the gate:
   stub-only (defers the class-1 egress slice again for no product progress) and a local
   ML model (the dependency tier pyproject explicitly excludes, and a third embedding
   source the provider route would supersede).
2. **Eager-and-uniform vectorisation at ingest — absence of the row is the state.**
   `embed_pending_chunks(conn, embedder, ...)` embeds every chunk lacking a
   `chunk_embedding` row for the active profile (anti-join — the exact idempotency
   pattern the result tables use), in deterministic chunk order, batched. Called at the
   end of each of the three ingestion paths **and** as an ensure-step at characterise
   start (safety net for corpora ingested pre-009 — the mechanism is eager; the backfill
   is honest). Uniform means *all* snapshots: uploads, acquired envelopes
   (`abstract_only`) and full-text snapshots alike — no source class is second-class in
   retrieval later. Embed failures never fail ingestion: the pass returns honest counts
   (`embedded` / `already_embedded` / `failed`), failures stay pending (no status column
   — the missing row *is* retryable state) and are retried on the next pass.
   **Oversized chunks** (008's known heading-light giants) exceed the provider's token
   window: embed-side **windowing** splits an oversized chunk's text deterministically
   (character-budget heuristic with a generous safety margin — no tokenizer dependency;
   exact-token budgeting is recorded at the seam), embeds each window, and stores the
   **mean vector** as the chunk's embedding — canonical chunks are never touched
   (one parse, one segmentation per snapshot stands; 008's "token-budgeted re-chunking"
   lands as embed-side windowing, not chunk mutation).
3. **Embedding storage: `chunk_embedding` table, JSONB vector, no pgvector yet.**
   One row per (chunk × embedding profile): `chunk_id` FK, `embedding_profile`,
   `vector JSONB` (float array), `created_at`; unique `(chunk_id, embedding_profile)`.
   Nothing in this slice does similarity search — clustering loads the scope's vectors
   into memory — so a pgvector column/index would be an unread index behind a dependency
   + extension + infra decision. pgvector arrives with the `retrieve` slice (the Tier-0
   retrieval contract commits to it there); keying by profile means that migration is
   additive. Profile-keyed rows also mean a future model/route change re-embeds under a
   new profile without touching history.
4. **Clustering: seeded deterministic k-means over document-level embeddings, run-local.**
   Document vector = mean of the document's chunk vectors from its **best available
   snapshot** (full-text snapshot when ingested, else envelope — mirrors "grounding and
   coverage see which a finding rests on"; the doc vector records which basis it used).
   Input set = the scope's **screened-in** documents (the landscape rests on the screened
   base). k-means in numpy, fixed seed, deterministic init (k-means++ with seeded RNG),
   k from a stated heuristic (`min(ceil(sqrt(n/2)), cap)`, cap a plan detail; degenerate
   smalls handled honestly: n < a floor → one cluster, counted). Cluster assignments are
   **run-local** (persisted only in this run's `characterisation_result` row — resume
   checkpoint, recomputable, superseded by the next run; never a canonical corpus fact,
   per capability.md). scikit-learn/HDBSCAN-class upgrades are a recorded seam if k-means
   proves too crude on real embeddings — entered via evals, not by default.
5. **Cluster labels: deterministic term-based in v3.0; LLM labelling is the recorded
   seam.** Labels derive from member titles/abstracts by a deterministic salience
   heuristic (e.g. top TF terms against the corpus, stopworded) — honest, reproducible,
   and meaningful over real semantic clusters. The spec's "lightly LLM-labelled" is the
   LLM-generation seam (like screen/classify stubs): it needs the inference-route
   *generation* gate, prompt-bearing work, and non-deterministic-output handling this
   slice doesn't otherwise carry. Embeddings ≠ generation: opening the egress gate for
   vectors does not silently open it for prompts. Labels persist as **topic/theme tags**
   (decision 6 note: tag writes are idempotent) on member documents via `source_tag`;
   the run's label→cluster mapping lives in the characterisation row.
6. **Egress governance: mechanical infrastructure, telemetry-plane — plus first-egress
   controls.** Embedding calls are not agent-invocable (`search` stays the only
   agent-invocable egress verb); like 008's fetch posture they are mechanical execution
   under the governed run: structured telemetry per batch + run-record summary counts
   (chunks embedded, batches, failures) in `component.completed` — no per-chunk
   governance events. First-egress controls, named: API key **only** from the
   environment (never a parameter default, never logged, never committed — `.env` is
   already gitignored); explicit request timeouts; bounded retry/backoff on transient
   failures; batch size capped; a **per-run embed budget guard** (max chunks per pass, a
   generous configurable cap — over it → the pass stops with honest `failed`/pending
   counts and a loud log, never a silent partial that looks complete; runaway-cost
   protection). What leaves the machine is chunk text (project corpus content) to the
   configured provider — the documented, spec-accepted v3.0 inference-route posture;
   embeddings return vectors only and interpret nothing (no instruction-following
   surface, so the injection posture is unchanged).
7. **Characterise writes content, not presentation (user decision, 2026-07-05).**
   Durable output per run: one `characterisation_result` row (scope, run, embedding
   profile, `coverage JSONB`, `clusters JSONB` — labels, sizes, member ids, top terms,
   doc-vector text-basis mix) + `source_tag` rows. **No artefact, no blocks**: EB
   produces one artefact, composed at the run terminus by the orchestrator; the
   **EB artefact-composition step** (create-or-supersede the single artefact, write
   landscape blocks from this content, summary/key-findings conventions, artefact
   versioning) is a **recorded seam** — the natural next-or-soon slice. Spec flow-back
   riding this contract: one clarifying line in components §5 ("characterise produces
   the landscape *content*; the single EB artefact is composed once at the run
   terminus") + `log.md` entry.
8. **The landscape summary is the intermediate-feedback surface (user steer,
   2026-07-05).** v3.0's steerability principle vs monolithic v2 means each stage should
   have something to say to the user. Characterise's `component.completed` payload
   carries a structured **landscape summary** designed for relay, not just counts:
   coverage distributions (with their base), cluster labels + sizes, and honest flags
   (full-text coverage rate, Unknown-classification share, share failed embedding,
   degenerate-clustering fallbacks). The skeleton renders it human-readably. This is
   exactly what the spec's mode-governed **landscape→synthesis steer-point** reads when
   steering modes land — that pause machinery is a recorded seam (plan-as-object
   territory), but the content it will relay ships now. No new event types; the payload
   is the surface.
9. **Coverage pass: deterministic distributions over what Tier-0 actually has.**
   Over the scope's screened-in set (with the not-relevant / screen-failed / unscreened
   counts alongside, so the base ladder is visible): `origin` · `text_basis` /
   `full_text_status` (+ failure reasons) · `primary_evidence_type` (evidence vs
   Non-evidence vs Unknown, honest about stub-classification reality) · quality tier ×
   `rubric_version` · `screen_basis` + confidence bands · year · language · backend ·
   publisher/geography where the envelope carries it (Overton `source` fields, retained
   in 007 *for this component*). The spec's fuller list (study geography, population)
   lives in text, not Tier-0 metadata — not fabricated; recorded as arriving with
   extraction. Distributions are computed by deterministic SQL/python (the lookup
   discipline: re-running the query *is* the verification), each carrying `base:
   "screened"` explicitly. **Flag-not-block** — nothing is excluded from coverage for
   being below any bar. **Dual-view coverage is a recorded seam**: no source/evidence
   policy object exists in v3.0 (verified), so the spec's "when the user has supplied a
   policy" condition never fires; single overall view ships.
10. **Tag layer lands minimally: `source_tag`.** Item × tag × type
    (`project_source_snapshot_id` FK, `tag`, `tag_type` — CHECK: `topic_theme` for now,
    additive later — `created_by_run_id`, `created_at`; unique `(pss, tag_type, tag)`).
    Written by characterise (the spec's rule: tags are created by capabilities that read
    documents, never by the orchestrator); insert-if-absent so re-runs accrete without
    duplicating; namespace consolidation stays the recorded orchestrator seam. classify's
    `open_tags` JSONB column is untouched — migrating it into this table is part of the
    LLM-classify seam, not this slice.
11. **Failure semantics: clustering requires full embedding coverage of its input.**
    After the ensure-pass, if any screened-in document still lacks a document vector
    (provider outage, budget guard tripped), characterise **fails loudly with honest
    counts** rather than clustering a biased subset (partial vectorisation biasing the
    shape is exactly what eager-uniform exists to prevent — lazy/on-demand stays
    rejected). Coverage distributions (metadata-only, no vectors needed) are still
    computed and reported in the failure payload — the deterministic half degrades
    honestly, the interpretive half refuses to fake it. Re-run retries pending
    embeddings idempotently.
12. **Component wiring mirrors 004–008.** `"characterise"` in `COMPONENT_REGISTRY`
    requiring `evidence_scope_id`; context dataclass `(scope_id, intent, context)`;
    `_run_characterise` via `_run_scope_component`; conditional-edge wiring;
    `component.started`/`completed`/`failed`. Counting invariant:
    `screened_in == clustered + <honest failure buckets>`, embed pass reports
    `embedded + already_embedded + failed == pending_at_start`, and the
    characterisation row is unique per `(scope, run)`. Realisation is "procedure"
    end-to-end in v3.0 (the "agent" half of "procedure + agent" arrives with LLM
    labelling).

### Schema

**Gated change 1 — three new tables** (one migration; table count 16 → 19):

```
chunk_embedding          chunk_embedding_id PK · chunk_id FK→chunk · embedding_profile TEXT
                         · vector JSONB · created_at
                         UNIQUE (chunk_id, embedding_profile)

characterisation_result  characterisation_id PK · evidence_scope_id FK · run_id FK
                         · embedding_profile TEXT · coverage JSONB · clusters JSONB
                         · created_at
                         UNIQUE (evidence_scope_id, run_id)      -- run-local by design

source_tag               source_tag_id PK · project_source_snapshot_id FK · tag TEXT
                         · tag_type TEXT CHECK (tag_type IN ('topic_theme'))
                         · created_by_run_id FK→runs (nullable) · created_at
                         UNIQUE (project_source_snapshot_id, tag_type, tag)
```

Downgrade drops the tables. No existing table changes. `tests/helpers.py`
`delete_project_data` gains the three tables in FK-safe order.

### Python

- **`embeddings.py`** — `EmbeddingBackend` protocol · `OpenAIEmbeddingBackend` ·
  `StubEmbeddingBackend` · `EMBEDDING_PROFILE` constant(s) · `embed_pending_chunks(conn,
  *, embedder, project_id, run_id, batch_size=…, max_chunks=…) -> dict` (counts) ·
  deterministic windowing for oversized chunks.
- **`characterise.py`** — `CharacteriseContext` · `characterise_scope(conn, *,
  project_id, run_id, context, embedder) -> dict` (ensure-embedded → coverage →
  document vectors → k-means → labels → tags → characterisation row → landscape
  summary) · deterministic k-means + labelling helpers.
- **`ingest.py` / `acquire.py` / `ingest_full_text.py`** — call `embed_pending_chunks`
  after their chunk writes (counts folded into their `component.completed` payloads).
- **`plan.py`** — `"characterise": {"requires": ["evidence_scope_id"]}`.
- **`harness.py`** — `_run_characterise`; `embedding_backend: EmbeddingBackend | None =
  None` on `run_harness` (defaults to `StubEmbeddingBackend()` — no default egress);
  threaded through `HarnessState`.
- **`skeleton.py`** — chain extended with characterise; renders the landscape summary;
  uses the live backend iff `OPENAI_API_KEY` is set.

### Tests (`tests/test_characterise.py` + `tests/test_embeddings.py`)

- Migration roundtrip; table count 19; unique constraints and the `tag_type` CHECK
  reject duplicates/invalid rows.
- Embed pass: anti-join idempotency (second call all `already_embedded`); deterministic
  chunk order; batching; failure isolation (a failing embedder double → honest `failed`
  counts, ingestion still succeeds, retry embeds the stragglers); budget guard trips
  loudly; oversized-chunk windowing (windows deterministic, mean vector stored, canonical
  chunk untouched); profile stamped on every row; stub vectors deterministic across
  processes (no hash randomisation dependency).
- Eager-uniform: after upload + acquire + full-text ingest, every chunk of every
  snapshot class has an embedding row for the profile.
- Coverage: distributions over a seeded corpus match hand-computed values; base counts
  (screened-in vs not-relevant vs failed vs unscreened) present; every distribution
  carries its base label; flag-not-block (below-bar/Unknown rows counted, never dropped).
- Clustering: deterministic across runs and worker/process variation (fixed seed);
  document vector uses full-text snapshot when present else envelope (and records which);
  small-n degenerate path honest; assignments land only in the characterisation row
  (no canonical cluster state anywhere).
- Labels/tags: deterministic labels; `source_tag` rows for members; re-run accretes
  without duplicates; created only by characterise (nothing else writes tags).
- Failure semantics: missing embeddings after ensure-pass → `component.failed`-style
  honest outcome with coverage still reported (decision 11); counting invariants hold.
- Landscape summary payload: structure asserted (coverage + clusters + flags + bases);
  no new event types; skeleton renders it.
- **Zero-egress guard extended**: `make verify` uses stubs only; socket-deny test covers
  an end-to-end characterise run (007/008 precedent — the live path is never exercised
  by the suite); `OpenAIEmbeddingBackend` constructed without a key fails loudly and
  early; the key never appears in logs/events (asserted against captured output).
- Idempotency/re-run: second characterise run → new characterisation row for the new
  run, tags accreted not duplicated, embeddings all `already_embedded`.
- Harness round-trip: `Plan(component="characterise")` → characterisation row + tags in
  DB; `test_compile.py` gains the registry case (valid with scope id, rejected without).
- `delete_project_data` clean with all three new tables populated.
- Downstream untouched: screen/classify/appraise/ingest outputs identical before/after
  (they don't read embeddings).

### Out of scope

- **EB artefact composition** (the single artefact, landscape blocks, summary /
  key-findings conventions, supersede-by-rerun + lock-on-advance versioning) — its own
  slice; recorded seam (decision 7).
- **`retrieve` / pgvector / hybrid retrieval** — the committed direction for the
  retrieval slice; embedding rows are ready for it (decision 3). Chunk-volume-bias
  controls stay recorded there.
- **LLM cluster labelling** (decision 5) and the **LLM screen/classify/grounding
  tools** — the inference-*generation* gate is not opened by this slice.
- **Steering modes / the landscape→synthesis steer-point pause** — plan-as-object
  machinery; the payload it will relay ships now (decision 8).
- **Dual-view coverage** — needs the source/evidence policy object (decision 9).
- **Bedrock embedding route** — the seam swap; recorded with the routing-seam note.
- **Exact-token budgeting (tiktoken-class) and semantic re-chunking** — recorded at the
  embed seam; v3.0 windowing is a char-budget heuristic (decision 2).
- **Tag namespace consolidation / `open_tags` migration** (decisions 5, 10).
- **`select` and everything deeper** — subsequent slices.
- **Backfill tooling for large pre-existing corpora** — the ensure-pass covers v3.0
  realities; a bulk backfill command is not needed until there is production data.

## Constraints & approval gates

**Four gated changes (approval needed at this gate):**

1. **Schema** — three new tables (`chunk_embedding` · `characterisation_result` ·
   `source_tag`), one migration, no existing-table changes.
2. **Dependencies** — `openai` (the provider SDK; also the eventual LLM-seam client) and
   `numpy` (vector math for k-means/means; deliberately *not* scikit-learn/scipy — the
   smallest step that makes 1536-dim math tractable).
3. **Public interface** — `run_harness` optional `embedding_backend` parameter + the
   `"characterise"` registry entry (007/008 precedent).
4. **Runtime egress** — `OpenAIEmbeddingBackend` sends chunk text to OpenAI's embeddings
   API on the production path. **The first product egress.** Controls in decision 6;
   `make verify` and all defaults remain egress-free; live is opt-in by explicit wiring
   + environment key.

Plus one spec clarification (components §5, decision 7) approved with this contract.

**Explicitly not crossed:** no LLM/generation calls, no auth/tenancy change, no CI
change, no pgvector/extension, no artefact/block writes, no changes to existing tables.

## Public / private boundary

- **Credentials**: `OPENAI_API_KEY` environment-only; never committed, logged, or echoed
  into events/verification artifacts (test-asserted). `.env` stays gitignored.
- **Chunk text leaves the machine on the live path** — to the configured provider only,
  under the spec-accepted v3.0 inference-route posture. Fixture-corpus content is
  openly licensed (008's licence guard), so even live verification runs send only
  committable text.
- Committed artifacts (profile names, table/column names, deterministic labels over
  fixture corpora, verification counts) are all public-safe. No recorded live vectors
  are committed in this slice (stub vectors cover the suite; if the plan finds a test
  that genuinely needs real vectors, committing recorded ones is a plan-gate question).

## Model route

**Embeddings only**: OpenAI `text-embedding-3-small` under the approved-controls posture
(→ Bedrock behind the `EmbeddingBackend` seam when the route lands). **No generation, no
prompts** — there is no prompt-bearing surface in this slice (cluster labels are
deterministic; decision 5). The embedding profile string is the model-version provenance
on every row.

## Disciplines binding this slice

- **Eager and uniform** — every ingested chunk embeds under the active profile; absence
  is pending, never a silent skip; lazy/on-demand stays rejected (partial-coverage
  clustering refused, decision 11).
- **Pattern grades never conflated** — coverage = metadata-grounded facts with an
  explicit base; clusters = interpretive shape, run-local, honestly soft; the summary
  carries both with their grades visible.
- **Run-local means run-local** — cluster assignments live only in the run's
  characterisation row; nothing promotes them to canonical corpus state.
- **Flag, don't drop** — coverage counts everything on the screened base;
  Unknown/Non-evidence/below-bar rows are present-and-visible, never excluded.
- **Honest absence** — every distribution and the summary carry the base ladder counts;
  population/geography absence from Tier-0 is stated, not papered over.
- **Snapshots and chunks immutable** — embedding rows and windows attach *alongside*;
  no chunk mutation, no re-segmentation (one parse, one segmentation stands).
- **Deterministic where claimed** — stub vectors, k-means, labels, coverage: same input,
  same output, test-enforced; live vectors are provider-dependent and never inside
  `make verify`.
- **No prompt-bearing work** rides this slice (decision 5 keeps generation out).

## Stop conditions

- Any gated change (schema · deps · public interface · **egress**) not yet approved, or
  any change beyond the gated items (e.g. an existing-table change, pgvector, a second
  provider).
- Any *default or test* code path would perform network I/O (live is explicit-wiring
  only).
- The one-artefact shape is threatened mid-build (something needs blocks/artefact writes
  after all) — halt, don't improvise composition.
- Clustering over real embeddings proves the k-means design inadequate *for the
  machinery to function* (not merely imperfect clusters — that's the eval seam) — halt
  and re-open decision 4 with evidence.
- Scope would grow past the contract (LLM labels, retrieval, composition, policy
  object, select).
- `make verify` red with unclear root cause; or the turn/token budget is spent.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green, deterministic, zero egress
  (socket-deny covers the characterise round-trip).
- **One manual live check** (evidence in verification.md): skeleton end-to-end with
  `OPENAI_API_KEY` set against the fixture corpus — real embeddings, real clusters,
  landscape summary rendered; per-run token/chunk counts and cost note recorded; key
  absent from all captured output.
- Deterministic vs AI eval: all suite checks are deterministic tests. Cluster *quality*
  on real embeddings is eval territory (the labelling/clustering upgrade seams); this
  slice's bar is machinery correctness + honest output, not cluster goodness.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny + key-hygiene test results named.
- Migration roundtrip clean; table count 19.
- Counting-invariant + idempotency + eager-uniform coverage test results named.
- The live-run evidence (manual check above): landscape summary as rendered, cluster
  labels + sizes over the fixture corpus, embed counts/batches, honest cost/token note.
- Determinism evidence: two stub runs byte-identical on the characterisation row.
- Public-safety confirmation (no credentials anywhere; live run sent openly-licensed
  fixture text only).
- Deferred seams recorded in `docs/deferred.md` (EB artefact composition · LLM cluster
  labelling · steering-mode steer-point reading the landscape payload · dual-view
  coverage behind the policy object · pgvector + retrieval · Bedrock route swap ·
  exact-token budgeting · clustering-algorithm upgrade via evals · tag namespace
  consolidation) and the class-1 "vectorisation at first reader" entry updated to
  discharged.
- Diff summary (any bulky fixture data excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — opens the runtime-egress gate (first product egress, credentials, project
data leaving the machine), three new tables, two new dependencies, a public-interface
addition. ADR 0005 (embed seam / first egress) due at step 4; contract- and plan-stage
adversarial reviews standard.

Review focus:
- **Security (the headline lane)**: key handling (env-only, never logged/committed);
  egress boundaries (stub default, live explicit; socket-deny in suite); what text
  leaves and under what posture; budget guard; timeout/retry bounds; no
  instruction-following surface in the embed path.
- **Correctness**: anti-join idempotency; eager-uniform coverage across all three
  ingestion paths; windowing determinism; k-means/label determinism; counting
  invariants; decision-11 refusal on partial coverage.
- **Provenance/honesty**: pattern grades kept distinct; bases on every claim; run-local
  clusters not leaking into canonical state; profile stamped everywhere.
- **Schema**: migration roundtrip; FK-safe deletes; unique constraints.
- **Scope**: no generation calls, no composition/blocks, no pgvector, no select.
