# Task contract: 009-characterise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted, rev 6 — rev 4 accepted by user 2026-07-06 ("seems fine");
> awaiting final sign-off with the 4.1 + 5 amendments and the rev-6 adversarial
> adjudication.
> Rev 6 (adversarial adjudication, 2026-07-06): Codex review of rev 4.1 returned
> **15 findings (2 blockers · 11 majors · 2 minors) — 12 adopted, 2 adopted-in-part,
> 1 rejected with rationale** (§ Contract-stage adversarial review). Blockers: the
> generation interface cannot ride `InferenceProvider.complete(prompt)->str` → a
> dedicated **`GroupingBackend` seam** + `run_harness` parameter (grows gate 3 —
> **flagged for the human at re-read**); the new tables lacked the repo's
> project-scoped composite-FK discipline → `project_id` + composite FKs added.
> Notable adoptions: per-batch **discard-and-retry-once** replaces residue-repair
> (simpler semantics); call budget restated as baseline vs enforced max; explicit
> **live opt-in flag** (env key alone never flips a path to egress); theme names
> treated as untrusted model output (length/charset constraints); no gap/absence
> *claims* in 009 output (distributions only — gap machinery stays at its seam);
> empty/small-n behaviour specified; provider-field normalisation named a plan
> requirement; `grouping_provenance JSONB` replaces the two scalar columns.
> Rejected: "tags must be run-scoped or not written" — components.md §5 explicitly
> sanctions label-persist-as-tags while the *grouping* stays run-local; the line is
> now stated in decision 10 (adopted-in-part as a clarification).
> Rev 5 (user steer, 2026-07-06 — "the whole point of characterise is understanding
> the corpus landscape; why not use the provider tags here?"): provider-topic tag
> materialisation pulled **in-slice**. `source_tag` gains **`asserted_by`** (assertion
> provenance; unique key includes it); acquire materialises provider topical
> assertions as tags (OpenAlex topics/SDGs; Overton
> topics/classifications/sdgcategories/`llm_document_theme`) with provider /
> provider-LLM / own-capability provenance classes distinguishable; coverage
> aggregates the tag layer grouped by `(tag_type, asserted_by)` instead of parsing
> backend JSONB twice. Spec flow-back (user as author): data-model's "nothing hangs
> off a tag" clarified to govern the tag *label* — the assignment row carries
> provenance, like every other assertion in the system.
> Rev 4.1 (user steer, 2026-07-06): provider-asserted topical signals (OpenAlex
> topics/SDGs; Overton topics/classifications/`llm_document_theme` — retained in 007
> for exactly this component) join the **coverage pass** as deterministic,
> provider-asserted-labelled distributions (decision 9); **tag materialisation and
> prompt enrichment recorded as seams** with provenance constraints (provider
> assertions never mix into `topic_theme`; a distinct tag type carries them when
> scoping/retrieval reads tags).
> Rev 4 (user question, 2026-07-06): the rev-3 single grouping call split into the
> **two-stage shape from the start** — discover (one judgment-model call, whole
> corpus) → assign (batched cheap-model calls, concurrent, against the fixed theme
> list) — after the user asked whether deferring the split bought anything. It
> didn't: assignment-vs-fixed-list is the easier task (equal-or-better quality at
> 20–200 docs), batches kill long-output degradation, repair becomes per-batch and
> targeted, latency is a wash with right-sized models per stage, and the
> large-corpus seam shrinks to discovery-sampling only. Also rev 4: BERTopic
> rejection wording corrected — the operative reason is the gate-excluded dependency
> stack (torch via sentence-transformers, umap/numba), not framework-ness per se.
> Rev 2 (user challenge, 2026-07-05): rev 1's numpy k-means judged subpar-by-default
> for a heterogeneous policy corpus; replaced with HDBSCAN + honest noise bucket +
> c-TF-IDF labels (scikit-learn) after a state-of-the-art sweep (last30days) and a v2
> theming reconnaissance — see § Clustering research grounding.
> Rev 3 (user decisions, 2026-07-06): algorithmic clustering dropped entirely —
> **thematic grouping is one bounded LLM call** (HDBSCAN judged degenerate-by-default
> at 10s-of-docs scopes; agglomerative judged tuning-fiddly with term-soup labels; the
> LLM aligns best with human topic judgment and generation was always coming — "don't
> hack together something needing constant tweaking"). **User explicitly confirmed the
> two gate expansions:** (1) the generation gate opens in 009 (first product prompt,
> lead-authored, versioned) and (2) the injection posture recorded at 007/008 comes
> due (first slice where third-party corpus text enters an LLM prompt). Also rev 3:
> **`chunk_embedding` stays chunk-grain at ingest** (user product call: certain future
> substrate for retrieval/synthesis; landing it with the egress gate beats a third
> egress slice — a recorded, approved exception to 008's vectorise-at-first-reader
> line, since nothing in 009 reads chunk vectors) · greenfield acknowledged (no
> backfill framing — nothing is deployed) · scikit-learn dropped from the dependency
> gate (no algorithm to ship).
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: 0005 (embed + generation
> seams / first product egress / injection posture) — to be written at step 4.
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
flag-not-block — and (b) **topic-level thematic shape**: an LLM discovers the scope's
themes from all titles + abstracts (one call), then assigns every screened-in document
against that fixed theme list (batched concurrent calls; a document may land
explicitly in none) — a **bounded call budget with an enforced maximum**, honest about being
the **softest grade** (an interpretive shape, not a count — recomputable, never a
deterministic fact, which is exactly the epistemic class an LLM grouping belongs to).

By user decision this is the slice that **opens the runtime-egress gate on both
fronts**: **embeddings** (OpenAI `text-embedding-3-small` behind an `EmbeddingBackend`
seam — eager-and-uniform chunk-grain vectorisation at ingest, landed ahead of its first
reader as an approved exception, because it is certain retrieval/synthesis substrate
and this is the gate-opening slice) and **generation** (the grouping call — the repo's
first product prompt and the first time third-party corpus text enters an LLM prompt,
so the recorded injection posture comes due here). The spec accepts live egress as the
documented v3.0 posture (inference via the configured route, first pass OpenAI → target
Bedrock, behind the routing seam); the gates exist so it is opened deliberately, here,
with the controls named below. `make verify` remains deterministic and egress-free
(stub embedder + stub grouper); live paths are explicit wiring + manual evidence.

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
  snapshots, full-text ingest) — no characterise-time ensure-step (greenfield,
  decision 2; deliverable/decision contradiction was adversarial finding 3).
- Ships `characterise.py`: deterministic Tier-0 coverage distributions; the two-stage
  LLM grouping — discover (one call) → assign (batched, concurrent, fixed theme list)
  — with lead-authored co-versioned prompts, schema-constrained outputs, code-enforced
  per-batch exhaustive assignment, targeted per-batch repair, and an honest
  `unclustered` bucket; a deterministic stub grouper for the suite; tag persistence;
  the run-scoped characterisation row; the structured landscape summary returned into
  `component.completed`.
- Ships the `GroupingBackend` seam (protocol + `OpenAIGroupingBackend` +
  deterministic stub; adversarial finding 1) — the structured-generation path; stub
  remains the default (gated changes 3 + 4).
- Adds `openai` as a runtime dependency (gated change 2).
- Registers `"characterise"` in `COMPONENT_REGISTRY`; wires `_run_characterise`;
  `run_harness` gains optional `embedding_backend` (gated change 3).
- Extends `skeleton.py`: … appraise → ingest_full_text → **characterise**, rendering the
  landscape summary (the intermediate-feedback surface, decision 8).
- The three spec flow-backs + `log.md` entries (matching the gates section exactly —
  adversarial finding 15): components §5 content-vs-artefact (decision 7); components
  §5 thematic mechanism + vectorisation-with-gate exception (decisions 4, 2);
  data-model tag-layer assertion provenance (decision 10).
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
   end of each of the three ingestion paths (greenfield — rev 3 drops the
   characterise-time ensure/backfill: nothing is deployed, characterise reads no
   vectors, and the anti-join makes any later ingest run the natural retry). **Rev 3
   scope note (user decision, 2026-07-06): chunk-grain embedding ships in this slice
   ahead of its first reader** — an approved exception to 008's
   vectorise-at-first-reader line (spec log entry rides this contract): chunk vectors
   are certain retrieval/synthesis substrate, and landing them with the egress gate
   beats relitigating egress in a third slice. Uniform means *all* snapshots: uploads,
   acquired envelopes
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
   Nothing in this slice reads the vectors at all (rev 3 — the rows are landed
   substrate for retrieval/synthesis, decision 2's approved exception), so a pgvector
   column/index would be an unread index behind a dependency + extension + infra
   decision. pgvector arrives with the `retrieve` slice — the vectors' actual first
   reader (the Tier-0 retrieval contract commits to it there); keying by profile means
   that migration is additive. Profile-keyed rows also mean a future model/route change re-embeds under a
   new profile without touching history.
4. **Thematic grouping: two-stage LLM — discover, then batched parallel assignment —
   code-owned validation and repair (rev 4; TopicGPT's shape at every corpus size).**
   Rev 2's HDBSCAN fell to the corpus-size check (density estimation is
   degenerate-by-default at 10s-of-docs scopes); agglomerative survives technically
   but needs per-corpus threshold tuning and yields term-soup labels — the "hack
   needing constant tweaking" the user rejected. The LLM route aligns best with human
   topic judgment (TopicGPT-class evidence) and fits the spec's own epistemics for
   clusters (interpretive, recomputable, never a deterministic fact). Rev 4 (user
   question, 2026-07-06) splits the rev-3 single call into the two-stage shape from
   the start — no drawback at 20–200 docs, several concrete wins (§ research
   grounding, rev 4 note). Design — every v2 operational defect structurally closed:
   - **Stage 1 — discover** (one call, judgment-heavy model): all screened-in
     documents' `(id, title, abstract)` — ~30K tokens at 100 docs — with the scope's
     intent; output schema-constrained to a **theme set** (name + one-line
     description, count bounded, e.g. 3–12). Discovery always sees the whole corpus;
     a sampling step at very large n is the only remaining scale seam.
   - **Stage 2 — assign** (batched, cheap classification model, batches run
     concurrently): each batch of ~25–50 docs is assigned against the **fixed theme
     list** from stage 1; output schema-constrained to `(doc_id, theme |
     "unclustered")` per doc. Assignment against a fixed list is an easier task than
     joint discovery+assignment, and bounded batch outputs avoid long-structured-
     output degradation — quality is equal or better at our sizes, and the same
     design runs unchanged at 2,000 docs. **Call budget (adversarial finding 7):
     baseline `1 + ceil(n/batch)`; enforced maximum
     `(1 + discovery_retry_cap) + ceil(n/batch) × (1 + assignment_retry_cap)`**
     (caps a plan detail, small) — the maximum is checked before any live call; the
     baseline is known before the run starts.
   - **Validation is code, not model trust — per batch, discard-and-retry
     (adversarial finding 9, adopted simplification):** schema conformance is
     provider-enforced (strict structured outputs); **exhaustiveness is not
     schema-expressible**, so code asserts every batch id assigned exactly once, no
     invented ids. A violating batch's output is **discarded whole and the batch
     retried once** — a batch persists only when fully valid, so "residue" semantics
     (undefined for invented-id or duplicate-conflict outputs) never arise; an
     invalid discovery output (theme count out of bounds, malformed) is likewise
     discarded and retried once. Still failing → the component fails honestly
     (decision 11); never silent drops, never a placeholder theme (v2's "General
     Theme" collapse is unrepresentable — a degenerate outcome is a flagged failure
     state, not fake success).
   - **Empty and small scopes (adversarial finding 8):** `n = 0` → grouping is
     skipped honestly (coverage still reported; summary flags `empty_scope`); small
     `n` → theme-count bounds become `1..min(n, max)`; `n < batch` is one batch.
     Each is a tested path, not an assumed one.
   - **`unclustered` is a first-class, counted outcome** — the model may decline to
     force-fit a document; those docs stay fully eligible downstream and form their
     own stratum when `select` lands. Counting invariant:
     `screened_in == grouped + unclustered` (+ honest failure states).
   - **No new orchestration dependency:** both stages are plain procedure code
     against the existing inference seam — the OpenAI SDK covers structured calls
     natively, and the concurrency is a bounded `gather` over assignment batches.
     (v2's LangChain constructs were thin wrappers over exactly this; its defects —
     dead critique stage, batch-size-1 mapping, silent drops between stages — were
     design flaws the validation-and-repair loop closes, not framework properties.)
   - **Grouping is run-local** (persisted only in this run's `characterisation_result`
     row — resume checkpoint, recomputable, superseded by the next run; never a
     canonical corpus fact, per capability.md). Re-runs may group differently — the
     spec's softest grade says exactly this; the run records prompt version, model
     ids and settings so any grouping is attributable.
   - **Test seam:** a deterministic **stub grouper** (the `_stub_screen`/`_stub_classify`
     pattern — stub discover + stub assign) keeps `make verify` egress-free and
     exercises all downstream machinery (batching, validation, repair routing, tags,
     row, summary, events); the live path is manual evidence.
5. **The grouping prompts are the repo's first product prompts — prompt-bearing,
   lead-authored, versioned (rev 3; rev 4: a co-versioned pair).** The discovery and
   assignment prompts version together as `characterise_grouping_v1`, recorded on the
   characterisation row and in the event payload (the appraisal `rubric_version`
   discipline applied to prompts). It carries v2's genuinely good
   prompt discipline where it belongs: **intent-anchored** (themes must serve the
   scope's stated intent), **MECE-oriented** (collectively exhaustive is *enforced in
   code*, not prompt-hoped; mutually exclusive and meaningful granularity are prompt
   discipline), **affirmative, evidence-grounded labels** (derived only from supplied
   text, no editorialising). Theme names double as the labels — no separate labelling
   mechanism exists (rev 2's c-TF-IDF is gone with the algorithm) — and persist as
   **topic/theme tags** (decision 6 note: tag writes are idempotent) on member
   documents via `source_tag`; the run's theme→members mapping lives in the
   characterisation row. Prompt-bearing work is lead-only per AGENTS.md — the prompt
   is written by the lead, never delegated.
6. **Egress governance + the injection posture coming due (rev 3).** Neither egress
   path is agent-invocable (`search` stays the only agent-invocable egress verb); like
   008's fetch posture both are mechanical execution under the governed run: structured
   telemetry per call/batch + run-record summary counts in `component.completed` — no
   per-chunk or per-document governance events. First-egress controls, named: API key
   **only** from the environment (never a parameter default, never logged, never
   committed — `.env` is already gitignored; asserted absent from all captured output);
   explicit request timeouts; bounded retry/backoff on transient failures; batch size
   capped; **per-run budget guards on both paths** (max chunks per embed pass; the
   grouping budget has a known baseline `1 + ceil(n/batch)` and an **enforced
   maximum** `(1 + discovery_retry_cap) + ceil(n/batch) × (1 + assignment_retry_cap)`
   checked before any live call (finding 7) — over any cap → stop with honest counts
   and a loud log, never a silent partial that looks complete). What
   leaves the machine is corpus text (chunk text on the embed path; titles + abstracts
   on the grouping path) to the configured provider — the documented, spec-accepted
   v3.0 inference-route posture. **Injection posture (user-confirmed): this is the
   first slice where third-party corpus text flows *into* an LLM prompt** — including
   provider-LLM-written Overton descriptions — the seam 007/008 pre-registered
   ("enforcement lands with the LLM seams that read them"). Mitigations, structural
   where possible: document content is passed as **data records keyed by id** under an
   explicit data/instructions separation in the prompt; the output channel is
   **schema-constrained to theme names + id assignments** (no tools, no free text
   acting on the world — a hijacked model can at worst mis-group or mis-label, which
   validation and the softest-grade framing bound); exhaustiveness and id validity
   are **enforced in code after the call**; embeddings interpret nothing (vectors
   back only). **Theme names and descriptions are themselves untrusted model output
   (adversarial finding 10, adopted):** they flow onward into the landscape summary
   and `source_tag` rows, so they carry code-enforced length and character
   constraints, are rendered/stored as data (never interpolated into anything
   executable), and the standing rule is recorded for future seams: **tags and
   summaries re-enter prompts only as data**. An injection-shaped theme-name case is
   a named test. The ADR covers this posture; adversarial prompt-content behaviour
   beyond the structural bounds is eval-seam territory, recorded.
7. **Characterise writes content, not presentation (user decision, 2026-07-05).**
   Durable output per run: one `characterisation_result` row (scope, run, prompt
   version + model id, `coverage JSONB`, `themes JSONB` — names, descriptions, member
   ids, sizes, the unclustered set) + `source_tag` rows. **No artefact, no blocks**: EB
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
   coverage distributions (with their base), theme names + descriptions + sizes, the
   unclustered share, and honest flags (full-text coverage rate, Unknown-classification
   share, share failed embedding, repair-path taken). The skeleton renders it
   human-readably. This is
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
   in 007 *for this component*) · **topical distributions over the tag layer (rev 4.1,
   reshaped by rev 5)**: coverage aggregates `source_tag` grouped by
   `(tag_type, asserted_by)` — one uniform, spec-sanctioned surface
   (provenance-grounding rung 1 is "counts/distributions over Tier-0 columns/tags")
   instead of two backend-specific JSONB parses. Provider-asserted, provider-LLM and
   our own topical assertions appear as **separate, labelled distributions** in the
   landscape — the 007 never-mix posture rendered structurally. Provider signals still
   do **not** enter the grouping prompts in v3.0 (recorded seam — see Out of scope). The spec's fuller list (study geography, population)
   lives in text, not Tier-0 metadata — not fabricated; recorded as arriving with
   extraction. Distributions are computed by deterministic SQL/python (the lookup
   discipline: re-running the query *is* the verification), each carrying `base:
   "screened"` explicitly. **Flag-not-block** — nothing is excluded from coverage for
   being below any bar. **No gap or absence claims (adversarial finding 11, adopted):**
   009's landscape output renders distributions and counts only — it never asserts
   "little/no evidence exists on X". Absence claims require the coverage-base +
   search-adequacy machinery (`search_coverage_record` join, fail-closed degradation)
   that belongs to the gap-claim seam; a wording constraint on the landscape summary
   enforces this and a test asserts no absence-claim field exists in the payload.
   **Provider-field normalisation is a named plan requirement (finding 13):** exact
   field paths, display-name vs id choice, string-vs-list handling (Overton `topics`
   is either), per-document dedup, and missing/unknown buckets — pinned at the plan
   gate with fixture tests over the mixed shapes 007 recorded. **Dual-view coverage
   is a recorded seam**: no source/evidence policy object exists in v3.0 (verified),
   so the spec's "when the user has supplied a policy" condition never fires; single
   overall view ships.
10. **Tag layer lands with assertion provenance: `source_tag` + `asserted_by`
    (rev 5, user steer 2026-07-06).** Item × tag × type × asserter
    (`project_source_snapshot_id` FK, `tag`, `tag_type` — CHECK: `topic_theme` for
    now, additive later — **`asserted_by`**, `created_by_run_id`, `created_at`; unique
    `(pss, tag_type, tag, asserted_by)`). Two writers in this slice:
    - **Provider materialisation at acquire** — provider topical assertions
      (OpenAlex `primary_topic`/`topics`/SDG names; Overton `topics` /
      `classifications` / `sdgcategories` / `llm_document_theme`) are normalised into
      tag rows when the envelope lands, `asserted_by` naming the source. The
      vocabulary must keep three provenance classes distinguishable (plan detail pins
      exact values): provider-curated/algorithmic (e.g. `openalex`, `overton`),
      **provider-LLM** (e.g. `overton_llm` — the 007 never-mix posture, now enforced
      by provenance rather than by exclusion), and our own capabilities.
      Uploads carry no provider tags — honest absence. Raw `provider_fields` JSONB
      stays retained unchanged (tags are a normalised view, not a replacement).
    - **Characterise's themes** — `asserted_by="characterise"` + the run id.
    Insert-if-absent on the full key so re-runs accrete without duplicating; the same
    document may carry the same topic from two asserters — **two rows, and that
    corroboration is signal, not duplication**. **The canonical/run-local line
    (adversarial finding 5, adopted-in-part):** components §5 draws it explicitly —
    "per-cluster labels persist as topic/theme tags; the run's cluster grouping stays
    run-local". Tags are **canonical soft item metadata** (assertions with provenance,
    accreting like any assertion history); grouping *memberships* are run-local and
    live only in the characterisation row. A later run grouping differently adds new
    assertions rather than mutating old ones — earlier tags remain as attributed
    historical assertions (`created_by_run_id NOT NULL` makes every one dateable and
    attributable; finding 6), and pruning/merging them is the namespace-consolidation
    seam. Namespace consolidation stays the recorded orchestrator seam. classify's `open_tags` JSONB column is untouched —
    migrating it into this table is part of the LLM-classify seam, not this slice.
    **Spec flow-back (rev 5, user as spec author):** data-model.md's "nothing hangs
    off a tag" is clarified, not repealed — it governs the tag *label* (no per-tag
    entity, lifecycle, status or owner); the tag *assignment* row carries provenance
    (`asserted_by`, run), consistent with every other assertion in the system
    (rubric versions on appraisals, prompt versions on groupings). One clarifying
    passage + `log.md` entry ride this contract.
11. **Failure semantics: the interpretive half refuses to fake it (rev 3).** If the
    grouping call fails (provider outage, repair exhausted, validation still
    violated), characterise **fails loudly with honest counts** — no placeholder
    theme, no partial grouping presented as complete. Coverage distributions
    (deterministic, metadata-only) are still computed and reported in the failure
    payload — the deterministic half degrades honestly, the interpretive half refuses
    to fake it. Re-running characterise retries the grouping cleanly (run-local rows
    are per-run; nothing to unwind). Embed-pass failures at ingest never block
    ingestion or characterise (nothing in 009 reads vectors); they surface as honest
    counts and retry via the anti-join on any later ingest run.
12. **Component wiring mirrors 004–008.** `"characterise"` in `COMPONENT_REGISTRY`
    requiring `evidence_scope_id`; context dataclass `(scope_id, intent, context)`;
    `_run_characterise` via `_run_scope_component`; conditional-edge wiring;
    `component.started`/`completed`/`failed`. Counting invariant:
    `screened_in == grouped + unclustered` (+ honest failure states), embed pass
    reports `embedded + already_embedded + failed == pending_at_start`, and the
    characterisation row is unique per `(scope, run)`. Realisation is the spec's
    "procedure + agent" in miniature: a deterministic procedure wrapping one bounded
    LLM call.

### Clustering research grounding (rev 2, 2026-07-05)

User challenge at the draft gate: k-means over raw 1536-dim vectors would "almost
definitely produce subpar results"; directed a state-of-the-art sweep (last30days) and a
v2 reconnaissance subagent. Both streams adjudicated by the lead:

**State of the art (web + 30-day social sweep; raw file:
`~/Documents/Last30Days/document-topic-clustering-with-embeddings-raw-v3.md`):**
- The practitioner-standard stack for document topic discovery is the **BERTopic-shaped
  pipeline**: embeddings → (UMAP) → **HDBSCAN** → c-TF-IDF labels, optionally LLM labels
  as a representation layer. Peer-reviewed policy science uses exactly this on
  31,000-document policy corpora (Policy Studies Journal research note, 2026) — our
  domain class.
- Raw high-dim k-means is the known-weak baseline (distance concentration; forced
  assignment of outliers; k must be guessed). HDBSCAN discovers k and has a native noise
  class — but carries its own recorded failure modes: benchmarks show it can label 30%+
  of points noise, its parameters are unintuitive, and **short documents (our
  abstract-only class) measurably degrade its coherence** — hence decision 4's honest
  noise/floor/mix flags rather than pretending the finickiness away.
- **TopicGPT-class LLM-only topic modelling** aligns best with human topic judgments but
  is per-document-LLM-shaped (cost, scale cliff, non-reproducible) — the hybrid
  (algorithmic clustering + LLM label/refine) is the emerging cost/quality balance. That
  is exactly decision 4 + the decision 5 seam.

**v2 reconnaissance (`../discovery_policy_atlas`, synthesis service): v2's theming was
LLM-only, LangChain, two-stage** (gpt-5-mini proposes a theme set from ALL concepts in
one prompt; gpt-5-nano classifies each concept in O(N) fan-out calls), over four fixed
facets (issue/intervention/outcome/risk) of **extracted findings — which maps to v3's
`group` component, not characterise** (v2 had no doc-level topic landscape at all).
Defects found (the task-008 pattern repeating): a **dead critique stage** (full LLM QA
call whose output is discarded — pure cost sink), **silent concept drops** (mapping
failures return None and vanish — no unassigned bucket, no count), **silent collapse**
(discovery failure → everything dumped into one "General Theme" placeholder at warning
level), **no scale guard** (whole corpus in one prompt — context cliff), MECE promised in
the prompt but unenforced by construction, temperature=0 with no seed (non-reproducible
runs). Worth porting: the four-facet decomposition and the MECE/RQ-anchored prompt
discipline — both recorded at the **`group` + LLM-labelling seams**, not built here.
Every v2 defect has a structural counter in this contract: unclustered is a counted
bucket (vs silent drops), degenerate paths are flagged states (vs silent collapse),
clustering is O(0) LLM calls now and O(clusters) at the seam (vs O(N)), deterministic by
construction (vs unseeded generative grouping).

**Rev 3 adjudication (2026-07-06) — why the LLM route won after all, and why one call:**
the corpus-size check killed HDBSCAN as default (density estimation degenerate at
10s-of-docs scopes) and exposed agglomerative's cost (per-corpus cosine-threshold
tuning, term-soup labels — refinement-heavy machinery for clusters the spec calls
interpretive anyway). The user's judgment: generation was always coming in an LLM-based
tool; if an LLM call is the most appropriate mechanism, use it rather than hack an
algorithmic stand-in — confirmed with both gate expansions (generation egress + the
injection posture). The v2 lesson is thereby *refined, not reversed*: v2's failure was
not "LLM grouping" but its **operational shape** — O(N) mapping calls, a context cliff
with no guard, silent drops, a dead critique stage, MECE promised but unenforced. At
v3.0 scope sizes (10s–100s docs) one bounded structured call with code-enforced
validation + one repair call closes every one of those defects while keeping the
quality edge TopicGPT-class evidence documents. **No LangChain**: the
valuable v2 residue is prompt discipline (moved into the versioned prompts) and the
facet decomposition (moved to the `group` seam); v2's defects were design flaws in its
workflow (dead critique, batch-size-1 mapping, silent drops), and the SDK covers
structured calls natively — a second framework would be a dependency for what plain
code does.

**Rev 4 adjudication (2026-07-06) — the split comes forward:** rev 3 kept discover +
assign in one call and deferred the TopicGPT-style split to a large-corpus seam; the
user asked what deferring actually bought. Answer on inspection: nothing. Assignment
against a fixed theme list is the *easier* task per decision than joint
discovery+assignment (each batch attends to ~50 docs × ~10 themes instead of tracking
hundreds of assignments in one output), so quality at 20–200 docs is equal or better;
batched outputs remove the long-structured-output degradation risk; the rev-3 repair
call *was already* an assignment-stage call, so the split makes the primary path and
the repair path the same mechanism (simpler, not more complex); latency is a wash —
assignment batches run concurrently on a cheap classification model
(discovery-model-call + one parallel batch wave ≈ the single big call, tens of seconds
either way, in a pipeline whose ingest step runs minutes); and cost likely *drops*
(the long output moves from the judgment model to a nano-class model — v2's one right
instinct, kept). The remaining scale seam shrinks to discovery-sampling at very large
n. v2's actual error was never the split — it was batch size 1 (O(N) calls), no
validation, and silent drops between stages.

### Schema

**Gated change 1 — three new tables** (one migration; table count 16 → 19):

```
chunk_embedding          chunk_embedding_id PK · chunk_id FK→chunk · embedding_profile TEXT
                         · vector JSONB (code-validated: JSON array, expected dims,
                           finite floats — adversarial finding 14) · created_at
                         UNIQUE (chunk_id, embedding_profile)

characterisation_result  characterisation_id PK · project_id FK · evidence_scope_id ·
                         run_id · grouping_provenance JSONB (required keys, test-
                         asserted: prompt_version, discovery_model, assignment_model,
                         batch_size, retry counts — adversarial finding 4)
                         · coverage JSONB · themes JSONB · created_at
                         Composite FKs (evidence_scope_id, project_id) and
                         (run_id, project_id) — the result-table cross-project guard
                         (adversarial finding 2; screening-result precedent)
                         UNIQUE (evidence_scope_id, run_id)      -- run-local by design

source_tag               source_tag_id PK · project_id FK · project_source_snapshot_id ·
                         tag TEXT · tag_type TEXT CHECK (tag_type IN ('topic_theme'))
                         · asserted_by TEXT NOT NULL
                         · created_by_run_id NOT NULL · created_at
                         Composite FKs (project_source_snapshot_id, project_id) and
                         (created_by_run_id, project_id) (adversarial findings 2 + 6)
                         UNIQUE (project_source_snapshot_id, tag_type, tag, asserted_by)
```

Downgrade drops the tables. No existing table changes. `tests/helpers.py`
`delete_project_data` gains the three tables in FK-safe order.

### Python

- **`embeddings.py`** — `EmbeddingBackend` protocol · `OpenAIEmbeddingBackend` ·
  `StubEmbeddingBackend` · `EMBEDDING_PROFILE` constant(s) · `embed_pending_chunks(conn,
  *, embedder, project_id, run_id, batch_size=…, max_chunks=…) -> dict` (counts) ·
  deterministic windowing for oversized chunks.
- **`characterise.py`** — `CharacteriseContext` · `characterise_scope(conn, *,
  project_id, run_id, context, grouping_backend) -> dict` (coverage → discover →
  batched assign →
  validate/repair → tags → characterisation row → landscape summary) · the
  `characterise_grouping_v1` prompt (lead-authored) · grouping-output validation
  helpers · deterministic stub grouper.
- **`ingest.py` / `acquire.py` / `ingest_full_text.py`** — call `embed_pending_chunks`
  after their chunk writes (counts folded into their `component.completed` payloads).
- **`acquire.py`** additionally materialises provider topical assertions into
  `source_tag` when writing each envelope (deterministic normalisation per backend
  mapper; `asserted_by` per provenance class; insert-if-absent — decision 10).
- **`plan.py`** — `"characterise": {"requires": ["evidence_scope_id"]}`.
- **`harness.py`** — `_run_characterise`; `embedding_backend: EmbeddingBackend | None
  = None` and `grouping_backend: GroupingBackend | None = None` on `run_harness`
  (both default to stubs — no default egress); threaded through `HarnessState`.
- **`skeleton.py`** — chain extended with characterise; renders the landscape summary;
  uses the live embedder + live grouper **only when an explicit live flag is set
  (e.g. `POLICY_ATLAS_LIVE=1`) in addition to `OPENAI_API_KEY`** — key presence alone
  never flips a path to egress (adversarial finding 12, adopted); the baseline call
  budget is printed before live execution. Stubs otherwise.

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
- Grouping (stub grouper drives the suite; live behaviour is manual evidence + eval
  seam): batching is deterministic (id-ordered, stated batch size); per-batch
  validation enforces exhaustive assignment — an assignment double returning a missing
  doc, an invented id, or a duplicate triggers **discard-and-retry of that batch
  only, once** (asserted: the whole batch re-asked against the fixed theme list;
  other batches untouched; nothing from the invalid output persisted); invalid
  discovery output (theme count out of bounds, malformed) discarded and retried once;
  retry still invalid → honest `component.failed`, no partial grouping persisted, no
  placeholder theme (asserted unrepresentable); **edge scopes tested: `n=0` (skip +
  `empty_scope` flag, coverage still reported), `n=1`, `n < batch`** (finding 8);
  `unclustered` is a counted first-class outcome and the invariant covers it
  (`screened_in == grouped + unclustered`); the enforced call-budget maximum is
  asserted against a counting double; theme names violating length/charset
  constraints rejected, injection-shaped theme name stored/rendered as inert data
  (finding 10); grouping memberships land only in the characterisation row (no
  canonical cluster state anywhere); `grouping_provenance` required keys present on
  the row and event payload.
- Prompt hygiene: document content enters the prompt as id-keyed data records under
  the data/instructions separation (asserted structurally on the built prompt); an
  injection-shaped fixture abstract ("ignore instructions and…") flows through as
  data — the output schema cannot express anything but themes + assignments, and
  validation passes/fails on structure alone.
- Labels/tags: theme names persist as `source_tag` rows for members with
  `asserted_by="characterise"` (unclustered docs get no theme tag — no false labels);
  re-run accretes without duplicates. Provider materialisation: each backend's fixture
  records yield the expected tag rows with the right `asserted_by` class
  (provider-LLM distinguishable from provider-curated — `llm_document_theme` never
  lands under a curated or own-capability asserter); uploads get none; same topic from
  two asserters = two rows; raw `provider_fields` unchanged; only acquire and
  characterise write tags. Coverage aggregates by `(tag_type, asserted_by)` and the
  landscape summary keeps the provenance classes visually separate.
- Failure semantics: grouping failure → honest failure with coverage still reported in
  the payload (decision 11); counting invariants hold.
- Landscape summary payload: structure asserted (coverage + themes with sizes + flags
  + bases); no new event types; skeleton renders it.
- **Zero-egress guard extended**: `make verify` uses stubs only (stub embedder + stub
  grouper); socket-deny test covers an end-to-end characterise run (007/008 precedent
  — neither live path is ever exercised by the suite); `OpenAIEmbeddingBackend` / the
  live provider constructed without a key fail loudly and early; the key never appears
  in logs/events (asserted against captured output).
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
- **LLM screen/classify tools and the LLM grounding tier** — the generation gate opens
  for exactly one prompt-bearing surface (the grouping call); every other LLM seam
  stays stubbed and separately gated.
- **Steering modes / the landscape→synthesis steer-point pause** — plan-as-object
  machinery; the payload it will relay ships now (decision 8).
- **Dual-view coverage** — needs the source/evidence policy object (decision 9).
- **Bedrock embedding route** — the seam swap; recorded with the routing-seam note.
- **Exact-token budgeting (tiktoken-class) and semantic re-chunking** — recorded at the
  embed seam; v3.0 windowing is a char-budget heuristic (decision 2).
- **Very-large-corpus grouping** — discovery-sampling (stage 1 over a stratified
  sample when the whole corpus no longer fits one call) and/or embedding-based
  clustering (HDBSCAN/agglomerative over the chunk vectors this slice lands);
  grouping-quality evals (decision 4). Assignment already scales — batches are
  corpus-size-independent. The `group` component inherits v2's theming lessons
  (four-facet decomposition; the two-stage validated shape) — recorded in deferred.md
  by this slice.
- **Provider-signal prompt enrichment** — feeding provider topics/themes into the
  grouping prompts as per-doc hints; real bias risk (provider taxonomies vs
  intent-anchored themes) → enters via the grouping-quality eval seam, not by default.
  (Provider-topic *tag materialisation* was a rev-4.1 seam, pulled in-slice by rev 5
  with `asserted_by` provenance — decision 10.)
- **Tag namespace consolidation / `open_tags` migration** (decisions 5, 10).
- **`select` and everything deeper** — subsequent slices.

### Contract-stage adversarial review — findings & adjudication (Codex, 2026-07-06)

Fifteen findings against rev 4.1 (2 blockers · 11 majors · 2 minors); none challenged
the user-settled directions. Adjudicated by the lead onto rev 6 (rev 5 had already
landed the `asserted_by` provenance findings 5/6 partially anticipate):

1. Generation can't ride `InferenceProvider.complete(prompt)->str` (blocker):
   **adopted** — dedicated `GroupingBackend` protocol + `run_harness
   grouping_backend` parameter (gate 3 grew — flagged for the human).
2. Missing project-scoped composite-FK discipline on new tables (blocker):
   **adopted** — `project_id` + composite FKs on `characterisation_result` and
   `source_tag`, per the screening-result precedent.
3. Deliverable/decision-2 ensure-step contradiction: **adopted** — ensure-step
   removed from the deliverable (greenfield; decision 2 stands).
4. Singular `grouping_model` vs two models: **adopted** — `grouping_provenance
   JSONB` with required, test-asserted keys.
5. Run-local clusters vs canonical tags tension: **adopted-in-part** — the spec
   itself draws the line (components §5: labels persist as tags; grouping stays
   run-local); now stated explicitly in decision 10. The "key tags by run or don't
   write them" remedy is **rejected** — it would contradict components §5.
6. Nullable run provenance + stale-tag accretion: **adopted-in-part** —
   `created_by_run_id NOT NULL` (every assertion attributable); accretion retained
   by design (assertion history), pruning/merging recorded at the consolidation seam.
7. "Budget known before run" false w.r.t. retries: **adopted** — baseline
   `1 + ceil(n/batch)` vs enforced retry-capped maximum, checked pre-call.
8. Empty/small-n scopes unspecified: **adopted** — `n=0` skip + `empty_scope` flag;
   theme bounds `1..min(n, max)`; tests for n=0, n=1, n<batch.
9. Repair-residue semantics undefined: **adopted (as simplification)** — per-batch
   discard-and-retry-once; a batch persists only when fully valid.
10. Theme names are untrusted model output: **adopted** — length/charset
    constraints, stored/rendered as data, injection-shaped-name test, standing rule
    that tags/summaries re-enter prompts only as data.
11. Gap/absence claims need coverage-base machinery: **adopted (forbid option)** —
    009 output makes no absence claims; distributions only, test-asserted; gap-claim
    machinery stays at its seam.
12. Env-key presence alone flips paths live: **adopted** — explicit live flag
    required in addition to the key; budget printed before live execution.
13. Provider-field shape normalisation unspecified: **adopted** — named plan
    requirement (paths, name-vs-id, string-vs-list, dedup, missing buckets) with
    mixed-shape fixture tests.
14. Vector JSONB unvalidated: **adopted** — code-level array/dims/finite validation
    + tests.
15. Deliverable vs gates flow-back mismatch: **adopted** — lists synced (three
    flow-backs).

Gate-scope note for the human: finding 1 **grows gate 3** (a second `run_harness`
parameter, `grouping_backend`) and finding 2 grows the approved schema item within
the same three tables (project_id + composite FKs — enforcing existing repo
discipline). Both flagged here rather than silently folded.

## Constraints & approval gates

**Four gated changes (approval needed at this gate):**

1. **Schema** — three new tables (`chunk_embedding` · `characterisation_result` ·
   `source_tag`), one migration, no existing-table changes.
2. **Dependencies** — `openai` only (embeddings + structured generation through one
   SDK). Rev 3 drops rev 2's `scikit-learn` (no clustering algorithm ships) and rev 1's
   `numpy`; **not** the BERTopic framework (default install pulls
   sentence-transformers → torch plus umap-learn/numba — the gate-excluded ML tier —
   to supply a pipeline this design no longer runs).
3. **Public interface** — `run_harness` optional `embedding_backend` parameter + the
   `"characterise"` registry entry (007/08 precedent) + **`grouping_backend` parameter
   (adversarial finding 1 — blocker, adopted):** the existing
   `InferenceProvider.complete(prompt) -> str` cannot honestly carry strict structured
   outputs, two models, schemas, timeouts and budget caps, so generation gets its own
   seam — a **`GroupingBackend` protocol** (`discover(docs, intent) -> ThemeSet`,
   `assign(batch, themes) -> Assignments`; `mode: "live" | "stub"`), the
   SearchBackend/DocumentFetcher/EmbeddingBackend precedent exactly. `run_harness`
   gains optional `grouping_backend` defaulting to the stub. The grounding
   `provider` seam is untouched. **This grew gate 3 at adjudication — flagged for
   the human at re-read.**
4. **Runtime egress — both fronts, user-confirmed (2026-07-06).**
   `OpenAIEmbeddingBackend` sends chunk text to the embeddings API;
   the grouping call sends titles + abstracts to the chat API with the repo's first
   **product prompt** (lead-authored, versioned) — and the **injection posture comes
   due** (decision 6). Controls in decision 6; `make verify` and all defaults remain
   egress-free (stub embedder + stub grouper); live requires an **explicit live flag
   in addition to the environment key** (finding 12 — key presence alone never
   selects egress).

Plus three spec flow-backs approved with this contract: the data-model tag-layer
clarification (rev 5, decision 10: "nothing hangs off a tag" governs the label; the
assignment row carries `asserted_by` provenance), the components §5
content-vs-artefact clarification (decision 7), and the §5 thematic-mechanism update
(decision 4: v3.0 groups via a bounded two-stage LLM procedure — discover, then
batched assignment — over titles/abstracts; embedding-based clustering and
discovery-sampling are the recorded very-large-corpus paths; chunk vectorisation lands
with the egress gate ahead of its first reader — approved exception to the 008
deferral line).

**Explicitly not crossed:** no agent-loop generation (a fixed two-stage procedure with
a baseline call budget of `1 + ceil(n/batch)` and an enforced retry-capped
maximum — schema-bound throughout), no auth/tenancy change, no CI change, no pgvector/extension, no
artefact/block writes, no changes to existing tables, no new orchestration dependency
(the SDK covers structured calls; LangChain would add a dependency for what plain code
does).

## Public / private boundary

- **Credentials**: `OPENAI_API_KEY` environment-only; never committed, logged, or echoed
  into events/verification artifacts (test-asserted). `.env` stays gitignored.
- **Corpus text leaves the machine on the live paths** — chunk text (embeddings) and
  titles + abstracts (grouping) — to the configured provider only, under the
  spec-accepted v3.0 inference-route posture. Fixture-corpus content is openly
  licensed (008's licence guard), so even live verification runs send only
  committable text.
- Committed artifacts (profile names, table/column names, deterministic labels over
  fixture corpora, verification counts) are all public-safe. No recorded live vectors
  are committed in this slice (stub vectors cover the suite; if the plan finds a test
  that genuinely needs real vectors, committing recorded ones is a plan-gate question).

## Model route

**Embeddings**: OpenAI `text-embedding-3-small` under the approved-controls posture
(→ Bedrock behind the `EmbeddingBackend` seam when the route lands); the embedding
profile string is the model-version provenance on every row. **Generation, two
right-sized models** (exact pins at the plan gate; both behind the existing `provider`
seam, → Bedrock at the same route swap): **discovery** on a judgment-capable model
(gpt-5-mini-class — one call per run) and **assignment** on a cheap classification
model (gpt-5-nano-class — `ceil(n/batch)` concurrent calls per run; v2's one right
instinct, kept). **Prompt-bearing surface: the `characterise_grouping_v1` prompt pair**
(discovery + assignment, co-versioned; decision 5) — lead-authored, recorded on the
characterisation row and event payload; the only prompts in the slice.

## Disciplines binding this slice

- **Eager and uniform** — every ingested chunk embeds under the active profile; absence
  is pending, never a silent skip; lazy/on-demand stays rejected.
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
- **Deterministic where claimed, honestly soft where not** — coverage, stub paths,
  validation logic: same input, same output, test-enforced. The live grouping is
  interpretive by design (softest grade); its provenance (prompt version, model id)
  makes every grouping attributable. Neither live path is inside `make verify`.
- **Exactly one prompt-bearing surface** — the `characterise_grouping_v1` prompt pair
  (discovery + assignment, co-versioned), lead-authored; no other generation exists in
  the slice (decision 5).
- **Never silent, never fake** — no placeholder themes, no silent drops, no partial
  grouping presented as complete (decisions 4, 11 — v2's failure modes made
  unrepresentable).

## Stop conditions

- Any gated change (schema · deps · public interface · **egress**) not yet approved, or
  any change beyond the gated items (e.g. an existing-table change, pgvector, a second
  provider).
- Any *default or test* code path would perform network I/O (live is explicit-wiring
  only).
- The one-artefact shape is threatened mid-build (something needs blocks/artefact writes
  after all) — halt, don't improvise composition.
- The two-stage grouping proves inadequate *for the machinery to function* on the live
  manual check (e.g. per-batch validation + repair cannot converge on the fixture
  corpus — not merely imperfect themes, which is the eval seam) — halt and re-open
  decision 4 with evidence; don't quietly grow extra stages or an agent loop.
- The grouping prompt needs capabilities beyond themes+assignments (tool use, free
  text, multi-turn) — that's a different design; halt.
- Scope would grow past the contract (other LLM seams, retrieval, composition, policy
  object, select).
- `make verify` red with unclear root cause; or the turn/token budget is spent.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green, deterministic, zero egress
  (socket-deny covers the characterise round-trip).
- **One manual live check** (evidence in verification.md): skeleton end-to-end with
  the explicit live flag + `OPENAI_API_KEY` set against the fixture corpus — real embeddings, a real grouping
  call (themes + assignments over the fixture docs), landscape summary rendered;
  per-run token/chunk counts and cost note recorded; key absent from all captured
  output.
- Deterministic vs AI eval: all suite checks are deterministic tests (stub embedder +
  stub grouper). Theme *quality* on the live path is eval territory (the
  grouping-quality seam); this slice's bar is machinery correctness + honest output,
  not theme goodness.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny + key-hygiene test results named.
- Migration roundtrip clean; table count 19.
- Counting-invariant + idempotency + eager-uniform coverage test results named.
- The live-run evidence (manual check above): landscape summary as rendered, theme
  names + sizes over the fixture corpus, embed counts/batches, grouping
  token/validation/repair counts, honest cost note.
- Determinism evidence: two stub runs byte-identical on the characterisation row.
- Public-safety confirmation (no credentials anywhere; live run sent openly-licensed
  fixture text only).
- Deferred seams recorded in `docs/deferred.md` (EB artefact composition ·
  large-corpus grouping — two-stage/batched or embedding-based clustering over the
  landed chunk vectors · grouping-quality + adversarial-content evals · steering-mode
  steer-point reading the landscape payload · dual-view coverage behind the policy
  object · pgvector + retrieval — the chunk vectors' first reader · Bedrock route
  swap · exact-token budgeting · v2 theming lessons at the `group` seam · tag
  namespace consolidation) and the class-1 "vectorisation at first reader" entry
  updated: discharged by 009 ahead of its reader (approved exception).
- Diff summary (any bulky fixture data excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — opens the runtime-egress gate on both fronts (first product egress:
embeddings + generation; credentials; project data leaving the machine; the repo's
first product prompt; the injection posture coming due), three new tables, a new
dependency, a public-interface addition. ADR 0005 (embed + generation seams / first
egress / injection posture) due at step 4; contract- and plan-stage adversarial
reviews standard.

Review focus:
- **Security (the headline lane)**: key handling (env-only, never logged/committed);
  egress boundaries (stub defaults, live explicit; socket-deny in suite); what text
  leaves and under what posture; **the prompt-injection surface** (id-keyed data
  records, schema-constrained output, no tools, code-side validation — the structural
  bounds hold?); budget guards; timeout/retry bounds.
- **Correctness**: anti-join idempotency; eager-uniform coverage across all three
  ingestion paths; windowing determinism; grouping validation + repair logic
  (exhaustiveness, invented ids, duplicates, bounds); counting invariants;
  decision-11 honest failure.
- **Provenance/honesty**: pattern grades kept distinct; bases on every claim;
  run-local groupings not leaking into canonical state; embedding profile + prompt
  version stamped everywhere; no placeholder-theme or silent-drop path representable.
- **Schema**: migration roundtrip; FK-safe deletes; unique constraints.
- **Scope**: exactly one generation surface; no composition/blocks, no pgvector, no
  select, no LangChain.
