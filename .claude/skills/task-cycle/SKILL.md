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

The repeatable spine for landing one implementation slice. It orchestrates the artifacts
and commands that already exist — it does not replace them. The detail lives in three
**phase skills**; this file holds only what every phase must respect: the tier gate, the
conversation map, the hard gates, and the exit criteria.

| Phase | Skill | Steps | Conversation |
|---|---|---|---|
| Design | [`task-cycle-design`](../task-cycle-design/SKILL.md) | 1–4: contract · rubric · plan · ADR | A |
| Build | [`task-cycle-build`](../task-cycle-build/SKILL.md) | 5–6: implement · verify | B |
| Review | [`task-cycle-review`](../task-cycle-review/SKILL.md) | 7–10: review stack · PR · merge · close-out | C |

Authoritative boundaries: [AGENTS.md](../../../AGENTS.md). Full rationale:
[advanced-agentic-engineering-manual.md](../../../docs/agentic-ops/references/advanced-agentic-engineering-manual.md).
Recurring lessons: [failure-log.md](../../../docs/agentic-ops/failure-log.md) — the phase
skills encode them; when in doubt, the failure log wins over convenience.

## Step 0 — Pick the risk tier first (the lazy gate)

Decide the tier **before** any ceremony. It sets how much of the cycle applies. Don't run
the Tier-4 ritual for a docs typo; don't downgrade a gated-surface change to skip approval.

| Tier | Example | Cycle steps that apply |
|---|---|---|
| 0 | docs/comment typo | Implement → focused check → PR |
| 1 | small isolated code | Implement → tests → `/code-review` + `/security-review` → PR |
| 2 | feature slice, integration | Contract → rubric → plan → implement → verify → review → PR |
| 3 | auth, PII, schema, runtime egress | + security-auditor lane + adversarial review (contract + plan + code) + human deep review |
| 4 | scaffold, migration, prod config, public API | + human-approved plan + ADR + rollback plan |

A change touching a **hard gate** (schema · auth · **runtime egress** · deps · CI · prod
config · public interface · scaffold) is **never below Tier 3** — see Stop conditions.

*Runtime egress* = the **running product** reaching the outside world (search backends,
model providers) carrying project data. Agent/dev-time network use — fetching docs, MCP
servers, recorder scripts, `uv`/Docker installs — is **not** gated and is expected.

## Running it across conversations (and goals)

State lives in **files, not chat history** — by design — so the cycle splits cleanly
across fresh conversations. **One phase = one conversation = (at most) one `/goal`.**
A single goal spanning build *and* review forces same-chat review and makes the author
the adjudicator (failure-log, 2026-07-05) — never do it.

| Conversation | Phase skill | Re-ground by reading | Produces | `/goal` shape (optional) |
|---|---|---|---|---|
| A — design | task-cycle-design | the specs it cites | `docs/tasks/NNN/*` + ADR | none — ends at human 🛑s |
| B — build | task-cycle-build | `contract.md`, `plan.md` + specs | code + `verification.md` | "through step 6: verification.md complete, `make verify` green" |
| C — review | task-cycle-review | the diff, `rubric.md`, `verification.md` | findings → fixes → PR | "review stack run and adjudicated; rubric item 8 holds" |

- **Between phases: start fresh.** The committed artifact is the handoff; re-reading it is
  lossless, whereas `/compact`'s summary is lossy. **Review requires a fresh conversation**
  — not just fresh reviewer lanes: the *adjudicator* of findings must not be the chat that
  wrote the code.
- **Within a long phase: `/compact`**, not a fresh start. `verify` stays with `implement`.
- Open each fresh conversation by re-grounding: read the task's artifacts and the specs
  they cite; a build conversation runs `make verify` first (never build on a red base).

## Commits

Each phase boundary (and each build sub-phase from the plan) ends with a commit on the
`task/NNN-slug` branch — that's what turns the artifact into a real handoff. The agent
prepares and runs commits as defined steps: never on the default branch, never on a red
`make verify`. **commit ≠ push** — pushing and merging stay human; the agent drafts the PR
and opens it on your go (step 8); the human owns review + merge (step 9).

## Evidence requirements

- `make verify` green (okf-validate · test · typecheck · lint · build).
- `verification.md` complete, including the exact end-to-end command run.
- Every rubric box checked or explicitly justified.

## Exit criteria

Done **only** when: all rubric boxes hold · PR open with linked evidence · knowledge
updated. Anything short of this is in progress, not done.

## Stop conditions — halt and escalate

- A **hard gate** (schema · auth · runtime egress · deps · CI · prod config · public
  interface · scaffold) is unapproved. Do **not** scaffold around it. Sign-off first,
  recorded.
- Scope would grow past the contract, or a new table/seam beyond the contract is needed.
- The spec/contract is wrong enough to **block** the slice — halt and run spec refinement
  (task-cycle-design § Spec refinement); don't silently obey it or deviate. (A *minor*
  deviation resolvable within the contract's own vocabulary may instead be resolved and
  flagged in `verification.md` — see task-cycle-build.)
- The slice tempts **product** egress (a real search backend or model-provider call) when
  the contract says stub.
- Turn/token budget spent. Report the blocker; don't push through.

## Anti-rationalisation

| Excuse | Reality |
|---|---|
| "Small change, skip the contract." | Tier it. Tier 0/1 genuinely skip — but tiering is the decision, not skipping it. |
| "It's basically a Tier-1, just touches the schema." | Touching a hard gate is Tier 3+. Get approval first. |
| "Tests are slow, I verified by reading." | Reading is not evidence. `make verify` runs or it isn't done. |
| "I'll write verification.md after the PR." | Evidence precedes the completion claim, not follows it. |
| "The plan is obvious, skip the checkpoint." | The checkpoint is the human's, not yours. Tier 2+ pauses for it. |
| "I'll defer that edge case silently." | Flag it → deferred.md. Silent omission ≠ deferral. |
| "Faster to just do it myself than delegate." | Routing was decided at plan time (executor marks). Re-deciding mid-build is the rationalisation. |
| "The review lanes are fresh contexts, so same-chat review is fine." | The adjudicator is the reviewer that matters. Fresh conversation, or the author grades their own work. |

## Scope boundaries

This skill governs landing **one** slice. It does not pick *which* slice (that's the phase
plan), and it is not a loop — the human steers every 🛑. Promote to a loop only if
unattended task execution is ever wanted, and never for Tier 3/4 work.

**Invocation.** Phase skills can auto-trigger from their descriptions, but for a process
you want reliably applied, invoke explicitly (`/task-cycle-build`, "run the review stack
for task NNN"). Forgetting on a turn is survivable: the *enforcement* lives in durable
artifacts (templates, PR template, settings deny rules, AGENTS.md), not in a skill being
"active". The skills are the glue; those are the gates.
