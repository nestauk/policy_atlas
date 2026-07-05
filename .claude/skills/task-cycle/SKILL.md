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

- **Plan / break down:** `/plan`, `agent-skills:plan` (`agent-skills:planning-and-task-breakdown`)
- **Refine a spec** (specs are living intent, not golden — see `docs/specs/README`):
  `agent-skills:idea-refine` / `agent-skills:spec` / `agent-skills:interview-me` (pin down ❓ opens),
  recorded via `agent-skills:documentation-and-adrs`.
- **Implement:** `agent-skills:incremental-implementation`; ground framework code (LangGraph,
  SQLAlchemy, pydantic, alembic) in official docs with `agent-skills:source-driven-development`;
  design seams/interfaces with `agent-skills:api-and-interface-design`; logic & bug-fixes via
  `agent-skills:test-driven-development` (TDD — failing test first; invoke as `/test`). A precise,
  machine-verifiable brief can go to Codex as doer (`codex:rescue`) when Claude budget is the
  constraint — then Claude anchors the review (family-flip; see harness.md § Agent-side model routing).
- **Debug a red `make verify`:** `agent-skills:debugging-and-error-recovery` (root-cause, not guess);
  escalate a stubborn/substantial fix to `codex:rescue` — Codex, write-capable: a *doer*, not a reviewer.
- **ADR:** `agent-skills:documentation-and-adrs`.
- **Review** (all read-only critique, no fixes):
  - `/code-review` (Claude) and `/codex:review` (Codex native pass; user-typed only, diff-shaped,
    takes no custom instructions) — find **defects/bugs** in the diff.
  - `agent-skills:review` (`agent-skills:code-review-and-quality`) — five-axis inline review
    (correctness · readability · architecture · security · performance); lighter-weight alternative
    when the full `/code-review` workflow isn't warranted.
  - `/codex:adversarial-review` — challenge the **approach/design/assumptions** (takes focus text);
    fires up to three times in the cycle: at contract time (step 1, Tier 3+ — after the human
    approves, before planning) against `contract.md` + `rubric.md`; at plan time (step 3, Tier 3+)
    against `plan.md` with the approved contract as context; and in the step-7 stack against the
    diff. Invocation note: `/codex:review` and `/codex:adversarial-review` are **user-typed only**
    (`disable-model-invocation`) and **diff-shaped** (working-tree/branch/`--base`) — right for the
    step-7 code review. For *document* reviews (steps 1/3) and custom-brief verification, the agent
    routes through the `codex-rescue` agent instead — same Codex runtime, and it auto-applies the
    plugin's GPT-5.4 prompt-shaping. ⚠️ rescue defaults to **write-capable** (`--write`): every
    review/verification brief sent through it must state **read-only / critique-only** explicitly.
    Background Codex jobs are tracked with `/codex:status` / `/codex:result` (user-typed).
    `agent-skills:doubt-driven-development` applies the same fresh-context skepticism to key
    decisions.
  - `/security-review` + `agent-skills:security-and-hardening` (untrusted input — prompt injection,
    retrieval poisoning, tenant boundaries), plus the `agent-skills:code-reviewer` /
    `agent-skills:security-auditor` / `agent-skills:test-engineer` subagents (installed `agent-skills`
    plugin, not `.claude/agents/` — dispatch via Claude or view under `/agents`).
- **Simplify:** `ponytail-review` (over-engineering pass — what to cut), then `/simplify`
  (built-in; applies the cleanups); `ponytail` mode throughout.
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
| 3 | auth, PII, schema, runtime egress | + `agent-skills:security-auditor` audit + adversarial review (contract, step 1 + plan, step 3 + code, step 7) + human deep review |
| 4 | scaffold, migration, prod config, public API | + human-approved plan + ADR + rollback plan |

A change touching a **hard gate** (schema · auth · **runtime egress** · deps · CI · prod
config · public interface · scaffold) is **never below Tier 3** — see Stop conditions.

*Runtime egress* = the **running product** reaching the outside world (search backends, model
providers) carrying project data. Agent/dev-time network use — fetching docs, MCP servers (e.g.
codex for adversarial review), `uv`/Docker installs — is **not** gated and is expected.

## Workflow (Tier 2+; lower tiers skip marked steps)

1. **Contract** — first, point the repo at this slice: set `AGENTS.md` **Current phase** to
   `NNN-slug` (the slice you're *starting*). That pointer is repo orientation state, not a deliverable
   of the previous slice — so it **leads the next slice here**, it does not trail the finishing one
   (step 10); it ships in this slice's branch. Then copy
   [_templates/contract.md](../../../docs/tasks/_templates/contract.md) →
   `docs/tasks/NNN-slug/contract.md`. If the *ask itself* is underspecified (unclear why / for whom /
   what "done" means), clarify with the user first (`agent-skills:interview-me`) — don't write a
   contract on guesses. Read the specs it depends on *in depth*, not headings — if a spec looks wrong
   or incomplete, refine it first (see **Spec refinement** below).
   🛑 **Human approves the contract before planning** (Tier 2+).
   **Contract-stage adversarial review** (Tier 3+ standard; Tier 2 on demand): after the human
   approves and before planning, the other family attacks `contract.md` + `rubric.md` — a
   **read-only** brief through the `codex-rescue` agent (state critique-only explicitly; rescue
   defaults to write-capable) naming the reading list (contract, rubric, the specs they cite,
   AGENTS.md, `docs/deferred.md`, the previous slice's contract as pattern precedent). Targets:
   unstated assumptions, missed requirements, contradictions with the specs, simpler alternatives.
   Decisions the human settled in review are *context, not targets* (challenge only on
   contradiction). The lead adjudicates findings into the contract; a material change reopens the
   🛑 for re-approval, minor ones are folded in and noted. Rationale: in this repo the contract
   fixes the design (schema, interfaces, tests) — attack it at its own gate, not after a plan is
   built on it.
2. **Rubric** — copy [_templates/rubric.md](../../../docs/tasks/_templates/rubric.md). Tier 2+ only.
   (Drafted alongside the contract so the step-1 human review and adversarial pass see both.)
3. **Plan** — `/plan` (read-only). Save accepted plan to `docs/tasks/NNN-slug/plan.md`.
   For a pattern-following slice, the previous slice's `plan.md` is the template — mirror it
   against the as-built code (not its own claims; plans drift, code doesn't). Reach for
   `agent-skills:planning-and-task-breakdown` only when the slice has no precedent shape
   (first slice of a new kind: frontend, LLM tool, migration) and the decomposition itself is
   the hard part.
   **Plan-phase adversarial review** (Tier 3+ standard; Tier 2 on demand — a loose contract, a
   surprising plan, or reliance on a 🟡/❓ spec area): before the 🛑, the other family attacks the
   drafted plan — a **read-only** brief via `codex-rescue` on `plan.md`, with the approved (and
   already contract-stage-reviewed) `contract.md` as *context, not target* — re-attack the contract
   only on contradiction. The brief names the reading list (contract, plan, the specs they cite,
   AGENTS.md, `docs/deferred.md`) and scopes the targets: plan↔contract/spec fit, sequencing
   risks, 🟡/❓ items, missed requirements, simpler alternatives. If it can't critique from the
   files alone, the artifacts aren't the self-sufficient handoff conversation B needs — fix that
   first. (Distinct from the high-stakes two-independent-takes rule, which generates alternatives
   *before* the design call; this attacks the chosen plan *after* drafting.)
   For a real design fork, an **Artifact** laying the options out side by side (trade-offs,
   diagrams) beats prose in chat as the decision surface.
   🛑 **Human confirms the plan** (Tier 2+) — the lead adjudicates any adversarial findings into it.
4. **ADR** — only if a design decision is made or changed (Tier 3–4 by default).
   `docs/adr/NNNN-slug.md`, status Accepted with sign-off date (`agent-skills:documentation-and-adrs`).
5. **Implement** — one contract at a time, incrementally (`agent-skills:incremental-implementation`).
   structlog only (no print/stdlib logging). Touch only what the contract requires. For logic and
   bug-fixes, drive with a failing test first (`agent-skills:test-driven-development`). If building reveals the design is
   wrong, pause and flow it back (**Spec refinement**) — don't code around an outgrown spec. Land a
   check before the next step. When the stop condition is objective (`make verify` green, a named
   test), `/goal` may drive the implement ↔ verify inner loop (scope: harness.md § Verification
   layer); judgment-call phases never — they end at a 🛑. (Durable records — `docs/knowledge/` learning and `docs/deferred.md`
   seams — are authored **after** the review stack finalises the code, at step 8 — not here, so they
   describe what actually shipped, not a draft the review then changes.)
6. **Verify** — fill [verification.md](../../../docs/tasks/_templates/verification.md): `make verify`
   green, named-test results, the **exact** end-to-end command, diff summary, public-safety, gaps.
   Drive the affected flow end-to-end with `/verify` (exercises real behaviour, not just tests) —
   the flow it drove supplies the exact end-to-end command.
   If `make verify` is red, root-cause it (`agent-skills:debugging-and-error-recovery`) — don't guess.
7. **Review stack** (after correctness — `make verify` green is the self-verify gate). Reviews run
   on pinned/heterogeneous reviewers, **not the lead** — the lead adjudicates findings and decides
   fixes (harness.md § review lane economics). Run review in a fresh conversation. **Token economy
   (failure-log, 2026-07-03):** a routine slice review lands **≤250K subagent tokens**; the Tier-3
   baseline is **three lanes** — contract-verifier · one security lane · the heterogeneous pair
   (Codex adversarial + `/code-review` at **`medium`** as the Claude half) — no duplicate lanes,
   and in particular **no second Claude defect pass**: two same-family reads of one diff add
   ~nothing (006 adjudication). `/code-review high` dispatches a workflow fan-out an order of
   magnitude costlier than `medium` (measured on 006: 552K tokens / 16 agents for one extra
   low-severity finding); reserve `high` for explicit user opt-in on large or hard-gate-dense
   diffs. A finding must anchor to a
   file that **ships**: fenced code blocks in `docs/tasks/**` (contract/plan pseudocode) are not
   implementation — confirm a flagged line exists in an executable file before raising it
   (failure-log, 2026-06-30). Whichever model family
   implemented, the other anchors review:
   - **Contract verifier** (Tier 2+) — a *fresh* reviewer checks the implementation against **every**
     rubric item: satisfied? what evidence? what's unverified? **And checks the claims in
     `verification.md` and any ADR against the as-built code** — "documented but not built" is a
     finding (e.g. a named exception that doesn't exist). Use the `contract-verifier` agent
     (`.claude/agents/`, pinned Opus, read-only), a **read-only** `codex-rescue` brief, or an
     `agent-skills:code-reviewer` subagent — **not** the agent that wrote the code. (Not
     `/codex:review` — the native diff pass takes no custom instructions, so it can't carry the
     rubric/verification checklist.)
   - `/code-review` — always, at `medium` (see token economy above; `high` is user-opt-in only).
     This **is** the Claude half of the Tier-3 heterogeneous pair — do not also run an
     `agent-skills:code-reviewer` subagent on the same diff (same family, same target, near-zero
     marginal findings; failure-log, 2026-07-03).
   - **One security lane** — always (data/provenance product; every PR gets a security skim;
     Tier 0 docs-only may skip): `agent-skills:security-auditor` subagent at Tier 3+,
     `/security-review` at Tier ≤2 — **never both on the same diff** (they fully overlapped on
     006; failure-log, 2026-07-03).
   - **OKF bundle check** — mechanical: `make okf-validate` (runs inside `make verify`) enforces
     conformance — every non-reserved `.md` in a bundle tree is a concept and needs parseable
     frontmatter with a non-empty `type`; `docs/specs/sources/` is exempt (raw frozen sources, not
     concepts). The `/okf` skill (user-env) remains the authoring/navigation aid, not the gate.
   - Adversarial review — challenge the approach with `/codex:adversarial-review` (or a read-only
     `codex-rescue` brief); Tier 2+. At Tier 3+ the **two heterogeneous reviewers** are this Codex
     pass plus the `/code-review medium` pass above (different model families) — the pair is about
     family diversity, not reviewer count; a five-axis `agent-skills:code-reviewer` subagent is an
     *alternative* Claude half, never an addition. The security lane above already covers Tier 3
     security depth; add `agent-skills:test-engineer` only when a coverage gap is suspected, not
     by default.
   - `/simplify` — last, cleanup only (after `ponytail-review`'s what-to-cut pass).
   - Record what each review caught in `verification.md` (§ Review findings).
8. **PR** — first, with the code now **finalised by the review stack**, author the slice's durable
   records against it: new seams → [docs/deferred.md](../../../docs/deferred.md), verified durable
   learning → `docs/knowledge/` (OKF, not a diary), **and any point-in-time claims the slice
   changes in `docs/agentic-ops/`** (`environment.md` header, `readiness.md` task-sequence line —
   write them as of this PR merged; they become true at merge, same logic as the records above).
   Authoring them *after* review — not at implement —
   is what keeps them honest: they describe the code that shipped, and ride in this PR for the human to
   check, not a stranded post-merge step. Then the agent **drafts the full PR description** from the
   task artifacts, in the shape of the
   [PR template](../../../.github/pull_request_template.md): What/why from the contract, proof from
   (and linked to) verification.md, risk tier, AI role, review focus, known gaps, and the
   public-safety + reviews-run checklists. Open it `task/NNN-slug` → `dev` **on your go**
   (`gh pr create --base dev --body-file …`). You review the draft — you don't transcribe it.
9. 🛑 **Human review + merge.** For a large diff, offer a **PR-overview Artifact** (what changed
   and why, tables/diagrams) as a reading aid for this pass — it supplements the diff, never
   replaces reviewing it.
10. **Close out** (after merge) — knowledge + `deferred.md` + agentic-ops point-in-time claims
    (step 8) and any ADR (step 4) already shipped *in the PR*, and `AGENTS.md` **Current phase**
    moves with the *next* slice (step 1), so this step is **verify-and-clean only — it commits
    nothing and opens no PR** (2026-07-03, user decision, after 006's two-line close-out PR):
    - **reconcile (read-only)** — confirm what merged still matches the slice's `docs/knowledge/`
      + ADR claims and the `docs/agentic-ops/` point-in-time claims. A discrepancy is a step-8
      miss: note it and fold the fix into the **next slice's branch** (like the Current-phase
      pointer) — never a standalone close-out PR;
    - delete any temporary scratchpad; confirm merge and delete the local task branch.
    The slices chain — each opens by repointing Current phase (step 1) and closes here; the human
    still steers every 🛑 (this is **not** an unattended loop — see *Scope boundaries*).

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
  task's `contract.md` / `plan.md` and the specs they cite, then continue the cycle. A **build**
  conversation (B) additionally confirms the baseline before implementing: run `make verify` first —
  don't build on a red base you'll later misattribute to your own changes.

**Commits.** Each phase boundary ends with a commit on the `task/NNN-slug` branch — that's what turns
the artifact into a real handoff for the next conversation. The agent prepares and runs the commit
**on your go** (it's a defined step, not automatic): it **asks first**, never commits the default
branch, and never commits a red `make verify`. **commit ≠ push** — pushing and merging stay human; the agent **drafts** the PR and opens it on your
go (step 8), but you own review + merge (step 9). `agent-skills:git-workflow-and-versioning` helps
with message/branch hygiene.
