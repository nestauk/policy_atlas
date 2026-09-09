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

### Phase 2 — task kind, links, registry, slice revision (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full) | pass | backend 2674 passed (8:01); frontend 625 tests / 80 files; okf 143/0; mypy 320 files clean; ruff clean; infra 46; audit-paths 0; prompt-guard unchanged; `drift-check: OK`; build OK |

Revision `b5e1d7a4c026` (revises `a7d3f1c8e2b5`): `task.capability` +
`ck_task_capability`; `ck_capr_capability` widened; `uq_plan_id_task`;
`evidence_scope.purpose` + `ck_scope_purpose`; `evidence_scope.plan_id` +
composite `fk_scope_plan_task`; `task_link` with `fk_task_link_source_run_task`,
`uq_task_link_pair`, `ck_task_link_distinct`, `ix_task_link_target_task_id`.
Downgrade refuses while any `task` or `capability_run` row carries
`options_scoping`, naming `scripts/ops_remove_scoping_tasks.py` (A5); the
round-trip test proves the refusal and the operator script's FK order.

**Registry (S1):** all ten validate sites and seven compose sites route through
`runtime/capability_registry.py`; `_open_capability_run` writes the task's
capability; `pause_points` / `lattice_name_for` / `lattice_policy` take the
capability's lattice (`lattice_policy` returns `off` for a name outside the
given lattice — A2's protection). **Deviation from S1 as written:**
`SteerPointDefault`'s validator was not routed through the registry —
`task_plan.py` cannot import the registry (cycle via `steering`); the ES
validator keeps checking `STEER_POINTS`, the registry's ES `steer_points` is
`frozenset(STEER_POINTS)` and a test pins the two together; the scoping plan
gets its own set the same way (Phase 3.2).

**Left for Phase 5, deliberately:** the four `lattice_name_for` /
`lattice_policy` calls inside the runner's boundary loop still take the ES
default because `_SteeringState` carries no capability; identical behaviour
today (`lattice_for("evidence_search") is LATTICE_POINTS`). Phase 5.2 must
put the capability on `_SteeringState` or `baseline_confirm` never fires.

**OpenAPI diff:** additive only — `TaskLinkOut`; `TaskCreate.capability`,
`.project_ids`, `.from_task_ids`; `TaskOut.capability`, `.from_task_ids`,
`.links`; three description strings replaced. No path or field removed or
retyped.

**Gotcha recorded:** the downgrade refusal bites the whole migration-test
family when any test commits a scoping task and leaves it — an autouse
cleanup in `test_task_links.py` deletes links then tasks. Any later test that
commits a scoping task must clean it up.

### Phase 3 (backend: 3.1 prompt, 3.2 plan/chain/router, 3.3 inherit) (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make verify-fast` | pass | backend 2740 passed (8:05); mypy 327 files clean; ruff clean |
| `make prompt-guard` | pass | 16 modules unchanged (the three new surfaces pinned at 91beec2a) |
| `make openapi-sync` + `make drift-check` | pass | `drift-check: OK` |
| `tests/runtime/test_inherit.py` | pass | 5 tests, rolled-back fixtures |

**Flagged deviations (3.2):**
7. **`PlanOut.plan` and `TaskAgentTurnOut.plan` became nullable** — a scoping
   plan has no Evidence search payload. The contract asked for additive
   fields only; nullability of an existing field is a type widening the
   frontend must null-check (done in 3.4). Everything else in the diff is
   additive (`ScopingPlanDraft`, `ScopingPlanPatch`, `TaggedOut`,
   `ScopingConstraintOut`, `YourContextOut`, `ScopingSteerPointDefaultOut`,
   `BaselineConfirmedOut`, `ConfirmBaselineIn`; `capability`, `scoping`,
   `scoping_plan` fields).
8. **One new acquire directive key, `search.record_cap`** (plan S2 allowed
   it): the grammar had no per-backend cap key (caps came from
   `DEPTH_CONSTANTS`); fail-closed integer `1..200`, absent = today's
   behaviour; `BASELINE_ACQUISITION_TARGET = 25` per backend (measured in
   Phase 7).
9. **`synthesis_tools` grammar widened for template mode only:** `nav_label`
   accepted on supplied sections (it was read but unreachable); `section_budget`
   no longer caps the supplied list when `template` is present (P14: it means
   "proposals allowed"); `DIRECTIVE_TEMPLATE_FOCUS_MAX = 600` for template
   foci (lead-authored code, not untrusted directive text — the 200-char
   bound stays for everything else). Lead confirms all three.
10. **`tests/helpers.delete_task_data`** nulls `evidence_scope.plan_id`
    before deleting plans (the new composite FK); shared helper, additive.
11. **Inherit coverage statement** ports the existing `coverage_out`
    sentence ("Searching completed. Coverage was judged adequate."), not the
    spec's aspirational "documents retrieved and passed … not searched"
    wording, which no read model builds yet.

**Counts pinned:** the supplied baseline section list is seven model-written
sections plus the code-rendered Sources = 8 = `SECTION_CAP`.

_(Phase 3 frontend, Phase 4 … Phase 7 rows are appended as each phase closes.)_

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

6. **The frontend URL token `?chat=planning` became `?chat=task_agent` with
   no alias** (review finding on `conversationState.ts`): a tab opened before
   the deploy that still carries `?chat=planning` shows "This chat couldn't be
   opened." until the user clicks the Task Agent. The token is transient view
   state, not a durable link, and the 038 rule (no redirect, no fallback code)
   applies to it as to the route. Recorded as a deliberate break.

### Phase 1 review pass (`/code-review medium` on e4128528, 2026-09-09)

Eight findings, none against the schema change (the reviewer confirmed the
revision, its round-trip and the hand-edited historical tests). Dispositions:

| # | Finding | Disposition |
|---|---|---|
| 1 | `?chat=planning` URL token renamed with no alias | recorded (deviation 6) |
| 2 | Backend wire-visible strings still said `task_agent` (422 details on the conversations router, the `run_active`/`stale_turn` details, the stub replies) | **fixed** by hand → "Task Agent" |
| 3 | Sweep + disclosed hand edits do not reproduce the commit | **fixed in the tool** (phrase rules for string/comment spans, `TaskAgent` → `Task Agent` joiner, `ruff --fix` post-step); the residual hand-edit list is recorded below |
| 4 | Two regex edges (unanchored role-union protector; `[Pp]lanning turn` without the hyphen lookbehind) | **fixed in the tool** |
| 5 | Kept `"planner"` role literal protected only for `:` / `=` / `==` shapes | **fixed in the tool**; engine test added |
| 6 | Ordinary English swept: `planning delays` (a fixture), `fan-out planning` (a docstring) | **fixed** by hand; contexts added to the tool |
| 7 | Migration docstring claimed a `pg_constraint` pre-check that did not exist | **fixed**: the check is implemented (upgrade and downgrade), with a test |
| 8 | Engine extraction changed the 038 tool's scan headings, refusal text and `is_dir` sentinel | **fixed**: carried as table fields with the 038 values |

### Phase 1 hand-edit record (replay of the sweep against the commit)

Replayed from `5854676a` (the last commit with `planner.py`) with the fixed
tools (`fed7622f`): `git mv` list → `--apply` phases 3, 4, 5 → `ruff --fix` →
`make openapi-sync`, diffed against `e4128528`. Thirty-two files differ only
where the fixed tool now writes "Task Agent <noun>" in prose that the commit
had left as `task_agent <noun>` — the replay is the better text and those
strings were hand-fixed afterwards (`fed7622f` and the Phase 2 commit). The
edits the sweep does not reproduce, by design:

| File | Hand edit |
|---|---|
| `tests/core/test_migration_038.py` | catalog assertion moved to `c1a7f4e9b0d2`; deploy-window write `created_by="task_agent"` |
| `tests/core/test_migrations_029.py`, `test_migrations_028.py`, `test_planning_transcript_migration.py` | head-side reads on the new table and kind; `legacy_table` below the revision |
| `tests/api/test_api_conformance.py` | the `agent` leaked-name invariant strips the product words `task-agent`/`task_agent`/`taskagent` first |
| `infra/DEPLOYMENT.md` | the "Renamed in task 044" note (old name written by hand after the sweep mangled it) |
| `frontend/src/views/workspace/chat/conversationState.ts` | `const taskAgent` (a snake-case TS local) |
| `docs/knowledge/synthesise-is-run-terminus.md`, `coverage-base-project-pool-wide.md` | EB → ES (outside the manifest's 13-file list; deviation 4) |
| `docs/specs/capabilities/options-scoping/{components,capability}.md` | EB → ES inside fenced ASCII diagrams (the tool skips code fences) |
| `frontend/src/views/historyPresentation.{ts,test.ts}`, `chat/ChatMessages.{tsx,test.tsx}` | "The Task Agent replied", "Open Task Agent" |
| `tests/api/test_task_agent_router.py` | one signature wrapped for the line limit |
| `runtime/task_agent.py` | module docstring "``planner_v1`` planning call" |

### Phase 4.1 — the template-keyed section writer (2026-09-09, lead)

`synthesis_backend.py`'s `SECTION_SYSTEM_PROMPT` is now `SECTION_REPORT_PREAMBLE
+ SECTION_CORE`; `SECTION_PREAMBLES` maps `report` and `baseline`;
`_section_system_prompt(seed)` selects by the seed's `template` and fails
closed on an unknown one. The Evidence search assembly is byte-identical to
`synthesise_section_v10` before the split: sha256 `87126525…9a42` without and
`e38e6c1e…17fb` with the priority block, pinned by
`test_section_prompt_templates.py`. **Fact found while re-pinning:**
`scripts/prompt_hash_guard.py` pins files whose *name* contains "prompt", so
`synthesis_backend.py`'s inline section prompt was never hash-pinned; the
contract's "re-pinned once as a words-only diff" therefore has nothing to
re-pin, and the byte-identity test is the pin. Recorded as a knowledge
candidate and a deferred item (add the inline-prompt modules to the guard).

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
  - The slice revision's downgrade refusal (A5) turns every migration
    round-trip test red behind any test that commits an `options_scoping`
    task and leaves it; shared-Postgres suites need the scoping fixtures
    cleaned up in the test that made them.
  - `capability_registry` cannot be imported from `task_plan.py` (registry →
    steering → task_plan); per-capability validators therefore hold their own
    steer-point sets, pinned equal to the registry's by test.
  - `make -C backend typecheck` runs `mypy src tests` from `backend/`, so
    repo-root `scripts/*.py` (now including a destructive operator script)
    is never typechecked.
  - `scripts/prompt_hash_guard.py` pins by filename (`*prompt*`), so the two
    inline prompt carriers (`synthesis_backend.py`, `finding_vetter.py`) are
    outside the guard; a prompt edit there is invisible to `make prompt-guard`.
  - Hash-pinned prompt modules must be excluded from any identifier sweep
    whole, not just their string literals: a docstring rename is a hash
    change (rubric "every other hash unchanged").

## Deferred work

_(Phase 7: `docs/deferred.md` deltas)_
