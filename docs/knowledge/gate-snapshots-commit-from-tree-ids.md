---
type: Convention
title: Gate an index snapshot in a second worktree and commit from the gated tree id, never from the live index or the working tree
description: In the task 046 builds the lead gated a snapshot (`git write-tree`) in `../policy_atlas-gate` while workers kept editing; the commit is made with `git commit-tree` from the gated tree id and `git update-ref`. Three snapshot faults came from edits landing between `git add` and the gate (regenerated OpenAPI files, a worker's staged deletion, a later phase's test file); `git commit <pathspec>` commits the working tree, not the index; a wrong path in a split list silently commits nothing for that file; a shared test database deadlocks two suites.
tags: [git, gating, worktree, verification, build-process, task-046]
timestamp: 2026-10-12
---

# Rule

1. **Snapshot by explicit path lists** into an index, `git write-tree`, check the tree out in
   the gate worktree, run the gate there. Generated files (`frontend/openapi.json`,
   `gen/types.ts`, `scripts/prompt_hashes.json`) are regenerated FROM the snapshot in the gate
   worktree, never taken from the live tree.
2. **Commit with `git commit-tree <tree> -p HEAD`** and `git update-ref`; `git commit --
   paths` commits the working tree's versions, which may already hold the next phase.
3. **After the last split, compare `git rev-parse HEAD^{tree}` with the gated tree id**; a path
   list naming a wrong directory commits nothing for that file and says nothing.
4. **One `*_test` database per concurrent suite** (`make reset-test-db TEST_DATABASE_URL=…`):
   a subagent's targeted pytest and the gate on one database deadlock on the migration
   round-trips. `pnpm` refuses a symlinked `node_modules` without a TTY (`CI=true` and a real
   install in the gate worktree).
5. **Two phases may share one gated tree** when the second cannot start before the first lands;
   the commits are split from that tree with the shared files in the earlier commit, and the
   record says so.

# Why

Amendments 2–4 of task 046 built this way so that gating (15 minutes a run) and building
overlapped; the faults above each cost a re-gate. See
[delegated executor practices](delegated-executor-practices.md).
