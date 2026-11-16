---
type: Runbook
title: A parallel-agent brief forbids git stash; a sibling's in-flight edits vanish between stash and pop
description: When several agents edit one working tree, git stash by one of them reverts every sibling's uncommitted file for the window until git stash pop, and a sibling that saves during that window loses its edit on the pop; briefs for parallel agents forbid stash, and each agent that needs a clean tree works in its own worktree.
tags: [agents, git, worktree, parallel, "056"]
timestamp: 2026-11-02
---

# Rule

A brief for an agent that shares a working tree with others says: **no `git stash`, no
`git checkout -- <file>`, no `git reset`.** Stash reverts every uncommitted file in the tree,
the siblings' included, until the pop; an edit a sibling saves inside that window is
overwritten by the pop, or the pop conflicts. An agent that needs a clean tree (to run a
gate, to apply a patch) gets its own worktree and test database
([gate snapshots](gate-snapshots-commit-from-tree-ids.md)); the lead serialises the
hand-backs.

# Why

During task 056's Phase 0 tidy-ups a fast-worker ran `git stash` / `git stash pop` while
four siblings were editing; no damage was found at hand-back, by luck of timing. The later
phases ran each agent in a worktree (`policy_atlas-aN`, database `policy_atlas_aN_test`) and
the lead applied their patches at its gates.
