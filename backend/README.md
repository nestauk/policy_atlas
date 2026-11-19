# Backend

The Python application. It holds the web API, the Capabilities, the database schema and the
tests. The import name is `policy_atlas`. Set it up from the repository root with `make setup`
(see the [root README](../README.md)).

## What is in it

| Path | What it holds |
| --- | --- |
| `src/policy_atlas/api/` | The web API (FastAPI): `contract/` (the request and response models that the OpenAPI document is made from), `routers/`, `read_models/`, and the local sign-in issuer `dev_issuer.py` |
| `src/policy_atlas/runtime/` | The Agent and the Task Agent, the capability runner, planning and steering |
| `src/policy_atlas/evidence_search/` | The Evidence search Capability: `sourcing/`, `assess/`, `corpus/`, `extract/`, `group/`, `synthesis/` |
| `src/policy_atlas/options_scoping/` | The Options scoping Capability |
| `src/policy_atlas/theory_of_change/` | The Theory of change Capability |
| `src/policy_atlas/core/` | Shared parts: the database schema (`schema.py`), the database connection, events, tracing, embeddings and the model clients |
| `src/policy_atlas/ops/` | The operator command line for organisations and users (`python -m policy_atlas.ops`), and the queued ingest worker |
| `src/policy_atlas/model_routes.toml` | The one file that names the AI model for each step, per route |
| `alembic/` | The database migrations (see [alembic/README](alembic/README)) |
| `tests/` | The tests. `tests/data/` holds the fixtures (recorded provider records and full-text documents) |
| `tutorials/` | Notebooks and notes that explain the Evidence search pipeline |
| `Dockerfile` | The container image that the cloud deploy runs (it starts the API) |

## Rules

- A change to the schema, the auth, the dependencies or a public interface needs approval
  ([AGENTS.md](../AGENTS.md)).
- Prompt text is hash-pinned. `make prompt-guard` fails if a prompt changes and
  `scripts/prompt_hashes.json` is not updated.
- A change to `src/policy_atlas/api/contract/` changes the generated frontend files. Run `make openapi-sync`;
  `make drift-check` fails until you do.
- The tests make no network calls. They run against their own database, never the dev database.

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

To run the Evidence search from the command line, without the web app:
`uv run --project backend python -m policy_atlas.runtime.agent`.
