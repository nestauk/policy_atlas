---
type: Runbook
title: Serve the commit under measurement from a second worktree, and name what makes a round not like-for-like
description: A live measurement round serves a detached second worktree (cherry-picks for lever isolation) so agents can edit the main tree meanwhile; a cherry-pick of a commit already in the history aborts the sequence (--quit, then re-pick); a verification.md conflict on the live worktree is always --theirs; never run make verify during a round; zsh needs ${=var} to word-split an argument list. A repeated question after the body-hash store is live is not like-for-like (30 to 50 documents per run come from the store); an adaptive pool at its cap finds the quota's edge by being throttled, which is the probe's cost, not a regression; a per-run row count over chunk_embedding over-counts the ingest stage by the acquire stage's abstract embeddings unless it filters on the snapshot kind.
tags: [measurement, worktree, live-check, cherry-pick, "057"]
timestamp: 2026-11-03
---

# Runbook

1. `git -C ../policy_atlas-live checkout --detach <commit>`, then cherry-pick the lever
   commits that isolate the round; a pick of a commit already present stops the sequence
   with "nothing to commit": `git cherry-pick --quit` and pick the rest. A conflict in
   `verification.md` is resolved `--theirs` (the record lives in the main tree only).
2. `uv sync` in the live worktree and start its server with the main tree's `backend/.env`
   (`uv run --env-file ... uvicorn ... --port 8000`), log to the scratchpad. The dev server
   caps concurrent walks at two ([executor capacity](run-executor-capacity-counts-database-rows.md)):
   the third fixed question starts when a slot frees.
3. Do not run `make verify` or any suite on the shared Postgres while a round runs; the
   round's walls are the evidence and the suite's load moves them.
4. In zsh, an unquoted `$args` holding several arguments is one word; use `${=args}`.
5. Read every figure back from the saved result file (`stage_walls.py` output, the
   per-document records), never from memory of a log line.

# What makes a round not like-for-like

- The body-hash store: a repeated question reuses 30 to 50 documents per run
  (`already_in_store`); the ingest wall drops with them. Name the count beside the wall.
- The embedding pool at its cap: more throttle sleeps than one request in flight saw are
  the cost of probing the quota's edge, not a regression.
- The embedding-loop overhead timer absorbs the other concurrent run's contention in the
  same process; two runs per round make it noisy.
- A window count over `chunk_embedding` includes the acquire stage's abstract (envelope)
  embeddings, about 1,200 to 1,500 rows per round; filter on the snapshot kind.

# Why

Task 057 ran seven measurement rounds on the fixed questions while agents built in the
main tree; each item above cost a wrong reading or an aborted round once before it was
written down.
