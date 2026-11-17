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
