---
name: task-cycle-design
description: >
  Task-cycle phase A (steps 1–4): contract → rubric → plan → ADR for one Policy Atlas
  slice, with human approval gates and contract/plan-stage adversarial reviews.
  Trigger when opening a new slice (writing its contract), drafting or revising a
  rubric/plan, or when the user says "contract task NNN" / "plan the next slice".
  Runs in its own conversation (A); it ends at human 🛑s, never rolls into the build.
  Tier rules, hard gates and conversation map live in the task-cycle spine — read it first.
---

# Task cycle — design phase (steps 1–4)

Prerequisite: [task-cycle spine](../task-cycle/SKILL.md) (tier decided at step 0; Tier 2+
runs this phase; Tier 0/1 skip it). Templates: `docs/tasks/_templates/`.

## Tools this phase orchestrates

- **Clarify an underspecified ask:** `agent-skills:interview-me` — if the *ask itself* is
  unclear (why / for whom / what "done" means), clarify with the user before writing a
  contract on guesses.
- **Refine a spec** (specs are living intent, not golden — `docs/specs/README`):
  `agent-skills:idea-refine` / `agent-skills:spec`, recorded via
  `agent-skills:documentation-and-adrs`.
- **Plan / break down:** `/plan` (read-only), `agent-skills:planning-and-task-breakdown`
  (only when the slice has no precedent shape and decomposition itself is the hard part).
- **Seams / interfaces:** `agent-skills:api-and-interface-design`.
- **ADR:** `agent-skills:documentation-and-adrs`.
- **Adversarial review (documents):** a **read-only** brief through the `codex-rescue`
  agent (see § Codex plumbing below). `agent-skills:doubt-driven-development` applies the
  same fresh-context skepticism to key decisions.

## Step 1 — Contract

First, point the repo at this slice: set `AGENTS.md` **Current phase** to `NNN-slug` (the
slice you're *starting*). That pointer is repo orientation state — it **leads the next
slice here**, it does not trail the finishing one; it ships in this slice's branch.

Then copy `docs/tasks/_templates/contract.md` → `docs/tasks/NNN-slug/contract.md`. Read
the specs it depends on *in depth*, not headings — if a spec looks wrong or incomplete,
refine it first (§ Spec refinement).

🛑 **Human approves the contract before planning** (Tier 2+).

**Contract-stage adversarial review** (Tier 3+ standard; Tier 2 on demand): after the
human approves and before planning, the other family attacks `contract.md` + `rubric.md` —
a **read-only** brief via `codex-rescue` naming the reading list (contract, rubric, the
specs they cite, AGENTS.md, `docs/deferred.md`, the previous slice's contract as pattern
precedent). Targets: unstated assumptions, missed requirements, contradictions with the
specs, simpler alternatives. Decisions the human settled in review are *context, not
targets* (challenge only on contradiction). The lead adjudicates findings into the
contract; a material change reopens the 🛑 for re-approval, minor ones are folded in and
noted. Rationale: in this repo the contract fixes the design (schema, interfaces, tests) —
attack it at its own gate, not after a plan is built on it.

## Step 2 — Rubric

Copy `docs/tasks/_templates/rubric.md`. Tier 2+ only. Drafted alongside the contract so
the step-1 human review and adversarial pass see both.

## Step 3 — Plan

`/plan` (read-only). Save the accepted plan to `docs/tasks/NNN-slug/plan.md`. For a
pattern-following slice, the previous slice's `plan.md` is the template — mirror it
against the **as-built code** (not its own claims; plans drift, code doesn't).

**Executor routing is a plan-time decision** (failure-log, 2026-07-05). Mark each plan
task with its executor — `lead` · `fast-worker` · `deep-reasoner` · `codex` — per
harness.md § Agent-side model routing, so the plan reviewer and the human gate see the
routing before the build starts. Rules of thumb:
- Test scaffolding from a precise contract test list, mechanical sweeps from an exact
  spec, boilerplate → `fast-worker`.
- Seam-bearing product code, prompt-bearing work, taste-bearing surfaces, adjudication →
  `lead`.
- One-command mechanical edits (`sed`-able renames, count bumps) → `lead` **inline** —
  delegation costs more than it saves there.
- If you can't write the brief (one concern, its intent, a self-checkable definition of
  done), it isn't delegable — keep it with the lead.
Re-deciding routing mid-build is the rationalisation the plan column exists to prevent.

**Plan-phase adversarial review** (Tier 3+ standard; Tier 2 on demand — a loose contract,
a surprising plan, or reliance on a 🟡/❓ spec area): before the 🛑, the other family
attacks the drafted plan — a **read-only** `codex-rescue` brief on `plan.md`, with the
approved contract as *context, not target* (re-attack it only on contradiction). The brief
names the reading list (contract, plan, the specs they cite, AGENTS.md, `docs/deferred.md`)
and scopes the targets: plan↔contract/spec fit, sequencing risks, 🟡/❓ items, missed
requirements, simpler alternatives. If it can't critique from the files alone, the
artifacts aren't the self-sufficient handoff conversation B needs — fix that first.
(Distinct from the high-stakes two-independent-takes rule, which generates alternatives
*before* the design call; this attacks the chosen plan *after* drafting.)

For a real design fork, an **Artifact** laying the options out side by side (trade-offs,
diagrams) beats prose in chat as the decision surface.

🛑 **Human confirms the plan** (Tier 2+) — the lead adjudicates adversarial findings into it.

## Step 4 — ADR

Only if a design decision is made or changed (Tier 3–4 by default).
`docs/adr/NNNN-slug.md`, status Accepted with sign-off date
(`agent-skills:documentation-and-adrs`).

## Spec refinement (specs are living)

Specs are current best *intent*, not golden (`docs/specs/README`) — refining them is
**part of the cycle**, not an exception. It fires here (step 1: a spec is wrong or
incomplete — refine before contracting on it) and at build time (step 5: building reveals
the design is wrong — the build skill routes back here).

The flow-back, same each time: propose → 🛑 **human decision** → update the spec + status
markers (+ an ADR if consequential) → add a line to the spec bundle's `log.md` → resume.
Sources are **frozen** — change the *spec*, not the source (ADR 0002).

## Codex plumbing (document reviews)

`/codex:review` and `/codex:adversarial-review` are **user-typed only** and **diff-shaped**
— right for step-7 code review, wrong for document reviews. For steps 1/3 the agent routes
through the `codex-rescue` agent instead — same runtime, auto-applies the GPT-5.4 prompt
shaping. ⚠️ rescue defaults to **write-capable**: every review brief sent through it must
state **read-only / critique-only** explicitly. ⚠️ rescue is **async fire-and-forget**:
its final message is a job id, never the findings. Retrieve results yourself:
`node "$CODEX_PLUGIN_ROOT/scripts/codex-companion.mjs" status|result <job-id>` — poll the
`Phase:` line (not progress lines, which contain the word "completed") in a background
shell, then `result` (failure-log, 2026-07-05).

## Phase exit

Contract approved · rubric drafted · plan confirmed (with executor marks) · ADR written if
due · everything committed on `task/NNN-slug`. **Stop.** The build runs in a fresh
conversation with [`task-cycle-build`](../task-cycle-build/SKILL.md).
