# AI-native Development Playbook

*A lightweight operating model for using coding agents safely and effectively in software teams*

**Draft v0.1 | June 2026**

## Who this is for

This playbook is for engineers, product-minded technical leads and collaborators who use AI coding agents such as Claude Code, Cursor, Copilot/Codex or similar tools to build software. It is intentionally practical and adoption-focused. It is not the full advanced agentic engineering manual.

The goal is to make AI-native development **safer by default, not heavier by default**.

## Executive summary

AI-native development is not about accepting whatever an agent writes. It is a disciplined workflow in which agents help with planning, implementation, testing and review, while humans remain responsible for intent, risk, architecture, security and merge decisions.

The core workflow is simple:

```text
clear intent
→ reviewable remit
→ executable evidence
→ risk-based review
→ human accountability
→ improve the harness only when needed
```

Use the lightest workflow that gives enough confidence for the risk of the change. Most everyday tasks should not require a heavyweight process. Risky changes should.

## 1. Core principles

### 1.1 Use AI to accelerate engineering, not replace it

AI agents are fast implementation partners. They can draft code, run tests, explain errors, propose plans and review diffs. They do not own the system. A human must still decide what should be built, whether the result is correct, and whether it is safe to merge.

### 1.2 Keep work scoped enough to verify

The best AI-generated change is coherent, bounded and verifiable. For onboarding and everyday work, prefer small slices. In mature harnesses, agents may take a larger remit when the work is partitioned into reviewable checkpoints, executable checks, evidence and clear human approval gates. The control is acceptance evidence and blast radius, not task size alone.

### 1.3 Evidence beats confidence

An agent saying "done" is not evidence. A task is done only when there is evidence: passing tests, type-checks, lint, builds, screenshots, logs, browser traces, or manual verification notes.

### 1.4 Review depth should match risk

Do not review a typo fix like a payment flow. Do not review a payment flow like a typo fix. Match process weight to blast radius, expected lifespan and how many people will need to maintain the code.

### 1.5 Never let agents weaken the gates

Agents may not remove tests, skip checks, lower coverage thresholds, weaken CI, change security controls, or broaden permissions just to get green output. CI, tests, lint and security checks are walls, not suggestions.

Do not rely on prose instructions for absolute prohibitions. If something must not happen, enforce it with permissions, hooks, protected branches, CI, managed settings or review gates.

### 1.6 Keep always-loaded context tiny

`AGENTS.md`, root `CLAUDE.md` and always-applied Cursor rules should not be codebase tours. Agents can inspect the repo. Always-loaded files should contain only non-obvious landmines, approval gates, canonical commands and pointers to the right artefacts. Put procedures in skills, path-specific constraints in scoped rules or subdirectory guidance, and deterministic guardrails in hooks or permissions.

### 1.7 Improve the system only when failure teaches you something

Do not add rules, hooks, skills or process because they sound impressive. Add them when a real failure repeats, when a serious failure exposes a missing guardrail, or when a recurring workflow is worth standardising.

### 1.8 Treat public repos as disclosure surfaces

Most durable repo artefacts in open-source projects are public evidence, not private agent memory. Commit only public-safe guidance, specs, contracts, ADRs and verification summaries. Keep raw scratchpads, exploit notes, private threat analysis, credentials, logs, traces, screenshots, HAR files and incident details in ignored or private locations.

## 2. Risk-tiered workflow

Decide the risk tier before starting. The tier determines how much process is justified.

| Tier | Typical work | Required workflow |
|---|---|---|
| 0 | Documentation typo, copy change, harmless comment | Direct edit, quick check, optional review |
| 1 | Small isolated code change | Brief plan, focused checks, PR contract, human skim |
| 2 | Feature slice, integration, moderate refactor | Read-only planning, task scope, tests/checks, AI first-pass review, human review |
| 3 | Auth, permissions, PII, tenant boundaries, payments, secrets, schema, public APIs | Explicit task contract, evidence file, security review, independent AI review, human deep review |
| 4 | Data migration, deletion, production config, release process, broad architectural change | Human-approved plan, ADR or decision record, rollback plan, full review stack, senior sign-off |

The tier is not about whether AI wrote the code. It is about the cost of being wrong.

## 3. Default workflow for everyday work

Use this for most AI-assisted development.

1. **Decide the risk tier.** Identify whether the task is low-risk, medium-risk or high-risk before asking the agent to edit.
2. **Plan briefly.** For non-trivial work, ask the agent to inspect first and produce a short plan before coding.
3. **Keep the remit reviewable.** One task should produce a coherent diff or a clear series of checkpoints that can be verified and integrated.
4. **Provide relevant context only.** Point to the specific files, spec, issue or examples the agent needs. Do not dump everything.
5. **Let the agent implement.** Prefer existing patterns. Avoid broad refactors unless they are the task.
6. **Run checks.** At minimum, run the narrowest relevant tests and any standard lint/type/build commands for the touched area.
7. **Capture proof.** Keep command output, screenshots, logs or manual verification notes.
8. **Fill in the PR contract.** Make intent, evidence, risk and review focus visible.
9. **Use AI review as a first pass.** Treat AI review as a sensor, not a verdict.
10. **Human owns the merge.** Merge only when a person can stand behind the change.

## 4. PR contract

Every meaningful PR should include a short contract. This is not bureaucracy. It saves reviewer time and forces the author to understand the change.

```markdown
## What / why

What changed and why? Keep this to 1-2 sentences.

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

## Public safety

For public repositories, are logs, screenshots, traces, prompts and links safe to publish?
```

If you cannot fill this in, the work is not ready for review.

## 5. Planning and task scoping

For Tier 0 and many Tier 1 tasks, a sentence may be enough. For Tier 2+ work, use a lightweight task scope before implementation.

```markdown
# Task scope: <name>

## Goal

What should change in user or system terms?

## Context

Which issue, spec, code path or examples matter?

## In scope

Files, behaviours or modules likely to change.

## Out of scope

What the agent must not change.

## Acceptance checks

Tests, commands, screenshots, logs or manual checks that prove completion.

## Review focus

Correctness, data integrity, security, scope creep, maintainability, or UX.
```

Use task scopes to prevent wrong-direction work. Do not use them to create ceremony for obvious edits.

## 6. Verification evidence

A change is not complete until it produces evidence appropriate to its risk.

Common evidence:

- command output from tests, lint, type-check and build;
- screenshots, videos or browser traces for UI changes;
- logs or traces for debugging and runtime behaviour;
- API examples or conformance cases for interfaces;
- a short explanation of anything not verified.

For Tier 2+ work, include a verification note in the PR or in `docs/tasks/<task-id>/verification.md`:

```markdown
# Verification: <task>

## Commands run

| Command | Result | Notes |
|---|---|---|
| `make test` | pass/fail | |
| `make typecheck` | pass/fail | |
| `make lint` | pass/fail | |
| `make build` | pass/fail | |

## Manual verification

What was clicked, exercised, inspected or reproduced?

## Evidence artefacts

Screenshots, logs, traces, PR links or output paths.

## Known unverified items

Anything not checked.
```

## 7. Human review guidance

AI changes the shape of review. It does not remove accountability.

### 7.1 Review test changes first

Agents can accidentally or deliberately make tests easier to pass. If tests changed, inspect the test diff before the implementation diff.

Block the PR if tests were removed, skipped, weakened or rewritten to match broken behaviour without explicit justification.

### 7.2 Focus human attention where AI is weakest

Human review should focus on:

- whether this is the right change;
- correctness of the intended behaviour;
- security and trust boundaries;
- hidden data or schema implications;
- accidental scope expansion;
- maintainability and comprehension;
- whether the evidence is enough.

Let automation and AI reviewers handle first-pass lint, obvious mistakes and routine checks. Do not outsource judgement.

### 7.3 Use AI review as a sensor

A second model or reviewer agent can catch real issues. Treat its output as information, not approval. For high-risk work, use heterogeneous review: for example, a general correctness reviewer plus a security-focused reviewer.

### 7.4 Review intake bar

Do not ask a human to be the first verification layer. Return the PR to the agent or author if it lacks clear intent, risk tier, check output, evidence, public-safety review or known gaps. Large or evidence-poor PRs should be split, checkpointed or sent back for evidence before human review.

## 8. Minimal repo setup

A repo does not need a huge AI configuration to be AI-native. Start with the smallest useful setup.

```text
repo/
  AGENTS.md or CLAUDE.md
  Makefile or task runner
  docs/
    specs/
    adr/
    deferred.md
  .github/
    pull_request_template.md
```

Add these standard commands if possible:

```text
make setup
make test
make lint
make typecheck
make build
make verify
```

These commands are more useful than paragraphs of prose. Agents can run commands. They cannot reliably infer team-specific setup magic.

## 9. Using Claude Code and Cursor in the same repo

The workflow is tool-agnostic. Claude Code and Cursor can both operate in the same repo if shared truth lives in repo artefacts, not in tool-specific chat state.

Recommended split:

| Layer | Owner |
|---|---|
| Shared protocol | `AGENTS.md` |
| Claude adapter | `CLAUDE.md`, `.claude/skills/`, `.claude/agents/`, hooks |
| Cursor adapter | `.cursor/rules/`, `.cursor/plans/`, `.cursor/mcp.json` |
| Source of truth | `docs/specs/`, `docs/adr/`, PR contracts, task scopes, verification evidence |
| Executable truth | `Makefile`, CI, tests, scripts |

Rule:

```text
Shared guidance goes in shared files.
Tool-specific behaviour goes in tool-specific files.
Never copy the same long instruction into both.
```

### Minimal `AGENTS.md`

```markdown
# Agent protocol

- Use `make test`, `make typecheck`, `make lint`, `make build`.
- Do not change schema, auth, dependencies, CI or public interfaces without approval.
- Never edit generated files.
- Use `docs/specs/` and task scopes for intent.
- Provide evidence before claiming completion.
- Touch only what the task requires.
```

`AGENTS.md` should be a routing file plus a landmine list. It should not describe everything an agent can discover by reading the repo.

## 10. Tool guidance

Use tools according to the job, not tribal preference.

| Tool or pattern | Best use | Adoption guidance |
|---|---|---|
| Claude Code | Terminal-native execution, planning, hooks, subagents, skills, security review, goal loops | Excellent for advanced users and deeper automation |
| Cursor | IDE-native planning, editing, navigation, visual review, plans and rules | Excellent for day-to-day development and people who prefer editor workflows |
| GitHub Spec Kit | Optional spec artefact scaffolding | Useful for larger features, greenfield work and cross-agent handoff; not required for every task |
| Addy Osmani-style skills | Reusable senior-engineer workflows | Use after workflows repeat; do not load everything by default |
| Codex or second-model review | Independent/adversarial review | Use for meaningful or risky diffs |
| Ponytail or simplification review | Anti-bloat review after correctness | Run after tests and correctness are established |

Do not make the first rollout dependent on everyone installing every tool.

## 11. What not to do

Avoid these failure modes:

- accepting code you cannot explain;
- merging without proof it works;
- asking an agent to "make it production-ready" without acceptance criteria;
- committing blind `/init` output as permanent context;
- putting discoverable repo facts into always-loaded files;
- letting agents weaken tests, lint, CI, coverage or security checks;
- mixing unrelated refactors into feature work;
- running many parallel agents before you can review their output;
- automating a workflow before the manual version is stable;
- treating an AI review as a merge decision.

## 12. Adoption path for a team

Start with behaviour, not tooling.

### Phase 1: shared habits

- Keep AI-generated changes reviewable and evidenced.
- Require proof it works.
- Use the PR contract.
- Review test changes first.
- Block agents from weakening gates.

### Phase 2: shared templates

- Add a PR template.
- Add a minimal `AGENTS.md` or `CLAUDE.md`.
- Add `make test`, `make lint`, `make typecheck`, `make build`.
- Add task scopes for Tier 2+ work.

### Phase 3: shared tooling

- Introduce Spec Kit or another spec artefact workflow where useful.
- Add Claude Code or Cursor conventions.
- Add AI first-pass review.
- Add a small set of reusable skills.

### Phase 4: advanced agentic engineering

- Add hooks, subagents, worktrees, loops and automation only when the manual process is boring and safe.
- Track repeated failures and improve the harness deliberately.

## 13. One-page checklist

Before asking an agent to code:

- Is the remit bounded, reviewable and verifiable?
- Is the risk tier clear?
- Does the agent have the relevant context, and only the relevant context?
- Are out-of-scope areas explicit?
- Do we know how success will be checked?

Before opening a PR:

- Have tests/checks been run?
- Is proof included?
- Is the PR contract filled in?
- If tests changed, were they reviewed carefully?
- Did the agent avoid unrelated changes?
- Are security, data, schema and dependency risks called out?

Before merging:

- Can a human explain the change?
- Is the evidence enough for the risk tier?
- Has AI review been treated as advisory, not authoritative?
- Are known gaps documented?
- Is someone accountable for the result?

## 14. The playbook in one sentence

Use AI agents to move faster, but make every change reviewable, evidenced, risk-tiered and owned by a human.

## Sources and further reading

This playbook synthesises current practice from Anthropic/Claude Code, Cursor, GitHub Spec Kit, Addy Osmani's writing on agentic engineering and skills, and practitioner work on AI-native code review. The advanced manual should contain the deeper source notes, tool details, command references and automation patterns.