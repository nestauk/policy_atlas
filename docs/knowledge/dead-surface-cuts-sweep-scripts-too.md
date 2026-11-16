---
type: Convention
title: Before deleting a "dead" method, grep its callers under scripts/, infra/ and the tests' seeds, not only src/
description: A simplification pass cut UploadStore.delete as unused; the operator removal script called it, its AttributeError was swallowed by a broad except, and the test seeded no uploads, so the rollback path silently stopped deleting files. Dead-surface cuts sweep every tree that imports the package and check that a test exercises the caller.
tags: [simplification, review, scripts, rollback, task-054]
timestamp: 2026-11-05
---

# Rule

- A "no callers" claim covers `backend/src`, `scripts/`, `infra/`, `backend/tests` and
  `frontend/src` — every tree that imports or calls the package. One grep over the repo root.
- A caller inside `try … except Exception` hides a removed method as a log line. Read the
  except blocks around the caller before cutting.
- The test that covers the caller must seed the data the caller acts on; a removal script's
  test that seeds no uploads never calls the store.

# Why

Task 054's simplification batch (`f81d8989`) removed `UploadStore.delete` as dead surface. The
operator script `scripts/ops_remove_toc_tasks.py` — the ADR's rollback remedy — called it inside a
broad `except`, so `--apply` logged a failure per file and reported success. Found by the
contract verifier and `/code-review` (2026-11-05); restored with a test that seeds a file.

# Citations

- `scripts/ops_remove_toc_tasks.py` (`_delete_files`); `backend/src/policy_atlas/core/uploads.py`
- `backend/tests/scripts/test_ops_remove_toc_tasks.py::test_apply_removes_the_uploaded_files_too`
- [054 simplification review](../tasks/054-toc-integration/simplification-review.md) § 2.1
- Related: [delegated-executor-practices](delegated-executor-practices.md)
