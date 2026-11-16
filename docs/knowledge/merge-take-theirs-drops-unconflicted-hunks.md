---
type: Convention
title: Resolving a merge conflict with "take theirs" drops every hunk of ours that did not conflict
description: git checkout --theirs on a conflicted file replaces the whole file, not just the conflicted region, so each of our non-conflicting hunks in that file is lost silently and the suite is the only thing that notices; before accepting a file wholesale, diff it against our pre-merge commit and re-apply each hunk of ours on top, and run the full gate after the merge even when the merge commit itself looks clean.
tags: [git, merge, review, process]
timestamp: 2026-10-21
---

# Rules

- **A conflict marker covers one region; "take theirs" covers the file.** When dev had
  rewritten `api/deps.py` and `runtime/agent.py`, accepting dev's version to honour its
  new implementation also removed three hunks of task 053 that lay outside the markers
  (the embedding seam, the search-generation choice, the live builder's default). No
  marker, no warning: only the full gate found them, as four failing tests.
- **Before accepting a file, list our hunks.** `git diff <merge-base> <our-tip> -- <file>`
  shows exactly what we changed in that file; after `checkout --theirs`, re-apply each
  hunk on top of theirs, then run that file's tests. The merge commit is not done until
  that list is empty.
- **A test that passed on our branch can still name the wrong thing after a merge.** Our
  selection test patched `OpenAIPlannerBackend`; dev had renamed it. A merge that compiles
  can still carry a test that patches a symbol that no longer exists.
- **A dependency audit red on dev is still ours to clear.** `make audit` runs in our gate,
  so an advisory inherited through the merge (certifi here) blocks our PR; a one-package
  lock bump is the fix, recorded as such.

# Citations

- [053 verification § Post-merge integration](../tasks/053-bedrock-local-route/verification.md)
- Related: [interface-change-sweeps-fakes-and-premise-pins](interface-change-sweeps-fakes-and-premise-pins.md)
