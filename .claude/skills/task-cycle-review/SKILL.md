---
name: task-cycle-review
description: >
  Task-cycle phase C (steps 7–10): the review stack, PR, human merge, and close-out for
  a built Policy Atlas slice. Trigger when a slice's build is complete ("run the review
  stack for task NNN", "review and PR the slice", or a fresh conversation opening on a
  finished verification.md), and for post-merge close-out. MUST run in a fresh
  conversation — the adjudicator of findings must not be the chat that wrote the code.
  Tier rules, hard gates and conversation map live in the task-cycle spine — read it first.
---

# Task cycle — review phase (steps 7–10)

Prerequisite: [task-cycle spine](../task-cycle/SKILL.md). Re-ground first: read
`rubric.md`, `verification.md`, and the diff (`git diff dev...HEAD`). Confirm
`make verify` is green — that's the self-verify gate before any review lane runs.

**This phase requires a fresh conversation.** Fresh reviewer *lanes* are not enough: in
007 all lanes were fresh subagents but the author adjudicated its own findings from inside
the build chat (failure-log, 2026-07-05). An optional `/goal` for this phase is "review
stack run and adjudicated, findings recorded, rubric item 8 holds".

## Step 7 — Review stack

Reviews run on pinned/heterogeneous reviewers, **not the lead** — the lead adjudicates
findings and decides fixes (harness.md § review lane economics). Whichever model family
implemented, the other anchors review.

**Token economy (failure-log 2026-07-03 → 008 retro 2026-07-05):** the budget is a
**cost proxy, split by model class** (a flat ceiling misread 008's cheap finder fan-out
as a 3× blowout): a routine slice review lands **≤250K reasoning-class subagent tokens**
(contract-verifier · security · Codex adversarial · session-model verifiers) **and
≤500K fast-worker tokens** (finder/verifier fan-out). The Tier-3 baseline is **three
lanes** — contract-verifier · one security lane · the heterogeneous pair (Codex
adversarial + `/code-review` at **`medium`** as the Claude half) — no duplicate lanes,
no second Claude defect pass (two same-family reads of one diff add ~nothing).
`/code-review high` is an order of magnitude costlier than `medium` (006: 552K /
16 agents for one low-severity finding); reserve `high` for explicit user opt-in.

**Per-angle diff scoping (008 retro, 2026-07-05):** the diff is the dominant finder cost
and a naive fan-out pays it once per angle (008: 8 angles × a ~4.8K-line diff ≈ 500K
before any finding). When dispatching `/code-review` finder angles, hand each angle a
**lens-matched pathspec**, never one shared whole-diff command: correctness angles
(line-by-line · removed-behaviour · cross-file) read product code
(`src`/`alembic`/config); cleanup angles (reuse · simplification · efficiency ·
altitude) read `src` + `tests`; conventions reads the governing rule files plus the
changed-file list. Apply at any diff size — it's free precision, and big slices are
normal here (user, 2026-07-05: sized to the model's orchestration capability); the
scoping is what keeps their reviews affordable.

**Diff hygiene (failure-log, 2026-07-05):** before dispatching any reviewer, **exclude
generated/bulk data files from the review diff by pathspec** — e.g.
`git diff dev...HEAD -- ':!src/policy_atlas/data/*.json'` — and give data files their own
purpose-built check (leak guard, schema/shape audit). On 007, 12K lines of fixture JSON
were read by all 8 finder angles for zero findings (~2× budget overrun). NB this is an
*exclude*-list of known data globs — the 2026-06-30 entry rejected *include*-lists, which
silently drop new code paths; an exclude-list fails open.

The lanes:

- **Contract verifier** (Tier 2+) — a *fresh* reviewer checks the implementation against
  **every** rubric item: satisfied? what evidence? what's unverified? **And checks the
  claims in `verification.md` and any ADR against the as-built code** — "documented but
  not built" is a finding. **Name the step-8-scheduled rubric items in the brief**
  (deferred.md entries, knowledge records) so the verifier reports them as *pending —
  check for contradictions with shipped code*, not as unmet findings (008 retro: a
  planned-pending item was reported MAJOR; the valuable part was the stale-entry
  contradiction inside it — keep that check). Use the `contract-verifier` agent
  (`.claude/agents/`, pinned Opus, read-only), a **read-only** `codex-rescue` brief, or an
  `agent-skills:code-reviewer` subagent — **not** the agent that wrote the code. (Not
  `/codex:review` — the native diff pass takes no custom instructions, so it can't carry
  the rubric checklist.)
- **`/code-review`** — always, at `medium` (see economy above). This **is** the Claude
  half of the Tier-3 heterogeneous pair — do not also run an `agent-skills:code-reviewer`
  subagent on the same diff.
- **One security lane** — always (data/provenance product; Tier 0 docs-only may skip):
  `agent-skills:security-auditor` subagent at Tier 3+, `/security-review` at Tier ≤2 —
  **never both on the same diff**.
- **Adversarial review** — challenge the approach: `/codex:adversarial-review`
  (user-typed, diff-shaped) or a read-only `codex-rescue` brief; Tier 2+. At Tier 3+ the
  two heterogeneous reviewers are this Codex pass plus `/code-review medium` (family
  diversity, not reviewer count). Add `agent-skills:test-engineer` only when a coverage
  gap is suspected, not by default.
- **OKF bundle check** — mechanical: `make okf-validate` (runs inside `make verify`).
- **`/simplify`** — last, cleanup only (after `ponytail-review`'s what-to-cut pass). If
  `/code-review` already ran reuse/simplification/efficiency/altitude finder angles and
  their fixes were applied, a separate same-family pass duplicates it — record the
  justification instead of re-running.

**Finding validity:** a finding must anchor to a file that **ships** — fenced code blocks
in `docs/tasks/**` (contract/plan pseudocode) are not implementation; confirm a flagged
line exists in an executable file before raising it (failure-log, 2026-06-30).

**Fake-done checks** (fold into adjudication and the rubric's no-weakened-tests item):
relaxed/deleted tests · swallowed errors · fake renames presented as fixes · stub returns
where logic was required · comment-deletion-as-fix. Verify none of the *fixes applied
during this phase* introduced one.

**Adjudication:** the lead weighs each finding (adopt / decline with recorded reason /
defer to `docs/deferred.md` with a note), applies fixes, re-runs `make verify`, and
records what each lane caught in `verification.md` § Review findings. Convergent findings
across families are high-confidence; unique-to-one-lane findings justify that lane's
existence — note both.

## Step 8 — Durable records + PR

With the code now **finalised by the review stack**, author the slice's durable records
against it (they ride in this PR, not a post-merge step): new seams →
[docs/deferred.md](../../../docs/deferred.md); verified durable learning →
`docs/knowledge/` (OKF concept + index + log lines, not a diary); **point-in-time claims
in `docs/agentic-ops/`** (environment.md header, readiness.md task-sequence line — written
as of this PR merged); a **living-doc sweep** for anything this slice renames or lands
(deferred.md/knowledge describe the *current* system; historical `docs/tasks/**` stay
untouched).

Then draft the full PR description from the task artifacts in the shape of
`.github/pull_request_template.md`: What/why from the contract, proof from (and linked to)
verification.md, risk tier, AI role, review focus, known gaps, and the public-safety +
reviews-run checklists. Relative links don't resolve in PR bodies — use plain paths. Open
it `task/NNN-slug` → `dev` **on the user's go**
(`gh pr create --base dev --body-file …`). You review the draft — you don't transcribe it.

## Step 9 — 🛑 Human review + merge

For a large diff, offer a **PR-overview Artifact** (what changed and why) as a reading aid
— it supplements the diff, never replaces reviewing it.

## Step 10 — Close-out (after merge)

Verify-and-clean only — **commits nothing, opens no PR** (2026-07-03, user decision):
- **Reconcile (read-only):** confirm what merged still matches the slice's
  `docs/knowledge/` + ADR claims and the `docs/agentic-ops/` point-in-time claims. A
  discrepancy is a step-8 miss: note it and fold the fix into the **next slice's branch**
  — never a standalone close-out PR.
- Delete any temporary scratchpad; confirm merge and delete the local task branch (a
  squash-merged branch's tip is never an ancestor of dev — check content, and expect the
  `-d` warning).
- `AGENTS.md` **Current phase** moves with the *next* slice (design step 1), not here.

## Codex plumbing (code reviews)

`/codex:review` / `/codex:adversarial-review` are user-typed only and diff-shaped. For a
custom-brief pass the agent routes through the `codex-rescue` agent — ⚠️ state
**read-only / critique-only** explicitly (rescue defaults to write-capable); ⚠️ rescue is
async fire-and-forget — its final message is **either the findings or a job id**; check
which before doing anything else. For a job id, retrieve results with the repo wrapper:
`scripts/codex_job.sh wait <job-id>` (or `status`/`result`) — it resolves the companion
script itself and fails loudly. ⚠️ Never call
`node "$CODEX_PLUGIN_ROOT/..."` from the lead's shell: that env var exists only inside
the rescue agent, the call MODULE_NOT_FOUNDs, and a grep-filtered background poll turns
that into a silent spin-to-timeout (failure-log, 2026-07-07). If you do hand-roll a
poll: dry-run it in the foreground once before backgrounding, and match the `Phase:` /
job-state line, never progress lines (failure-log, 2026-07-05).
