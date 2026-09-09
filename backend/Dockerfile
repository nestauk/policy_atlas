# syntax=docker/dockerfile:1

# Ported from v2's two-stage uv image. v3's locked production dependencies
# have Linux wheels, so no compiler or OpenMP runtime packages are required.
FROM python:3.12-slim AS builder

# Pinned minor (review finding, 026 step 7): :latest is a moving tag straight
# into the production image build.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Cache locked production dependencies separately from application source.
# `--no-group ops` (task 033, approved Dockerfile change): the operator CLI's
# boto3/botocore are a DEFAULT group (pyproject `[tool.uv] default-groups`) so
# tests, mypy and pip-audit reach them — the image opts out. `--no-dev` drops only
# `dev`, so this flag is load-bearing, and it must appear on BOTH sync
# invocations: the second one re-resolves the environment and would reinstate the
# group, shipping boto3 while the declaration says otherwise.
RUN uv sync --no-dev --no-group ops --no-install-project --frozen

COPY . .

# Install the src-layout project itself into the virtual environment.
RUN uv sync --no-dev --no-group ops --frozen


FROM python:3.12-slim

RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /app app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv ./.venv
COPY --from=builder --chown=app:app /app/src ./src
COPY --from=builder --chown=app:app /app/alembic ./alembic
COPY --from=builder --chown=app:app /app/alembic.ini ./alembic.ini

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

USER app

CMD ["uvicorn", "policy_atlas.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
