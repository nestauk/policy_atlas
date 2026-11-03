# Data flow: queued full-text ingest (task 057)

One page for the owner's Data Protection Impact Assessment (DPIA) addendum. It names the
services the full-text reading stage now uses, what data moves between them, where it is
kept and for how long, and which identifiers appear where. Written at the build (step 6);
the owner's DPIA addendum gates the merge (contract G7).

## What changed

Before task 057 the web server fetched and parsed every full-text document itself. Now, in
the cloud (`ingest_mode = queued`, staging first), the web server puts one message per
document on a queue and a function fetches, parses and writes that document; the web
server embeds the text as documents land. On laptops and in tests (`ingest_mode =
in_process`) the same per-document code runs on threads inside the web server, so the data
never leaves the machine.

## Services and what each sees

| Service | Role | Data it handles | Kept for |
|---|---|---|---|
| Amazon SQS queue `policy-atlas-v3-ingest` | Holds one message per document until a function takes it | The message body only: `link_row_id` (a row id), `run_id` (a run id), `schema` (a version number). No URL, no document text, no user identifier. Encrypted at rest with SQS-managed keys; transport is TLS only. | At most 4 days; normally seconds |
| Dead-letter queue `policy-atlas-v3-ingest-dlq` | Receives a message after its second failed attempt | The same three fields | 14 days |
| AWS Lambda function `policy-atlas-v3-ingest` | Fetches the document from the publisher, parses it, writes the text into the database | The document's bytes and parsed text, in memory only, for one invocation (at most 3 minutes); no bytes are kept after parsing (data-model rule "no original bytes retained") | Nothing persists in the function |
| Amazon Aurora (the existing database) | The document store | The parsed text (`source_snapshot`, `chunk`), the vectors (`chunk_embedding`), and the link from a task to its documents (`task_source_snapshot`) | As today; see the retention rule |
| AWS Secrets Manager | Gives the function the database connection string at start | The database secret only. The function holds no model-provider credential and no permission to call Amazon Bedrock. | n/a |
| Amazon CloudWatch Logs `/policy_atlas_v3/ingest` | The function's log | Structured JSON lines: message ids, the two row ids above, status and reason codes, timings, byte counts. Publisher URLs are redacted to their scheme, host and path (the query string, which is where access tokens would be, is dropped; the same redaction the web server applies today). No document text, no prompts. | 30 days |
| Publishers (the open web, as today) | The source of the documents | The function sends the same requests the web server sent before: the document URL, from the NAT instance's address. Same hosts, same data, from a new place (contract G1). | n/a |

Not used: Amazon S3 (no bucket), VPC endpoints, any model provider from the function.

## Identifiers

- The queue and the dead-letter queue carry two pseudonymous ids (a link-row id and a run
  id) and a schema number. Both ids are meaningless outside the database.
- The function reads the document's candidate URLs and its PubMed Central id from the
  database (the link row's envelope snapshot), never from the message.
- The shared document store row (`source_snapshot`) carries no task id, no user id and no
  run id: those live on the task's own link row (`ingested_by_run_id`, `fetched_from`). The
  shared row's `source_locator` is the address the bytes were fetched from by the first task
  that stored them (the final URL after redirects, query string included), as the column held
  before task 057; whether to drop the query string on the shared row is an open owner item
  from the task 057 review.
- Logs name message ids and the two row ids; a URL appears as its scheme, host and path only.

## Retention rule for the store

A full-text snapshot that no task links any more (no link row through either of its two
snapshot columns), that no citation quotes and that no extraction record names, is deleted
with its chunks and vectors once it is older than 90 days, by an operator running
`scripts/prune_unlinked_snapshots.py --apply` by hand (dry run by default). There is no
scheduler in this slice. The script locks each candidate and re-checks for a link inside
the same transaction, so a link racing in cannot be orphaned.

## Where the rules live

- Contract: `docs/tasks/057-queued-ingest/contract.md` (N1, N2, N9, N11, N12, D3, D5, G1).
- Infrastructure as code: `infra/infra/components/ingest_worker.py` (queue, function, log
  group, alarms) with tests pinning every value; `infra/DEPLOYMENT.md` for the operator
  commands (dead-letter drain, `ingest_mode` per environment).
- Code: `backend/src/policy_atlas/ops/ingest_worker.py` (the function's handler),
  `evidence_search/sourcing/ingest_document.py` (the per-document function),
  `evidence_search/sourcing/ingest_queue.py` (the queue clients).
