#!/usr/bin/env bash
# Run the built frontend against a local, real Policy Atlas API in stub mode.
# It is intentionally self-contained so local and CI execution exercise the
# same compose database, dev-issuer, CORS/base-URL build, and browser transport.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_port="${FE_API_SMOKE_API_PORT:-8001}"
frontend_port="${FE_API_SMOKE_FRONTEND_PORT:-4174}"
# Own disposable database, never policy_atlas_test: the smoke persists real
# projects/runs, and the backend suite's migration round-trip tests downgrade
# with existing data present — shared state broke them (build finding,
# 2026-07-21). Recreated on every run; dropped on teardown.
smoke_db_name="${FE_API_SMOKE_DB_NAME:-policy_atlas_smoke}"
test_database_url="${FE_API_SMOKE_DATABASE_URL:-postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/${smoke_db_name}}"
api_url="http://localhost:${api_port}"
frontend_url="http://127.0.0.1:${frontend_port}"
issuer_dir="$(mktemp -d "${TMPDIR:-/tmp}/policy-atlas-fe-api-smoke.XXXXXX")"
api_log="$(mktemp "${TMPDIR:-/tmp}/policy-atlas-fe-api-smoke-api.XXXXXX.log")"
frontend_log="$(mktemp "${TMPDIR:-/tmp}/policy-atlas-fe-api-smoke-frontend.XXXXXX.log")"
api_pid=""
frontend_pid=""

cleanup() {
  local status=$?
  trap - EXIT
  for pid in "$frontend_pid" "$api_pid"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  if [[ $status -ne 0 ]]; then
    echo "fe-api-smoke: API log follows:" >&2
    sed 's/^/[api] /' "$api_log" >&2 || true
    echo "fe-api-smoke: frontend log follows:" >&2
    sed 's/^/[frontend] /' "$frontend_log" >&2 || true
  fi
  rm -rf "$issuer_dir"
  rm -f "$api_log" "$frontend_log"
  docker compose exec -T db dropdb --if-exists -U policy_atlas "$smoke_db_name" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT

wait_for_http() {
  local url=$1
  local label=$2
  local attempts=${3:-60}
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: ${label} did not become ready within ${attempts}s (${url})" >&2
  return 1
}

cd "$repo_root"

echo "fe-api-smoke: ensuring compose Postgres is ready"
docker compose up -d db
for ((attempt = 1; attempt <= 60; attempt++)); do
  if docker compose exec db pg_isready -U policy_atlas -q; then
    break
  fi
  if [[ $attempt -eq 60 ]]; then
    echo "ERROR: compose Postgres did not become ready within 60s" >&2
    exit 1
  fi
  sleep 1
done
docker compose exec -T db dropdb --if-exists -U policy_atlas "$smoke_db_name"
docker compose exec -T db createdb -U policy_atlas "$smoke_db_name"

echo "fe-api-smoke: applying migrations to the smoke database"
(
  cd backend
  DATABASE_URL="$test_database_url" uv run alembic upgrade head
)

echo "fe-api-smoke: creating throwaway dev issuer"
(
  cd backend
  uv run python -m policy_atlas.api.dev_issuer init --dir "$issuer_dir"
)
dev_token="$(
  cd backend
  uv run python -m policy_atlas.api.dev_issuer mint \
    --dir "$issuer_dir" \
    --sub "fe-api-smoke-${RANDOM}-${RANDOM}" \
    --client-id policy-atlas-dev \
    --ttl 600
)"

echo "fe-api-smoke: starting API at ${api_url}"
(
  cd backend
  OIDC_ISSUER=http://dev-issuer.local \
  OIDC_CLIENT_ID=policy-atlas-dev \
  OIDC_JWKS_PATH="$issuer_dir/jwks.json" \
  OIDC_JWKS_URL= \
  APP_ORIGIN="$frontend_url" \
  DATABASE_URL="$test_database_url" \
  PA_BACKEND_MODE=stub \
  uv run uvicorn policy_atlas.api.app:create_app --factory --host 127.0.0.1 --port "$api_port"
) >"$api_log" 2>&1 &
api_pid=$!
wait_for_http "${api_url}/healthz" "API"

echo "fe-api-smoke: building frontend with real API base URL"
(
  cd frontend
  env \
    -u VITE_MOCK \
    -u VITE_OIDC_AUTHORITY \
    -u VITE_OIDC_CLIENT_ID \
    -u VITE_OIDC_REDIRECT_URI \
    VITE_API_BASE_URL="$api_url" \
    VITE_DEV_TOKEN="$dev_token" \
    pnpm build
)

echo "fe-api-smoke: serving built frontend at ${frontend_url}"
(
  cd frontend
  pnpm vite preview --host 127.0.0.1 --port "$frontend_port" --strictPort
) >"$frontend_log" 2>&1 &
frontend_pid=$!
wait_for_http "$frontend_url" "built frontend"

echo "fe-api-smoke: running isolated Playwright spec"
(
  cd frontend
  FE_API_SMOKE_FRONTEND_URL="$frontend_url" \
    pnpm exec playwright test --config playwright.fe-api-smoke.config.ts
)
echo "fe-api-smoke: PASS"
