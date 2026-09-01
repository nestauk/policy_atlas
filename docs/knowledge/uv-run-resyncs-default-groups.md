---
type: Integration quirk
title: uv run re-syncs to default-groups on every invocation — a CI dependency group lives in [tool.uv] default-groups, not an install step
description: Any Makefile or workflow `uv sync --group X` is silently undone by the next `uv run`, which re-syncs the environment to the configured default groups. 033's ops group (boto3 for CI-side tests) had to land in default-groups; the image excludes it with --no-group on both Dockerfile sync lines.
tags: [uv, ci, dependencies, docker, "033"]
timestamp: 2026-08-25
---

# Rule

`uv run` re-syncs the environment to `[tool.uv] default-groups` on **every
invocation**. A dependency group that CI (or `make verify`) needs must be
listed in `default-groups` — a one-off `uv sync --group X` install step is
silently reverted by the next `uv run`, so the group appears installed in
the step that installed it and missing in the step that needed it.

The inverse control is the image build: exclude the group with
`--no-group X` on **every** `uv sync` line in the Dockerfile (033 has two),
pinned by an infra test that greps all sync lines
(`test_every_uv_sync_excludes_the_ops_group`) and a backend test that no
`api/`/`core/` module imports the excluded package.

# Why

033 added an `ops` group (boto3 + stubs) that tests, mypy and pip-audit
must see but the runtime image must not ship. The install-step approach
failed exactly as above; `default-groups = ["dev", "ops"]` was the CI
change the contract had to approve. `--no-dev` alone ships the group
(94 vs 86 packages) — the `--no-group` flag is load-bearing.

# Watch out

- `pip-audit` coverage follows the synced environment, so putting the group
  in `default-groups` is also what gets it audited (see
  [pip-audit-environment-mode-under-uv](pip-audit-environment-mode-under-uv.md)).
- The excluded package's *source* may still ship in the image if the
  Dockerfile copies `src/` wholesale — harmless while the import fails, but
  know it is there (033 review, info-level).
