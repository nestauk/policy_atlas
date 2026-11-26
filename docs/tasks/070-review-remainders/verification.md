# Verification: 070-review-remainders

Evidence for the build of items A1 to A3 (see [contract.md](contract.md) and
[plan.md](plan.md)). Written at step 6. The review stack (step 7) adds its findings later.

## Commands run

All commands ran in the worktree `policy_atlas-070-review-remainders` on 2026-11-25.

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, before any edit) | pass, with a note | First run: 16 failures, all "too many clients already". Two other sessions ran full suites on the same Postgres. The failed files passed alone (215 passed). The other stages passed. |
| `make verify` (after the three phases) | pass | 5,012 backend tests, 173 infrastructure tests, 2,025 frontend tests. Ran on a Postgres of its own (see below). |
| `make verify` (exit gate, final code, after step 5c and the Codex fixes) | pass, with a note | Backend: 5,014 passed. Infrastructure: 173 passed. Lint, type check, guards and drift check: pass. Frontend: 1 of 2,025 tests timed out at 5 seconds (`ProjectsView.test.tsx`, "asks for the next page of the project's tasks") while other sessions loaded the machine; `make frontend-verify` alone then passed (2,025). The slice changes no frontend file. |
| `make verify` (one run earlier, same code) | 2 failures under load | `test_option_searches_run_at_the_configured_width` and `test_the_run_read_names_the_toc_walk_kind_and_the_draft_a_check_follows` failed with the machine at a load average above 100. Both files passed alone (38 passed) and in the exit gate. The slice does not touch them. |
| `make drift-check` (part of `make verify`) | pass | No generated file changed. |
| `make verify` (review phase, 2026-11-26, before the lanes) | pass | Backend: 5,014 passed. Infrastructure: 173. Frontend: 2,025. |
| `make verify` (review phase, after the review fixes) | pass | Backend: 5,024 passed. Frontend: 2,025. |
| `make verify` (review phase, final files, runs 1 and 2) | 2 failures, then 1, under load | Load average above 100 from two other sessions. Run 1: `test_sse_backlog_to_tail_has_no_duplicate_or_missing_mapped_sequences` and `test_option_searches_run_at_the_configured_width`. Run 2: the second one only (it saw 9 of 10 child runs inside its 30-second wait). Both files passed alone (130 passed with `test_fetch_live.py`). The slice touches neither. |
| `make verify` (review phase, final files, run 3, exit gate) | pass | Load average about 15. Backend: 5,024 passed. Infrastructure: 173. Frontend: 2,025. Lint, type check, guards, drift check and `okf-validate` (191 concepts): pass. |

The full gate ran against a separate Postgres container, because several sessions shared
the default one and exhausted its 100 connections. The owner approved this on 2026-11-25.

```
docker compose -p policy_atlas_070 -f docker-compose.yml -f <override: port 5470, max_connections=300> up -d db
COMPOSE_PROJECT_NAME=policy_atlas_070 \
TEST_DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5470/policy_atlas_test \
make verify
```

One run on the new container failed for a setup reason (2,435 errors, 0 failures): see the
first knowledge candidate below. The role was created once by hand and the next run passed.

## Checks beyond the build

**Named tests (all pass):**

| Rubric | Test |
|---|---|
| 9 | `tests/api/test_body_limit.py::test_a_declared_body_over_the_limit_is_refused_before_sign_in_with_cors_headers`, `::test_the_app_is_not_called_when_the_declared_length_is_over_the_limit` |
| 10 | `tests/api/test_body_limit.py::test_a_streamed_body_over_the_limit_is_refused_and_a_small_one_passes`, `::test_a_body_that_arrives_in_several_messages_is_counted_as_one` |
| 11 | `tests/api/test_toc_uploads.py::test_an_upload_of_the_largest_allowed_file_is_accepted`, `tests/api/test_body_limit.py::test_only_a_post_to_the_exact_upload_path_gets_the_larger_limit` |
| 12 | `tests/api/test_body_limit.py::test_the_ops_app_refuses_a_body_over_the_limit` |
| 13 | `tests/evidence_search/sourcing/test_fetch_live.py::test_both_clients_ask_for_gzip_or_deflate_only`, `::test_an_answer_in_a_compression_format_we_did_not_offer_is_refused_unread`, `::test_a_gzip_answer_is_still_read` |
| 14 | `tests/core/test_embeddings.py::test_embed_unit_split_stops_after_three_calls_in_an_outage` (13 cases: 3 OpenAI, 9 Bedrock, 1 malformed reply), `::test_embed_unit_split_treats_vectors_of_the_wrong_size_as_an_outage` |
| 15 | `tests/core/test_embeddings.py::test_embed_unit_split_keeps_the_half_that_works_after_an_outage` |
| 16 | `tests/core/test_embeddings.py::test_embed_unit_split_continues_for_errors_that_are_not_an_outage` (2 cases) |
| 17 | `test_embed_unit_split_isolates_one_poisoned_unit_in_128` and the throttling tests: green, unchanged. |

**AI evals:** none. No prompt changed (`make prompt-guard` passes).

**Manual check on a real server.** The test client joins a streamed body into one message,
so the size limit was also checked on uvicorn (the real web server) with `curl`:

| Request to `POST /api/v1/waitlist` | Reply |
|---|---|
| 2,000,000 bytes with `Content-Length`, with an `Origin` header | 413, code `payload_too_large`, with `access-control-allow-origin` and `x-content-type-options` |
| 2,000,000 bytes with `Transfer-Encoding: chunked` (no `Content-Length`) | 413, code `payload_too_large` |
| `{}` | 422 `validation_error` (the request passed the limiter) |

The server log had no traceback.

## End-to-end command

```
cd backend
export DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5470/policy_atlas \
  APP_ORIGIN=http://localhost:5173 OIDC_ISSUER=http://dev-issuer.local \
  OIDC_CLIENT_ID=policy-atlas-dev OIDC_JWKS_PATH=<scratch>/issuer/jwks.json
uv run python -m policy_atlas.api.dev_issuer init --dir <scratch>/issuer
uv run alembic upgrade head
uv run uvicorn policy_atlas.api.app:create_app --factory --port 8070 &
head -c 2000000 /dev/zero > 2mb.bin
U=http://127.0.0.1:8070/api/v1/waitlist
curl -i -X POST $U -H 'Content-Type: application/json' -H 'Origin: http://localhost:5173' --data-binary @2mb.bin
curl -i -X POST $U -H 'Content-Type: application/json' -H 'Transfer-Encoding: chunked' --data-binary @2mb.bin
curl -i -X POST $U -H 'Content-Type: application/json' -d '{}'
```

The live check after the staging deploy (plan § Live check) is not done: it needs the deploy.

## Diff summary

- **A2, `evidence_search/sourcing/fetch_live.py`:** a constant `ACCEPT_ENCODING = "gzip, deflate"`
  is sent by both HTTP clients (the document fetcher and the Europe PMC client).
  Added at the review (R1): `_encoding_refused` refuses, before the body is read, a reply that
  is not one plain layer of gzip or deflate.
- **A3, `core/embeddings.py`:**
  - `ProviderProtocolError(RuntimeError)` replaces the plain `RuntimeError` for a malformed
    reply (4 places).
  - `_is_outage(exc)` holds the fixed outage list of the plan.
  - `_embed_units_with_isolation` keeps its signature. It now uses two helpers:
    `_embed_batch_once` (one provider call and the vector checks) and `_split_failed_batch`.
  - A new log event `embedding.outage_split_stopped` records each stop.
- **A1, `api/body_limit.py` (new) and `api/app.py`:** `BodyLimitMiddleware` is added before the
  CORS middleware. Order from the outside in: server errors, security headers, request
  context, CORS, **body limit**, exception handlers, router.
- **`docs/deferred.md`:** the `api/app.py` body-size entry is replaced, and the three gaps of
  the plan are added.

**Flagged deviations (minor, inside the contract's intent):**

1. **A failed half is not called again as a whole.** The plan says a half that failed goes
   "through the normal split, as today", which would repeat the call for that half. The build
   passes the known error on. Result: 5 calls, not 6, when one half works and the other is
   still down. The full-outage count stays 3. A split for a bad text is unchanged (the
   existing test's call list is the same).
2. **Each failed text carries its own half's error**, not the error of the first whole-batch
   call.
3. **Mid-stream stop.** The plan says "stop passing data on". FastAPI turns any error raised
   while it reads a body into a 400 reply, so the limiter does not raise into the app. It
   tells the app that the client has gone (`http.disconnect`), drops what the app then
   sends, and writes the 413 itself. When a reply had already started, it raises so that the
   server closes the connection and the client cannot take a cut-off reply for a complete one.
4. **`Content-Length` that is not a number** is read as 0; the running count still applies.
5. **Phase commits.** The three phases were built in parallel (two delegated), so the three
   commits were made together after one green full `make verify`, not one gate per commit.
6. **`docs/deferred.md` was edited in the build**, as the plan (3b) and rubric item 7 ask. The
   build skill leaves durable records to step 8; the plan is more specific and wins here.

## Simplification (build step 5c)

Four read-only reviewers (reuse, simplification, efficiency, altitude) read
`git diff dev...HEAD -- backend`. The efficiency reviewer found the production code clean.

**Applied (tests only):**

- `test_the_app_is_not_called_when_the_declared_length_is_over_the_limit` no longer repeats
  the 413 checks on raw messages; the end-to-end tests cover them.
- `test_both_clients_ask_for_gzip_or_deflate_only` uses one request list for each client.

**Found, not applied:**

| Finding | Why not |
|---|---|
| Merge the two split paths of `_split_failed_batch` into one loop. | It changes the order of calls, so the existing isolation test would change. Rubric item 17 says it stays unchanged. |
| Split the streamed-body test into two tests. | One test may cover two behaviours; a second test builds the app again. |
| Replace the 10 MB upload test with arithmetic. | Rubric item 11 asks for the real 201. |
| Derive the 15,000,000 limit from `uploads.MAX_BYTES`. | The upload test already fails if the two drift apart. |
| Raise `ProviderProtocolError` (not `ValueError`) from the split layer's own vector-count check. | Left at step 5c; applied after the Codex review gave a concrete case (see § Review findings, finding 3). |
| Structural findings | See the deferred candidates below. |

## Review findings

**First adversarial review (Codex, read-only, 2026-11-25).** The owner approved one Codex
review in the build conversation. The lead that built the slice made the rulings below, so
the fresh review conversation must look at them again. The rest of the review stack is
not yet run.

| # | Codex finding | Severity (Codex) | Ruling by the build lead |
|---|---|---|---|
| 1 | The streamed count works only when the app reads the body. A route that never reads it (an unknown path, a `GET`) replies without a 413. | blocker | **Not accepted, with evidence.** A body that no code reads is never held in memory: the server stops reading from the network. Check on uvicorn: a 200 MB chunked `POST` to `/healthz` and to an unknown path got 405 and 404 with 0 bytes uploaded, and the server's memory stayed at about 95 MB. The finding H-02 is about bodies the app reads. |
| 2 | When the limit is passed after a reply has started, the limiter raises. The server then logs an error for each such request. | should-fix | **Open, for the review conversation.** Only a client that sends more than 1 MB to a streaming route can reach this. The other choice is a plain return: quiet, but the outer layers then end a cut-off reply as if it were complete. No change made. |
| 3 | The split layer's own vector checks raise `ValueError`, so a reply with vectors of the wrong size (the OpenAI backend checks only the count) is split up to 191 times. | should-fix | **Accepted and fixed.** `_embed_batch_once` raises `ProviderProtocolError` for a wrong count and for a vector that fails `validate_vector`. This matches the plan's intent ("wrong vector count, invalid body, wrong vector size"). One bad vector among good ones is still isolated, because the split goes on while one half works. New test: `test_embed_unit_split_treats_vectors_of_the_wrong_size_as_an_outage`. |
| 4 | The build does not repeat the call for a failed half; the plan says it goes through the normal split. | should-fix | **Stands as flagged deviation 1.** It saves a call and changes no result. The owner or the review conversation may amend the plan text or ask for the literal form. |
| 5 | The streamed-body test sends one message, so it does not prove that the count adds up across messages. | should-fix | **Accepted and fixed.** New test at the middleware: `test_a_body_that_arrives_in_several_messages_is_counted_as_one`. |

Codex found these sound: the 15,000,000 limit covers the largest valid upload; the path
pattern refuses trailing slashes, double slashes and other methods; the outage list matches
the plan; `Throttled` passes through every call; no text is lost or returned twice; both
fetcher clients send the header on redirects and retries.

**Review stack (step 7, fresh conversation, 2026-11-26).** `make verify` was green on the
build's last commit before any lane ran (5,014 backend, 173 infrastructure, 2,025 frontend
tests). The lanes read `git diff dev...HEAD`; the diff holds no generated or bulk data file.

| Lane | Reader | Result |
|---|---|---|
| Contract verifier | `contract-verifier` subagent | Rubric items 1 to 7 and 9 to 17 hold; 4 low or informational findings. |
| Code review | `/code-review` at `medium` | 10 findings. |
| Security | a `general-purpose` subagent on Claude Opus with a security brief | 4 findings. The pinned `agent-skills:security-auditor` subagent was not installed in this session, so this reader stood in. It ran its checks on a real uvicorn. |
| Adversarial | Codex, read-only (second model family; all the code is from Claude models) | 6 findings, and a view on the open question of the first review. |
| Over-engineering | `ponytail-review` | Lean; nothing to cut. |
| OKF bundle | `make okf-validate` | 191 concepts, 0 violations. |

No live-trace lane (the slice has no live runs) and no design lane (no frontend change).

**Adjudication.** "CR" is the code review, "Sec" the security lane, "CV" the contract verifier.

| # | Finding | Lanes | Ruling |
|---|---|---|---|
| R1 | A2 did not close the zstd hole. The HTTP library picks its decoder from the reply's `Content-Encoding`, not from the request header. A hostile host that answers in zstd, or in stacked layers (`gzip, gzip`), still expands a few kilobytes to gigabytes before the size check. Measured: 6 KB of zstd and 483 bytes of `gzip, gzip` each became 200 MB in one read step. The test checked only the request header. | CR, Sec (convergent) | **Adopted and fixed.** `_encoding_refused` in `fetch_live.py` refuses, before the body is read, any reply that is not one plain layer of gzip or deflate. Both clients call it. New tests: `test_an_answer_in_a_compression_format_we_did_not_offer_is_refused_unread` (3 cases; each asserts that the body was never read, and each fails without the check) and `test_a_gzip_answer_is_still_read`. This goes one step beyond the contract's fix text ("send the header") and stays inside its intent; the plan's line "a server must honour the request header" was wrong. No new outbound data. |
| R2 | The stop rule also fires when two texts that each reliably cause an outage-type error sit one in each half. The whole batch of 96 then fails on every pass. This includes an invalid vector, which the build turned into `ProviderProtocolError` after the first Codex review. | CR, CV, Sec ("not confirmed": no such text found) | **Deferred** (`docs/deferred.md`). No text is known to do this, one such text alone is still isolated, and the other choice (up to 191 calls when a provider sends wrong-size vectors for every text) is the finding the task exists to close. |
| R3 | "3 calls" is up to 12 HTTP requests on the OpenAI route, because that backend retries 4 times inside each call. | Codex (blocker), CR, Sec (info) | **Not a defect; wording fixed.** The build recorded this reading in § Intent & assumptions, and the contract counts calls to the embedding backend. The live route is Bedrock (no inner retry: 3 requests). The docstring now says "3 backend calls" and names the inner retries. The rest is in the deferred entry of R4. The owner may ask for the literal reading. |
| R4 | A stop for an outage marks the texts failed; a throttled batch is deferred. | CR | **Declined for this task, deferred.** The contract says "the remaining texts fail at once" and the caller leaves failed texts for the next pass. |
| R5 | A body that the app never reads is not counted (no 413 for an unknown path or a `GET`). | CR, Codex (the first Codex review also) | **Not a defect; the build's ruling is confirmed.** The security lane checked it again on uvicorn: the server stops taking data after about 64 KB, so such a body costs no memory. The class docstring claimed "every body is counted"; it now says "every body the app reads". |
| R6 | After a reply has started, the limiter raises, and the server logs an error with a traceback. No committed test covered this. (First Codex review, finding 2, left open by the build.) | CR, Sec (low), CV (low), Codex (view) | **Closed: the raise stays, and it has a test.** Codex, asked for a view, called the raise the right default: a plain return ends a cut-off streamed reply as if complete. Only a signed-in client that sends more than 1 MB to a streaming route reaches it. New test: `test_a_reply_that_had_started_is_cut_off_with_an_error_not_ended_as_complete`. |
| R7 | Once the limit is passed, any error from the app is swallowed and no log line records the refusal. | CR | **Declined.** An app error on a body the limiter cut off is the limiter's doing. The access log already records each 413 with its path. |
| R8 | The 413 is sent while body bytes are still on the connection; behaviour behind the load balancer is not proven. | CR (marked unverified) | **Declined as a code change.** On uvicorn the client got the 413 for a 2 MB declared and a 2 MB chunked body, and the security lane saw the connection stay open with the rest thrown away. The staging live check (plan § Live check) covers the load balancer. |
| R9 | The upload path pattern also matches 33 hexadecimal characters or 36 hyphens, which are not task ids. | Codex, Sec | **Declined.** A tighter pattern gains nothing: a request with a valid random id and no sign-in gets the same 15 MB allowance, because the framework reads the body before the sign-in check (R10). |
| R10 | On the upload path, a request with no sign-in can make the API read and parse up to 15 MB (about 90 MB in memory for a moment). | Sec (low) | **Accepted and deferred** (`docs/deferred.md`). The firewall's rate rule limits it, and before this task the path had no limit at all. |
| R11 | The 15,000,000 limit and the path are written by hand, apart from the route and `uploads.MAX_BYTES`. | CR | **Declined; the build's step 5c ruling is confirmed.** The largest-file upload test fails if they drift apart. |
| R12 | `_split_failed_batch` has two split paths. | CR, `ponytail-review` | **Declined; step 5c ruling confirmed.** One loop changes the call order that rubric item 17 pins. |
| R13 | The OpenAI backend accepts a reply with duplicate indexes and could pair a text with the wrong vector. | Codex | **Out of scope.** The code is on `dev` unchanged; the slice only renamed the error class beside it. Not deferred: no such reply has been seen. |
| R14 | The several-messages test feeds the same message without end. | Codex (nit) | **Declined.** One message is under the limit, so only a count across messages gives the 413 the test asserts. |
| R15 | The Europe PMC docstring said the request carries no headers but the user agent. | Codex (nit) | **Fixed.** |
| R16 | Five entries of the outage list had no test case. | CV (info) | **Fixed.** The outage test now has 13 cases, one for each entry. |

**Re-review of the fixes (round 2, Codex, read-only, on the uncommitted fix diff).** Two
findings; no third round was needed.

| # | Finding | Ruling |
|---|---|---|
| F1 | `_encoding_refused` drops `identity`, so `gzip` with a second header line `identity` passes. Codex states that this is not an expansion bypass: one real decoder runs. | **Declined.** `identity` expands nothing, and a refusal would only reject harmless replies. |
| F2 | The zstd test case sent bytes that are not zstd, so it passed with or without the check. | **Adopted and fixed.** The test now uses a reply body that records whether anything read it, and asserts for all three formats that nothing did. Run against the code without the check: 3 of 3 fail. |

Codex found the rest sound: the check matches the library's own header parsing, no accepted
header form builds a zstd, brotli or stacked decoder, every body read in the file passes the
check first, no byte is decoded before it, and the early return leaves the byte accounting
untouched.

Fake-done check on the fixes of this phase: no test was removed or relaxed, and the new
fetcher test fails without the check.

**Flagged deviations of the build (rulings by the review lead).**

1. A failed half is not called again as a whole: **adopted as built.** It saves a call and
   changes no result; the contract verifier found it inside the contract. The plan text
   ("through the normal split") stays as written; this line is the record.
2. Each failed text carries its own half's error: **adopted.**
3. Mid-stream stop by `http.disconnect`, and a raise when a reply had started: **adopted**
   (see R6).
4. A `Content-Length` that is not a number counts as 0: **adopted.** The security lane found
   that uvicorn refuses such a request with a 400 before the app runs.
5. Three phases committed together after one green gate, and 6. `docs/deferred.md` edited
   in the build: **adopted**; both are process points with no effect on the code.

The build lead's rulings on the first Codex review are confirmed: finding 1 (see R5),
finding 3 (with the residual case in R2), findings 4 and 5. Finding 2 is closed by R6.

**Knowledge candidates.** Authored: `http-client-decodes-any-content-encoding` (from R1,
with the httpx and zstd candidate) and `asgi-body-limit-middleware` (the five middleware,
uvicorn and test-client candidates, with R5, R6 and R10). Folded into
`parallel-agent-test-databases`: the exhausted connections and the `CREATE ROLE pa_ops`
race on a new server. Declined: the four tests that failed once under load (not
investigated, so not a verified fact), and "a new worktree has no installed dependencies"
(`measure-a-commit-from-a-second-worktree` covers it).

**Deferred candidates of the build.** Not added to `docs/deferred.md`: the shared outage
list, the shared "provider unavailable" signal (the R4 entry names it), the second copy of
the error reply, and the ops `Settings` helper in tests are tidy-ups for the periodic
structural review, with no behaviour open. The two search clients in `search_live.py` call
fixed services, not arbitrary hosts.

## Rubric status

Items 1 to 7 and 9 to 17 hold (the contract verifier checked each one). Item 8 holds: the
review stack ran and its findings are adjudicated above.

## Intent & assumptions

- "3 calls" in the contract counts calls to the embedding backend. The OpenAI backend
  retries a timeout or server error up to 4 times inside one call
  (`EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS`), so an OpenAI outage is up to 12 HTTP requests for a
  batch. Before this task it was up to 191 calls, each with the same inner retries. Bedrock
  has no inner retry in the backend: 3 requests.
- The upload path pattern accepts a task id of 32 to 36 hexadecimal characters and hyphens.
  Another spelling of a UUID (universally unique identifier) gets the default limit.

## Known unverified items

- The live check on staging (plan § Live check): 413 on the deployed API, a real theory of
  change upload of several megabytes, one small evidence search.
- No live provider call was made. The outage errors in the tests are real exception objects
  from the OpenAI and AWS libraries, but no real outage was observed.
- Three tests outside the slice failed once each under heavy machine load and passed on
  rerun (see § Commands run). They may be sensitive to timing; not investigated.
- `tests/api/test_sse.py::test_sse_backlog_to_tail_has_no_duplicate_or_missing_mapped_sequences`
  failed once in one run of `tests/api` during the build, then passed alone 5 times of 5 and
  in both full gates. It looks like a timing flake under load; not proven.

## Public safety

Safe to publish. No secret, no source text, no trace. The dev sign-in key was made in a
scratch folder and is not committed.

## Review handoff (step-7/8 inputs)

**Executor provenance:**

| Files | Written by |
|---|---|
| `fetch_live.py`, `test_fetch_live.py`, `docs/deferred.md`, this file | lead (Claude Fable 5.2) |
| `core/embeddings.py`, `tests/core/test_embeddings.py` | `deep-reasoner` (Claude Opus), reviewed by the lead |
| `api/body_limit.py`, `api/app.py`, `tests/api/test_body_limit.py`, `tests/api/test_toc_uploads.py` | `deep-reasoner` (Claude Opus), reviewed by the lead; small test edits by the lead |

All code is from the Claude family, so the adversarial review belongs to Codex.

**For adjudication:** the six flagged deviations above, and the build lead's rulings on the
five Codex findings (finding 2 is open).

**Knowledge candidates:**

- The migration's `CREATE ROLE pa_ops` is not safe on a brand-new Postgres server when
  several test workers migrate at once. Roles belong to the whole server, not to one
  database. Two workers that create the role at the same moment get `unique_violation`
  on `pg_authid_rolname_index`, and the `EXCEPTION WHEN duplicate_object` clause does not
  catch that. Seen as 2,435 errors on a fresh container; the shared container never shows it
  because the role already exists. Fix idea: also catch `unique_violation`.
- Under heavy machine load (several sessions running full suites) these tests failed once
  and passed on rerun: `test_option_searches_run_at_the_configured_width`,
  `test_the_run_read_names_the_toc_walk_kind_and_the_draft_a_check_follows` (a 401 reply),
  `ProjectsView.test.tsx` "asks for the next page" (5-second timeout), and
  `test_sse_backlog_to_tail_has_no_duplicate_or_missing_mapped_sequences`.
- Several worktree sessions that run `make test` at once exhaust the default container's 100
  connections ("too many clients already") and produce failures that look real. A Postgres
  of its own for each session avoids it (commands above).
- FastAPI turns any exception raised while it reads a request body into a 400 reply. A
  middleware that must stop a body cannot do it by raising from `receive`; it must return
  `http.disconnect` and write its own reply.
- Starlette puts a middleware added later outside one added earlier. A middleware that
  writes its own error reply must be added before CORS to get the CORS headers.
- Starlette's test client joins a streamed request body into one message. A test with a
  generator body proves "no `Content-Length`", not "many chunks". Use a real server for that.
- A request body that no code reads costs no memory: uvicorn stops reading from the network
  until the app asks for more. A size limit matters only for bodies the app reads.
- uvicorn has no limit on the size of a request body, and a WAF (Web Application Firewall)
  on a load balancer reads only the first 8 KB.
- The HTTP library (httpx) offers zstd only when the `zstandard` package is installed; a
  fixed `Accept-Encoding` header on the client replaces the offer.
- A new git worktree has no `backend/.venv` and no `frontend/node_modules`: run `uv sync` and
  `pnpm install --frozen-lockfile` before `make verify`.

**Deferred candidates (structural, not applied at step 5c):**

- Two lists of "the provider is failing" errors now exist: `_is_outage` in
  `core/embeddings.py` and `_retryable` in `core/tracing.py`. They differ already: `_retryable`
  lacks `ConnectionClosedError`, `ModelTimeoutException`, `InternalServerException` and the
  Bedrock status 500 and above, so model-call retries miss failures that the embedding split
  counts as an outage. One shared list in a small module would serve both.
- Each embedding backend could raise one shared "provider unavailable" signal, as it does
  for `Throttled`, so that the split layer does not need to know the OpenAI and AWS error
  types.
- `api/body_limit.py` builds the error reply itself; `_error_response` in `api/app.py` does
  the same. Moving the helper next to `ErrorEnvelope` would leave one copy.
- The two search clients in `search_live.py` (the search client and `crossref_abstracts`) do
  not send the `Accept-Encoding` header and read replies with no size limit. They call
  fixed search services, not arbitrary hosts.
- Three test files build ops-mode `Settings` by hand (`test_ops_router.py`,
  `test_service_role.py`, `test_body_limit.py`); a shared helper in
  `tests/api/resource_support.py` would replace them.

## Deferred work

The three gaps of the plan are in [docs/deferred.md](../../deferred.md): gzip expansion in the
fetcher, maximum lengths on four text fields, and configuration errors in the embedding split.
