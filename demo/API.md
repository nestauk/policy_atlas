# Demo API contract (demo-live-run branch — throwaway, never merges to dev)

Backend: FastAPI at `http://localhost:8100`. Frontend dev server proxies `/api` there.

> **Post-016/017 rewire (2026-07-10):** the server now wraps the REAL backend —
> planning turns are `policy_atlas.planner` (017), execution is
> `policy_atlas.runner.run_plan` over `orchestration_plan.compose` (017), full-text
> fetching is `fetch_live.LiveDocumentFetcher` (016). Check-ins are the real steering
> vocabulary and their answers are functional. Demo-only glue that remains, by
> explicit decision: LLM narration/check-in prose, the SSE bus + structlog bridge,
> stage labels, and the gpt-5.5-synthesis/facet-cap monkeypatches.

## User-visible vocabulary (locked)
- CTA: **"Start the analysis"** (never "Build"/"Run"). In-progress: **"Analysing the evidence…"**
- plan → "plan" (approved term) · rerun → "refresh the analysis" · artefact → "evidence base"
- corpus → "sources" · classify/appraise → "quality-checking" · extract → "pulling out findings"
- Component names (screen/classify/…) never appear in the UI; use `stage_label` from events.

## REST

### `GET /api/projects`
`[{project_id, name, question, status: "new"|"planning"|"running"|"paused"|"complete"|"failed", created_at, source_count, updated_at}]`
`paused` = a run is blocked on a steering check-in (Landing shows "Paused — waiting on your input").

### `POST /api/projects` `{name}` → `{project_id}`

### `POST /api/projects/{id}/chat` `{message}` → `{reply, plan, suggestions: [string]}`
One REAL planner turn (017 `planner_v1`, ~20–30 s). `plan` is the full current draft
(see Plan shape). `suggestions` are the planner's suggested answers to its clarifying
question (empty when none) — render as tappable quick-reply chips that send as a chat
message. History lives server-side. When the planner marks the draft ready it is
validated fail-closed into an `OrchestrationPlan`; a validation failure appends an
honest explanation to `reply` and `ready` stays false.

### `POST /api/projects/{id}/start` → `{ok: true}`
Writes the approved plan row and starts the real runner in the background
(400 if the plan hasn't validated ready). Progress arrives on the SSE stream.

### `POST /api/projects/{id}/checkin/{checkin_id}` `{reply, params?}` → `{ok: true}`
Answer a pending steering pause. `reply` is an option **id** from the `checkin` event.
For `requires_user_input` options, `params` carries the fill-in:
- `adjust_budget` → `{budget: <int>}`
- `deepen_clusters` → `{strata: [<cluster id>...], docs: [<doc id>...]}`
Answers are FUNCTIONAL: they map to real steering responses (Continue / Adjust —
which re-runs the shortlist with the new directive — / Abort).

### Read models (poll after each `stage.completed`, or on view mount)
- `GET /api/projects/{id}/plan` → Plan shape
- `GET /api/projects/{id}/funnel` → `{found, relevant, screened_out, quality_checked, read_in_full, selected, findings, cited}` (any key may be null before its stage)
- `GET /api/projects/{id}/landscape` → `{evidence_types: {label: count}, years: {year: count}, themes: [{name, size, description}], geographies?: {label: count}}`
  - INVARIANT: every landscape distribution is computed over the **screened-in set only**
    (characterise loads `status == "relevant"`); mock data must sum to the included count,
    never the found count. Only the funnel spans the full flow.
- `GET /api/projects/{id}/groups` → `{facets: [{facet, groups: [{label, description, size}], ungrouped: int}]}`
- `GET /api/projects/{id}/evidence` → `[{title, year, venue, origin: "OpenAlex"|"Overton"|"Uploaded", status, status_reason?, evidence_type?, appraisal_tier?, cited: bool, url?}]`
  - `status` ∈ found | screened_out | relevant | not_selected | selected | read_in_full | findings_extracted | cited | unavailable (abstract-only)
- `GET /api/projects/{id}/artefact` → `{title, question, coverage_snapshot: {source_count, study_types: {..}, year_range, included, screened_out}, sections: [{title, blocks: [{block_id, prose, claims: [{claim_id, text, citations: [{n, source_title, quote, grounding_tier, appraisal_label}]}], gaps: [..]}]}], references: [{n, title, year, venue, url?}]}`
  - Detail panels are provenance (quotes, tiers, appraisal, set-aside/gaps) — never generic expansion.

## SSE: `GET /api/projects/{id}/events`
`event:` = type below, `data:` = JSON. On connect, the full backlog for the project replays
first (so refresh mid-run rebuilds state), then live events follow.

- `plan.updated` `{plan}` — after each chat turn
- `analysis.started` `{}`
- `stage.started` `{stage, stage_label, stage_blurb}` — e.g. `{stage:"screen", stage_label:"Screening for relevance", stage_blurb:"Reading titles and abstracts…"}`
- `stage.progress` `{stage, kind, ...}` — high-frequency ticks. Kinds (best-effort, from logs):
  - `kind:"search_query"` `{backend, query}` — a query going out
  - `kind:"results"` `{backend, count}` — a result batch landing
  - `kind:"round"` `{round, new_relevant, total_relevant}` — deep-loop round summary
  - `kind:"tick"` `{note}` — anything else worth a line in the activity feed
    (full-text fetch progress arrives as per-document ticks: "Read a document in
    full" / "A document couldn't be fetched — recorded")
- `stage.completed` `{stage, stage_label, summary}` — summary is stage-specific counts
  (from the runner's deterministic check-in payload; `summary.seconds` = wall clock)
- `stage.failed` `{stage, stage_label, reason, skipped}` — honest, non-fatal; the runner
  chains the rest of the run off successful predecessors (`skipped:true` = never ran
  because its prerequisite failed)
- `narration` `{text, suggestions?}` — orchestrator speaking in the thread (markdown);
  planning-turn replays carry the turn's suggestion chips
- `checkin` `{checkin_id, kind: "steer_point"|"check_in", text, render, options, triggers}`
  — analysis paused awaiting the user. `text` is the LLM-prose wrap (demo glue);
  `render` is the deterministic steering render (the content of record). `options` is
  `[{id, label, description, requires_user_input}]` — ALWAYS server-supplied, never
  invent options client-side. At the deepening-selection steer point the ids are the
  017 intent vocabulary (`deepen_clusters`, `strongest_evidence`, `most_relevant`,
  `adjust_budget`) plus `continue` and `abort`; a plain check-in offers
  `continue`/`abort` only. `triggers` lists fired steer-point triggers
  `[{trigger, detail}]` (e.g. `excluded_large_stratum`).
- `analysis.completed` `{status: "succeeded"|"degraded", collation}` — `collation` is the
  runner's flagged-event render (failures/retries/skips), shown honestly on completion
- `analysis.failed` `{stage, message, collation?}` · `analysis.aborted` `{collation}`

## Plan shape (the real 017 `OrchestrationPlan`, drafted field-by-field)

Every field except `steps`/`ready` may be **null/empty while drafting** — the planner
fills them as the conversation converges. Never trust an optional field.

```json
{
  "title": "Childhood obesity — what works",
  "question": "What works to reduce childhood obesity in the UK?",
  "scoping_notes": ["UK evidence prioritised", "interventions in schools"],
  "screening_criteria": ["Excludes pharmaceutical interventions"],
  "backend_scope": "academic_only" | "grey_lit_only" | "both",
  "scope_constraints": {"published_after": "2015-01-01", "publisher_country": "GB"},
  "search_effort": "rapid" | "standard" | "deep",
  "analysis_depth": "landscape" | "standard" | "deep",
  "components": ["screen_stage2", "characterise", "select", "extract", "group"],
  "component_rationale": {"select": "…why this component fits the intent…"},
  "steering_mode": "frequent" | "moderate" | "minimal" | "unattended",
  "assumptions": ["…"],
  "expected_artefact_shape": "…",
  "time_band": "~30-45 min",
  "steps": [{"label": "Searching sources", "blurb": "…", "stage": "acquire"}, ...],
  "ready": false
}
```

- The old `search_depth` quick/deep is GONE — depth is the two-axis
  `search_effort` × `analysis_depth` gradation. `time_band` and
  `expected_artefact_shape` are derived server-side (measured bands, never invented).
- `check_in` is GONE — `steering_mode` has FOUR modes including `unattended`
  (auto-resolves steer points to visible plan defaults; nothing pauses).
- `steps` is the REAL composed chain (`orchestration_plan.compose`) with demo labels —
  populated only once `ready:true`; empty while drafting.
- `ready:true` means the draft validated fail-closed into an executable plan.

## Stage order (for the journey timeline)
Order = `plan.steps` (the composed chain). Full standard/deep chain:
acquire → screen → classify → appraise → ingest_full_text → screen_stage2 →
characterise → select → extract → group → synthesise. Landscape depth drops
screen_stage2/select/extract/group. Deep search rounds run INSIDE acquire/screen
(surfacing as `stage.progress kind:"round"` ticks); a steering adjustment can re-run
select (`stage.started` for select may repeat). UI labels come from `stage_label`.

## Added read models (feature-showcase pass)

- `GET /api/projects/{id}/findings` → `[{intervention, outcome, direction: positive|negative|no_effect|mixed|unclear, population?, study_design?, statistic?, quote?, quote_verified, source_title}]`
- `GET /api/projects/{id}/decisions` → `[{at, kind, text}]` — projection over the canonical event log + this session's check-ins, ascending.
- `GET /api/projects/{id}/coverage` → `{backends: [..], stop_condition, stop_text, adequacy, verdict_origin} | null`
- Artefact claims now carry `span: {start, end}` — char offsets into the block `prose` (the claim IS a span of the text); citation chips anchor inline at span end.

## Annotation-layer + dossier pass (round 3)

- Artefact claims now carry `claim_type`: `citation | gap | reasoning | pattern | theme`.
  EVERY annotation is a prose span (span offsets as before); gaps/reasoning render IN the
  prose, typed — never as separate callouts. `citations` is populated for citation-type only.
- `GET /api/projects/{id}/findings` rows now carry: `finding_id`, `comparator`,
  `estimate_level`, `causality`, `is_primary`, `statistics` (full reported dict: effect_size,
  effect_type, ci, se, p_value, n, k, i2, tau2 — whichever were reported),
  `stratum_qualifiers: [{type, value}]`, and `groups: {facet: group_label}` from the latest
  grouping run.
- `GET /api/projects/{id}/sources/{source_id}` (NEW) → the evidence row PLUS
  `{abstract, abstract_source, doi, language, publisher_org, record_type, cited_by_count,
  fwci, indexed_in, tags: [{tag, tag_type, asserted_by}], cited_claims: [{claim, quote,
  verified, section}]}`.
- `GET /api/projects/{id}/decisions` entries now carry `detail: {label: scalar}` — the
  flattened stage payload for expandable rows.
- `GET /api/projects/{id}/landscape` now carries `tags: {"<tag_type>/<asserter>": {tag: count}}`
  — the tag layer with assertion provenance, screened-in set only.
