# Policy Atlas

Policy Atlas is an evidence-led policy-analysis workspace. It is for policy makers and policy
analysts in government and the civil service who must give an answer that they can defend with
evidence. It is not a document generator and not a chatbot.

A **Task** is one use of a **Capability**. A Task makes **Artefacts**, for example a report with
citations and a screened source list. A **Project** is a collection of Tasks. The code has three
Capabilities: Evidence search, Options scoping and Theory of change. The web app shows Options
scoping and Theory of change only when their feature flags are set (see
[environment.md](docs/agentic-ops/environment.md)).

The product intent is in [docs/specs/](docs/specs/index.md). The product words are defined in
[vocabulary.md](docs/specs/vocabulary.md). The users and the product principles are in
[PRODUCT.md](PRODUCT.md). The visual design system is in [DESIGN.md](DESIGN.md).

## What is in the repository

| Folder | What it holds |
| --- | --- |
| [backend/](backend/README.md) | The Python application: the web API, the Capabilities, the database schema and migrations, and the tests |
| [frontend/](frontend/README.md) | The web app (React, TypeScript, Vite and Tailwind CSS) |
| [infra/](infra/README.md) | The Amazon Web Services (AWS) infrastructure, written with the AWS Cloud Development Kit (CDK) |
| `scripts/` | Repository checks, deploy scripts, operations scripts, and the evaluation scripts under `scripts/evals/` |
| `docs/` | Specs, architecture decision records (ADRs) in `docs/adr/`, task records in `docs/tasks/`, the verified-facts bundle in `docs/knowledge/`, and the agent process docs in `docs/agentic-ops/` |
| `output/` | Exported infrastructure diagrams |
| `.claude/` | Claude Code settings, project skills and pinned subagents |

## Set up and run locally

You need:

- [uv](https://docs.astral.sh/uv/) (the Python package manager) and Python 3.12 or later;
- Docker (it runs the local Postgres database);
- Node.js 20 or later, and pnpm (the frontend package manager). Install pnpm as a standalone
  tool. `frontend/package.json` pins its version in the `packageManager` field.

Run these commands from the repository root, in this order:

```sh
cp backend/.env.example backend/.env   # local settings; the defaults work for local use
make setup                             # starts Postgres, makes the test database, installs the
                                       # Python packages and migrates the dev database
make frontend-install                  # installs the frontend packages from the lockfile
make dev                               # API on http://localhost:8000, web app on http://localhost:5173
make dev-seed                          # optional: adds a sample organisation and two more users
```

`make dev` signs you in as a local user. You do not need a password. With no model key in
`backend/.env`, the API uses stub (fake) model and search backends, so a run costs nothing. To
use real models and real search, set the keys that `backend/.env.example` describes.

[environment.md](docs/agentic-ops/environment.md) has the details: every environment variable,
what to do after you pull a change, the test databases, and the known problems (for example,
how to run in a git worktree).

## Run the checks

| Command | What it runs | When to use it |
| --- | --- | --- |
| `make verify` | The full check: the knowledge-bundle format check, the backend tests, type check, lint and build, the evaluation-script checks, the infrastructure tests, the path audit, the prompt-hash guard, the font guard, the generated-API drift check, and the frontend type check, lint, unit tests and build | Before you open a pull request. Continuous integration (CI) runs it on every pull request |
| `make verify-fast` | The backend tests without the slow full-text ingest tests, the backend type check and lint, and the evaluation-script checks | For a commit between steps of backend work |
| `make frontend-verify-fast` | The frontend type check, lint and unit tests, without the production build | For a commit of frontend-only work |

`make verify` and `make verify-fast` need the Postgres database from `make setup`. The browser
tests run on their own: `make fe-api-smoke` (the built web app against the real local API) and
`cd frontend && pnpm e2e` (the web app against mock data). The [Makefile](Makefile) lists every
target.

## How the work is organised

[AGENTS.md](AGENTS.md) holds the rules for people and coding agents. Each piece of engineering
work is a task with its records in `docs/tasks/<task-id>/`. The task-cycle skills in
`.claude/skills/` (start at [task-cycle](.claude/skills/task-cycle/SKILL.md)) give the steps
from contract to merge. [docs/agentic-ops/](docs/agentic-ops/harness.md) describes the agent
setup, the local environment and the known failures. The Claude Code plugins that the skills
use are declared in `.claude/settings.json` (`enabledPlugins` and `extraKnownMarketplaces`).
Each contributor installs them in their own Claude Code.

## Licence

GNU Affero General Public License v3.0 only (AGPL-3.0-only). See [LICENSE](LICENSE).
