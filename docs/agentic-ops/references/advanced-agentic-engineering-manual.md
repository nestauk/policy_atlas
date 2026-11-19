# Advanced Agentic Engineering Manual (extract)

A general draft from June 2026, written before the current model generation. Kept as background only: the live rules are in AGENTS.md, the task-cycle skills and harness.md.
Only the two sections that live files cite are kept here; the full draft is in git history.

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

The durable rule is reviewable remit. Small slices are the onboarding default, not the ambition ceiling. Larger remits are acceptable when the harness turns them into checkpoints, executable checks, evidence, verifier output, budgets and human approval gates.

## 16.2 Harness expiry review

Review periodically:

```text
Which rules are still needed?
Which hooks are blocking useful work?
Which skills are no longer pulling their weight?
Which model weaknesses have improved?
Which new model behaviours need new guardrails?
Which MCP/tool descriptions are too broad?
```
