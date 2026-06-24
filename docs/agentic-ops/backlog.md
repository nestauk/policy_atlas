# Agentic-ops backlog

Harness improvements and decisions, per the manual's maintenance cadence. Each deferred item names
its **trigger to act** — don't pre-build, earn it. Baseline audit 2026-06-24 against the four docs in
[references/](references/) (manual, quick-start, AI-native playbook, OKF).

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

- `failure-log.md` — fill on the **first real harness failure**, not before.
- `metrics.md` — start tracking (time-to-green, rework rate, review findings/task, diff size) once
  there are ~5+ merged tasks to measure.
- `loops/` + any automation — only after a workflow has run manually ~3×, is stable, and has a state
  file + checkable rubric + explicit gates + budget (quick-start skill-readiness bar). Never Tier 3/4.
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
