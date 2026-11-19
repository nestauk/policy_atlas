# Policy Atlas v3.0: project review

**Date:** 2026-10-19. **Branch:** `dev` (commit `a31489d5`).
**Method:** 13 parallel review agents read the code. Each agent looked at one topic (see the topic numbers in section 2). They did not change files, run the application, call external services or connect to a database. The lead reviewer then removed duplicate findings, checked the most important findings against the code, and set the final priorities.
**Sources:** the code, and `.claude/overview.md`. The review did not use other files in `.claude/` or `AGENTS.md`. It did not review `Dockerfile.claude` and `docker-compose.claude.yml` (local files only).

This is a technical review, not legal advice. The data protection items (section 5) must go to Nesta's Data Protection Officer.

---

## 1. How to read this file

### Priorities

| Priority | Meaning |
|---|---|
| **Critical** | An outside person or a normal user can use it now to steal data, lose data or run code on the server. Fix immediately. |
| **High** | A serious risk that needs only a likely condition (for example, any signed-in user, a provider outage or a deploy). Fix before the next production release. |
| **Medium** | A weakness that adds risk, removes a layer of protection, or causes noticeable problems. Plan a fix. |
| **Low** | A good-practice improvement or clean-up. |

### Confidence

- **Confirmed:** the reviewer read the code path and it does what the finding says.
- **Verified:** the lead reviewer also checked it in the code.
- **Likely:** the reasoning depends on library defaults, AWS defaults or load. It was not tested.

### Short glossary

| Term | Meaning |
|---|---|
| LLM | Large language model (here, OpenAI's GPT models). |
| SSE | Server-Sent Events: the one-way live stream that sends run progress to the browser. |
| JWT / JWKS | JSON Web Token (the signed sign-in token) / JSON Web Key Set (Cognito's list of public keys that check the token). |
| ALB | Application Load Balancer: the AWS component that receives web traffic for the API and passes it to the backend container. |
| ECS / Fargate | Elastic Container Service: AWS service that runs the backend container. Fargate is the "serverless" mode of ECS. |
| WAF | Web Application Firewall: an AWS service that blocks or rate-limits bad web traffic before it reaches the app. |
| CSP | Content Security Policy: a browser header that limits where a page can load scripts from. |
| PII | Personally identifiable information. |
| UK GDPR | The UK General Data Protection Regulation (data protection law). |
| Event loop | The single thread that serves all `async` code in the API. If it blocks, every live stream stops. |

---

## 2. Summary

**There are no critical findings.** The project has a strong base:

- No SQL injection. All queries use bound parameters.
- Authorization is consistent. Every route requires sign-in or is public on purpose, and every ID is checked against the caller's access in the database query.
- No file upload route, and no way to run code on the server.
- Strong protection against server-side request forgery (SSRF: tricking the server into fetching internal addresses).
- No raw HTML is rendered in the frontend, so there is no cross-site scripting (XSS).
- Untrusted text goes into prompts as fenced data, and LLM output is checked against strict schemas.

The main risks are **availability and cost control** (one server, no firewall, no quotas, no alerts), **data protection compliance** (privacy notice, deletion, third-party processors), and **reliability of long runs** (deploys, outages, stuck runs).

### Count by priority

| Priority | Count |
|---|---|
| Critical | 0 |
| High | 17 |
| Medium | 30 |
| Low | 30 |

### Review topics

| # | Topic | Highest priority found |
|---|---|---|
| 1 | OWASP common issues and SQL injection | High (H-01, H-02) |
| 2 | Authorization | Medium |
| 3 | File upload and server-side execution | High (H-02); otherwise medium |
| 4 | Dead and debug code | Medium |
| 5 | Performance | High |
| 6 | Data loss | High |
| 7 | Web server set-up (SSRF, CORS, CSRF, headers) | Medium |
| 8 | Prompt injection | Medium |
| 9 | Rate limiting, abuse and alerts | High |
| 10 | Error messages that show internals or secrets | High |
| 11 | Data protection and compliance | High |
| 12 | Resilience | High |
| 13 | Unescaped HTML/CSS/JavaScript in the frontend | Medium |

### All findings

| ID | Priority | Topic | Title |
|---|---|---|---|
| H-01 | High | 1, 5, 9 | Random sign-in key IDs can freeze the API without sign-in |
| H-02 | High | 1, 3, 7, 9 | No request size limit; bodies are read before sign-in |
| H-03 | High | 9 | No firewall or rate limits in front of the API |
| H-04 | High | 9 | No per-user or per-organisation quotas or spend caps |
| H-05 | High | 9, 12 | No alerts, budgets or automatic deploy rollback |
| H-06 | High | 10, 11 | Error logs contain local variables: user text and parts of secrets |
| H-07 | High | 11 | The privacy notice does not match what the system does |
| H-08 | High | 11 | No way to delete a user's data, and no retention policy |
| H-09 | High | 10, 11 | Langfuse receives full conversations and user IDs |
| H-10 | High | 6 | The test suite can damage the production database |
| H-11 | High | 12 | A run that fails between steps stays "running" |
| H-12 | High | 12 | An OpenAI outage can keep a run retrying for hours |
| H-13 | High | 6, 12 | Each deploy kills runs that are in progress |
| H-14 | High | 5 | The screening query reads the whole table for each task |
| H-15 | High | 5 | Each chat message loads all the task's embeddings into memory |
| H-16 | High | 5, 12 | Slow work can use all threads and connections, and the health check then replaces the server |
| H-17 | High | 9, 2 | One user can take every run slot |
| M-01 | Medium | 2, 4 | Options scoping is blocked only in the browser |
| M-02 | Medium | 2, 11 | Removing a user from an organisation does not stop their access |
| M-03 | Medium | 7, 13, 1 | No Content Security Policy; sign-in tokens readable by scripts |
| M-04 | Medium | 7 | The website also works over plain HTTP |
| M-05 | Medium | 3, 7 | A compressed web page can use all the server's memory |
| M-06 | Medium | 3 | PDF parsing processes have no memory limit |
| M-07 | Medium | 1, 6 | The application uses the database master account |
| M-08 | Medium | 8 | Hidden text in documents can be quoted as "verified" |
| M-09 | Medium | 8 | Invisible Unicode characters reach most prompts |
| M-10 | Medium | 8 | In unattended mode, document titles can steer the agent |
| M-11 | Medium | 10 | Raw error text is sent to the browser |
| M-12 | Medium | 11 | User content goes to OpenAI in the US |
| M-13 | Medium | 11, 9 | No multi-factor sign-in, but admins can read all organisations |
| M-14 | Medium | 11 | No procedure to give users a copy of their data |
| M-15 | Medium | 11 | Metabase can reach the production database |
| M-16 | Medium | 6 | Only 7 days of backups; no snapshot before migrations |
| M-17 | Medium | 6 | The Cognito user pool has no deletion protection |
| M-18 | Medium | 6 | Re-running `user enrol` resets a user's sharing settings |
| M-19 | Medium | 5, 12 | Database transactions stay open during external calls |
| M-20 | Medium | 12 | If the key download fails, every user is signed out |
| M-21 | Medium | 7, 12, 5 | Web server settings cause occasional 502 errors |
| M-22 | Medium | 12, 5 | Search retries and rate limits are incomplete |
| M-23 | Medium | 12 | Pipeline step failures are logged without a stack trace |
| M-24 | Medium | 5 | A new Python process starts for every document |
| M-25 | Medium | 5 | Each open progress stream queries the database 2.5 times a second |
| M-26 | Medium | 5 | Evidence and findings pages load the whole task, then cut one page |
| M-27 | Medium | 5 | Task list runs 3 to 4 queries per task; indexes missing |
| M-28 | Medium | 5, 12 | The hosting cannot scale past one server |
| M-29 | Medium | 5, 12 | Chat streaming uses a pool of about 6 threads |
| M-30 | Medium | 1, 2, 7, 9, 11 | The public waitlist can be spammed and shows who signed up |
| L-01 … L-30 | Low | various | See section 6 |

---

## 3. Critical findings

None.

---

## 4. High findings

### H-01 Random sign-in key IDs can freeze the API without sign-in
- **Topic:** 1, 5, 9. **Confidence:** Verified.
- **Location:** `backend/src/policy_atlas/api/auth.py:56-98` (`JwksProvider.get_key`), `auth.py:185-205` (`get_current_user`).
- **Description:** Each sign-in token has a "key ID" in its header. When the API sees a key ID that it does not know, it downloads Cognito's key list again. It remembers missing key IDs one at a time, so a new random key ID on each request causes a new download each time. No sign-in is necessary: anyone can make a fake token header. The download is a blocking network call inside an `async` function, so it runs on the event loop and stops all other requests, live progress streams and chat streams while it runs (up to 5 seconds each). There is only one server process. The list of missing key IDs also grows without limit.
- **Recommendation:**
  1. Make `get_current_user` a normal `def` function, or run `authenticate` in a worker thread (`anyio.to_thread.run_sync`).
  2. Allow at most one key download every 30 to 60 seconds in total, for all key IDs.
  3. Limit the size of the missing-key memory, or remove it after step 2.

### H-02 No request size limit; bodies are read before sign-in
- **Topic:** 1, 3, 7, 9. **Confidence:** Likely (standard FastAPI and Uvicorn behaviour).
- **Location:** `backend/src/policy_atlas/api/app.py` (no size limit), `backend/Dockerfile:47`. Text fields with no maximum length: `api/contract/tasks.py:66` and `:126` (`question`), `api/contract/projects.py:41`, `:80` (`description`), `api/contract/chat.py:42` (`title`), `api/contract/task_agent.py:728`, `:733`, `api/contract/check_ins.py:131` (`FreeTextResponse.text`), and `OptionResponse.params`.
- **Description:** Uvicorn (the web server), FastAPI and the load balancer accept a request of any size. FastAPI reads and decodes the full body before it checks sign-in. So a person with no account can send a body of several gigabytes to any POST route, including the public waitlist. A few such requests can use all 8 GB of memory in the single container. The container then restarts, and all runs in progress stop. Signed-in users can also store very large text, and some of it goes to the LLM, which adds cost.
- **Recommendation:**
  1. Add a small middleware that rejects bodies larger than about 1 MB with a 413 error. It must check the `Content-Length` header and also stop streamed bodies.
  2. Add `max_length` to the text fields above (other fields already use limits such as 10,000 characters).
  3. Also add a body-size rule in the firewall (see H-03).

### H-03 No firewall or rate limits in front of the API
- **Topic:** 9 (also 1, 7). **Confidence:** Confirmed.
- **Location:** `infra/infra/network_stack.py:100-142`, `infra/infra/policy_atlas_stack.py:191-235`, `scripts/deploy.sh:522-527` (`--desired-count 1`).
- **Description:** No AWS WAF is attached to the load balancer or to CloudFront. There are no rate limits per IP address, no AWS managed rule sets and no size limits at the edge. Only the basic AWS Shield protection applies, and it does not stop floods of normal web requests. The API runs as one container with no autoscaling. Public routes include `/readyz` (it queries the database), `POST /api/v1/waitlist` (it writes a row) and the public task views.
- **Recommendation:**
  1. Attach an AWS WAF web ACL (web access control list) to the load balancer, with:
     - a rate rule per IP address: a strict one for `/api/v1/waitlist` and a looser general one;
     - the AWS managed rule groups `CommonRuleSet`, `KnownBadInputs` and `AmazonIpReputationList`;
     - a body-size rule.
  2. Consider two or more containers (see M-28).

### H-04 No per-user or per-organisation quotas or spend caps
- **Topic:** 9 (also 1). **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/routers/runs.py:66-79`, `:296-299`; `api/chat_turns.py:35`, `:340`; `api/routers/task_agent.py:974`; `api/continuation.py:282-337`; `api/routers/longlist.py:98-153`; `core/usage.py`.
- **Description:** Each run has good internal limits on searches, documents and LLM calls. But nothing limits how much one user or one organisation can do over time:
  - There is no limit on the number of tasks or runs per day.
  - Planner turns are limited to one at a time for each task, but there is no limit for each user.
  - Chat allows 2 turns in progress per user, but has no limit per minute or per day.
  - "Free-text steering" calls the LLM each time, with no lock.
  - "Add option" searches do not count against the run limit.
  - `core/usage.py` records token use in logs and Langfuse, but nothing stores a total for each user or checks it.

  A stolen account (refresh tokens last 30 days) or a careless user can run up large OpenAI bills.
- **Recommendation:**
  1. Store token use and cost for each user and organisation in the database.
  2. Add daily or monthly quotas for runs, chat turns and planner turns, and refuse work above a spend cap.
  3. Add a lock to free-text steering so only one call runs at a time for each check-in.
  4. Add a rate limit for each user on POST routes.

### H-05 No alerts, budgets or automatic deploy rollback
- **Topic:** 9, 12. **Confidence:** Confirmed.
- **Location:** all of `infra/` (only a log group, `policy_atlas_stack.py:83-86`). `infra/cdk.json:69` (`removeDefaultDeploymentAlarm`). `policy_atlas_stack.py:192-201` (no `circuit_breaker`).
- **Description:** These are missing:
  - CloudWatch alarms for server errors (5xx), unhealthy containers, CPU, memory or the database;
  - AWS Budgets and billing alarms;
  - an SNS (Simple Notification Service) topic for notifications;
  - log metric filters (rules that count log lines);
  - error tracking such as Sentry.

  The ECS "circuit breaker", which rolls back a failed deploy, is off. The old container stops before the new one starts, so a bad image leaves production down. An attack, a runaway user, an outage or a bad deploy would be found only by hand.
- **Recommendation:**
  1. Set up AWS Budgets with alerts at 50%, 80% and 100%.
  2. Add CloudWatch alarms on: ALB `HTTPCode_Target_5XX_Count` and `UnHealthyHostCount`; ECS CPU and memory; Aurora CPU, connections and free memory.
  3. Add metric filters on the JSON logs for: total tokens (`*.usage`), `api.unhandled_exception`, `api.run_dispatch_failed`, `runner.component_failure_backstop` and `auth.token_rejected`.
  4. Turn on the ECS deployment circuit breaker with rollback.
  5. Also check the provider settings outside the code (section 7).

### H-06 Error logs contain local variables: user text and parts of secrets
- **Topic:** 10, 11. **Confidence:** Verified by a local test (2026-10-19, see below).
- **Location:** `backend/src/policy_atlas/core/logging.py:23`; `api/settings.py:35`; `api/app.py:436`; `api/routers/runs.py:288`; `evidence_search/sourcing/search_live.py:587` (OpenAlex `_auth_params`), `:680-688` (Overton params).
- **Description:** In production, logs are JSON (`LOG_FORMAT=json`). For errors, the code uses `structlog.processors.dict_tracebacks`. In structlog 26.1.0 (the locked version) this adds the **local variables of every code frame** to the error log (`show_locals=True` by default). Each value is shown as its Python `repr`, cut to **80 characters**, and each frame shows at most 10 variables. These logs go to CloudWatch, where everyone with log access can read them.

  What the test showed:
  - **User text is logged.** A user question in a local variable appeared in full.
  - **Secrets are logged in part, or in full when they are short or near the start of a value.** A dict `{'q': ..., 'api_key': ...}` showed the first 11 characters of the fake key before the 80-character cut. In the OpenAlex client, `_auth_params` builds `{"api_key": ...}` with the key **first**, so a key shorter than about 65 characters would appear in full. A secret held in its own local variable (for example a `password` string inside a database driver frame) would appear in full if it is shorter than 80 characters.
  - **The `Settings` object did not leak the database password in the test.** Its `repr` begins with the OIDC fields, so `database_url` falls after the 80-character cut. This depends on field order and is not a safe protection.
  - **The fix works.** With `ExceptionDictTransformer(show_locals=False)`, no frame had local variables, and none of the fake values appeared.
- **Test method:** the real `configure_logging()` and the real `Settings` class from `backend/src`, with structlog 26.1.0 (wheel hash checked against `uv.lock`) and fake secret values. The script is in the session scratchpad, not in the repository.
- **Recommendation:**
  1. Replace `dict_tracebacks` with `structlog.processors.ExceptionRenderer(structlog.tracebacks.ExceptionDictTransformer(show_locals=False))`.
  2. Mark `database_url` as `field(repr=False)`, so it is safe even when locals are shown.
  3. Add a test that checks no `locals` key appears in JSON error logs.
  4. Search the existing CloudWatch logs for `"locals"`, `api_key`, `password` and `dbadmin`. If any secret appears, change the database password and the provider API keys. User text in old logs disappears when the 30-day log retention ends.

### H-07 The privacy notice does not match what the system does
- **Topic:** 11. **Confidence:** Confirmed.
- **Location:** `frontend/src/views/legal/PrivacyView.tsx:52`, `:74`, `:98`, `:128-145`, `:148-153`; `frontend/src/views/legal/TermsView.tsx:80`, `:89`.
- **Description:** UK GDPR requires a privacy notice that tells people correctly what is collected, who receives it, where it goes and how long it is kept. This notice has these errors:
  - It says Amazon Bedrock processes queries. No Bedrock code exists; OpenAI does this.
  - It says OpenAI receives "anonymised search queries". In fact, user messages, questions and chat history go to OpenAI unchanged.
  - It says email is "the only user-specific identifier we store". The system also stores the Cognito user ID and the user's real name.
  - It does not say that chat transcripts are stored.
  - It does not name Langfuse as a processor.
  - It does not mention the transfer of data to the US (OpenAI).
  - It does not say that admins can read all data in all organisations.
  - It says no IP addresses are processed. Cognito does process them.
  - It gives only one purpose, but the Terms also say inputs are used to improve the search.
  - It has no "last updated" date.
- **Recommendation:** The Data Protection Officer rewrites the notice so it matches the system. Remove the claims about Bedrock and "anonymised" data until they are true.

### H-08 No way to delete a user's data, and no retention policy
- **Topic:** 11. **Confidence:** Confirmed.
- **Location:** `PrivacyView.tsx:65`, `:148-153`; `backend/src/policy_atlas/ops/commands.py:759-806`; `infra/infra/database_stack.py:66`, `:76`.
- **Description:** The notice promises that data "will be permanently deleted" when the pilot ends or when a user asks, and that waitlist data is kept only until the beta ends. Nothing in the code can do this:
  - The API has no DELETE routes. Tasks and chats can only be archived.
  - `user de-enrol` only clears the organisation, email and admin flag. It keeps the user ID, real name, tasks, questions, results and chats. It does not change public links, and it does not disable the Cognito account.
  - There are no scheduled clean-up jobs.
  - Waitlist rows never expire.

  UK GDPR has a right to erasure (Article 17) and a storage limit (Article 5(1)(e)).
- **Recommendation:**
  1. Build a tested erasure script. For one user ID it must: delete the rows in every table, delete or disable the Cognito user, and delete the Langfuse traces.
  2. Add a waitlist purge.
  3. Set a retention period for chat transcripts.
  4. Until this exists, change the notice so it does not promise automatic deletion.

### H-09 Langfuse receives full conversations and user IDs
- **Topic:** 10, 11. **Confidence:** The data flow is confirmed. The hosting location is not known.
- **Location:** `backend/src/policy_atlas/core/tracing.py:1-6`, `:58-97`, `:160-190`; `infra/infra/policy_atlas_stack.py:144-146`, `:156-159`; `trace_scope(user_id=...)` in `api/routers/conversations.py:756`, `:822`, `api/routers/task_agent.py:1007`, `api/routers/runs.py:124`.
- **Description:** In production, Langfuse records the full input and output of every LLM call. This includes user questions and chat messages, tagged with the user's Cognito ID. A deploy fails if the Langfuse keys are missing, so tracing is always on. A comment in the infrastructure code says production traces go into the **shared development Langfuse project**. So everyone with development access can read production user data. No masking function is used. The code does not show where Langfuse is hosted or how long it keeps data, and the privacy notice does not mention it.
- **Recommendation:**
  1. Use a separate production Langfuse project with restricted access and a set retention period.
  2. Confirm where it is hosted, and put a data processing agreement in place if a third party runs it.
  3. Consider a `mask=` function, and hash the user ID.
  4. Add Langfuse to the privacy notice.

### H-10 The test suite can damage the production database
- **Topic:** 6. **Confidence:** Verified.
- **Location:** `backend/tests/conftest.py:19`, `:58-67`; `backend/tests/core/test_migrations_025.py:253` (and other `test_migration_*` files); `infra/infra/database_stack.py:64`.
- **Description:** The test-safety check blocks only the database name `policy_atlas` (local development). The production database is named `policy_atlas_db`, so the check allows it. Operators connect to production through a tunnel on `localhost:15432`. If an operator has `DATABASE_URL` set to the tunnel and runs `uv run pytest` directly (not `make test`), all the tests run against production as the master user. The migration tests take the schema back several versions, which drops columns and tables, and then upgrade again. The data in those columns is lost. Many tests also commit test rows. `conftest.py` also loads `backend/.env`.
- **Recommendation:**
  1. In `conftest.py`, refuse to run unless the database name ends in `_test`. The `reset-test-db` target already uses this rule.
  2. Also refuse any port other than the local Docker port 5432.
  3. Give operators a database role that is not the master user (M-07).

### H-11 A run that fails between steps stays "running"
- **Topic:** 12. **Confidence:** Verified.
- **Location:** `backend/src/policy_atlas/api/routers/runs.py:163-164` (`_dispatch_run`). Compare `api/routers/check_ins.py:173-185`.
- **Description:** If a run fails inside a pipeline step, a backstop marks it as failed. If it fails between steps (for example a short database error while it writes events or finishes the run), `_dispatch_run` only logs the error. The database still shows the run as `running`, and these things happen:
  - The task refuses new runs with `409 run_active`.
  - The run uses one of the 10 run slots.
  - The user sees a run that never ends.

  Only a container restart fixes this. The continuation path already has the fix (`mark_interrupted_best_effort`), but the new-run path does not.
- **Recommendation:**
  1. Call `mark_interrupted_best_effort` in `_dispatch_run`. Create the run ID before dispatch so the function can use it.
  2. Consider a small periodic job that finds runs which have been "running" for too long.

### H-12 An OpenAI outage can keep a run retrying for hours
- **Topic:** 12. **Confidence:** Verified (code). The timing is an estimate.
- **Location:** `backend/src/policy_atlas/core/embeddings.py:366-400` (`_embed_units_with_isolation`), `:42-46`, `:168-169`; called inside a database transaction from `evidence_search/sourcing/acquire.py:1009` and `runtime/runner.py:5805`.
- **Description:** If an embedding batch fails, the code splits it in half and tries again until it finds the bad text. It does this for every error, including timeouts, connection errors and "quota used up" errors. If every call fails, one batch of 128 texts becomes 255 calls, and each call has its own retries:
  - When the quota runs out, this takes about 2 hours per batch.
  - When the calls hang until their timeout, it can take about 6 hours.

  During this time the run looks alive and keeps a database transaction open.
- **Recommendation:**
  1. Split only for input errors (HTTP 400, or an invalid vector).
  2. For timeouts, connection errors, 5xx and quota errors, fail the batch or the step at once.
  3. Add a total time or call limit for each embedding pass.

### H-13 Each deploy kills runs that are in progress
- **Topic:** 6, 12. **Confidence:** Confirmed.
- **Location:** `scripts/deploy.sh:435-439`, `:523-527`, `:619-621`; `infra/infra/policy_atlas_stack.py:165` (`stop_timeout` 10 s), `:196`; `backend/src/policy_atlas/api/app.py:313`, `:335-345`; `backend/Dockerfile:47`.
- **Description:** A deploy stops the only container, runs the migrations, then starts a new container. The container gets 10 seconds to stop, but runs take minutes. When the new container starts, it marks the old runs as "interrupted". Users cannot resume them, so the work and the LLM spend are lost. These are also lost: chat answers being written, evidence checks, and steering previews kept in memory. The shutdown code waits for runs before it sends the Langfuse traces, so the traces of the stopped runs are lost too. `deploy.sh` does not check for active runs. Staging deploys automatically on every push to `dev`.
- **Recommendation:**
  1. In `deploy.sh`, count active runs and refuse to deploy (or wait) unless an override is given.
  2. Send the Langfuse traces before the shutdown waits for runs, and use `executor.shutdown(wait=False, cancel_futures=True)`.
  3. Add `--timeout-graceful-shutdown` to Uvicorn, with a value lower than the stop timeout.
  4. In the longer term, let users resume an interrupted run from its last finished step.

### H-14 The screening query reads the whole table for each task
- **Topic:** 5. **Confidence:** Verified (code). The size of the effect depends on how much data there is.
- **Location:** `backend/src/policy_atlas/evidence_search/assess/screen.py:171-193`; callers `api/routers/_common.py:321-334` (`included_source_count`, one call for each task in the task list), `api/readmodels/repository.py:646-649` (funnel, landscape, evidence, source page, coverage).
- **Description:** The query that finds the current screening result for each document numbers the rows in groups by `(evidence_scope_id, task_source_snapshot_id)`, and only after that filters by `task_id`. PostgreSQL cannot apply the task filter first, so it reads and sorts **every screening row of every task**. No index starts with `task_id`. The task list calls this once per row (50 rows by default), and the browser polls the task list every 15 seconds while a run is active. The query becomes slower as the number of users grows.
- **Recommendation:**
  1. Add `task_id` to `partition_by`, or filter by `task_id` inside the subquery.
  2. Add an index on `(task_id, evidence_scope_id, task_source_snapshot_id)`.
  3. Check the result with `EXPLAIN ANALYZE`.

### H-15 Each chat message loads all the task's embeddings into memory
- **Topic:** 5. **Confidence:** Verified (storage and cap). The size depends on the size of real tasks.
- **Location:** `backend/src/policy_atlas/api/chat_scope.py:346-385`; `evidence_search/synthesis/synthesis_tools.py:91` (`RETRIEVAL_UNIT_CAP = 20_000`), `:1370-1439`, `:1490-1515`; `core/schema.py:703` (`vector` stored as JSONB).
- **Description:** Embeddings (number vectors that represent the meaning of text) are stored as JSON arrays of 1,536 numbers. For every chat message and every synthesis run, the code loads every vector of the task, turns the JSON into Python lists, and calculates the similarity in Python. With 5,000 units this is about 250 MB, and with 20,000 units about 1 GB, for each message. It also uses seconds of CPU while it holds Python's global lock, so all other users get slower responses. Nothing is cached between messages.
- **Recommendation:**
  1. Cache the retrieval data for each finished run, because it does not change.
  2. Store the vectors as pgvector (the PostgreSQL vector extension) and do the similarity search in the database, so that only the best matches come back.

### H-16 Slow work can use all threads and connections, and the health check then replaces the server
- **Topic:** 5, 12. **Confidence:** Likely (the mechanism is confirmed; the load level where it starts is not known).
- **Location:** `backend/src/policy_atlas/api/app.py:197-216`, `:290-300`; `runtime/runner.py:5805-5867`; `api/routers/task_agent.py:1070`; `infra/infra/policy_atlas_stack.py:207-217`; `infra/pa_config.json` (pool 15 + overflow 10).
- **Description:** Most routes share a pool of 40 threads. Some routes wait for the LLM inside the request (Task Agent turn, plan patch, gate turns), for up to about 9 minutes in the worst case. Each running pipeline step keeps one database connection for its whole duration (up to 14 of the 25 connections). The load balancer health check (`/readyz`) needs a free thread **and** a free database connection, and it must answer in 5 seconds. Under load it can fail. After about 2.5 minutes ECS replaces the only container, which kills every run. A short database outage has the same effect.
- **Recommendation:**
  1. Point the load balancer health check at `/healthz` (the process is alive), and keep `/readyz` for diagnosis only.
  2. Do not keep connections open during LLM or network calls (M-19).
  3. Move LLM calls in requests to background work, or use the async OpenAI client.
  4. Increase the pool size above the real need, check Aurora `max_connections`, and set `pool_timeout`.

### H-17 One user can take every run slot
- **Topic:** 9, 2. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/routers/runs.py:66-79`, `:306`; `infra/pa_config.json` (`run_executor_max: 10`); `api/routers/task_agent.py:945-975`; `api/routers/sse.py:607-683`.
- **Description:** The server allows 10 runs at a time in total, with no limit for each user. One user can create 10 tasks and start 10 runs, and everyone else then gets `409 capacity`. In the same way, one user with many tasks can hold all 40 request threads with planner turns, or open many live progress streams.
- **Recommendation:** Set limits for each user and each organisation on concurrent runs (for example 2), planner turns and open streams.

---

## 5. Medium findings

### M-01 Options scoping is blocked only in the browser
- **Topic:** 2, 4. **Confidence:** Confirmed.
- **Location:** `frontend/src/lib/capabilities.ts:23`; `scripts/deploy.sh:568-570`; `backend/src/policy_atlas/api/contract/tasks.py:66`; `api/routers/tasks.py:389-423`.
- **Description:** `VITE_OPTIONS_SCOPING` hides the unfinished options scoping feature in the production frontend, but the backend has no matching switch. A signed-in user can call `POST /api/v1/tasks` with `"capability": "options_scoping"` and run it with live, paid services. These rows also block migration downgrades.
- **Recommendation:** Add a backend setting (for example `PA_ENABLED_CAPABILITIES`) for each environment. Refuse disabled capabilities with 422 on task creation and on the run and plan routes.

### M-02 Removing a user from an organisation does not stop their access
- **Topic:** 2, 11. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/ops/commands.py:759-805`; `api/auth.py:147-182`.
- **Description:** `user de-enrol` changes only the database. The Cognito account stays active, and the API accepts any valid token without checking if the user is still enrolled. A person who has left can still sign in, read their tasks, create tasks and start paid runs. Their public links stay public, and their open progress streams keep running.
- **Recommendation:** Add a `user offboard` command that calls Cognito `AdminDisableUser` and `AdminUserGlobalSignOut` and clears `is_public`. Optionally, add a `disabled` flag that `get_current_user` checks.

### M-03 No Content Security Policy; sign-in tokens readable by scripts
- **Topic:** 7, 13, 1. **Confidence:** Confirmed.
- **Location:** `infra/infra/policy_atlas_stack.py:260`, `:293`, `:300`; `frontend/index.html`; `frontend/src/auth/OidcAuthProvider.tsx:36-45`; `infra/infra/cognito_auth.py:60-64`.
- **Description:** CloudFront uses the AWS managed `SECURITY_HEADERS` policy. It has no CSP and no Permissions-Policy. The sign-in tokens, including a refresh token that is valid for 30 days, are in `sessionStorage`, where any script on the page can read them. No XSS bug was found, so this is a missing second layer of protection: if an XSS bug is added later, nothing would block it.
- **Recommendation:**
  1. Create a custom CloudFront response headers policy that keeps the current headers and adds a CSP. For example: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' <API origin> <Cognito domain>; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self' <Cognito domain>`.
  2. Add a Permissions-Policy, and add `includeSubDomains` to HSTS (the header that forces HTTPS).
  3. Release the CSP first as "report only".
  4. Consider a shorter refresh-token lifetime.

### M-04 The website also works over plain HTTP
- **Topic:** 7. **Confidence:** Verified.
- **Location:** `infra/infra/policy_atlas_stack.py:289-303`.
- **Description:** The CloudFront behaviours do not set `viewer_protocol_policy`, so the CDK default `ALLOW_ALL` applies, and `http://` serves the app without encryption. The browser obeys the HSTS header only after one HTTPS visit. On a first visit, a person on the same network (for example public Wi-Fi) can change the JavaScript and show a fake sign-in page.
- **Recommendation:** Set `viewer_protocol_policy=REDIRECT_TO_HTTPS` on both behaviours, and add a test so this setting cannot be lost.

### M-05 A compressed web page can use all the server's memory
- **Topic:** 3, 7. **Confidence:** Likely (from the httpx 0.28.1 source and the lock file; not reproduced).
- **Location:** `backend/src/policy_atlas/evidence_search/sourcing/fetch_live.py:286-293`, `:550`.
- **Description:** The `zstandard` package is installed (it comes in through LangGraph). So httpx tells servers it accepts zstd compression and expands it with no size limit. The 25 MB download limit is checked only after the data is expanded. A small "decompression bomb" can expand to about 2 GB from one 64 KB network chunk. Downloads run inside the API process, so this can crash the API and every run. Anyone whose web page appears in Overton or OpenAlex results can trigger it. After a restart, the same page can be fetched again.
- **Recommendation:** Send `Accept-Encoding: gzip, deflate` and refuse other encodings. A better fix is to read raw bytes and decompress them with an output limit.

### M-06 PDF parsing processes have no memory limit
- **Topic:** 3. **Confidence:** Likely.
- **Location:** `backend/src/policy_atlas/evidence_search/sourcing/ingest_full_text.py:106`, `:666-669`, `:778`, `:844`.
- **Description:** PDF and HTML parsing runs in child processes with a 120-second limit (good), but with no memory limit. A 25 MB PDF can expand to many gigabytes inside the PDF library. Between 4 and 8 child processes share the 8 GB container with the API. If the system runs out of memory, it can stop the API.
- **Recommendation:** In `_worker_entry`, call `resource.setrlimit(resource.RLIMIT_AS, ...)` with about 1 to 1.5 GB. Also consider limits on the number of pages and on the length of the parsed text.

### M-07 The application uses the database master account
- **Topic:** 1, 6. **Confidence:** Confirmed.
- **Location:** `infra/infra/policy_atlas_stack.py:149`, `:185`; `infra/infra/database_stack.py:65`; `scripts/ops_run.sh`.
- **Description:** The API, the migration task and the operator tools all use the Aurora master user `dbadmin`, which can drop tables and create roles. No SQL injection exists now, but if the container were ever compromised, the attacker would have full control of the database.
- **Recommendation:**
  1. Create an application role that can only read, insert, update and delete rows.
  2. Keep `dbadmin` for migrations only.
  3. Create a separate role with limited access for operators.

### M-08 Hidden text in documents can be quoted as "verified"
- **Topic:** 8. **Confidence:** Likely (the chain follows from the code; it was not tested with a crafted PDF).
- **Location:** `backend/src/policy_atlas/evidence_search/sourcing/ingest_full_text.py:669`, `:696`; `frontend/src/views/ArtefactView.tsx:180`.
- **Description:** The text extraction keeps text that a person cannot see, such as white-on-white text, invisible PDF text, tiny fonts and HTML hidden with CSS. A document in the search results can hide a false claim or an instruction. The quote checker confirms the text is in the document, and the report then shows it as "Direct quote, verified against the source". This is the most realistic way for hidden instructions to get into the extraction and synthesis prompts.
- **Recommendation:**
  1. Remove invisible PDF text (render mode 3), text with the same colour as the background, and very small text.
  2. Remove hidden HTML elements before trafilatura runs.
  3. Record how many characters were removed, as a quality signal.
  4. Change the label to "quote found in the source text".

### M-09 Invisible Unicode characters reach most prompts
- **Topic:** 8. **Confidence:** Confirmed (code path).
- **Location:** `backend/src/policy_atlas/evidence_search/extract/iof_prompt.py:320-361` (also used by `icf_prompt.py` and `extract_interventions_prompt`); `runtime/chat_backend_openai.py:216`; `evidence_search/synthesis/grounding_judge.py` (`build_envelope`).
- **Description:** `sanitize_prompt_field` removes invisible characters (Unicode "tag" characters, zero-width characters and text-direction controls) that attackers use to hide instructions. Screening uses it, but extraction, synthesis tool results, chat and the grounding judge do not. A person reading the document cannot see these characters, but the model can.
- **Recommendation:** Remove invisible format characters once, when the document is ingested and before it is split into chunks. Then every later step, including the quote checker, sees the same clean text. Add a test.

### M-10 In unattended mode, document titles can steer the agent
- **Topic:** 8. **Confidence:** Likely.
- **Location:** `backend/src/policy_atlas/runtime/runner.py:4452-4474`; `runtime/agent_backend.py:1185-1196`; `runtime/steering_bundles.py:99-118`, `:461`, `:523`; `runtime/agent_prompt.py:638-660`.
- **Description:** In "Unattended" mode, an LLM "watch" agent decides for the user at check-in points, and its changes are applied without a person checking them. Its input includes document titles from outside sources, and these are not cleaned. A crafted title can try to make it change the screening criteria or re-run a search, and so skew the evidence. The damage is limited: the changes go through a strict grammar check, only one re-run is allowed at each pause, and every decision is recorded and flagged.
- **Recommendation:**
  1. In unattended mode, allow only searches that add results. Pause, or only propose, changes to criteria and re-runs that replace results.
  2. Clean the titles with `sanitize_prompt_field`.
  3. Show the criteria that the agent wrote clearly at the end of the run.

### M-11 Raw error text is sent to the browser
- **Topic:** 10. **Confidence:** Confirmed (code path).
- **Location:** `backend/src/policy_atlas/runtime/harness.py:196`, `:530`, `:609`; `runtime/runner.py:1480`, `:6044`, `:6265`; `runtime/steering.py:517-519`; `api/routers/sse.py:318-333`.
- **Description:** When a pipeline step fails, `str(exc)` (the raw error message) is stored in the event log. The progress stream then sends it to the browser, and it can also appear in check-in text. Library error messages can contain SQL statements and parameter values, internal database host names, and the OpenAI organisation ID. Only users who can read the task see it.
- **Recommendation:** Store a fixed, user-safe message with the error type and an error ID. Log the details on the server only (after H-06 is fixed).

### M-12 User content goes to OpenAI in the US
- **Topic:** 11. **Confidence:** Likely (the contracts are outside the code).
- **Location:** `backend/src/policy_atlas/runtime/chat_backend_openai.py:78`; `core/openai_client.py:140`.
- **Description:** All LLM calls go directly to OpenAI in the US. Under UK GDPR this is a "restricted transfer". It needs a legal safeguard (the UK-US data bridge, an International Data Transfer Agreement or the UK Addendum) and a data processing agreement. OpenAI can keep API data for up to 30 days for abuse monitoring unless "Zero Data Retention" is agreed.
- **Recommendation:** Confirm the agreement, the safeguard and the retention status (section 7), and add them to the privacy notice.

### M-13 No multi-factor sign-in, but admins can read all organisations
- **Topic:** 11, 9. **Confidence:** Confirmed.
- **Location:** `infra/infra/cognito_auth.py:27-46`; `backend/src/policy_atlas/api/routers/_access.py:210-233`.
- **Description:** The Cognito user pool has no multi-factor authentication (MFA: a second sign-in step after the password) and no threat protection (detection of risky sign-ins). The minimum password length is 8. An admin account can read every private task and chat in every organisation with only a password. Accounts can also start paid work with no quota.
- **Recommendation:** Require MFA, at least for admins. Turn on Cognito threat protection, and consider a minimum password length of 12.

### M-14 No procedure to give users a copy of their data
- **Topic:** 11. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/routers/me.py`; `api/contract/waitlist.py:3`.
- **Description:** UK GDPR gives people the right to a copy of their data (Article 15) and to take it elsewhere (Article 20). No export exists for tasks, chats, plans, waitlist entries and Langfuse traces, and no manual procedure is written down.
- **Recommendation:** Write a tested SQL or script procedure, keyed by user ID and email, that covers every table, Cognito and Langfuse.

### M-15 Metabase can reach the production database
- **Topic:** 11. **Confidence:** Likely (depends on the live settings).
- **Location:** `infra/infra/analytics_stack.py:28-30`, `:144-148`.
- **Description:** Metabase (the analytics dashboard) is deployed in staging and production, and it is allowed to connect to the main database "for a future curated read role". That read-only role is not in the code. If someone connected Metabase with the master account, every Metabase user could see emails, names and full chat transcripts. Metabase tracking and its AI features are off, and access is limited to an IP allowlist.
- **Recommendation:** Check the live Metabase data source. Create a read-only role that cannot read `app_user.email`, `waitlist_entry`, `chat_turn`, `task_agent_transcript` or free-text columns, or that reads only summary views.

### M-16 Only 7 days of backups; no snapshot before migrations
- **Topic:** 6. **Confidence:** Confirmed.
- **Location:** `infra/infra/database_stack.py:76`; `scripts/deploy.sh` (`run_migrations`).
- **Description:** Aurora keeps automatic backups for 7 days, and point-in-time restore works only in that period. No manual snapshot is taken before a migration. There is no AWS Backup plan and no copy in another account or region. If data is damaged and nobody notices for more than 7 days, it cannot be recovered.
- **Recommendation:** Keep backups for 14 to 35 days in production. Take a snapshot before `run_migrations`, and wait for it to finish. Consider an AWS Backup plan with a copy to another account or region.

### M-17 The Cognito user pool has no deletion protection
- **Topic:** 6. **Confidence:** Confirmed.
- **Location:** `infra/infra/cognito_auth.py:27-46`.
- **Description:** All tasks and projects are linked to the user's Cognito ID. The pool has `RemovalPolicy.RETAIN`, but `deletion_protection` is not set. Some infrastructure changes create a new, empty pool with new IDs. Users could then not sign in, and their work would not be reachable until someone fixed it by hand. Cognito has no backup feature.
- **Recommendation:** Set `deletion_protection=True`. Add a test that fixes the pool's logical ID. Consider a scheduled export of users (email and ID) to S3.

### M-18 Re-running `user enrol` resets a user's sharing settings
- **Topic:** 6. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/ops/commands.py:645-694`, `:1085-1121`, `:1124-1167`.
- **Description:** `user enrol` is the only command that changes a display name, so operators will run it again to fix a name. Each time, even when the user stays in the same organisation, it sets all the user's tasks and projects to private and deletes the links to colleagues' projects. It has no dry run and asks for no confirmation.
- **Recommendation:** If the organisation does not change, update only the name and email. Add a `user rename` command and a `--dry-run` option.

### M-19 Database transactions stay open during external calls
- **Topic:** 5, 12. **Confidence:** Confirmed (scope). The blocking effects are likely.
- **Location:** `backend/src/policy_atlas/runtime/runner.py:5805-5867`; `core/events.py` (`APPEND_ATTEMPTS = 32`); `evidence_search/sourcing/acquire.py:808-866`, `:1009`; `api/app.py:290-295`; `core/db.py:24`.
- **Description:** Each pipeline step runs inside one database transaction, which also covers the search, LLM and embedding calls. The transaction can stay open for minutes. Results of this:
  - A short database error late in a step loses the whole step.
  - The step keeps a connection for its whole duration.
  - Other writers on the same task wait, because of the event numbering. The retries were already raised from 5 to 32 for this reason.
  - The database clean-up process (autovacuum) is blocked.
  - Progress is not visible until the step commits.

  Also, the database settings have no `connect_timeout`, `statement_timeout` or `idle_in_transaction_session_timeout`, and short database errors are not retried.
- **Recommendation:**
  1. Commit in stages, and do not make external calls inside a transaction.
  2. Number the events from a counter for each task.
  3. Add connection and statement timeouts and `pool_recycle`.
  4. Retry short write transactions after temporary errors.

### M-20 If the key download fails, every user is signed out
- **Topic:** 12. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/auth.py:76-79`, `:100-118`, `:206-208`; `api/settings.py:37`.
- **Description:** The API keeps Cognito's public keys for 5 minutes. When this time ends, the next download must succeed. If Cognito or the network fails for a short time, the API does not use the old keys, which are still valid. Every request then gets 401, and the frontend signs users out. The log shows `auth.token_rejected` with no reason, so an outage looks like a lot of bad tokens.
- **Recommendation:** Keep using the old keys when a download fails, and wait a short time before the next try. Log download failures as errors, separately from token failures.

### M-21 Web server settings cause occasional 502 errors
- **Topic:** 7, 12, 5. **Confidence:** Confirmed (settings). The 502 effect is documented AWS behaviour.
- **Location:** `backend/Dockerfile:47`; `infra/infra/network_stack.py:114`.
- **Description:**
  - **Keep-alive:** Uvicorn closes idle connections after 5 seconds, but the load balancer keeps them for 120 seconds. The load balancer sometimes uses a connection that Uvicorn has closed, and the user gets a 502 error. POST requests such as "start run" then fail where the user can see it.
  - **Proxy headers:** Uvicorn does not trust the load balancer's forwarded headers, so the logs do not show the real client IP address, and redirects point to `http://`.
  - **Server header:** Uvicorn sends `server: uvicorn` in each response.
  - **Long LLM routes:** they can take longer than the load balancer's 120-second limit, so the user gets a 504 error while the server keeps working.
- **Recommendation:**
  1. Add `--timeout-keep-alive 125 --proxy-headers --forwarded-allow-ips='*' --no-server-header`. Trusting all forwarded IPs is safe here because only the load balancer can reach the container.
  2. Make long LLM routes return 202 and send the result over the progress stream.

### M-22 Search retries and rate limits are incomplete
- **Topic:** 12, 5. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/evidence_search/sourcing/search_live.py:194-245`, `:300-304`, `:819`, `:1033-1038`; `api/deps.py:156-168`.
- **Description:**
  - Connection errors and reset connections are not retried, so those search results are lost.
  - The retry delay is a fixed doubling with no random "jitter", so parallel threads retry together.
  - The `Retry-After` header from the provider is not used.
  - Each run has its own rate limiter. With N runs at the same time, the server sends N times the planned request rate to Overton and OpenAlex.
- **Recommendation:**
  1. Retry all `httpx.TransportError` errors.
  2. Add jitter, and use `Retry-After` up to a maximum.
  3. Use one rate limiter for each provider for the whole process.

### M-23 Pipeline step failures are logged without a stack trace
- **Topic:** 12. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/runtime/runner.py:5917-5925`, `:6043-6044`; `options_scoping/model_calls.py:64-68`; `evidence_search/extract/extract.py:2177-2178`; about 20 other places.
- **Description:** When a step fails, the log is a warning with the error type and up to 200 characters of the message, but no stack trace (the list of code lines that led to the error). Bugs and provider outages are then difficult to tell apart.
- **Recommendation:** Add `exc_info=True` at the backstop and at the other places that continue after errors. Fix H-06 first, so that the stack traces do not contain secrets.

### M-24 A new Python process starts for every document
- **Topic:** 5. **Confidence:** Confirmed (design). The size of the effect is likely.
- **Location:** `backend/src/policy_atlas/evidence_search/sourcing/ingest_full_text.py:25-61`, `:106`, `:796-870`.
- **Description:** Each document gets a new Python interpreter, which loads pymupdf, trafilatura, SQLAlchemy, the OpenAI SDK and pydantic again. That is probably 1 to 2 seconds of CPU per document, so several CPU-minutes for each run on a container with 2 vCPUs. At least 4 parsing processes compete with the API for the CPU. Downloaded documents also wait in memory.
- **Recommendation:**
  1. Use a long-lived pool of parsing workers, with a watchdog for timeouts.
  2. Move parsing to a small module that does not import SQLAlchemy or OpenAI.
  3. Limit the number of downloaded documents that wait in memory.
  4. Set the pool size from the real CPU count.

### M-25 Each open progress stream queries the database 2.5 times a second
- **Topic:** 5. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/routers/sse.py:163-188`, `:608-686`; `api/settings.py:38`; `frontend/src/store/useRunStream.tsx`.
- **Description:** Every open task tab, including tabs for finished tasks and hidden tabs, queries the database every 0.4 seconds and never stops. When the stream connects, it reads every event row of the task, with the full JSON (often thousands of rows), and then discards most of them.
- **Recommendation:**
  1. Filter by the needed event types in SQL.
  2. Query less often when no run is active, or use PostgreSQL LISTEN/NOTIFY (the database tells the server when new events arrive).
  3. Close the stream when the run is finished or the tab is hidden, and reconnect from the last cursor.

### M-26 Evidence and findings pages load the whole task, then cut one page
- **Topic:** 5. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/readmodels/repository.py:911-954`, `:968-1167`, `:1300-1365`, `:1608-1651`.
- **Description:** The evidence page loads every source with its full metadata and every screening and classification event, builds an object for each one, sorts them, and only then takes one page. The findings, decisions and source pages are similar, and they also have the H-14 problem. The frontend loads these pages again after each finished stage.
- **Recommendation:** Do the filtering, sorting and LIMIT/OFFSET in SQL. Store the reasons in the result rows instead of reading event data, and read only the metadata fields that are necessary.

### M-27 Task list runs 3 to 4 queries per task; indexes missing
- **Topic:** 5. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/routers/_common.py:380-405`; `core/schema.py`.
- **Description:** A task-list page of 50 rows runs about 150 to 200 queries (one set for each row), every 15 seconds during runs. Several tables are filtered by `task_id` but have no index that starts with it: `capability_run`, `runs`, `source_screening_result`, `source_tag`, `intervention_outcome_finding` and `implementation_context_finding`.
- **Recommendation:**
  1. Get the data for all rows of the page together, with `DISTINCT ON (task_id)` and grouped counts.
  2. Add indexes that start with `task_id`, for example `capability_run(task_id, started_at DESC)`.

### M-28 The hosting cannot scale past one server
- **Topic:** 5, 12. **Confidence:** Confirmed.
- **Location:** `infra/infra/policy_atlas_stack.py:192-201`; `infra/db_config.json`; `api/routers/runs.py:80-90`; `api/chat_turns.py:68`; `api/routers/task_agent.py:140-157`; `api/continuation.py:63-65`; `core/liveness.py`.
- **Description:** Several locks and stores are kept in the memory of one process: run start, live progress, turn locks and confirmation tokens. So the service can run only one container: 2 vCPUs and 8 GB for the API, the runs, the parsing and the chat. Nothing enforces the "one container" rule except the deploy script. The database is one `t3.medium` instance, a class that AWS recommends only for development and test. Deploys cause downtime.
- **Recommendation:**
  1. Short term: fix H-14, H-15 and M-24, and add a test that enforces the one-container rule.
  2. Longer term: move the locks into the database (advisory locks, LISTEN/NOTIFY) so that two or more containers can run.
  3. Use an `r6g` or `r7g` Aurora instance in production.

### M-29 Chat streaming uses a pool of about 6 threads
- **Topic:** 5, 12. **Confidence:** Confirmed (code). The thread count is the Python default.
- **Location:** `backend/src/policy_atlas/api/routers/conversations.py:845-851`.
- **Description:** Each streaming chat uses one thread from Python's default pool. On a container with 2 vCPUs that pool has about 6 threads. From the 7th chat stream at the same time, answers stop until a thread is free.
- **Recommendation:** Use an `asyncio.Queue` with `loop.call_soon_threadsafe`, as `TickHub` already does.

### M-30 The public waitlist can be spammed and shows who signed up
- **Topic:** 1, 2, 7, 9, 11. **Confidence:** Confirmed.
- **Location:** `backend/src/policy_atlas/api/routers/waitlist.py:24-67`; `api/contract/waitlist.py:21-65`; `frontend/src/views/splash/WaitlistForm.tsx`.
- **Description:** `POST /api/v1/waitlist` needs no sign-in. Its only spam protection is a hidden "honeypot" field. It has no rate limit, CAPTCHA or email check, so a script can add unlimited rows. The reply `409 already_registered` lets anyone test whether a given email address is on the list. The form has no privacy text next to it.
- **Recommendation:**
  1. Return the same 201 reply for duplicate emails.
  2. Add a WAF rate rule (H-03) and a CAPTCHA.
  3. Add one line of privacy text with a link next to the submit button.

---

## 6. Low findings

| ID | Topic | Title and description | Location | Recommendation |
|---|---|---|---|---|
| L-01 | 7 | **TLS policies use defaults.** The load balancer may still accept TLS 1.0/1.1. CloudFront uses `TLSv1.2_2019`. | `infra/infra/network_stack.py:125`; `policy_atlas_stack.py:289` | Set `ssl_policy=RECOMMENDED_TLS` and `minimum_protocol_version=TLS_V1_2_2021`, and test them. |
| L-02 | 7 | **Small web hardening gaps.** API responses have no `Cache-Control: no-store`. The load balancer does not drop invalid headers. There are no access logs for the load balancer or CloudFront. A download has no total time limit (a slow server can hold a slot). The fetcher can connect to any port. NAT64 addresses (`64:ff9b::/96`) are not blocked. | `api/app.py:191-199`; `network_stack.py:108-125`; `fetch_live.py` | Add `no-store`. Turn on `drop_invalid_header_fields` and access logs. Add a total download deadline (for example 120 s), allow only ports 80/443/8080, and block NAT64. |
| L-03 | 1, 11 | **The database connection does not check the server certificate.** `sslmode=require` encrypts but does not verify the server. `rds.force_ssl` is not set on the main cluster. The password is put into the URL without encoding. | `infra/infra/deploy_functions/load_secret/load_secret.py:20`; `database_stack.py:58-80`; `analytics_stack.py:256` | Use `sslmode=verify-full` with the AWS RDS certificate bundle. Set `rds.force_ssl=1`. URL-encode the user name and password. |
| L-04 | 1 | **Frontend packages are not checked for known vulnerabilities.** CI runs `pip-audit` only for Python. | `.github/workflows/verify.yml` | Add `pnpm audit --prod --audit-level high` or OSV-Scanner. |
| L-05 | 1 | **Build inputs are not pinned.** The verify workflow uses tag-pinned actions (`@v4`) and has no `permissions:` block. The Dockerfile uses floating tags (`python:3.12-slim`, `uv:0.9`). | `.github/workflows/verify.yml:20-91`; `backend/Dockerfile` | Pin the actions to commit IDs and add `permissions: contents: read`. Pin the images by digest, and use Dependabot or Renovate. |
| L-06 | 1 | **Sign-in failure logs are thin.** A rejected token is logged with no reason, IP address or user ID. The signed-in user ID is not added to the request logs. | `api/auth.py:207`; `api/app.py:171-176` | Log the error class and the source IP. Add `user_id` to the log context. Add an alarm on spikes. |
| L-07 | 1 | **The operator tool puts the email straight into a Cognito filter.** An email that contains `"` would change the filter. Only trusted operators can enter it. | `ops/commands.py:1268-1270`; `ops/cli.py:140-157` | Refuse emails that contain `"` or `\`. |
| L-08 | 3 | **The container can change its own code.** The root file system is writable, and the `app` user owns `.venv` and `src`. The code also uses `exec` to patch the pymupdf4llm library (it runs only the library's own source, so it cannot be exploited). | `backend/Dockerfile`; `policy_atlas_stack.py:127-169`; `ingest_full_text.py:92` | Copy the files as owned by root, set `readonly_root_filesystem=True`, and pin the base image by digest. Document the `exec`, or replace it with a monkeypatch. |
| L-09 | 13, 8 | **The Markdown export does not escape text.** LLM text and document titles go into the `.md` download unchanged. In another Markdown viewer, an injected image link could report that the file was opened, or show a phishing link. The text also skips `scrub()`. | `frontend/src/views/artefactPresentation.ts:313`, `:463-537`; `ArtefactDownload.tsx:22-28` | Escape the Markdown control characters, or remove links, images and HTML. Run the text through `scrub()`. |
| L-10 | 13 | **Nothing makes code use `safeHref`.** Today the only link built from data uses it, but nothing stops a future link that does not. | `frontend/src/lib/safeHref.ts`; `SourcesView.tsx:1069`, `:1089` | Add an ESLint rule or a test. |
| L-11 | 2 | **The Task Agent transcript has two different visibility rules.** The conversation is hidden from colleagues on one route, but its full content is readable on `GET /tasks/{id}/task-agent-turns`. | `api/routers/task_agent.py:1175-1215`; `api/routers/conversations.py:141-147`, `:199-203` | The product owner decides the rule, and then both routes follow it. |
| L-12 | 2 | **Making a task public can also publish a colleague's linked work.** An options scoping task copies the documents of a colleague's evidence search. If the owner makes it public, those documents become public too. | `api/routers/tasks.py:540-554`; `runtime/inherit.py:455` | Refuse to make a task public while a linked source task is not public, or leave the copied rows out of the public view. |
| L-13 | 2 | **A progress stream continues after the sign-in token expires.** The token is checked only when the stream opens. | `api/routers/sse.py:607-681` | Close the stream when the token expires, or limit how long a stream can stay open. |
| L-14 | 2 | **A lock is taken before the access check.** A signed-in non-owner who knows a task ID can briefly block the owner's planner turns. | `api/routers/task_agent.py:972-974` | Check access first. |
| L-15 | 2 | **The automatic "other user gets 404" test covers only GET routes.** | `backend/tests/api/test_api_conformance.py:265-292` | Add POST and PATCH routes to the test. |
| L-16 | 8 | **Chat quotes are shown before they are checked.** The model writes the quote text for chunk citations. | `runtime/chat_floor.py:196-212`; `frontend/src/views/workspace/chat/ChatMessages.tsx:293` | Run `QuoteMatcher` on these quotes before they are shown. |
| L-17 | 8 | **Other prompt injection issues.** Some prompts are not in use (V2 search) and have no "data, not instructions" guard. In batched calls, one document can try to change the scores of the others. A user can ask the model to show its system prompt (it contains no secrets). | `search_prompts.py:287-296`; `corpus/ranking.py:52-57`; `runtime/chat_prompt.py:79-86` | Add the guard before you use V2. Accept and record the batching risk. Add a confidentiality line only if the prompt wording is commercially confidential. |
| L-18 | 9 | **Some LLM calls have no output-token limit.** The loop limits keep the cost bounded, but the worst case is higher than necessary. | `synthesis/synthesis_backend.py` (9 calls, for example `:1946`); `synthesis/grounding_judge.py:327` | Set `max_completion_tokens` on each call. |
| L-19 | 10 | **Some 422 errors return raw Pydantic text.** It shows internal class names and the library version. | `api/routers/task_agent.py:1555`, `:1640`; `api/routers/check_ins.py:238`; `api/continuation.py:279`, `:418` | Build the message from `exc.errors()` (`loc` and `msg` only). |
| L-20 | 10 | **A local sign-in key is in git history.** `backend/.dev-issuer/dev-key.pem`, commit `a6424256`, branch `origin/demo-live-run-test-1`. It is only the local dev key, so it cannot sign in to staging or production. | git history | Delete the branch or remove the file from history. Make new local dev keys. |
| L-21 | 10 | **The operator script passes the database secret as a command argument.** Other users on the machine can see it with `ps`. | `scripts/ops_run.sh:68-80` | Pass the secret on standard input. |
| L-22 | 9, 10 | **`confirm_expired` gives a 500 error instead of 409.** `ApiConflict` raises `ValueError` for codes that are not in `_CONFLICT_CODES`. (Verified.) | `api/routers/check_ins.py:236`; `api/app.py:32-57`, `:80-81`; `frontend/src/lib/errors.ts` | Add `confirm_expired` to both lists. |
| L-23 | 11 | **The admin audit log is kept for only 30 days.** Admin email searches are also in the URL, so the access log records them. | `infra/infra/policy_atlas_stack.py:83-86`; `api/routers/_access.py:304`, `:313-345` | Send the admin audit events to a protected store that keeps them longer. Send `owner_email` in a POST body instead of the URL. |
| L-24 | 11 | **The warning banner does not mention personal data.** It says only "sensitive or confidential", but the Terms forbid personal data. The banner is not shown on the waitlist. | `frontend/src/views/SensitiveInfoBanner.tsx:35`; `TermsView.tsx:59` | Change it to "Do not enter personal, sensitive or confidential information". |
| L-25 | 6 | **A long migration is reported as failed while it keeps running.** `aws ecs wait` stops after about 10 minutes. If the operator then runs the deploy again, a second migration can start. | `scripts/deploy.sh:498-505` | Poll with a longer deadline, and refuse to start a migration while another is running. |
| L-26 | 6 | **Most schema downgrades delete data with no warning.** Deploys never run downgrades, but a manual rollback (or H-10) does. | for example `backend/alembic/versions/f1b6d3a8c2e5_*.py` | Refuse a downgrade if the column contains data. Keep "restore a snapshot first" as the documented rule. |
| L-27 | 6 | **Fonts bucket and operator scripts.** The fonts bucket has no versioning, and the licensed fonts are not in git. `dev_org_seed.py` and `ops_remove_scoping_tasks.py` have no environment check, and the production tunnel is also `localhost`. | `policy_atlas_stack.py:245-248`; `scripts/dev_org_seed.py:63`; `scripts/ops_remove_scoping_tasks.py:438` | Turn on versioning, or write down where the master copy is. Make the scripts refuse port 15432, or use `ops.environment.verify_environment`. |
| L-28 | 4 | **Deploy and image checks.** `deploy.sh` checks that the production `VITE_*` settings exist, but does not refuse `VITE_MOCK` or `VITE_DEV_TOKEN`. A deploy from a laptop with `VITE_MOCK=1` would serve the fake API. Nothing runs `scripts/image_layer_scan.sh`. Infra sets `LOG_LEVEL`, but the code ignores it. | `scripts/deploy.sh:535-546`; `scripts/image_layer_scan.sh`; `policy_atlas_stack.py:142`; `core/logging.py:41` | Refuse these settings and extend the guard test. Run the scan in CI. Read `LOG_LEVEL`, or remove it. |
| L-29 | 4 | **Code and dependencies that production does not use.** pandas is a production dependency, but only `scripts/evals` uses it. `types-psycopg2` is not used. One-off rename scripts and their tests (about 4,000 lines) still run in `make verify`. Old prompts (`synthesis_prompts_v6.py`, V2 search) ship in the production package. About 25 Python names and frontend exports are not used (listed in the agent report). The dev token issuer, the OpenAPI exporter and the stub corpus are in the image. | `backend/pyproject.toml:60`, `:98`; `scripts/rename_*.py`, `scripts/schema_manifest.py`; `evidence_search/synthesis/synthesis_prompts_v6.py`; `sourcing/search_generation.py:271-277` | Move pandas to an `evals` group, and remove `types-psycopg2`. Delete the rename scripts. Move the old prompts to `scripts/evals/`. Delete the unused names, and add `knip` or `ts-prune` to the frontend checks. Keep development tools out of the image. |
| L-30 | 4, 12, 5 | **Smaller reliability and efficiency items.** The event log is not protected against changes in the database (noted in a code comment). The chat evidence check starts a second call when the first times out, and a stuck "pending" status is never cleared. A failed step is retried at once, whatever the error. The browser progress client loses its position when the connection drops, and does not detect a silent stall. About 20 OpenAI clients are created for each planning request and never closed. Starting a run polls the database every 10 ms. Recharts is probably in the first download. | `core/events.py:6-7`; `api/chat_enrichment.py:386-405`; `runtime/runner.py:163`, `:1319-1350`; `frontend/src/api/sse.ts:118-121`; `api/deps.py:156-168`; `api/routers/runs.py:250-279`; `frontend/src/views/ThemesView.tsx:8` | Add a database trigger or REVOKE on `event_log`. Set the judge client timeout below 45 s with no retries, and clear stale "pending" rows. Retry only temporary errors, after a delay. Update the cursor for each frame and add a 45-second watchdog. Create the clients once at startup. Poll every 100 to 250 ms. Move `orderThemes` out of the chart module. |

---

## 7. Checks to do outside the code

The code cannot show these items. A person with access to the accounts must check them.

| Item | Why | Related findings |
|---|---|---|
| OpenAI: data processing agreement, transfer safeguard, Zero Data Retention, monthly budget and hard limit, usage alerts | UK GDPR transfer rules, and cost control | M-12, H-04, H-05 |
| Langfuse: who runs it, where it is hosted, retention setting, data processing agreement; is production in a separate project? | Full user content goes there | H-09 |
| Overton and OpenAlex: plan quotas and usage alerts | Cost and availability | H-04, M-22 |
| CloudWatch logs: search for `"locals"`, `api_key`, `password` and `dbadmin` | The local test confirmed that error logs include local variables | H-06 |
| Live Metabase data source: which database user does it use? | Possible access to PII | M-15 |
| Live Cognito: MFA setting and threat protection | Account takeover | M-13 |
| Live Aurora: is `rds.force_ssl` on? What is `max_connections`? | Encryption and capacity | L-03, H-16 |
| Data protection impact assessment (DPIA) and record of processing | The project's own documents say "NOT DONE" | H-07, H-08 |
| Is the repository or its deploy logs public? | Effect of L-20 and of any log output | L-20 |

---

## 8. What works well

The reviewers checked these areas and found them safe. Keep them working when you make changes.

- **SQL:** all queries use SQLAlchemy expressions or bound parameters. The few SQL strings built in code use only fixed names from the code. Sorting uses fixed values (`Literal`). JSON keys are fixed.
- **Authorization:** one central access module (`api/routers/_access.py`). Access is checked in SQL. A missing row and another user's row both give the same 404. Admins can read but not write. No route lets users change their own organisation or admin status. Request models refuse unknown fields (`extra="forbid"`). The tests check that every route needs sign-in.
- **Sign-in token checks:** the algorithm is fixed to RS256, the issuer is checked, `token_use` and `client_id` are checked, the key list is downloaded over HTTPS only, and the dev issuer cannot be turned on in the cloud. Cognito self sign-up is off.
- **Uploads and code execution:** no upload route. No `eval`, pickle, unsafe YAML, `subprocess` or template rendering of user content. The LLM tool calls can use only read-only tools from a fixed list. "Plan-as-data" accepts only components from a fixed list.
- **SSRF protection:** only http and https; every resolved IP address is checked, and the connection uses the checked address; each redirect is checked again; proxy settings from the environment are ignored; cookies are off; downloads have size and time limits.
- **Web set-up:** CORS allows one exact origin with no credentials. Cross-site request forgery does not apply, because sign-in uses a header, not cookies. The API documentation pages are off in production. API error responses are generic.
- **Frontend:** no raw HTML is inserted anywhere, links go through `safeHref`, CSV export protects against spreadsheet formulas, and there are no source maps in production.
- **Prompts:** untrusted text is fenced as data, LLM output is checked against strict Pydantic models, and IDs are checked against the input. Steering changes must pass a strict grammar and a user confirmation step.
- **Data:** the database has deletion protection, a final snapshot when it is deleted, and encryption. Migrations run in one transaction while the API is stopped. There are no ON DELETE CASCADE rules and no hard-delete routes. Data stays in the AWS London region. Cognito holds all passwords.
- **Secrets:** no live keys in the repository. Secrets reach the container through Secrets Manager. The search errors and the httpx logs hide API keys.
