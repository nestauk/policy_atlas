---
type: Invariant
title: Block content_hash is a normalised hash
description: content_hash is a whitespace-insensitive hash of block content and excludes the (deferred) summary.
tags: [schema, blocks, content-hash, invariant]
timestamp: 2026-06-24
---

# Rule

A block's `content_hash` is a **normalised** hash of its `content`: whitespace-insensitive, so
trivially different formatting yields the same hash. It does **not** include the block summary.

# Why

A stable, normalisation-aware hash lets identical content de-duplicate and version-compare reliably.
The co-versioned `summary` column is deferred (the summary faithfulness judge isn't run yet), which
makes "content_hash excludes summary" trivially true for now.

# Watch out

When the summary column lands, the hash must continue to **exclude** summary — a summary change must
not change content identity. Verified by the content-hash stability test.

# Citations

- [001-walking-skeleton/contract.md](../tasks/001-walking-skeleton/contract.md) (block table)
- [001-walking-skeleton/verification.md](../tasks/001-walking-skeleton/verification.md) (content-hash stability)
