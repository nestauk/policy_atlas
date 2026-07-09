# Demo API contract (demo-live-run branch — throwaway, never merges to dev)

Backend: FastAPI at `http://localhost:8100`. Frontend dev server proxies `/api` there.

## User-visible vocabulary (locked)
- CTA: **"Start the analysis"** (never "Build"/"Run"). In-progress: **"Analysing the evidence…"**
- plan → "plan" (approved term) · rerun → "refresh the analysis" · artefact → "evidence base"
- corpus → "sources" · classify/appraise → "quality-checking" · extract → "pulling out findings"
- Component names (screen/classify/…) never appear in the UI; use `stage_label` from events.

## REST

### `GET /api/projects`
`[{project_id, name, question, status: "new"|"planning"|"running"|"complete"|"failed", created_at, source_count, updated_at}]`

### `POST /api/projects` `{name}` → `{project_id}`

### `POST /api/projects/{id}/chat` `{message}` → `{reply, plan}`
One planning-conversation turn. `plan` is the full current draft (see Plan shape). The
conversation history lives server-side.

### `POST /api/projects/{id}/start` → `{ok: true}`
Compiles the plan and starts the analysis in the background. Progress arrives on the SSE stream.

### `POST /api/projects/{id}/checkin/{checkin_id}` `{reply}` → `{ok: true}`
Answer a pending check-in; the analysis resumes.

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
  - `kind:"verdict"` `{relevant, not_relevant, screened_so_far, total}` — screening tick
  - `kind:"fetch"` `{ok, failed, total}` — full-text fetching tick
  - `kind:"tick"` `{note}` — anything else worth a line in the activity feed
- `stage.completed` `{stage, stage_label, summary}` — summary is stage-specific counts
- `narration` `{text}` — orchestrator speaking in the thread (markdown)
- `checkin` `{checkin_id, text, options: [string]}` — analysis paused awaiting the user
- `analysis.completed` `{}` · `analysis.failed` `{stage, message}`

## Plan shape
```json
{
  "question": "What works to reduce childhood obesity in the UK?",
  "focus": ["UK evidence prioritised", "interventions in schools"],
  "search_depth": "quick" | "deep",
  "evidence_sources": "academic_only" | "grey_lit_only" | "both",
  "check_in": "minimal" | "moderate" | "frequent",
  "steps": [{"label": "Search academic + policy sources", "stage": "acquire"},
             {"label": "Screen for relevance", "stage": "screen"}, ...],
  "ready": false
}
```
`ready:true` once the orchestrator considers the plan complete enough to start.

## Stage order (for the journey timeline)
acquire → screen → (deep rounds may repeat acquire/screen) → classify → appraise →
ingest_full_text → characterise → select → extract → group → synthesise.
UI labels come from `stage_label`; the deep loop surfaces as repeated search/screen ticks
inside one "Searching" stage group, per `stage.progress kind:"round"`.

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
