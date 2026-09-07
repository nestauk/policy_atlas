---
type: Integration quirk
title: The prompt hash guard hashes the whole module, so a package move changes component prompt hashes through their import lines alone
description: `scripts/prompt_hash_guard.py` pins the SHA-256 of each prompt module's bytes, not of its prompt strings. Moving the package (`evidence_base` → `evidence_search`) changed seven of ten component prompt hashes with no prompt text touched; only the three modules with no package-relative import stayed byte-identical. The words-only proof of a prompt change is the diff of the prose hunks, never hash equality.
tags: [prompts, prompt-guard, hashing, review, task-038]
timestamp: 2026-09-05
---

# Rule

- A prompt module's hash changes whenever **any byte** of the module
  changes: `import` re-paths, `ruff` import re-sorts, a re-wrapped
  docstring. Do not read a hash change as a prompt change, and do not
  promise hash equality across a refactor that touches the module.
- The review artefact for a prompt edit is the prose diff, split from the
  identifier/import hunks (038's [prompt-diff.md](../tasks/038-vocabulary-alignment/prompt-diff.md)):
  the lead reads every prose hunk as words, and the re-pin
  (`python3 scripts/prompt_hash_guard.py --update`) lands in the same commit.
- Under a like-for-like word-swap ruling (038 R1) no version suffix moves
  and no replay is owed; a change of meaning is a version bump.

# Why

Contract 038 V3 promised "identical hash values" for the component prompts
after the package move. It could not hold: the hash covers the file. The
guard still does its job — it fails loud on any unreviewed byte — but the
promise was made about the wrong object.

# Citations

- `scripts/prompt_hash_guard.py`, `scripts/prompt_hashes.json`
- [038-vocabulary-alignment/prompt-diff.md](../tasks/038-vocabulary-alignment/prompt-diff.md)
- [038-vocabulary-alignment/verification.md](../tasks/038-vocabulary-alignment/verification.md) (§ Phase 3.3 "Minor deviation flagged")
- [AGENTS.md](../../AGENTS.md) § Landmines (prompt text is hash-pinned)
