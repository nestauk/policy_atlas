---
type: Invariant
title: A queued row's final write guards on its status and on the run that queued it; an unknown send outcome stays queued
description: A status-only guard (`queued`) lets a dead run's late delivery write into a row a later run has re-queued; stamp the queuing run on the row and require it in every read and write, including the stage's own deadline close. A send whose outcome is unknown (a transport error after the queue may have accepted the batch) must leave the rows queued for the deadline, never close them as failed, or the accepted message no-ops and the document is lost for the run. The handler always writes a reason before giving up, even for an unexpected error.
tags: [ingest, queue, sqs, lambda, idempotency, "057"]
timestamp: 2026-11-03
---

# Rule

- **Two keys on the guard.** The row carries the run that queued it (`ingested_by_run_id`,
  stamped in the same committed update that flips it to `queued`). The handler's first
  read, its final write and the stage's own close (`not_ready`, `send_failed`) all require
  `status = 'queued' AND ingested_by_run_id = :run`. A delivery from another run returns
  `not_queued` before it fetches anything.
- **Unknown is not failed.** A `ClientError` or a per-entry `Failed` from the queue closes
  the row (`send_failed`). A `BotoCoreError` (a read timeout after the request went out)
  leaves the row queued: the deadline closes it `not_ready` if no message ever arrives, and
  an accepted message still finds the row open.
- **A reason before giving up.** On the last delivery, an unexpected exception writes a
  closed-vocabulary reason (`worker_error`, a not-read-yet reason, not an access failure)
  before the message dead-letters; the log carries the error's type only, never its text
  (a database error's text holds SQL, parameters, chunk text and the URL).
- **Recovery lives in the shared function.** A store hit whose snapshot the retention script
  deleted between the lookup and the link write is parsed afresh inside `ingest_document`,
  so the in-process mode (production's) recovers the same way the Lambda does.

# Why

Task 057's review: the build guarded on status only; the Codex and security lanes both
found that a run that died with messages in flight (visibility 210 s, retention 4 days)
could have its late result land in the row the retry run had re-queued, with the dead run's
id as provenance. Codex also found the send path closing rows on any botocore error. The
prune-race recovery sat in the Lambda wrapper, so the in-process path failed the component
instead. See [reject at the fault grain and persist the reason](validation-reject-at-fault-grain.md)
for the older rule this extends.
