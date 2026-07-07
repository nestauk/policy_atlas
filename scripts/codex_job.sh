#!/usr/bin/env bash
# Thin shim for the Codex companion runtime, for the LEAD session's shell.
#
# Why (failure-log 2026-07-07): the plugin's /codex:status and /codex:result
# commands are user-typed only, and their `${CLAUDE_PLUGIN_ROOT}` is injected
# only while plugin commands execute — nothing resolves the script in the
# lead's shell. This shim ONLY resolves the path; waiting is the companion
# script's own `status --wait` (don't hand-roll polls — it has one built in).
#
# Usage:
#   scripts/codex_job.sh status <job-id>
#   scripts/codex_job.sh result <job-id>
#   scripts/codex_job.sh wait   <job-id> [timeout-seconds=1800]
set -euo pipefail

companion=$(ls -1d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1 || true)
[ -n "$companion" ] || companion="$HOME/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs"
[ -f "$companion" ] || { echo "ERROR: codex-companion.mjs not found under ~/.claude/plugins" >&2; exit 2; }

cmd=${1:?usage: codex_job.sh status|result|wait <job-id> [timeout-seconds]}
job=${2:?missing job id}

case "$cmd" in
  status|result)
    exec node "$companion" "$cmd" "$job"
    ;;
  wait)
    ms=$(( ${3:-1800} * 1000 ))
    out=$(node "$companion" status "$job" --wait --timeout-ms "$ms")
    echo "$out"
    # Native wait returns the last snapshot even on timeout — check terminal
    # state on the job's own line (never progress lines) before fetching.
    if echo "$out" | grep -qE "^- $job \| (completed|failed) \|"; then
      echo "---- result ----"
      exec node "$companion" result "$job"
    fi
    echo "ERROR: job $job not finished within ${3:-1800}s" >&2
    exit 3
    ;;
  *)
    echo "ERROR: unknown command '$cmd' (status|result|wait)" >&2
    exit 2
    ;;
esac
