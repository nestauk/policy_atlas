---
name: task-cycle
description: >
  The per-task lifecycle spine for Policy Atlas: contract → rubric → plan → ADR →
  implement → verify → review → PR → update knowledge, gated by risk tier and split
  into three phase skills (task-cycle-design, task-cycle-build, task-cycle-review).
  Trigger when starting a new implementation slice, picking up a task contract, or
  when the user says "run task NNN" / "start the next slice" — then invoke the phase
  skill for wherever the slice actually is. Do NOT trigger for one-off edits,
  spec-prep, or answering questions — those skip the cycle. The ceremony scales with
  risk tier; low-tier tasks skip most steps.
---

# Task cycle (spine)

The spine for landing one slice. The detail is in three **phase skills**; this file holds
what every phase respects: the tier, the conversation map, the hard gates, the exit criteria.

| Phase | Skill | Steps | Conversation |
|---|---|---|---|
| Design | [`task-cycle-design`](../task-cycle-design/SKILL.md) | 1–4: contract · rubric · plan · ADR | A |
| Build | [`task-cycle-build`](../task-cycle-build/SKILL.md) | 5–6: implement · simplify · verify | B |
| Review | [`task-cycle-review`](../task-cycle-review/SKILL.md) | 7–10: review stack · PR · merge · close-out | C |

Boundaries: [AGENTS.md](../../../AGENTS.md). Rationale:
[advanced-agentic-engineering-manual.md](../../../docs/agentic-ops/references/advanced-agentic-engineering-manual.md).
Recurring lessons: [failure-log.md](../../../docs/agentic-ops/failure-log.md); when in
doubt, the failure log wins over convenience.

## Step 0 — Pick the risk tier first

Decide the tier **before** any ceremony. Do not run the Tier-4 ritual for a docs typo; do
not downgrade a gated-surface change to skip approval.

| Tier | Example | Cycle steps that apply |
|---|---|---|
| 0 | docs/comment typo | Implement → focused check → PR |
| 1 | small isolated code | Implement → tests → `/code-review` + `/security-review` → PR |
| 2 | feature slice, integration | Contract → rubric → plan → implement → verify → review → PR |
| 3 | auth, PII, schema, runtime egress | + security-auditor lane + adversarial review (contract + plan + code) + human deep review |
| 4 | scaffold, migration, prod config, public API | + human-approved plan + ADR + rollback plan |

A change that touches a **hard gate** (schema · auth · **runtime egress** · deps · CI · prod
config · public interface · scaffold) is **never below Tier 3**.

*Runtime egress* = the **running product** reaching the outside world (search backends,
model providers) with project data. Agent and dev-time network use (docs, MCP servers,
recorder scripts, `uv`/Docker installs) is **not** gated.

## Conversations and goals

State lives in **files, not chat history**. **One phase = one conversation = (at most) one
`/goal`.** A goal across build *and* review makes the author the adjudicator: never.

| Conversation | Phase skill | Re-ground by reading | Produces | `/goal` shape (optional) |
|---|---|---|---|---|
| A — design | task-cycle-design | the specs it cites | `docs/tasks/NNN/*` + ADR | none — ends at human 🛑s |
| B — build | task-cycle-build | `contract.md`, `plan.md` + specs | code + `verification.md` | "through step 6: verification.md complete, `make verify` green" |
| C — review | task-cycle-review | the diff, `rubric.md`, `verification.md` | findings → fixes → PR | "review stack run and adjudicated; rubric item 8 holds" |

- **Between phases: start fresh.** The committed artifact is the handoff; `/compact` loses
  detail. **Review requires a fresh conversation**, not only fresh lanes: the
  *adjudicator* must not be the chat that wrote the code.
- **Within a long phase: `/compact`.** Verify stays with implement.
- A build conversation runs `make verify` first: never build on a red base.

## Commits

Each phase boundary and each plan sub-phase ends with a commit on `task/NNN-slug`: never on
the default branch, never on a red check. The check is **tiered**: `make verify-fast` for
intermediate build commits; `make frontend-verify-fast` with it for frontend polish
commits; full `make verify` at the build-open baseline, at any phase that touches schema
or ingest code, and at the step-6 exit (rule: task-cycle-build § Step 5). **commit ≠
push**: pushing and merging stay human. The agent opens the PR on the human's go (step 8);
the human reviews and merges (step 9).

## Evidence and exit criteria

- `make verify` green (the `Makefile` `verify` target lists its checks).
- `verification.md` complete, with the exact end-to-end command.
- Every rubric box checked or explicitly justified.

Done **only** when all rubric boxes hold · PR open with linked evidence · knowledge
updated. Anything less is in progress.

## Stop conditions — halt and escalate

- A **hard gate** is unapproved. Do **not** scaffold around it; get sign-off and record it.
- Scope would grow past the contract, or the slice needs a table or seam the contract lacks.
- The spec or contract is wrong enough to **block** the slice: run spec refinement
  (task-cycle-design § Spec refinement); do not silently obey or deviate. A *minor*
  deviation within the contract's vocabulary may be resolved and flagged in
  `verification.md` (task-cycle-build).
- The slice tempts **product** egress (a real search or model-provider call) when the
  contract says stub.
- Turn or token budget spent. Report the blocker.

## Anti-rationalisation

| Excuse | Reality |
|---|---|
| "Small change, skip the contract." | Tier it. Tier 0/1 genuinely skip — but tiering is the decision, not skipping it. |
| "It's basically a Tier-1, just touches the schema." | Touching a hard gate is Tier 3+. Get approval first. |
| "Tests are slow, I verified by reading." | Reading is not evidence. `make verify` runs or it isn't done. |
| "I'll write verification.md after the PR." | Evidence precedes the completion claim, not follows it. |
| "The plan is obvious, skip the checkpoint." | The checkpoint is the human's, not yours. Tier 2+ pauses for it. |
| "I'll defer that edge case silently." | Flag it → deferred.md. Silent omission ≠ deferral. |
| "The review lanes are fresh contexts, so same-chat review is fine." | The adjudicator is the reviewer that matters. Fresh conversation, or the author grades their own work. |

## Scope boundaries

This skill lands **one** slice. It does not pick the slice (the phase plan does), and it is
not a loop: the human steers every 🛑. Make it a loop only if unattended execution is ever
wanted, and never for Tier 3/4.

**Periodic structural review and test prune.** About every five merged slices, a chore
branch (not a product task) runs both, because a slice review sees one diff and misses
drift across slices.
- Structural review: logic in the wrong layer, a copy of an existing helper, a file pushed
  past 1,000 lines.
- Test prune: remove or replace tests tied to the implementation or already covered by a
  boundary test; keep the guards (task-cycle-build § Step 5). A reviewer who did not make
  the removal confirms it.

**Invocation.** Phase skills trigger from their descriptions; for reliable use, invoke one
explicitly (`/task-cycle-build`, "run the review stack for task NNN"). The *enforcement*
lives in durable artifacts (templates, PR template, settings deny rules, AGENTS.md), not in
an active skill. The skills are the glue; those are the gates.
