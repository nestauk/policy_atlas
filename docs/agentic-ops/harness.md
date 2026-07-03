# Harness inventory

What the agentic harness for Policy Atlas actually *is*, as it stands. This is a map of existing
machinery, not a wishlist — add a row when the thing exists, and keep the **Known gaps** section
honest. Rationale and the full menu of options:
[advanced-agentic-engineering-manual.md](references/advanced-agentic-engineering-manual.md).

## Purpose

Let agents do non-trivial implementation slices with evidence and human gates, without
re-deriving the project's intent or boundaries each time.

## Model assumptions

- Primary: Claude Code in the IDE and CLI — **Fable 5, effort `high`**, as the lead. `high` is the
  default on purpose: `max` burns budget for little gain on routine work; raise effort per
  subagent-call for the hardest verify/judge steps instead of globally.
- Secondary: Cursor (`.cursor/rules/core.mdc` -> "Follow AGENTS.md"). No Cursor-specific skills yet.
- Skills are written tool-agnostic in prose; only `.claude/skills/` is packaged so far.

### Agent-side model routing

*Agent-side* means the models doing the development. Distinct from the product's **inference
route** ([engineering-considerations.md](engineering-considerations.md)) — that stays behind the
routing seam and its runtime-egress gate; nothing here touches it.

The lead plans, decomposes, judges and synthesizes; volume work is delegated so the lead's budget
goes on judgment, not typing. The routing is **structural, not advisory**: the delegate tiers are
pinned agent definitions in [`.claude/agents/`](../../.claude/agents/) (model in frontmatter,
description-driven selection), so the model choice rides with the agent type instead of relying on
whoever delegates to remember a table. The Agent/Workflow `model` + `effort` params remain the
per-call override; the `agent-skills` subagents cover the named review roles. The two knobs this
does **not** control: the *lead* model/effort (user-held — `/model` / `/effort`; deliberately not
pinned in `settings.json`, since a hard pin breaks on model unavailability and teammate access),
and the lead-only rules below (you can't pin a "don't delegate" — those stay protocol, in AGENTS.md).

| Work | Route |
|---|---|
| Orchestration, architecture, hard debugging, synthesis, final judgment | Fable 5 (the lead itself) |
| Deep-reasoning offload: long independent analysis, root-cause hunts | [`deep-reasoner`](../../.claude/agents/deep-reasoner.md) (pinned Opus) |
| Mechanical volume: boilerplate, sweeps, broad codebase search | [`fast-worker`](../../.claude/agents/fast-worker.md) (pinned Sonnet); `Explore` agents for search |
| Scoped implementation from a precise brief, when Claude budget is the constraint | Codex as doer (`codex:rescue` / `codex exec`) — then the **other family reviews** (see below) |
| Review fan-out: contract verification, adversarial passes | [`contract-verifier`](../../.claude/agents/contract-verifier.md) (pinned Opus) · `agent-skills` reviewer subagents · Codex — **not the lead**; the lead adjudicates findings |
| Heterogeneous peer (different model family): native review, adversarial review, rescue/doer | Codex — `/codex:review` · `/codex:adversarial-review` · `codex:rescue` |

**Review lane economics.** The review stack is where lead-model usage spikes: each pass re-reads
the same diff, and that reading is systematic work, not frontier judgment. So: reviewers run on
pinned Opus (`contract-verifier`), plugin reviewer subagents, and Codex — the lead's job in step 7
is to *adjudicate* findings and decide fixes, not to generate the reviews. Run review in a fresh,
short conversation (task-cycle context strategy) so the diff is the only context being re-paid;
pass an effort level to `/code-review` (`medium` at Tier ≤2 — fewer, high-confidence findings;
`high` at Tier 3+). **Family-flip rule:** whichever family implemented, the other family anchors
review — Claude implements → Codex reviews; Codex implements → Claude reviews. Maker ≠ checker
holds across model families in both directions.

- **High-stakes decisions** (Tier 3+, real design forks): two *independent* takes — e.g. an Opus
  subagent and Codex on the same brief, neither shown the other's answer — then the lead
  synthesizes. The review stack's two-heterogeneous-reviewers rule, applied upstream at design time.
- **Design-phase adversarial review** (Tier 3+ standard; Tier 2 on demand): before the plan 🛑, the
  other family attacks the drafted `contract.md` + `plan.md` from the committed artifacts alone —
  settled/ADR'd decisions are context, not targets. Complements the rule above: that generates
  alternatives *before* the design call; this attacks the chosen plan *after* drafting. A review
  that fails for lack of context is itself a finding — the artifacts aren't a self-sufficient
  handoff. Details: task-cycle step 3.
- **Escalate on quality, not price.** If a cheaper model's output misses the bar, redo it with a
  smarter one — don't hand-polish weak output. For anything that ships: capability first, cost as
  tie-breaker.
- **Prompt-bearing work is lead-only.** Policy Atlas is an AI tool: the product's prompts, judge
  rubrics and eval criteria are its highest-leverage surface (the contract template already flags
  prompt-bearing changes; [engineering-considerations.md](engineering-considerations.md) requires
  strongest-model review for prompt changes). Authoring or editing them is done by the most
  intelligent model available — the lead itself, never delegated down, even when the surrounding
  implementation is.
- Taste-bearing surfaces (user-facing copy, interface/API shape) stay with the lead or Opus, never
  the mechanical lane.
- **Delegation briefs** (any surface): one concern; enough context that the worker doesn't
  re-explore the repo; a definition of done the worker can check itself; a short report shaped for
  the orchestrator's next decision. Workers execute the brief — they don't invent the plan; run
  independent briefs in parallel. If a result is off, rewrite the brief and re-spawn rather than
  silently patching over it (unless trivial). If you can't name the subtasks, don't delegate —
  when judgment *is* the work (a hard design call, a bug needing one coherent thread), stay one agent.
- On the Cursor surface (secondary), the same split holds: Fable plans, coordinates and judges;
  Composer-class workers execute the scoped subtasks.

## Context layer

- [AGENTS.md](../../AGENTS.md) — non-discoverable operational truth + boundaries (the smell ledger).
- [CLAUDE.md](../../CLAUDE.md) — thin Claude adapter; points to AGENTS.md and the slash commands.
- [docs/specs/](../specs/index.md) — OKF *intent* bundle: distilled, status-tagged system + capability
  specs + conflict-resolution index. Source wins on conflict.
- [engineering-considerations.md](engineering-considerations.md) — non-binding stack direction +
  approval gates. [readiness.md](readiness.md) — pre-implementation gate checklist.
- [docs/knowledge/](../knowledge/index.md) — OKF *verified* bundle: durable verified knowledge about
  the built system + domain (open types; conventions, invariants, pitfalls so far).
- `docs/deferred.md` — registered seams left open on purpose.

## Tool layer

- **Command surface:** `Makefile` — `setup / test / typecheck / lint / build / verify /
  okf-validate` (okf-validate runs inside verify: OKF bundle conformance via
  `scripts/okf_validate.py`, stdlib-only).
- **Runtime:** uv (Python), Docker Compose (Postgres), alembic (migrations).
- **Required plugins** — declared in `.claude/settings.json` (`enabledPlugins` + `extraKnownMarketplaces`)
  so a teammate opening the repo gets them; core to the workflow, not optional. The
  [task-cycle](../../.claude/skills/task-cycle/SKILL.md) says which phase uses what:
  - `agent-skills` — senior-engineer skills (incremental-implementation, test/TDD, debugging,
    source-driven-development, api-and-interface-design, documentation-and-adrs, security-and-hardening,
    doubt-driven-development, …) + the `agent-skills:code-reviewer` / `agent-skills:security-auditor` /
    `agent-skills:test-engineer` subagents.
  - `codex` — heterogeneous (GPT-family) review/rescue: `/codex:review`, `/codex:adversarial-review`,
    `/codex:rescue`; job lifecycle `/codex:status` · `/codex:result` · `/codex:cancel`; `/codex:setup`
    (readiness + an optional **stop-time review gate**).
  - `ponytail` — anti-over-engineering: `ponytail` mode, `/ponytail-review` (diff), `/ponytail-audit` (repo).
- **Built-in commands:** `/plan`, `/goal` (see Verification layer), `/code-review`,
  `/security-review`, `/verify`, `/simplify`. The `/okf` skill is **user-env** (authoring/nav
  aid) — the conformance *gate* is `make okf-validate`, a repo script, so it doesn't depend on a
  personal skill being installed.
- **Local subagents:** `.claude/agents/` — `deep-reasoner` (pinned Opus) · `fast-worker` (pinned
  Sonnet) · `contract-verifier` (pinned Opus, read-only). The structural half of § Agent-side
  model routing.
- **Permissions:** `.claude/settings.json` deny rules + `.claude/settings.local.json` allowlist.

## Execution layer

- [task-cycle skill](../../.claude/skills/task-cycle/SKILL.md) — the per-slice lifecycle, tiered.
- Per-task artifacts under `docs/tasks/<id>/`: `contract.md`, `rubric.md`, `verification.md`,
  `plan.md`, from `docs/tasks/_templates/`.
- ADRs at `docs/adr/NNNN-slug.md` for Tier-3/4 design decisions.
- `/plan` for read-only planning before non-trivial work.

## Enforcement layer

**Mostly advisory.** Most boundaries in AGENTS.md (no hand-editing generated files, hard gates need
approval) are guidance the agent is asked to follow — with **no hooks and no CI status checks**
behind them. The hard mechanisms: a **protected `dev` branch** on GitHub (PR required to merge,
force-push blocked, deletion restricted); `.claude/settings.json` **denies** reading/writing
`.env`/secrets and editing generated artifacts (`uv.lock`, `dist/`); `settings.local.json` holds the
command allowlist. Note **egress here means *runtime* egress** — the deployed product reaching
search backends or model providers with project data (a per-slice approval gate, see
[engineering-considerations.md](engineering-considerations.md)); agent/dev-time network use is not
gated. See Known gaps.

## Verification layer

- `make verify` (okf-validate / test / typecheck / lint / build) — the green bar.
- `/goal` — goal-conditioned runs for the **implement ↔ verify inner loop only**, and only when the
  stop condition is objective (`make verify` green, a named test passing — CLAUDE.md's "only when
  completion is measurable"). Its independent checker model grades completion, so the maker doesn't
  grade its own homework. Session-scoped, attended; **not** for judgment-call phases
  (contract/plan/review — those end at a 🛑), and scheduling/unattended runs stay behind the
  `loops/` earn-it bar ([backlog.md](backlog.md)).
- `verification.md` per task — commands run, exact end-to-end command, evidence, public-safety, gaps.
- `rubric.md` — completion checklist; done only if every box holds.
- Review stack: `/code-review` + `/security-review` (every PR) -> adversarial subagent review
  (`security-auditor` at Tier 3+) -> `/simplify`.

## Observability

- **structlog** mandated from the first slice (no print / stdlib logging).
- Canonical, append-only `event_log` table = the audit plane, separate from execution telemetry.
- Langfuse (trace backbone + prompt registry) and CloudWatch — **deferred**, direction only.

## Known harness gaps

- **Thin enforcement.** `.env`/secrets and generated artifacts are now denied via
  `.claude/settings.json`; everything else (no unapproved hard-gate change, the runtime-egress gate)
  is still doc-only — no PreToolUse/Stop hooks. (`dev` is now a protected branch — PR required,
  force-push/deletion blocked — but no CI status check gates merges yet.)
- **No `metrics.md`** — the ~5-merged-tasks trigger fired 2026-07 and was consciously deferred:
  no current harness question needs numbers, and the candidate metrics are reconstructible from
  git/GitHub history (backfill by script when one does — see [backlog.md](backlog.md)). Harness
  decisions/deferrals are tracked in [backlog.md](backlog.md).
- **OKF bundle is young** — `docs/knowledge/` seeded from task-001; grow it **in the implementing PR**
  (after the review stack finalises the code, task-cycle step 8), not after merge and not speculatively.
- **No CI status checks** (GitHub Actions deferred) — `dev` is protected (PR required,
  force-push/deletion blocked), but no automated check (e.g. `make verify`) gates merges yet; the
  merge gate is human review.
