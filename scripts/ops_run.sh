#!/usr/bin/env bash
# Setup-and-forward wrapper for the ops CLI (owner request, 2026-08-25).
#
# Usage: scripts/ops_run.sh <staging|prod> <ops command and flags...>
#   e.g. scripts/ops_run.sh staging user create --email a@b.org \
#          --display-name "A Name" --org "Org"
#
# Owns the setup the manual procedure in infra/DEPLOYMENT.md § 6 spells out —
# AWS session check, user-pool id from SSM, database credentials from Secrets
# Manager, the SSM port-forward tunnel (opened here and torn down on exit, or
# reused if :15432 is already listening) — then forwards everything after the
# environment name to the real CLI verbatim. The CLI's own parser stays the
# sole grammar authority; this script never validates or rewrites a flag.
#
# What deliberately stays manual:
#   - `aws sso login` (interactive by nature; we fail loudly with the command);
#   - PA_OPS_ACCOUNT_<ENV>: the expected-account is the operator's independent
#     assertion. Deriving it here from the same STS call the environment guard
#     compares against would turn that guard into a tautology — never do it;
#   - the CLI's typed day-zero confirmation (stdin/tty pass straight through).
#
# No credential ever touches argv: DATABASE_URL is assembled in-process and
# exported. OPS_DRY_RUN=1 prints the CLI argv (one per line) instead of doing
# anything — tests/ops/test_make_wrappers.py uses it to parse every make
# wrapper's output against the real parser, so wrapper↔CLI drift fails the
# suite.
set -euo pipefail

usage() {
  echo "usage: scripts/ops_run.sh <staging|prod> <ops command...>" >&2
  exit 2
}

[ $# -ge 2 ] || usage
env=$1
shift
case "$env" in staging | prod) ;; *) usage ;; esac

if [ "${OPS_DRY_RUN:-}" = "1" ]; then
  printf '%s\n' --env "$env" "$@"
  exit 0
fi

repo_root=$(cd "$(dirname "$0")/.." && pwd)

command -v session-manager-plugin >/dev/null 2>&1 || {
  echo "session-manager-plugin not installed (needed for the SSM tunnel)" >&2
  exit 2
}

aws sts get-caller-identity >/dev/null 2>&1 || {
  echo "AWS session invalid or expired — run: aws sso login${AWS_PROFILE:+ --profile $AWS_PROFILE}" >&2
  exit 2
}

# Pool id: same source the runbook uses. Account id: never derived (see header).
suffix=$(printf '%s' "$env" | tr '[:lower:]' '[:upper:]')
pool_var="PA_OPS_USER_POOL_${suffix}"
if [ -z "${!pool_var:-}" ]; then
  pool_id=$(aws ssm get-parameter --name /policy_atlas_v3/auth/user_pool_id \
    --query Parameter.Value --output text)
  export "${pool_var}=${pool_id}"
fi

if [ -z "${DATABASE_URL:-}" ]; then
  secret_id=$(aws ssm get-parameter --name /policy_atlas_v3/db/secret_name \
    --query Parameter.Value --output text)
  secret_json=$(aws secretsmanager get-secret-value --secret-id "$secret_id" \
    --query SecretString --output text)
  DATABASE_URL=$(python3 - "$secret_json" <<'PY'
import json
import sys
import urllib.parse

secret = json.loads(sys.argv[1])
user = urllib.parse.quote(secret.get("username", "dbadmin"), safe="")
password = urllib.parse.quote(secret["password"], safe="")
dbname = secret.get("dbname", "policy_atlas_db")
print(f"postgresql+psycopg://{user}:{password}@localhost:15432/{dbname}?sslmode=require")
PY
  )
  export DATABASE_URL
  unset secret_json
fi

# Tunnel: reuse an already-open one (and leave it running afterwards), else
# open our own from the DatabaseStack's fixed-target command and tear it down.
tunnel_pid=""
if ! nc -z 127.0.0.1 15432 2>/dev/null; then
  forward_cmd=$(aws cloudformation describe-stacks --stack-name PaV3DatabaseStack \
    --query "Stacks[0].Outputs[?contains(OutputKey, 'PortForwardingCommand')].OutputValue | [0]" \
    --output text)
  if [ -z "$forward_cmd" ] || [ "$forward_cmd" = "None" ]; then
    echo "no PortForwardingCommand output on PaV3DatabaseStack — open the § 6 tunnel manually" >&2
    exit 2
  fi
  # The command string comes from our own stack's output (trusted infra).
  eval "$forward_cmd" >/dev/null 2>&1 </dev/null &
  tunnel_pid=$!
  trap '[ -n "$tunnel_pid" ] && kill "$tunnel_pid" 2>/dev/null || true' EXIT
  opened=0
  for _ in $(seq 1 60); do
    if nc -z 127.0.0.1 15432 2>/dev/null; then
      opened=1
      break
    fi
    kill -0 "$tunnel_pid" 2>/dev/null || { echo "tunnel process exited before the port opened" >&2; exit 2; }
    sleep 0.5
  done
  [ "$opened" = "1" ] || { echo "tunnel did not open :15432 within 30s" >&2; exit 2; }
fi

# stdin/tty pass through: the CLI's typed confirmation must reach a human.
cd "$repo_root"
uv run --project backend python -m policy_atlas.ops --env "$env" "$@"
