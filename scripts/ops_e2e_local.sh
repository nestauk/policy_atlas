#!/usr/bin/env bash
# Local end-to-end check of the ops service (task 065, step 6): a real ops-mode
# server serving the built pages and the ops routes, a real api-mode server,
# one database. Needs the compose Postgres and a built backend/ops-ui/.
#   DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_e2e_test bash scripts/ops_e2e_local.sh
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
db="${DATABASE_URL:?set DATABASE_URL to a *_test database}"
issuer_dir="$(mktemp -d "${TMPDIR:-/tmp}/pa-ops-e2e.XXXXXX")"
ops_log="$(mktemp)"; api_log="$(mktemp)"
cleanup() {
  kill "${ops_pid:-}" "${api_pid:-}" 2>/dev/null || true
  rm -rf "$issuer_dir" "$ops_log" "$api_log"
  (cd "$repo/backend" && uv run python - "$db" <<'PY' >/dev/null 2>&1 || true
import sys; from sqlalchemy import create_engine, text
with create_engine(sys.argv[1]).connect().execution_options(isolation_level="AUTOCOMMIT") as c:
    c.execute(text("ALTER ROLE pa_ops NOLOGIN"))
PY
  )
}
trap cleanup EXIT
cd "$repo/backend"
uv run alembic upgrade head >/dev/null
# The ops server runs as the least-privilege login, the way the deployed one does
# (review stack, 2026-11-17): the master login sets LOGIN and a throwaway password.
ops_db="$(uv run python - "$db" <<'PY'
import sys; from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from psycopg import sql
master = make_url(sys.argv[1])
with create_engine(master).connect().execution_options(isolation_level="AUTOCOMMIT") as c:
    c.connection.driver_connection.execute(sql.SQL("ALTER ROLE pa_ops LOGIN PASSWORD {}").format(sql.Literal("e2e-only")))
print(URL.create(master.drivername, "pa_ops", "e2e-only", master.host, master.port, master.database).render_as_string(hide_password=False))
PY
)"
uv run python -m policy_atlas.api.dev_issuer init --dir "$issuer_dir" >/dev/null
sub="e2e-ops-$RANDOM$RANDOM"
token="$(uv run python -m policy_atlas.api.dev_issuer mint --dir "$issuer_dir" --sub "$sub" --client-id policy-atlas-dev --ttl 600)"
common=(OIDC_ISSUER=http://dev-issuer.local OIDC_CLIENT_ID=policy-atlas-dev OIDC_JWKS_PATH="$issuer_dir/jwks.json" OIDC_JWKS_URL= DATABASE_URL="$db" PA_BACKEND_MODE=stub)
env "${common[@]}" DATABASE_URL="$ops_db" APP_ORIGIN=http://127.0.0.1:8002 POLICY_ATLAS_SERVICE_ROLE=ops OPS_UI_DIR="$repo/backend/ops-ui" \
  uv run uvicorn policy_atlas.api.app:create_app --factory --host 127.0.0.1 --port 8002 >"$ops_log" 2>&1 &
ops_pid=$!
env "${common[@]}" APP_ORIGIN=http://127.0.0.1:8003 \
  uv run uvicorn policy_atlas.api.app:create_app --factory --host 127.0.0.1 --port 8003 >"$api_log" 2>&1 &
api_pid=$!
for _ in $(seq 1 60); do curl -fs http://127.0.0.1:8002/healthz >/dev/null && curl -fs http://127.0.0.1:8003/healthz >/dev/null && break; sleep 1; done
ops=http://127.0.0.1:8002; api=http://127.0.0.1:8003; auth="Authorization: Bearer $token"
check() { local want="$1" got="$2" what="$3"; if [[ "$got" == "$want" ]]; then echo "PASS: $what ($got)"; else echo "FAIL: $what: want $want got $got"; exit 1; fi; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
check 200 "$(code "$ops/people")" "ops host answers /people with the page"
curl -s "$ops/people" | grep -q '<div id="root">' && echo "PASS: /people body is the ops index.html"
check 404 "$(code "$ops/api/v1/tasks")" "ops host has no task routes"
check 404 "$(code "$ops/api/v1/me")" "ops host has no /me"
check 401 "$(code "$ops/api/v1/ops/organisations")" "ops route without a token"
check 403 "$(code -H "$auth" "$ops/api/v1/ops/organisations")" "ops route without the role"
check 200 "$(code "$ops/brand/email-logo.png")" "a nested bundle file is served (brand/)"
check DENY "$(curl -s -D - -o /dev/null "$ops/people" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-frame-options"{print $2}')" "the ops host refuses framing"
rows="$(uv run python - "$db" "$sub" <<'PY'
import sys; from sqlalchemy import create_engine, text
e = create_engine(sys.argv[1])
with e.begin() as c:
    print(c.execute(text("select count(*) from app_user where user_id=:s"), {"s": sys.argv[2]}).scalar_one())
PY
)"
check 0 "$rows" "no app_user row created by the refused calls"
# The ops role is CLI-only (ops grant); the local stand-in is the same row write.
uv run python - "$db" "$sub" <<'PY'
import sys; from sqlalchemy import create_engine, text
e = create_engine(sys.argv[1])
with e.begin() as c:
    c.execute(text("insert into app_user (user_id, display_name, email, is_ops, created_at) values (:s, 'E2E Operator', :m, true, now())"), {"s": sys.argv[2], "m": sys.argv[2] + "@example.test"})
PY
check 200 "$(code -H "$auth" "$ops/api/v1/ops/organisations")" "ops route with the role"
org="$(curl -s -H "$auth" -H 'Content-Type: application/json' -d "{\"name\":\"E2E Org $sub\"}" "$ops/api/v1/ops/organisations")"
org_id="$(printf '%s' "$org" | uv run python -c 'import json,sys; print(json.load(sys.stdin)["org_id"])')"
echo "PASS: organisation created ($org_id)"
check 200 "$(code -H "$auth" -H 'Content-Type: application/json' -d '{"task_quota_per_year":1,"runs_per_user":null}' "$ops/api/v1/ops/organisations/$org_id/quota")" "organisation quota set to 1"
check 200 "$(code -H "$auth" -H 'Content-Type: application/json' -d "{\"user_ids\":[\"$sub\"],\"org_id\":\"$org_id\"}" "$ops/api/v1/ops/people/enrol")" "person moved into the organisation"
limit="$(curl -s -H "$auth" "$api/api/v1/me" | uv run python -c 'import json,sys; print(json.load(sys.stdin)["task_quota"]["limit"])')"
check 1 "$limit" "/me on the api host shows the inherited limit"
check 201 "$(code -H "$auth" -H 'Content-Type: application/json' -d '{"name":"first","question":"q?"}' "$api/api/v1/tasks")" "first task admitted"
second="$(curl -s -H "$auth" -H 'Content-Type: application/json' -d '{"name":"second","question":"q?"}' "$api/api/v1/tasks")"
check task_quota "$(printf '%s' "$second" | uv run python -c 'import json,sys; print(json.load(sys.stdin)["error"]["code"])')" "second task refused by the quota"
people="$(curl -s -H "$auth" "$ops/api/v1/ops/people?q=E2E%20Operator")"
check 1 "$(printf '%s' "$people" | uv run python -c 'import json,sys; print(sum(1 for p in json.load(sys.stdin) if p["display_name"]=="E2E Operator"))')" "people list finds the operator"
actions="$(uv run python - "$db" "$sub" <<'PY'
import sys; from sqlalchemy import create_engine, text
e = create_engine(sys.argv[1])
with e.begin() as c:
    print(",".join(r[0] for r in c.execute(text("select action from ops_action where actor_user_id=:s order by at"), {"s": sys.argv[2]})))
PY
)"
check "org.create,org.quota,person.move" "$actions" "one ops_action row per write, in order"
# The ops server did all of the above as pa_ops: prove the login it used.
who="$(curl -s -H "$auth" "$ops/api/v1/ops/organisations" >/dev/null; uv run python - "$ops_db" <<'PY'
import sys; from sqlalchemy import create_engine, text
with create_engine(sys.argv[1]).connect() as c:
    print(c.execute(text("select current_user")).scalar_one())
PY
)"
check pa_ops "$who" "the ops server's database login is pa_ops"
grep -c '"ops.action"\|ops.action' "$ops_log" >/dev/null && echo "PASS: ops.action lines in the ops server log"
echo "ops-e2e-local: PASS"
