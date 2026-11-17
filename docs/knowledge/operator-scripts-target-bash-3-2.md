---
type: Convention
title: Operator shell scripts are written for bash 3.2, because that is what macOS ships
description: `mapfile`, `${var,,}`, associative arrays and other bash-4 features pass the script tests on a laptop with Homebrew bash first on the PATH and on CI's Linux, then fail for an operator whose `/usr/bin/env bash` is Apple's 3.2; use `while read` loops and `tr` instead, and know that a green script test is not a portability proof.
tags: [bash, shell, scripts, macos, portability, convention]
timestamp: 2026-11-17
---

# Rule

Scripts under `scripts/` that an operator runs from a laptop (`waf_report.sh`,
`deploy.sh` in a local recovery) start with `#!/usr/bin/env bash`, which on macOS resolves
to Apple's bash 3.2 unless Homebrew's bash is earlier on the PATH. Bash 4 features
(`mapfile` / `readarray`, `${var,,}` and `${var^^}` case conversion, `declare -A`,
`&>>`) are therefore not safe. The 064b report script shipped two of them from a Codex
build, and `make deploy-build-guard-test` was green locally and on CI, because both ran
a newer bash.

Write for 3.2: `while IFS= read -r line; do arr+=("$line"); done < <(...)` instead of
`mapfile`, `tr '[:upper:]' '[:lower:]'` or a plain comparison instead of case
conversion, indexed arrays only. The lead's review, not the test, is where this is
caught; a `bash --version` line in a script test would make it mechanical.

# Citations

- `scripts/waf_report.sh` (the `rules=()` read loop and its comment).
- [task 064b verification](../tasks/064b-waf-captcha/verification.md) § Review handoff,
  knowledge candidates.
