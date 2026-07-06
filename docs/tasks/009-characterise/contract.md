# Task contract: 009-characterise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** **approved** (rev 9 — clean consolidation of revs 1–8 plus the
> single-tag-home change) — planning in progress.
> Contract approved (before planning): **2026-07-06 · Shabeer Rauf** (rev 9,
> covering the four flagged acks: `grouping_backend` parameter · project-scoped
> composite FKs · `open_tags` retirement · `langfuse` dependency; contract-stage
> adversarial review adjudicated at revs 6–6.1) ·
> Plan approved (before implementation): _pending_ ·
> ADR: 0005 (embed + generation seams / first product egress / injection posture) —
> due at step 4.
>
> **Revision history** (all user-decided or user-confirmed; detail in § Research
> grounding and § Adversarial review):
> - **rev 1** (2026-07-05): initial draft. User-settled: whole characterise in one
>   slice · live OpenAI embeddings (egress gate opens here) · no artefact/blocks
>   (option A — EB's single artefact composes at the run terminus) · landscape
>   summary as the intermediate-feedback relay surface.
> - **rev 2**: numpy k-means (user-challenged) → HDBSCAN + c-TF-IDF, after a
>   state-of-the-art sweep + v2-theming reconnaissance.
> - **rev 3**: algorithmic clustering dropped → LLM grouping. **User confirmed both
>   gate expansions: generation egress + the injection posture coming due.** Also:
>   chunk-grain embedding ships ahead of its first reader (approved exception to
>   008's deferral line); greenfield (no backfill); deps shrink to `openai`.
> - **rev 4/4.1**: grouping split into the two-stage TopicGPT shape (discover →
>   batched concurrent assignment, right-sized models); BERTopic-rejection reason
>   corrected to the dependency stack; provider topical signals join coverage.
> - **rev 5**: provider-topic tags pulled in-slice — `source_tag.asserted_by`
>   assertion provenance; spec flow-back: "nothing hangs off a tag" governs the
>   label, the assignment row carries provenance.
> - **rev 6/6.1**: Codex adversarial review adjudicated (15 findings; § Adversarial
>   review) — `GroupingBackend` seam, project-scoped composite FKs, budget
>   baseline/max, edge scopes, untrusted theme names, no absence claims; user
>   reversed two adoptions (targeted residue repair restored; no extra live flag —
>   egress is the product).
> - **rev 7**: Langfuse tracing baseline in-slice; trace content settled: **full I/O
>   payloads, eval-ready spans** ("maximum use — state-of-the-art telemetry layer
>   and eval surface").
> - **rev 8**: mean-pooled windowing → **embedding-unit layer** (~512-token units,
>   ~10% intra-chunk overlap, one vector per unit), after a chunking
>   state-of-the-art sweep.

## Goal

Add **characterise** — the EB shallow terminus (component 5). After the cheap envelope
passes and full-text ingestion, characterise produces the **evidence landscape
content** for a scope:

- **Deterministic coverage distributions** over Tier-0 columns and the tag layer —
  the hardest pattern grade, exactly reproducible, resting on the **screened base**,
  flag-not-block.
- **Topic-level thematic shape**: an LLM discovers the scope's themes from all
  titles + abstracts (one call), then assigns every screened-in document against
  that fixed theme list (batched concurrent calls; a document may land explicitly in
  none) — a bounded call budget with an enforced maximum, honest about being the
  **softest grade** (an interpretive shape, not a count — recomputable, never a
  deterministic fact: exactly the epistemic class an LLM grouping belongs to).

This is the slice that **opens the runtime-egress gate on both fronts** (user
decisions, 2026-07-05/06): **embeddings** (OpenAI `text-embedding-3-small` behind an
`EmbeddingBackend` seam — eager-and-uniform chunk-grain vectorisation at ingest,
landed ahead of its first reader as an approved exception: certain
retrieval/synthesis substrate, and this is the gate-opening slice) and **generation**
(the grouping calls — the repo's first product prompts, and the first time
third-party corpus text enters an LLM prompt, so the recorded injection posture comes
due). The spec accepts live egress as the documented v3.0 posture (first pass OpenAI
→ target Bedrock, behind the routing seams); the gates exist so it is opened
deliberately, here, with the controls in decision 6. `make verify` remains
deterministic and egress-free (stub embedder + stub grouper); live paths are explicit
wiring + manual evidence.

Characterise writes **content, not presentation**: a run-scoped characterisation
record + topic/theme tags. It does **not** mint an artefact — EB produces **one**
artefact, composed at the run terminus by the orchestrator (capability.md); the
artefact-composition step is a recorded seam (user clarification, 2026-07-05).

## Deliverable

A PR on `task/009-characterise` → `dev` that:
- Ships `embeddings.py`: `EmbeddingBackend` (protocol), `OpenAIEmbeddingBackend`,
  `StubEmbeddingBackend`, the named versioned embedding profile + unit policy, and
  `embed_pending_chunks()` — the eager-and-uniform, idempotent embed pass over
  embedding units.
- Ships the `GroupingBackend` seam: protocol + `OpenAIGroupingBackend` (two-stage
  structured generation) + deterministic stub.
- Ships `characterise.py`: deterministic coverage distributions; the two-stage LLM
  grouping (discover → batched assign) with lead-authored co-versioned prompts,
  schema-constrained outputs, code-enforced per-batch validation + targeted repair,
  and an honest `unclustered` bucket; tag persistence; the run-scoped
  characterisation row; the structured landscape summary in `component.completed`.
- Adds three tables — `chunk_embedding`, `characterisation_result`, `source_tag` —
  and retires `source_classification_result.open_tags` (single tag home,
  decision 10), via one Alembic migration (gated change 1; table count 16 → 19).
- Wires the embed pass into all three ingestion paths (upload, acquire envelope,
  full-text ingest); acquire additionally materialises provider topical assertions
  into `source_tag` (decision 10). No characterise-time ensure-step (greenfield).
- Adds `openai` and `langfuse` as runtime dependencies (gated change 2); Langfuse
  tracing wraps the two live backends, env-driven, no-op without keys (decision 13).
- Registers `"characterise"` in `COMPONENT_REGISTRY`; wires `_run_characterise`;
  `run_harness` gains optional `embedding_backend` and `grouping_backend`
  parameters (gated change 3).
- Extends `skeleton.py`: … appraise → ingest_full_text → **characterise**, rendering
  the landscape summary (decision 8).
- Lands the three spec flow-backs + `log.md` entries (matching § Constraints):
  components §5 content-vs-artefact (decision 7); components §5 thematic mechanism +
  vectorisation-with-gate exception (decisions 4, 2); data-model tag-layer assertion
  provenance (decision 10).
- Records the deferred seams in `docs/deferred.md`; updates `tests/helpers.py`
  delete order for the new tables.
- Passes `make verify` — all green, deterministic, egress-free (live paths exercised
  manually, evidence in verification.md).

## Read first

- [EB components §5 — characterise](../../specs/capabilities/evidence-base/components.md)
  (coverage over Tier-0 columns/tags, flag-not-block, screened base; thematic
  grouping, labels persist as topic/theme tags, grouping stays run-local) and **§4's
  embed discipline** (eager-and-uniform at ingest; this slice discharges the 008
  deferral, ahead of its reader by approved exception).
- [EB capability](../../specs/capabilities/evidence-base/capability.md) — **one
  artefact**; orchestrator composes sections; cluster-persistence rules; the
  landscape→synthesis mode-governed steer-point (decision 8's future reader).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) +
  [system provenance-grounding § Patterns](../../specs/system/provenance-grounding.md)
  — the pattern grades, never conflated; coverage claims carry their base; absence
  claims need machinery this slice deliberately does not build (decision 9).
- [System data-model](../../specs/system/data-model.md) — tag layer (item × tag,
  typed, created by capabilities); substrate key = content hash × parse-profile ×
  segmentation-policy × embedding-model version.
- [System execution-orchestration](../../specs/system/execution-orchestration.md) —
  Tier-0 retrieval contract (pgvector is the *retrieval* slice's commitment, not
  ours); `search` stays the only agent-invocable egress verb; characterise
  realisation = "procedure + agent".
- [docs/deferred.md](../../deferred.md) — "vectorisation at the first vector reader"
  (class-1, discharged here); 008's chunk-volume-bias + token-budgeted re-chunking
  notes; the `open_tags` consolidation seam.
- [008-full-text contract](../008-full-text/contract.md) — pattern precedent (seams,
  gated `run_harness` parameters, decision structure).

**Code grounding (surveyed 2026-07-05):** 16 tables; no vector/embedding/pgvector
anything; no tag table (`open_tags` is a stub-empty JSONB column on classification —
retired by this slice, decision 10); chunks live
in `chunk` (`sequence`, `content`, `content_hash`, `locator JSONB`,
`segmentation_policy`); chunk writes happen at exactly three sites (upload ingest,
acquire envelope, full-text ingest parent-side write loop); `run_harness(conn, *,
config, project_id, run_id, provider, search_backends=None, document_fetcher=None)`
is the injection precedent; `InferenceProvider` is `complete(prompt) -> str` (why
generation needs its own seam); Overton's retained `source` field was kept *for
characterise*; the walking skeleton's artefact/block machinery exists but nothing
here writes to it.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **Embedding backend: live OpenAI `text-embedding-3-small` behind an
   `EmbeddingBackend` seam — the first product egress** (user, 2026-07-05).
   Protocol: `embed_texts(list[str]) -> list[list[float]]` + `mode` (`"live"` |
   `"stub"`), mirroring `SearchBackend`/`DocumentFetcher`. `OpenAIEmbeddingBackend`
   (the `openai` SDK, `OPENAI_API_KEY` env-only) is production;
   `StubEmbeddingBackend` (deterministic content-hash-derived vectors, same
   dimensionality) keeps the suite egress-free. `run_harness` defaults to the stub.
   The **embedding profile** (`openai_text_embedding_3_small_v1`: provider, model,
   dimensions, distance convention) is stamped on every row — the substrate-key leg
   data-model reserves for embedding-model version. Bedrock swaps in at this seam.
   Declined: stub-only (defers the class-1 egress slice for no product progress);
   local ML model (the gate-excluded dependency tier, superseded by the provider
   route anyway).
2. **Eager-and-uniform vectorisation at ingest, over embedding units.**
   - `embed_pending_chunks(conn, embedder, ...)` embeds every chunk lacking rows for
     the active profile (anti-join — the result-table idempotency pattern), in
     deterministic chunk order, batched; called at the end of all three ingestion
     paths. Uniform = all snapshot classes (uploads, envelopes, full-text). Embed
     failures never fail ingestion: honest counts (`embedded` / `already_embedded` /
     `failed`); the missing row *is* the retryable state; any later ingest run is
     the natural retry (greenfield — no backfill machinery).
   - **Ahead-of-reader exception (user, 2026-07-06):** nothing in 009 reads these
     vectors; they ship anyway because chunk vectors are certain
     retrieval/synthesis substrate and landing them with the egress gate beats
     relitigating egress in a third slice. Spec log entry rides this contract.
   - **Embedding units (research-grounded, § Chunking grounding):** embedding-side
     segmentation is a first-class, named, versioned layer
     (`embedding_unit_policy_v1`). In-budget chunks (most paragraphs/abstracts) are
     **one unit**; oversized chunks (008's known heading-light giants) split
     deterministically at sentence/paragraph boundaries into **~512-token-target
     units with ~10% intra-chunk overlap** (the benchmarked practitioner optimum for
     descriptive/technical corpora; token budget via a conservative character
     heuristic — no tokenizer dependency). **One embedding row per unit**, each with
     offsets back into its canonical chunk — never a mean vector over a 10-page
     section (small-to-big: match at unit grain, cite the canonical chunk).
     Canonical chunks are never touched (one parse, one segmentation stands; 008's
     "token-budgeted re-chunking" lands as this layer, not chunk mutation).
     Deliberately not adopted: semantic chunking (marginal gains, ~10x cost — our
     canonical chunks are already structure-aware, the property benchmarks reward).
     Recorded seams, entered via retrieval evals: contextual retrieval
     (Anthropic-style chunk context; 49–67% failure reduction at LLM-call-per-chunk
     cost), late chunking (long-context embedder), exact-token budgeting.
3. **Embedding storage: `chunk_embedding` at unit grain, JSONB vector, no pgvector.**
   One row per (chunk × profile × unit policy × unit index); vector as a JSONB float
   array, code-validated (array, expected dims, finite). Nothing in this slice reads
   the vectors, so a pgvector column/index would be an unread index behind a
   dependency + extension + infra decision — pgvector arrives with the `retrieve`
   slice, the vectors' actual first reader (the Tier-0 retrieval contract commits to
   it there); the migration is additive. Profile/policy-keyed rows mean a future
   model or unit-policy change re-embeds under new keys without touching history.
4. **Thematic grouping: two-stage LLM — discover, then batched concurrent assignment
   — code-owned validation and targeted repair** (user decisions, revs 3–4;
   TopicGPT's shape; rationale in § Grouping grounding).
   - **Stage 1 — discover** (one call, judgment-capable model): all screened-in
     documents' `(id, title, abstract)` (~30K tokens at 100 docs) + the scope's
     intent; output schema-constrained to a **theme set** (name + one-line
     description; count bounded, e.g. 3–12). Discovery sees the whole corpus;
     discovery-sampling at very large n is the only remaining scale seam.
   - **Stage 2 — assign** (batched ~25–50 docs, cheap classification model, batches
     concurrent): each batch assigned against the **fixed theme list**; output
     schema-constrained to `(doc_id, theme | "unclustered")` per doc. Fixed-list
     assignment is the easier per-decision task and bounded outputs avoid
     long-structured-output degradation — equal-or-better quality at 20–200 docs,
     unchanged design at 2,000.
   - **Call budget** (finding 7): baseline `1 + ceil(n/batch)`, known pre-run;
     enforced maximum `(1 + discovery_retry_cap) + ceil(n/batch) ×
     (1 + assignment_retry_cap)` (caps small, plan-pinned), checked before any live
     call.
   - **Validation is code, not model trust — per batch, targeted repair with defined
     residue semantics** (finding 9, as user-directed): schema conformance is
     provider-enforced (strict structured outputs); exhaustiveness is not
     schema-expressible, so code repairs by case — **invented ids** dropped in code
     (no call); **duplicate-same-theme** deduped in code (no call); **missing ∪
     conflicting ids = the residue** — one targeted repair call re-asks exactly
     those ids against the fixed theme list, keeping the batch's valid assignments.
     Invalid discovery output (theme count out of bounds, malformed) is retried
     once. Residue still invalid after repair → honest failure (decision 11) —
     never silent drops, never a placeholder theme (v2's "General Theme" collapse
     is unrepresentable).
   - **Empty and small scopes** (finding 8): `n = 0` → grouping skipped honestly
     (coverage still reported; `empty_scope` flag); small `n` → theme bounds
     `1..min(n, max)`; `n < batch` is one batch. Each is a tested path.
   - **`unclustered` is a first-class, counted outcome** — the model may decline to
     force-fit; those docs stay fully eligible downstream and form their own
     stratum when `select` lands. Counting invariant:
     `screened_in == grouped + unclustered` (+ honest failure states).
   - **No new orchestration dependency**: both stages are plain procedure code
     against the `GroupingBackend` seam — the SDK covers structured calls natively;
     concurrency is a bounded `gather`. (v2's LangChain constructs were thin
     wrappers over exactly this; its defects were design flaws, not framework
     properties.)
   - **Grouping is run-local** (persisted only in this run's characterisation row —
     resume checkpoint, recomputable, superseded by the next run; never a canonical
     corpus fact, per capability.md). Re-runs may group differently — the softest
     grade says exactly this; `grouping_provenance` (prompt version, model ids,
     settings) makes every grouping attributable.
   - **Test seam:** a deterministic stub grouper (stub discover + stub assign — the
     `_stub_screen`/`_stub_classify` pattern) drives the suite and exercises all
     downstream machinery; the live path is manual evidence.
5. **The grouping prompts are the repo's first product prompts — prompt-bearing,
   lead-authored, co-versioned.** Discovery + assignment prompts version together as
   `characterise_grouping_v1`, recorded in `grouping_provenance` and the event
   payload (the appraisal `rubric_version` discipline applied to prompts). They
   carry v2's genuinely good prompt discipline: **intent-anchored** (themes serve
   the scope's stated intent), **MECE-oriented** (collective exhaustiveness enforced
   *in code*; exclusivity and granularity are prompt discipline), **affirmative,
   evidence-grounded labels** (derived only from supplied text). Theme names double
   as the labels — no separate labelling mechanism — and persist as topic/theme tags
   on member documents (decision 10). Prompt-bearing work is lead-only per
   AGENTS.md.
6. **Egress governance + the injection posture coming due.** Neither egress path is
   agent-invocable (`search` stays the only agent-invocable egress verb); like 008's
   fetch posture both are mechanical execution under the governed run: structured
   telemetry per call/batch + run-record summary counts in `component.completed` —
   no per-chunk/per-document governance events. Controls: API keys env-only (never
   a parameter default, never logged, never committed; asserted absent from captured
   output); explicit timeouts; bounded retry/backoff; batch caps; **per-run budget
   guards on both paths** (max chunks per embed pass; the grouping baseline/maximum
   of decision 4) — over any cap → stop with honest counts and a loud log, never a
   silent partial. What leaves: chunk text (embed path), titles + abstracts
   (grouping path), to the configured provider — the spec-accepted v3.0 posture.
   **Injection posture (user-confirmed):** first slice where third-party corpus
   text — including provider-LLM-written Overton descriptions — enters an LLM
   prompt; the seam 007/008 pre-registered. Structural mitigations: content passed
   as **id-keyed data records** under explicit data/instructions separation; output
   channel **schema-constrained to themes + id assignments** (no tools, no free
   text acting on the world — a hijacked model can at worst mis-group or
   mis-label, bounded by validation and the softest-grade framing); exhaustiveness
   and id validity enforced in code; embeddings interpret nothing. **Theme names
   and descriptions are themselves untrusted model output** (finding 10): they flow
   into the summary and tags, so they carry code-enforced length/charset
   constraints, are stored/rendered as data, and the standing rule is recorded:
   **tags and summaries re-enter prompts only as data**. ADR 0005 covers this
   posture; adversarial prompt-content behaviour beyond the structural bounds is
   eval-seam territory.
7. **Characterise writes content, not presentation** (user, 2026-07-05). Durable
   output per run: one `characterisation_result` row (`grouping_provenance`,
   `coverage`, `themes` — names, descriptions, member ids, sizes, the unclustered
   set) + `source_tag` rows. **No artefact, no blocks**: the EB
   artefact-composition step (create-or-supersede the single artefact, landscape
   blocks, summary/key-findings conventions, artefact versioning) is a recorded
   seam. Spec flow-back: components §5 clarified — "characterise produces the
   landscape *content*; the single EB artefact is composed once at the run
   terminus".
8. **The landscape summary is the intermediate-feedback surface** (user,
   2026-07-05: v3.0 steerability vs monolithic v2). The `component.completed`
   payload carries a structured landscape summary designed for relay, not just
   counts: coverage distributions (with their base), theme names + descriptions +
   sizes, the unclustered share, honest flags (full-text coverage rate,
   Unknown-classification share, failed-embedding share, repair-path taken,
   `empty_scope`). The skeleton renders it human-readably. This is what the
   mode-governed landscape→synthesis steer-point reads when steering modes land —
   that pause machinery is a recorded seam; the content it relays ships now. No new
   event types; the payload is the surface.
9. **Coverage pass: deterministic distributions over what Tier-0 actually has.**
   Over the scope's screened-in set (with not-relevant / screen-failed / unscreened
   counts alongside — the base ladder visible): `origin` · `text_basis` /
   `full_text_status` (+ reasons) · `primary_evidence_type` (honest about
   stub-classification reality) · quality tier × `rubric_version` · `screen_basis`
   + confidence bands · year · language · backend · publisher/geography where the
   envelope carries it (Overton `source`, retained in 007 for this component) ·
   **topical distributions over the tag layer**, grouped by
   `(tag_type, asserted_by)` — one uniform, spec-sanctioned surface
   (provenance-grounding rung 1 covers columns *and tags*); provider-asserted,
   provider-LLM and own-capability assertions appear as separate, labelled
   distributions (the 007 never-mix posture rendered structurally). Computed by
   deterministic SQL/python (re-running the query *is* the verification), each
   distribution carrying `base: "screened"`. **Flag-not-block** — nothing excluded
   for being below any bar. **No gap or absence claims** (finding 11): 009 renders
   distributions and counts only — never "little/no evidence exists on X"; absence
   claims need the `search_coverage_record` adequacy machinery that belongs to the
   gap-claim seam; test-asserted (no absence-claim field in the payload).
   **Provider-field normalisation is a named plan requirement** (finding 13): field
   paths, name-vs-id, string-vs-list (Overton `topics` is either), per-document
   dedup, missing/unknown buckets — plan-pinned with mixed-shape fixture tests.
   The spec's fuller list (study geography, population) lives in text, not Tier-0 —
   not fabricated; arrives with extraction. **Dual-view coverage is a recorded
   seam**: no source/evidence policy object exists in v3.0, so the spec's
   "when the user has supplied a policy" condition never fires.
10. **The tag layer lands with assertion provenance: `source_tag` + `asserted_by`**
    (user, 2026-07-06). Item × tag × type × asserter; unique
    `(pss, tag_type, tag, asserted_by)`; `tag_type` CHECK (`topic_theme` for now,
    additive later); `asserted_by` and `created_by_run_id` NOT NULL (every
    assertion dateable and attributable). Two writers in this slice:
    - **Provider materialisation at acquire**: OpenAlex `primary_topic`/`topics`/
      SDG names; Overton `topics`/`classifications`/`sdgcategories`/
      `llm_document_theme` — normalised into tag rows when the envelope lands,
      `asserted_by` naming the source. Three provenance classes stay
      distinguishable (plan pins values): provider-curated/algorithmic (e.g.
      `openalex`, `overton`), **provider-LLM** (e.g. `overton_llm` — the 007
      never-mix posture enforced by provenance rather than exclusion), and our own
      capabilities. Uploads carry no provider tags. Raw `provider_fields` stays
      retained unchanged (tags are a normalised view, not a replacement).
    - **Characterise's themes**: `asserted_by="characterise"` + the run id.
    Insert-if-absent on the full key; the same topic from two asserters = two rows —
    corroboration is signal, not duplication. **The canonical/run-local line**
    (finding 5): components §5 draws it — labels persist as tags (canonical soft
    item metadata, accreting assertion history); grouping *memberships* are
    run-local, in the characterisation row only. A later run adds assertions rather
    than mutating old ones; pruning/merging is the namespace-consolidation seam.
    **`source_tag` is the single tag home (user, 2026-07-06):** classify's
    `open_tags` JSONB column is **retired in this slice** — it is stub-empty (the
    stub always wrote `[]`, nothing reads it, greenfield), so dropping the column +
    its array CHECK now costs one small migration line and prevents a second tag
    home from ever existing. All tag writers, present and future, write
    `source_tag`: the LLM classify tool will write
    `tag_type="methodological_structural"` rows with `asserted_by="classify"` when
    its seam opens (the CHECK widens by a one-line migration then — no speculative
    value ships now). Later agents interact with one queryable, typed,
    provenance-stamped surface. Spec flow-back (user as author): data-model's "nothing
    hangs off a tag" clarified, not repealed — it governs the tag *label*; the
    assignment row carries provenance, like every other assertion in the system.
11. **Failure semantics: the interpretive half refuses to fake it.** Grouping
    failure (provider outage, repair exhausted, validation still violated) →
    characterise fails loudly with honest counts; coverage (deterministic,
    metadata-only) is still computed and reported in the failure payload. Re-running
    retries cleanly (run-local rows are per-run). Embed-pass failures at ingest
    never block ingestion or characterise (nothing in 009 reads vectors); honest
    counts, anti-join retry.
12. **Component wiring mirrors 004–008.** `"characterise"` in `COMPONENT_REGISTRY`
    requiring `evidence_scope_id`; context dataclass `(scope_id, intent, context)`;
    `_run_characterise` via `_run_scope_component`; conditional-edge wiring;
    `component.started`/`completed`/`failed`. Invariants:
    `screened_in == grouped + unclustered` (+ failure states);
    `embedded + already_embedded + failed == pending_at_start`; one
    characterisation row per `(scope, run)`. Realisation is the spec's "procedure +
    agent" in miniature: a deterministic procedure wrapping bounded LLM calls.
13. **Langfuse tracing baseline — full I/O, eval-ready** (user, 2026-07-06;
    engineering-considerations names Langfuse the trace backbone; first slice with
    LLM traffic, so the baseline lands with the seams instead of being retrofitted).
    - Tracing wraps the **two live backends only**: one trace per run, spans per
      component and call, carrying project/run ids, component, embedding profile,
      prompt version, model ids, tokens, latency, cost. Dev vs prod instance
      routing is environment configuration.
    - **Env-driven, off by default**: no `LANGFUSE_*` keys → no-op; stubs are never
      traced; the suite stays deterministic and egress-free. Telemetry goes only to
      the user-operated Langfuse instances — the third egress destination (gate 4).
    - **Trace content — settled: full I/O payloads** (prompts + outputs), resolving
      the engineering-considerations resolve-before-sensitive-tracing item for
      acquired text; instances are user-operated. Retention, sampling, masking and
      access control are the observability seam's recorded open items. Direction
      set with it ("maximum use — state-of-the-art telemetry layer and eval
      surface"): traces ship **eval-ready, not log-shaped** — spans carry
      structured metadata (doc ids, batch index, validation outcome, retry/repair
      events, unclustered counts) and validation outcomes attach as Langfuse
      scores, so trace → eval-dataset promotion has substrate from day one.
    - **Prompt registry stays repo-first**; traces record prompt name + version so
      the runtime-registry hookup (deployment, labels/environments, emergency-edit
      reconciliation) is additive — a recorded seam.

### Research grounding

**Grouping (revs 2–4; raw file:
`~/Documents/Last30Days/document-topic-clustering-with-embeddings-raw-v3.md`).**
The practitioner-standard algorithmic stack is BERTopic-shaped (embeddings → UMAP →
HDBSCAN → c-TF-IDF; used in peer-reviewed policy science on 31K-doc corpora), but it
failed our constraints in order: raw k-means is the known-weak baseline (rev 1 →
rev 2); HDBSCAN is degenerate-by-default at 10s-of-docs scopes and short documents
(our abstract-only class) measurably degrade it; agglomerative needs per-corpus
threshold tuning and yields term-soup labels. TopicGPT-class LLM grouping aligns
best with human topic judgment; its costs are operational, and at 10s–100s docs a
bounded two-stage procedure with code-enforced validation closes every one of them.
The BERTopic *framework* was declined for its dependency stack (default install
pulls sentence-transformers → torch + umap/numba — the gate-excluded ML tier), not
framework-ness; scikit-learn left the gate with the algorithm.

**v2 reconnaissance (`../discovery_policy_atlas`, synthesis service).** v2's theming
was LLM-only LangChain, two-stage — gpt-5-mini discovery over ALL concepts in one
prompt; gpt-5-nano assignment in O(N) per-concept calls — over four fixed facets of
*extracted findings* (maps to v3's `group`, not characterise; v2 had no doc-level
landscape). Defects, each with a structural counter here: dead critique stage (cost
sink) → no vestigial stages; silent concept drops → exhaustiveness enforced in code,
`unclustered` counted; "General Theme" silent collapse → degenerate outcomes are
flagged failures, placeholder unrepresentable; no scale guard → budget
baseline/maximum + discovery-sampling seam; O(N) calls → batched `ceil(n/batch)`;
MECE prompt-hoped → exhaustiveness code-enforced. Worth porting: the facet
decomposition (→ `group` seam) and the MECE/intent-anchored prompt discipline (→
decision 5). v2's one right instinct — nano-class models for assignment — is kept.
The two-stage split costs nothing at our sizes and wins on every axis (assignment
against a fixed list is the easier task; bounded outputs; repair = the assignment
mechanism; the long output moves to the cheap model).

**Chunking (rev 8; raw file:
`~/Documents/Last30Days/rag-chunking-strategies-for-embeddings-raw-v3.md`).**
2026 benchmarks: recursive/structural ~512-token splitting wins end-to-end accuracy
(69% vs semantic chunking's 54%, ~10x cheaper); 512–1024 tokens suits
descriptive/technical content; ~10% overlap kills boundary-straddling; structure-
aware-vs-naive is the big gap — which vindicates 008's structure-aware canonical
chunks and kills mean-pooling giant sections. Hence decision 2's embedding-unit
layer. Contextual retrieval (+49–67% at LLM-call-per-chunk cost) and late chunking
(long-context embedder) are recorded retrieval-eval seams.

**TopicGPT lineage.** Decision 4 *is* TopicGPT's two-stage method against our seams
(the codebase is a research artifact; prompts are lead-authored here regardless).
Deliberately deferred to the grouping-quality eval seam: **topic refinement**
(merge/prune near-duplicates — largely suppressed by the bounded theme count) and
**quotation-verified assignment** (the cheapest known lever on assignment quality,
but it would pull the grounding economy into an output the spec keeps soft). Its
iterative generation is the discovery-sampling seam.

### Contract-stage adversarial review — findings & adjudication (Codex, 2026-07-06)

Fifteen findings against rev 4.1 (2 blockers · 11 majors · 2 minors); none
challenged the user-settled directions. Adjudicated by the lead; two adoptions later
reversed at user pushback (rev 6.1):

1. Generation can't ride `InferenceProvider.complete(prompt)->str` (blocker):
   **adopted** — dedicated `GroupingBackend` protocol + `run_harness
   grouping_backend` parameter (grew gate 3 — flagged for the human).
2. Missing project-scoped composite-FK discipline on new tables (blocker):
   **adopted** — `project_id` + composite FKs, per the screening-result precedent.
3. Deliverable/decision-2 ensure-step contradiction: **adopted** — ensure-step
   removed (greenfield).
4. Singular `grouping_model` vs two models: **adopted** — `grouping_provenance
   JSONB` with required, test-asserted keys.
5. Run-local groupings vs canonical tags tension: **adopted-in-part** — the spec
   draws the line (components §5: labels persist as tags; grouping stays
   run-local), now stated in decision 10; the "key tags by run or don't write them"
   remedy **rejected** (contradicts components §5).
6. Nullable run provenance + stale-tag accretion: **adopted-in-part** —
   `created_by_run_id NOT NULL`; accretion retained by design (assertion history);
   pruning/merging at the consolidation seam.
7. "Budget known before run" false w.r.t. retries: **adopted** — baseline vs
   enforced retry-capped maximum, checked pre-call.
8. Empty/small-n scopes unspecified: **adopted** — `n=0` skip + `empty_scope`;
   theme bounds `1..min(n, max)`; tests for n=0, n=1, n<batch.
9. Repair-residue semantics undefined: **adopted, then reversed at user pushback**
   — the gap was real but the fix is *defining* the semantics, not discarding good
   batches: invented/dup-same = code fixes (no call); residue = missing ∪
   conflicting ids, one targeted call. Targeted fixes beat whole-batch retries at a
   few hundred docs.
10. Theme names are untrusted model output: **adopted** — length/charset
    constraints, stored as data, injection-shaped-name test, standing
    tags/summaries-re-enter-prompts-only-as-data rule.
11. Gap/absence claims need coverage-base machinery: **adopted (forbid option)** —
    009 makes no absence claims; distributions only, test-asserted.
12. Env-key presence alone flips paths live: **adopted, then reversed at user
    pushback** — egress is the product; a configured key on the skeleton is live
    intent. What stands: suite + library defaults stub/egress-free (socket-deny);
    baseline budget logged before live execution.
13. Provider-field shape normalisation unspecified: **adopted** — named plan
    requirement with mixed-shape fixture tests.
14. Vector JSONB unvalidated: **adopted** — code-level array/dims/finite validation
    + tests.
15. Deliverable vs gates flow-back mismatch: **adopted** — lists synced.

Gate-scope note for the human: finding 1 grew gate 3 (`grouping_backend` parameter)
and finding 2 grew the schema item within the same three tables (project_id +
composite FKs — enforcing existing repo discipline). Flagged, not silently folded.

### Schema

**Gated change 1 — three new tables** (one migration; table count 16 → 19):

```
chunk_embedding          chunk_embedding_id PK · chunk_id FK→chunk
                         · embedding_profile TEXT · unit_policy TEXT
                         · unit_index INT · unit_locator JSONB (offsets into the
                           canonical chunk)
                         · vector JSONB (code-validated: array, expected dims,
                           finite floats) · created_at
                         UNIQUE (chunk_id, embedding_profile, unit_policy, unit_index)

characterisation_result  characterisation_id PK · project_id FK · evidence_scope_id
                         · run_id · grouping_provenance JSONB (required keys,
                           test-asserted: prompt_version, discovery_model,
                           assignment_model, batch_size, retry counts)
                         · coverage JSONB · themes JSONB · created_at
                         Composite FKs (evidence_scope_id, project_id),
                         (run_id, project_id) — cross-project guard
                         UNIQUE (evidence_scope_id, run_id)   -- run-local by design

source_tag               source_tag_id PK · project_id FK
                         · project_source_snapshot_id · tag TEXT
                         · tag_type TEXT CHECK (tag_type IN ('topic_theme'))
                         · asserted_by TEXT NOT NULL
                         · created_by_run_id NOT NULL · created_at
                         Composite FKs (project_source_snapshot_id, project_id),
                         (created_by_run_id, project_id)
                         UNIQUE (project_source_snapshot_id, tag_type, tag,
                                 asserted_by)
```

The same migration drops `source_classification_result.open_tags` +
`ck_scr_open_tags_array` (decision 10; downgrade restores them). Downgrade drops the
three tables. `tests/helpers.py` `delete_project_data` gains the three tables in
FK-safe order.

### Python

- **`embeddings.py`** — `EmbeddingBackend` protocol · `OpenAIEmbeddingBackend` ·
  `StubEmbeddingBackend` · profile + unit-policy constants · unit derivation
  (deterministic sentence-boundary splitting to the token target) ·
  `embed_pending_chunks(conn, *, embedder, project_id, run_id, batch_size=…,
  max_chunks=…) -> dict` (counts).
- **`grouping.py` (or within `characterise.py`)** — `GroupingBackend` protocol
  (`discover(docs, intent) -> ThemeSet`, `assign(batch, themes) -> Assignments`,
  `mode`) · `OpenAIGroupingBackend` (structured outputs, two models) · deterministic
  stub grouper.
- **`characterise.py`** — `CharacteriseContext` · `characterise_scope(conn, *,
  project_id, run_id, context, grouping_backend) -> dict` (coverage → discover →
  batched assign → validate/repair → tags → characterisation row → landscape
  summary) · the `characterise_grouping_v1` prompt pair (lead-authored) ·
  validation/repair helpers.
- **`ingest.py` / `acquire.py` / `ingest_full_text.py`** — call
  `embed_pending_chunks` after their chunk writes (counts folded into the two
  components' `component.completed` payloads; upload ingest has no component
  surface, so its counts go to a structured log — plan-review finding 3). `acquire.py` additionally materialises provider
  topical assertions into `source_tag` per envelope (deterministic per-backend
  normalisation; `asserted_by` per provenance class; insert-if-absent).
- **`plan.py`** — `"characterise": {"requires": ["evidence_scope_id"]}`.
- **`harness.py`** — `_run_characterise`; `embedding_backend: EmbeddingBackend |
  None = None` and `grouping_backend: GroupingBackend | None = None` on
  `run_harness` (both default to stubs — no default egress); threaded through
  `HarnessState`.
- **`skeleton.py`** — chain extended with characterise; renders the landscape
  summary; uses the live embedder + grouper when `OPENAI_API_KEY` is configured
  (egress is the product — a configured key on the demo entrypoint is the
  operator's live intent; suite and library defaults stay stub regardless), logging
  the baseline call budget before live execution.
- **Langfuse wiring** — tracing around the two live backends per decision 13;
  no-op without keys.

### Tests (`tests/test_characterise.py` + `tests/test_embeddings.py`)

- Migration roundtrip; table count 19; unique constraints, CHECKs and composite FKs
  reject invalid/duplicate/cross-project rows.
- Embed pass: anti-join idempotency (second call all `already_embedded`);
  deterministic chunk order; batching; failure isolation (failing embedder double →
  honest `failed` counts, ingestion still succeeds, stragglers retried); budget
  guard trips loudly; **unit derivation deterministic** (in-budget chunk → exactly
  one unit; oversized chunk → sentence-boundary units at the token target with ~10%
  overlap, offsets recorded, canonical chunk untouched; no mean-pooling path
  exists); profile + unit policy stamped on every row; vector validation rejects
  wrong type/length/non-finite; stub vectors deterministic across processes.
- Eager-uniform: after upload + acquire + full-text ingest, every chunk of every
  snapshot class has embedding rows for the profile.
- Coverage: distributions over a seeded corpus match hand-computed values; base
  counts (screened-in / not-relevant / failed / unscreened) present; every
  distribution carries its base; flag-not-block; no absence-claim field in the
  payload; provider-field normalisation over mixed fixture shapes.
- Grouping (stub grouper drives the suite): deterministic id-ordered batching;
  per-batch validation repairs by case — invented ids dropped and duplicate-same
  deduped **in code, no LLM call** (asserted); missing + conflicting ids → one
  targeted repair call with exactly the residue (valid assignments kept; other
  batches untouched); invalid discovery retried once; repair exhausted → honest
  `component.failed`, nothing persisted, placeholder theme unrepresentable; edge
  scopes `n=0` (skip + `empty_scope`, coverage still reported), `n=1`, `n<batch`;
  `unclustered` counted and covered by the invariant; call-budget maximum asserted
  against a counting double; theme-name length/charset constraints enforced;
  injection-shaped theme name stored/rendered as inert data; memberships land only
  in the characterisation row; `grouping_provenance` required keys present on row
  and event payload.
- Prompt hygiene: document content enters prompts as id-keyed data records under
  the data/instructions separation (asserted structurally on the built prompt); an
  injection-shaped fixture abstract flows through as data — the output schema can
  express nothing but themes + assignments.
- Tags: theme names persist with `asserted_by="characterise"` (unclustered docs get
  no theme tag); re-runs accrete without duplicates; provider materialisation per
  backend fixture yields expected rows with the right provenance class
  (`llm_document_theme` never lands under a curated or own-capability asserter);
  uploads get none; same topic × two asserters = two rows; `provider_fields`
  unchanged; only acquire and characterise write tags; coverage aggregates by
  `(tag_type, asserted_by)` with classes kept separate in the summary.
- Failure semantics: grouping failure → honest failure with coverage still in the
  payload; counting invariants hold.
- Landscape summary: structure asserted (coverage + themes + flags + bases); no new
  event types; skeleton renders it.
- **Zero-egress guard**: suite uses stubs only; socket-deny covers an end-to-end
  characterise run; tracing no-op without `LANGFUSE_*` keys (no side effects, no
  SDK egress attempts); live backends constructed without keys fail loudly and
  early; no key appears in logs/events (asserted against captured output).
- Idempotency/re-run: second characterise run → new characterisation row, tags
  accreted not duplicated, embeddings all `already_embedded`.
- Harness round-trip: `Plan(component="characterise")` → row + tags in DB;
  `test_compile.py` gains the registry case.
- `open_tags` retirement: column + CHECK gone after migration; classify stub no
  longer emits the field; classify tests updated; no writer or reader of `open_tags`
  remains (grep-asserted in review).
- `delete_project_data` clean with all three tables populated.
- Downstream untouched: screen/classify/appraise/ingest outputs identical
  before/after (they don't read embeddings or tags).

### Out of scope

- **EB artefact composition** (single artefact, landscape blocks, summary/
  key-findings conventions, supersede + lock-on-advance versioning) — its own slice
  (decision 7).
- **`retrieve` / pgvector / hybrid retrieval** — the chunk-embedding rows' first
  reader; chunk-volume-bias controls recorded there (decision 3).
- **Contextual retrieval, late chunking, exact-token budgeting, semantic
  re-chunking** — retrieval-eval seams on the embedding-unit layer (decision 2).
- **LLM screen/classify tools and the LLM grounding tier** — the generation gate
  opens for exactly one prompt-bearing surface (the grouping pair); every other LLM
  seam stays stubbed and separately gated.
- **Steering modes / the landscape→synthesis steer-point pause** — plan-as-object
  machinery; the payload it will relay ships now (decision 8).
- **Dual-view coverage** — needs the source/evidence policy object (decision 9).
- **Bedrock routes** — the seam swaps for both backends.
- **Very-large-corpus grouping** — discovery-sampling and/or embedding-based
  clustering over the landed chunk vectors; grouping-quality evals (decision 4).
  Assignment already scales. The `group` component inherits v2's theming lessons
  (facet decomposition; the two-stage validated shape).
- **TopicGPT extensions** — topic refinement and quotation-verified assignment at
  the grouping-quality eval seam (§ Research grounding).
- **Provider-signal prompt enrichment** — provider topics as per-doc grouping hints;
  taxonomy-bias risk → eval seam, not default.
- **Langfuse follow-ons** — runtime prompt registry deployment
  (labels/environments, emergency-edit reconciliation), retention/sampling/masking/
  access policies, trace→eval-dataset promotion (decision 13).
- **Tag namespace consolidation** (pruning/merging accreted assertions —
  orchestrator seam, decisions 5, 10). The LLM classify tool writes `source_tag`
  directly when its seam opens; there is no `open_tags` migration left to do.
- **`select` and everything deeper** — subsequent slices.

## Constraints & approval gates

**Four gated changes (approval needed at this gate):**

1. **Schema** — three new tables (`chunk_embedding` · `characterisation_result` ·
   `source_tag`, project-scope-guarded per repo discipline) **plus one existing-table
   change: `source_classification_result.open_tags` (stub-empty) and its array CHECK
   are dropped** — `source_tag` is the single tag home (decision 10). One migration.
2. **Dependencies** — `openai` (embeddings + structured generation, one SDK) and
   `langfuse` (trace backbone; no-op without keys). Not scikit-learn/numpy (no
   algorithm ships), not BERTopic (torch via sentence-transformers + umap/numba —
   the gate-excluded ML tier), not LangChain (the SDK covers structured calls).
3. **Public interface** — `run_harness` gains optional `embedding_backend` and
   `grouping_backend` parameters (both default to stubs) + the `"characterise"`
   registry entry. `GroupingBackend` exists because
   `InferenceProvider.complete(prompt) -> str` cannot carry strict structured
   outputs, two models, and budget caps (adversarial finding 1); the grounding
   `provider` seam is untouched.
4. **Runtime egress — both fronts + telemetry (user-confirmed).**
   `OpenAIEmbeddingBackend` sends chunk text to the embeddings API; the grouping
   calls send titles + abstracts to the chat API under the repo's first product
   prompts; traces carry full I/O to the user-operated Langfuse instances
   (decision 13). Controls in decision 6. `make verify` and library defaults stay
   egress-free; the skeleton goes live on a configured key (egress is the
   product).

Plus three spec flow-backs approved with this contract: components §5
content-vs-artefact (decision 7); components §5 thematic mechanism +
vectorisation-with-gate exception (decisions 4, 2); data-model tag-layer assertion
provenance (decision 10).

**Explicitly not crossed:** no agent-loop generation (fixed two-stage procedure,
budget baseline `1 + ceil(n/batch)`, enforced retry-capped maximum, schema-bound
throughout); no auth/tenancy change; no CI change; no pgvector/extension; no
artefact/block writes; no existing-table changes beyond the gated `open_tags`
retirement; no new orchestration dependency.

## Public / private boundary

- **Credentials**: `OPENAI_API_KEY` and `LANGFUSE_*` env-only; never committed,
  logged, or echoed into events/verification artifacts (test-asserted). `.env`
  stays gitignored.
- **Corpus text leaves the machine on the live paths** — chunk text (embeddings),
  titles + abstracts (grouping) — to the configured provider, and as full-I/O
  traces to the user-operated Langfuse instances (decision 13), under the
  spec-accepted v3.0 posture. Fixture-corpus content is openly licensed (008's
  licence guard), so even live verification runs send only committable text.
- Committed artifacts (profile/policy names, table/column names, verification
  counts) are public-safe. No recorded live vectors are committed (stub vectors
  cover the suite; a test genuinely needing real vectors is a plan-gate question).

## Model route

**Embeddings**: OpenAI `text-embedding-3-small` behind the `EmbeddingBackend` seam
(→ Bedrock at the seam swap); the embedding profile is the model-version provenance
on every row. **Generation, two right-sized models behind the `GroupingBackend`
seam** (exact pins at the plan gate; → Bedrock at the same class of swap):
**discovery** on a judgment-capable model (gpt-5-mini-class, one call per run);
**assignment** on a cheap classification model (gpt-5-nano-class, `ceil(n/batch)`
concurrent calls). **Prompt-bearing surface: the `characterise_grouping_v1` prompt
pair** (discovery + assignment, co-versioned, lead-authored) — the only prompts in
the slice, recorded in `grouping_provenance` and the event payload.

## Disciplines binding this slice

- **Eager and uniform** — every ingested chunk embeds under the active profile;
  absence is pending, never a silent skip; lazy/on-demand stays rejected.
- **Pattern grades never conflated** — coverage = metadata-grounded facts with an
  explicit base; themes = interpretive shape, run-local, honestly soft; the summary
  carries both with grades visible.
- **Run-local means run-local** — grouping memberships live only in the run's
  characterisation row; nothing promotes them to canonical corpus state.
- **Flag, don't drop** — coverage counts everything on the screened base;
  Unknown/Non-evidence/below-bar rows present-and-visible, never excluded.
- **Honest absence** — distributions and the summary carry base-ladder counts; no
  absence claims at all in 009 output; Tier-0's real limits stated, not papered
  over.
- **Snapshots and chunks immutable** — embedding units attach *alongside*; no chunk
  mutation, no re-segmentation (one parse, one segmentation stands).
- **Deterministic where claimed, honestly soft where not** — coverage, stubs, unit
  derivation, validation: same input, same output, test-enforced. Live grouping is
  interpretive by design; `grouping_provenance` makes every grouping attributable.
  Neither live path is inside `make verify`.
- **Exactly one prompt-bearing surface** — the `characterise_grouping_v1` pair,
  lead-authored; no other generation exists in the slice.
- **Never silent, never fake** — no placeholder themes, no silent drops, no partial
  grouping presented as complete (v2's failure modes made unrepresentable).

## Stop conditions

- Any gated change (schema · deps · public interface · egress) not yet approved, or
  any change beyond the gated items (existing-table change, pgvector, a second
  provider, another generation surface).
- Any *suite or library-default* code path would perform network I/O.
- The one-artefact shape is threatened mid-build (something needs blocks/artefact
  writes after all) — halt, don't improvise composition.
- The two-stage grouping proves inadequate *for the machinery to function* on the
  live manual check (validation + repair cannot converge on the fixture corpus —
  not merely imperfect themes, which is the eval seam) — halt and re-open
  decision 4 with evidence; don't quietly grow extra stages or an agent loop.
- The grouping prompts need capabilities beyond themes + assignments (tool use,
  free text, multi-turn) — a different design; halt.
- Scope would grow past the contract (other LLM seams, retrieval, composition,
  policy object, select).
- `make verify` red with unclear root cause; or the turn/token budget is spent.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green, deterministic, zero
  egress (socket-deny covers the characterise round-trip; tracing no-op without
  keys).
- **One manual live check** (evidence in verification.md): skeleton end-to-end with
  `OPENAI_API_KEY` (+ `LANGFUSE_*` for the dev instance) against the fixture corpus
  — real embeddings, real discovery + assignment calls, landscape summary rendered,
  **run trace visible in the dev Langfuse instance** (span structure, prompt
  version, tokens/cost); per-run counts and cost note recorded; keys absent from
  all captured output.
- Deterministic vs AI eval: all suite checks are deterministic tests (stub embedder
  + stub grouper). Theme *quality* on the live path is eval territory (the
  grouping-quality seam); this slice's bar is machinery correctness + honest
  output.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny + key-hygiene results named.
- Migration roundtrip clean; table count 19.
- Counting-invariant + idempotency + eager-uniform + unit-derivation test results
  named.
- Live-run evidence (manual check above): landscape summary as rendered, theme
  names + sizes over the fixture corpus, embed counts/batches, grouping
  token/validation/repair counts, honest cost note, dev-instance trace note.
- Determinism evidence: two stub runs byte-identical on the characterisation row.
- Public-safety confirmation (no credentials anywhere; live run sent
  openly-licensed fixture text only).
- Deferred seams recorded in `docs/deferred.md` (EB artefact composition ·
  very-large-corpus grouping · grouping-quality + adversarial-content evals ·
  TopicGPT refinement + quotation-verified assignment · contextual retrieval + late
  chunking + exact-token budgeting · steer-point pause reading the landscape
  payload · dual-view coverage behind the policy object · pgvector + retrieval —
  the vectors' first reader · Bedrock route swaps · provider-signal prompt
  enrichment · v2 theming lessons at the `group` seam · tag namespace
  consolidation · Langfuse follow-ons: runtime prompt registry,
  retention/sampling/masking/access, trace→eval promotion), the existing
  `open_tags`-population entries revised (column retired; the LLM classify tool
  writes `source_tag`), and the class-1
  "vectorisation at first reader" entry updated: discharged by 009 ahead of its
  reader (approved exception).
- Diff summary (bulky fixture data excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — opens the runtime-egress gate on both fronts (first product egress:
embeddings + generation + telemetry; credentials; corpus text leaving the machine;
the repo's first product prompts; the injection posture coming due), three new
tables, two new dependencies, two public-interface additions. ADR 0005 (embed +
generation seams / first egress / injection posture) due at step 4; contract- and
plan-stage adversarial reviews standard.

Review focus:
- **Security (the headline lane)**: key handling (env-only, never logged/committed);
  egress boundaries (stub defaults, live explicit; socket-deny); what text leaves
  and under what posture (provider + Langfuse); **the prompt-injection surface**
  (id-keyed data records, schema-constrained output, no tools, code-side
  validation — do the structural bounds hold?); budget guards; timeout/retry
  bounds.
- **Correctness**: anti-join idempotency; eager-uniform coverage across all three
  ingestion paths; unit-derivation determinism; grouping validation + targeted
  repair (exhaustiveness, invented ids, duplicates, residue semantics, bounds);
  counting invariants; honest failure (decision 11).
- **Provenance/honesty**: pattern grades distinct; bases on every claim; run-local
  groupings not leaking into canonical state; tag provenance classes never mixed;
  profile/policy/prompt versions stamped everywhere; no placeholder-theme or
  silent-drop path representable.
- **Schema**: migration roundtrip; composite FKs; FK-safe deletes; unique
  constraints.
- **Scope**: exactly one generation surface; no composition/blocks, no pgvector, no
  select, no new frameworks.
