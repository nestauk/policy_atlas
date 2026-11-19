#!/usr/bin/env bash
# Assert deploy.sh refuses production frontend builds missing required VITE vars.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_script="$repo_root/scripts/deploy.sh"

if [[ ! -f "$deploy_script" ]]; then
  echo "deploy-build-guard-test: SKIPPED — scripts/deploy.sh is not present yet; D.1 must provide its documented guard interface."
  exit 0
fi

if [[ ! -r "$deploy_script" ]]; then
  echo "ERROR: scripts/deploy.sh exists but is not readable" >&2
  exit 1
fi

for missing_var in VITE_OIDC_AUTHORITY VITE_OIDC_CLIENT_ID VITE_API_BASE_URL; do
  stderr_file="$(mktemp "${TMPDIR:-/tmp}/policy-atlas-deploy-guard.XXXXXX")"

  case "$missing_var" in
    VITE_OIDC_AUTHORITY)
      guard_env=(-u VITE_OIDC_AUTHORITY -u VITE_OIDC_CLIENT_ID -u VITE_API_BASE_URL
        VITE_OIDC_CLIENT_ID=guard-test-client VITE_API_BASE_URL=https://guard-test-api.invalid)
      ;;
    VITE_OIDC_CLIENT_ID)
      guard_env=(-u VITE_OIDC_AUTHORITY -u VITE_OIDC_CLIENT_ID -u VITE_API_BASE_URL
        VITE_OIDC_AUTHORITY=guard-test-authority VITE_API_BASE_URL=https://guard-test-api.invalid)
      ;;
    VITE_API_BASE_URL)
      guard_env=(-u VITE_OIDC_AUTHORITY -u VITE_OIDC_CLIENT_ID -u VITE_API_BASE_URL
        VITE_OIDC_AUTHORITY=guard-test-authority VITE_OIDC_CLIENT_ID=guard-test-client)
      ;;
  esac

  set +e
  env "${guard_env[@]}" PA_DEPLOY_GUARD_ONLY=1 \
    bash "$deploy_script" update 2>"$stderr_file" >/dev/null
  status=$?
  set -e

  if [[ $status -eq 0 ]]; then
    echo "ERROR: deploy guard accepted a missing ${missing_var}" >&2
    rm -f "$stderr_file"
    exit 1
  fi
  if ! grep -Fq "$missing_var" "$stderr_file"; then
    echo "ERROR: deploy guard failure for ${missing_var} did not name the missing variable" >&2
    sed 's/^/[deploy.sh] /' "$stderr_file" >&2
    rm -f "$stderr_file"
    exit 1
  fi
  rm -f "$stderr_file"
done

# CAPTCHA values are required only when the guard's scoped test override says
# CAPTCHA is enabled. The override must not change normal deploy behaviour.
for missing_var in VITE_WAF_CAPTCHA_SCRIPT_URL VITE_WAF_CAPTCHA_API_KEY; do
  stderr_file="$(mktemp "${TMPDIR:-/tmp}/policy-atlas-deploy-guard.XXXXXX")"
  case "$missing_var" in
    VITE_WAF_CAPTCHA_SCRIPT_URL)
      guard_env=(-u VITE_WAF_CAPTCHA_SCRIPT_URL -u VITE_WAF_CAPTCHA_API_KEY
        VITE_WAF_CAPTCHA_API_KEY=guard-test-key)
      ;;
    VITE_WAF_CAPTCHA_API_KEY)
      guard_env=(-u VITE_WAF_CAPTCHA_SCRIPT_URL -u VITE_WAF_CAPTCHA_API_KEY
        VITE_WAF_CAPTCHA_SCRIPT_URL=https://guard-test.invalid/)
      ;;
  esac

  set +e
  env "${guard_env[@]}" PA_DEPLOY_GUARD_ONLY=1 PA_DEPLOY_GUARD_WAF_CAPTCHA=1 \
    VITE_OIDC_AUTHORITY=guard-test-authority \
    VITE_OIDC_CLIENT_ID=guard-test-client \
    VITE_API_BASE_URL=https://guard-test-api.invalid \
    bash "$deploy_script" update 2>"$stderr_file" >/dev/null
  status=$?
  set -e

  if [[ $status -eq 0 ]] || ! grep -Fq "$missing_var" "$stderr_file"; then
    echo "ERROR: deploy guard did not refuse missing ${missing_var} with CAPTCHA on" >&2
    sed 's/^/[deploy.sh] /' "$stderr_file" >&2
    rm -f "$stderr_file"
    exit 1
  fi
  rm -f "$stderr_file"
done

env -u VITE_WAF_CAPTCHA_SCRIPT_URL -u VITE_WAF_CAPTCHA_API_KEY \
  PA_DEPLOY_GUARD_ONLY=1 PA_DEPLOY_GUARD_WAF_CAPTCHA=0 \
  VITE_OIDC_AUTHORITY=guard-test-authority \
  VITE_OIDC_CLIENT_ID=guard-test-client \
  VITE_API_BASE_URL=https://guard-test-api.invalid \
  bash "$deploy_script" update >/dev/null

aws() {
  if [[ "$1 $2" == "wafv2 list-api-keys" ]]; then
    printf '%s\n' "$STUB_KEYS_JSON"
  else
    echo "unexpected aws call: $*" >&2
    return 1
  fi
}
export -f aws

# The staging key lists a second domain too: a key that includes ours is taken.
matching_keys_json='{"ApplicationIntegrationURL":"https://captcha.example.aws/","APIKeySummaries":[{"TokenDomains":["other.example"],"APIKey":"other-key"},{"TokenDomains":["api.v3.policyatlas.uk","v3.policyatlas.uk"],"APIKey":"staging-key"}]}'
matching_output="$(env -u AWS_REGION -u AWS_DEFAULT_REGION \
  STUB_KEYS_JSON="$matching_keys_json" PA_DEPLOY_WAF_KEYS_ONLY=1 \
  bash "$deploy_script" update)"
if [[ "$matching_output" != *"https://captcha.example.aws/"* || \
      "$matching_output" != *"staging-key"* || \
      "$matching_output" == *"other-key"* ]]; then
  echo "ERROR: WAF API-key lookup did not return only the matching key" >&2
  exit 1
fi

no_match_keys_json='{"ApplicationIntegrationURL":"https://captcha.example.aws/","APIKeySummaries":[{"TokenDomains":["policyatlas.uk"],"APIKey":"prod-key"}]}'
stderr_file="$(mktemp "${TMPDIR:-/tmp}/policy-atlas-deploy-guard.XXXXXX")"
set +e
env -u AWS_REGION -u AWS_DEFAULT_REGION \
  STUB_KEYS_JSON="$no_match_keys_json" PA_DEPLOY_WAF_KEYS_ONLY=1 \
  bash "$deploy_script" update >/dev/null 2>"$stderr_file"
status=$?
set -e
if [[ $status -eq 0 ]] || ! grep -Fq \
  "create-api-key --scope REGIONAL --token-domains v3.policyatlas.uk" "$stderr_file"; then
  echo "ERROR: WAF API-key lookup did not give the staging create command" >&2
  sed 's/^/[deploy.sh] /' "$stderr_file" >&2
  rm -f "$stderr_file"
  exit 1
fi
rm -f "$stderr_file"

# CAPTCHA off: values inherited from the caller's shell must not reach the build.
off_output="$(env -u AWS_REGION -u AWS_DEFAULT_REGION \
  VITE_WAF_CAPTCHA_SCRIPT_URL=https://stale.invalid/ VITE_WAF_CAPTCHA_API_KEY=stale-key \
  PA_DEPLOY_WAF_KEYS_ONLY=1 PA_DEPLOY_GUARD_WAF_CAPTCHA=0 \
  bash "$deploy_script" update)"
if [[ "$off_output" != *"VITE_WAF_CAPTCHA_SCRIPT_URL="$'\n'* || "$off_output" == *"stale"* ]]; then
  echo "ERROR: CAPTCHA off did not unset inherited CAPTCHA values" >&2
  printf '%s\n' "$off_output" >&2
  exit 1
fi

echo "deploy-build-guard-test: PASS"
# The ops checks below use the stub on PATH; the exported function would shadow it.
unset -f aws

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/policy-atlas-deploy-order.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT
stub_dir="$work_dir/bin"
mkdir -p "$stub_dir"

cat >"$stub_dir/aws" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "$1 $2" == "wafv2 list-api-keys" ]]; then
  printf '%s\n' '{"ApplicationIntegrationURL":"https://captcha.example.aws/","APIKeySummaries":[{"TokenDomains":["v3.policyatlas.uk"],"APIKey":"staging-key"}]}'
  exit 0
fi

if [[ "$1" == "ssm" && "$2" == "get-parameter" ]]; then
  name=""
  query=""
  for ((index = 1; index <= $#; index++)); do
    if [[ "${!index}" == "--name" ]]; then
      next=$((index + 1)); name="${!next}"
    elif [[ "${!index}" == "--query" ]]; then
      next=$((index + 1)); query="${!next}"
    fi
  done
  if [[ "$query" == "Parameter" ]]; then
    printf '%s\n' '{"Type":"StringList","Value":"203.0.113.0/24"}'
    exit 0
  fi
  case "$name" in
    */allowed_cidrs) printf '%s\n' '203.0.113.0/24' ;;
    */ops_db_secret_arn) printf '%s\n' 'arn:aws:secretsmanager:region:account:secret:ops_db' ;;
    */ops_target_group_arn) printf '%s\n' 'target-group-arn' ;;
    */https_listener_arn) printf '%s\n' 'listener-arn' ;;
    */cluster_arn) printf '%s\n' 'cluster-arn' ;;
    */private_subnet_ids) printf '%s\n' 'subnet-a,subnet-b' ;;
    */migration_sg_id) printf '%s\n' 'security-group-id' ;;
    */migration_task_def_arn) printf '%s\n' 'migration-task-definition' ;;
    */frontend_bucket_name) printf '%s\n' 'frontend-bucket' ;;
    */fonts_bucket_name) printf '%s\n' 'fonts-bucket' ;;
    */distribution_id) printf '%s\n' 'distribution-id' ;;
    */issuer) printf '%s\n' 'https://issuer.invalid' ;;
    */client_id) printf '%s\n' 'client-id' ;;
    *) printf '%s\n' 'value' ;;
  esac
  exit 0
fi

case "$1 $2" in
  "secretsmanager describe-secret") exit 0 ;;
  "secretsmanager get-secret-value")
    printf '%s\n' '{"username":"pa_ops","password":"test","db_connection_string":"postgresql://pa_ops:test@db/test"}'
    exit 0
    ;;
  "ecs describe-services")
    if [[ "$*" == *"services[0].status"* ]]; then printf '%s\n' ACTIVE; else printf '%s\n' 0; fi
    exit 0
    ;;
  "ecs list-tasks") printf '%s\n' 0; exit 0 ;;
  "ecs run-task") printf '%s\n' migration-task; exit 0 ;;
  "ecs describe-tasks")
    if [[ "$*" == *"lastStatus"* ]]; then printf '%s\n' STOPPED; else printf '%s\n' 0; fi
    exit 0
    ;;
  "ecs update-service"|"ecs wait"|"cloudfront wait") exit 0 ;;
  "s3 sync")
    if [[ "$*" == *"frontend/public/fonts/"* ]]; then
      mkdir -p frontend/public/fonts
      touch frontend/public/fonts/guard-font.woff2
    fi
    exit 0
    ;;
  "s3 ls") printf '%s\n' 'font.woff2'; exit 0 ;;
  "cloudfront create-invalidation") printf '%s\n' invalidation-id; exit 0 ;;
  "elbv2 describe-rules")
    printf '%s\n' '{"Rules":[{"Priority":"1","Conditions":[{"Field":"host-header","HostHeaderConfig":{"Values":["ops.v3.policyatlas.uk"]}},{"Field":"source-ip","SourceIpConfig":{"Values":["203.0.113.0/24"]}}]},{"Priority":"2","Conditions":[{"Field":"host-header","HostHeaderConfig":{"Values":["metabase.v3.policyatlas.uk"]}},{"Field":"source-ip","SourceIpConfig":{"Values":["203.0.113.0/24"]}}]}]}'
    exit 0
    ;;
esac
echo "unexpected aws command: $*" >&2
exit 1
EOF
chmod +x "$stub_dir/aws"

cat >"$stub_dir/npx" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$stub_dir/npx"

cat >"$stub_dir/pnpm" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "build:ops" ]]; then
  mkdir -p ../backend/ops-ui
  touch ../backend/ops-ui/index.html
fi
exit 0
EOF
chmod +x "$stub_dir/pnpm"

cat >"$stub_dir/curl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$stub_dir/curl"

order_output="$work_dir/order.out"
PATH="$stub_dir:$PATH" PA_DEPLOY_ORDER_ONLY=1 \
  bash "$deploy_script" update >"$order_output"

expected_order=$'check ops allowlist\nbuild ops pages\ncdk deploy\ncheck ops secret\ncheck ops service\nstop api\nstop ops\nmigrate\nstart api\npublish frontend\nstart ops'
actual_order="$(grep -E '^(check ops allowlist|build ops pages|cdk deploy|check ops secret|check ops service|stop api|stop ops|migrate|start api|start ops|publish frontend)$' "$order_output")"
if [[ "$actual_order" != "$expected_order" ]]; then
  echo "ERROR: deploy sequence differs from its required order" >&2
  printf '%s\n' "$actual_order" >&2
  exit 1
fi

echo "deploy-order-test: PASS"
