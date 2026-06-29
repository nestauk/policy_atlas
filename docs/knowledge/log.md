# Knowledge update log

## 2026-06-29
* **Creation**: Added [upload-no-dedup](upload-no-dedup.md) — the no-content-hash-dedup invariant for uploaded sources (task 003).
* **Creation**: Added [citation-flag-dont-drop](citation-flag-dont-drop.md) — citation row written before GroundingError; fail evidence survives committed transactions via the harness (task 003).

## 2026-06-24
* **Initialization**: Created the bundle — index + four verified concepts from task 001
  ([structlog-only](logging-structlog.md), [test DB](testing-database.md),
  [event-log sequence](event-log-sequence.md), [block content_hash](block-content-hash.md)).
* **Update**: Added the [plan→config compile fails-closed](plan-compile-fails-closed.md) invariant —
  also verified by task 001, missed in the initial seed.
