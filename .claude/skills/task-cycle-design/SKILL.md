---
name: task-cycle-design
description: >
  Task-cycle phase A (steps 1–4): contract → rubric → plan → ADR for one Policy Atlas
  slice, with human approval gates and contract/plan-stage adversarial reviews.
  Trigger when opening a new slice (writing its contract), drafting or revising a
  rubric/plan, or when the user says "contract task NNN" / "plan the next slice".
  Runs in its own conversation (A); it ends at human 🛑s, never rolls into the build.
  Tier rules, hard gates and conversation map live in the task-cycle spine — read it first.
---

# Task cycle — design phase (steps 1–4)

Fixes what one slice builds and how: contract, rubric, plan, ADR when due. Tier 2+ only;
conversation A; ends at human 🛑s. Read the [task-cycle spine](../task-cycle/SKILL.md)
first. Templates: `docs/tasks/_templates/`.

## Exit condition

- [ ] Contract approved; rubric drafted; contract-stage adversarial review folded in (Tier 3+).
- [ ] Plan confirmed, with executor marks, gate map and plan-stage adversarial review folded in (Tier 3+).
- [ ] ADR written, if due.
- [ ] Frontend-heavy slice: design annex and mock frozen before the contract.
- [ ] All committed on `task/NNN-slug`. Then **stop**: the build runs in a fresh
      conversation with [`task-cycle-build`](../task-cycle-build/SKILL.md).

## Human approval (🛑)

- The contract, before planning (Tier 2+). A material change from its adversarial review
  reopens this 🛑.
- The plan, after its adversarial review (Tier 2+).
- Every spec change (§ Spec refinement).
- The mock's direction ("direction settled"), and any new dependency.

## Forbidden

- Product code, or rolling into the build in this conversation.
- Phase state in `AGENTS.md`: it duplicates the branch name and `Status` line and goes stale
  on `dev` after every merge.
- Edits to `docs/specs/sources/**` (frozen, ADR 0002).
- A colour, weight or spacing in a contract.
- Committing a raw adversarial review record. It stays in the task's gitignored
  `research/` folder; the findings and their adjudication go into the contract (or plan).
  Older task folders hold committed `adversarial-review-*.md` files: do not copy that.

## Frontend-heavy slices: design pass before step 1

Looks settle only once seen, and a contract that names looks turns each taste change into
a deviation. So, in conversation A:

1. **Ground**: explorers cover the touched surfaces (states, copy, tests, the mock API)
   and the research; conclusions in `docs/tasks/NNN/research/` (gitignored).
2. **Script**: the lead writes `docs/tasks/NNN/design-annex.md` from the template: every
   state, transition and line of copy, in the product voice. The lead owns copy and
   direction; agents gather facts.
3. **Mock**: a `builder` builds a throwaway page from the script, published as a private
   artifact. Rounds with the owner run until structure, states and copy freeze. Stop rule:
   the owner's "direction settled", never pixel satisfaction. Each round edits the script
   first, then the mock.
   - Direction open: the `prototype` skill (versions of one UI piece behind a picker). It
     runs only when called: the owner types `/prototype`, or the brief tells the `builder`
     to read `~/.claude/skills/prototype/SKILL.md` first.
   - New frontend dependency needed: `pick-ui-library` (the owner types
     `/pick-ui-library`, or the agent reads `~/.claude/skills/pick-ui-library/SKILL.md`).
     The dependency still needs owner approval.
4. **Contract** **pins behaviours, states, interfaces, invariants and measured outcomes,
   and cites the annex by version.** Rubric rows are testable (vitest, the mock journey).
   Visual decisions live only in the annex, so a change is an annex edit.

Every agent that touches the frontend in any phase is the pinned **`frontend-designer`**
(`.claude/agents/frontend-designer.md`). It loads the frontend design skills, `PRODUCT.md`
(committed; § Product Principles are the team's six), `DESIGN.md` (committed) and the
slice's research first, because unskilled workers ship correct but unpolished surfaces. A
frontend brief to any other agent needs a reason in the plan. Polish passes: task-cycle-build
§ Step 5b and task-cycle-review § Frontend-heavy slices.

## Step 1 — Contract

- **Identity** lives only in the branch name `task/NNN-slug` and the `Status` line of its
  `contract.md`. A fresh conversation re-grounds from `docs/tasks/<newest>/contract.md`.
- **Read the deferred work for the parts the slice touches**: the matching sections of
  `docs/deferred.md` (it is ordered by part of the system). State in the contract which
  entries the slice takes in. An entry is read only when its part is opened, so this is
  the point where it is picked up or left on purpose.
- If the request is unclear (why, for whom, what "done" means), load
  `agent-skills:interview-me` with the Skill tool and clarify with the user before you
  write the contract.
- Copy `docs/tasks/_templates/contract.md` → `docs/tasks/NNN-slug/contract.md`. Read the
  cited specs *in depth*. If one is wrong or incomplete, refine it first (§ Spec refinement).
- If the contract defines a seam or public interface, load
  `agent-skills:api-and-interface-design` with the Skill tool first.

**Live-check scope is a contract-time pin.** If acceptance includes a live manual check,
name its scope. Default: the changed surfaces plus one cheap full-chain smoke. A full live
e2e is an upgrade the gate approves with its wall-time cost named. Do not inherit the
previous slice's shape.

**Design docs must be legible cold**, because the human gate and conversation B read them
without your context:

- **Define jargon once**, in the contract's § Terms: internal labels (`P1`), abbreviations
  (`PSS`), words in a special sense (grain, round). Rubric and plan point at it.
- **Map what the slice touches** in the shape that fits (UI: surface → number shown →
  rendering file → broken / correct-do-not-change). "Do not change" rows weigh the same.
- **One defect numbering everywhere**: goal, scope, invariants, plan phases and rubric
  items cite the same ids, so an invariant with no defect shows as a hole.
- **Split anything that needs two acceptance invariants.** One defect, one cause, one invariant.
- **Resolve name collisions from the code**: say which is the field and which the label.

Prose is ASD-STE100: short sentences, active voice, plain words ("accepted defect", not "wart").

🛑 **Human approves the contract before planning** (Tier 2+).

**Contract-stage adversarial review** (Tier 3+; Tier 2 on demand), after approval and
before planning: a **read-only** `codex-rescue` brief (§ Codex plumbing) attacks
`contract.md` and `rubric.md`. Reading list: contract, rubric, cited specs, AGENTS.md,
the sections of `docs/deferred.md` for the parts the slice touches, the previous slice's contract as precedent. Targets: unstated
assumptions, missed requirements, spec contradictions, simpler alternatives. Human-settled
decisions are *context, not targets* (challenge only on contradiction). The lead folds
findings into the contract; material changes reopen the 🛑, minor ones are noted. The
contract fixes the design here (schema, interfaces, tests), so attack it at its own gate.

## Step 2 — Rubric

Copy `docs/tasks/_templates/rubric.md`. Draft it with the contract, so the step-1 review
and adversarial review see both.

## Step 3 — Plan

- Run `/plan` (read-only); save the accepted plan to `docs/tasks/NNN-slug/plan.md`.
- If the slice has no precedent shape, load `agent-skills:planning-and-task-breakdown`
  with the Skill tool first. If the plan defines a seam or public interface, load
  `agent-skills:api-and-interface-design`.
- For a pattern-following slice, mirror the previous `plan.md` against the **as-built
  code**, not the plan's own claims. The plan cites the contract's tables and numbering.
- **Reuse before new code**: for each new helper, type or module, the plan names the
  existing one it reuses, or states that none exists. Duplication is one line to prevent
  here and a cross-module refactor to remove at review.
- For a key decision at Tier 3+, load `agent-skills:doubt-driven-development` with the
  Skill tool. For a real design fork, set the options side by side in an **Artifact**.

**Executor routing is a plan-time decision.** Mark each plan task `lead` · `fast-worker` ·
`deep-reasoner` · `frontend-designer` · `builder` · `codex` (full ladder: harness.md
§ Agent-side model routing):

- Cannot write a self-checkable brief → `lead`.
- Prompt-bearing work, taste-bearing surfaces, adjudication, seam *design* (signatures,
  semantics, the brief) → `lead`, regardless of budget. The *implementation* of a
  lead-designed seam against a machine-verifiable done is delegable.
- **Judgment-bearing execution** (nontrivial logic, multi-file coherence, unfamiliar APIs)
  with a machine-verifiable done → `deep-reasoner`, the
  **default doer**. Mark `codex` only when the build needs a second family's view, with the
  reason in the plan: the family flip already happens at step 7.
- Frontend implementation or polish → `frontend-designer`.
- Mechanical transcription of an exact spec (test scaffolding, sweeps, boilerplate) →
  `fast-worker`.
- One-command edits (`sed` renames, count bumps) → `lead` **inline**.
- Analysis, not code → `deep-reasoner`; Codex takes the second seat in two-independent-takes.

Routing is not re-decided mid-build.

**Gate consolidation is a plan-time decision.** The plan marks which boundaries run full
`make verify` and which `make verify-fast`. Adjacent low-risk phases (new files, no schema
or reader contact) may share one full-verify gate, argued in the plan. The mandatory
classes (build-open baseline · schema/ingest-adjacent phases · step-6 exit) are never skipped.

**Plan-stage adversarial review** (Tier 3+; Tier 2 on demand: a loose contract, a
surprising plan, a 🟡/❓ spec area), before the 🛑: a **read-only** `codex-rescue` brief on
`plan.md`, with the contract as *context, not target*. Reading list: contract, plan, cited
specs, AGENTS.md, the sections of `docs/deferred.md` for the parts the slice touches. Targets: plan↔contract/spec fit, sequencing risks,
🟡/❓ items, missed requirements, simpler alternatives. If it cannot critique from the files
alone, the files are not a self-sufficient handoff: fix that first. (Two-independent-takes
generates options *before* a high-stakes call; this attacks the chosen plan.)

🛑 **Human confirms the plan** (Tier 2+), with the adversarial findings folded in.

## Step 4 — ADR

Only when a design decision is made or changed (Tier 3–4 by default). Load
`agent-skills:documentation-and-adrs` with the Skill tool first. `docs/adr/NNNN-slug.md`,
status Accepted with the sign-off date.

## Spec refinement (specs are living)

Specs are intent, not golden (`docs/specs/README`). Refinement fires here (a spec is wrong
before you contract on it) and from the build (building shows the design is wrong). Load
`agent-skills:idea-refine` and `agent-skills:spec` with the Skill tool; load
`agent-skills:documentation-and-adrs` to record the change. Flow: propose → 🛑 **human
decision** → update the spec and status markers (and an ADR if consequential) → a line in
the bundle's `log.md` → resume. Sources are **frozen**: change the *spec* (ADR 0002).

## Codex plumbing (document reviews)

- `/codex:review` and `/codex:adversarial-review` are **user-typed only** and
  **diff-shaped**, so steps 1 and 3 use the `codex-rescue` subagent.
- ⚠️ It is **write-capable** by default: every brief states **read-only / critique-only**.
- ⚠️ It is **async**: its final message is **either the findings or a job id**; check
  which first. For a job id: `scripts/codex_job.sh wait <job-id> [timeout-s]` (or
  `status`/`result`), the runtime's **native** wait.
- ⚠️ Do not write your own status poll: a filtered loop can hide a hard error until timeout.
- **Fallback**: if Codex fails or is not available, a `deep-reasoner` subagent in a fresh
  context runs the same read-only brief, and the contract's status line records that a
  Claude reader stood in. A second independent read still finds defects the other lanes miss.
