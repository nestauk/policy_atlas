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
goes on judgment, not typing. Route subagents **per call** with the Agent/Workflow `model` +
`effort` params — no pinned custom agents in `.claude/agents/` (a routing default in a doc beats
two more agent files, and the `agent-skills` subagents already cover the named review roles).

| Work | Route |
|---|---|
| Orchestration, architecture, hard debugging, synthesis, final judgment | Fable 5 (the lead itself) |
| Deep-reasoning offload: long independent analysis, root-cause hunts | Opus subagent (`model: opus`) |
| Mechanical volume: boilerplate, sweeps, broad codebase search | Sonnet subagent (`model: sonnet`); `Explore` agents for search |
| Heterogeneous peer (different model family): native review, adversarial review, rescue/doer | Codex — `/codex:review` · `/codex:adversarial-review` · `codex:rescue` |

- **High-stakes decisions** (Tier 3+, real design forks): two *independent* takes — e.g. an Opus
  subagent and Codex on the same brief, neither shown the other's answer — then the lead
  synthesizes. The review stack's two-heterogeneous-reviewers rule, applied upstream at design time.
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

- **Command surface:** `Makefile` — `setup / test / typecheck / lint / build / verify`.
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
- **Built-in commands:** `/plan`, `/code-review`, `/security-review`, `/verify`, `/simplify`, `/okf`.
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

- `make verify` (test / typecheck / lint / build) — the green bar.
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
- **Empty stub:** `failure-log.md` — earn it on the first real failure, don't pre-fill.
- **No `metrics.md`** — add when there's enough task volume to measure (~5+ merged tasks). Harness
  decisions/deferrals are tracked in [backlog.md](backlog.md).
- **OKF bundle is young** — `docs/knowledge/` seeded from task-001; grow it **in the implementing PR**
  (after the review stack finalises the code, task-cycle step 8), not after merge and not speculatively.
- **No CI status checks** (GitHub Actions deferred) — `dev` is protected (PR required,
  force-push/deletion blocked), but no automated check (e.g. `make verify`) gates merges yet; the
  merge gate is human review.
