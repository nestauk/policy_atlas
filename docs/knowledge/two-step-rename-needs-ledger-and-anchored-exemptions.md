---
type: Convention
title: A two-step rename whose second step produces the first step's source word needs a per-checkout ledger, anchored never-map patterns and a fresh-clone guard
description: `portfolio→project` after `project→task` makes a swept tree indistinguishable from an unswept one by tokenising alone. The sweep tool keeps a gitignored hash ledger and refuses a tree that already looks swept; its never-map exemptions must be anchored (`[project]` matched a list literal, `--project` matched the ops CLI flag and caused a mid-sweep collision); its collision check counts prose and sees symbols, not senses — never re-run `--apply` on an edited post-sweep tree.
tags: [rename, sweep, tooling, idempotence, task-038]
timestamp: 2026-09-05
---

# Rule

`scripts/rename_038.py` (the committed rebase tool for PRs #62/#52) is the
shape to copy for any ordered rename:

- **Ledger, not tokenising, for idempotence.** Step 2 produces step 1's
  source word, so `--apply` records the post-sweep hash of every file it
  writes (`scripts/.rename_038_state.json`, gitignored) and skips files that
  still carry it; a tree with no ledger that already looks swept is refused
  unless `--force`.
- **Anchor every never-map pattern.** `[project]` (the pyproject table
  header) must match at line start or it also matches `data=[project]`;
  `--project` (the `uv run` flag) must be anchored to `uv run ` or it also
  matches an argparse flag — on 038 that let step 2 rename `--portfolio` on
  to an unrenamed `--project` (a collision the audit could not predict).
- **The collision check counts prose.** A comment saying "the global
  projects page" blocks `projects→tasks` in a file that declares `tasks`;
  reword the comment first.
- **The ledger re-sweeps an edited file whole**, and the collision check
  sees declared symbols, not senses: a file holding only new-Project
  vocabulary would be renamed on to Task. Run the tool on the *arriving*
  pre-sweep branch, never on a post-sweep tree that still carries its
  ledger.

# Why

No tokeniser can tell a `project` that was always a Project from one that
used to be a Portfolio once step 2 has run; only a record of what was swept
can. The exemptions and the collision check are pattern matches over text,
and every unanchored pattern on 038 bit once.

# Watch out

- Sweep a fresh clone and the guard fires (no ledger); that is the safe
  path for rebasing an open PR (`docs/deferred.md` § Vocabulary).
- Same family: [rename-sweep-inverts-screen-sense-words](rename-sweep-inverts-screen-sense-words.md),
  [stored-json-keys-are-vocabulary-too](stored-json-keys-are-vocabulary-too.md).

# Citations

- `scripts/rename_038.py` (module docstring; `NEVER_MAPPED_CONTEXTS`), `backend/tests/scripts/test_rename_038.py`
- [038-vocabulary-alignment/verification.md](../tasks/038-vocabulary-alignment/verification.md) (§ Phase 2, § Phase 3 "Sweep misses", "Unpredicted collision", § Review findings R15)
- [038-vocabulary-alignment/plan.md](../tasks/038-vocabulary-alignment/plan.md) (D2–D4)
