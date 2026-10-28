---
type: Testing rule
title: A protocol change or an approved gate change must be swept through every test fake and every structural pin before the gate runs
description: When a Protocol method gains an argument, grep the tests for every fake that implements it (grep -rn "def embed_texts(" tests) and extend them before a targeted run, or the full gate finds the one you missed; when a contract approves a gate that overturns a premise (a dependency moving into the image), grep the tests for pins of the old premise and repoint them at what is still true rather than deleting them.
tags: [testing, protocols, fakes, dependency-gates, review]
timestamp: 2026-10-14
---

# Rules

- **A seam change is a sweep, not an edit.** `EmbeddingBackend.embed_texts` gained
  `kind=`; three test fakes implemented the old signature in three files. A targeted
  run of the two files the executor knew about passed; the full gate failed 16 tests
  in the third. Before any targeted run, list the fakes mechanically
  (`grep -rn "def <method>(" tests`) and include every file that matches.
- **An approved gate can invalidate a pin somewhere else.** `test_image_hygiene.py`
  pinned "the image ships no AWS SDK". The contract's approved dependency move put
  `boto3` in the image on purpose, so the pin's premise was gone. The right move is to
  **repoint** the guard at what the image still does not ship (the type stubs, still
  in the `ops` group), keep the witness assertion that stops it passing vacuously, and
  record why in the test's docstring and `verification.md`; never delete or loosen it.
  Grep the tests for the old premise when the contract is approved, not when the gate
  fails.
- **A repointed structural guard must keep its original reach.** The first repoint
  scanned `api/` and `core/` only, while the new `boto3` call sites sat in
  `evidence_search/`; the review widened it to every package except `ops/`.

# Citations

- [053 verification § Test changes and § Review findings](../tasks/053-bedrock-local-route/verification.md)
- `backend/tests/core/test_image_hygiene.py`; `backend/tests/evidence_search/synthesis/test_synthesis_tools.py` `FakeEmbedder`
- Related: [wire-field-additions-break-all-construction-sites](wire-field-additions-break-all-construction-sites.md)
