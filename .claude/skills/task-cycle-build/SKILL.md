---
name: task-cycle-build
description: >
  Task-cycle phase B (steps 5–6): implement an approved Policy Atlas contract/plan and
  produce verification evidence. Trigger when starting implementation of a contracted
  slice ("implement task NNN", "start the build", a fresh conversation opening on an
  approved plan). Runs in its own conversation (B); scope a /goal to "through step 6"
  only — never let it span the review phase. Tier rules, hard gates and conversation
  map live in the task-cycle spine — read it first.
---

# Task cycle — build phase (steps 5–6)

Prerequisite: [task-cycle spine](../task-cycle/SKILL.md). Re-ground first: read
`docs/tasks/NNN-slug/contract.md` + `plan.md` and the specs they cite, then run
`make verify` — **never build on a red base** you'll later misattribute to your own
changes. An optional `/goal` for this phase is "through step 6: verification.md complete,
`make verify` green, phases committed" — one goal per phase, never spanning review.

## Tools this phase orchestrates

- **Implement:** `agent-skills:incremental-implementation`; ground framework code
  (LangGraph, SQLAlchemy, pydantic, alembic) in official docs with
  `agent-skills:source-driven-development`; seams/interfaces with
  `agent-skills:api-and-interface-design`; logic & bug-fixes via
  `agent-skills:test-driven-development` (failing test first; invoke as `/test`).
- **Delegate volume per the plan's executor marks** (decided at plan time — see
  harness.md § Agent-side model routing for the tiers and the delegation-brief shape):
  `fast-worker` for mechanical volume and test scaffolding from a precise list;
  `deep-reasoner` for reasoning offload; Codex as doer (`codex:rescue`) for a precise,
  machine-verifiable brief when Claude budget is the constraint — then Claude anchors the
  review (family-flip). The lead reviews delegated output before it lands; if it misses
  the bar, rewrite the brief or escalate the model — don't hand-polish weak output.
  Mid-build smell (failure-log, 2026-07-05): the lead catching itself editing product
  code directly means a brief should have been written — delegation is the default and
  `lead` marks need justification at the plan gate, not re-litigation mid-build.
- **Debug a red `make verify`:** `agent-skills:debugging-and-error-recovery` (root-cause,
  not guess); escalate a stubborn/substantial fix to `codex:rescue` — write-capable, a
  *doer*, not a reviewer.
- **Situational:** `agent-skills:deprecation-and-migration` (schema/API migrations),
  `agent-skills:observability-and-instrumentation` (logging/metrics/tracing),
  `agent-skills:git-workflow-and-versioning` (branch/commit hygiene).

## Step 5 — Implement

One contract at a time, incrementally. structlog only (no print/stdlib logging in package
code). Touch only what the contract requires. Land a check before the next sub-phase; each
plan checkpoint ends with a commit on `task/NNN-slug`, gated by the **tiered commit gate**
(011 retro: eight full-verify gates ≈ 30 min of low-signal wall time on a slice whose own
tests ran in seconds):

- **Intermediate phase commits**: green `make verify-fast` (test-fast + typecheck + lint).
- **Full `make verify` is mandatory at**: the build-open baseline (the re-ground above),
  any phase touching **schema or ingest-adjacent code** (table-count/metadata assertions
  live inside the excluded `test_ingest_full_text.py` — a schema slice silently skips
  them under test-fast; 011 phase 1 hit exactly this coupling), and the **step-6 exit**.
- The tiering changes *which suite runs*, never the rule: any red is still a full stop,
  and no commit lands on a red gate.
- **The plan's gate map is binding** (failure-log, 2026-07-08): which phase boundaries
  carry full verify vs verify-fast was decided at the plan gate — consecutive low-risk
  phases may share one full-verify gate there. Don't add full-verify runs mid-build
  "to be safe" (014 ran six where three carried the signal), and don't downgrade a
  plan-marked full gate either.

**When building reveals a design problem**, size it before reacting:
- **Blocking / material** (the contract or a spec is wrong enough to change the design):
  pause and flow it back — task-cycle-design § Spec refinement (propose → 🛑 human →
  update spec + log → resume). Don't code around an outgrown spec.
- **Minor, resolvable within the contract's own vocabulary** (e.g. the contract offers
  "None/absent" and one of the two makes its stated intent true): resolve it, add a test,
  and **flag it explicitly in `verification.md`'s diff summary** — visible deviation, not
  silent drift, and not a full stop (precedent: 007's None-vs-absent envelope persistence).

Durable records (`docs/knowledge/`, `docs/deferred.md`, agentic-ops claims) are authored
**after** the review stack finalises the code — at step 8, not here — so they describe
what actually shipped. But **capture is this phase's job** (014 retro, 2026-07-08): what
the build learned dies at the conversation boundary unless it's written into the handoff —
step 6's knowledge-candidates list below is where.

## Step 6 — Verify

Fill `docs/tasks/_templates/verification.md` → `docs/tasks/NNN-slug/verification.md`:
`make verify` table, named-test results, the **exact** end-to-end command, diff summary
(flagging any minor deviations per above), public-safety, gaps, and the **knowledge
candidates** list in § Review handoff (014 retro, 2026-07-08): one bullet per
durable-seeming lesson the build hit, however raw — surprises, gotchas, invariants that
held for a non-obvious reason — *not just* flagged deviations. Step 8 authors
`docs/knowledge/` from this list plus the review findings, against the final code; a
lesson that never makes the list is invisible to that conversation, which is how
step-8 knowledge drifted review-biased on 012–014 (the 014 `__main__`-guard/spawn lesson
made verification.md only as an incident note and became knowledge nowhere).

Drive the affected flow end-to-end with `/verify` (exercises real behaviour, not just
tests) — the flow it drove supplies the exact end-to-end command. **The live check runs
at the scope the contract pinned** (failure-log, 2026-07-08: default = changed surfaces
+ one cheap full-chain smoke; full live e2e only where the contract bought it) — a
bigger live run than contracted is spend the gate never approved, not extra rigour. If `make verify` is red,
root-cause it — don't guess. When the stop condition is objective (`make verify` green, a
named test), a `/goal` may drive the implement ↔ verify inner loop; judgment-call phases
never — they end at a 🛑.

**Fixture/recording slices only:** if the slice derives committed fixtures from real
recorded data, the sanitizer's output is verified by **substring-auditing the raw
recording against the committed fixture** (no identifying raw string survives), not by
reviewing the sanitizer's key list — see
`docs/knowledge/sanitized-fixtures-audit-against-raw.md`; put the audit in the contract's
acceptance checks at design time when you know the slice records.

## Phase exit

`make verify` fully green · end-to-end flow driven and recorded · `verification.md`
complete · all plan checkpoints committed. **Stop — do not run the review stack here.**
Review runs in a fresh conversation with
[`task-cycle-review`](../task-cycle-review/SKILL.md): the adjudicator of findings must not
be the conversation that wrote the code (failure-log, 2026-07-05).
