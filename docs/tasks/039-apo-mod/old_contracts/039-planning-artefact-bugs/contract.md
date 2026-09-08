# Task contract: 039-planning-artefact-bugs

Bug-fix slice capturing work already proven on a dirty branch, to be
**re-implemented on a fresh branch from current `dev`** (merge conflicts made
cherry-pick impractical). Boundaries: [AGENTS.md](../../../AGENTS.md).

> **Status:** drafted for re-apply. Owner intends to save these artefacts,
> cut a clean branch from `dev`, and re-implement from the plan.
> ADR: none expected (bug fixes + small planner prompt bump).

## Goal

Three user-facing bugs:

1. **Case studies cite the wrong source** — every case-study card on the
   artefact shows the same citations (typically the last card’s). Project
   used for diagnosis: `11241c21-f481-418e-9470-82e98aa254f4`.
2. **Plan edits sometimes cannot apply, and Start search never runs** —
   after editing (often screening rules), Start fails with a vague
   “couldn’t be applied” message and there is no way to proceed until a
   reload; fixing the plan in place does not clearly unblock Start.
3. **APO restriction is hard to see / incomplete from chat** — when
   sources are restricted to Australian Policy Online, Source geography
   should read **APO**. Asking for APO in planning chat should set the
   same restriction (and show it); typing APO / Australian Policy Online
   in the geography box (with grey literature only) already did via 038
   and must keep working.

Also ship the agreed screening UX: one text field per rule with `+` / `−`,
and a higher per-rule length cap (200 was too short).

## Deliverable

A PR that lands all three fixes with tests. After merge:

- Distinct case-study cards cite distinct sources (and old artefacts with
  colliding rollup aliases still project correctly).
- Local plan edits apply reliably on Start; failures show the real reason;
  the user can fix and retry or **Discard edits and start**.
- Screening rules edit as a list of fields; per-rule cap is 1000 chars
  (composed question+criteria still 2000).
- APO appears in Source geography when `publisher_source` is set; chat can
  set that via `planner_v11`.

## Terms

| Term | Meaning |
|---|---|
| **Plan overlay** | Local uncommitted plan edits held in the UI until Start search PATCHes `/plan`. See `frontend/src/views/workspace/planOverlay.ts`. |
| **Synthesis claim alias** | In-synthesis id `s{section}c{index}` stored on annotation payload and in case-study rollup `claim_ids`. Public `claim_id` is the unit UUID. |
| **publisher_source** | Scope constraint value `"apo"` → Overton wire `source=apo` (task 038). |
| **SCREENING_CRITERION_MAX** | Per screening-rule character cap (target **1000**). Distinct from global `DIRECTIVE_STRING_MAX` (200) used by other guidance channels. |
| **SCREEN_INTENT_MAX** | Composed question + criteria budget (**2000**); unchanged. |

## Read first

- Case studies: synthesis case-studies pass + artefact read projection
  (`synthesise` / `CaseStudyCardOut` / readmodels repository). Paths on
  older trees: `evidence_base/synthesis/`; on vocabulary-aligned `dev`
  they may live under `evidence_search/synthesis/` — follow the tree you
  branch from.
- Planning overlay: `planOverlay.ts`, `planStart.ts`, `PlanDocument.tsx`,
  `PlanCard.tsx`.
- APO: `docs/tasks/038-apo-mod/` (geography token + filter chain already
  landed or landing with 038); this slice **extends** chat + display UX.

## Scope / Out of scope

- **In:**
  - Case-study claim-id minting across cards; rollup `claim_ids` uniqueness;
    read-path recovery when aliases collide.
  - Plan overlay dirty-only saves and patch-against-plan; Start failure UX
    (clear message, clear notice on overlay change, Discard edits and start).
  - Screening per-rule `+/-` UI; `SCREENING_CRITERION_MAX = 1000` in plan
    model + screen directive parse + client validation.
  - `planner_v11`: teach `publisher_source: "apo"` + `backend_scope:
    grey_lit_only` when the user asks / planner chooses APO; bump prompt
    hash; show APO in Source geography without overlay blanking it.
- **Out:**
  - Raising global `DIRECTIVE_STRING_MAX`.
  - Replacing 038’s geography-token / Overton allowlist work (reuse it).
  - Broader planner geography redesign.
  - Case-study prompt / synthesis content quality.

## Constraints & approval gates

- Prompt bump (`planner_v10` → `planner_v11`) is deliberate slice work:
  re-pin `scripts/prompt_hashes.json`.
- No schema migration expected.
- Public API: no new fields required; behaviour-only + existing
  `publisher_source` / case-study cards.
- On re-apply: confirm package paths (`evidence_base` vs `evidence_search`)
  against the branch tip before editing.

## Model route

- Planner only (`planner_v11` system prompt addition for APO + screening
  length wording). No new model calls.

## Acceptance checks

- `make verify` green (or `make verify-fast` while iterating, full verify
  before PR).
- Case studies: composition test asserts unique `claim_ids` across cards;
  repository unit test recovers colliding aliases by prose match; live
  artefact (or seeded fixture) shows distinct sources per card.
- Planning: dirty-only overlay tests; failed apply surfaces API message;
  Discard clears overlay and can start; screening list UI test; 1000-char
  criterion accepted, 1001 rejected; composed 2000 still enforced.
- APO: plan with `publisher_source: "apo"` renders Source geography `APO`;
  overlay Sources-only edit does not blank geography; planner version pin
  + prompt contains APO instructions; geography box tokens still work
  (038 tests).

## Risk tier & review focus

**Tier 2** (feature/bugfix integration; one prompt bump).

Focus: claim-id uniqueness, overlay not clearing APO, honest Start errors,
prompt-hash pin, path rename on current `dev`.
