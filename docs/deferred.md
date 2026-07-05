# Deferred seams

Recorded, not built in v3.0 — seams left open per "build light, leave seams." Each is a real
architectural decision to defer, not an omission. Sources: architecture reference §§3–11
(Appendix A; Appendix B), briefing Appendix A, EB build spec, EB handoff §7. Grouped by area.

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
  strength Y") and divided-evidence *direction* verdict (synthesise component 9).
- **Relative-to-feasible appraisal tier** + the **full two-stage appraisal pass** (richer
  full-text methods/risk-of-bias on the selected subset) + modifier-tag-driven rubric dimensions
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
- **`open_tags` population** — the column exists and the `ck_scr_open_tags_array` constraint
  enforces the array type; the LLM classify tool will populate it. Stub always returns `[]`.
- **Open tag namespace consolidation / dedup / type management** — follow-on once the LLM tool
  populates `open_tags` and the tag space emerges from real data.
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
  implementation conditions); cross-schema linkage is reference-mediated via `group`.
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

- **Live `SearchBackend` implementations** (OpenAlex, Overton) — the seam is built and both
  envelope mappings run against authentic recorded structure; wiring live HTTP is **runtime
  egress**, its own gated slice. Requirements carried from the v2 integration review (task 007
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
  bug report is filed as follow-up.
- **Time-budget-aware parser selection** — the user's stated time horizon picks the parser
  (tight → pymupdf4llm, long → ML layout); `parse_profile`-per-snapshot (ADR 0004) is the hook.
- **Chunk-volume bias controls at the retrieve seam** — full-text documents contribute tens of
  chunks vs one abstract chunk; per-document caps / MMR / document-grain grouping when
  retrieval lands. Token-budgeted re-chunking at the embed seam subdivides the oversized
  heading-light sections above regardless.
- **OCR for `no_text_layer` documents** — scanned-only PDFs are reason-coded and kept, never
  parsed; an OCR tier (with its own honesty label) is the follow-on. Text-layer detection is
  Unicode-aware (`\w`), so non-Latin scripts don't false-positive into this bucket.
- **Vectorisation at the first vector reader** — eager-and-uniform discipline restated in EB
  components §4 (008 spec clarification): embed at ingest *when the first vector consumer
  lands*, with token-budgeted chunk sizing decided there.
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
- **Boundary-spanning quote → `citation_chunk` join table** — when a verified quote spans two
  chunks the current implementation assigns `citation.chunk_id` to the first matching chunk or falls
  back to `chunk_ids[0]`; replace with a `citation_chunk` join table when a real provider lands.

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
