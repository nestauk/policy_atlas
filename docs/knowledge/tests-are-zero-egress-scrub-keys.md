---
type: Testing rule
title: The suite is zero-egress by policy — scrub product-egress keys after loading .env
description: Every live/stub backend switch keys off environment variables, so a developer's keyed backend/.env must never reach the pytest process unscrubbed. conftest scrubs after load_dotenv(); alembic/env.py reads DATABASE_URL side-effect-free via dotenv_values() so its own load_dotenv() doesn't re-poison every migration fixture; API settings stay pure os.environ.
tags: [testing, zero-egress, dotenv, socket-deny, review-lesson]
timestamp: 2026-07-21
---

# Rule

The suite is zero-egress by policy (socket-deny), and every live/stub backend
switch (`PA_BACKEND_MODE`, `deps.py::_live()`) keys off environment-variable
presence — so a developer's keyed `backend/.env` must never reach the pytest
process unscrubbed. Three coordinated pieces enforce this:

- `tests/conftest.py` calls `load_dotenv()` (needed for `DATABASE_URL` and
  similar) and then **explicitly pops** the product-egress keys
  (`OPENAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_HOST`, `LANGFUSE_BASE_URL`, `OVERTON_API_KEY`, `OPENALEX_API_KEY`)
  from `os.environ` right after.
- `alembic/env.py::_get_url()` reads `DATABASE_URL` via **side-effect-free**
  `dotenv_values()` — never `load_dotenv()` — specifically because its own
  `load_dotenv()` would re-inject the whole `.env` file (including the keys
  conftest just scrubbed) into `os.environ` on **every** migration-running
  fixture.
- API `deps.py`'s `_live()` and settings loading stay pure `os.environ` reads
  with no dotenv call of their own; `make -C backend dev` owns real `.env`
  loading via `uv run --env-file` for the actual server process. Backend mode
  is explicit via `PA_BACKEND_MODE` (`stub` / `live` / `auto`), and `live` fails
  loud (`RuntimeError`) without `OPENAI_API_KEY`.

# Why

The 025 live check found a keyed `backend/.env` silently drove a CLI pin test
(`orchestrate.main`) into the real OpenAI branch under socket-deny — the
developer's own live keys reached pytest via alembic's redundant
`load_dotenv()`, even with conftest's scrub already in place. The suite is now
green with real keys present in `backend/.env`, which is the exact state every
keyed developer machine has.

# Watch out

Any new module that reads config from the environment **and also** calls
`load_dotenv()` / re-loads the `.env` file reopens this leak path. The
sequencing that matters is: load-and-scrub happens exactly once, in conftest;
every other module either reads pure `os.environ` or uses the side-effect-free
`dotenv_values()` accessor.

# Citations

- `backend/tests/conftest.py`
- `backend/alembic/env.py` (`_get_url`)
- `backend/src/policy_atlas/api/deps.py` (`_live`)
