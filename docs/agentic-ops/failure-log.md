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

---

## 2026-07-03 — Step-7 review stack token bloat: `/code-review` high-effort workflow burned 552K tokens for one low-severity finding

**Task:** 006-appraise

**What happened:** The Tier-3 review stack ran six lanes totalling ≈850K subagent tokens against a
~430-line implementation diff. The `/code-review` workflow at `high` effort alone consumed **552K
tokens across 16 agents** — 65% of the stack — and contributed exactly one confirmed finding the
other lanes missed (a low-severity `StopIteration` in the demo script). Its other ten findings were
rejected as contract-pinned or duplicated lanes costing a fraction as much: Codex adversarial found
"no defects" for **17K**, the contract verifier did the deepest unique work (rubric-item audit,
independent re-verify, a wrong count caught) for **86K**. Two lanes fully overlapped: `/security-review`
(71K) and the `security-auditor` subagent (48K) both ran and both came back clean.

**Root cause:** Two compounding process choices, not a tooling bug. (1) The task-cycle mandated
`/code-review` at `high` for Tier 3+ without knowing that `high` dispatches the workflow-backed
fan-out (one finder per angle + an independent verifier per candidate location) — an order of
magnitude costlier than a single reviewer, priced for "thoroughly audit this", not for a routine
slice review. (2) The stack listed `/security-review` *and* a Tier-3 security-auditor pass as
separate mandatory lanes, so the same diff got two full security reads.

**Fix (adopted 2026-07-03, installed in task-cycle step 7 + harness.md review-lane economics):**
- `/code-review` runs at **`medium`** by default at every tier. The high-effort workflow is
  reserved for explicit user opt-in (large/hard-gate-dense diffs where the user accepts the cost).
- **One security lane, not two:** Tier 3+ runs the `security-auditor` subagent; Tier ≤2 runs
  `/security-review`; never both on the same diff.
- **One Claude defect pass, not two** (tightened same day, on user challenge): `/code-review
  medium` *is* the Claude half of the Tier-3 heterogeneous pair — the pair's value is family
  diversity (Codex vs Claude), not reviewer count. Running a five-axis `code-reviewer` subagent
  *and* `/code-review` on the same diff is two same-family reads; on 006 the second read's
  marginal yield was an unused logger and one test-coverage gap.
- Tier-3 baseline stack = **three lanes**: contract-verifier · one security lane · the
  heterogeneous pair (Codex adversarial brief + `/code-review medium` as the Claude half).
- Budget guardrail: a routine feature-slice review should land **≤250K subagent tokens**; if the
  planned stack exceeds it, cut overlap before launching, and say so at the 🛑.

---

## 2026-07-05 — `codex-rescue` dispatch treated as synchronous; findings retrieval dead-ended in an autonomous session

**Task:** 007-acquire (contract-stage adversarial review)

**What happened:** The lead dispatched the contract-stage adversarial review through the
`codex-rescue` agent (correct route for a document-shaped brief) expecting the findings report in
the agent's final message. The agent instead returned only a background job id. A follow-up
SendMessage asking it to poll and return results was refused — the agent's contract is a fixed
single forward-to-Codex, and it does not poll, fetch results, or accept remit expansion mid-task.
Two wasted hops (~30K subagent tokens) before the lead recovered by invoking the plugin runtime
directly.

**Root cause:** Two-part process gap, not a tooling bug. (1) The rescue lane is async
fire-and-forget by design; the task-cycle SKILL.md documented the dispatch but its only retrieval
note — "background Codex jobs are tracked with `/codex:status` / `/codex:result` (user-typed)" —
assumes a human mid-loop. In an autonomous/background session no one types those commands, so the
documented loop dead-ends exactly where the review runs (fresh conversation, agent-driven).
(2) The lead didn't connect "user-typed" to "the agent's report will not contain findings" at
dispatch time.

**Fix (adopted 2026-07-05, installed in task-cycle step-1/3/7 tool notes):** the SKILL.md
invocation note now states that `codex-rescue` returns a job id, never findings, and that the
agent retrieves results itself via the plugin runtime — `codex-companion.mjs status|result
<job-id>` (poll `status` in a background shell, then `result`); the slash commands remain the
user-typed equivalents. Dispatch briefs need no change; the retrieval leg is now agent-executable.
