#!/usr/bin/env bash
# Codex companion job helper for the LEAD session (the agent's own shell).
#
# Why this exists (failure-log 2026-07-07): $CODEX_PLUGIN_ROOT is only set inside
# the codex-rescue agent's environment — in the lead's shell the documented
# `node "$CODEX_PLUGIN_ROOT/..."` call fails with MODULE_NOT_FOUND, and inside a
# grep-filtered background poll that failure is silent (the loop spins to
# timeout). This wrapper resolves the companion script itself and FAILS LOUDLY.
#
# Usage:
#   scripts/codex_job.sh status <job-id>
#   scripts/codex_job.sh result <job-id>
#   scripts/codex_job.sh wait   <job-id> [timeout-seconds=1800]
#     `wait` polls every 15s until the job reports done/failed, then prints the
#     result. Any resolver/status error exits non-zero IMMEDIATELY — never poll
#     through an error.
set -euo pipefail

resolve_companion() {
  if [ -n "${CODEX_PLUGIN_ROOT:-}" ] && [ -f "$CODEX_PLUGIN_ROOT/scripts/codex-companion.mjs" ]; then
    echo "$CODEX_PLUGIN_ROOT/scripts/codex-companion.mjs"
    return 0
  fi
  # Newest cached plugin version wins; marketplaces checkout is the fallback.
  local hit
  hit=$(ls -1d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1 || true)
  if [ -z "$hit" ]; then
    hit=$(ls -1 "$HOME"/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs 2>/dev/null | head -1 || true)
  fi
  if [ -z "$hit" ]; then
    echo "ERROR: codex-companion.mjs not found (plugin cache and marketplaces both empty)" >&2
    exit 2
  fi
  echo "$hit"
}

cmd=${1:?usage: codex_job.sh status|result|wait <job-id> [timeout]}
job=${2:?missing job id}
companion=$(resolve_companion)

case "$cmd" in
  status|result)
    exec node "$companion" "$cmd" "$job"
    ;;
  wait)
    timeout=${3:-1800}
    deadline=$(( $(date +%s) + timeout ))
    while :; do
      # Capture status; a failing status command aborts the wait (set -e).
      out=$(node "$companion" status "$job")
      # Match the job's own state line / Phase line — never progress lines,
      # which can contain the word "completed" (failure-log 2026-07-05).
      if echo "$out" | grep -qE "^- $job \| (completed|failed)|^ *Phase: *(done|failed|error)"; then
        echo "$out"
        echo "---- result ----"
        exec node "$companion" result "$job"
      fi
      if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "ERROR: timed out after ${timeout}s waiting for $job; last status:" >&2
        echo "$out" >&2
        exit 3
      fi
      sleep 15
    done
    ;;
  *)
    echo "ERROR: unknown command '$cmd' (status|result|wait)" >&2
    exit 2
    ;;
esac
