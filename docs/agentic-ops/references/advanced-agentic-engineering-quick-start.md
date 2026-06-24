# Advanced Agentic Engineering Quick Start Guide

*Install the tools, prepare a repo, and run the first full workflow without over-engineering the rollout*

**Draft v0.1 | June 2026**

## Who this is for

This guide is for engineers who want to run the **advanced agentic engineering workflow** in a real repo. It is a practical companion to the Advanced Agentic Engineering Manual, not a replacement for it.

Use this guide when you want to:

- install the recommended tooling;
- create an agent-ready greenfield repo;
- add the workflow to an existing repo;
- make Claude Code and Cursor coexist without config drift;
- run the first full task loop with specs, task contracts, verification evidence and review.

The goal is to get to a useful v0.1 quickly. Do not install every advanced pattern on day one. Start with the minimum reliable harness, then add skills, hooks, subagents, loops and automations only when they solve observed problems.

## 0. The shape of the workflow

The advanced workflow is:

```text
thin context
-> spec
-> task contract
-> rubric or acceptance checks
-> scratchpad if useful
-> skill-driven implementation
-> verification evidence
-> independent review
-> simplification/security review where relevant
-> human sign-off
-> durable memory update only when justified
```

For quick start purposes, reduce that to:

```text
prepare repo
-> write spec
-> create first task contract
-> implement one reviewable slice
-> capture evidence
-> review by risk
-> merge or revise
```

## 1. Install the core tools

### 1.1 Required local tools

Install these first:

```bash
git --version
python3 --version
node --version
make --version
```

Recommended baseline:

- Git
- Python 3.11+
- Node.js / npm if your stack or plugins need it
- `uv` for Python tool installation
- a task runner: `make`, `just`, `task`, `npm scripts`, or equivalent
- your normal package manager and language toolchain

The workflow assumes the repo can be set up and verified from a clean checkout by running documented commands.

### 1.2 Install Claude Code

Claude Code is the recommended terminal-native agent for the full advanced workflow.

macOS, Linux or WSL:

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude --version
claude doctor
claude
```

Windows PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
claude --version
claude doctor
claude
```

Inside Claude Code, useful first commands are:

```text
/help
/login
/permissions
/mcp
/agents
/plugin
/plan
```

Use `/init` only as a temporary bootstrap. Do not blindly commit the generated `CLAUDE.md` or `AGENTS.md`; delete discoverable codebase-tour content and keep only landmines, commands, approval gates and pointers.

Claude Code steering rule of thumb:

| Need | Prefer |
|---|---|
| Always-relevant repo facts | Root `CLAUDE.md`, kept short and owned |
| Directory-specific conventions | Subdirectory `CLAUDE.md` or path-scoped rules |
| Cross-cutting path/file constraints | `.claude/rules/` with `paths:` |
| Repeatable procedures | `.claude/skills/` |
| Noisy or isolated side tasks | `.claude/agents/` subagents |
| Absolute prohibitions | Permissions, managed settings, hooks or CI |
| Major response-mode changes | Built-in output styles first; custom styles rarely |

Avoid custom output styles for normal engineering workflow. A custom output style can change Claude Code's default software-engineering behaviour, so prefer skills, rules, hooks or appended prompts for most workflow changes.

### 1.3 Install Cursor CLI if you use Cursor

Cursor is optional but useful for people who prefer IDE-native planning, visual review, agent worktrees, or Cursor’s models.

macOS, Linux or WSL:

```bash
curl https://cursor.com/install -fsS | bash
agent --version
agent login
agent
```

Windows PowerShell:

```powershell
irm 'https://cursor.com/install?win32=true' | iex
agent --version
agent login
agent
```

Useful Cursor CLI commands:

```bash
agent --plan "Plan the next task without editing files"
agent --worktree "Investigate this issue in an isolated worktree"
agent -p "Review the current diff for blocking correctness issues" --output-format json
agent mcp list
agent update
```

### 1.4 Optional: install GitHub Spec Kit

Use Spec Kit when you want standardised spec artefacts: constitution, specify, plan, tasks and consistency analysis. It is useful for greenfield work, larger features and cross-agent handoff, but it is not mandatory if Claude Code, Cursor or repo-specific skills already produce accepted specs, contracts, checks and verification notes.

Install from the official GitHub repository, not from similarly named PyPI packages.

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
specify version
specify self check
```

Replace `vX.Y.Z` with a release tag from the Spec Kit repository.

For a one-time trial:

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init my-project --integration claude
```

Common integrations:

```bash
specify init my-project --integration claude
specify init my-project --integration copilot
specify init my-project --integration gemini
```

After initialization, the important workflow commands are:

```text
/speckit.constitution
/speckit.specify
/speckit.clarify
/speckit.plan
/speckit.tasks
/speckit.analyze
/speckit.implement
```

Use `/speckit.implement` cautiously. For serious work, prefer converting generated tasks into task contracts and running the review workflow below.

### 1.5 Recommended Claude Code plugins

Install these when you are ready to use the full advanced workflow.

Codex plugin for independent/adversarial review:

```text
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

Addy Osmani agent-skills for senior-engineer lifecycle discipline:

```text
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
/reload-plugins
```

Ponytail for simplification / anti-bloat review:

```text
/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail
/reload-plugins
```

Start with the plugin defaults. Do not install every community plugin. Treat plugins and skills as trusted execution/context surfaces.

## 2. Create a new agent-ready repo

### 2.1 Create the repo scaffold

```bash
mkdir my-project
cd my-project
git init
mkdir -p docs/{specs,plans,tasks,adr,knowledge,agentic-ops}
mkdir -p .claude/{skills,agents,hooks,rules}
mkdir -p .cursor/{rules,plans}
touch AGENTS.md CLAUDE.md docs/deferred.md
```

`docs/specs/` (intent) and `docs/knowledge/` (verified knowledge) are both **OKF bundles** — markdown concept files with a `type:`, a status marker and cross-links. Treat specs as *living intent, not golden*: if building shows a spec is wrong, flow the change back (propose → human decision → update the spec + an ADR if consequential → log) rather than coding around it.

Add a task runner immediately. Example `Makefile`:

```makefile
setup:
	@echo "Install dependencies here"

test:
	@echo "Run tests here"

typecheck:
	@echo "Run typecheck here"

lint:
	@echo "Run lint here"

build:
	@echo "Run build here"

verify: test typecheck lint build
```

Replace the placeholder commands as soon as the stack is chosen. The first goal is not feature breadth; it is that an agent can run, test and verify the repo from a clean checkout.

### 2.1.1 Ignore private agent working state

For open-source repositories, commit only public-safe durable artefacts. Add private working state and raw evidence to `.gitignore`:

```gitignore
.agent/
.agent-private/
docs/work/
*.har
*.trace
*.log
.env
.env.*
```

Keep exploit notes, private threat analysis, credentials, incident material, raw logs, HAR files, screenshots and recordings out of public history.

### 2.2 Add the shared agent protocol

Put shared, tool-neutral instructions in `AGENTS.md`:

```markdown
# Agent protocol

- Use the commands in the `Makefile`.
- For non-trivial work, plan before editing.
- Use `docs/specs/` for product and system intent.
- Use `docs/tasks/<task-id>/` for per-task artefacts: `contract.md` (scope), `rubric.md`
  (completion criteria, when risk is medium or high), `verification.md` (public-safe evidence, or in the PR).
  Templates live in `docs/tasks/_templates/`.
- Do not change schema, auth, dependencies, CI, production config or public interfaces without approval.
- Never edit generated files, secrets or private agent working state.
- Touch only what the task requires.
```

Keep `AGENTS.md` short. Do not include a directory tour the agent can discover by reading the repo.

### 2.3 Add the Claude adapter

Put Claude-specific guidance in `CLAUDE.md`. Keep the root file short, owned and reviewed like code:

```markdown
# Claude Code adapter

Read `AGENTS.md` first.

Use:
- `/plan` for non-trivial changes.
- `/goal` only when completion is measurable.
- `/code-review` before meaningful commits.
- `/security-review` for auth, data, secrets, dependency or MCP changes.
- Skills for repeatable workflows.
- Hooks for rules that must be enforced.

Do not duplicate long shared instructions here. Point to the shared docs instead.
```

### 2.3.1 Add path-scoped Claude rules when needed

Create `.claude/rules/` files for specific constraints that should load only for matching files:

```markdown
---
paths:
  - "src/api/**"
  - "**/*.handler.ts"
---

All API handlers must validate input before processing.
```

Do not put every rule in root `CLAUDE.md`. Unscoped rules and root instructions are always-loaded context.

### 2.4 Add the Cursor adapter

Create `.cursor/rules/core.mdc`:

```markdown
---
description: Core Cursor agent rules
alwaysApply: true
---

- Follow `AGENTS.md`.
- Use `.cursor/plans/` for Cursor-native working plans.
- Promote accepted plans that matter into `docs/plans/` or a task contract under `docs/tasks/<task-id>/`.
- Keep changes scoped to the task.
- Produce verification evidence before review.
```

Add path-scoped Cursor rules later, only when a directory has genuinely different conventions.

### 2.5 Initialise Spec Kit

From the repo root:

```bash
specify init . --integration claude
```

If the repo also uses Cursor, keep Spec Kit’s generated artefacts in the repo but avoid duplicating the same workflow instructions into both Claude and Cursor files. The shared docs remain canonical.

Run the front-end workflow:

```text
/speckit.constitution
/speckit.specify
/speckit.clarify
/speckit.plan
/speckit.tasks
/speckit.analyze
```

Then promote important tasks into `docs/tasks/<task-id>/` (a `contract.md`, plus `rubric.md` for medium/high-risk work).

## 3. Add the workflow to an existing repo

### 3.1 Start read-only

Do not begin by installing lots of plugins or generating giant context files. First establish current truth.

```bash
git status
make test
make typecheck
make lint
make build
```

If the repo does not have those commands, create a task runner wrapper around the real commands.

### 3.2 Create the minimal files

```bash
mkdir -p docs/{specs,plans,tasks,adr,knowledge,agentic-ops}
mkdir -p .claude/{skills,agents,hooks,rules}
mkdir -p .cursor/{rules,plans}
touch AGENTS.md CLAUDE.md docs/deferred.md
```

Populate only:

- canonical commands;
- non-obvious tool gotchas;
- approval gates;
- protected paths;
- generated files;
- known landmines.

Do not add a codebase overview unless the repo has no documentation and the overview is genuinely useful as a temporary bridge.

Likewise, leave `docs/agentic-ops/failure-log.md` empty until the first real failure, and don't create a `metrics.md` until there's enough task volume to measure. Earn the artefact; an empty-by-default file is honest, not a gap.

### 3.3 Ask an agent for a read-only repo map

Prompt Claude Code or Cursor:

```text
Read-only task. Do not edit files.

Map this repository for agentic development:
- setup/build/test/typecheck/lint commands
- main subsystems and boundaries
- generated files and protected paths
- current testing patterns
- risky areas
- public interfaces
- missing local verification commands

Write a concise proposal for docs/knowledge/repo-map.md and docs/agentic-ops/readiness.md.
```

Review the output before committing it.

### 3.4 Add one safety gate before advanced work

Create `docs/agentic-ops/readiness.md`:

```markdown
# Agentic readiness

- [ ] Clean checkout setup is documented.
- [ ] Tests can run locally.
- [ ] Typecheck/lint/build commands are documented.
- [ ] Known failing tests are documented.
- [ ] Generated files are identified.
- [ ] Schema/auth/dependency/CI approval gates are documented.
- [ ] Secrets and production config are protected.
- [ ] PR evidence expectations are clear.
- [ ] Runtime/product egress (the running product calling external services with project data) is a recognised approval gate.
```

Agent/dev-time network use — installing packages, fetching docs, review MCP servers — is expected and not gated; only the product's own outbound reach is.

Only after this should you add skills, hooks, subagents or loops.

## 4. Run the first full task

### 4.1 Choose a reviewable vertical slice

Good first tasks:

- add one regression test and a small fix;
- build one endpoint or one UI path;
- add one integration check;
- create one docs update with verification;
- refactor one small seam behind existing tests.

Bad first tasks:

- redesign architecture;
- change auth;
- replace the database layer;
- migrate many files;
- ask the agent to “make it production ready”.

### 4.2 Write a task contract

Create `docs/tasks/001-example-slice/contract.md`:

```markdown
# Task contract: 001-example-slice

## Goal

What should change in user or system terms.

## Context

Specs, plans, OKF files or examples to read.

## Scope

Files, modules or behaviours likely in scope.

## Out of scope

What must not be changed.

## Constraints

Interfaces, schema, dependencies, generated files, auth, performance or compatibility constraints.

## Acceptance checks

- `make test`
- `make typecheck`
- `make lint`
- `make build`
- Any manual/browser/API checks required.

## Review focus

Correctness, missed requirements, security, data integrity, scope creep and unnecessary abstraction.
```

For low-risk tasks, this can be five lines. For high-risk tasks, make it explicit.

If the ask itself is underspecified — unclear why, for whom, or what "done" means — clarify with the human *before* writing the contract (an interview-style skill such as `agent-skills:interview-me` helps). Do not write a contract on guesses.

### 4.3 Optional: write a rubric

Create `docs/tasks/001-example-slice/rubric.md` for medium/high-risk work:

```markdown
# Rubric: 001-example-slice

The task is complete only if:

1. The implementation satisfies `docs/tasks/001-example-slice/contract.md`.
2. The specified checks pass.
3. No public interface changed without approval.
4. No new dependency was added without approval.
5. No generated files were edited manually.
6. No tests were deleted, skipped or weakened without justification.
7. Verification evidence was produced.
8. Known gaps are listed.
```

### 4.4 Run implementation

Claude Code:

```text
/plan Implement docs/tasks/001-example-slice/contract.md. Do not edit yet. Identify files, tests and risks.
```

After you approve the plan:

```text
Implement docs/tasks/001-example-slice/contract.md. Keep the remit reviewable. Run the acceptance checks and write public-safe verification evidence.
```

For measurable tasks:

```text
/goal All criteria in docs/tasks/001-example-slice/rubric.md are satisfied. Run and report make test, make typecheck, make lint and make build. Stop after 8 turns if incomplete and list blockers.
```

Cursor CLI:

```bash
agent --plan "Plan docs/tasks/001-example-slice/contract.md without editing files"
agent "Implement docs/tasks/001-example-slice/contract.md. Keep the remit reviewable and produce public-safe verification evidence."
```

For an isolated experiment:

```bash
agent --worktree "Implement docs/tasks/001-example-slice/contract.md in an isolated worktree and report evidence"
```

### 4.5 Capture verification evidence

Create `docs/tasks/001-example-slice/verification.md`:

```markdown
# Verification: 001-example-slice

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass/fail | |
| `make typecheck` | pass/fail | |
| `make lint` | pass/fail | |
| `make build` | pass/fail | |

## Manual checks

## Diff summary

## Intent and assumptions

## Known unverified items

## Public safety

Are logs, screenshots, traces, prompts and links safe to publish?

## Deferred work
```

Do not accept “done” without evidence.

### 4.6 Review by risk

| Risk tier | Examples | Required review |
|---|---|---|
| 0 | typo, comment, small docs | focused check |
| 1 | small isolated code change | tests + AI review or human skim |
| 2 | feature slice, integration, refactor | contract verifier + tests + human review |
| 3 | auth, schema, data integrity, secrets, untrusted input | full checks + security review + adversarial review + human deep review |
| 4 | migration, production config, deletion, public API change | human-approved plan + ADR + rollback plan + full review stack |

Claude Code review commands:

```text
/code-review high
/security-review
/simplify
```

Codex plugin review:

```text
/codex:review --base main
/codex:adversarial-review --base main Focus on correctness, missed requirements, security boundaries, data loss, scope creep and simpler alternatives.
```

Use simplification only after correctness is established.

### 4.7 Fill in the PR contract

Add this to the PR description:

```markdown
## What / why

## Proof it works

- Tests:
- Typecheck:
- Lint:
- Build:
- Manual verification:

## Risk tier

## AI role

## Review focus

## Known gaps
```

No PR should ask reviewers to reconstruct intent from the diff alone.

The agent can draft this whole section from the task artefacts — you review the draft, not transcribe it. Drafting the PR is not merging it: opening, review and merge stay human.

### 4.8 Commit as a checkpoint

```bash
git status
git diff --stat
git add <files>
git commit -m "001-example-slice: <short description>"
```

Use one small commit per task contract. Avoid “AI changes” mega-commits.

State lives in files, not chat history — so a long task can split across fresh conversations. Between phases, start a fresh conversation and re-ground from the committed artefacts (the commit is the handoff); `/compact` only mid-phase, when valuable state isn't in a file yet. Review especially wants a fresh conversation, so the reviewer isn't the chat that wrote the code.

## 5. Add skills, hooks and subagents only after v0.1 works

### 5.1 Skill vs subagent rule

Use a skill when the procedure should happen in the main thread and the human may want to steer each step. Use a subagent when the task is isolated, noisy, parallel or should return only a summary, such as dependency audit, log analysis, deep search or security sweep.

### 5.2 First skills to add

Start with:

- TDD / verification workflow
- PR review workflow
- debugging workflow
- migration workflow
- context-maintenance workflow

A good skill is a workflow, not an essay. It should include:

- trigger description;
- concrete steps;
- checkpoints;
- evidence requirements;
- exit criteria;
- anti-rationalisation table;
- stop/escalation conditions.

Some teams consolidate the whole per-slice lifecycle (contract → … → PR → knowledge update) into one **tiered "task-cycle" skill** that orchestrates the others; the ceremony scales with the risk tier, so low-risk slices skip most steps.

### 5.3 First hooks to add

Start with enforcement hooks that prevent obvious failures:

- block writes to generated files;
- block destructive commands;
- block edits to secrets or production config;
- run format/lint/tests after relevant edits;
- require verification evidence before the agent claims done.

Hook principle:

```text
silent on success, verbose on failure
```

### 5.4 First subagents to add

Start with only two or three:

- contract verifier;
- security reviewer;
- simplification reviewer.

Do not create a large agent team until the review process is already working.

## 6. When to add loops and automations

Do not automate a workflow until the manual version is boring.

A loop is ready only when:

- the task has happened at least three times;
- the prompt/skill is stable;
- the inputs are well-defined;
- the verifier rubric is checkable;
- the output format is predictable;
- the loop has a state file;
- the human approval gates are explicit;
- the token/runtime budget is defined.

Good first loops:

- daily CI failure summary;
- stale PR triage;
- dependency warning summary;
- issue classification;
- docs drift report.

Bad first loops:

- auto-merge code;
- edit auth or production config;
- broad refactors;
- schema changes;
- “fix everything failing in CI”.

## 7. Minimal installation checklist

Use this as a copy/paste checklist.

```text
Local tools
[ ] Git installed
[ ] Language toolchain installed
[ ] Python 3.11+ installed
[ ] uv installed
[ ] Node/npm installed if needed
[ ] make/just/task/npm scripts available

Agents
[ ] Claude Code installed and authenticated
[ ] Cursor CLI installed if used
[ ] Spec Kit installed from GitHub repository

Repo scaffold
[ ] Makefile or equivalent task runner
[ ] AGENTS.md shared protocol
[ ] CLAUDE.md Claude adapter
[ ] .cursor/rules/core.mdc if Cursor is used
[ ] docs/specs/
[ ] docs/tasks/
[ ] docs/tasks/_templates/ (contract.md, rubric.md, verification.md)
[ ] docs/adr/
[ ] docs/deferred.md
[ ] docs/agentic-ops/readiness.md

First workflow
[ ] product/system spec drafted
[ ] first task contract written
[ ] acceptance checks defined
[ ] implementation done in a reviewable slice
[ ] verification evidence captured
[ ] AI review completed where useful
[ ] human review completed
[ ] small commit created
```

## 8. Common failure modes and fixes

| Failure | Fix |
|---|---|
| Agent makes a huge diff | Split or checkpoint the remit; require evidence per checkpoint |
| Agent claims done without proof | Require `docs/tasks/<task-id>/verification.md` or PR evidence |
| Agent edits generated files | Add protected path rule and hook |
| Agent weakens tests | Review test diffs first; add rubric blocker |
| Agent chooses wrong tool command | Add command to Makefile and AGENTS.md |
| Context files become bloated | Delete discoverable facts; move procedures into skills, path-scoped rules or subdirectory guidance |
| Claude and Cursor disagree | Move shared truth into AGENTS.md/docs; keep adapters thin |
| Parallel agents collide | Use worktrees and partition by module/test/file |
| Repeated manual rescue | Reverse-spec the fix into a test, hook, skill, OKF note or contract template |

## 9. The first week plan

### Day 1: install and scaffold

- Install Claude Code, optional Cursor CLI and Spec Kit.
- Add `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/core.mdc` if needed.
- Add task runner commands.
- Add readiness checklist.

### Day 2: write the first spec

- Use Spec Kit or manual drafting.
- Write product/system intent.
- Clarify boundaries and approval gates.

### Day 3: first small task contract

- Choose a low-risk vertical slice.
- Write contract and acceptance checks.
- Implement with one agent.
- Capture evidence.

### Day 4: add review stack

- Add `/code-review` or Cursor/Codex review.
- Add PR contract template.
- Start risk-tiered review.

### Day 5: ratchet one real failure

- Pick one observed agent failure.
- Fix it with the smallest harness improvement: test, hook, skill, rule, task template or OKF note.
- Do not add rules for imagined failures.

## 10. Source notes

These commands and recommendations were checked against official documentation in June 2026:

- Claude Code quickstart and setup: https://code.claude.com/docs/en/quickstart and https://code.claude.com/docs/en/setup
- Cursor CLI docs: https://cursor.com/docs/cli/installation and https://cursor.com/cli
- GitHub Spec Kit installation docs: https://github.github.io/spec-kit/installation.html
- Codex plugin for Claude Code: https://github.com/openai/codex-plugin-cc
- Addy Osmani Agent Skills: https://github.com/addyosmani/agent-skills
- Ponytail: https://github.com/DietrichGebert/ponytail

Always check the upstream docs before standardising organisation-wide install commands.