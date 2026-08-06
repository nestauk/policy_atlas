# Read-model additions (plan-gate list — contract § Constraints, strand gates)

The adjudicated output of the plan-time audit (fast-fanout audit 2026-07-28 over
`contract/read_models.py`, `routers/read_models.py`, `readmodels/repository.py`,
`core/schema.py`, the writers, and the demo server's reference projections).
**This list is exhaustive**: the build adds exactly these API changes and no
others; every item is additive (new optional fields, new params, one new
endpoint, one allowlist widening). Lead adjudications of the audit's ten
decision items are inline, marked **[D‑n]**.

## 1. Already served (no change — build renders what exists)

Funnel (all 7 stages + `screened_out`) · timeline labels/blurbs/seconds/
reasons via SSE · coverage `sentence` · groups facets/labels/sizes/
descriptions · landscape types/years/themes/`geographies` (publication
geography — caveat copy correct) · run status vocabulary · `PlanDraft` full
shape incl. `scope_constraints.country_group` · artefact sections/roles/
claims **all six claim types** (render-breadth only) · citation
`grounding_tier` + `appraisal_label` · chunk context current-chunk offsets
(404 → quote-only degrade) · coverage snapshot (`included`, `study_types`,
`year_range`, `screened_out`) · evidence row `venue`/`status`/`status_reason`/
`appraisal_tier`/`cited` · `DecisionOut.detail` (raw payload) · findings
`profile` + `relevance`.

## 2. Additive field/endpoint changes (the approved list)

| # | Endpoint/model | Addition | Source | Notes |
|---|---|---|---|---|
| 1 | `CoverageOut` | `backends: list[str]` (public backend names only — never `trust_class`/`mode`) | `search_coverage_record.backends` | |
| 2 | `CoverageOut` | `backends_detail: list[{backend, results, relevant, queries: [{query, results}]}]` | `event_log` `search.executed` scoped by `acquired_by_run_id` + effective screens ⋈ snapshot backend | Post-run coverage card. Known wart (audit, demo-inherited): `relevant` attribution is project-wide — documented in copy, revisited at workspace-cluster. Per-**query** relevance NOT-RECORDED → omitted. |
| 3 | `FindingOut` | Discriminated enrichment per the typed-variants pin, **discriminated on the existing `profile: "iof"\|"icf"` literal** (plan-adversarial finding 8 — no `kind` field anywhere; filter param is `?profile=`): `IofFindingOut` (`intervention, outcome, effect_direction, statistics{effect_size, effect_size_type, ci_lower, ci_upper, standard_error, p_value, n, k, i_squared, tau2}, comparator, estimate_level, causality_by_design, is_primary, stratum_qualifiers, effect_basis, study_geography, population, setting, study_design, quote, quote_verified, groups: {facet: label}`) · `IcfFindingOut` (`context_type, claim, context_label, intervention, outcome, population, setting, study_geography, study_design, claim_level, claim_basis, level, resource_requirements, workforce_requirements, quote, quote_verified, groups`) | `intervention_outcome_finding.*`, `implementation_context_finding.*`, `.grounding` (keys `match_status`/`quote_verified` — NOT the demo's `anchor.match`), `grouping_result` member ids | `field_coverage` deliberately NOT exposed (null-omission is the honesty rule; exposing invites the banned render). `is_prevalence_only` omitted (no surface). |
| 4 | `EvidenceItemOut` | `screen_confidence: float?`, `screen_basis?`, `screen_stage?` | `effective_screen_rows()` — columns already selected, just not projected | Zero-cost. |
| 5 | `EvidenceItemOut` | `screen_status: str?` (`relevant\|not_relevant\|excluded_retracted`) | same | **[D‑3]** additive passthrough instead of widening the closed `EvidenceStatus` literal; UI renders "Excluded — retracted" and suppresses the misleading 100%-confidence chip. |
| 6 | `EvidenceItemOut.url` | **Fix (bug, not addition):** fallback ladder `landing_page_url → source_locator → provider landing page → https://doi.org/{doi}` | `source_snapshot.source_locator`, `provider_fields` | **[D‑8]** today the field is usually a bare DOI string `safeHref` rejects. |
| 7 | **New endpoint** `GET /projects/{id}/sources/{source_id}` (the contract's one optional dossier endpoint) | `abstract` + `abstract_source` (`provider\|llm_description` — the Overton LLM-description fallback must be marked, never presented as the document's own words) · `publisher` · `record_type` · `language` · `doi` · `cited_by_count` · `fwci` (OpenAlex only; omit otherwise) · `tags: [{tag, tag_type, asserted_by}]` (schema already guarantees per-asserter rows) · `cited_in: [{claim, quote, section_title}]` · plus the row-level fields | `source_snapshot.metadata`, `source_tag`, citation⋈annotation⋈addressable_unit⋈synthesis blocks | findings-from-source served via the findings `source_id` filter (#10), not embedded. **`cited_in` correctness pins (finding 10):** the citation→source mapping covers **both** PSS snapshot links (envelope AND full-text `source_snapshot_id`, per the existing artefact-code precedent at repository.py:786) and is **scoped to the latest `synthesis_result`** — never mixing prior artefacts into the dossier. |
| 8 | `ChunkContextOut` | `previous?`, `next?`, `year?`, `venue?` | `chunk.sequence ± 1`, snapshot metadata | |
| 9 | `SectionOut` | `focus?` | `synthesis_result.blocks[].focus` | Final-artefact parity with the `artefact.skeleton` event. |
| 10 | Filters — `GET /evidence`: `status` (repeatable; "Included" = the 7 in-ladder values) + `cited` · `GET /findings`: `profile`, `facet`+`group` (or `group_id`), `source_id` | derivations per audit strand 6 | `total_items` reflects the filter (collection-true counts). Evidence status derivation stays in Python (derive project-wide, paginate after — bounded; `funnel_out` precedent) unless profiling says otherwise. |
| 11 | `DecisionOut` | Widen `repository._EVENT_KINDS` with `component.completed/failed/skipped` (+ fixed-English summary per kind, per the existing map pattern) | `event_log` | **[D‑5]** the demo log's main content. Client groups `search.executed` rows into one "Search terms used (N queries)" entry. |
| 12 | `ClaimOut` | `weakly_grounded: bool?` | `annotation.payload` (`quote_unverified`/`weakly_grounded`/anchor `match_status`) | **[D‑10]** replaces the constant-true "verified" chip the audit killed; renders the demo's "source check" claim styling. |
| 13 | `ClaimOut` | `gap: {grade, caveat{search_space, adequacy_verdict, verdict_origin}, inferred}?` — a **new optional field** (plan-adversarial finding 7: `BlockOut.gaps` is typed `list[str]`, so populating it with structured objects would be a type change — non-additive; the legacy field stays as-is and is documented deprecated-empty) | `annotation.payload["gap"]` | **[D‑9 rev]** the claim-panel gap explainer reads `ClaimOut.gap`; "coverage claims keep their base" rides the caveat. |
| 14 | `PlanDraft.time_band` | Derive during drafting once both effort+depth are set (`TIME_BANDS[(search_effort, analysis_depth)]`) | existing table | **[D‑7a]** cheap, honest expectation-setting. |
| 15 | Approved-plan steps | **Fix (bug):** `_draft_from_plan` routes composed components through `STAGE_BY_REGISTRY` + `STAGE_PRESENTATION` — real labels + blurbs, `step.stage` = public `StageKey`; `ingest_full_text`→`acquire`, `screen_full`→`screen` collapse (dedupe by StageKey) | `api/stage_vocabulary.py` | **[D‑6]** today: raw-enum labels ("Screen Full"), empty blurbs, and stage keys that would duplicate timeline rows. |

## 3. Lead adjudications of the audit's remaining decision items

- **[D‑1 rev 2 — plan-adversarial finding 2 killed the polling design]:**
  `search.executed` events are appended on the acquire component's own
  connection (acquire.py:722/746) — inside the component-wide transaction —
  so the decisions read sees **nothing until acquire commits**, exactly when
  the coverage card takes over. There is no honest live per-backend data
  without either extending tick payloads or new SSE events — both outside
  the approved `artefact.*` set (contract stop condition). **Adjudication:
  the live search card is redefined honestly** — while acquire runs, the
  journey shows the tick-based activity card (stage + live notes, which DO
  flow — ticks are ephemeral, not event_log); per-backend counts + the
  query list arrive when the stage completes (coverage card,
  `backends_detail`). The contract's strand-1 hedge ("honest omission where
  the data doesn't carry it") covers this; flagged for the owner at the
  plan gate as the one demo moment (accumulating result count-up) that
  durable architecture genuinely cannot reproduce in this slice.
- **[D‑2] Per-run scoping — accepted project-wide** for this slice (matches
  the one-question-per-project reality; run-scoped read models are
  workspace-cluster's job). Copy says "across this project" where it matters;
  recorded in deferred.md.
- **[D‑4] `DecisionOut.detail` — client-side allowlist + label map** (the
  demo server's `_DECISION_DETAIL_LABELS` is the vocabulary source); server
  narrowing would be non-additive and is recorded in deferred.md as an API
  hygiene item. Unknown keys omit (rubric 9).
- **[D‑7b] Draft-time steps checklist — honest omission until `ready`**
  (the wire never carries steps; best-effort `compose()` on partial drafts
  is speculative). Pre-ready, the pane renders the components list; the
  steps checklist appears at ready/approved via #15.
- **Timeline summary counts + groups facet keys + finding `profile` chips —
  client label maps** (locked-vocabulary rule; unknown key → omit). The
  audit's coverage-sentence defect ("stopped because completed") is a
  server-side map extension in the same spirit — one copy fix, additive.

## 4. Honest omissions (NOT-RECORDED — surfaces hide, never fake)

Screening rationale prose (only in model-authored event payloads — no read
model) · per-query relevance · completion/failure collation narrative
(`render_collation` never persisted) · activity ticks for non-acquire stages
(no emitters; adding them = behaviour change outside strands 12–13) ·
tag-distribution chart (demo never rendered it) · FWCI on Overton rows ·
draft-time steps (D‑7b) · mid-run per-backend relevant counts (D‑1).

## 5. Demo transcription traps (bound into the per-view briefs)

1. IOF statistics keys are `ci_lower/ci_upper/standard_error/i_squared/tau2`
   — the demo's `STAT_LABELS` (`ci`, `se`, `i2`) yields an empty panel.
2. Grounding verification is `match_status`/`quote_verified` — the demo's
   `anchor.match` does not exist.
3. Coverage snapshot: `source_count` is the **cited/reference** count — the
   demo's "N found" copy is false against prod; the cell reads "N cited ·
   M included".
4. `LandscapeOut.geographies` = the demo's `publication_countries` (values
   are mixed ISO codes and names — normalise in the label layer).
