---
type: Live behaviour
title: The run executor's capacity check counts running walks in the database, not in the process
description: Two API servers on one database share one RUN_EXECUTOR_MAX, so a second server (another route, a live worktree) steals the first server's slots and its launches get HTTP 409; a 409'd task keeps its approved plan and can be re-posted; a live worktree server shares the dev database and needs alembic upgrade head after a schema slice.
tags: [runtime, executor, live-check, worktree, "056"]
timestamp: 2026-11-02
---

# Behaviour

- `RUN_EXECUTOR_MAX` is enforced by counting running walks **in the database**, not in the
  process. Two servers on one database (one per model route, or a detached live worktree
  beside `make dev`) share the one budget: the second server's running walks fill the first
  server's slots and its launches answer HTTP 409 "at capacity".
- A task whose run got 409 keeps its approved plan; `scripts/fixed_questions.py` posts `{}` to
  start the run, so re-posting later needs no re-planning. Launch one question at a time as
  the executor frees up (`--only`).
- A live worktree's server shares the dev database. A phase that adds a migration needs
  `alembic upgrade head` on that database before its live run, or the run reaches the new
  table mid-way (task 056's final set started one migration behind and was upgraded two
  minutes in, before any run reached appraisal).

# Why

Task 056's final fixed-question set ran `bedrock` on :8000 and `openai-direct` on :8001 from
two detached worktrees; the three bedrock launches got 409 for this reason and were re-posted
as slots freed. Related: [gate snapshots](gate-snapshots-commit-from-tree-ids.md) for the
worktree pattern itself.
