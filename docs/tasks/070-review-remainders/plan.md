# Plan: 070-review-remainders

> **Status:** drafted 2026-11-25, revised the same day after the adversarial review (see
> the last section). Not approved. Item ids (A1 to A3) are the contract's.

**Tier 3.** A1 changes the public interface and A2 changes a header the running product
sends to outside servers. Both are hard gates, so the tier cannot be lower. No ADR: no
design decision changes. Rollback is a revert of the pull request; nothing is stored.

Three phases, one commit each. The phases do not depend on each other.

## Phase 1: A2, the fetcher stops accepting zstd

- **Change:** `evidence_search/sourcing/fetch_live.py`. Add
  `"Accept-Encoding": "gzip, deflate"` to the default headers of **both** HTTP clients in
  the file: the document fetcher and the Europe PMC client. One line each.
- **What this closes:** the HTTP library offers zstd only because the `zstandard` package
  is installed. A fixed header replaces that offer, so the very high expansion ratio of
  zstd is gone.
- **What stays open (accepted, see the contract):** gzip. The library expands each network
  chunk before the 25 MB check. gzip expands at most about 1,000 times, so one chunk of
  64 KB becomes at most about 66 MB. That is bounded, where zstd was not.
- **Reuse:** the existing `headers=` dictionaries. No new helper.
- **Tests:** in `backend/tests/evidence_search/sourcing/test_fetch_live.py`, with the
  existing fake transport: a document request and a Europe PMC request each carry exactly
  this header value.
- **Executor:** lead, inline. **Gate:** `make verify-fast`.

## Phase 2: A3, the embedding split stops in an outage

- **Change:** `core/embeddings.py`.
  1. A small exception class `ProviderProtocolError(RuntimeError)`. The live backends
     raise it where they raise a plain `RuntimeError` today for a malformed reply (wrong
     vector count, invalid body, wrong vector size). A malformed reply is the provider's
     fault, not one text's.
  2. A small function `_is_outage(exc)`. It returns true for a fixed list only:
     - OpenAI: `APITimeoutError`, `APIConnectionError`, `APIStatusError` with status 500
       or above;
     - Bedrock transport: `ReadTimeoutError`, `ConnectTimeoutError`,
       `EndpointConnectionError`, `ConnectionClosedError`;
     - Bedrock service: `ClientError` with code `ModelTimeoutException`,
       `ServiceUnavailableException`, `InternalServerException` or
       `ModelNotReadyException`, or with HTTP status 500 or above;
     - `ProviderProtocolError`.
     Everything else keeps today's behaviour. That includes `ValidationException` (a bad
     text) and the credential, region and profile errors of the AWS library.
  3. In `_embed_units_with_isolation`: when a batch of 2 or more texts fails with an
     outage error, call the provider once for each half, with no further split.
     - Both halves fail with an outage error: stop. Every text in the batch is returned
       as failed with that error. Total: 3 calls for the batch.
     - Otherwise: keep the vectors of a half that worked, and send a half that failed
       through the normal split, as today.
  4. A batch that fails with any other error splits as today. `Throttled` is re-raised
     as today, also when a probe call raises it.
- **Effect in an outage:** 3 calls for each batch of 96 texts, where today there are up
  to 191.
- **What does not change:** the caller. It already receives failed texts and leaves them
  for the next pass.
- **Reuse:** the existing exception imports and the existing return shape. No new module.
- **Tests:** in `backend/tests/core/test_embeddings.py`, at `_embed_units_with_isolation`
  with a fake backend, as the two existing tests do:
  - outage, OpenAI error types: 3 calls, all texts failed;
  - outage, Bedrock error types (one transport error, one service code): 3 calls, all
    texts failed;
  - a malformed reply: 3 calls, all texts failed;
  - an outage error on the batch, then one half works: its vectors are kept;
  - Bedrock `ValidationException` and a missing-credentials error are not outages.
  The existing isolation test and the throttling test stay unchanged.
- **Executor:** deep-reasoner (logic with a machine-checkable result). **Gate:**
  `make verify` (full), because the file is ingest code.

## Phase 3: A1, the request size limit and the text limits

### 3a. Body limit

- **Change:** one new file, `api/body_limit.py`, with a plain ASGI middleware (ASGI is the
  interface between the web server and the app). `create_app` in `api/app.py` adds it
  **before** the CORS middleware is added. The framework puts a later middleware outside
  an earlier one, so the limiter sits inside the CORS and security-header layers. Its 413
  reply then carries those headers and a browser can read it. It is added before the
  point where the ops service returns early, so the public API and the ops service both
  get it.
  - Requests with a `Content-Length` above the limit: reply 413 at once. The app behind
    the limiter is not called.
  - Requests with no `Content-Length`: count the bytes as they arrive. When the count
    passes the limit, stop passing data on. If no reply has started, reply 413. If a
    reply has started, send nothing more and let the connection close.
  - The 413 body is the API's normal error shape with code `payload_too_large`. The
    limiter writes it itself, because the app's error handlers sit inside it.
- **Limits:** a default of 1,000,000 bytes. One named exception: `POST` on the exact
  path `/api/v1/tasks/{task id}/toc/uploads`, 15,000,000 bytes. That covers the
  14,000,000 characters the route's own model allows, plus the other fields. The
  exceptions are a small table in `body_limit.py`: method and anchored path pattern →
  limit. A future upload route adds one row. The review found no other request that can
  rightly pass 1,000,000 bytes.
- **Reuse:** none exists.
- **Tests:** in a new `backend/tests/api/test_body_limit.py`, through the real app:
  - 413 for a large `Content-Length` on the public waitlist route, with no sign-in, and
    the reply has the CORS header for the app's origin;
  - 413 for a streamed body with no `Content-Length`;
  - a normal small request passes;
  - a path that only looks like the upload path (for example another route that ends in
    `/uploads`, or `GET`) gets the default limit;
  - the ops app refuses a large body too.
  One test at the middleware itself, with a counting fake app: the app is not called when
  `Content-Length` is over the limit. In `test_toc_uploads.py`: an upload of the largest
  allowed size returns 201.

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
  general error message for a refused request, not a message next to the field. The
  review found no caller, fixture or mock in the repository that sends a longer value.
- **Generated files:** `make openapi-sync`, then `make drift-check`.
- **Docs:** replace the `api/app.py` body-size entry in `docs/deferred.md` with the two
  gaps this task leaves (see below).
- **Tests:** one parametrised test for the table: at the limit passes, one over gets 422.
- **Executor:** deep-reasoner for 3a (ASGI streaming is easy to get wrong); lead for 3b.
  **Gate:** `make verify` (full). This is also the step-6 exit.

## Gaps this task leaves (go to `docs/deferred.md`)

- **gzip expansion in the fetcher (rest of M-05).** Closing it needs the fetcher to read
  raw bytes and expand them itself with an output limit. Condition: a later security slice.
- **Configuration errors in the embedding split.** A missing credential or region is
  caught by the split and reported as failed texts, not raised. The knowledge note
  `isolation-belts-reraise-config-errors` says such errors must be raised. This task does
  not change that behaviour and does not make it worse. Condition: the next change to
  the embedding pass.

## Live check after the staging deploy

Scope: the changed surfaces only.

1. Send a 2 MB request to the waitlist route with `curl`: expect 413.
2. Upload a theory of change image of several megabytes: expect success.
3. Start one small evidence search and confirm that documents are fetched and embedded.

## Risks

| Risk | Answer |
|---|---|
| A legitimate request above 1 MB exists that neither the lead nor the review found. | The staging deploy runs the live check. The fix is one row in the exceptions table. |
| A Bedrock error for a bad text is in the outage list by mistake. | Then one bad text fails its batch of 96 until the next pass. The list is fixed and named, and a test pins `ValidationException` as not an outage. |
| A website serves only zstd. | Not expected: a server must honour the request header. Such a page would fail as an unreadable document, as other fetch failures do. |

## Adversarial review (2026-11-25)

One read-only Codex review covered the contract, the rubric and the plan together,
because the slice is three small changes. Eight findings; adjudication by the lead:

| # | Finding | Ruling |
|---|---|---|
| 1 | The Europe PMC client is a second client without the header. | Accepted. Phase 1 covers both clients. |
| 2 | gzip can still expand one chunk before the size check. | Accepted as a stated gap, not fixed here. The contract no longer says M-05 is closed in full. |
| 3 | "Every `BotoCoreError` is an outage" would hide credential and region errors; some Bedrock outage codes are not HTTP 500. | Accepted. The outage list is now fixed and named. Raising configuration errors is a stated gap. |
| 4 | A malformed provider reply is not a bad text. | Accepted. `ProviderProtocolError` joins the outage list. |
| 5 | The limiter's place, its reply headers, the mid-stream case, the exact route match and the ops app were not defined. | Accepted. Phase 3a defines each. |
| 6 | Rubric items 9 and 13 did not prove what they claimed. | Accepted. The rubric is revised. |
| 7 | No other request above 1,000,000 bytes; the four text limits break no caller. | Noted. |
| 8 | The three-call rule is well defined for small batches and for throttling. | Noted. |

The review did not look for simpler alternatives.
