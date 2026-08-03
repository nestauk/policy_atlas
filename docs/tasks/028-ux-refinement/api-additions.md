# 028 additive API / schema / event surface (plan annex, draft)

> Enumerated at plan time per the contract's additive gate. Everything here
> is additive-only; anything that turns non-additive during the build is a
> stop condition. Approved at the plan 🛑; regenerated client via
> `make drift-check`.

## Read models / endpoints (additive fields & params)

| Surface | Addition | Strand |
|---|---|---|
| `PlanningTurnOut` (transcript rows) | `part` — the structured part proposal (id · step label · title · body? · chips? · options[2–4] · confirmed-state derives client-side from later turns) | 3 |
| Sources list (`/evidence` router) | `sort` + `order` query params (title · year · type · strength · status); `theme` filter param | 7 |
| Landscape endpoint | `scope=cited` variant param (cited-only distributions for the report's gathered section) | 10 |
| `SectionOut` | `summary` + `summary_status` (`pending/verified/failed`) — the block summary projection | 13 |
| Artefact read model | `summary` + `summary_status` (artefact grain) | 13 |
| Theme/steering read surface | renamed labels serve through the existing theme refs (rename is a durable edit, not a new endpoint — the steering delta carries it) | 14 |

## Schema (one migration, additive, tested downgrade)

- `planning_transcript.part` — nullable JSONB (strand 3)
- `block.summary` — nullable text + `block.summary_status` marker (strand 13;
  excluded from `content_hash` per spec)
- `artefact.summary` — nullable text + `artefact.summary_status` (strand 13)

No backfill anywhere. Plan payload (`orchestration_plan.payload` JSONB) gains
optional `section_budget` — model-level addition, no DDL.

## Steering surface (behaviour-gated, event-payload level — no API change)

- New lattice point `finding_groups` (after group, deep-only) + mode-table
  update incl. **unattended default**.
- Option floors: re-homed/slimmed per the binding taxonomy record; static
  copy rewrite; depth-conditional floors.
- New delta class: `rename_theme` (P2-only) + steering audit event.
- Authored options: validated against the compiled grammar at authoring +
  apply; drop+log+event on non-compile.

## Prompt surfaces (six, all lead-authored, versioned)

`planner_v6` · key-findings section rev · `synthesise_sections_v3` (flow +
section budget) · summariser (new) · faithfulness judge (new) ·
watch-authoring rev.

## Explicitly NOT changing

Auth · deps · CI · SSE vocabulary · prod config · check-in response API
(`option`/`free_text`/`free_text_confirm` shapes) · 027 substrate invariants.
