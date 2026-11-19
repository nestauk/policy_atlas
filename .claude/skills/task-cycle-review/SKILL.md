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

Reviews a built slice, fixes what the review finds, writes the durable records, opens the
PR, and closes out after merge. Conversation C **must be fresh**: fresh lanes are not
enough, because an author who adjudicates the findings grades its own work. Read the
[task-cycle spine](../task-cycle/SKILL.md) first. Optional `/goal`: "review stack run and
adjudicated, findings recorded, rubric item 8 holds".

## Exit condition

- [ ] Each lane that applies ran on the scoped diff; findings in `verification.md` § Review findings.
- [ ] Every finding, build-flagged anomaly and flagged minor deviation adjudicated.
- [ ] Fixes re-reviewed; `make verify` green.
- [ ] Frontend-heavy slice: second polish round signed off; screenshots in `verification.md`.
- [ ] Durable records written and the PR open (step 8).
- [ ] After merge: step 10 done.

## Human approval (🛑)

- Opening the PR (the user's go), and step 9 review and merge.
- The owner's sign-off on the second polish round (frontend-heavy slices).
- Open findings after the third fix-and-re-review round.
- A deviation escalated as a contract problem.

## Forbidden

- The lead writing reviews: pinned and heterogeneous reviewers do; the lead adjudicates
  and decides fixes (harness.md § Review lane economics).
- A second Claude defect pass, or a second security lane, on the same diff.
- `/code-review high` without explicit user opt-in.
- Include-list pathspecs for the review diff.
- Committing a raw review record.
- Commits or PRs at step 10.

## Re-ground

Read `rubric.md`, `verification.md` **including § Review handoff, the flagged deviations and
Known unverified items** (step-7 work items, not background), and `git diff dev...HEAD`.
Confirm `make verify` is green before any lane runs.

## Step 7 — Review stack

**Family flip.** The family that did not build anchors the review. **On mixed-executor
slices, apply it per surface** from the handoff's provenance map: Claude lanes anchor the
Codex-written files; the Codex review anchors the Claude-written ones (lead prompts
included). Without the map, a same-family read passes as heterogeneous.

**Baseline (Tier 3):** contract verifier · one security lane · the heterogeneous pair
(Codex adversarial + `/code-review` at **`medium`**). Two same-family reads of one diff add
almost nothing. The conditional lanes below add to this.

**Per-angle diff scoping.** Give each `/code-review` finder angle a **lens-matched
pathspec**, never one shared whole-diff command: correctness angles (line-by-line ·
removed-behaviour · cross-file) read `backend/src`, `backend/alembic`, config; cleanup
angles, if the recipe runs any (reuse · simplification · efficiency · altitude), read
`backend/src` + `backend/tests`; conventions reads the rule files plus the changed-file
list. Any diff size.

**Diff hygiene.** Before any reviewer runs, **exclude generated and bulk data files by
pathspec**, e.g. `git diff dev...HEAD -- ':!backend/tests/**/data/*.json'`, and give data
files their own check (leak guard, shape audit). An exclude-list fails open; an
include-list silently drops new code paths. Also exclude **declared non-slice commits**
(process-record commits the handoff names) from slice-code lanes; the adjudicator reads
them once to confirm they are what they claim.

The lanes:

- **Contract verifier** (Tier 2+): checks **every** rubric item (satisfied, evidence,
  unverified) **and the claims in `verification.md` and any ADR against the as-built
  code**: "documented but not built" is a finding. **Name the step-8 rubric items in the
  brief** (deferred.md entries, knowledge records), so it reports them as *pending: check
  for contradictions*. Use the `contract-verifier` subagent; alternatives are a read-only
  `codex-rescue` brief or an `agent-skills:code-reviewer` subagent, never the author. Not
  `/codex:review`: it takes no custom instructions, so it cannot carry the rubric.
- **`/code-review`**, always, at `medium`: bugs and instruction-file violations (cleanup
  was build step 5c). It **is** the Claude half of the pair: no `agent-skills:code-reviewer`
  subagent on the same diff.
- **One security lane**, always, because this is a data and provenance product (a Tier 0
  docs-only change may skip it):
  `agent-skills:security-auditor` subagent at Tier 3+, `/security-review` at Tier 2 and
  below. **Never both on one diff.**
- **Adversarial review** (Tier 2+): `/codex:adversarial-review` (user-typed, diff-shaped)
  or a read-only `codex-rescue` brief. Findings are adjudicated into `verification.md`.
  If Codex fails or is not available, a `deep-reasoner` subagent in a fresh context runs
  the same read-only brief, and `verification.md` records that a Claude reader stood in: a
  second independent read still finds defects the other lanes miss. Add an
  `agent-skills:test-engineer` subagent only when a coverage gap is suspected.
- **Live-trace content review**, when the evidence includes live runs: the lead reads the
  traces for **content** (model I/O per phase, validator and judge behaviour on real
  outputs, every build-flagged anomaly), not only cost and key hygiene. The database
  roll-up shows counts without the cause; the cause can exist **only** in the trace. Pull
  the failing call's exact input and output and **replay it through the real validator**.
  A persisted rejection or repair decision must persist its *reason*; one only traces can
  diagnose is a finding.
- **Design lane** (frontend-heavy): § Frontend-heavy slices.
- **`ponytail-review`**: load it with the Skill tool on the scoped diff.
- **OKF bundle check**: `make okf-validate` (inside `make verify`).

**Finding validity.** A finding anchors to a file that **ships**. Fenced code in
`docs/tasks/**` is not implementation; confirm the line exists in an executable file.

**Fake-done checks** (in adjudication and the rubric's no-weakened-tests item): tests
relaxed or deleted without a reviewed reason · swallowed errors · fake renames presented
as fixes · stub returns where logic was required · comment deletion as a fix. Check that
no fix made in this phase introduced one.

**Adjudication.** For each finding: adopt, decline with a recorded reason, or defer to
`docs/deferred.md` with a note. Apply fixes, re-run `make verify`, record what each lane
caught in § Review findings. Note convergent findings across families (high confidence)
and findings unique to one lane (they justify the lane). The review, not the agent that
changed it, confirms that a removed or replaced test left its behaviour covered.

- **An anomaly the build flagged "for the review stack" is a step-7 work item.** Root-cause
  it in the stack (the trace lane) before adjudication closes; one that survives review
  unexamined is fake-done.
- **Flagged minor deviations** are resolutions the build made alone. Confirm or contest
  each one explicitly: adopt as-is, require a change, or escalate as a contract problem.

**Fix-and-re-review loop.** After fixes, re-review only the new changes. At most three
rounds; then stop and bring the open findings to the owner.

## Frontend-heavy slices — design lane and second polish round

- **Design lane**: the pinned `frontend-designer` subagent, briefed read-only, reviews the
  built surfaces against the annex and returns ordered material fixes. The contract
  verifier checks behaviours against the annex's cited version, never looks. "Differs from
  the mock" is not a finding; "differs from the annex" is.
- **Second polish round**, after the fixes land: the task-cycle-build § Step 5b passes
  again, same rules. Then step 8.
- `verification.md` carries live-dev screenshots of every changed surface.

## Step 8 — Durable records + PR

Write the durable records against the final code, in this PR:

- New seams and step 5c's structural findings → [docs/deferred.md](../../../docs/deferred.md).
- Verified learning → `docs/knowledge/` (OKF concept + index + log lines, not a diary),
  from **both** the knowledge candidates in § Review handoff **and** this stack's findings:
  findings alone lose the build's lessons. Adjudicate each candidate: author, fold into an
  existing concept, or decline with a reason. An empty list on a non-trivial slice is a
  smell; note it.
- **Update `docs/agentic-ops/environment.md` and `readiness.md` in place** to describe the
  merged system: no "as of task" line, no running history.
- **Living-doc sweep** for anything this slice renames or lands. Historical `docs/tasks/**`
  stay untouched.

Draft the PR description from the task artifacts in the shape of
`.github/pull_request_template.md`: what and why (contract), proof linked to
verification.md, risk tier, AI role, review focus, known gaps, the public-safety and
reviews-run checklists. Use plain paths: relative links do not resolve in PR bodies. Open
`task/NNN-slug` → `dev` **on the user's go** (`gh pr create --base dev --body-file …`).

## Step 9 — 🛑 Human review + merge

For a large diff, offer a **PR-overview Artifact** (what changed and why) as a reading aid.
It never replaces reading the diff.

## Step 10 — Close-out (after merge)

Verify and clean only.

- **Reconcile (read-only):** what merged still matches the slice's `docs/knowledge/` and
  ADR claims, and `environment.md` and `readiness.md` describe it. A discrepancy is a
  step-8 miss: fold the fix into the **next slice's branch**, never a close-out PR.
- Delete any temporary scratchpad. Confirm the merge and delete the local task branch (a
  squash-merged tip is never an ancestor of dev: check content; expect the `-d` warning).
- The next slice's identity is its branch name and contract `Status` line. `AGENTS.md` does
  not change.

## Codex plumbing (code reviews)

- `/codex:review` and `/codex:adversarial-review` are user-typed only and diff-shaped. For
  a custom brief, use the `codex-rescue` subagent.
- ⚠️ It is write-capable by default: state **read-only / critique-only**.
- ⚠️ It is async: its final message is **either the findings or a job id**; check which
  first. For a job id: `scripts/codex_job.sh wait <job-id> [timeout-s]` (or
  `status`/`result`), the runtime's **native** wait.
- ⚠️ Do not write your own status poll: a filtered loop can hide a hard error until timeout.
