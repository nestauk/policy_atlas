# A.1 — Monorepo hoist map (lead-designed brief for A.2)

Import-neutral hoist (contract strand 1): the `policy_atlas` package name and
all intra-package imports are unchanged; only tooling paths move.

## Moves (`git mv`, history-preserving)

| From (root) | To |
|---|---|
| `pyproject.toml` | `backend/pyproject.toml` |
| `uv.lock` | `backend/uv.lock` |
| `src/` | `backend/src/` |
| `tests/` | `backend/tests/` |
| `alembic/` | `backend/alembic/` |
| `alembic.ini` | `backend/alembic.ini` |
| `.env.example` | `backend/.env.example` |

Rationale for `.env.example`: `load_dotenv()` (alembic/env.py, package config)
resolves from the working directory; all backend commands now run with
CWD=`backend/`, so `.env` lives there. CI copies `backend/.env.example` →
`backend/.env`.

## Stays at root

- `docs/` (shared), `scripts/` (repo-level: `okf_validate.py` computes repo
  root from its own location and validates `docs/`; `codex_job.sh` is agent
  tooling; the fixture recorders run as
  `uv run --project backend python scripts/record_*.py` — update the comment
  headers in those scripts and `.env.example` accordingly),
- `docker-compose.yml` (shared db service; root Makefile owns it),
- `README.md`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`, `.github/`, `.gitignore`,
  `.cursor/`, `.claude/`.

## New

- `frontend/README.md` placeholder (one line: scaffold lands in phase F —
  keeps the dir tracked without a .gitkeep that F.0 would delete).
- `infra/.gitkeep`.
- `backend/Makefile` (the Python targets, below).
- Root `Makefile` becomes the orchestrator (below).
- `scripts/audit_paths.py` — the path audit (below).

## Makefile split

`backend/Makefile` keeps, verbatim semantics, CWD=backend:
`setup` (uv sync + alembic upgrade head — **no docker compose here**; DB is
root's job), `test`, `test-fast`, `typecheck`, `lint`, `build`, `audit`,
`verify` (db pre-check via `docker compose exec` — compose v2 resolves the
root compose file from the parent dir; if it does not on this machine, use
`docker compose -f ../docker-compose.yml`), `verify-fast`.
TEST_DATABASE_URL default unchanged.

Root `Makefile` (orchestrator — every existing target name keeps working
from root):

```make
setup:        docker compose up -d db + healthwait + test-db create + $(MAKE) -C backend setup
test:         $(MAKE) -C backend test          # likewise test-fast/typecheck/lint/build/audit
okf-validate: uv run --project backend python scripts/okf_validate.py
verify:       db pre-check → okf-validate → $(MAKE) -C backend verify-core → audit-paths
verify-fast:  $(MAKE) -C backend verify-fast
audit-paths:  uv run --project backend python scripts/audit_paths.py
```

(Exact split of db pre-check duplication is the executor's call; the binding
rule is: `make setup && make verify` from a fresh clone root must behave
exactly as today. Frontend lanes are added to root verify in phases F–H, not
now.)

## CI (`.github/workflows/verify.yml`)

- `cp backend/.env.example backend/.env` (path updated).
- `make setup` / `make verify` unchanged (root orchestrator).
- audit job: `make audit` → delegates to backend.
- Add `working-directory` nothing — root make targets cover it.

## Path audit script (`scripts/audit_paths.py`, stdlib-only, same style as okf_validate.py)

Fails (exit 1, listing violations) when a **tracked** file references a moved
path as repo-root-relative. Patterns (regex, line-scoped):
`(^|[\s"'(\[=])(src/policy_atlas|tests/|alembic/|alembic\.ini|pyproject\.toml|uv\.lock|\.env\.example)`
in file kinds: `Makefile`, `*.yml`, `*.yaml`, `*.toml`, `*.md`, `*.py`,
`*.sh`, `*.ini`.

Allowlist (path prefixes, point-in-time records that must NOT be rewritten):
- `docs/tasks/` (all task archives incl. 025's own docs)
- `docs/agentic-ops/failure-log.md`, `docs/agentic-ops/references/`
- `docs/knowledge/` entries dated pre-025 — allowlist the whole dir; new
  knowledge is written post-hoist anyway
- `backend/` itself (paths are root-relative *to backend* there — correct)
- `scripts/audit_paths.py` (self)
- `.claude/` (session tooling)

Living docs that MUST be swept and updated (not allowlisted): `README.md`,
`AGENTS.md`, `docs/specs/**`, `docs/deferred.md`, `.github/**`,
root `Makefile`, `docker-compose.yml` comments.

## Acceptance (A.3)

- `python scripts/audit_paths.py` green.
- Full `make verify` green from root (scaffold gate).
- `git log --follow backend/src/policy_atlas/core/schema.py` shows pre-hoist
  history (mv, not delete+add).
