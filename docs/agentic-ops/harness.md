# Harness inventory

What the agentic harness for Policy Atlas actually *is*, as it stands. This is a map of existing
machinery, not a wishlist — add a row when the thing exists, and keep the **Known gaps** section
honest. Rationale and the full menu of options:
[advanced-agentic-engineering-manual.md](references/advanced-agentic-engineering-manual.md).

## Purpose

Let agents do non-trivial implementation slices with evidence and human gates, without
re-deriving the project's intent or boundaries each time.

## Model assumptions

- Primary: Claude Code (Opus-class) in the IDE and CLI.
- Secondary: Cursor (`.cursor/rules/core.mdc` -> "Follow AGENTS.md"). No Cursor-specific skills yet.
- Skills are written tool-agnostic in prose; only `.claude/skills/` is packaged so far.

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
- **OKF bundle is young** — `docs/knowledge/` seeded with four verified concepts (task-001); grow it
  at the after-merge cadence, not speculatively.
- **No CI status checks** (GitHub Actions deferred) — `dev` is protected (PR required,
  force-push/deletion blocked), but no automated check (e.g. `make verify`) gates merges yet; the
  merge gate is human review.
