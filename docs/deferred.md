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
  (appraise component 4).
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
- **`appraise` and all subsequent EB components** — subsequent slices.
- **`implementation_context_finding`** — the second reusable finding schema (mechanisms, barriers,
  implementation conditions); cross-schema linkage is reference-mediated via `group`.
- **Saturation-based search stopping** (iterating retrieval↔screen until no new relevant docs);
  `saturated` is not a v3.0 `search_coverage_record` stop value.
- **Budget cap + lazy vectorisation** for very large relevant sets; the **tiered content peek**
  for poor-metadata grey lit at screen.
- **LLM-based screen tool** — `_stub_screen` is the deterministic stub; the real tool (LLM call
  with title/abstract → relevant/not_relevant/failed decision) is the deferred seam.
  `ScreenContext`, `ScreenResult`, and `source_screening_result` are durable and ready.
- **Thin-base re-search trigger** — `screen_decision_confidence` is stored; the trigger that
  re-runs `search` when confident-relevant count is below threshold hits the runtime-egress hard
  gate. Deferred until the search backend lands.
- **Re-screening** — a second result row for the same `(screening_scope_id, project_source_snapshot_id)`
  pair is prevented by `uq_ssr_scope_source`; follow-on seam when re-screening is wanted.
- **`screen_failed` recovery loop** — `status='failed'` rows are representable; no retry logic
  built. Deferred until a real inference provider makes failure transient.
- **Graph-structured synthesis** — query-time multi-hop / community / contradiction-location over
  the findings graph (run-local → project-scoped persistent → graph datastore), gated on an
  entity-resolution-quality bar; **never** an ingestion-time global / cross-project KG.

## Data model / evidence

- **`supersedes` edge on `source_snapshot`** — human-asserted pointer from a corrected re-upload
  to its predecessor; deferred until the re-upload UX is scoped. The schema shape (content-addressed
  snapshots without project_id) already supports it; no data migration needed.
- **Content-hash dedup for acquired cross-project snapshots** — the schema shape supports sharing
  (no `project_id` on `source_snapshot`), but the dedup lookup logic for the `acquire` path is a
  follow-on slice.
- **`search_coverage_record` table** — required to make honest absence claims ("we searched X and
  found nothing relevant"); deferred to the `acquire` slice where it becomes load-bearing.
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
