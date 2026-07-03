# Agentic-ops backlog

Harness improvements and decisions, per the manual's maintenance cadence. Each deferred item names
its **trigger to act** — don't pre-build, earn it. Baseline audit 2026-06-24 against the four docs in
[references/](references/) (manual, quick-start, AI-native playbook, OKF).

## Done (2026-07-03) — harness review follow-through

Full review of harness + skills + references + backlog (user-driven). Verdict: sound; the gaps
were the harness's own triggers firing without follow-through. Changes:

- **Ratchet closed on the 2026-06-30 failure** — the `/code-review`-on-pseudocode false-positive
  fix is now installed as a task-cycle step-7 rule: a finding must anchor to a file that ships;
  fenced blocks in `docs/tasks/**` are pseudocode. Chose the reviewer-instruction form over the
  failure-log's path-filter suggestion — an include-list silently drops new paths from review as
  the codebase grows (user call).
- **metrics.md trigger acknowledged and re-aimed** — fired at 5 merged tasks, consciously
  deferred with a new trigger (see Deferred).
- **De-stale sweep** — harness.md known-gaps (failure log is live, no longer an "empty stub");
  environment.md header (001–002 → 001–005); readiness.md boxes that concrete artifacts had
  satisfied; engineering-considerations.md command-surface language (the Makefile exists).
  Structural fix alongside: task-cycle step 10 close-out now re-checks point-in-time claims in
  `docs/agentic-ops/`.
- **Design-phase adversarial review installed** (user-driven): Tier 3+ standard, Tier 2 on
  demand — the other family attacks the drafted contract+plan before the plan 🛑 (task-cycle
  step 3; harness.md § review lane). Fixes an asymmetry: implementation had heterogeneous review,
  the plan had only the human gate — and design is the cheapest place to catch wrong-direction
  work. The lack-of-context objection resolves by design: artifacts must already be
  self-sufficient handoffs (conversation B depends on it), so a review that fails for lack of
  context is itself a finding; settled/ADR'd decisions are scoped as context, not targets, so it
  can't relitigate what the human already decided. First live run: task 006's design phase.
- Noted, no action: CI as required status check is the next earned enforcement candidate
  (user decision pending); AGENTS.md Current phase repoints at task-006 step 1, per design.

## Done (2026-07-02) — Fable 5 rebaseline

- **Agent-side model routing for Fable 5** — `harness.md` § Model assumptions updated (was
  "Opus-class"): Fable 5 effort-`high` lead + a per-call subagent routing table (Opus =
  deep-reasoning offload, Sonnet = mechanical volume, Codex = heterogeneous peer), plus the
  high-stakes rule (two independent takes, lead synthesizes) and escalate-on-quality. One-bullet
  digest in AGENTS.md. Delegate tiers are **pinned agent definitions** —
  `.claude/agents/deep-reasoner.md` (Opus) and `fast-worker.md` (Sonnet) — so the model choice is
  structural (frontmatter + description-driven selection), not a table someone must remember at
  delegation time; the Agent/Workflow `model` param is the per-call override. *(Corrects a
  same-day earlier call that skipped the agent files as "zero files beats two" — that made routing
  advisory-only and left subagent model choice to memory; user called it, 2026-07-02.)* Still
  advisory by design: the **lead** model/effort (user-held, deliberately not pinned in
  `settings.json` — a hard pin breaks on model unavailability and teammate access) and the
  lead-only / don't-delegate rules (protocol in AGENTS.md; no mechanism pins a negative).
- **Review-lane economics + Codex-as-implementer** (2026-07-02, user-driven: lead-model usage was
  spiking in the review phase). Root cause: the step-7 stack (contract-verifier · `/code-review` ·
  `/security-review` · adversarial pass) re-reads the same diff several times on the session model
  — systematic reading, not frontier judgment. Fixes: `contract-verifier` added to
  `.claude/agents/` (pinned Opus, read-only, encodes the step-7 role); harness.md review-lane rule
  — reviewers run pinned/heterogeneous, the lead only adjudicates; review in a fresh conversation;
  `/code-review` effort tiered (`medium` ≤ Tier 2, `high` Tier 3+). Codex promoted from
  debug-rescue-only to an **implementation lane** for precise, machine-verifiable briefs when
  Claude budget is the constraint — guarded by the **family-flip rule** (whichever family
  implements, the other anchors review), which preserves cross-family maker ≠ checker in both
  directions. Prompt-bearing and taste work stay lead-only regardless of lane.
- **Cursor Fable-orchestrator pattern reviewed** (X, 2026-07) — routing already matches (Fable
  plans/judges, cheap workers execute); absorbed the **delegation-brief shape** into harness.md
  (one concern · scoped context · self-checkable done · decision-shaped report · rewrite-and-respawn
  on a miss · don't delegate when judgment is the work) and a one-line Composer mapping for the
  Cursor surface. Model *rotation* noted as practice, not doc: occasionally run a real slice's
  subtask through another frontier model so "what good looks like" stays calibrated by work, not
  benchmarks — the Codex peer lane already does this de facto every review.
- **`fable-mode` skill removed** — legacy stopgap that imposed Fable-like staging discipline on
  Opus while Fable was unavailable; superseded by Fable itself (user call, 2026-07-02).
- **mattpocock/skills evaluated → not adopted** (~154k-star skills collection, active). Core skills
  (`diagnosing-bugs`, `code-review`, `tdd`) are substantive, but nearly everything overlaps
  installed machinery (tdd / code-review / debugging / grill-me ≈ `agent-skills` equivalents +
  task-cycle; `to-prd`/`to-issues`/`triage` ≈ contract/plan; its setup skill wants to own
  issue-tracker config — a second process layer). Same reasoning as the Spec Kit rejection. Its
  installer (`npx skills add mattpocock/skills`) copies skills *individually*, so later adoption
  can be per-skill. Ideas noted, not installed: a project **glossary** concept in `docs/knowledge/`
  (adopt when vocabulary drift first bites); `diagnosing-bugs`' "no red-capable reproduction
  command → no hypothesising" gate (fold into the debug step if debugging discipline slips).
- **jbarbier/CLAUDE.md mined; not adopted** — ~500-line personal operating manual; roughly a third
  is redundant with current Claude Code defaults; confirms the keep-CLAUDE.md-thin stance.
  Absorbed: the **deterministic-work rule** (one AGENTS.md line). Deferred: its two-lane test
  split — *gate tests* (deterministic, free, <2s, every commit) vs *periodic evals* (paid LLM
  calls, before ship + nightly) — adopt when real inference lands behind the routing seam
  (stub-only today; pairs with the eval-readiness persistence property).
- **2026 guidance scan** (Cherny · Karpathy · Ng, verified sources) — the harness already embodies
  the load-bearing recommendations: verification loops as the top lever (`make verify` +
  `verification.md` + review stack), file-based state, subagents to protect lead context, human
  gates scaled by tier (Karpathy's leash-as-autonomy-slider; his verified 2026 line: "LLMs automate
  what you can verify"). Calibration notes: Cherny now frames CLAUDE.md as an **append-only earned
  error ledger** — matches AGENTS.md-as-smell-ledger + `failure-log.md`'s earn-it policy; when a
  failure teaches a rule, the rule lands as one AGENTS.md line. Ng's three-loop cadence (agentic
  minutes / developer hours / external days) → keep `make verify` fast; the human product-decision
  loop is already the 🛑 gates. **Provenance note (corrected 2026-07-02):** the viral 4-rule
  "Karpathy CLAUDE.md" is Forrest Chang's distillation of Karpathy's January-2026 X post, not
  Karpathy's own file; the "ten rules + self-check protocol" expansion is *attributed* to Karpathy
  (who joined Anthropic's pre-training team ~June 2026) but unconfirmed — he hasn't commented.
  Evaluate on merits, not authority — and on merits its six additions are already installed here:
  reproduce-first verification ≈ `agent-skills:test-driven-development`; debugging sequence ≈
  `agent-skills:debugging-and-error-recovery`; dependency discipline ≈ the deps hard gate + the
  ponytail ladder; named failure modes (Kitchen Sink · Wrong Abstraction · Optimistic Path ·
  Runaway Refactor) ≈ ponytail + "touch only what the task requires"; machine-verifiable "done" ≈
  rubric.md. Nothing to import.

## Done (2026-06-24)

- PR template ([.github/pull_request_template.md](../../.github/pull_request_template.md)),
  `harness.md`, `environment.md`, and this backlog created.
- `.claude/settings.json` deny rules for `.env`/secrets + generated artifacts.
- `task-cycle` skill now wires the **already-installed** plugins (`agent-skills`, `codex`, `ponytail`
  — the three the quick-start recommends) into its steps, and adds an explicit **contract-verifier**
  review step with heterogeneous reviewers at Tier 3+.
- **Coherence pass** (external-review-driven): de-staled phase/status language (`spec-authoring`,
  `engineering-considerations`, contract/verification templates); tightened templates to match the
  task-cycle (plan-approval note, exact e2e command, **Review findings** section, rubric review-stack
  + `/okf validate` boxes, PR reviews-run checklist, runtime-egress definition); **declared the
  required plugins in `.claude/settings.json`** (agent-skills/codex/ponytail) so teammates get them on
  opening the repo — no longer just installed in the user env.
- **Knowledge/phase cadence** (review-driven): durable records (`docs/knowledge/`, `deferred.md`) are
  authored **in the implementing PR after the review stack finalises the code** (task-cycle step 8) —
  not at implement (a draft the review then rewrites), not in a stranded post-merge step. The
  contract-verifier now checks `verification.md`/ADR claims against the as-built code (catches
  "documented but not built" — e.g. the task-001 `CompileError` that never existed). `AGENTS.md`
  **Current phase** now *leads* the next slice (step 1), not trails the finishing one (step 10 is now
  "Close out": reconcile + cleanup). Updated `SKILL.md`, `harness.md`, `docs/knowledge/index.md`, and
  the reference manual's workflow lists (§7, §21).

## Resolved

- **OKF lanes** (2026-06-24) — both `docs/specs/` and `docs/knowledge/` are OKF bundles. OKF is a
  navigation format; it does **not** require "verified" (only parseable frontmatter + a non-empty
  `type`). The bundles differ by *editorial policy*, not format:
  - `docs/knowledge/` = verified durable knowledge about the built system + domain. **Open types**
    (OKF fixes no taxonomy); conventions, invariants and pitfalls are just the first ones, seeded
    from task-001. Grow **in the implementing PR** (after review, task-cycle step 8 — see the
    "Knowledge/phase cadence" entry below) — bar is verified · durable · not another lane's job.
  - `docs/specs/` = intent (status-tagged 🟡/❓, not "verified"). Converted additively — frontmatter
    only; bodies, status markers and the conflict-resolution index untouched. `sources/` left as raw
    canonical sources, not concepts.
  Neither dir renamed (the names already carry the intent-vs-verified contrast). Both bundles declare
  `okf_version: "0.1"` and have a `log.md`. *(Corrects an earlier call that specs shouldn't be
  OKF-formatted — that conflated the manual's `knowledge/` editorial policy with OKF's actual minimal
  requirements.)*

- **Specs are living, not golden** (2026-06-24) — the architecture + EB specs (and their `sources/`)
  were reasoned deliberately but fast, before the tool was real. Agents must treat them as current
  best *intent*, refinable as implementation lands: neither blindly obey a doubted spec nor silently
  deviate in code — **flag → human decision → update spec + status + ADR → log**. Recorded in
  [../specs/README](../specs/README), the [task-cycle](../../.claude/skills/task-cycle/SKILL.md)
  (stop condition + a "Refine a spec" tool group: `agent-skills:idea-refine` / `:spec` /
  `:interview-me` / `:api-and-interface-design` / `:doubt-driven-development` → `:documentation-and-adrs`),
  and AGENTS.md. The "source wins" rule is unchanged — it governs *distillation fidelity*, not design finality.

- **Spec Kit not adopted** (2026-06-24) — `.specify/` machinery + the speckit skills were removed; we
  use the bespoke `docs/specs` + `docs/tasks` + task-cycle flow, a **tailored superset** of Spec Kit
  (status markers, OKF bundles, public/private boundary, model route, ADR governance, risk tiering).
  Adopting it now = a second overlapping spec system (YAGNI at one slice in). Its ideas are already
  absorbed (constitution ≈ AGENTS.md; specify/plan/tasks ≈ contract/plan/rubric; clarify ≈
  `agent-skills:interview-me`; analyze ≈ contract-verifier). **Revisit if:** the repo becomes
  multi-tool / Cursor-heavy and contributors need the *workflow* (not just the docs) outside Claude
  Code — overlaps the deferred `skills-source/` split — or the team grows enough that a known external
  standard onboards faster than the bespoke flow.

## Spec governance — resolved ([ADR 0002](../adr/0002-spec-governance.md), 2026-06-24)

`sources/` are **frozen** historical origin; `docs/specs/` + `docs/adr/` are **canonical and living**.
The old "source wins on conflict" rule is retired (it governed distillation fidelity only). Spec
changes flow back via [../specs/README](../specs/README) — this decision is the first ADR'd instance.
Wording in index.md, README, spec-authoring.md and the per-spec intros updated to point at ADR 0002.
Spec refinement is now an explicit part of the [task-cycle](../../.claude/skills/task-cycle/SKILL.md).

## Deferred — earn it first (aligned with the manual's "improve the system only when failure teaches you")

- `failure-log.md` — **live since 2026-06-30** (first entry: `/code-review` pseudocode
  false-positives; its fix installed 2026-07-03). The bar continues per entry: each new failure
  lands one harness change, or is explicitly accepted as a one-off.
- `metrics.md` — **trigger fired at 5 merged tasks (2026-07-03) and consciously deferred**:
  per-slice manual fill adds friction with no current question to answer, and every candidate
  metric (time-to-green, rework rate, review findings/task, diff size) is reconstructible from
  git/GitHub history, so deferring loses nothing. New trigger: the first harness decision that
  actually needs numbers (the likely one: a loop's cost-per-accepted-change judgment) — then
  **backfill by script**, don't hand-fill per slice.
- `loops/` + any automation — only after a workflow has run manually ~3×, is stable, and has a state
  file + checkable rubric + explicit gates + budget (quick-start skill-readiness bar). Never Tier 3/4.
  *(2026-07 note: the "loop engineering" wave — Cherny: "my job is to write loops"; Osmani's five
  components: scheduled automations, worktree isolation, skills, MCP, separate ideation vs
  verification subagents ("the worker does not grade its own homework") — raises the payoff, and
  every component is already installed here. The earn-it bar stands unchanged; the first candidate
  loop is whichever task-cycle phase gets run manually ~3× with a stable shape.)*
  Adoption bar, refined from the loop-engineering roadmap (Deviatkin/0xCodez 14-step, 2026-06 —
  which itself endorses restraint): pass the **4-condition test** first (task repeats ≥ weekly ·
  an automated verifier can reject bad output · budget absorbs retry waste · agent has
  senior-engineer tooling); build in order **manual run reliable → skill → loop → schedule**;
  judge by **cost per accepted change** (accepted-rate < 50% = the loop is losing); hard stops
  (budget/iterations) + human gate before anything irreversible; never on judgment-call work.
  Distinguish from `/goal`: session-scoped goal-conditioned runs against an objective stop
  condition are in-bounds **today** (harness.md § Verification layer) — it's the *scheduling*
  (unattended cadence) that stays behind this bar. Loop-specific risks when the bar is met:
  Ralph-Wiggum early-exit (soft completion tokens — the gate must be a test/build, not an
  opinion), goal drift on long runs (reread the standing spec each cycle), comprehension debt
  (read the diffs; spot-check that the gate still catches what it claims), and the security tax
  (audit community skills before install — measured audits found credential-leaking skills;
  re-audit loop permissions periodically).
- Portable `skills-source/` split — only when Cursor (or another tool) actually needs to *run* a
  skill; today `.cursor/rules/core.mdc` just defers to AGENTS.md.
- Enforcement hooks beyond the deny rules (e.g. a verification-evidence Stop hook) — high
  false-positive; rubric + verification.md + PR template already gate evidence. `/codex:setup`'s
  built-in **stop-time review gate** is the off-the-shelf version — but (verified by reading
  `stop-review-gate-hook.mjs`) it runs a **full Codex review on every `Stop` / turn, with no
  diff/no-op guard**, foreground and blocking (15-min timeout), and can block the turn. So it's for
  **unattended / loop runs**, not interactive dev (≈ one Codex job per exchange). **Keep it off**;
  use `/codex:review` as the explicit review-step call instead.
- CI (GitHub Actions) — deferred with the CI scope. `dev` is now a **protected branch** (PR required,
  force-push/deletion blocked; 2026-06-24); when CI lands, add it as a **required status check**
  running the **same `make verify`** so local and CI stay identical.

## Aligned — no action

- The quick-start's **minimum reliable harness** and the playbook's **minimal repo setup** (§8) are
  now fully met: AGENTS.md, CLAUDE.md, Makefile surface, `docs/specs/`, `docs/adr/`, `docs/deferred.md`,
  PR template, `readiness.md`, thin always-loaded context.
- The contract/rubric/verification templates **exceed** the manual's baseline (they add
  public/private boundary, model route, stop conditions, and the project's slice disciplines).
- The three recommended plugins (Codex, Agent Skills, Ponytail) are installed — no custom
  tdd/debug/migrate/context skills to author; reuse the plugin skills.
