# Agentic ops failure log

Recurring issues encountered during the task cycle. Each entry: what happened, root cause, fix.

---

## 2026-07-07 — Full `make verify` at every phase commit: ~30 min of low-signal gate time on one build

**Task:** 011-extract (build phase)

**What happened:** The build ran full `make verify` (~5–6 min) at eight points — the
green-base check, each of the six phase commits, and reruns chasing one transient failure —
totalling ~35 minutes of wall time. Nearly all of each run is `test_ingest_full_text.py`
(~2.5 min of real PDF parsing) which the extract slice barely touches; the slice's own 107
new tests run in ~2 seconds, and the 107 added tests moved the full-suite time by ~10
seconds. The user flagged the build as feeling long; the live model runs (~40 min, which
caught two real bugs) were well spent — the repeated full-suite gates were not.

**Root cause:** The task-cycle commit rule was written as "green `make verify` only" with a
single, undifferentiated gate. It predates the 008 slice that made the full suite expensive
(committed real-document ingest tests), so the rule silently inherited a 5-minute price per
checkpoint that no one re-derived. `make test-fast` existed as an inner-loop convenience but
nothing licensed it as a commit gate.

**Fix (adopted 2026-07-07, installed in Makefile + task-cycle spine § Commits +
task-cycle-build § Step 5 + harness.md § Verification layer):** a **tiered commit gate**.
New `make verify-fast` target (test-fast + typecheck + lint, ~30s) gates intermediate build
sub-phase commits; full `make verify` remains mandatory at the build-open baseline, any
phase touching **schema or ingest-adjacent code**, and the step-6 exit. The schema carve-out
is load-bearing, not caution: 011's phase 1 bumped a table-count assertion *inside* the
excluded `test_ingest_full_text.py` — under test-fast alone that assertion would not run
until five phases later. Counter-consideration kept explicit: full-suite-only signals
(ordering-dependent flakes — 011 saw one unreproduced 1-of-427 failure in a full run) now
surface only at full-verify points; that is the accepted trade. Never-commit-on-red is
unchanged.

---

## 2026-07-05 — One `/goal` spanned the whole cycle: review ran in the build conversation, author adjudicated its own findings

**Task:** 007-acquire

**What happened:** The user set `/goal "run task 007 implementation with the task cycle,
using the rubric as the completion criteria"`. The goal's stop-hook blocks ending the session
until the condition holds, and the rubric includes the review stack — so the review ran inside
the build conversation. Every review *lane* was a fresh context (contract-verifier,
security-auditor, Codex, code-review finders — none had written the code), but the **lead that
adjudicated their findings was the author**, sitting on ~150K tokens of build context. Two
findings were declined by the same agent whose code they criticised; the artifacts-as-handoff
property was never exercised.

**Root cause:** The task-cycle's conversation-boundary rule ("review in a fresh conversation")
and the goal's "don't stop until done" were in direct conflict; the agent resolved it toward
the goal. The monolithic skill made the boundary a paragraph, not a structural gate.

**Fix (adopted 2026-07-05):** (1) **One phase = one conversation = at most one `/goal`** —
goal #1 "through step 6: verification.md complete, make verify green" (conversation B); fresh
chat + goal #2 for the review stack (conversation C). (2) The task-cycle skill is **split into
a spine + three phase skills** (`task-cycle-design` / `-build` / `-review`), making the
conversation boundary the invocation boundary; the review skill states the
adjudicator-must-not-be-author rule directly. Also trims standing context: each conversation
now loads only its phase's instructions.

---

## 2026-07-05 — Step-7 finder lanes ingested 12K lines of fixture JSON: review ran ~2× the token budget

**Task:** 007-acquire

**What happened:** The Tier-3 stack ran the calibrated three-lane baseline plus `/code-review`
**medium** (8 finder angles on Sonnet) — and still totalled ≈675K subagent tokens against the
≤250K target. Dominant cause: the slice's diff legitimately contained two committed fixture
files (~12K lines of sanitized JSON), and every finder ran `git diff dev...HEAD` and read them.
Eight agents ingested the same generated data for zero findings; the data files already had
their own purpose-built checks (leak-guard test + the security lane's fixture audit).

**Root cause:** The review dispatch had no diff-hygiene rule for generated/bulk data. The
2026-06-30 entry had rejected path *include*-lists (they silently drop new code paths), and
nothing distinguished that from *exclude*-lists of known data globs.

**Fix (adopted 2026-07-05, installed in task-cycle-review step 7):** exclude generated/bulk
data files from the review diff by pathspec — e.g.
`git diff dev...HEAD -- ':!src/policy_atlas/data/*.json'` — and route data files to their own
audit lane. An exclude-list fails open (new code paths still enter review), so the 2026-06-30
rejection doesn't apply. Secondary observation for future calibration: the five cleanup angles
(reuse/simplification/efficiency/altitude/conventions, ~298K) yielded one applied one-liner and
two small refactors, while the three correctness angles (~191K) found all three real bugs — if
medium is still over budget after diff hygiene, collapse the cleanup angles into one combined
finder before touching the correctness angles.

---

## 2026-07-05 — Lead wrote ~450 lines of test scaffolding itself; executor routing didn't exist at plan time

**Task:** 007-acquire

**What happened:** `test_acquire.py` (~450 lines) was written by the lead (Fable) despite the
contract containing an unusually precise test list — the exact shape `fast-worker` (pinned
Sonnet) exists for. The routing table in harness.md was in place; nothing in the *plan* carried
a routing decision, so at implement time the lead defaulted to "faster to just do it".

**Root cause:** Delegation was an implement-time impulse instead of a plan-time decision.
Mid-build, the lead always has full context loaded and every task looks cheapest inline.

**Fix (adopted 2026-07-05, installed in task-cycle-design step 3 + harness.md routing):** the
plan marks each task with its **executor** (`lead` / `fast-worker` / `deep-reasoner` /
`codex`), decided at the plan gate where the human sees it. Counter-rule kept explicit:
one-command mechanical edits (`sed`-able renames, count bumps) stay inline — delegation costs
more than it saves there; and if you can't write the brief (one concern, intent, self-checkable
definition of done), it isn't delegable.

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

---

## 2026-07-05 — Plan-time executor marks over-assigned implementation to the lead

**Task:** 008-full-text (build phase)

**What happened:** The plan's executor column routed the schema/migration, the core
`ingest_full_text.py` module, the concurrency/egress test cases, the spec flow-back and
`verification.md` to `lead` — only the wiring and bulk-test transcription went to
`fast-worker`, one task to Codex. The build followed the marks faithfully, so the lead
(an orchestrator-class model) spent most of its budget typing implementation. The user
flagged it at the build retro: Fable should orchestrate — brief, adjudicate, review
delegated output — and do little direct implementation.

**Root cause:** Two gaps in the routing ladder, not a failure to follow it. (1) The
"seam-bearing product code → lead" rung conflates *designing* a seam (signatures,
semantics, failure vocabulary — genuinely lead work) with *typing its implementation*
(delegable against `make verify` + named tests, like any judgment-bearing execution).
(2) No burden inversion: with `lead` as an unremarkable default, plan-time
path-of-least-resistance keeps work in-house, and nothing at the plan gate pushes back.

**Fix (adopted 2026-07-05, installed in harness.md § Agent-side model routing +
task-cycle-design step 3):** the default executor is a delegate; every `lead` mark
carries a one-line justification the plan gate reviews. The ladder rung now reads
"seam *design* → lead; implementation of a lead-designed seam → delegable". Mid-build
smell added: the lead catching itself editing product code directly means a brief
should have been written. (The post-goal amendments in the same session already ran
this way — investigation, wiring, and root-cause all delegated — and delegate briefs
with "report verbatim, no workarounds" acceptance clauses surfaced a real upstream
parser bug the lead would likely have papered over inline.)

---

## 2026-07-05 — Review-stack token target blown 3× by finder fan-out on a large diff

**Task:** 008-full-text (review phase)

**What happened:** The Tier-3 stack ran within its lane shape (contract-verifier ·
security-auditor · Codex adversarial · `/code-review` medium — no duplicate lanes) and
with the 007 diff hygiene applied (bulk fixtures + lockfile pathspec-excluded), yet spent
≈760K subagent tokens against the ≤250K slice target. Breakdown: the 8 `/code-review`
medium finder angles ≈500K (each angle independently re-read the ~4.8K-line review diff
plus surrounding files), contract-verifier ≈118K, security ≈56K, verifiers ≈70K, Codex
≈20K. The economy rules bounded lane *count* but nothing bounded per-lane reading on a
diff this size.

**Root cause:** The ≤250K target was calibrated on smaller slices; `/code-review`
medium's cost scales with diff size × angle count, and each finder pays the full diff
independently. Diff hygiene removed the *data* bulk but 008's legitimate code+test+docs
diff was still ~4.8K lines.

**Fix (adopted 2026-07-05 retro, installed in task-cycle-review SKILL.md § token
economy/per-angle scoping + harness.md § review lane economics):** two changes. (1)
**Per-angle diff scoping at any diff size** — each `/code-review` finder angle gets a
lens-matched pathspec (correctness → `src`/`alembic`/config; cleanup → `src`+`tests`;
conventions → rule files + changed-file list) instead of one shared whole-diff command;
all eight angles kept (the empty removed-behaviour/cross-file results are the clean-bill
evidence, and the one confirmed bug came from line-by-line). (2) **Budget re-denominated
by model class** — the target was always a cost proxy, and a flat token ceiling priced
cheap fast-worker finder tokens like pinned-Opus lane tokens, misreading this run as a
3× blowout: now ≤250K reasoning-class + ≤500K fast-worker. The three main lanes stay
unchanged — on budget, each earned a unique finding (timeout-mislabel bug: /code-review
only; unmet rubric item: contract-verifier only; worker-egress gap: security only). A
slice-size cap was considered and **rejected** (user, 2026-07-05): big slices are fine —
sized to the model's orchestration capability — and the scoping/budget changes are what
keep their reviews affordable. Also installed: step-8-scheduled rubric items are named
in the contract-verifier brief (pending-with-contradiction-check, not MAJOR-unmet —
same retro).

## 2026-07-07 — Amended migration never re-applied locally; stale test DB masked an FK break that CI caught

**What happened:** The 011 review stack added `fk_exr_selection` by amending the
branch-local migration `d4e9b2f7a1c5` in place (legitimate pre-merge practice). The dev
DB was roundtripped (`downgrade -1` → `upgrade head`) — but the **test** DB was not.
`tests/conftest.py` applies migrations idempotently by revision (`alembic upgrade head`),
and the test DB was already stamped at that head, so the amended DDL never re-applied
locally. `make verify` ran green twice; PR #18's CI, building the schema fresh, failed
one test whose direct insert fabricated a `selection_run_id` the new FK correctly
rejects.

**Root cause:** Amending an already-applied migration changes the DDL without changing
the revision id, so every environment stamped at that head silently keeps the old
schema. Any revision-keyed idempotent migration runner (conftest, dev bring-up) has this
blind spot; a green local suite after a migration amendment proves nothing about the
amended DDL.

**Fix:** After amending an applied migration, roundtrip **every** local database that
has it applied (dev *and* `policy_atlas_test`) before trusting a green suite — the CI
fresh-build is the arbiter. Applied on 011: test DB roundtripped, the fabricating test
now seeds a real selection row, and the FK gained a positive rejection test
(`test_extraction_result_dangling_selection_run_rejected`). If migration amendments
recur, consider a `make test-db-rebuild` target (drop + fresh `upgrade head`) as the
standard post-amendment step.

## 2026-07-07 — Codex job tracking failed silently again: $CODEX_PLUGIN_ROOT absent in the lead's shell + error-swallowing background poll

**What happened:** During the 012 design phase, the plan-stage adversarial review came
back as a job id (the contract-stage one, minutes earlier, had returned findings
directly). The lead launched a background poll using the documented
`node "$CODEX_PLUGIN_ROOT/scripts/codex-companion.mjs" status …` command. That env var
is set only inside the codex-rescue agent's environment — in the lead's shell the call
dies with MODULE_NOT_FOUND. The poll piped status through `grep`/`case`, so the error
was swallowed and the loop degenerated into a silent spin-to-timeout; the finished
review (6m 36s) sat unread until the user asked "is the review still running?". Same
failure family as 2026-07-05 (polling progress lines) — job tracking has now failed in
design and implementation phases both.

**Root cause:** Two compounding defects. (1) The skill instruction encoded an
environment assumption that only holds inside the subagent, not where the instruction
is executed. (2) The hand-rolled poll violated fail-loud: filtering command output
before checking command success turns a hard error into an infinite wait.

**Fix (installed):** `scripts/codex_job.sh` — resolves the companion script itself
(env var → newest plugin cache → marketplaces checkout, error if none) and provides
`status | result | wait`; `wait` aborts immediately on any status failure and times
out loudly. Both task-cycle skills (design § Codex plumbing, review § Codex plumbing)
now point at the wrapper, state that a rescue return may be findings OR a job id, and
require any hand-rolled poll to be foreground-dry-run before backgrounding.

**Rule:** never background a poll you haven't run successfully in the foreground once;
never filter a command's output without also checking the command's own success.

**Addendum (same day, user challenge "have we over-engineered this?"):** yes, the
first wrapper was — reading the plugin's own docs showed the companion runtime has a
NATIVE `status <id> --wait --timeout-ms` (surfaced as `/codex:status [job-id]
[--wait]`, user-typed only), so the hand-rolled 15s polling loop duplicated built-in
functionality. Also, the skills' `$CODEX_PLUGIN_ROOT` never existed anywhere — the
plugin uses `${CLAUDE_PLUGIN_ROOT}`, injected only while its slash commands execute.
The shim now does the one thing the plugin genuinely leaves unsolved for the lead's
shell (path resolution) and delegates waiting to the native flag. Meta-lesson: read
the tool's own invocation docs BEFORE building the fix — the first wrapper was written
from the failure, not from the docs.
