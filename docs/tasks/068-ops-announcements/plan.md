# Implementation plan: 068-ops-announcements

> Status: **draft 2, 2026-11-25.** The plan-stage adversarial review (Codex, read-only,
> 15 findings: 1 blocker, 11 material, 3 minor) is folded in (§ Folded findings). Awaits
> the owner's approval. Contract: [contract.md](contract.md) revision 2.
> Rubric: [rubric.md](rubric.md), 30 items. Annex: [design-annex.md](design-annex.md)
> version 1. ADR 0051: written when the owner approves this plan.
> Terms, items (A1 to E6), invariants (I1 to I3) and the ten live checks are the
> contract's and are not restated. The build runs in a fresh conversation with
> task-cycle-build, opening on Phase 0.

## Context

Five steps, built in the order they must land:

| Step | Switch | What exists after it | Phases |
|---|---|---|---|
| A. Tables, rules, mail seam, layout | none (code and migration) | the send logic, tested with the in-memory mailer | 1 to 3 |
| B. Ops routes | 503 until the sender settings exist | the ops API can preview, test, send, list, retry | 4 |
| C. Public unsubscribe | none | a person can stop and restart product updates | 5, 7 |
| D. Ops pages | the ops bundle | the operator's journey, against the mock and the real routes | 6 |
| E. AWS setup | `email.enabled` (E4) · `email.announcements` (E1 to E3) · `email.inbound` (E5) | real sending, pictures, DMARC, incoming email | 8, 9 |

Schema first, then the seam every later phase calls, then the logic, then the routes, then
the pages, then the infrastructure. Each phase ends with its tests green. Nothing sends a
real email before Phase 11.

## Decisions taken in this plan

Each names the existing code it reuses, or says that none exists.

1. **Module layout.** No SES code exists today.
   - `backend/src/policy_atlas/ops/mail.py` (new): the `Mailer` protocol, `SesMailer`,
     `MemoryMailer`, and `render_announcement`. `commands.py` is already past 2,600 lines,
     so the new logic does not go there.
   - `backend/src/policy_atlas/ops/announcements.py` (new): recipient rules, the
     fingerprint, the create, claim, send and retry functions. Each takes an open
     `Connection`, as every function in `commands.py` does, and records its audit row with
     the existing `commands.record_action`.
   - `backend/src/policy_atlas/api/routers/ops_announcements.py` (new): the B routes. It
     reuses `require_ops`, `after_commit`, `_queue_log` and the error mapping from
     `routers/ops.py` and is mounted beside it in ops mode only.
   - Request and response types go in the existing `api/contract/ops.py`.
   - The email layout is one HTML file beside `mail.py`, copied in look from
     `infra/email/invitation.html`. `infra/email/` is not in the backend image, so the
     file is not shared.
2. **Mailer injection.** Reuse the `Identity` pattern: built once in `_ops_lifespan`
   (`api/app.py`), kept on `app.state`, read through a `get_mailer` dependency in
   `api/deps.py` that answers 503 when the sender settings are absent. Tests override the
   dependency with `MemoryMailer`; `SesMailer` is tested with `botocore.stub.Stubber`, as
   the Cognito client is in `backend/tests/ops/support.py`.
3. **The raw email.** `email.message.EmailMessage` from the standard library builds the
   message (subject, From, To, both unsubscribe headers, a plain-text part and an HTML
   part). `sesv2.send_email(Content={"Raw": ...}, FromEmailAddress=...)` sends it. The
   default policy of `EmailMessage` raises on a line break in a header: that is the
   header-injection guard, and a test pins it.
4. **The sender.**
   - Thread: reuse `in_background` (`api/titles.py`); move it to a shared module if the
     ops code cannot import it without the public routers.
   - Start after the commit: `after_commit` in `routers/ops.py` today only writes log
     lines. It gains a second queue, `request.state.ops_after_commit`, of callables run
     after the log lines. The send and retry routes queue "start the sender".
   - Claim, in one transaction: (1) pick one `pending` row with `FOR UPDATE SKIP LOCKED`;
     (2) read that person's `app_user` row **with `FOR UPDATE`**, so an unsubscribe or a
     deactivate that runs at the same moment waits; (3) write `sending`, or `left_out`
     with the reason; (4) commit. The commit of this transaction is the moment that
     decides: a change to the account before it stops the email, a change after it does
     not. `pa_ops` can lock the row because it holds column updates on `app_user`; Phase 1
     proves it in the `pa_ops` test.
   - Then call the mailer, then write `sent` or `failed` in a second transaction.
   - Rate: a 0.2 second pause between emails, with a `ponytail:` comment that names the
     ceiling (about 1,000 recipients, one sender) and the upgrade (a queue).
   - Start-up: `_ops_lifespan` calls `announcements.resume_all(engine, mailer)` after the
     mailer is built. It starts one sender for each announcement with `pending` rows.
   - Each sender uses its own connections from the ops engine (the `pa_ops` login).
5. **The fingerprint.** SHA-256 over the lines `user_id|email|status|reason`, sorted by
   `user_id`. Computed by the same function for B1 and B4.
6. **The suppression list.** `sesv2.list_suppressed_destinations`, all pages, into a dict.
   B1 and B4 read it once per request. B6 reads it with `StartDate` set to the send time.
   A `ponytail:` comment names the ceiling (a list of thousands) and the upgrade (a cache
   or the event stream).
7. **The public routes.** A new `api/routers/email_preferences.py`, mounted in API mode
   only, beside `waitlist_router`. No dependency on sign-in. The routes read the token
   from the query string and run one `UPDATE ... WHERE unsubscribe_token = :t`.
   - Token out of the log: uvicorn's access log prints the request target with its query
     string. A `logging.Filter` on the `uvicorn.access` logger, installed once in
     `create_app`, matches only the two route paths, replaces only the query part of the
     request-target argument before the record is formatted, never logs the original, and
     leaves every other line as it is. The test feeds it a real `uvicorn.access`
     `LogRecord` and builds the app twice to show that the filter is installed once.
   - The structured request log in `app.py` is checked the same way.
   - The firewall: only the rate rules and the managed groups stand in front
     (`infra/infra/components/waf.py`). Live check 2 proves that a mail provider's POST
     passes: Gmail's own Unsubscribe button, a form POST to
     `/api/v1/unsubscribe?token=…` with no origin, expected answer 204. If a managed group
     blocks it, the fix is a scoped exception, and that is a stop-and-ask.
8. **The picture.** Reuse the `UploadStore` protocol, `S3UploadStore`, `LocalUploadStore`
   and `uploads.check` (leading bytes) from `core/uploads.py`. The existing
   `get_upload_store` always returns the task-upload bucket, so this task adds
   `get_announcement_image_store` in `api/deps.py`: built from the picture-bucket setting
   (E2), or a local folder in local work, and answering 503 when neither is set. Tests
   override it. A separate size limit of 1 MB for this route. The key is
   `email-images/<uuid4>.<png|jpg>`. The address returned is the public site address plus
   the key. A4 accepts a picture address only if it starts with that prefix.
9. **The frontend.**
   - Ops: `AnnouncementsView.tsx`, `ComposeAnnouncementView.tsx`, `AnnouncementView.tsx`
     under `frontend/src/ops/views/`; hooks in `ops/api.ts` in the existing
     `useQuery`/`useOpsAction` shape; routes in `ops/routes.tsx`; the section in
     `OpsShell.tsx`; mock handlers and the annex's example data in `ops/mock/`.
   - Picture resize: a canvas and `toBlob`, no library.
   - Unsent text: `localStorage`, read and written inside `try`/`catch`.
   - Public: `frontend/src/views/unsubscribe/UnsubscribeView.tsx`, routed beside
     `/privacy` in both route lists in `routes.tsx`, with
     `<meta name="referrer" content="no-referrer">` set while the page is shown.
10. **The infrastructure.** One new construct file, `infra/infra/components/email.py`,
    called from `policy_atlas_stack.py`:
    - Switches: `email.enabled` (exists) controls E4; `email.announcements` controls E1
      to E3; `email.inbound` controls E5. The synth tests cover each on and off.
    - E1: two `PolicyStatement`s on the ops task role: `ses:SendEmail` on the identity
      with the condition `ses:FromAddress` equal to `updates@<sender domain>` (AWS
      documents this condition for raw sending too), and `ses:ListSuppressedDestinations`
      on `*`. Both are pinned by synth tests.
    - E3: the bucket (kept on stack removal), a second origin with origin access control,
      and the `/email-images/*` behaviour on the existing distribution. The distribution answers a
      missing object with the app's `index.html` (its existing error rule); a missing
      picture is therefore a broken image in the email, which is acceptable.
    - E4: `route53.TxtRecord`. No TXT pattern exists yet.
    - E5: `route53.MxRecord`; the bucket with a 14-day lifecycle rule (no lifecycle
      pattern exists yet), `RemovalPolicy.DESTROY` and `auto_delete_objects=True`, so
      that turning `email.inbound` off removes it together with any email still in it
      (at most 14 days; the copies in the team inbox stay).
    - The receipt rule set and its one rule: `tls_policy=REQUIRE`, `scan_enabled=True`,
      recipients exactly the two addresses, the store action first and the forwarder
      action second (asynchronous invoke).
    - The policies are written by hand, not left to the CDK actions' defaults: the bucket
      policy lets `ses.amazonaws.com` put objects only with `aws:SourceAccount` equal to
      the account and `aws:SourceArn` equal to this rule; the Lambda permission has the
      same two conditions. A synth test asserts each condition.
    - The forwarder: a `_lambda.Function` with
      `Code.from_asset("infra/deploy_functions/forward_email")`, the pattern of
      `load_secret` in `database_stack.py`, with `reserved_concurrent_executions=2`.
      Lambda retries a failed asynchronous run twice; the contract accepts that a retry
      can forward one email twice (E5).
    - Activation: an `AwsCustomResource` with a fixed physical id, created after the
      rule. On create and update it calls `setActiveReceiptRuleSet` with the set's name;
      on delete it calls it with no name. Its role holds `ses:SetActiveReceiptRuleSet` on
      `*` and nothing else. If the deploy role cannot create it, the fallback is one
      command in `DEPLOYMENT.md`, and the owner approves the change of wording first.
    - The team address: SSM parameter `/policy_atlas_v3/email/forward_to`, created by
      hand, read by the forwarder at each run.
    - The existing test `test_cognito_email_creates_no_ses_identity_or_dkim_record` stays
      true: this task creates no identity and no DKIM record.
11. **The forwarder code** is plain Python with `boto3` (present in the Lambda runtime)
    and the standard library's `email` package.
    - It reads the SES event, takes the message id, and reads the object
      `<prefix><message id>` from the bucket.
    - Size: it asks for the object's size first. Above 25 MB (SES sends at most 40 MB
      after encoding) it sends the short notice (sender, subject, size) instead of the copy.
    - An error raises, so Lambda retries; nothing is caught and hidden.
    - Unit tests run under `infra/tests/` with fixture emails and a stubbed client: each
      drop rule, the headers of the copy, a line break in a name, a size just under and
      just over the limit.
12. **`scripts/deploy.sh`** does not change. If Phase 8 or 9 shows that it must, that is a
    stop-and-ask (the CI and deploy gate).

## Gate map (binding)

| Boundary | Check |
|---|---|
| Phase 0 (build-open) | `make verify` |
| Phase 1 (schema) | `make verify` |
| Phases 2, 3 | `make verify-fast` |
| Phase 4 (routes) | `make verify-fast`, `make openapi-sync`, `make drift-check` |
| Phase 5 (public route) | `make verify-fast`, `make openapi-sync`, `make drift-check` |
| Phases 6, 7 (frontend) | `make frontend-verify-fast` |
| Phase 8 (infra) | `make -C infra test` |
| Phase 9 (infra, incoming email) | `make verify`, and `make openapi-sync` with `make drift-check` once more |
| Phase 12 (exit) | `make verify` |

Phases 2 and 3 share one reason for the fast gate: new files, no schema contact after
Phase 1, no reader of an existing table changes. Each phase ends with a commit on
`task/068-ops-announcements`.

## Deploy order (binding for Phase 11)

For staging first, then production after the merge:

1. **Preconditions, checked by hand and recorded:**
   - `aws sesv2 get-account`: production access is on; the account suppression list covers
     `BOUNCE` and `COMPLAINT`; the sending rate is at least 5 a second.
   - The sender identity shows DKIM as verified.
   - `aws ses describe-active-receipt-rule-set` returns no set.
   - The team-address parameter exists.
2. Deploy the code and the migration with both switches off (stop both services, migrate,
   start, as today).
3. Set `email.announcements` true and deploy. Run live checks 1 to 4, 6 and 7.
4. Set `email.inbound` true and deploy. Run live checks 5 and 8.
5. Run live check 9, then each rollback (check 10), then deploy forward again.

## Phases

Executor marks follow `docs/agentic-ops/harness.md`. The lead writes every brief and all
copy.

### Phase 0 — Build-open (`lead`)
`make verify` on the branch base. Read the three knowledge files the contract names.

### Phase 1 — Schema (A1) (`deep-reasoner`)
`core/schema.py`, one migration after `a3c9e1f7b2d4`, the grants, the `pa_ops` pin test.
A migration test: upgrade, every existing user has a distinct token, downgrade.
Done: rubric 9.

### Phase 2 — Mail seam and layout (A3, A4) (`deep-reasoner`; the layout text is `lead`)
`ops/mail.py`, the layout file, `get_mailer`. The approved development dependency:
`boto3-stubs` gains the `sesv2` extra in `backend/pyproject.toml`, the lock file is
regenerated, and the production image is unchanged (the group is not installed there).
Tests at the public functions:
`render_announcement` (escaping, lists, button rule, footers, headers by kind, plain-text
part), `SesMailer.send` against a stubbed client (raw content, one recipient), the
header line-break refusal. Done: rubric 11 (the API-mode half), 12, 20 (one recipient).

### Phase 3 — Rules, send, retry (A2, B4, B5, B7, I1 to I3) (`deep-reasoner`)
`ops/announcements.py`. Tests with `MemoryMailer` and the annex's example data: the
counts 82, 79 and 81; each reason and its precedence; the fingerprint, including the
same-count swap; create in one transaction; two senders, one copy; the check at the
send, with an unsubscribe and a deactivate that run against a claim in a second
connection; a mailer error; a failure after the mailer accepted; retry; `resume_all`.
Done: rubric 10, 16 (logic), 17, 19, 21 (the send half).

### Phase 4 — Ops routes (B1 to B7) (`deep-reasoner`, to the lead's route table below)
The router, the contract types, `after_commit`'s second queue, the lifespan wiring
(`get_mailer`, `resume_all`), the picture route, the ops OpenAPI document and types by
`make openapi-sync`. Tests at the routes: each route needs the ops role; 503 without a
mailer; the audit rows; no address in a log line; the 409; the detail overlay and its
flag. The ops-mode route test (`tests/api/test_service_role.py`) gains the new paths.
Done: rubric 11, 13 to 16, 18, 20.

### Phase 5 — Public unsubscribe routes (C1) (`deep-reasoner`)
The router, the access-log filter, the public OpenAPI document by `make openapi-sync`.
Tests: set, clear, repeat, unknown token, a GET changes nothing, the form POST with no
origin, the log line. The API-mode route test gains the two paths; the ops-mode test
asserts they are absent. Done: rubric 21.

### Phase 6 — Ops pages (D1 to D4) (`frontend-designer`)
Built to the annex and to § Ops pages: data rules below. The mock journey test plays the
five scenes. Then the two polish
rounds of task-cycle-build § Step 5b. Done: rubric 24.

### Phase 7 — Unsubscribe page and privacy text (C2, C3) (`frontend-designer`; copy is `lead`)
The page and its four states. The lead drafts the privacy text; the owner takes it to the
Data Protection Officer. The sign-off is a merge gate, not a build gate. Done: rubric 22;
rubric 23 at the merge.

### Phase 8 — Infra: send, settings, pictures, DMARC (E1 to E4) (`deep-reasoner`)
`components/email.py`, `pa_config.json` (`email.announcements` false in both
environments at first), the ops environment, the synth tests, the pin tests in
`test_service_wiring.py`. Done: rubric 25 to 28.

### Phase 9 — Infra: incoming email (E5) (`deep-reasoner`)
The MX record, bucket, rule set, activation, forwarder and its tests; `email.inbound`
false in both environments at first. Done: rubric 29.

### Phase 10 — Documents (E6) (`lead`)
`infra/DEPLOYMENT.md` (§ Deploy order above, the parameter, the rollbacks);
`docs/deferred.md` (the "no notification channel" entry narrowed; the contract's Out
list; the unused-picture limit; no alert on forwarder errors; DMARC at `p=none`); new
knowledge files for facts the build verified.

### Phase 11 — Staging and the live checks (`lead`, with the owner)
§ Deploy order, the ten live checks, each rollback once. Wall time about 45 minutes plus
deploys. The owner runs or approves each deploy.

### Phase 12 — Exit (`lead`)
`make verify`; `verification.md` complete. Then stop: the review runs in a fresh
conversation with task-cycle-review.

## Route table (lead-owned; Phase 4 and Phase 5 build to it)

Ops API, prefix `/api/v1/ops`, every route behind `require_ops`:

| Route | Body | Answer |
|---|---|---|
| `POST /announcements/recipients` (B1) | `kind`, `audience` | counts, `recipients[]` (user id, name, email, organisation, status, reason), `fingerprint` |
| `POST /announcements/test` (B2) | the message fields, `kind` | 204 |
| `POST /announcement-images` (B3) | `content_type`, `data_base64` | 201 `url` |
| `POST /announcements` (B4) | the message fields, `kind`, `audience`, `fingerprint` | 201 `announcement_id` · 409 `recipients_changed` with the B1 answer |
| `GET /announcements` (B6) | none | `items[]`: id, subject, kind, audience summary, sender's name, time, counts by status |
| `GET /announcements/{id}` (B6) | none | the announcement, `recipients[]` with the overlay, `suppression_unreadable` |
| `POST /announcements/{id}/retry` (B7) | none | 202 |

- `audience` is `{everyone: bool, cohort_ids: [], org_ids: [], user_ids: []}`; with
  `everyone` true the three lists must be empty.
- The message fields are `subject`, `body`, `button_label`, `button_url`, `image_url`,
  `image_alt`. Limits: subject 150 characters, body 10,000, button label 40, picture
  description 200.
- Errors follow `routers/ops.py`: 404 for an unknown id, `ApiConflict` for a refusal, 422
  for a field rule, 503 with no mailer or no picture store.

Public API: `POST /api/v1/unsubscribe` and `POST /api/v1/resubscribe`, query `token`,
answer 204 or 404.

## Ops pages: data rules (Phase 6)

| Thing | Rule |
|---|---|
| Query keys | `["ops","announcements"]` for the list; `["ops","announcements",id]` for the detail |
| Detail refresh | every 3 seconds while a recipient is `pending` or `sending` and the newest change is under 2 minutes old; otherwise none |
| After send and after retry | both keys are marked stale |
| Recipient preview | a mutation, run again 400 ms after the kind or the audience last changed; an older answer is dropped |
| "Test of the current text" | the page keeps a hash of all message fields and the kind at the moment the test succeeded; the send button is on only while the current hash equals it |
| Mock | one handler for each route above, with the annex's example data, including the 409 |

## Folded findings (plan-stage adversarial review, Codex, 2026-11-25)

| # | Finding | What changed |
|---|---|---|
| 1 | The check at the send did not lock the account row (blocker) | Decision 4: `FOR UPDATE` on `app_user`, the deciding moment named; Phase 3 test |
| 2 | The existing upload store always uses the task bucket | Decision 8: `get_announcement_image_store` |
| 3 | Three switches, not two | Context table; decision 10 |
| 4 | Receipt rule properties and narrow policies were left open | Decision 10: written by hand, each condition tested; open point closed |
| 5 | Lambda retries can forward twice | Accepted and stated; contract E5 amended |
| 6 | The large-email rule had no design | Decision 11: 25 MB, size read first, tests |
| 7 | The incoming bucket would block its own removal | Decision 10: destroy with its objects; contract rollback amended |
| 8 | Phase 9 needed the full gate | Gate map |
| 9 | The development dependency had no phase | Phase 2 |
| 10 | Activation by custom resource was vague | Decision 10 |
| 11 | The From-address condition is documented for raw sending | Decision 10; open point closed |
| 12 | The log filter was vague | Decision 7 |
| 13 | The pages' refresh and test-state rules were missing | § Ops pages: data rules |
| 14 | Route shapes are the lead's to fix | § Route table |
| 15 | The firewall point needs a named check | Decision 7; open point 1 below |

## Open points (🟡)

1. Whether the firewall's managed groups pass Gmail's one-click POST. Only staging can
   show it (live check 2). A block is a stop-and-ask.
2. Whether the deploy role can create the two custom resources (activation, and the
   emptying of the incoming bucket). Phase 9 synthesises them; the first staging deploy
   shows it. The fallback for activation is in decision 10.

## What the plan does not do

Nothing in the contract's Out list. No change to Cognito's email, to `scripts/deploy.sh`,
to the public Content Security Policy or the ops one, and no new runtime dependency.
