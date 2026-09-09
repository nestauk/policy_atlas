# Verification: 044-scoping-shell-baseline

Evidence for the build phase (steps 5–6). Public-safe: no secrets, raw source
text, credentials or unredacted traces. Filled as each phase closes; **Review
findings** and **Rubric status** are added by the review conversation (step 7).

## Commands run

### Phase 0 — build-open baseline (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make verify` at `b4b1e93b` | fail | backend 2552 passed; typecheck, lint, build green; **`infra` test red**: `test_dockerignore_covers_gitignored_backend_content` — `b4b1e93b` added `PRODUCT.md` and `DESIGN.md` to `.gitignore` without the Docker-ignore mirror. Not this slice's change. |
| hotfix `5854676a` (`backend/.dockerignore` +2 lines) then `make audit-paths prompt-guard font-guard drift-check frontend-verify` | pass | frontend 79 files / 617 tests; the remaining stages that the infra failure had skipped |

The base was green before any 044 code landed. The hotfix is one commit on
this branch, outside the rename phase's reviewed diff.

### Phase 1 — Task Agent rename and EB → ES sweep (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `scripts/rename_044.py --apply --phase 3 / 4 / 5` | pass | 46 / 49 / 31 files; 715 / 457 / 177 replacements; second `--apply` on each phase: 0 changes; `--scan --ignore-ledger`: 0 unmapped, 0 collisions |
| `make verify` (full) | pass after re-sync | backend 2615 passed (8:15); typecheck, lint, build green; infra 46 passed; audit-paths, prompt-guard (13 unchanged, one path moved), font-guard green; `drift-check` was red once because the docs sweep touched contract-model docstrings after the last `make openapi-sync` — re-synced, `drift-check: OK` |
| `cd frontend && pnpm e2e` | pass | 11 passed (13.4s), mock mode |
| `make okf-validate` | pass | 143 concepts, 0 violations |
| `backend/tests/scripts` (038 + 044 tool tests, sweep test) | pass | 121 tool tests; the sweep test's five docs paths green after 1.4 |

**Rename sweep result (contract § Acceptance checks):** no `planning_transcript`,
`/planning-turns`, `PlanningTurn`, `PlannerBackend`, `planner_prompt`,
`POLICY_ATLAS_PLANNER_MODEL` in `backend/src`, `frontend/src`, `frontend/e2e`,
`infra/DEPLOYMENT.md`, `web-api.md`; no `planner_state`, `created_by = 'planner'`
or `planning`-named constraint in `schema.py`; allow-list honoured
(`eb_iof_base_v1`, `eb_icf_base_v1`, `evidence_base_coverage`, `planner_v\d+`,
the `"role": "planner"` literal, `planner-proposed`, the kept prompt module's
symbols); the old path is 404; `PLANNER_PROMPT_VERSION == "planner_v11"`
(`backend/tests/scripts/test_rename_044_sweep.py`).

**EB → ES grep** (`grep -rn -w EB` over `docs/specs` minus `sources/` and
`log.md`, `docs/agentic-ops`, `docs/tasks/_templates`, `AGENTS.md`,
`.claude/skills`, `backend/src`, `frontend/src`, `docs/knowledge`): the only
remaining hits are the four "EB handoff" citations (`product.md:11`,
`index.md:15`, `plan-as-object.md:100`, `spec-authoring.md:14`), kept by
ruling (they name the frozen source document).

**Prompt-hash diff:** one key moved, `runtime/planner_prompt.py` →
`runtime/task_agent_prompt.py`, value `4e85172f…8ce2` unchanged; no other
entry changed.

**OpenAPI diff:** one path renamed, four schemas renamed (`TaskAgentTurnCreate`,
`TaskAgentTurnOut`, `TaskAgentTranscriptTurnOut`, `Page_TaskAgentTranscriptTurnOut_`),
two operation ids, the conversation `kind` enum value `planning` →
`task_agent`, docstring text; `planner-proposed` unchanged; nothing structural.

**Migration round-trip** (`test_migration_044_rename.py`): upgrade renames the
table, column and the ten catalog-named constraints and indexes, moves both
stored values; downgrade restores the seeded fixture byte-identically; upgrade
again.

_(Phase 2 … Phase 7 rows are appended as each phase closes.)_

## Checks beyond the build

_(filled per phase)_

## End-to-end command

_(Phase 7)_

## Diff summary

_(filled per phase; flagged deviations listed here as they arise)_

### Flagged deviations (minor, resolved within the contract's vocabulary)

1. **`planning_turn_in_progress` → `task_agent_turn_in_progress`** (a 409
   error code, wire-visible). The contract names the path rename as the one
   non-additive change; the manifest (§ A.2, the deliverable-2 checklist per
   C13) lists this code, and A10 says the rename is complete or not done. The
   frontend is the only consumer. Renamed; recorded here next to the path.
2. **`runtime/agent_prompt.py` docstring keeps `planner_prompt.py` /
   `planner_v5`**: the module is hash-pinned and rubric 13 keeps every other
   hash unchanged, so the stale pointer stays until the next `agent_v` edit.
3. **`docs/tasks/_templates/contract.md:32` link** `capabilities/evidence-base/`
   → `evidence-search/`: a dead link since 038, fixed in the docs sweep.
4. **EB → ES in three `docs/knowledge/` files** (`index.md` line 117 and the
   two concept files it names, `synthesise-is-run-terminus.md` and
   `coverage-base-project-pool-wide.md`): `docs/knowledge/` content was
   outside the EB → ES scope in the manifest; the index line was swept by
   the tool and the two files were then swept by hand so the index and the
   titles agree. Filenames unchanged. Every "EB handoff" phrase is kept.
5. **Stored conversation title `"Planning"`** (`conversation_lifecycle.py`)
   and the History category `"Planning"` are kept: the screen never shows the
   stored title for the Task Agent (the vocabulary label does) and the
   category is ordinary English. The pane's aria label "Planning conversation"
   became "Task Agent conversation".

### Owner rulings taken during the build

- **2026-09-09 — the section writer's prompt becomes template-keyed** ("For
  the synthesise, let's go with option 2"): one writer, a shared core plus a
  preamble per output kind; the Evidence search preamble renders byte-identical
  messages (pinned by a test); the baseline preamble has its own version; the
  `synthesis_backend.py` hash is re-pinned once as a words-only diff. Contract
  § Constraints (prompts), rubric 13 and plan S3 / 4.1 amended with the quote.

## Review findings

_(step 7)_

## Rubric status

_(step 7)_

## Intent & assumptions

## Known unverified items

## Public safety

## Review handoff (step-7/8 inputs)

- **Knowledge candidates** (raw; step 8 authors `docs/knowledge/` from these
  against the final code):
  - The 038 rename engine's separator/casing logic only handled equal-length
    word rules; the first one-to-two expansion (`planner` → `task_agent`)
    produced `TASKAGENT_MODEL` and `_ModerateStubTask_Agent` until the joiner
    was derived from the identifier's own inter-word separator (a leading
    underscore is not one). `rename_engine.infer_separator`.
  - A gitignore line without its `.dockerignore` mirror turns `make verify`
    red at the next build-open baseline (infra image-hygiene test); the
    failure surfaces one commit later than its cause.
  - A table-driven identifier sweep renames stored enum literals as happily
    as code names: `planner-proposed` (a `country_group.authorship` value in
    plan payloads) went through the 044 sweep and surfaced only as an enum
    change in the OpenAPI diff. Review every changed quoted literal in the
    sweep diff against the migration's rewrite list before the gate.
  - Hash-pinned prompt modules must be excluded from any identifier sweep
    whole, not just their string literals: a docstring rename is a hash
    change (rubric "every other hash unchanged").

## Deferred work

_(Phase 7: `docs/deferred.md` deltas)_
