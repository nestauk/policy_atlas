# Agentic ops failure log

Recurring issues encountered during the task cycle. Each entry: what happened, root cause, fix.

---

## 2026-06-30 — `/code-review` workflow evaluated contract/plan pseudocode as implementation code

**Task:** 004-screen

**What happened:** The code-review workflow produced 9 "CONFIRMED" findings, all false positives.
The reviewers flagged constructs like `compile()` forwarding, LangGraph edge maps, and `screened_at`
field references — none of which existed in the implementation. Every finding pointed at a line in
`docs/tasks/004-screen/contract.md` or `plan.md`.

**Root cause:** The workflow diffs `git diff @{upstream}...HEAD`, which includes all changed files.
Both task artifact files contain fenced pseudocode blocks. The review subagents have no mechanism
to distinguish executable `.py` files from pseudocode in `.md` fences — they evaluate everything
with code-like syntax as real implementation.

**Fix:** Pass an explicit path filter when invoking the workflow so only executable files enter
the diff: `git diff @{upstream}...HEAD -- src/ tests/ alembic/`. Alternatively, add a reviewer
instruction to skip `.md` files or to confirm each finding is in an executable file before raising it.

**Adopted (2026-07-03):** the reviewer-instruction form, installed in task-cycle step 7 — a finding
must anchor to a file that ships; fenced blocks in `docs/tasks/**` are pseudocode. The path-filter
form was rejected: an include-list silently drops new paths from review as the codebase grows.
