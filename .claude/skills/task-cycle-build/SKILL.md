---
name: task-cycle-build
description: >
  Task-cycle phase B (steps 5–6): implement an approved Policy Atlas contract/plan and
  produce verification evidence. Trigger when starting implementation of a contracted
  slice ("implement task NNN", "start the build", a fresh conversation opening on an
  approved plan). Runs in its own conversation (B); scope a /goal to "through step 6"
  only — never let it span the review phase. Tier rules, hard gates and conversation
  map live in the task-cycle spine — read it first.
---

# Task cycle — build phase (steps 5–6)

Builds the approved contract and plan, simplifies it, and records the evidence.
Conversation B. Read the [task-cycle spine](../task-cycle/SKILL.md) first. Optional
`/goal`: "through step 6: verification.md complete, `make verify` green, phases committed".

## Exit condition

- [ ] `make verify` fully green on the simplified code; all plan checkpoints committed.
- [ ] Step 5c done and recorded.
- [ ] End-to-end flow driven at the contracted scope; exact command recorded.
- [ ] `verification.md` complete: flagged deviations, executor provenance, knowledge candidates.
- [ ] Frontend-heavy slice: both polish passes done, annex updated, owner sign-off recorded.

Then **stop. Do not run the review stack here.** It runs in a fresh conversation with
[`task-cycle-review`](../task-cycle-review/SKILL.md): the adjudicator must not be the
conversation that wrote the code.

## Human approval (🛑)

- A blocking design problem (task-cycle-design § Spec refinement).
- A hard gate the contract did not approve (spine § Stop conditions).
- The owner's polish sign-off (frontend-heavy slices).

## Forbidden

- A commit on a red check or on the default branch; a push.
- Re-deciding executor routing; adding or downgrading full-verify gates against the
  plan's gate map (**the gate map is binding**).
- A live run bigger than the contract pinned: spend the gate never approved.
- Coding around an outgrown spec.
- Hand-polishing weak delegated output: rewrite the brief or escalate the model.
- Writing durable records (`docs/knowledge/`, `docs/deferred.md`, agentic-ops claims):
  step 8 writes them against the final code.

## Re-ground

Read `contract.md`, `plan.md` and the cited specs. Run `make verify`: **never build on a
red base** that you will later blame on your own changes.

## Step 5 — Implement

Load `agent-skills:incremental-implementation` with the Skill tool at the start, and
`agent-skills:git-workflow-and-versioning` before the first commit.

**Delegate per the plan's executor marks** (harness.md § Agent-side model routing has the
brief shape): `deep-reasoner` is the default doer; `fast-worker` for mechanical volume;
`frontend-designer` for frontend; Codex (`codex:rescue`) only where the plan marks it, and
then Claude anchors the review. Record in `verification.md` § Review handoff which
executor wrote which files. Review delegated output before it lands.

Subagents do not see this skill. In each brief, tell the subagent to load, with the Skill
tool before it starts, each skill whose condition holds (the lead loads the same when it
does the work itself):

- framework code (LangGraph, SQLAlchemy, pydantic, alembic) → `agent-skills:source-driven-development`;
- a seam or interface → `agent-skills:api-and-interface-design`;
- a bug fix → `agent-skills:test-driven-development` (`/test`): a failing test that
  reproduces the bug first;
- a schema or API migration → `agent-skills:deprecation-and-migration`;
- logging, metrics or tracing → `agent-skills:observability-and-instrumentation`.

When `make verify` is red, load `agent-skills:debugging-and-error-recovery` and find the
root cause; do not guess. Escalate a stubborn or large fix to `codex:rescue` (write-capable:
a doer, not a reviewer).

**Tests.** Write one focused test for each behaviour the contract states, at a public
boundary: the HTTP route, the public function, the rendered component, the stored row.
Mock only what the repository does not own (network, model providers, the clock). Do not
test an internal helper that a boundary test already covers. A frontend test checks what
the user sees and can do; it never asserts a style class name, and a polish round adds no
test for looks. Scratch checks and one-off scripts are not committed. The existing tests
are not the model for new ones: many check more than this rule asks. Keep the guards the
repository relies on: tenancy and access rules, migration round-trips and database
constraints, parser security, drift checks between lists that must agree. The number of
tests is a cap, not a quota: one test may cover two behaviours. Prefer no new test to a
bad test. Write each test from the behaviour the contract states, not from the code you
just wrote.

Code, comments, docstrings and test names carry no task numbers, dates, review or polish
rounds, contract or rubric item ids, or owner rulings. ADR numbers may stay.

structlog only (no print or stdlib logging in package code). Touch only what the contract
requires. Each plan checkpoint ends with a commit on `task/NNN-slug`, gated by the
**tiered commit gate**:

- Intermediate commits: green `make verify-fast` (test-fast + typecheck + lint).
- Frontend polish commits: green `make verify-fast` and `make frontend-verify-fast`.
- **Full `make verify`** at the build-open baseline, at any phase touching **schema or
  ingest-adjacent code** (its table-count and metadata assertions live in
  `test_ingest_full_text.py`, which test-fast excludes), and at the **step-6 exit**.
- Any red is a full stop, whichever suite ran.

**When building reveals a design problem**, size it:

- **Blocking / material** (the contract or a spec is wrong enough to change the design):
  pause and flow it back through task-cycle-design § Spec refinement.
- **Minor, resolvable within the contract's own vocabulary** (the contract offers
  "None/absent" and one makes its stated intent true): resolve it, add a test, and **flag
  it in `verification.md`'s diff summary**. Visible deviation, not silent drift.

**Capture knowledge now, author it at step 8.** What the build learns is lost at the
conversation boundary unless it goes on step 6's knowledge-candidates list.

## Step 5b — Polish passes (frontend-heavy slices)

After step 5, on green `make verify-fast`, two passes on the live dev app, in the same PR:

1. **Agent pass**: the pinned `frontend-designer` reviews the build against
   `design-annex.md` and applies material fixes within the annex. Copy and direction
   changes are proposals to the lead.
2. **Owner pass**: the owner looks at the live app; the lead applies the notes, round by
   round until sign-off, within the contract's round budget.

Rulings go into the annex, not the contract. The sign-off is a 🛑 recorded in
`verification.md`. The rubric has one row: "polish passes complete, annex updated, owner
sign-off recorded". Run the passes in their **own conversation**, re-grounded from the
annex and the running app (`make dev`; Playwright screenshots), not the build transcript.
Both passes run again at the end of review.

## Step 5c — Simplify

Never skipped. Runs after step 5 (and 5b).

- Load the `simplify` skill with the Skill tool; let it apply its fixes to the slice's
  changes (`git diff dev...HEAD`).
- It must not change hash-pinned prompt files (listed in `scripts/prompt_hashes.json`)
  unless the slice already changes them.
- Run the check the commit rules require, then commit.
- Record in `verification.md` what it changed and what it found but did not apply. Put
  each finding it left because it is structural on the knowledge-candidates and deferred
  list in § Review handoff, so step 8 writes it into `docs/deferred.md`.

Step 6 then verifies the simplified code.

## Step 6 — Verify

Fill `docs/tasks/_templates/verification.md` → `docs/tasks/NNN-slug/verification.md`: the
`make verify` table, named-test results, the **exact** end-to-end command, the diff summary
(minor deviations flagged), public safety, gaps, the step-5c record, and the **knowledge
candidates** in § Review handoff: one bullet per durable-seeming lesson, however raw
(surprises, gotchas, invariants that held for a non-obvious reason), not only deviations.
Step 8 cannot see a lesson that is not on the list.

Drive the affected flow end-to-end with `/verify`; that run gives the exact command. **The
live check runs at the scope the contract pinned.** A `/goal` may drive the implement ↔
verify loop only when the stop condition is objective (`make verify` green, a named test).

**Fixture/recording slices only:** verify sanitized fixtures by **substring-auditing the raw
recording against the committed fixture** (no identifying raw string survives), not by
reviewing the sanitizer's key list (`docs/knowledge/sanitized-fixtures-audit-against-raw.md`).
If you know at design time that the slice records, put the audit in the contract's
acceptance checks.
