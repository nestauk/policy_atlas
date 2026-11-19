# Backend

The Python application. It holds the web API, the Capabilities, the database schema and the
tests. The import name is `policy_atlas`. Set it up from the repository root with `make setup`
(see the [root README](../README.md)).

## What is in it

| Path | What it holds |
| --- | --- |
| `src/policy_atlas/api/` | The web API (FastAPI): `contract/` (the request and response models that the OpenAPI documents are made from), `routers/`, `read_models/`, `settings.py` (every server setting and its environment variable), and the local sign-in issuer `dev_issuer.py` |
| `src/policy_atlas/runtime/` | The Agent and the Task Agent, the capability runner, planning and steering |
| `src/policy_atlas/evidence_search/` | The Evidence search Capability: `sourcing/`, `assess/`, `corpus/`, `extract/`, `group/`, `synthesis/` |
| `src/policy_atlas/options_scoping/` | The Options scoping Capability |
| `src/policy_atlas/theory_of_change/` | The Theory of change Capability |
| `src/policy_atlas/core/` | Shared parts: the database schema (`schema.py`), the database connection, events, tracing, embeddings and the model clients |
| `src/policy_atlas/ops/` | The operator command line (`python -m policy_atlas.ops`) for organisations, people, quotas, sign-up domains, offboarding and the admin and ops roles; it acts only on a cloud environment. Also the self-signup sweep (`sweep.py`), the ops database login update (`db_role.py`) and the queued ingest worker |
| `src/policy_atlas/model_routes.toml` | The one file that names the AI model for each step, per route |
| `alembic/` | The database migrations (see [alembic/README](alembic/README)) |
| `tests/` | The tests. `tests/data/` holds the fixtures (recorded provider records and full-text documents) |
| `tutorials/` | Notebooks and notes that explain the Evidence search pipeline |
| `Dockerfile` | The container image that the cloud deploy runs. The API and the ops service both run it |
| `ops-ui/` | The built ops pages, which the ops service serves. `pnpm build:ops` in `frontend/` makes it. It is not committed |

## Rules

- A change to the schema, the auth, the dependencies or a public interface needs approval
  ([AGENTS.md](../AGENTS.md)).
- Prompt text is hash-pinned. `make prompt-guard` fails if a prompt changes and
  `scripts/prompt_hashes.json` is not updated.
- A change to `src/policy_atlas/api/contract/` changes the generated frontend files. Run `make openapi-sync`;
  `make drift-check` fails until you do.
- The tests make no network calls. They run against their own database, never the dev database.

## Two services from one codebase

The same code and the same container image run two services. The environment variable
`POLICY_ATLAS_SERVICE_ROLE` selects one:

- `api` (the default): the public web API that the web app uses.
- `ops`: the ops service. It serves only the ops pages (from the folder that `OPS_UI_DIR`
  names) and the `/api/v1/ops/*` routes. In the cloud, it connects to the database with its
  own restricted login, `pa_ops`.

Both answer `GET /healthz` (the process runs) and `GET /readyz` (the database answers). The ops service has its own OpenAPI document,
`frontend/openapi-ops.json`. Architecture decision record (ADR)
[0046](../docs/adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md) gives the
design. [ADR 0045](../docs/adr/0045-per-user-run-cap-task-quota-offboarding.md) gives
the limits on each person: `RUNS_PER_USER` (how many runs at the same time) and
`TASK_QUOTA_PER_YEAR` (how many Tasks in 365 days). Administrators have no limit, and an
operator can set other limits for an organisation or a person. `make dev` sets a high task
quota for the local user.

## Commands

Run these from the repository root. Each one calls the target of the same name in
`backend/Makefile`.

```sh
make test         # all tests, on a fresh test database
make test-fast    # all tests except the slow full-text ingest tests
make typecheck    # mypy on src and tests
make lint         # ruff check on src and tests
make build        # builds the Python package
make audit        # looks for known vulnerabilities in the locked packages
make -C backend dev   # the API only, on port 8000 (make dev starts the web app too)
```

To check the ops service and the API together on your machine, build the ops pages
(`pnpm build:ops` in `frontend/`), then run `scripts/ops_e2e_local.sh` with `DATABASE_URL` set to
a test database (a name that ends in `_test`). The script starts both services on ports 8002
and 8003.

To run the Evidence search from the command line, without the web app:
`uv run --project backend python -m policy_atlas.runtime.agent`.
