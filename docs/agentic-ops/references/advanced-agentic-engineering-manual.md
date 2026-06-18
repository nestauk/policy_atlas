# Advanced Agentic Engineering Manual

*A practical operating system for building software with coding agents while preserving correctness, security and human control*

**Draft v0.1 | June 2026**

## How to use this manual

This manual is the advanced companion to the AI-native Development Playbook. The playbook is for broad organisational adoption. This manual is for engineers and technical leads who want to run the full agentic engineering process in a repo, including specs, contracts, rubrics, skills, hooks, review agents, tool adapters, loops and harness maintenance.

The goal is not to make every task heavy. The goal is to build a small, legible system around agents so that they can do more work safely. Use the lightest effective harness for the task at hand.

Core thesis:

```text
Build the product.
Build the machine that helps build the product.
Only automate stable recurring work.
Keep all three under human judgement.
```

## 1. Core philosophy

Agentic engineering is professional software engineering with agents in the implementation and verification loop. The human specifies intent, constraints and acceptance criteria. Agents plan, edit, run tools, test, review and iterate. The human remains accountable for correctness, security, architecture, maintainability and merge decisions.

The stable workflow is:

```text
thin context
-> spec
-> task contract
-> rubric
-> scratchpad
-> skill-driven execution
-> independent verification
-> adversarial review
-> simplification review
-> human sign-off
-> verified memory update
```

The scarce resource is not code generation. It is review bandwidth, judgement, product taste, security boundaries and confidence that generated code is correct.

### 1.1 Make AI-native development safer by default, not heavier by default

A tiny typo does not need a full task contract. An auth change does. The workflow should be risk-sensitive.

```text
Low risk: direct edit -> focused check -> quick review.
Medium risk: plan -> task scope -> implementation -> checks -> AI review -> human review.
High risk: explicit contract -> rubric -> evidence -> independent verification -> security/adversarial review -> human sign-off.
```

### 1.2 The human moves up the loop

Humans do not need to inspect every generated line with the same depth. Humans do need to inspect enough evidence, tests, intent, risk areas and design fit to stand behind the merge. The human is not removed. The human moves from typing code to owning the system of trust.

### 1.3 The model is not the agent

A coding agent is the model plus the harness around it: context, tools, filesystem, shell, skills, hooks, permissions, subagents, MCP, review loops, memory, state files, sandboxes and observability.

When the agent fails, ask:

```text
Which harness assumption failed?
What was missing from context, tooling, checks, permissions, task scope or review?
Should we fix code, tests, hooks, skills, rules or the workflow itself?
```

Do not blame the model by default. Do not add rules by default. Diagnose the harness.

## 2. Harness levels

Match harness weight to task risk and uncertainty.

| Level | Pattern | Use when | Do not use when |
|---|---|---|---|
| 0 | Direct edit | Small obvious change | Risk, ambiguity or multiple files are involved |
| 1 | Plan -> implement -> verify | Normal non-trivial work | Task touches trust boundaries or public interfaces |
| 2 | Contract + rubric + goal loop | Completion can be measured | Goal is vague or subjective |
| 3 | Planner -> generator -> evaluator | Longer task needing independent QA | A single small diff would be enough |
| 4 | Worktrees, cloud agents, dynamic workflows | Large mechanical migration, audit, parallel research | Core architecture or unclear product design |
| 5 | Scheduled loops and automations | Stable recurring work | Manual version is still unreliable |

Use the lowest level that gives enough confidence.

## 3. Repo operating system

A repo that works well with agents has shared truth in files, executable checks in commands, and thin tool adapters. It does not rely on chat history.

Recommended structure:

```text
repo/
  AGENTS.md
  CLAUDE.md
  Makefile

  docs/
    specs/
      product.md
      system.md
      index.md
    plans/
    contracts/
    rubrics/
    verification/
    work/
    knowledge/
      index.md
      architecture/
      concepts/
      runbooks/
      integrations/
      conventions/
    adr/
    deferred.md
    agentic-ops/
      harness.md
      environment.md
      readiness.md
      backlog.md
      failure-log.md
      metrics.md
      loops/

  .claude/
    skills/
    agents/
    hooks/

  .cursor/
    rules/
    plans/
    mcp.json
    permissions.json
```

Start smaller when onboarding colleagues. Add the advanced directories when the workflow proves useful.

### 3.1 Shared truth vs tool adapters

Use one shared repo operating system and thin adapters for each tool.

| Layer | Recommended owner |
|---|---|
| Shared agent protocol | `AGENTS.md` |
| Claude Code adapter | `CLAUDE.md`, `.claude/skills/`, `.claude/agents/`, hooks, plugins |
| Cursor adapter | `.cursor/rules/`, `.cursor/plans/`, `.cursor/mcp.json`, `.cursor/permissions.json` |
| Durable source of truth | `docs/specs/`, `docs/contracts/`, `docs/rubrics/`, `docs/verification/`, `docs/adr/`, `docs/knowledge/` |
| Executable truth | `Makefile`, scripts, tests, CI |

Rule:

```text
Shared guidance goes in shared files.
Tool-specific behaviour goes in tool-specific files.
Never copy the same long instruction into both.
```

## 4. Context and memory

Always-loaded context should be small. The more you put into every prompt, the more you dilute attention, increase cost and risk stale instructions.

### 4.1 `AGENTS.md` as protocol and landmine list

`AGENTS.md` should not be a codebase tour. Agents can inspect files and directories. Use it for non-discoverable operational truth.

Good content:

```text
Use uv, not pip.
Run tests with --no-cache because cached fixtures produce false positives.
The legacy auth module is deprecated but still imported in production.
Never edit generated files in src/generated/.
Schema, auth, dependency and CI changes require approval.
```

Bad content:

```text
This repo has a frontend and backend.
The source code lives in src/.
The project uses TypeScript.
There is a tests directory.
```

Treat `AGENTS.md` as a smell ledger. Every line should trace to a real failure, hard constraint or landmine. Each line should have an expiry question: could this be replaced by a test, hook, linter, clearer code structure or better command?

Minimal `AGENTS.md`:

```markdown
# Agent protocol

- Use `make test`, `make typecheck`, `make lint`, `make build`.
- Do not change schema, auth, dependencies, CI or public interfaces without approval.
- Never edit generated files.
- Use `docs/contracts/` for task scope.
- Use `docs/rubrics/` for completion criteria when present.
- Provide evidence before claiming completion.
- Touch only what the task requires.
- If requirements conflict, stop and ask.
```

### 4.2 `CLAUDE.md` as Claude adapter

Keep `CLAUDE.md` short. Point to `AGENTS.md` and shared docs rather than duplicating them.

```markdown
# Claude Code adapter

Read `AGENTS.md` first.

Use:
- `/plan` for non-trivial changes.
- `/goal` only when completion is measurable.
- `/code-review` before meaningful commits.
- `/security-review` for auth, data, secrets, dependencies, MCP, CI or production config.

Prefer skills for reusable workflows.
Prefer hooks for rules that must be enforced.
```

### 4.3 Cursor rules as scoped adapters

Use `.cursor/rules/` for Cursor-native behaviour, especially file-pattern-specific guidance.

Example `core.mdc`:

```markdown
---
description: Core Cursor agent rules
alwaysApply: true
---

- Follow `AGENTS.md`.
- Use `.cursor/plans/` for saved plans.
- Keep changes scoped to the task.
- Produce PR evidence before review.
```

Example path-scoped rule:

```markdown
---
description: Backend-specific rules
globs: ["backend/**/*.ts"]
---

- Preserve service boundaries.
- Do not alter database migrations without approval.
- Prefer existing error-handling patterns.
```

### 4.4 OKF-style durable knowledge

Use `docs/knowledge/` for durable, verified domain and repo knowledge. Do not use it as a diary.

Good content:

```text
domain concepts
architecture explanations
API contracts
integration quirks
schema meanings
runbooks
testing conventions
deployment assumptions
recurring pitfalls
verified rules
```

Memory update rule:

```text
Only durable, verified learning goes into long-term memory.
```

Use the progression:

```text
fail -> investigate -> verify -> distil -> consult
```

Example OKF file:

```markdown
---
type: Rule
title: Price fields in imported order data
tags: [data-model, imports, pricing]
verified_by: "make test-unit TEST=orders_import_price_fields"
---

# Price fields in imported order data

## Rule

`orders.prc` is stored in minor currency units. Convert to major units only at presentation boundaries.

## Verification

Verified by `make test-unit TEST=orders_import_price_fields`.

## Why this exists

A previous implementation treated `prc` as major units and produced 100x overstatements.
```

## 5. Specification and planning

Specs are not bureaucracy. They are the shared intent that keeps agents from guessing. But specs should be just detailed enough. Too little context produces hallucination. Too much context creates drift and cost.

### 5.1 Spec Kit as the specification front-end

GitHub Spec Kit is useful for the front half of the workflow:

```text
constitution -> specify -> clarify -> checklist -> plan -> tasks -> analyze
```

Use it to generate and maintain specs, plans and task breakdowns. Do not let it replace verification, security review, simplification review or human sign-off.

Recommended greenfield flow:

```text
1. Create repo scaffold.
2. Run Spec Kit constitution.
3. Specify product/system intent.
4. Clarify ambiguity.
5. Create the technical plan.
6. Generate tasks.
7. Analyze consistency.
8. Convert important tasks into contracts and rubrics.
9. Implement one contract at a time.
```

Recommended existing-repo flow:

```text
1. Baseline current repo state.
2. Create repo map and OKF notes.
3. Use Spec Kit with existing conventions as constraints.
4. Generate spec, plan and tasks for a specific feature.
5. Analyze consistency.
6. Manually check that tasks respect existing patterns.
7. Convert accepted tasks into contracts and rubrics.
```

### 5.2 Spec template

```markdown
# Spec: <feature or system>

## Objective

## User or system outcome

## Commands

## Testing expectations

## Project structure

## Code style examples

## Git workflow

## Boundaries

### Always

### Ask first

### Never

## Success criteria

## Open questions

## Out of scope
```

### 5.3 Boundary tiers

Use three boundary tiers in specs, contracts and `AGENTS.md`:

| Tier | Meaning | Examples |
|---|---|---|
| Always | Safe defaults | Run focused checks, preserve style, update evidence |
| Ask first | Human approval required | Schema, auth, dependencies, CI, public APIs, production config |
| Never | Hard stop | Secrets, generated files, deleting tests, weakening CI, removing security gates |

### 5.4 Spec index for large specs

Large specs need an index so agents can load only relevant sections.

```markdown
# Spec index

- Auth: login, refresh, logout, session expiry. See section 3.
- Data model: users, organisations, roles. See section 4.
- Security: tenant boundaries, token storage, audit events. See section 7.
- Testing: conformance cases and browser flows. See section 10.
```

Use the index as always-available context. Load full sections only when needed.

## 6. Task contracts, rubrics and scratchpads

The task contract tells the worker what to build. The rubric tells the verifier when it is done. The scratchpad carries temporary working state. The verification note records evidence.

### 6.1 Task contract template

```markdown
# Task contract: <task name>

## Goal

What should change, in user or system terms.

## Context

Why this matters and which specs, plans or OKF files to read.

## Scope

Files, modules, behaviours or interfaces likely in scope.

## Out of scope

What must not be changed.

## Constraints

Interfaces, schema, dependencies, generated files, auth, performance or compatibility constraints.

## Acceptance checks

Exact tests, commands, screenshots, fixtures or manual checks.

## Implementation rules

Prefer existing patterns. Keep the diff small. Do not introduce abstractions unless needed.

## Review focus

Correctness, missed requirements, security, data integrity, scope creep and unnecessary abstraction.

## Deliverable

Small diff, updated tests, verification evidence and deferred notes.
```

### 6.2 Rubric template

```markdown
# Rubric: <task name>

The task is complete only if:

1. The implementation satisfies `docs/contracts/<task>.md`.
2. The specified tests pass.
3. Typecheck passes.
4. Lint passes.
5. Build passes where relevant.
6. No public interface changed unless approved.
7. No new runtime dependency was added unless approved.
8. No generated files were edited manually.
9. No tests were deleted, skipped, weakened or rewritten to match broken behaviour without explicit justification.
10. Security or data-integrity risks have been reviewed.
11. Known incomplete edge cases are listed in `docs/deferred.md`.
12. The worker produced evidence in `verification.md`.
13. The verifier lists any unverified criteria.
```

### 6.3 Scratchpad template

Use a per-task scratchpad for temporary state.

```text
docs/work/task-042/
  scratchpad.md
  verification.md
```

`scratchpad.md`:

```markdown
# Scratchpad: <task>

## Current goal

## Decisions made

## Assumptions

## Open questions

## Files inspected

## Commands run

## Next step
```

Scratchpads are not permanent memory. At the end, distil durable information into OKF, ADRs, skills, hooks or rules.

### 6.4 Verification note template

```markdown
# Verification: <task name>

## Intent

What this change is trying to achieve.

## Alternatives considered

- Option A:
- Option B:
- Why rejected:

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass/fail | |
| `make typecheck` | pass/fail | |
| `make lint` | pass/fail | |
| `make build` | pass/fail | |

## Manual verification

What was clicked, exercised, inspected or reproduced?

## Artefacts

Screenshots, videos, browser traces, logs, PR/branch links.

## Diff summary

Brief summary of changed files and why.

## Known unverified items

Anything not checked.

## Deferred work

Follow-up work added to `docs/deferred.md`.
```

## 7. Core workflows

### 7.1 Greenfield workflow

Greenfield danger: generating a large plausible app before the repo has stable seams, checks and a verifiable skeleton.

Goal: operability first, breadth later.

```text
1. Create agent-ready repo scaffold.
2. Write product brief, system brief and core invariants.
3. Add thin AGENTS.md, CLAUDE.md, Cursor rules and OKF index.
4. Add build/test/lint/typecheck/verify commands.
5. Run Claude Code Setup or equivalent repo diagnostic.
6. Build the walking skeleton.
7. Save a phase plan.
8. Convert each phase into task contracts.
9. Create rubrics for non-trivial tasks.
10. Implement one contract at a time.
11. Verify with evidence.
12. Run verifier, adversarial review and simplification review as appropriate.
13. Human review and merge.
14. Update OKF, ADRs, deferred.md, rules, skills, hooks and agentic-ops backlog.
```

Walking skeleton acceptance:

```text
one request path
one domain operation
one persistence path
one test path
one local run path
one CI path
one verification command
```

### 7.2 Existing repo workflow

Existing repo danger: confident agents making plausible but convention-breaking changes.

Goal: map first, change second.

```text
1. Baseline current checks and known failures.
2. Run read-only repo exploration.
3. Extract repo map, conventions and risk areas into OKF.
4. Keep AGENTS.md/CLAUDE.md short and link to OKF.
5. Run setup diagnostics.
6. Add only the highest-value hooks, MCPs, skills and subagents.
7. For each change, create contract + rubric + scratchpad when risk justifies it.
8. Implement narrowly.
9. Verify with evidence.
10. Run independent review.
11. Human review and merge.
12. Update durable knowledge only after verification.
```

### 7.3 Bug workflow

```text
1. Reproduce or characterise the failure.
2. Identify likely root cause.
3. Add a regression test or executable reproduction.
4. Implement the smallest fix.
5. Run affected test subset.
6. Run broader checks.
7. Reviewer checks for hidden side effects.
```

Debugging should not be static guesswork. Use:

```text
reproduce -> hypothesise -> instrument -> collect runtime evidence -> fix -> verify -> remove temporary instrumentation
```

### 7.4 Feature workflow

```text
1. Find existing analogous implementation.
2. Write or generate the task contract.
3. Extend existing patterns before inventing new abstractions.
4. Add tests or executable checks first where possible.
5. Implement narrowly.
6. Verify with evidence.
7. Review for convention drift and scope creep.
```

### 7.5 Refactor workflow

```text
1. Map current behaviour.
2. Identify seams and tests.
3. Add missing characterisation tests.
4. Refactor one seam at a time.
5. Preserve public interfaces unless explicitly approved.
6. Run simplification review.
7. Human review test changes first.
```

### 7.6 Large migration workflow

Large migrations work only when partitioned mechanically.

Partition by:

```text
package
callsite
route
failing test
module
database migration unit
generated checklist
```

Use worktrees or dynamic workflows for independent partitions. Do not let multiple agents edit the same seam.

## 8. Review system

Review is now the main bottleneck. The goal is not to read every generated line with equal depth. The goal is to allocate human attention where being wrong is costly.

### 8.1 Risk-tiered review

| Tier | Examples | Required review |
|---|---|---|
| 0 | Docs typo, harmless copy | Focused check, optional AI review |
| 1 | Small isolated code change | Tests, one AI review or human skim |
| 2 | Feature slice, integration, moderate refactor | Contract verifier, tests, AI review, human review |
| 3 | Auth, payments, PII, tenant boundaries, schema, secrets, untrusted input | Full tests, security review, two heterogeneous AI reviewers, human deep review |
| 4 | Migration, production config, deletion, public API change | Human-approved plan, ADR, full review stack, rollback plan, senior sign-off |

### 8.2 Review stack

For meaningful work:

```text
worker self-verification
-> contract verifier
-> adversarial review
-> security review if relevant
-> simplification review
-> human review
```

Use all layers only when justified by risk.

### 8.3 Worker self-verification

The worker must run checks and produce evidence. A claim is not enough.

### 8.4 Contract verifier

The verifier grades against the rubric.

It should answer:

```text
Did the implementation satisfy every rubric item?
What evidence proves that?
Which items are unverified?
Which failures are blocking?
Did the worker change anything outside scope?
Were tests weakened or rewritten incorrectly?
```

### 8.5 Adversarial review

Use Codex, another model family, or a dedicated reviewer to challenge correctness. Focus on:

```text
missed requirements
correctness bugs
security and data-integrity risks
hidden scope creep
unnecessary complexity
simpler alternatives
```

### 8.6 Security review

Required for:

```text
auth
permissions
tenant boundaries
secrets
payments
data deletion
PII
network calls
dependency changes
MCP changes
deployment changes
```

### 8.7 Simplification review

Run after correctness is established. Use Ponytail, Claude `/simplify`, or a code simplification skill to ask what can be deleted, simplified or replaced with native functionality.

Do not simplify away security, data integrity, accessibility or trust-boundary checks.

### 8.8 Human review checklist

Human review should focus on what machines are weakest at:

```text
is this the right change?
semantic correctness
architecture fit
trust boundaries
hidden migrations
product judgement
scope control
future maintenance burden
whether the evidence is enough
```

Review test changes first. Block removed, skipped, weakened or rewritten tests unless explicitly justified.

### 8.9 PR contract

Every meaningful PR should include:

```markdown
## What / why

## Proof it works

- Tests:
- Typecheck:
- Lint:
- Build:
- Manual verification:
- Screenshots/logs/traces:

## Risk tier

Tier 0 / 1 / 2 / 3 / 4

## AI role

What did the agent draft, edit, test or review?

## Review focus

Where should the human reviewer spend attention?

## Known gaps

What remains unverified, deferred or intentionally out of scope?
```

## 9. Skills

A skill is not a long essay. A useful skill is a workflow with checkpoints and exit criteria. Skills encode repeatable senior-engineer behaviour that agents otherwise skip.

### 9.1 Skill quality checklist

A skill is acceptable only if it has:

```text
narrow trigger description
concrete workflow
checkpoints
evidence requirements
exit criteria
anti-rationalisation table
scope boundaries
escalation or stop conditions
references loaded only when needed
```

### 9.2 Anti-rationalisation table

Agents can rationalise skipping process. Pre-write the rebuttal.

```markdown
## Anti-rationalisation table

| Excuse | Response |
|---|---|
| This is too small for a contract | Write a five-line contract. Zero lines is not acceptable. |
| I will add tests later | Later is not a plan. Add the failing test or explain why no test is possible. |
| Existing tests pass | Passing tests are evidence, not proof. Check task-specific behaviour. |
| I found adjacent cleanup | Do not touch it unless required. Add it to deferred work. |
| The implementation seems obvious | Surface assumptions before editing. |
```

### 9.3 Custom skills to create

Create skills only after a workflow repeats or fails.

High-value repo-specific skills:

```text
tdd-verify
migration
debugging
release
pr-review
context-maintenance
browser-verification
security-review
```

### 9.4 Portable skill source

Keep a tool-agnostic source version, then package for Claude and Cursor as needed.

```text
docs/agentic-ops/skills-source/
  tdd-verify.md
  pr-review.md
  debugging.md
  migration.md

.claude/skills/
  tdd-verify/SKILL.md

.cursor/
  rules/ or skills/
```

## 10. Hooks and enforcement

Hooks are the enforcement layer. They turn guidance into system behaviour.

Principle:

```text
Hooks should be silent on success and verbose on failure.
```

Examples:

| Hook type | Use |
|---|---|
| PreToolUse | Block destructive commands, protected path writes, unsafe MCP write tools |
| PostToolUse | Run targeted format/lint/test checks after edits |
| UserPromptSubmit | Inject guardrails or require a contract for risky prompts |
| Notification | Alert when long-running work needs input |
| Stop | Require verification summary or block done without evidence |
| SessionEnd | Save state; do not auto-push by default |
| PreCompact/PostCompact | Preserve handoff state around context compression |
| WorktreeCreate/Remove | Set up or clean isolated environments |

Do not put everything into hooks. Use hooks for deterministic rules, not fuzzy preferences.

## 11. Tools and adapters

### 11.1 Claude Code

Best for:

```text
terminal-native execution
hooks
subagents
skills
plugins
goal loops
batch/dynamic workflows
headless automation
security and code review commands
```

Useful command map:

| Command | Use |
|---|---|
| `/init` | Bootstrap, then prune generated context aggressively |
| `/memory` | Inspect/refine memory |
| `/mcp` | Manage MCP servers |
| `/agents` | Manage subagents |
| `/permissions` | Manage tool allow/ask/deny rules |
| `/plugin` | Install bundles of skills/hooks/agents |
| `/plan` | Read-only planning for non-trivial work |
| `/goal` | Measurable self-correction loop |
| `/run` | Launch and exercise the app |
| `/verify` | Confirm runtime behaviour where relevant |
| `/diff` | Inspect changed files |
| `/code-review` | Review diff for correctness and cleanups |
| `/security-review` | Review pending changes for vulnerabilities |
| `/simplify` | Cleanup-only review after correctness |
| `/fork` | Background side investigation with inherited context |
| `/branch` | Branch conversation path, not git branch |
| `/batch` | Partition broad work into isolated worktrees |
| `/loop` | Re-run prompt on a cadence in-session |
| `/schedule` | Cloud routine for recurring tasks |
| `/autofix-pr` | Watch current PR and push narrow fixes where appropriate |
| `/context` | Inspect context usage |
| `/compact` | Compress current session |
| `/clear` | Fresh session for a new task |

Use `/goal` only with measurable conditions:

```text
/goal All criteria in docs/rubrics/task-042-rubric.md are satisfied, the worker has run and pasted results for make test, make typecheck and make lint, no public interfaces changed, and the final response lists unverified criteria. Stop after 12 turns if not complete.
```

### 11.2 Cursor

Best for:

```text
IDE-native planning and editing
visual review
code navigation
frontend/browser-heavy workflows
local Agent Review
Bugbot / PR review
cloud handoff
team-friendly editor workflow
```

Recommended usage:

```text
Use Plan Mode for non-trivial work.
Save durable plans into docs/plans/ or docs/contracts/.
Use .cursor/rules/ for scoped project rules.
Use AGENTS.md as shared protocol.
Use Agent Review as first-pass review, not final approval.
Use cloud agents only for bounded tasks with good environment setup.
```

### 11.3 GitHub Spec Kit

Use Spec Kit to structure:

```text
constitution
specify
clarify
checklist
plan
tasks
analyze
```

Do not treat `implement` as autopilot for serious work. Use it only when checks, task scope and review are strong enough.

### 11.4 Codex or second-model review

Use for independent adversarial review. Good for:

```text
non-trivial diffs
security-sensitive code
data integrity
refactors
migrations
suspicious implementations
final review before merge
```

For high-risk work, prefer heterogeneous review: two reviewer types with different strengths rather than multiple copies of the same reviewer.

### 11.5 Ponytail or simplification tools

Use after correctness. Ask:

```text
Does this need to exist?
Can the standard library, platform or existing dependency solve it?
Can the diff be smaller?
Can abstractions be removed?
```

## 12. MCP, permissions and containment

MCP expands what the agent can touch. Treat it as a trusted execution surface.

Baseline:

```text
start with read-only where possible
use narrow servers
allow only needed tools
version-control project MCP config
avoid broad personal/company data access
do not expose production secrets
review MCP server additions like dependency additions
```

Containment is stronger than approval-only safety.

Use:

```text
isolated worktrees or VMs
no production credentials in agent environments
network deny by default where possible
scoped MCP permissions
read-only modes for research
hooks for destructive commands
manual approval for schema, auth, dependency and production changes
```

Approval gates:

```text
schema changes
auth/permission changes
dependency additions
secret handling
CI/CD changes
production config
MCP server additions
data deletion or migration
public interface changes
```

## 13. Agent environment readiness

The development environment is part of the product. If an agent cannot run the system, it will compensate by guessing.

A repo is agent-ready when a fresh environment can:

```text
install dependencies
run tests
run typecheck
run lint
run build
seed data
start the app
run verification commands
produce useful logs
exercise a browser path where relevant
```

Create `docs/agentic-ops/environment.md`:

```markdown
# Agent environment

## Setup commands

## Required services

## Seed data

## Test accounts

## Local env vars

## Secret policy

## Network policy

## Browser verification

## CI parity notes

## Known environment quirks
```

## 14. Worktrees, subagents and parallelism

Default to one main implementation agent. Add sidecars for research, verification, security, adversarial review and simplification.

Parallel implementation is useful only when work partitions cleanly by:

```text
module
route
callsite
package
migration unit
failing test
file set
```

Rules:

```text
Use worktrees for parallel code changes.
Use subagents for noisy research and review.
Use /fork or conversation branches for reasoning alternatives.
Do not let parallelism outrun human review bandwidth.
```

## 15. Loop engineering

A loop is a recurring system that discovers, assigns, verifies, records and repeats work. It sits above individual tasks and harnesses.

Loop anatomy:

```text
automation or trigger
work isolation
skills
connectors/MCP
subagents
state file
verifier
human approval gate
budget
failure behaviour
```

Do not automate a workflow until the manual version is boring.

### 15.1 Loop design template

```markdown
# Loop design: <loop name>

## Purpose

What recurring problem this loop handles.

## Trigger

Schedule, event, manual command, CI failure, issue label, PR event or explicit goal.

## Inputs

Repos, branches, issue tracker queries, CI logs, docs, metrics, tickets or state files.

## Skills used

Which skills the loop invokes and why.

## Connectors / MCP

Which external tools it can access. Prefer read-only unless write access is essential.

## Work isolation

Clean branch, worktree, cloud environment or sandbox.

## State file

Where the loop records what it found, tried, completed, skipped and deferred.

## Verifier

Which independent verifier checks the result, and against what rubric.

## Output

PR, issue comment, triage report, branch, markdown summary, Slack message or backlog item.

## Human approval gates

What the loop must never merge, send, delete, deploy or modify without approval.

## Budget

Maximum runtime, turn count, token budget, number of worktrees and review limit.

## Failure mode

What happens if it cannot complete safely.
```

### 15.2 Safe loop types

| Loop type | Use | Risk |
|---|---|---|
| Reporting loop | Summarise CI, open issues, stale PRs, dependency warnings | Low |
| Triage loop | Classify failures, group issues, propose task contracts | Low-medium |
| Verification loop | Re-run checks, confirm fixes, produce evidence | Medium |
| Draft-fix loop | Open worktree, attempt bounded fix, produce PR | Medium-high |
| Migration loop | Partition broad mechanical work across worktrees | High |

Start with reporting and triage. Do not start with migration loops.

### 15.3 Loop state

Use structured loop state, not chat memory.

```text
docs/agentic-ops/loops/
  ci-triage/
    loop.md
    state.md
    inbox.md
    runs/
      2026-06-18.md
```

State should track:

```text
what was checked
what was found
what was attempted
what passed
what failed
what needs human review
what should not be retried
```

### 15.4 Triage inbox

Loops should not silently fail or pretend to finish. Anything uncertain goes to a triage inbox.

```markdown
## 2026-06-18: CI failure in checkout tests

- Source: nightly CI triage loop
- Status: needs human review
- Evidence: link/log path
- Agent attempted: reproduced locally, narrowed to payment fixture setup
- Blocker: unclear whether fixture or product behaviour is wrong
- Suggested next action: human decides expected behaviour, then create task contract
```

### 15.5 Loop budgets

Every loop needs a budget:

```text
max runs per day
max worktrees open
max turns per run
max retries per finding
max PRs opened per day
max review queue size
stop if CI is red for unrelated reasons
stop if the same failure repeats twice
```

## 16. Harness engineering

Harness engineering is the discipline of improving the scaffolding around the model.

Add `docs/agentic-ops/harness.md`:

```markdown
# Agent harness inventory

## Purpose

What this harness is optimised for.

## Model assumptions

What we assume current models can and cannot do unaided.

## Context layer

AGENTS.md, CLAUDE.md, Cursor rules, OKF files, task contracts, rubrics.

## Tool layer

Shell commands, MCP servers, browser tools, database tools, docs lookup, observability.

## Execution layer

Local checkout, worktrees, sandbox, VM, cloud agents, CI.

## Enforcement layer

Hooks, permissions, approval gates, protected paths, destructive command blocks.

## Verification layer

Tests, typecheck, lint, build, browser checks, verifier subagents, adversarial review, security review, simplification review.

## Observability

Logs, traces, cost, latency, failure log, review findings.

## Known harness gaps

What this harness still fails to prevent.
```

### 16.1 Harness ratchet

Every repeated or serious failure should produce one harness change. Every harness change should be earned.

Failure log template:

```markdown
# Agentic failure log

## <date> - <task>

### What failed

### Why it failed

### Harness root cause

What did the harness fail to provide or enforce?

### How it was fixed

### What artefact changed

- [ ] Spec
- [ ] Contract template
- [ ] Rubric
- [ ] Skill
- [ ] Hook
- [ ] OKF
- [ ] ADR
- [ ] Test
- [ ] Tooling
- [ ] Permission
- [ ] No change, accepted as one-off

### Removal condition

When should this new rule/check be deleted?
```

### 16.2 Harness expiry review

Review periodically:

```text
Which rules are still needed?
Which hooks are blocking useful work?
Which skills are no longer pulling their weight?
Which model weaknesses have improved?
Which new model behaviours need new guardrails?
Which MCP/tool descriptions are too broad?
```

## 17. Downgrade paths

If the agentic loop fails repeatedly, downgrade deliberately.

Rule of thumb:

```text
If the same task fails after 2 serious agent attempts or 3 rubric refinements, downgrade.
```

Downgrade path:

```text
agentic loop
-> pair-programming style with the agent
-> manual coding for the hard part
-> reverse-spec the manual fix
-> update rules/skills/OKF/rubric/tests/hooks if needed
```

Reverse-spec questions:

```text
What did I know that the agent did not?
What assumption did the agent keep getting wrong?
What test, rule, invariant or example would have prevented this?
Should this become an OKF note, ADR, skill update, hook or task-template change?
```

Manual rescue should improve the machine when there is a durable lesson.

## 18. Maintenance cadence and metrics

### After each meaningful task

```text
update verification.md
record deferred work
update scratchpad status
distil durable learning if any
update task status
```

### After each merge

```text
delete or archive temporary scratchpads
update OKF only with verified learning
write ADR if design decision changed
update skills/hooks/rules if a failure repeated
```

### Weekly or after a milestone

```text
review agentic-ops backlog
prune stale AGENTS.md or CLAUDE.md content
promote repeated procedures into skills
tighten verifier rubrics
review failed agent attempts
improve environment setup
review MCP permissions
```

### Periodically

```text
run repo setup diagnostics again
audit rules and hooks
check whether skills are still useful
remove unused automations
refresh OKF index
review security containment
```

### Metrics

Do not optimise for tokens or files changed alone.

Track:

```text
time from task start to green checks
rework rate from wrong requirements
review findings per task
average diff size at merge
number of unverified claims per task
number of context/session resets
agent failures by category
manual rescue frequency
agentic-ops backlog age
```

## 19. Quick decision rules

### Is this task small?

```text
direct edit
-> focused check
-> maybe quick review
-> commit
```

### Is this task non-trivial?

```text
plan
-> contract or task scope
-> acceptance checks
-> implement
-> verify
-> review
```

### Is this task risky?

```text
read-only exploration
-> human-approved plan
-> contract + rubric
-> tests/checks first
-> implementation
-> verifier
-> adversarial review
-> security review
-> simplification review
-> human sign-off
-> ADR/OKF update
```

### Is this task failing repeatedly?

```text
downgrade
-> solve manually or pair-style
-> reverse-spec
-> improve the harness if there is a durable lesson
```

### Is this task broad and mechanical?

```text
partition
-> worktrees or dynamic workflow
-> independent verification per partition
-> integrate carefully
```

## 20. Installation and adoption guidance

### Recommended stack

Install or trial deliberately:

```text
GitHub Spec Kit for spec/plan/tasks
Claude Code Setup for repo diagnostics
Claude Code as terminal-native harness
Cursor as IDE-native cockpit
Codex or equivalent for adversarial review
Ponytail or /simplify for anti-bloat review
Addy Osmani-style skills for lifecycle discipline
fable-mode only for long/staged tasks where useful
```

Do not make the workflow depend on everyone installing every tool on day one.

### Rollout sequence

For a team:

```text
1. Start with the playbook: small tasks, evidence, risk-tiered review.
2. Add PR contract and minimal AGENTS.md.
3. Add standard commands and CI parity.
4. Add Spec Kit for feature planning.
5. Add AI first-pass review.
6. Add skills for repeated workflows.
7. Add hooks for repeated failures.
8. Add loops only after manual workflows are stable.
```

## 21. Final reference workflow

### Greenfield

```text
1. Create agent-ready repo scaffold.
2. Write product brief, system brief and core invariants.
3. Add thin AGENTS.md, CLAUDE.md, Cursor rules and OKF knowledge index.
4. Add build/test/lint/typecheck/verify commands.
5. Use Spec Kit for constitution/spec/plan/tasks where useful.
6. Build the walking skeleton.
7. Save a phase plan.
8. Convert each phase into task contracts.
9. Create rubrics for non-trivial tasks.
10. Implement one contract at a time.
11. Verify with evidence.
12. Run verifier, adversarial review and simplification review as appropriate.
13. Human review and merge.
14. Update OKF, ADRs, deferred.md, rules, skills, hooks and agentic-ops backlog.
```

### In-progress repo

```text
1. Baseline current checks and known failures.
2. Run read-only repo exploration.
3. Extract repo map, conventions and risk areas into OKF.
4. Keep AGENTS.md/CLAUDE.md short and link to OKF.
5. Run repo setup diagnostics.
6. Add only the highest-value hooks, MCPs, skills and subagents.
7. For each change, create contract + rubric + scratchpad when risk justifies it.
8. Implement narrowly.
9. Verify with evidence.
10. Run independent review.
11. Human review and merge.
12. Update durable knowledge only after verification.
```

## 22. The mental model

You are operating a software delivery system.

The system has:

```text
inputs: specs, contracts, context and tools
processors: agents, skills, workflows and hooks
quality gates: tests, rubrics, verifiers and reviews
memory: OKF, ADRs, rules and skills
safety boundaries: containment, permissions and approval gates
feedback: failure logs, metrics and agentic-ops backlog
```

Good agentic engineering means making this system small, legible, testable and worth maintaining.

```text
Build the product.
Build the machine that builds the product.
Then, only for stable recurring work, build loops that operate the machine.
Keep all three under human judgement.
```

## Sources and reference material

This manual synthesises current practice and documentation from:

- Anthropic / Claude Code official docs: https://code.claude.com/docs/
- Claude Code feature overview: https://code.claude.com/docs/en/features-overview
- Cursor official docs: https://cursor.com/docs
- Cursor rules docs: https://cursor.com/docs/rules
- GitHub Spec Kit docs: https://github.github.com/spec-kit/
- Addy Osmani writings on agentic engineering, agent skills, harness engineering, loop engineering and agentic code review.
- Practitioner material on risk-tiered review, proof-oriented PRs, context management and multi-agent workflows.

This document is a working manual, not a legal or security policy. For production systems, align it with your organisation's security, data protection, accessibility and software assurance requirements.