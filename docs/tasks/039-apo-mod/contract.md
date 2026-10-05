# Task contract: 039-apo-mod (re-apply)

One combined slice that re-implements two owner-approved change sets on a
fresh branch from current `dev` (`task/039-apo-mod`). The originals were
proven on the abandoned `task038/apo-mod` branch; the task-038 vocabulary
rename made merging impractical. Full detail lives in
[old_contracts/](old_contracts/) — this contract binds the re-apply and maps
the renamed tree; it does not restate the originals.

> **Status:** approved for re-apply (owner instruction, 2026-09-08). The APO
> mod contract was approved 2026-09-04 with a Codex adversarial pass (4
> findings, folded in — see `old_contracts/038-apo-mod/plan.md`); the bug-fix
> contract was drafted for re-apply by the owner. No new adversarial pass:
> reimplementation of reviewed designs, not new design. ADR: none.

## Goal — numbered steps

- **S1 — APO source restriction** (from `old_contracts/038-apo-mod/`):
  a run restricted to Australian Policy Online makes no OpenAlex calls
  (existing `backend_scope="grey_lit_only"`), and every Overton call carries
  `source=apo`, set by typing "APO" / "Australian Policy Online" in the
  Source geography box (422 unless Sources is grey literature only). The plan
  document shows "Geography: APO". Verified live on 2026-09-04.
- **S2 — case-study citations** (bug 1): each case-study card cites its own
  sources. Write path mints unique claim ids across cards; read path recovers
  already-written artefacts whose rollup aliases collide.
- **S3 — plan edits / Start reliability + screening UX** (bug 2): section
  saves write only changed fields into the overlay (a Sources-only save must
  not blank APO geography); Start failures show the API's real message plus a
  "Discard edits and start" action; screening rules edit as a list with
  +/− and a 1000-char per-rule cap (`SCREENING_CRITERION_MAX`; composed
  question+criteria stays 2000; global `DIRECTIVE_STRING_MAX` 200 unchanged).
- **S4 — planner chat sets APO** (bug 3): `planner_v10 → planner_v11` teaches
  the planner to set `publisher_source: "apo"` + `backend_scope:
  grey_lit_only` when the user asks for APO, and updates the screening-length
  wording to the 1000-char cap. Prompt hash re-pinned (deliberate slice work).

## Terms

The old contracts' term tables stand. Renames on this tree (task 038 landed):

| Old name (in old docs) | Now |
|---|---|
| product "Task" / code row `project`, `project_id` | row `task`, `task_id`; routes `/api/v1/tasks/…` |
| product "Project" / code row `portfolio` | row `project` |
| `runtime/orchestration_plan.py` · `OrchestrationPlan` | `runtime/task_plan.py` · `TaskPlan` |
| `runtime/orchestrate.py` (`build_plan`) | `runtime/agent.py` |
| `evidence_base/…` | `evidence_search/…` |
| `_project_card_claims` (readmodels) | `_task_card_claims` |

## Scope / Out of scope

- **In:** exactly the union of the two old contracts' In lists, at the
  renamed paths. New-tree additions the old plans could not know:
  `agent.py _render_scope_constraints` must render the new field, and
  `scopeChips` feeds the overlay's geography via private
  `geographyFromConstraints` (string-slice coupling — needs a paired test).
- **Out:** everything both old contracts list as Out; resolving the abandoned
  `task038/apo-mod` branch; re-running the design gates.

## Constraints & approval gates

As per the old contracts: runtime egress = one constant Overton param
(approved 2026-09-04); public API = the additive `publisher_source` field;
prompt bump `planner_v11` is deliberate slice work (re-pin
`scripts/prompt_hashes.json`); no schema migration; no new dependencies.

## Model route

`planner_v11` system-prompt addition (APO + screening wording) — lead-only,
prompt-bearing. No new model calls.

## Acceptance checks

The union of both old contracts' checks, at the new paths, plus:

- `make verify` green at the step-6 exit.
- The 038-pinned live check re-run: real Overton request URL carries
  `source=apo`; returned records are APO documents; no OpenAlex call.
- Case studies: unique `claim_ids` across cards (composition test);
  colliding-alias recovery (read-model test).
- Overlay: Sources-only save leaves APO geography intact; Start failure shows
  the API message; Discard clears the overlay and starts.
- Screening: 1000-char rule accepted, 1001 rejected; list max 50 and composed
  2000 unchanged; +/− list UI test.
- Planner: version `planner_v11`; prompt names APO/`publisher_source` and the
  1000-char wording; 038 geography-token router tests green.
- Manual check of the diagnosis task `11241c21-…` is **not** re-pinned (that
  database belonged to the old branch's environment); the fixture tests and
  one seeded multi-card artefact check stand in.

## Risk tier & review focus

**Tier 3** (egress + additive public field + prompt bump — the prompt bump
raises this above the old 039 slice's Tier 2). Review focus: the old
contracts' foci, plus rename drift (no stale `project`/`portfolio`/
`evidence_base` references introduced).
