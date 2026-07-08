# Deferred seams

Recorded, not built *yet* — seams left open per "build light, leave seams." Each is a real
architectural decision to defer, not an omission. Sources: architecture reference §§3–11
(Appendix A; Appendix B), briefing Appendix A, EB build spec, EB handoff §7. Grouped by area.

**Two kinds of entry live here — don't conflate them** (user clarification, 2026-07-05):

1. **Sequenced v3.0 capabilities** — required for v3.0 to function as intended, waiting only
   on their approval gates (runtime egress · LLM/inference). The specs are explicit that
   **v3.0 has live egress** (briefing §Security: inference calls via the configured route,
   first pass OpenAI → target Bedrock; search queries to configured evidence backends —
   "accepted as a documented v3.0 risk because external evidence gathering is core to the
   product", arch-ref §3.3). "Zero runtime egress" in task docs is a *build-stage discipline*
   (each slice introducing product egress needs explicit approval — harness.md), never a v3.0
   scope statement. In this class: **live `SearchBackend`s** · **live `DocumentFetcher`** ·
   the **LLM screen / classify tools** · the **LLM grounding tier** — the product cannot
   search, fetch, ingest or reason without them. **Vectorisation** left this class in
   task 009: live OpenAI embeddings shipped at ingest, deliberately *ahead of* their first
   reader (approved exception — see the discharged entry under Full-text ingestion).
2. **Deferred beyond v3.0** — everything else below: doors deliberately left open (other
   capabilities, branch parallelism, per-item egress controls, private deployments, …).

## Capabilities

- **All capabilities except Evidence Base** — Options Assessment, Impact, Transferability, Value
  for Money, Theory of Change, Risk, Scrutinise/Red-team (Appendix A). v3.0 builds EB only.
- **Options Assessment** consumes EB output + the findings layer to resolve descriptive
  intervention clusters into named, comparable options — the decision-relative step EB explicitly
  leaves out.

## Product / output

- **Export & sharing** — share CTAs, read-only/public links, version-pinned external deep links
  back into the body (handoff §7.3). The primary surface is the tool itself.
- **Cross-boundary traceability** — statement-to-statement cross-artefact tracing; chain-strength
  composition; chain display; version-pinned cross-artefact staleness (behind the
  addressable-span seam).
- **Body-level coherence** — semantic-pass contradiction detection across a selected
  decision-support-body view (never auto-edits locked artefacts).
- **Chart view-types** over structured-content blocks.
- **Summaries as a retrieval-routing signal**
  (route-never-substitute recorded).
- **Artefact-level confidence badge / `ArtefactVersion.confidence`** and aggregate cross-source
  confidence scores (handoff §7.2) — use descriptive factual-snapshot metadata + finding-strength
  language instead.

## Evidence Base internals

- **Consensus / weighted-strength roll-up** — the strength-weighted verdict ("supports X at
  strength Y") and divided-evidence *direction* verdict (synthesise component 9). Task 013
  confirms the boundary as the intended v3.0 line (contract rev 7.4, user-affirmed): the
  artefact describes the spread, never "the evidence supports X", until this seam lands.
  Never-contribute constraints restated for the eventual roll-up: Unsupported/mis-cited and
  Tier-4 **reasoning claims** never contribute positively; weakly-grounded only at a
  discount; **gap claims** never contribute (absence is coverage, not strength).
- **Relative-to-feasible appraisal tier** + the **full two-stage appraisal pass** (richer
  full-text methods/risk-of-bias on the selected subset — which exists as of task 010:
  select's run-scoped `selection_result` row defines it) + modifier-tag-driven rubric dimensions
  (appraise component 4). Typed dimensions (`dimensions` column/bag) arrive with that second
  pass — nothing populates or reads them in v3.0, so no half-built column shipped (task 006).
- **Steerable / plan-carried appraisal rubric** — the orchestrator compiles a provisional
  evidence hierarchy into the plan; the user inspects/adjusts before the run. v3.0 is
  default-rubric-only (`DEFAULT_RUBRIC` in `appraise.py`), with provenance carried by
  `rubric_version` (`v2-hierarchy-v1`) on every row and event — the seam a plan-carried rubric
  plugs into. Validation that a stored `rubric_version` names a rubric that actually exists
  belongs to this seam too (review note, task 006).
- **Re-appraisal under a new rubric version** — `uq_sar_scope_source` deliberately blocks a
  second appraisal per `(scope, source)`; the re-run seam relaxes it to
  `(scope, source, rubric_version)`. That slice must also revisit the counting semantics:
  `already_appraised` counts all appraisal rows for the scope, so if re-classification ever
  changes a source's evidence type after it was appraised, a rerun double-counts it (one
  appraisal row + one skip bucket for the same classification row) and the counting invariant
  breaks (adversarial-review finding, task 006).
- **v2's small-sample penalty** — v2 applied −1 to causal studies with sample size < 100.
  Needs sample size, which v3.0's acquire-stage metadata doesn't carry; deferred with the
  richer full-text appraisal pass, not silently dropped (contract decision 3, task 006).
- **`source_appraisal_result` → `source_classification_result` FK — deliberately absent, not
  just deferred** (mirrors the classify→screen entry below). A composite FK onto
  classification's `(evidence_scope_id, project_source_snapshot_id)` unique key would
  DB-enforce "only classified rows are appraised", but both result tables' unique constraints
  are slated to gain re-run/rubric-version columns, which the FK would hard-block. The
  invariant lives in the read path (`appraise_sources` selects *from*
  `source_classification_result`) and is covered by the round-trip tests; rationale also at
  the table definition in `schema.py` (task 006, contract-adjudicated).
- **Grey-lit category granularity** — splitting v2's coarse Policy-Guidance / Expert-Opinion
  primary types (classify component 3; needs policy-team input). `source_classification_result`
  and `primary_evidence_type` check constraint are durable; column split is additive when ready.
- **LLM-based classify tool** — `_stub_classify` is the deterministic stub; the real tool (LLM
  call → one of the 9 closed `primary_evidence_type` values) is the deferred seam.
  `ClassifyContext`, `ClassifyResult`, and `source_classification_result` are durable and ready.
- **Open tags → `source_tag`** (revised, task 009): the stub-empty
  `source_classification_result.open_tags` column and its array CHECK were **retired** by
  migration 9 — `source_tag` (item × tag, typed, assertion provenance in the unique key) is
  the single tag home. When the LLM classify tool's seam opens it writes `source_tag`
  directly (`asserted_by='classify'`, `tag_type='methodological_structural'` — the
  `ck_stag_tag_type` CHECK widens by a one-line migration; the value lives in
  `schema.TOPIC_THEME`-style constants and all writers route through
  `tags.insert_source_tags`). There is no `open_tags` migration left to do.
- **`Unknown / Insufficient information` resolution** — sources landing `Unknown` are kept-and-eligible;
  full-text re-classification is a deferred seam mirroring the appraisal path.
- **`source_classification_result` → `source_screening_result` FK — deliberately absent, not just
  deferred.** No composite FK ties a classification row to its screening result; the "only relevant
  sources are classified" discipline is enforced only in `classify_sources`, not durably at the
  schema level. This is low-risk today (no direct writer to the table exists besides
  `classify_sources`), but a hard FK here may be the *wrong* direction long-term, not merely
  incomplete hardening: `project_source_snapshot.origin` already distinguishes `"uploaded"` from
  `"acquired"` sources, and uploaded documents are plausibly relevant by user intent alone — a
  future slice may let them skip `screen` entirely and go straight to `classify`, which a FK to
  `source_screening_result` would hard-block. **Confirmed direction: `acquired` sources always
  screen** (search/acquisition provides no relevance signal, so screen's recall-oriented filter
  still applies); whether `uploaded` sources skip screen is the open question for that future
  slice — needs its own spec refinement (`docs/specs/capabilities/evidence-base/components.md`
  currently describes classify as running on "the screened-in set" unconditionally) before any
  component is built against it.
- **`characterise`+ EB components** — subsequent slices (screen, classify, appraise, acquire
  and full-text ingestion landed: tasks 004–008). The task-007 note that retained provider URL
  fields "for slice 008" is discharged: 008 consumed them with an **updated precedence** —
  OpenAlex `best_oa_location.pdf_url` → `primary_location.pdf_url` → `open_access.oa_url` →
  `primary_location.landing_page_url` (contract-stage adversarial finding 4 superseded v2's
  `primary_location`-first order); Overton `pdf_url` → `document_url`. v2's **parse caps were
  not carried** — truncation is abolished (full text or honest failure; `too_large`/`timeout`
  fail loudly, contract decision 6) — and v2's fragilities (fetch errors swallowed at debug
  level; thin landing-page text reported `ok`) are structurally closed (reason-coded
  `full_text_status`/`full_text_error`, thin-text guard). Snapshot identity resolved as a
  **new immutable `full_text` snapshot linked at the project-source link** (ADR 0003).
- **`implementation_context_finding`** — the second reusable finding schema (mechanisms, barriers,
  implementation conditions); cross-schema linkage is reference-mediated via `group`. Extract-side
  note (task 011): V2's CFIR implementation-profile field definitions (cost/staffing/complexity +
  the inner-setting rule) are recorded design input for this schema; no field of it entered
  `intervention_outcome_finding`.
- **Saturation-based search stopping** (iterating retrieval↔screen until no new relevant docs);
  `saturated` is not a v3.0 `search_coverage_record` stop value.
- **Budget cap + lazy vectorisation** for very large relevant sets; the **tiered content peek**
  for poor-metadata grey lit at screen.
- **LLM-based screen tool** — `_stub_screen` is the deterministic stub; the real tool (LLM call
  with title/abstract → relevant/not_relevant/failed decision) is the deferred seam.
  `ScreenContext`, `ScreenResult`, and `source_screening_result` are durable and ready.
- **Thin-base re-search trigger** — `screen_decision_confidence` is stored and
  `re_searched_still_thin` is a valid `search_coverage_record.stop_condition` (task 007), but
  nothing fires it; the trigger that re-runs `search` when confident-relevant count is below
  threshold waits on the live backends (runtime-egress gate).
- **Re-screening** — a second result row for the same `(evidence_scope_id, project_source_snapshot_id)`
  pair is prevented by `uq_ssr_scope_source`; follow-on seam when re-screening is wanted.
- **`screen_failed` recovery loop** — `status='failed'` rows are representable; no retry logic
  built. Deferred until a real inference provider makes failure transient.
- **Graph-structured synthesis** — query-time multi-hop / community / contradiction-location over
  the findings graph (run-local → project-scoped persistent → graph datastore), gated on an
  entity-resolution-quality bar; **never** an ingestion-time global / cross-project KG.

## Search / acquisition (task 007 seams)

- **Live `SearchBackend` implementations** (OpenAlex, Overton) — **confirmed in-scope for
  v3.0** (user, 2026-07-05; header class 1 — the product cannot function without live
  search). The seam is built and both envelope mappings run against authentic recorded
  structure; wiring live HTTP is **runtime egress**, its own gated slice. Requirements carried from the v2 integration review (task 007
  contract): explicit request timeouts everywhere (v2's OpenAlex path could hang unbounded);
  a real Overton rate limiter (max 1 call/s, 429 + key-block on abuse — v2 had none); the
  OpenAlex query sanitizer (commas inside quoted phrases break queries) applied on the
  *production* path; per-provider result caps so the verbose provider can't crowd out grey
  literature; no sync HTTP inside async contexts. Security posture for the same slice: keep
  provider JSON out of top-level snapshot metadata (everything provider-controlled stays nested
  under `provider_fields` — the stub sentinels `_stub_*` and envelope keys share the top-level
  namespace); a third backend requires registering its mapper (`acquire_sources` rejects unknown
  backend names loudly rather than skipping their results).
- **Arm-B agentic search loop — the chosen query-derivation direction** (user, 2026-07-05;
  colleague R&D June 2026: v2 branch `search-experiment-pr`, PR nestauk/discovery_policy_atlas#184;
  presentation `docs/research-and-development/Search methods [Policy Atlas R&D] - June 2026.pdf`
  (internal, not published); handover `backend/testing/r_and_d/search_experiments/ONBOARDING.md`,
  maintainer Aidan Kelly). Iterative search with query reformulation from judged exemplars,
  citation snowballing (forward + backward), LLM-suggested-paper grounding, Thompson-sampling
  adaptive judging with a short-circuit stop, blend ranking (0.9·LLM-judge + 0.075·rerank);
  measured ~2× single-pass recall@k_est at ~$0.44/query, ~6 min. LLM- and egress-heavy → lands
  behind the LLM + live-backend gates. What 007 left ready: `SearchBackend` grows into the R&D's
  `SourceClient` shape (add citation-fetch / reference-fetch / title-grounding-lookup /
  optionally dense-search verbs + per-backend capability flags — additive to the protocol);
  N search calls per run already fit (per-call `search.executed` events + one per-run coverage
  record, queries by reference); `stop_condition` vocabulary grows by one-line CHECK migration
  (quota / exhausted / short-circuit are cousins of the deferred `saturated`). Snowball-discovered
  records enter as acquired sources through the same envelope + dedup. **Semantic Scholar** is
  the candidate third backend (Arm C was a close second; dense `/snippet/search`, `x-api-key`,
  ~1 req/s). An **Overton arm-B** is named future work (the presentation calls it a novel
  open-source contribution). The **Campbell/3ie/EPPI golden-dataset** recommendation belongs to
  the eval workstream (per data-model's judge-calibration ownership). Blend-rank + LLM-judge
  relevance belong to the screen / retrieval-rerank seams, not acquire. v2's central lesson
  stands recorded: a single LLM-generated boolean query is unstable/low-recall (v2 built a
  query-stability eval to prove it); its multi-query fan-out design + eval harness are the
  starting point when the seam opens. v3.0's intent-verbatim query is stable by construction.
- **User-selectable backend scope** (academic-only / grey-lit-only / both — v2 precedent; later
  possibly orchestrator-derived from the intent conversation) — lands as a Plan/Config field
  (its own public-interface gate) driving the `search_backends` parameter `run_harness` gained
  in task 007; nothing in v3.0 reads a selection, so no inert field shipped.
- **Per-backend query mode is a backend property, not one-size-fits-all** (user, 2026-07-05):
  v2 production ran semantic-only on Overton (`squery` + `min_similarity` — cheap) and
  boolean-only on OpenAlex (semantic exists there but costs more; v2 bet on query generation).
  To explore at the seam: a semantic/keyword mix per backend; whether Overton's semantic mode is
  already hybrid under the hood (unverified). The richer **Overton filters**
  (`source_country`/`source_region` with v2's region-label mapping, `source_type`, date bounds)
  sit at the same seam; v3.0 sends none (`scope_filters` stays `{}`, shape reserved on the
  coverage record).
- **Injection screening of acquired text** — posture recorded at task 007 (contract decision 9):
  acquired titles/abstracts/snippets are third-party text entering the corpus ("ingestion is not
  a tool"); v3.0's deterministic stubs never interpret them (security-review-confirmed), but the
  LLM screen/classify seams will — enforcement lands with those seams / the live backends.
  Overton's `llm_document_description`/`llm_document_theme` are provider-LLM text, persisted
  visibly (`abstract_source="llm_description"`; theme retained under `provider_fields`) and
  never mixed into document-own-words fields — when grounding lands, claims resting on
  `llm_description` text are flagged distinctly (flag-not-drop).
- **Downstream consumers of the acquired envelope** (API exploration, 2026-07-05): the LLM
  screen tool should read `abstract_source` (lower decision confidence on provider-LLM
  summaries; decide non-English handling — fixtures carry a non-English record); the LLM
  classify tool should consume structured provider priors (`record_type`, Overton
  `source.type`/`organisation_type`, provider topics) to cut `Unknown`s on acquired documents —
  classification quality gates appraisal coverage (all acquired docs are `Unknown` →
  `skipped_unknown` under the v3.0 stubs, honest but appraisal-empty); `is_retracted` is
  retained-but-unread — becomes a visible flag in the deferred appraisal second pass
  (flag-not-block); the small-sample-penalty deferral is now evidence-backed (neither API ships
  sample size).

## Full-text ingestion (task 008 seams)

- **Live `DocumentFetcher`** — **confirmed in-scope for v3.0** (user, 2026-07-05: the product
  cannot function as intended without live fetching), so this entry is *sequencing*, not
  scoping-out — unlike most of this file. The seam is built (protocol +
  `run_harness(document_fetcher=…)`); wiring live HTTP is **runtime egress**, its own gated
  slice. Requirements carried from the 008 contract + review stack (pre-registered so they
  aren't rediscovered in production):
  explicit timeouts, redirect handling with an explicit protocol policy (SSRF posture for
  provider-supplied URLs), politeness + per-host rate limiting, retry/backoff, content-type
  sniffing (a PDF served as `application/octet-stream` must not fall through to the plain-text
  parser — magic bytes, not headers) and charset handling (v3.0 decodes HTML as UTF-8-replace;
  honour the declared charset or pass bytes to trafilatura), landing-page scrape + PDF-link
  discovery, DOI-URL fallback, a **paywall-detection signal ladder** (v3.0 maps only HTTP
  401/403) with an OA-status cross-check, per-link exception isolation (a fetcher raise must
  become a reason-coded outcome, not a component failure — fail-loud is correct fixture-world,
  wrong live), bounded in-flight buffering / streaming (parent-side bodies are unbounded per
  cascade round today; fine at 24 fixture docs, an OOM risk live) and concurrent fetching
  (v3.0 fetches serially in the parent — fine for fixture replay, sum-of-latencies live), and
  a worker-side / OS-level egress guard in the test suite (the socket-deny test now covers
  parent + workers; an `unshare -n`-style CI guard is the stronger durable control). A
  `pip-audit`-style dependency check belongs in CI now that binary parsing deps (pymupdf,
  lxml) are in the tree — CI config is its own gate. **Fixture-corpus relocation** (user
  decision, 2026-07-05): the ~24 MB committed corpus ships inside the package only because
  replay *is* the v3.0 product behaviour; when the live fetcher takes over as default, move
  the documents out of `src/policy_atlas/data/fulltext/` (to `tests/` or a pinned-hash
  release asset) so the wheel slims — the corpus itself stays in the repo as the
  deterministic test substrate. Growth is capped meanwhile by a test-enforced ≤30 MB budget
  (`test_licence_guard`); raising the cap means consciously choosing the corpus strategy.
- **Concurrent-run write guard** — eligibility selection takes no row locks and final writes
  are unconditional, so two simultaneous ingest runs over **one scope** could interleave
  (mirrors 007's concurrent-run dedup note; Codex adversarial finding, task 008). Scoped
  precisely (user question, 2026-07-05): the load-bearing invariant is **at most one active
  run per project**, not a single-process deployment. Everything the pipeline components
  mutate is project-scoped (eligibility filters on `project_id`; updates hit
  `project_source_snapshot`; result-table unique constraints are per-scope; the event-log
  sequence is `(project_id, sequence)`), so a **multi-user web app with users on different
  projects is already safe** — the spec's "single active writer" is a per-project property.
  The hazard is two writers on the *same* project (double-submit, retry racing the original,
  two queue workers claiming one run). **Pre-registered requirement for the web-app /
  durable-execution slice:** enforce one-active-run-per-project at run dispatch (Postgres
  advisory lock on project id, or a partial unique index allowing one `running` run per
  project) — or add row-level guards (`SELECT … FOR UPDATE` / status-guarded `UPDATE … WHERE`)
  in the components.
- **ML-layout parse escalation (docling)** — the quality tier for documents where pymupdf4llm's
  font-size heading heuristic fails. Observed at 008's /verify: four heading-light academic
  PDFs (Nature Comms ×2, Frontiers ASHP, PLOS) collapse into 2–3 very large chunks — content
  complete and locators honest, but exactly the heuristic-vs-ML gap this seam exists for; gate
  escalation on parse-quality evals. Sizing note: docling on CPU misses the couple-of-minutes
  wall-clock target (~5–20 min fanned out per ~100 docs) — GPU (AWS) sizing is part of this
  seam. The **pymupdf-layout tier is licence-blocked** for distribution: PolyForm
  Noncommercial / Artifex commercial — a further restriction AGPL-3.0 §7 cannot carry
  (investigated 2026-07-05; offline operation proven, so it slots in here if commercial
  licensing is ever bought). The determinism source-patch
  (`_install_deterministic_column_boxes`) deliberately no-ops if upstream's source changes —
  the fan-out determinism test is the backstop, the pin floor is `>=0.3.4`, and an upstream
  bug report is filed as follow-up. Task-011 pointer: extraction yield/failure rates on the
  collapsed-chunk PDFs (extract handles them via deterministic oversize subsegment splitting,
  so the full-read guarantee holds) are the **first downstream consumer signal** for gating
  this escalation — the parse-quality eval now has a measurable customer.
- **Time-budget-aware parser selection** — the user's stated time horizon picks the parser
  (tight → pymupdf4llm, long → ML layout); `parse_profile`-per-snapshot (ADR 0004) is the hook.
- **Chunk-volume bias controls at the retrieve seam** — full-text documents contribute tens of
  chunks vs one abstract chunk; per-document caps / MMR / document-grain grouping when
  retrieval lands. Token-budgeted re-chunking at the embed seam subdivides the oversized
  heading-light sections above regardless.
- **OCR for `no_text_layer` documents** — scanned-only PDFs are reason-coded and kept, never
  parsed; an OCR tier (with its own honesty label) is the follow-on. Text-layer detection is
  Unicode-aware (`\w`), so non-Latin scripts don't false-positive into this bucket.
- **Vectorisation at the first vector reader — DISCHARGED ahead of the reader (task 009,
  approved exception).** The eager-and-uniform discipline (EB components §4) now runs: every
  chunk on all three ingestion paths gets unit-grain vectors (`embedding_unit_policy_v1`,
  ~2000-char sentence-boundary units, ~200-char overlap, one vector per unit, offsets into
  the untouched canonical chunk) via the `EmbeddingBackend` seam, live
  `text-embedding-3-small` behind the runtime-egress gate. The *reader* (retrieve/pgvector)
  is still the deferred piece — see the 009 section below. Token-budgeted re-chunking of
  oversized heading-light sections remains at the embed/eval seam.
- **Multi-PDF Overton assembly** — `grouped_pdf_ids_in_result` is retained; v3.0 ingests the
  primary `pdf_url` only.
- **Injection-screening posture extended to fetched full text** — same posture as acquired
  abstracts (007 entry above): full-text chunks are third-party content-of-record; nothing in
  v3.0 interprets them; enforcement lands with the LLM seams that read them.
- **Cross-project full-text snapshot reuse** — same shape as the acquired-envelope dedup entry
  (Data model section): `source_snapshot` is project-free, so reuse is additive. Note: today
  concurrent ingest of one document in two projects merely duplicates snapshots (wasteful, not
  corrupting); the reuse seam turns that into the system's first genuinely **cross**-project
  write race (two projects deduping onto one snapshot) — that slice inherits the concurrency
  design, alongside the per-project run guard above.

## Characterise / embeddings / telemetry (task 009 seams)

- **EB artefact composition — LANDED with revised ownership (task 013, ADRs 0009 + 0010).**
  Synthesise (not the orchestrator) composes the one EB artefact at the run terminus —
  capability-composes; the orchestrator shapes sections at plan time. What remains
  deferred is the **composition-conventions** seam (block ordering/summary/key-findings
  conventions beyond proposal-order binding; citation renumbering-by-first-appearance —
  the V2-autopsy composition-seam note) and supersede + lock-on-advance versioning
  (blocks ship at `version=1`).
- **`retrieve` / pgvector / hybrid retrieval — first increment LANDED (task 013).**
  The 009 vectors' first reader is synthesise's scoped `search_chunks` tool: in-memory
  hybrid (cosine + lexical, RRF-fused) over JSONB vectors, guarded by a fail-closed
  `RETRIEVAL_UNIT_CAP` (20k units — beyond it the component fails structurally naming
  the cap, never a degraded sample), behind a swappable helper seam. Still deferred:
  **corpus-scale retrieval** (beyond the cap, or over unscreened content) and the full
  index-backed `retrieve` tool — pgvector-vs-alternatives, retrieval profiles,
  storage migration, and the chunk-volume-bias controls (per-doc caps / MMR /
  doc-grain grouping, 008 entry). Also at this seam: **judge-envelope widening +
  re-gather repair** (the repair alternative that re-gathers targeted evidence needs
  `retrieve`; v1 repair is reword-down over already-gathered evidence only).
- **Contextual retrieval, late chunking, exact-token budgeting, semantic re-chunking** —
  retrieval-eval seams on the embedding-unit layer (contract decision 2, rev-8 research).
  The unit policy is versioned (`embedding_unit_policy_v1`) so any of these lands as a new
  co-existing policy, not a rewrite.
- **Embed-pass live robustness** — fixture-scale is single-batch; pre-registered for real
  corpora: rate-limit backoff under real 429s (the SDK retries transient failures at
  `max_retries=2`, so the HTTP ceiling is (1+retries)× the logical call budget — comment at
  the client seam), batch-failure isolation granularity (one bad unit currently fails every
  chunk sharing its 128-unit API batch — transient over-reporting only, failed chunks
  re-embed next pass; split-on-failure lands here), and concurrent multi-batch behaviour at
  n ≫ batch (review adjudication, 2026-07-06).
- **Very-large-corpus grouping** — discovery currently reads all titles+abstracts in one
  call; the scale seam is discovery-sampling and/or embedding-based clustering over the
  landed chunk vectors (contract decision 4). Assignment already scales (batched,
  concurrent, budget-enforced).
- **Grouping-quality + adversarial-content evals** — theme quality is *not* asserted by
  the build (sanitized fixture corpora make it meaningless by construction); the eval seam
  owns: quality bars, adversarial/injection-shaped corpora beyond the shipped unit tests,
  **zero-support theme pruning** (discovery can emit themes assignment gives no members;
  they persist honestly with `size: 0` — pruning is a quality call, review adjudication
  2026-07-06), and a **two-scopes-one-project coverage fixture** (semantics verified
  correct, untested combination).
- **TopicGPT extensions** — topic refinement (merge/split against assignment evidence) and
  quotation-verified assignment, at the grouping-quality eval seam (contract § Research
  grounding).
- **Provider-signal prompt enrichment** — provider topics as per-doc grouping hints;
  taxonomy-bias risk → enters via the eval seam, never as a silent default.
- **`group`-component inheritance — discharged (task 012)** — v2's theming lessons
  transferred when `group` was built; each recorded defect closed structurally: dead
  critique stage → no critique stage built (one schema-constrained partition + one
  validated repair is the entire call surface); silent concept drops → code-enforced
  exhaustiveness (counted `ungrouped`/`no_value` residuals, sum identities
  test-enforced); "General Theme" collapse → exact forbidden-generic-label validation
  rejects the response (prompt negative rule *and* code check); no scale guard →
  fail-closed `FACET_VALUE_CAP`; unseeded runs → deterministic sorted value
  ordering/ids (identical inputs yield identical prompts).
- **Tag namespace consolidation** — pruning/merging accreted `source_tag` assertions
  (re-runs accrete by design; provenance classes never merge) — an orchestrator-seam
  follow-on once real tag spaces emerge (contract decisions 5, 10). A third search backend
  also registers its tag extractor next to its mapper — `_provider_tags` dispatches by
  backend name and silently yields no tags for unknown names (`_MAPPERS` and the tag
  branches are two structures today; unify or add exhaustiveness enforcement when backend
  #3 lands — review adjudication, 2026-07-06).
- **Langfuse follow-ons** (decision 13 ships the baseline: env-gated client, full-I/O
  spans, in-span scores, no-op with nothing configured, loud on partial config / missing
  host): runtime prompt-registry deployment (labels/environments, emergency-edit
  reconciliation), retention/sampling/masking/access policies, trace→eval-dataset
  promotion, and **two detached-trace warts** (span content complete in both; verified
  against the live instance, 2026-07-06): (a) OTel context does not propagate into
  `ThreadPoolExecutor` workers, so the first concurrent `assign` call surfaces as a
  detached trace — fix is context capture/attach at submit; (b) the **upload-ingest embed
  pass** runs outside any `component_span` (`ingest_upload` is app-boundary, not a run
  component), so its `embed:batchN` observations mint their own root traces — resolves
  with the upload audit-event seam below, which gives uploads their own observability
  surface.
- **Steering modes / landscape→synthesis steer-point pause** — plan-as-object machinery;
  the payload it relays (the structured landscape summary in `component.completed`) ships
  now (contract decision 8). The deepening-selection steer-point's read surface followed
  in task 010 (see the Select section).
- **Dual-view coverage** — corpus-view vs evidence-view distributions need the
  source/evidence policy object (contract decision 9); v3.0 ships single-view with the
  explicit `base` ladder and **no absence claims** (test-asserted).
- **Bedrock routes** — both seams (`EmbeddingBackend`, `ThemeGroupingBackend`) swap
  implementations; first pass OpenAI → target Bedrock is the documented v3.0 posture.
- **Upload audit-event seam** — when the web-app slice gives uploads a real surface they
  get their own audit event + observable processing (incl. embed counts, currently a
  structured log line `ingest_upload.embed_counts`) — an app-boundary event, not a run
  component (user Q&A at the 009 plan gate). Its tracing rides along: a live upload's
  embed batches currently surface as detached root traces (no surrounding span — wart (b)
  in the Langfuse entry above); the seam wraps them in an upload-scoped span.

## Select (task 010 seams)

- **Deepening-selection steer-point pause** — the mode-governed pause (Frequent/Moderate/
  Minimal routing, escalation UX) is plan-as-object machinery; its **read surface shipped in
  010**: the bidirectional rationale (always logged) and the computed trigger flags —
  `large_stratum_excluded`, `priority_stratum_excluded` (the hardest: a user-nominated
  stratum with zero selections), `must_include_conflict`, `thin_base` (honestly
  stub-constant until the LLM screen tool lands), `thin_full_text` (extraction-shaping).
  The pause slice reads these flags; no new signal computation needed.
- **Agent-authored directives** — the capability agent authors the `SelectionDirective`
  **just-in-time at invocation, post-characterise** (plan-as-object § forecast-vs-commit:
  the up-front plan is a non-compiling forecast, never the executed directive). v3.0
  sources the directive from `evidence_scope.context["selection"]`; the `select` facade
  signature is deliberately the tool call the agent will make, so arrival is a
  parameter-authoring change, zero re-plumbing.
- **Rerank-quality evals** — deterministic-ranked vs LLM-reranked selections compared on
  downstream yield once extract gives selection a consequence; the eval-ready Langfuse
  traces (full I/O, `rank_batch_valid` scores) exist now. **Listwise ordering** (the model
  emits a ranking, not per-doc scores) is the known-better method with a cross-batch merge
  cost — it lands at this seam, competing with the shipped pointwise 0–10 +
  composite-tie-break baseline.
- **Embedding-relevance for select — declined seam** (010 contract rev 4): by select time
  the semantic dimension is spent twice (screening judged relevance; stratification grouped
  semantically), so within-stratum cosine-to-intent discriminates weakly. Revisit **only**
  if rerank-quality evals show the deterministic composite/fallback needs a semantic leg.
  The 009 chunk vectors' first reader remains `retrieve`, unchanged.
- **Cross-encoder relevance models (Cohere-class, available on Bedrock)** — they score
  query-relevance, not purpose-fit: recorded at the **`retrieve` seam** (retrieval's
  rerank upgrade), deliberately not select's.
- **Capability-run entity** — a durable run spanning components (today one run = one
  component execution; the chain order lives only in `skeleton.py`, the agent's stand-in).
  The recorded Langfuse detached-trace warts (009's executor threads; 010's `rank:batch`
  generation spans) are early symptoms of this gap; fix belongs here, not per-component.
- **Policy soft-prior tilt** — integration shape recorded, not deferred-blind: when the
  source/evidence policy object lands, it **compiles into directive boosts**
  (provenance-stamped as policy-sourced), becoming one more directive author beside the
  user and the capability agent. Select's code is untouched by construction — the boost
  surface is the ground-up design for it.
- **Selection-diversity extensions** — publication-country stratification and
  study-geography/population diversity dimensions: the spec itself marks them rough,
  cluster-approximated and properly post-extraction.
- **Second `select` strategies** — Transferability dependency-scoping et al. (other
  capabilities' problem); the strategy registry validates exactly the two built-ins.
- **Suite-wide socket deny** (010 security-lane note) — per-test socket-deny helpers now
  exist three times (008/009/010 patterns); `pytest-socket` (deny by default, allowlist
  the DB host) is the structural defense-in-depth upgrade.

## Extract / findings layer (task 011 seams)

- **The extraction service + evidence dataset snapshots** — profile resolution against
  existing records, per-source task objects, capability commits declaring extraction
  profiles, and pinned point-in-time dataset consumption. 011 shipped the minimal honest
  form: a per-document extraction record with a partial-unique memo key over the success
  states, checked before any call; EB's profile is the named constant `eb_iof_base_v1`.
  `group` will read the run roll-up (`extraction_result` by `extraction_run_id`), not a
  pinned dataset, until this seam lands.
- **Extraction-quality evals** — finding-level ground truth over the fixture corpus; the
  slice's bar was machinery correctness, schema fidelity, honest coverage accounting and
  verified anchoring — extraction *quality* (right/complete findings) is unmeasurable
  without this. Gates most seams below; also **unblocks 010's recorded rerank-quality
  eval seam** (same eval workstream).
- **Multi-pass recall extraction** (contract rev 1.3) — a second identical-prompt pass
  raises recall on long documents (LangExtract's recipe: char-interval overlap merge,
  first-pass-wins recorded at the seam); can't be measured without ground truth →
  eval-gated. `extraction_provenance.pass_count` records 1 from day one so the seam opens
  cheaply. One named recall gap for the evals to weigh (011 review, Codex): when a single
  segment fills a whole window, the greedy windowing must advance without overlap (the
  no-regress progress guarantee), so a claim spanning the boundary between two
  window-filling chunks is never seen whole by any one call.
- **Retrieval-augmented extraction** (contract rev 1.1c) — full read + targeted in-doc
  retrieval repair / cross-window context assembly (incl. cross-window naming consistency,
  cut at rev 1.2). Composable and legitimate — the full read licenses coverage — but
  eval-gated behind `retrieve` + extraction-quality evals showing a field-completeness gap
  on multi-window documents.
- **Retrieval-scoped extraction — declined** (contract rev 1.1b) — reading a retrieved
  subset makes `no_findings`/`not_extracted` unverifiable (a silent new base-ladder rung —
  false-absence machinery EB exists to prevent) and inverts the recall-critical trade. Any
  future retrieval scoping must be an explicit, recorded coverage-base rung, never silent.
- **Generic finding container — declined** (contract rev 1.1a) — typed tables with
  CHECK-enforced vocabularies won ("coherent typed record, dimensions intact and
  queryable"); revisit only if a third finding schema is specced.
- **Reason-then-constrain extraction** (rev 1.3) — draft free-form then bind to schema;
  demonstrated gains are on small open-weight models and closed-weight API models resist
  the format tax; eval-gated remedy if judgment-heavy fields show errors.
- **LangExtract dependency — declined** (rev 1.3) — techniques absorbed (raw-offset span
  recording, negative rules, pre-flight example validation, multi-pass merge recipe); the
  library itself is Gemini-first and outside our provenance model.
- **Per-intervention focused-call decomposition** (rev 1.4) — V2's cross-contamination
  remedy (one intervention per call); eval-gated remedy if quality evals show cross-finding
  contamination in the per-doc call. Same trigger family as multi-pass.
- **Bounded fuzzy quote fallback** (rev 1.4) — LangExtract's coverage+density-gated LCS
  tier, fuzzy-only-on-failure; adopt only if evals show exact+normalised recall
  insufficient, and never inside the verified-verbatim guarantee (a fuzzy match can flag,
  never verify).
- **Failed-extraction recovery loop** — beyond the in-run window retry, a failed doc
  re-enters via a new run (the screen_failed precedent); failure rows are attempt history
  and never block the memo. A dedicated recovery sweep is unbuilt.
- **Cross-window dedup** — windows are independent; the 1-chunk overlap can in principle
  yield near-duplicate findings across windows that exact claim-key dedup already collapses
  when identical; heuristics beyond that are out until observed in practice (the contract's
  stop condition: bring it back to a plan gate, never grow silently).
- **Hybrid-indexing of `intervention`/`outcome`** — committed for v3.0; the mechanism is
  the `retrieve` adapter's second index target and lands with `retrieve`. Columns are
  filterable now.
- **Mixed/unclear findings are first-class — requirement carried forward** — V2 extracted
  `mixed`/`unclear` effect directions and then aggregation silently zeroed them;
  flag-not-drop must survive the whole deep chain: `group` and `synthesise` must carry
  these findings, never discard them at aggregation.
- **Intra-run shared-basis-snapshot memo** — two selected docs whose basis resolves to the
  *same* content-keyed snapshot (identical full text dedup'd across docs) would both
  fresh-extract and collide on the memo key (IntegrityError → honest loud failure).
  Impossible with the current corpus (pss is unique per project+snapshot; full-text
  snapshots are per-doc); if content-hash full-text dedup ever lands, add an in-run memo
  update so the second doc reuses the first's record. Same posture for **concurrent
  extract runs** over the same project/fingerprint (011 review, Codex): the memo read is
  not atomic with the insert, so two simultaneous runs can both extract fresh and the
  second fails loudly on `uq_ser_memo` — wasted spend, never corruption; a single-writer
  operating model makes this a non-path today.
- **Evidence type is prompt input but not a memo/record key component** (011 review,
  Codex) — `primary_evidence_type` conditions the extraction prompt, yet the memo keys on
  (project, basis snapshot, fingerprint) only and the record does not store the evidence
  type used. Unreachable today: classification is insert-once per (scope, doc) and the
  skeleton orders classify before extract — the only trigger is a hand-rolled plan that
  extracts *before* classifying (docs extract as "Unclassified" and memo-reuse after
  classification lands). If such plans become supported, record the evidence type on
  `source_extraction_record` and make memo hits require a match.
- **Per-run window/call ceiling** (011 review, security) — the enforced call budget is
  `windows × (1 + retry_cap)`, which scales with document length; there is no absolute
  per-run cap, so a pathological oversized corpus drives spend linearly ("within
  budget"). Bounded today by `select`'s budget (the designed cost control) and the
  fixture corpus. If arbitrary corpora land, add an absolute window ceiling as a
  fingerprint component with a per-doc `window_cap_exceeded` failure reason.
- **Prompt envelope fencing** (011 review, security) — segment text enters the prompt as
  id-keyed JSON data records, but the envelope title/abstract are interpolated inline in
  the user template, so a hostile abstract can structurally spoof the template around
  them (impact bounded: wrong findings for its own document, quotes still
  verified-or-flagged). Fence the envelope as a JSON data object at the next
  `extract_iof_v1` version bump — prompt changes are eval-blind until the
  extraction-quality evals exist, so this deliberately does not ride the review phase.
- **`thin_extraction` roll-up flag** — named in the contract "where computed"; no
  definition was pinned and v1 deliberately does not compute it. Define (e.g. findings per
  extracted full-text doc below a floor) when a consumer needs it.

## Group / facet-level theming (task 012 seams)

- **`query-findings` tool — DISCHARGED in full (task 013).** The scoped read tool landed
  with its deliberative consumer exactly as recorded: agent-invoked in synthesise's
  section loop (`make_findings_reader` behind the closed tool set), deterministic and
  project/run-scoped. Group's deterministic read stands unchanged; the 012 deviation
  from components §8's tool table is closed.
- **Facet-grouping quality evals** — extends the 009 grouping-quality eval seam:
  partition coherence/usefulness on real reference sets, negative-rule adherence beyond
  the shipped unit tests, and **`FACET_VALUE_CAP` calibration** (150 is plan-pinned; the
  eval owns the real ceiling). The 012 bar was machinery correctness, exhaustiveness
  invariants, honest residuals and provenance fidelity — grouping *quality* is not
  asserted by the build.
- **Large-corpus grouping algorithm** — beyond the fail-closed `FACET_VALUE_CAP`
  (`value_cap_exceeded`, loud, never a degraded pass): tail-group-capable discovery
  and/or embedding-assisted value clustering over the landed chunk vectors. Eval-gated —
  a head sample cannot discover tail-only groups, which is why the sample-discover/assign
  shape was rejected at contract rev 1.3 and stays rejected until evals exist.
- **Agent-authored grouping directive** — the same seam as select's agent-authored
  directives (above): the capability agent authors `context["grouping"]` just-in-time at
  invocation; the `group` facade signature is already the tool call, so arrival is a
  parameter-authoring change, zero re-plumbing.
- **Cross-schema reference-mediated linkage** — activates with
  `implementation_context_finding` (EB internals entry): the shared source-named
  vocabulary means a facet group's member values can link findings across schemas by
  reference. 012 ships the design property (source-named values, run-referenced
  groupings), no linkage machinery.
- **Re-grouping / steering UX** — a different facet is simply a new run with a different
  directive (shipped semantics); mode-governed steer-points around grouping (pause,
  re-group, facet-switch UX) are plan-as-object machinery at the standing steering seam.
- **Facet-theme promotion** (012 contract rev 1.2) — canonical/queryable facet groupings
  for downstream capability agents. The data-model's staged ladder: run-local (shipped —
  rung 1) → project-scoped persistent → graph datastore, gated on an
  entity-resolution-quality bar (a facet-group label bundling different sources' strings
  asserts cross-source identity, often question-relative — never trusted canonically
  before that bar exists). Options Assessment reads run-referenced groupings by
  `grouping_run_id` until then.
- **Shared traced-call helper across OpenAI backends — DISCHARGED (task 013).** The
  recorded trigger fired: `tracing.traced_call` factors the shape and all five OpenAI
  backends (`extraction_backend.py`, `ranking.py`, `facet_grouping.py`,
  `synthesis_backend.py`, `grounding_judge.py`) ride it, heterogeneous call-sites
  preserved (ranking's in-span trace score via the `after` hook).
- **Harness failure-event append dies inside an aborted transaction** (012 live check,
  standing behaviour — predates 012, affects every component): a server-side DB error
  mid-component leaves the connection's transaction aborted, so `_run_scope_component`'s
  `component.failed` event INSERT itself fails (`InFailedSqlTransaction`) — the run dies
  loudly but without its failure event recorded. Fix belongs in the harness (append the
  failure event on a fresh transaction/rollback first); repo-wide, not group-specific.

## Synthesise (task 013 seams)

- **Plan-compile section machinery** — the fail-closed `context["synthesis"]` directive
  (sections + retrieval_boosts, normative grammar per contract rev 8 M5) is the compile
  target the future plan-shaped-sections machinery and the source/evidence policy compile
  into (the 010 pin); nothing compiles into it yet.
- **Cross-encoder chunk reranking** — the `ChunkRerankerBackend` stage ships pass-through
  (`reranker: "none"` recorded in provenance); the live Bedrock Rerank backend + its
  `run_harness` injection point land with the Bedrock integration slice (the retrieval
  contract's inference-trust-boundary line; the 010 Cohere-class note). No public kwarg
  ships while nothing live exists — the V2 dead-config lesson.
- **Content-scan pattern claims** (contract rev 8 M9) — the spec's soft pattern rung ("a
  shape the agent reads across the corpus") is prohibited in v1: no deterministic
  validator and no judge-lane fit exists yet; a cross-corpus-shape assertion without
  computable counts rejects, and the prompt says so. The type arrives with its
  verification mechanism, never silently absorbed.
- **Policy-conditioned citable-bar flagging** — the source/evidence policy's citable bar
  applies flag-not-block; v1 honours the rule through the weakly-grounded mechanism only.
  Policy-conditioned flagging (below-policy support visibly flagged as such) lands with
  the policy surface.
- **Block summaries / artefact summary / faithfulness judging** — the navigation layer
  (provenance-grounding § Summaries): co-versioned block summary column, the artefact
  summary field, flat faithfulness judging. Blocks ship summary-free at `version=1`.
- **Synthesis structure discovery** (contract rev 7.2 — declined-for-now bundle):
  recon-informed section proposal, structure-mismatch signals, a bounded revision
  checkpoint. Revisit with evidence if one-shot sectioning proves a real problem on live
  corpora.
- **Regeneration-time coherence** — the data-model's original seam: a coherence pass when
  blocks regenerate. Deliberately not a write-time pass — the rolling claim ledger owns
  write-time coherence (rev 7.2).
- **Synthesis / judge / retrieval quality evals** — the eval workstream owns judge
  calibration (clean/weak line, repair round count), section/prose quality, retrieval
  quality, and the calibration of every plan-pinned constant (`SECTION_CAP`,
  `SECTION_TURN_CAP`, `SYNTH_CHUNK_TOP_K`, `SYNTH_CHUNK_CHAR_BUDGET`,
  `RETRIEVAL_UNIT_CAP`, `REPAIR_ROUND_CAP`, retrieval-boost weights, the `lookup`
  vocabulary). The 013 bar was mechanism correctness, invariant enforcement, honest
  flags and provenance fidelity; the field's loudest warning (rev 7.3 scan) — shipping
  without an eval harness — makes this the recommended next slice.
- **Artefact capability-discriminator + versioning grain** — `synthesis_result` is the
  run-scoped roll-up pointing at its artefact; future capabilities mint artefacts into
  the same 001 substrate with their own roll-ups. The discriminator column and the
  versioning grain arrive with their first readers.

## Data model / evidence

- **`supersedes` edge on `source_snapshot`** — human-asserted pointer from a corrected re-upload
  to its predecessor; deferred until the re-upload UX is scoped. The schema shape (content-addressed
  snapshots without project_id) already supports it; no data migration needed.
- **Content-hash dedup for acquired cross-project snapshots** — the schema shape supports sharing
  (no `project_id` on `source_snapshot`); task 007 built **project-scoped** dedup only (three
  guards: `backend_record_id` · normalized DOI · content hash, preloaded in-memory per call).
  Cross-project snapshot reuse, **fuzzy near-dup matching** (title similarity — DOI-only
  cross-backend identity in v3.0), and **concurrent-run dedup hardening** (two simultaneous
  acquire runs for one project could double-insert past the in-memory preload; a DB-level guard
  is a gated schema change; v3.0 execution is single-process/serial — Codex adversarial finding,
  task 007) are the follow-ons.
- **LLM-as-judge grounding tier on `citation`** — `citation.verification_result` is set by the
  deterministic verbatim quote-presence check only; the full grounding tier classification
  (confident / uncertain / fabricated) is deferred to when a real inference provider lands.
- **Boundary-spanning quote → `citation_chunk` join table** — task 013 pins the interim
  shape within the approved schema (contract rev 8 B2): a boundary-spanning verified quote
  writes **one citation row per spanned chunk** (same annotation, same quote; exact span
  offsets on the annotation payload — the 011 anchor precedent). The join-table
  normalisation remains the recorded seam. (The 001 echo path's first-matching-chunk
  behaviour stands until that path is retired.)

- **`Library`** (curated cross-project collection: per-user → team/org) and **`Connected`**
  (auth'd departmental-repository ingest) — the public/acquired dedup slice is *un*-deferred; the
  curated collection + access layers are not. **Source-class lifecycles** stay collapsed to
  `origin`.
- **Source-document versioning lifecycle** beyond immutable snapshots + a human-asserted
  `supersedes` edge — diffing, upstream-change monitoring, automatic propagation.
- **Open-web `search` backend** (trust class: untrusted open web) — behind the same `search` verb,
  declaration-scoped, with mandatory injection screening; ingests as frozen chunks (no
  cite-the-live-web path).
- **Cross-project finding reuse** (sits next to the rejected global KG).
- **Editing UX** — human amendment is representable in provenance now; the editing *UX* is
  deferred to user testing.
- **Support-direction relations** (supports / caveats / contradicts) + user counter-evidence
  search.

## Execution / collaboration / ops

- **Branch-level parallelism** — intra-run parallel branches with a check-in blocking only the
  dependent sub-graph; a dedicated durable workflow engine; durable timers. (Within-step
  data-parallel fan-out is **retained**, not deferred.)
- **Formal sign-off / clearance workflow**, **artefact-scoped permissions / full RBAC**,
  cross-project nudges.
- **Per-item sensitivity gates & egress control**, **private / self-host deployments** — return
  when a sensitivity label drives concrete behaviour (block / approve / generalise / route /
  private deploy).
- **Formal SLO/SLA, incident process, canaries, live drift monitors, product analytics**, and a
  committed **judge calibration scheme** (owned by the eval workstream; v3.0 only persists judge
  I/O for eval-readiness).
- **Time/cost estimate model** (the plan drives an estimate; the model is deferred — a coarse band
  suffices in v3.0).
- **Forecast/prewarm extraction** — modelled only if built (no inert forecast object otherwise).
- **`structlog.contextvars.bind_contextvars` for ambient run/project correlation** —
  `logging.py` wires `merge_contextvars` into the processor chain but nothing calls
  `bind_contextvars`, so every log call must manually repeat `project_id`/`run_id` and most
  don't (e.g. `harness.py`'s `component.started`/`grounding.failed`). Bind once per run/component
  instead of threading kwargs through every call site. Also: exceptions are logged as `error=str(exc)`
  with no type/traceback, and the processor chain has no `exc_info`/traceback renderer to make
  `exc_info=True` useful even if added.
