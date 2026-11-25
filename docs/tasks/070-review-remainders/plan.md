# Plan: 070-review-remainders

> **Status:** drafted 2026-11-25. Not approved. Item ids (A1 to A3) are the contract's.

**Tier 3.** A1 changes the public interface and A2 changes a header the running product
sends to outside servers. Both are hard gates, so the tier cannot be lower. No ADR: no
design decision changes. Rollback is a revert of the pull request; nothing is stored.

Three phases, one commit each. The phases do not depend on each other.

## Phase 1: A2, the fetcher stops accepting zstd

- **Change:** `evidence_search/sourcing/fetch_live.py`, the `httpx.Client` of the document
  fetcher. Add `"Accept-Encoding": "gzip, deflate"` to its default headers. One line.
- **Why this is enough:** the HTTP library offers zstd only because the `zstandard`
  package is installed. A fixed header replaces that offer. The 25 MB check on expanded
  data stays as the second layer for gzip.
- **Reuse:** the existing `headers=` dictionary. No new helper.
- **Test:** one test in `backend/tests/evidence_search/sourcing/test_fetch_live.py`, with
  the existing fake transport: the request the fetcher sends has exactly this header value.
- **Executor:** lead, inline. **Gate:** `make verify-fast`.

## Phase 2: A3, the embedding split stops in an outage

- **Change:** `core/embeddings.py`.
  1. A small function `_is_outage(exc)`. It returns true for:
     - OpenAI: `APITimeoutError`, `APIConnectionError`, and `APIStatusError` with status
       500 or above;
     - Bedrock: any `botocore.exceptions.BotoCoreError` (timeouts and connection
       failures), and `ClientError` with HTTP status 500 or above.
     Everything else (HTTP 400, an invalid vector, a wrong vector count) is an input error.
  2. In `_embed_units_with_isolation`: when a batch of 2 or more texts fails with an
     outage error, call the provider once for each half, with no further split.
     - Both halves fail with an outage error: stop. Every text in the batch is returned
       as failed with that error. Total: 3 calls for the batch.
     - Otherwise: keep the vectors of a half that worked, and send a half that failed
       through the normal split, as today.
  3. A batch that fails with an input error splits as today. `Throttled` is re-raised
     as today.
- **Effect in an outage:** 3 calls for each batch of 96 texts, where today there are up
  to 191.
- **What does not change:** the caller. It already receives failed texts and leaves them
  for the next pass.
- **Reuse:** the existing exception imports and the existing return shape. No new module.
- **Tests:** in `backend/tests/core/test_embeddings.py`, at `_embed_units_with_isolation`
  with a fake backend, as the two existing tests do:
  - outage, OpenAI error types: 3 calls, all texts failed;
  - outage, Bedrock error types: 3 calls, all texts failed;
  - an outage error on the batch, then one half works: its vectors are kept.
  The existing isolation test and the throttling test stay unchanged.
- **Executor:** deep-reasoner (logic with a machine-checkable result). **Gate:**
  `make verify` (full), because the file is ingest code.

## Phase 3: A1, the request size limit and the text limits

### 3a. Body limit

- **Change:** one new file, `api/body_limit.py`, with a plain ASGI middleware (ASGI is the
  interface between the web server and the app). `api/app.py` adds it so that it runs
  before every other middleware.
  - Requests with a `Content-Length` above the limit: reply 413 at once. The body is
    not read.
  - Requests with no `Content-Length`: count the bytes as they arrive, and reply 413
    when the count passes the limit.
  - The reply is the API's normal error shape with code `payload_too_large`.
- **Limits:** a default of 1,000,000 bytes. One named exception: the theory of change
  upload route (`POST …/uploads` on the theory of change router), 15,000,000 bytes. That
  covers the 14,000,000 characters the route's own model allows, plus the other fields.
  The exceptions are a small table in `body_limit.py`: route path pattern → limit. A
  future upload route adds one row.
- **Reuse:** none exists. `app.py` has two `@app.middleware("http")` functions, but that
  style reads the whole body first, so it cannot stop a streamed body.
- **Tests:** in a new `backend/tests/api/test_body_limit.py`, through the real app:
  413 for a large `Content-Length` on the public waitlist route (no sign-in); 413 for a
  streamed body with no `Content-Length`; a normal small request passes. In
  `test_toc_uploads.py`: an upload of the largest allowed size returns 201.

### 3b. Text limits (the owner approves these numbers)

| Field | Model | Proposed limit | Reason |
|---|---|---|---|
| `question` | `TaskCreate`, `TaskUpdate` (`contract/tasks.py`) | 10,000 | Same as a chat message (`CHAT_MESSAGE_MAX`). |
| `description` | project create and update (`contract/projects.py`) | 4,000 | A few paragraphs. |
| `title` | chat create (`contract/chat.py`) | 200 | Same as a task name (`TASK_NAME_MAX`). |
| `text` | `FreeTextResponse` (`contract/check_ins.py`) | 10,000 | Same as a message to the task agent (`TASK_AGENT_MESSAGE_MAX`). |

- `OptionResponse.params` is an open dictionary. It gets no field limit; the 1 MB body
  limit bounds it.
- Other request models in `contract/task_agent.py` with unbounded strings are bounded by
  the 1 MB body limit only. This task does not add a limit to each one.
- **Existing rows are safe:** the limits apply to new requests only. A stored question
  longer than 10,000 characters still reads; it fails only when someone edits it.
- **Frontend:** the forms get no change. A user who goes over a limit sees the existing
  error message for a refused request. This is how the task name limit behaves today.
- **Generated files:** `make openapi-sync`, then `make drift-check`.
- **Docs:** remove the `api/app.py` body-size entry from `docs/deferred.md`.
- **Tests:** one parametrised test for the table: at the limit passes, one over gets 422.
- **Executor:** deep-reasoner for 3a (ASGI streaming is easy to get wrong); lead for 3b.
  **Gate:** `make verify` (full). This is also the step-6 exit.

## Live check after the staging deploy

Scope: the changed surfaces only.

1. Send a 2 MB request to the waitlist route with `curl`: expect 413.
2. Upload a theory of change image of several megabytes: expect success.
3. Start one small evidence search and confirm that documents are fetched and embedded.

## Risks

| Risk | Answer |
|---|---|
| A legitimate request above 1 MB exists that we did not find. | Before the build, the lead searches the request models for every field that can carry large data. The staging deploy runs the live check. The fix is one row in the exceptions table. |
| The Bedrock error for a bad text has a status of 500 or above. | Then one bad text fails its batch of 96 until the next pass. The Bedrock test pins the classification of `ValidationException` as an input error. |
| A website serves only zstd. | Not expected: a server must honour the request header. Such a page would fail as an unreadable document, as other fetch failures do. |
