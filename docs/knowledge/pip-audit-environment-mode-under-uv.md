---
type: Integration quirk
title: pip-audit's -r mode SIGABRTs under uv-managed CPython on macOS
description: pip-audit's -r (requirements-file) mode unconditionally builds a throwaway venv via ensurepip, which crashes under uv-managed CPython on macOS; environment-mode audit over the synced lockfile closure is the CI-parity fix.
tags: [pip-audit, uv, dependencies, integration-quirk, "016", security]
timestamp: 2026-07-10
---

# Rule

Do not run `pip-audit -r <requirements-file>` against a uv-managed project.
That mode unconditionally builds a throwaway venv via `ensurepip`, which
SIGABRTs under uv-managed CPython on macOS — a CI-parity violation, since the
crash is local-environment-specific. Instead run environment-mode audit over
the already-synced lockfile closure:

```
uv run --with pip-audit pip-audit --skip-editable
```

(see the `audit` target in the Makefile). This audits the identical pinned
dependency set, with identical local/CI behaviour, because it inspects the
environment uv already built rather than constructing a new one. `--strict`
is deliberately dropped — the editable first-party project is the one
visible skip, and that's expected, not a masked failure (rationale recorded
in the Makefile comment next to the `audit` target).

# Why

016 flagged this as deviation 1 during the build, and the review stack
confirmed it: `-r` mode's throwaway-venv construction is orthogonal to what
the audit is actually trying to check (the pinned dependency closure), and
on this platform it doesn't even run reliably. Environment-mode audit gets
the same coverage without the crash and without diverging from what CI does.
