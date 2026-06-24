---
name: task-cycle
description: >
  The per-task lifecycle for Policy Atlas: contract → rubric → plan → ADR →
  implement → verify → review → PR → update knowledge, gated by risk tier.
  Trigger when starting a new implementation slice, picking up a task contract,
  or when the user says "run task NNN" / "start the next slice". Do NOT trigger
  for one-off edits, spec-prep, or answering questions — those skip the cycle.
  The ceremony scales with risk tier; low-tier tasks skip most steps.
---

# Task cycle

The repeatable spine for landing one implementation slice. It orchestrates the
artifacts and commands that already exist — it does not replace them. Read the
referenced file only when you reach the step that needs it.

Authoritative boundaries: [AGENTS.md](../../../AGENTS.md). Full rationale:
[advanced-agentic-engineering-manual.md](../../../docs/agentic-ops/references/advanced-agentic-engineering-manual.md).

## Tools this orchestrates

This skill drives capabilities that are **already installed** (the `agent-skills`, `codex` and
`ponytail` plugins the quick-start recommends) — it does not reimplement them:

- **Plan / break down:** `/plan`, `agent-skills:plan`
- **Refine a spec** (specs are living intent, not golden — see `docs/specs/README`):
  `agent-skills:idea-refine` / `agent-skills:spec` / `agent-skills:interview-me` (pin down ❓ opens),
  recorded via `agent-skills:documentation-and-adrs`.
- **Implement:** `agent-skills:incremental-implementation`; ground framework code (LangGraph,
  SQLAlchemy, pydantic, alembic) in official docs with `agent-skills:source-driven-development`;
  design seams/interfaces with `agent-skills:api-and-interface-design`; logic & bug-fixes via
  `agent-skills:test` (TDD — failing test first).
- **Debug a red `make verify`:** `agent-skills:debugging-and-error-recovery` (root-cause, not guess);
  escalate a stubborn/substantial fix to `codex:rescue` — Codex, write-capable: a *doer*, not a reviewer.
- **ADR:** `agent-skills:documentation-and-adrs`.
- **Review** (all read-only critique, no fixes):
  - `/code-review` (Claude) and `/codex:review` (Codex native pass) — find **defects/bugs** in the diff.
  - `/codex:adversarial-review` — challenge the **approach/design/assumptions** (takes focus text);
    `agent-skills:doubt-driven-development` applies the same fresh-context skepticism to key decisions.
  - `/security-review` + `agent-skills:security-and-hardening` (untrusted input — prompt injection,
    retrieval poisoning, tenant boundaries), plus the `agent-skills:code-reviewer` /
    `agent-skills:security-auditor` subagents (installed `agent-skills` plugin, not `.claude/agents/`
    — dispatch via Claude or view under `/agents`).
- **Simplify:** `ponytail-review` (over-engineering pass — what to cut), then `/simplify`; `ponytail` mode throughout.
- **Situational** (not every cycle): `agent-skills:deprecation-and-migration` (schema/API migrations),
  `agent-skills:observability-and-instrumentation` (adding logging/metrics/tracing),
  `agent-skills:git-workflow-and-versioning` (branch/commit hygiene). Frontend / CI / deploy / perf
  skills are deferred with their scope.

## Step 0 — Pick the risk tier first (the lazy gate)

Decide the tier **before** any ceremony. It sets how much of the cycle applies.
Don't run the Tier-4 ritual for a docs typo; don't downgrade a gated-surface
change to skip approval.

| Tier | Example | Cycle steps that apply |
|---|---|---|
| 0 | docs/comment typo | Implement → focused check → PR |
| 1 | small isolated code | Implement → tests → `/code-review` + `/security-review` → PR |
| 2 | feature slice, integration | Contract → rubric → plan → implement → verify → review → PR |
| 3 | auth, PII, schema, runtime egress | + `agent-skills:security-auditor` audit + adversarial review + human deep review |
| 4 | scaffold, migration, prod config, public API | + human-approved plan + ADR + rollback plan |

A change touching a **hard gate** (schema · auth · **runtime egress** · deps · CI · prod
config · public interface · scaffold) is **never below Tier 3** — see Stop conditions.

*Runtime egress* = the **running product** reaching the outside world (search backends, model
providers) carrying project data. Agent/dev-time network use — fetching docs, MCP servers (e.g.
codex for adversarial review), `uv`/Docker installs — is **not** gated and is expected.

## Workflow (Tier 2+; lower tiers skip marked steps)

1. **Contract** — copy [_templates/contract.md](../../../docs/tasks/_templates/contract.md) →
   `docs/tasks/NNN-slug/contract.md`. Read the specs it depends on *in depth*, not headings — if a
   spec looks wrong or incomplete, refine it first (see **Spec refinement** below).
   🛑 **Human approves the contract before planning** (Tier 2+).
2. **Rubric** — copy [_templates/rubric.md](../../../docs/tasks/_templates/rubric.md). Tier 2+ only.
3. **Plan** — `/plan` (read-only). Save accepted plan to `docs/tasks/NNN-slug/plan.md`.
   🛑 **Human confirms the plan** (Tier 2+).
4. **ADR** — only if a design decision is made or changed (Tier 3–4 by default).
   `docs/adr/NNNN-slug.md`, status Accepted with sign-off date (`agent-skills:documentation-and-adrs`).
5. **Implement** — one contract at a time, incrementally (`agent-skills:incremental-implementation`).
   structlog only (no print/stdlib logging). Touch only what the contract requires. For logic and
   bug-fixes, drive with a failing test first (`agent-skills:test`). If building reveals the design is
   wrong, pause and flow it back (**Spec refinement**) — don't code around an outgrown spec. Land a
   check before the next step.
6. **Verify** — fill [verification.md](../../../docs/tasks/_templates/verification.md): `make verify`
   green, named-test results, the **exact** end-to-end command, diff summary, public-safety, gaps.
   If `make verify` is red, root-cause it (`agent-skills:debugging-and-error-recovery`) — don't guess.
7. **Review stack** (after correctness — `make verify` green is the self-verify gate):
   - **Contract verifier** (Tier 2+) — a *fresh* reviewer checks the implementation against **every**
     rubric item: satisfied? what evidence? what's unverified? Use `/codex:review` or an
     `agent-skills:code-reviewer` subagent — **not** the agent that wrote the code.
   - `/code-review` — always.
   - `/security-review` — always (data/provenance product; every PR gets a security skim). Tier 0 docs-only may skip.
   - **OKF bundle check** — if the task touched `docs/specs/` or `docs/knowledge/`, run `/okf validate`.
     Every non-reserved `.md` in a bundle tree is a concept and needs a non-empty `type` (a new doc
     dropped in without frontmatter breaks conformance).
   - Adversarial review — challenge the approach with `/codex:adversarial-review`; plus the
     `agent-skills:code-reviewer` subagent, Tier 2+; add `agent-skills:security-auditor` at Tier 3+.
     At Tier 3+ aim for **two heterogeneous reviewers** (e.g. `/codex:adversarial-review` + an
     `agent-skills:code-reviewer` subagent — different model families), not two of the same.
   - `/simplify` (or `ponytail`) — last, cleanup only.
8. **PR** — open with the [PR template](../../../.github/pull_request_template.md); link
   verification.md rather than re-pasting evidence. Branch `task/NNN-slug` → `dev`.
9. 🛑 **Human review + merge.**
10. **Update knowledge** (after merge):
    - new seams → [docs/deferred.md](../../../docs/deferred.md);
    - verified durable learning → `docs/knowledge/` (OKF), not a diary;
    - ADR if a decision changed; update AGENTS.md **Current phase**;
    - delete any temporary scratchpad.

## Spec refinement (specs are living)

Specs are current best *intent*, not golden ([docs/specs/README](../../../docs/specs/README)) —
refining them is **part of this cycle**, not an exception. It fires at two points:

- **Contract (step 1):** if reading the specs in depth shows one is wrong or incomplete, refine it
  *first* — the contract must stand on specs you trust.
- **Implement (step 5):** if building reveals the design is wrong, **pause and flow the change back**
  before coding around it.

The flow-back, same each time: propose → 🛑 **human decision** → update the spec + status markers
(+ a `docs/adr/` ADR if consequential, via `agent-skills:documentation-and-adrs`) → add a line to the
spec bundle's `log.md` → resume. Shape the change with `agent-skills:idea-refine` / `agent-skills:spec`
/ `agent-skills:interview-me` (pin down ❓ opens) / `agent-skills:api-and-interface-design` /
`agent-skills:doubt-driven-development`. Sources are **frozen** — change the *spec*, not the source
([ADR 0002](../../../docs/adr/0002-spec-governance.md)).

## Evidence requirements

- `make verify` green (test · typecheck · lint · build).
- verification.md complete, including the exact end-to-end command run.
- Every rubric box checked or explicitly justified.

## Exit criteria

Done **only** when: all rubric boxes hold · PR open with linked evidence · knowledge updated.
Anything short of this is in progress, not done.

## Anti-rationalisation

| Excuse | Reality |
|---|---|
| "Small change, skip the contract." | Tier it. Tier 0/1 genuinely skip — but tiering is the decision, not skipping it. |
| "It's basically a Tier-1, just touches the schema." | Touching a hard gate is Tier 3+. Get approval first. |
| "Tests are slow, I verified by reading." | Reading is not evidence. `make verify` runs or it isn't done. |
| "I'll write verification.md after the PR." | Evidence precedes the completion claim, not follows it. |
| "The plan is obvious, skip the checkpoint." | The checkpoint is the human's, not yours. Tier 2+ pauses for it. |
| "I'll defer that edge case silently." | Flag it → deferred.md. Silent omission ≠ deferral. |

## Stop conditions — halt and escalate

- A **hard gate** (schema · auth · runtime egress · deps · CI · prod config · public interface · scaffold)
  is unapproved. Do **not** scaffold around it. Get sign-off, recorded, first.
- Scope would grow past the contract, or a new table/seam beyond the contract is needed.
- The spec/contract is wrong enough to **block** the slice — halt and run **Spec refinement** (above)
  before continuing; don't silently obey it or deviate.
- The slice tempts **product** egress (a real search backend or model-provider call) when the contract says stub.
- Turn/token budget spent. Report the blocker; don't push through.

## Scope boundaries

This skill governs landing **one** slice. It does not pick *which* slice (that's the phase plan),
and it is not a loop — the human steers every 🛑. Promote to a loop only if unattended task
execution is ever wanted, and never for Tier 3/4 work.

## Running it across conversations

**Invocation.** The skill can auto-trigger from its description when you start a slice, but that's a
model judgment call — for a process you want reliably applied, invoke it explicitly (`/task-cycle`, or
"start task NNN with the task cycle"). Forgetting on a turn is survivable: the *enforcement* lives in
durable artifacts (the contract/rubric/verification templates, the PR template, `.claude/settings.json`
deny rules, AGENTS.md), not in the skill being "active". The skill is the glue; those are the gates.

**Context strategy.** State lives in **files, not chat history** — by design — so the cycle splits
cleanly across fresh conversations. Decision rule: **start a fresh conversation when the state is
already in a committed artifact; `/compact` when valuable state is in-flight and not yet in a file.**

| Conversation | Phase | Re-ground by reading | Produces |
|---|---|---|---|
| A — design | Contract · Rubric · Plan · ADR | the specs it cites | `docs/tasks/NNN/*` + ADR |
| B — build | Implement · Verify | `contract.md`, `plan.md` + specs | code + `verification.md` |
| C — review | the review stack | the diff, `rubric.md`, `verification.md` | findings → fixes → PR |

- **Between phases: start fresh.** The committed artifact is the handoff; re-reading it is lossless,
  whereas `/compact`'s summary is lossy. **Review especially wants a fresh conversation** — the
  contract-verifier / adversarial reviewer must not be the chat that wrote the code.
- **Within a long phase: `/compact`**, not a fresh start — it keeps the in-flight thread that isn't in
  a file yet (e.g. a big implementation mid-way). `verify` stays with `implement` (you iterate between them).
- Open each fresh conversation by re-grounding (`agent-skills:context-engineering` helps): read the
  task's `contract.md` / `plan.md` and the specs they cite, then continue the cycle.

**Commits.** Each phase boundary ends with a commit on the `task/NNN-slug` branch — that's what turns
the artifact into a real handoff for the next conversation. The agent prepares and runs the commit
**on your go** (it's a defined step, not automatic): it **asks first**, never commits the default
branch, and never commits a red `make verify`. **commit ≠ push** — push, PR and merge stay human
(steps 8–9). `agent-skills:git-workflow-and-versioning` helps with message/branch hygiene.
