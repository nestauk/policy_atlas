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

echo "deploy-build-guard-test: PASS"
