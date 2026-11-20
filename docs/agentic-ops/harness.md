# Harness inventory

What the agentic harness for Policy Atlas is now: the instructions, tools, agents and checks
that let coding agents build the product. This file lists what exists, not what is planned.
Add a row when a thing exists, and keep **Known harness gaps** honest. Background reading (a
general draft, not a rule source):
[advanced-agentic-engineering-manual.md](references/advanced-agentic-engineering-manual.md).

## Purpose

Let agents build non-trivial slices with evidence and human approval gates, without working out
the project's intent or boundaries again each time.

## Model assumptions

- **Lead:** Claude Code in the IDE and the command line, with Claude Fable 5.2 as the lead (the
  session model). The user sets the lead model and its effort with `/model` and `/effort`.
  `.claude/settings.json` does not pin them, because a pin breaks when a model is unavailable or
  a teammate has no access to it.
- **Subagents:** each pinned agent in `.claude/agents/` sets its model in its frontmatter
  (`model`, and `effort` on some). An agent's description may say what it is for and which
  model it uses.
- **Slice size:** slices can be large. The control is evidence and gates (risk tiers,
  `verification.md`, the `make verify` check in CI (continuous integration)), not small slices.
- **Cursor** is a secondary surface. `.cursor/rules/core.mdc` tells it to follow AGENTS.md.
  Only `.claude/skills/` holds packaged skills.
- **Harness review at each change of lead model.** When a lead model arrives or goes away, review
  the harness: which rules are still needed, which skills and hooks no longer earn their cost,
  which model weaknesses have gone, and which new behaviours need a guardrail. Trim rules that
  tell the model how to think before you trim process and gates.

### Agent-side model routing

*Agent-side* means the models that build the product. The product's own model calls (the
*inference route*) are a different thing: they go through
`backend/src/policy_atlas/model_routes.toml` and the runtime-egress gate. Nothing here changes
them.

The lead orchestrates: it plans, splits the work, marks an executor for each plan task, judges
results and synthesizes. The routing is structural: each delegate is a pinned agent definition in
[`.claude/agents/`](../../.claude/agents/), so the model goes with the agent type and nobody has
to remember a table. The Agent tool's `model` parameter overrides it for one call.
**A `general-purpose` subagent starts with `model: "opus"`**, also when the caller is an
Opus agent. The exception is `/code-review`: its reviewers run on the lead's model. The `agent-skills` plugin supplies the named reviewer subagents.

| Work | Route |
|---|---|
| Orchestration, architecture, hard debugging, synthesis, final judgment | The lead |
| Judgment-bearing implementation (nontrivial logic, multi-file coherence, unfamiliar APIs) from a precise brief with a machine-checkable done | **[`deep-reasoner`](../../.claude/agents/deep-reasoner.md), the default doer** (Opus) |
| Deep-reasoning offload: long independent analysis, root-cause hunts, option studies | [`deep-reasoner`](../../.claude/agents/deep-reasoner.md) (Opus) |
| Frontend work under `frontend/`: polish passes, design reviews, builds from a design annex | [`frontend-designer`](../../.claude/agents/frontend-designer.md) (Opus, effort high). It loads the frontend design skills, `PRODUCT.md` and `DESIGN.md` first |
| Mechanical volume: boilerplate, sweeps, scoped edits, broad search | [`fast-worker`](../../.claude/agents/fast-worker.md) (Sonnet); `Explore` agents for search |
| Web research: one narrow, sourced question per agent, notes to a named file | [`researcher`](../../.claude/agents/researcher.md) (Opus, effort medium; web tools and Write only). To widen the search, add researchers, not layers |
| Throwaway artefacts built to measure something: experiment scripts, probes, prototypes in a scratch or gitignored folder | [`builder`](../../.claude/agents/builder.md) (Opus, effort high; code tools, no web) |
| Contract verification at review | [`contract-verifier`](../../.claude/agents/contract-verifier.md) (Opus, effort high, read-only) |
| Other review passes | `agent-skills` reviewer subagents and Codex. The lead adjudicates; it does not write the reviews |
| Heterogeneous peer (a different model family): review, adversarial review, rescue | Codex: `/codex:review`, `/codex:adversarial-review`, `codex:rescue` |

**Routing is decided at plan time.** The plan marks each task with its executor (`lead`,
`deep-reasoner`, `frontend-designer`, `fast-worker`, `builder` or `codex`), and the plan gate
reviews the marks. The decision ladder:

1. You cannot write a self-checkable brief: `lead`.
2. Prompt-bearing work, taste-bearing surfaces, adjudication, and seam *design* (signatures,
   semantics, the brief itself): `lead`. The *implementation* of a seam the lead designed, against
   a machine-checkable done, can be delegated like any other build.
3. Judgment-bearing implementation: `deep-reasoner`. The model family changes at the Codex
   review, so a Codex build adds no independence and costs a slow round-trip. Mark `codex` as the
   doer only when the build itself needs a second family's view, and give the reason in the plan.
   Codex runs in the background, so its done must be self-checkable (`make verify`, named tests).
4. Frontend implementation or polish: `frontend-designer`.
5. Mechanical transcription of an exact spec: `fast-worker`. One-command mechanical edits (a
   `sed` sweep) stay with the lead.
6. Analysis, not code: `deep-reasoner`.

**Review lane economics.** The review stack reads the same diff many times. That reading is
systematic work, so pinned reviewers and Codex do it, and the lead only adjudicates findings and
decides fixes. Review runs in a fresh conversation, because the adjudicator must not be the
author. Rules (the detail is in the `task-cycle-review` skill):

- Exclude generated and bulk data files from the review diff by an exclude pathspec. Data files
  get their own check.
- `/code-review` runs at `medium` at every tier. `high` runs only when the user asks.
- One security lane and one Claude defect pass per diff. `/code-review medium` is the Claude half
  of the heterogeneous pair.
- Give each `/code-review` finder angle a diff pathspec that matches its lens.
- **Family-flip rule:** the family that did not build anchors the review. Claude builds, Codex
  reviews; Codex builds, Claude reviews.
- Delegated test code is where defects collect. Read delegated test diffs closely.
- If the lead model declines a benign security pass, the pinned Opus or Codex reviewers run it.

Codex parallel builds on one working tree are safe only when their file sets do not overlap and
each brief says "never revert files you did not change" and lists the other job's files. Track
Codex jobs with `scripts/codex_job.sh`.

Other rules:

- **High-stakes decisions** (Tier 3 and up, real design forks): two *independent* takes, for
  example a `deep-reasoner` and Codex on the same brief, neither shown the other's answer. The
  lead then synthesizes.
- **Design-phase adversarial review** (standard at Tier 3 and up, on request at Tier 2): before
  the plan gate, the other family attacks the drafted `contract.md` and `plan.md` from the
  committed files alone. Decisions already settled or in an ADR (architecture decision record)
  are context, not targets. A review that fails for lack of context is a finding: the files are
  not a complete handoff. Details: `task-cycle-design` step 3.
- **Escalate on quality, not price.** If a cheaper model's output misses the bar, redo it with a
  stronger model. Do not hand-polish weak output.
- **Prompt-bearing work is lead-only.** The product's prompts, judge rubrics and eval criteria
  are its highest-leverage surface. The lead writes and edits them, even when the code around
  them is delegated.
- **Taste-bearing surfaces** (user-facing copy, interface and API shape) stay with the lead or an
  Opus agent, never the mechanical lane.
- **Delegation briefs:** one concern; the intent (why, and who it is for); enough context that
  the worker does not explore the repository again; a done the worker can check itself; a short
  report shaped for the lead's next decision. Workers carry out the brief; they do not make the
  plan. Run independent briefs in parallel. For related subtasks, continue one subagent instead
  of starting new ones. If a result is wrong, rewrite the brief and start again, unless the fix
  is trivial. If you cannot name the subtasks, do not delegate.

## Context layer

- [AGENTS.md](../../AGENTS.md): the agent protocol, boundaries and landmines.
- [CLAUDE.md](../../CLAUDE.md): a thin Claude adapter that loads AGENTS.md.
- [docs/specs/](../specs/index.md): the *intent* bundle in OKF (Open Knowledge Format):
  status-tagged system and capability specs. Specs and ADRs win over the frozen sources
  ([ADR 0002](../adr/0002-spec-governance.md)). `docs/specs/vocabulary.md` holds the product
  vocabulary. How to write or change a spec: [spec-authoring.md](spec-authoring.md).
- [docs/knowledge/](../knowledge/index.md): the *verified* OKF bundle: durable, checked facts
  about the built system and the domain.
- `PRODUCT.md` (product principles) and `DESIGN.md` (the visual system), read by frontend work.
- `docs/deferred.md`: seams left open on purpose.
- [environment.md](environment.md): local setup and known quirks.
  [readiness.md](readiness.md): what is settled and what is open.
- [failure-log.md](failure-log.md): past harness failures and their lessons.
- `.claude/output-styles/simple.md`: the plain-English writing style.

## Tool layer

- **Command surface:** the root `Makefile`. It calls `backend/Makefile` and `infra/` for their
  parts. Main groups:
  - setup and run: `setup`, `frontend-install`, `dev`, `dev-seed`;
  - checks: `verify`, `verify-fast`, `frontend-verify`, `frontend-verify-fast`, `test`,
    `test-fast`, `typecheck`, `lint`, `build`, `audit`, `fe-api-smoke`;
  - generated files: `openapi-sync`, `drift-check`;
  - evaluations: `eval-check`, `eval-search-recall`;
  - cloud operations: `deploy-*`, `infra-setup`, and the user and organisation targets.
- **Runtime:** uv (Python), pnpm (frontend), Docker Compose (Postgres), alembic (database
  migrations), AWS CDK (infrastructure).
- **Required plugins**, declared in `.claude/settings.json` (`enabledPlugins` and
  `extraKnownMarketplaces`) so that Claude Code offers them to a teammate who opens the repository. Each teammate
  installs them. The
  [task-cycle](../../.claude/skills/task-cycle/SKILL.md) says which phase uses which:
  - `agent-skills`: engineering skills (incremental implementation, test-driven development,
    debugging, interface design, ADRs, security, and more) and the
    `agent-skills:code-reviewer`, `agent-skills:security-auditor` and
    `agent-skills:test-engineer` subagents.
  - `codex`: the heterogeneous (GPT-family) peer: `/codex:review`, `/codex:adversarial-review`,
    `/codex:rescue`, `/codex:setup`, and the job commands `/codex:status`, `/codex:result`,
    `/codex:cancel`.
  - `ponytail`: checks for over-engineering: `/ponytail-review` (a diff) and `/ponytail-audit`
    (the whole repository).
  - `impeccable`, `taste-skill` and `frontend-design`: frontend design skills that the
    `frontend-designer` subagent loads.
  - `langfuse`: query traces, datasets and prompts in Langfuse.
  - `okf`: write and maintain an Open Knowledge Format (OKF) bundle such as `docs/knowledge/`.
- **Project skills** in `.claude/skills/`: the four `task-cycle` skills, and seven design
  skills copied from `emilkowalski/skills` (MIT licence, kept beside each skill), because that
  repository is not a plugin: `emil-design-eng`, `apple-design`, `animate`,
  `review-animations`, `find-animation-opportunities`, `prototype` and `pick-ui-library`.
- **Built-in commands:** `/plan`, `/goal`, `/code-review`, `/security-review`, `/verify`,
  `/simplify`. The
  conformance check for an OKF bundle is `make okf-validate`, a repository script, so it does
  not depend on the `okf` plugin.
- **Local subagents** in `.claude/agents/`: `deep-reasoner`, `fast-worker`, `frontend-designer`,
  `researcher`, `builder`, `contract-verifier` (see the routing table).
- **Permissions:** deny rules in `.claude/settings.json`, and a command allowlist in each user's
  `.claude/settings.local.json`.

## Execution layer

- [task-cycle skill](../../.claude/skills/task-cycle/SKILL.md): the lifecycle of one slice,
  tiered by risk, split into design, build and review phases.
- Per-task files under `docs/tasks/<id>/`: `contract.md`, `rubric.md`, `verification.md` and,
  for frontend slices, `design-annex.md`, from `docs/tasks/_templates/`. `plan.md` has no
  template: copy the shape of the previous slice's plan.
- ADRs at `docs/adr/NNNN-slug.md` for Tier 3 and 4 design decisions.
- `/plan` for read-only planning before non-trivial work.

## Enforcement layer

Some rules are enforced by a tool. The others are guidance that the agent is asked to follow.

Enforced by a tool:

- A **protected `dev` branch** on GitHub: a merge needs a PR, force-push is blocked, deletion is
  restricted.
- **CI** ([.github/workflows/verify.yml](../../.github/workflows/verify.yml)) runs `make verify`
  on every PR. The `verify` job is a required check in the `dev` ruleset.
- Checks inside `make verify`:
  - `drift-check`: generated API files match the backend contract;
  - `prompt-guard`: prompt text matches its pinned hash;
  - `font-guard`: no licensed font files are committed;
  - `audit-paths`: no file uses a backend path as if it were at the repository root;
  - `okf-validate`: both OKF bundles conform.
- `pytest-socket` blocks network calls from the tests.
- `.claude/settings.json` denies reading and writing `.env` files, and direct edits to
  generated and frozen files (`uv.lock`, `dist/`, `frontend/openapi.json`,
  `frontend/src/api/gen/types.ts`, `docs/specs/sources/`).
- A hook in `.claude/settings.json` (a command that Claude Code runs before a tool call)
  refuses `git commit` while the branch is `dev`.

Guidance only: asking for approval before a hard-gate change (schema, auth, runtime egress,
dependencies, CI, production config, public interfaces, scaffold).
The `/codex:setup` stop-time review gate stays off: it runs a full Codex review at the end of
every turn and can block the turn, which suits unattended runs, not interactive work. Run
`/codex:review` as an explicit review step instead.

*Egress* here means *runtime* egress: the deployed product sends project data to search services
or model providers. Agent and developer network use is not gated.

## Verification layer

- **`make verify`, the green bar.** It checks that Postgres is running, then runs, in order:
  - `okf-validate`;
  - the backend: `test` (`pytest -n auto`, one database copy per worker), `typecheck` (mypy),
    `lint` (ruff), `build`;
  - `eval-check` (the evaluation scripts' self-tests and lint);
  - `make -C infra test`;
  - `audit-paths`, `prompt-guard`, `font-guard`, `drift-check`;
  - `frontend-verify` (type check, lint, unit tests, build).
- **`make verify-fast`** covers the backend only: `test-fast` (the backend tests without the
  full-text ingest suite), `typecheck`, `lint`, then `eval-check`.
- **`make frontend-verify-fast`**: frontend type check, lint and unit tests, without the
  production build.
- **Which check gates which commit** (rule in `task-cycle-build` § Step 5):
  - full `make verify` at the build-open baseline, at any phase that touches schema or ingest
    code, and at the step-6 exit;
  - `make verify-fast` for other intermediate commits;
  - `make frontend-verify-fast` (with `make verify-fast`) for frontend polish commits.

  Never commit on a red check. The plan's gate map may merge adjacent low-risk phases into one
  full-verify checkpoint. The contract sets the scope of the live check (default: the changed
  surfaces and one cheap full-chain run).
- **`/goal`**: a goal-conditioned run, only when the stop condition is objective (`make verify`
  green, a named test passing). A separate checker model grades completion, so the maker does not
  grade its own work. One goal per task-cycle phase, never across phases: a goal that spans build
  and review makes the author the adjudicator. Not for judgment phases (contract, plan), which end
  at a human gate.
- **`verification.md`** per task: commands run, the exact end-to-end command, evidence, public
  safety, gaps.
- **`rubric.md`**: the completion checklist. The task is done only if every box holds.
- **Review stack** (detail in the `task-cycle-review` skill): `contract-verifier`, `/code-review`
  at `medium`, one security lane (`agent-skills:security-auditor` at Tier 3 and up,
  `/security-review` below), the Codex adversarial review, a live-trace content review when the
  slice has live runs, a design lane for frontend slices, and `ponytail-review`. Fresh
  conversation; data files excluded from the diff. Cleanup is not a review lane: `/simplify`
  runs at the end of the build (step 5c), so the review reads the simplified code.

## Observability

- **structlog** for all application logging (no `print`, no standard-library logging).
- The append-only **`event_log`** table is the audit record. It is separate from traces and
  metrics.
- **Langfuse** (self-hosted) traces model calls, with user and session ids
  ([ADR 0038](../adr/0038-langfuse-observability-boundaries.md)). The `langfuse` plugin skill
  queries it. The code, not Langfuse, holds the prompts.
- **CloudWatch** holds the cloud logs (configured in `infra/`).

## Known harness gaps

- **Thin enforcement.** The hard-gate approval rule and the runtime-egress gate are guidance only.
  No hook enforces them.
- **No `metrics.md`.** No current harness question needs numbers. The likely metrics
  (time to green, rework rate, review findings per task, diff size) can be rebuilt from git and
  GitHub history by a script when a decision needs them.
- **No scheduled loops.** Automate a workflow only after it has run by hand about three times
  with a stable shape, and it has a state file, a checkable rubric, explicit gates and a budget.
  Never for Tier 3 or 4 work.
- **Repository-wide `/ponytail-audit`.** Run it at milestones, about every five merged slices. The
  per-slice `ponytail-review` is already in the review stack.
- **Docstrings are not checked by a tool** (see [readiness.md](readiness.md) § Open decisions).
- **Grow `docs/knowledge/` in the implementing PR**, after the review stack finishes the code
  (task-cycle step 8), not after merge and not on speculation.
