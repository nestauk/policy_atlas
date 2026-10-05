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

The slice's identity lives in two places and nowhere else: the branch name
`task/NNN-slug` and the `Status` line at the top of its `contract.md`. Do not write phase
state into `AGENTS.md` (removed 2026-09-04: it duplicated both and was stale on `dev` after
every merge). A fresh conversation re-grounds by reading `docs/tasks/<newest>/contract.md`.

Copy `docs/tasks/_templates/contract.md` → `docs/tasks/NNN-slug/contract.md`. Read
the specs it depends on *in depth*, not headings — if a spec looks wrong or incomplete,
refine it first (§ Spec refinement).

**Live-check scope is a contract-time pin** (failure-log, 2026-07-08): when the
acceptance checks include a live manual check, name what it covers. Default = a live
run scoped to the slice's changed surfaces plus one cheap full-chain smoke; a full live
e2e is a deliberate upgrade the gate approves with its wall-time cost named (014's
inherited "skeleton e2e" spent ~50 min of downstream live chain to evidence surfaces
needing ~2 min). Don't inherit the previous slice's live-check shape by default.

**Design docs must be legible cold** (2026-08-13): the human gate and conversation B both
read these files without your context. Five habits, cheap now and expensive to retrofit:

- **Define the jargon once, in the contract** — the § Terms stub in the template. One row
  for each term a cold reader cannot expand: internal labels (`P1`), abbreviations
  (`PSS`), and any word the slice uses in a special sense (grain, round). The rubric and
  the plan *point at* that table. They never restate it.
- **Map what the slice touches, in whatever shape fits it.** For a UI slice that was a
  table of surface → the number it shows → the file that renders it → broken /
  correct-do-not-change. The shape is slice-specific; the rule is not. The
  "do not change" rows carry the same weight as the broken ones.
- **Number the problems, and use one numbering everywhere.** Goal, deliverable, scope,
  invariants, plan phases and rubric items all cite the same defect ids. Then any symptom
  traces to its fix, and an invariant with no defect shows up as a hole.
- **Split anything that is really two problems.** The tell: it needs two acceptance
  invariants. One defect, one cause, one invariant.
- **Resolve name collisions from the code, not by rewording.** When two names in the docs
  appear to mean one thing, read the source and say which is the field and which is the
  label. A doc that hedges here teaches the next reader the same confusion.

Prose follows the repo output style (ASD-STE100): short sentences, active voice, plain
words in place of metaphors — "accepted defect", not "wart" or "blemish".

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
against the **as-built code** (not its own claims; plans drift, code doesn't). The terms
and surface tables stay in the contract; the plan cites them and reuses its defect
numbering (§ Design docs must be legible cold).

**Executor routing is a plan-time decision** (failure-log, 2026-07-05). Mark each plan
task with its executor — `lead` · `fast-worker` · `deep-reasoner` · `codex` — per
harness.md § Agent-side model routing, so the plan reviewer and the human gate see the
routing before the build starts. **Default to a delegate; every `lead` mark carries a
one-line justification the plan gate reviews** (failure-log, 2026-07-05 — the 008 plan
over-assigned to the lead; the burden sits on keeping work, not on delegating it).
The ladder (full version in harness.md):
- Can't write the brief (one concern, its intent, a self-checkable definition of done)?
  Not delegable — `lead`.
- Prompt-bearing work, taste-bearing surfaces, adjudication, and seam *design*
  (signatures, semantics, the brief itself) → `lead`, regardless of budget. The
  *implementation* of a lead-designed seam against a machine-verifiable done is
  delegable like any other execution — "seam-bearing" describes the design decision,
  not the typing.
- **Judgment-bearing execution** (nontrivial logic, multi-file coherence, unfamiliar
  APIs) with a machine-verifiable done → `codex` — the **default doer** for complex
  subtasks: ~Opus-tier capability on the non-Claude budget, and the family-flip review
  comes built in. (Async fire-and-forget: if the task would need mid-course steering,
  it fails the brief test — keep it with the lead.)
- Mechanical transcription of an exact spec (test scaffolding from a precise contract
  list, sweeps, boilerplate) → `fast-worker` — Codex overpays here and the async
  round-trip is slower.
- One-command mechanical edits (`sed`-able renames, count bumps) → `lead` **inline** —
  delegation costs more than it saves there.
- Analysis-not-code → `deep-reasoner`; Codex takes the second seat in
  two-independent-takes.
Re-deciding routing mid-build is the rationalisation the plan column exists to prevent.

**Gate consolidation is likewise a plan-time call** (failure-log, 2026-07-08): the plan
marks which phase boundaries carry a full `make verify` and which gate on
`make verify-fast` — consecutive low-risk phases (new files, no schema/reader contact)
may share a single full-verify gate, argued in the plan and reviewed at the plan 🛑.
The mandatory full-verify classes (build-open baseline · schema/ingest-adjacent phases ·
step-6 exit) are untouched; consolidation merges *adjacent* checkpoints, never skips a
class. 014 ran six full-suite gates (~45 min) where three carried the same signal.

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
its final message is **either the findings or a job id** — check which before doing
anything else. For a job id, retrieve results with the repo shim:
`scripts/codex_job.sh wait <job-id> [timeout-s]` (or `status`/`result`) — it only
resolves the companion-script path (the plugin's `${CLAUDE_PLUGIN_ROOT}` is injected
solely while its user-typed `/codex:*` commands run; no such variable exists in the
lead's shell — `$CODEX_PLUGIN_ROOT` never existed at all) and delegates waiting to the
runtime's **native** `status --wait --timeout-ms`. ⚠️ Do not hand-roll a status poll —
the runtime has one built in, and a grep-filtered background loop turns a hard error
into a silent spin-to-timeout (failure-log, 2026-07-07; progress-line pitfall
2026-07-05).

## Phase exit

Contract approved · rubric drafted · plan confirmed (with executor marks) · ADR written if
due · everything committed on `task/NNN-slug`. **Stop.** The build runs in a fresh
conversation with [`task-cycle-build`](../task-cycle-build/SKILL.md).
