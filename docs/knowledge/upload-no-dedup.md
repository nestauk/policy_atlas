---
type: Invariant
title: Upload ingest creates a new snapshot per call
description: Each ingest_upload call produces a new source_snapshot row regardless of content hash — no silent dedup for uploaded sources.
tags: [ingest, source-snapshot, dedup, invariant]
timestamp: 2026-06-29
---

# Rule

`ingest_upload` generates a fresh `uuid4()` on every call. Two calls with identical content
produce two distinct `source_snapshot` rows. The content hash is stored (for future reference),
but it is **not** used as a dedup key.

# Why

A corrected re-upload is a new snapshot by design. Silent content-hash dedup would hide the user's
intent to supersede an earlier upload. The planned `supersedes` edge (deferred) is what lets a user
explicitly mark a re-upload as correcting its predecessor; dedup would make that link invisible.

Cross-project dedup for **acquired** sources (search-pipeline results) is a separate, follow-on
feature with different rules — the schema shape supports it (no `project_id` on `source_snapshot`),
but the lookup logic is deferred.

# Watch out

Do not introduce content-hash dedup into `ingest_upload`. If you suspect a regression, check
`test_ingest_upload_no_dedup` — two identical calls must return distinct UUIDs.

# Citations

- [system/data-model.md](../specs/system/data-model.md) (upload vs acquired dedup behaviour)
- [003-source-snapshot/contract.md](../tasks/003-source-snapshot/contract.md) (§ No content-hash dedup for uploaded sources)
- [003-source-snapshot/verification.md](../tasks/003-source-snapshot/verification.md) (test_ingest_upload_no_dedup)
