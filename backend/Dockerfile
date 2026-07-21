# syntax=docker/dockerfile:1

# Ported from v2's two-stage uv image. v3's locked production dependencies
# have Linux wheels, so no compiler or OpenMP runtime packages are required.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Cache locked production dependencies separately from application source.
RUN uv sync --no-dev --no-install-project --frozen

COPY . .

# Install the src-layout project itself into the virtual environment.
RUN uv sync --no-dev --frozen


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
