# Verification: 068-ops-announcements, part 068a (send)

Evidence for the build of part 068a. Part 068b (receive) is not built. Contract:
[contract.md](contract.md) revision 3 with the picture-switch ruling. Plan: [plan.md](plan.md).

> **State:** build complete except the owner's polish pass and the staging live checks
> (§ Known unverified items).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` at build-open (Phase 0) | pass, with 2 load failures | 4,993 backend tests passed. `tests/runtime/test_option_search.py::test_option_searches_run_at_the_configured_width` failed (9 == 10) and one frontend test timed out at 5 s. Three test suites ran on the machine at the same time. Both pass alone (3 runs of 29; 43 of 43). Not this task's code. |
| `make verify` after Phase 1 (schema) | pass, with the same 1 load failure | 4,997 passed; the timing test passed alone. `make` stops at the first failure, so the remaining steps ran one by one: typecheck, lint, eval-check, infra tests, audit-paths, rules-check, prompt-guard, font-guard, drift-check, frontend-verify: all pass. |
| `make verify-fast` after Phases 2, 3, 4, 5 | pass | Phase 5: 5,048 passed. The timing test failed once in Phases 2 and 3 and passed alone. |
| `make openapi-sync`, `make drift-check` | pass | After Phases 4 and 5 and after the field-name change. |
| `make -C infra test` after Phase 8 | pass | 178 tests. |
| `make frontend-verify-fast` after Phase 6 | pass | 151 files, 2,041 tests. |
| `make verify` on the simplified code | pass | 5,086 backend tests, typecheck, lint, 178 infra tests, guards, drift check, 2,052 frontend tests and the build. No load failure this time. |
| `make verify` at the step-6 exit, after the Codex fixes (`6b53bdc1`) | pass | Exit 0. 5,112 backend tests, typecheck, lint, 178 infra tests, guards, drift check, 2,053 frontend tests and the build. Another checkout ran its suite at the same time; no load failure. |

Every backend run used its own test database (`TEST_DATABASE_URL=…/policy_atlas_068_test`
or `…_068v_test`), because other checkouts ran tests on the default one.

## Checks beyond the build

- **Deterministic tests:** listed by rubric row in § Rubric status. No AI eval applies.
- **Manual / browser:** the ops pages against the mock, screenshots at 1280 and 400 wide
  (build and polish rounds). The unsubscribe page, signed out, against intercepted
  answers: every state at 1280 and 400 wide; the token left the address bar and each POST
  went out with no `Referer` header.
- **Live checks on staging (contract § Acceptance checks):** **not run in the build.**
  They need a deploy, which is the owner's. See § Known unverified items.

## End-to-end command

The contract pins the live end-to-end thread to staging (ten checks, about 45 minutes).
That needs a deploy and is **not run** in the build. What ran locally, at the widest
scope that needs no AWS account:

```bash
# Backend: a send through the route, the sender after the commit, start-up resume,
# and the public unsubscribe routes (in-memory mailer, real database).
cd backend && DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_068_test \
  uv run pytest \
  "tests/api/test_ops_announcements_router.py::test_a_send_records_everything_and_the_sender_runs_after_the_commit" \
  "tests/api/test_ops_announcements_router.py::test_ops_start_up_with_a_mailer_finishes_pending_rows" \
  tests/api/test_email_preferences.py -q -p no:xdist
# 21 passed

# Frontend: the annex's five scenes against the mock, and the unsubscribe page.
cd frontend && pnpm vitest run src/ops/views/announcements.journey.test.tsx src/views/unsubscribe
# 2 files, 11 tests passed
```

To look at the pages by hand:

```bash
cd frontend && VITE_MOCK=1 pnpm exec vite --config vite.ops.config.ts --port 5288 --strictPort
# http://localhost:5288/announcements            (the ops pages against the mock)
# http://localhost:5288/announcements?mock=list-changes   (the "list changed" dialog)
cd frontend && pnpm exec vite --port 5377 --strictPort
# http://localhost:5377/unsubscribe?token=x      (arrive state; the buttons need the API)
```

## Diff summary

What exists after the build, by contract step:

- **A. Tables, rules, mail seam, layout.** Migration `6727acd9234c` (two `app_user`
  columns, tables `announcement` and `announcement_recipient`, `pa_ops` grants).
  `ops/mail.py`: the `Mailer` seam, `SesMailer`, `MemoryMailer`, `render_announcement`,
  with the layout in `ops/announcement.html`. `ops/announcements.py`: recipient rules,
  fingerprint, create, the background sender, retry, resume at start.
- **B. Ops routes.** `api/routers/ops_announcements.py`, seven routes; the mailer is
  built in the ops lifespan only.
- **C. Public unsubscribe.** `api/routers/email_preferences.py`; the access-log filter.
  `frontend/src/views/unsubscribe/UnsubscribeView.tsx`, routed outside the sign-in guard.
- **D. Ops pages.** `frontend/src/ops/views/Announcement*.tsx`, the mock handlers.
- **E. AWS setup.** `infra/infra/components/email.py`; three switches in `pa_config.json`.

### Flagged deviations (minor, resolved inside the contract's intent)

1. **Update grant by column.** The contract says `SELECT, INSERT, UPDATE` on
   `announcement_recipient`. Built: `SELECT, INSERT` on the table and
   `UPDATE (email, status, reason, updated_at)`. Narrower: `pa_ops` cannot rewrite a row's
   key. It matches every other `pa_ops` update grant and the pin test's shape.
2. **A line break in the subject is refused**, not escaped. Rubric row 12 reads as if it
   were escaped in the HTML. A subject is a header, and the contract refuses a line break
   in a header. The route answers 422.
3. **The claim is one transaction, not one statement** (contract B5 wording). The plan's
   decision 4 requires the account row to be locked in the same transaction.
4. **Picture hosting has its own switch, `email.pictures`** (owner ruling during the
   build, recorded in the contract). With one switch, the rollback of sending removed the
   CloudFront path and broke pictures in sent emails.
5. **Local development has no mailer.** The contract says the in-memory mailer "serves
   local work, the mock journey and tests". Built: tests use it; local ops pages use the
   frontend mock; a local ops server without the sender settings answers 503, as rubric
   row 11 requires. A stand-in mailer for a local server is not built.
6. **A failed test send answers 502** with code `upstream_failed` and a short failure
   code. The plan's route table did not name it. A 502 from an `HTTPException` used to
   map to `internal`; this route is the only one that raises it.
7. **A field rule answers 422 with code `invalid_message` and `details.field`**, so the
   page shows the message under the right field. The plan said 422 only.
8. **The privacy text is not written in this branch.** Task 069 (PR #151, open) already
   carries the text about email, product updates, the unsubscribe link and SES. The
   contract says to build on it and not to write a second version. Before the merge:
   rebase on #151 and check its wording against what was built (rubric row 23).
9. **`docs/deferred.md` and `docs/knowledge/` are not written in the build**, although
   plan Phase 10 lists them. The build skill gives them to step 8, against the final code.
   The candidates are in § Review handoff.

### Things the build found

- Python's standard library folds a header longer than 78 characters. It turned
  `List-Unsubscribe: <https://…>` into an encoded word that mail providers do not read
  as a link. `SesMailer` writes the message with `policy.SMTP.clone(max_line_length=None)`.
  The SES test checks the raw bytes.
- Five existing tests delete every `app_user` row. They failed after the announcement
  tests ran in the same worker, because committed recipient rows point at users and the
  foreign key does not cascade (a sent email's record must not vanish with an account).
  Those tests now clear the recipient rows first.

## Simplification (build step 5c)

Four read-only reviewers (reuse, simplification, efficiency, layering) read
`git diff dev...HEAD` for the product code. Two agents applied the fixes. No route,
status code, JSON shape, schema, IAM statement or user-facing word changed; the generated
OpenAPI files show no change. Checks after it: `make verify-fast` (5,048 passed) and
`make frontend-verify-fast` (2,052 passed), both builds.

**Applied, backend** (commit `e73664f0`):

- `create_announcement` and `retry_failed` return the audit row's id and the counts they
  already hold. The route no longer looks the id up again or counts the rows again.
- `failure_code` is public in `ops/mail.py`. `queue_log` and `audit` are public in
  `routers/ops.py`; the test and picture routes use `audit`.
- `in_background` moved to `core/background.py` with the log event name as an argument.
  A sender that crashes now logs `announcement.sender_crashed` (the one new event name).
- The access-log filter moved to `core/logging.py`; `configure_logging()` installs it.
  It still matches only the two unsubscribe paths.
- `get_optional_mailer` in `api/deps.py`: one way to reach the mailer.
- The detail route reads the suppression list only when at least one row is `sent`.
- The picture store is built once at start-up, not for each upload.
- `build_recipients` returns the audience summary on the list; one query fewer.
- The six message fields are named once (`dataclasses.fields(Message)`).
- `html.escape` is called directly; `AnnouncementKind` is `mail.Kind`.

**Applied, frontend** (commit `b23c6bf8`):

- `ChoiceRow` moved to `ui/brand/ChoiceRow.tsx`; the ops pages no longer import from the
  public app's workspace view.
- `LIVE_MS` moved to `announcementParts.tsx`.
- One `serverSentence` helper and one `DraftInput` component on the compose page. The
  rendered markup was compared before and after: identical.
- The audience lists and the result table's sort are memoised; one collator.
- Mock: one constant and one helper for values that appeared twice; the 409 uses `apiError`.

**Found, not applied:**

- *The fingerprint sorts lines that are already in order.* Not applied: the sort is by
  the whole line, not by user id, so removing it changes the value for some ids.
- *Validate the message before the suppression list is read.* Not applied: a send with a
  bad field and an unreadable list would answer 422 where it now answers 503.
- *Reuse `rememberedChoice` for the unsent text.* Not applied: it has no "remove".
- *Reuse `NameList` in the "See the list" dialog.* Not applied: its container differs,
  so the look would change.
- *One store factory in `core/uploads.py` for the task bucket and the picture bucket.*
  Structural; on the deferred list.
- *Write the unsent text after a short pause, not on each key press.* Small; on the
  deferred list.
- *Render the email once for an announcement, not once for each person.* Under one
  millisecond for each email against the 0.2 second pause.
- *A rest-destructure in the mock's list route.* The lint rule refuses it.

## Review findings

The full review stack runs in a fresh conversation (step 7). The owner approved one
Codex adversarial review in the build session (2026-11-26, read-only, on the simplified
code at `b23c6bf8`). It gave four findings. The lead checked each against the code; all
four are real and are fixed in the build. The fresh conversation should still judge the
fixes: their author is this session.

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | Blocker | A send error after SES may have accepted the email (a read timeout, a closed connection, a 5xx answer) was written as `failed`, so a retry could send a second copy (I1). The SDK's automatic retries could do the same inside one call. The existing test raised a `BaseException`, which never reached the handler. | Automatic retries off for the SES client. A row becomes `failed` only when the email provably did not go (it could not be built, no connection was made, or SES refused it with a 4xx answer). Any other error leaves the row `sending` ("Not confirmed") and the sender goes on. |
| 2 | Material | The limit of 5 emails a second held for each sender thread, not for the ops process. | One lock for the process around "send, then pause". |
| 3 | Material | When a sender thread stopped, rows still waiting had no action on the page. | The result page offers "Send to the N still waiting" when rows wait and the send is not live. New words: annex § Deferred polish, for the owner's pass. |
| 4 | Minor | The access-log filter missed odd forms of the two addresses (a double slash, upper case), so a token could be logged for a request that answers 404. | The filter matches the normalised path. |

Hardening idea, not taken: parse the button link and the picture address as URLs, not by
prefix. The input is the operator's own, the text is escaped, and the picture prefix is
the site's own origin.

Codex found these areas clean: the opt-out lock order (I3), no address or text in a log
(I2), the public routes, the picture path, the "test before send" rule and the
fingerprint after a 409, and the IAM statements.

Open for step 7: contract verifier · `/code-review` · security lane · design lane ·
human deep review.

## Rubric status

State at the end of the build. "Test" names the main test; "live" needs staging.

| Row | State | Evidence |
|---|---|---|
| 1 Contract A1 to E6 | Built, except what the rows below mark | § Diff summary |
| 2 `make verify`, drift check, infra tests, live checks | Local part holds; **live checks not run** | § Commands run |
| 3 No unapproved gated change | Holds | One new config key, `email.pictures`, by owner ruling. One new 422 code and one 502 mapping on the ops API (deviations 6 and 7) |
| 4 No generated file or secret edited by hand | Holds | Generated files only through `make openapi-sync`; § Public safety |
| 5 No test deleted, skipped or weakened | Holds | Two existing tests changed: the ops gate sweep skips the announcement routes (pinned by their own test); five environment tests clear recipient rows first |
| 6 Verification recorded | This file | |
| 7 Gaps and deferred seams listed | Listed here; `docs/deferred.md` at step 8 | § Review handoff |
| 8 Review stack | **Open** (fresh conversation). First Codex review ran: § Review findings | |
| 9 A1 | Holds | `test_upgrade_gives_each_existing_person_a_distinct_token`; `test_pa_ops_grants_are_exactly_the_contract_list`; `test_pa_ops_refuses_ungranted_statements`. Update grant by column (deviation 1) |
| 10 A2 | Holds | `test_example_audience_gives_82_chosen_79_for_an_update_and_81_for_a_notice`; `test_a_person_is_left_out_for_the_first_reason_that_applies` |
| 11 A3 | Holds | `test_api_mode_builds_no_mailer_even_with_the_sender_settings`; `test_without_a_mailer_the_sending_routes_answer_503` |
| 12 A4 | Holds, with deviation 2 | `tests/ops/test_mail.py` |
| 13 B1 | Holds | `test_preview_gives_the_example_counts_and_reasons_and_writes_nothing` |
| 14 B2 | Holds | `test_a_test_goes_only_to_the_operators_own_address_with_the_sample_token` |
| 15 B3 | Holds | `test_a_png_and_a_jpeg_are_stored_and_their_address_returned`; `test_a_picture_that_breaks_a_rule_is_refused_and_nothing_is_stored` |
| 16 B4 | Holds | `test_a_send_records_everything_and_the_sender_runs_after_the_commit`; `test_a_changed_list_with_the_same_count_answers_409_and_inserts_nothing` |
| 17 B5, I1 | Holds after the Codex fix | `tests/ops/test_announcements.py`; `test_ops_start_up_with_a_mailer_finishes_pending_rows` |
| 18 B6 | Holds | `test_the_detail_shows_a_sent_row_bounced_after_the_send_and_stores_nothing`; `test_the_detail_answers_with_the_flag_when_the_suppression_list_cannot_be_read` |
| 19 B7, I1 | Holds | `test_retry_sends_the_failed_rows_and_leaves_sent_and_sending_alone`; the page words a stale `sending` row "Not confirmed" |
| 20 I2 | Holds | `test_no_log_line_or_audit_row_holds_an_address_the_subject_or_the_body`; `test_logs_and_audit_rows_of_a_send_hold_no_address_or_subject` |
| 21 I3, C1 | Holds | `test_a_service_notice_reaches_people_who_unsubscribed_or_have_not_signed_in`; `tests/api/test_email_preferences.py` |
| 22 C2 | Holds | `frontend/src/views/unsubscribe/UnsubscribeView.test.tsx` (10 tests) |
| 23 C3 | **Open: a merge gate** | The text is in PR #151; the approval record is the owner's (deviation 8) |
| 24 D1 to D4 | Holds | `announcements.journey.test.tsx` "plays the five scenes" |
| 25 E1 | Holds | `test_ops_role_may_send_only_as_updates_and_read_suppressions_and_the_api_role_has_no_ses` |
| 26 E2 | Holds | `test_announcement_settings_reach_only_the_ops_container_and_only_when_switched_on` |
| 27 E3 | Holds | `test_picture_bucket_is_private_read_only_by_the_site_distribution_and_ops_may_only_add`; `test_rolling_back_sending_keeps_the_pictures_served_and_removes_every_send_right` |
| 28 E4 | Holds | `test_one_dmarc_record_for_the_sender_domain_only_when_email_is_enabled` |
| 29 E5 | Not in 068a | Part 068b |
| 30 E6 | Document written; **live part open** | `infra/DEPLOYMENT.md` § Announcement email from the ops pages |
| Polish passes | Agent pass done; **owner pass open** | Annex § Polish log, § Deferred polish |

## Intent & assumptions

- "Sent" means SES accepted the email. Nothing tracks delivery or opening.
- A row is `sending` before SES is called. A server that stops in between leaves the row
  `sending` for ever ("Not confirmed"); no code sends it again (invariant I1).
- The sender sends at most 5 emails a second, one thread for each announcement. The
  ceiling is about 1,000 recipients (`# ponytail:` comment in `send_pending`).
- The suppression list is read in full on every preview and send (`# ponytail:` comment
  in `SesMailer.suppressed`).

## Known unverified items

- **All ten staging live checks.** Not run. They need: a deploy of the code and the
  migration; `email.pictures` and `email.announcements` set true; the checks before the
  deploy in `infra/DEPLOYMENT.md`.
- **Whether the firewall passes a mail provider's one-click POST** (plan open point 1).
  The firewall is in block mode with the AWS common rule set, which blocks a request
  with no `User-Agent`. Only live check 2 shows it.
- **`ses:SendEmail` for a raw send.** The SES version 2 API sends raw content through
  `SendEmail`; the role has no `ses:SendRawEmail`. Live check 1 proves it.
- **The picture resize in the browser** (canvas, at most 1200 pixels wide) has no
  automated test: the test browser cannot run a canvas.
- **The DMARC record** is created at the next deploy of each environment, because
  `email.enabled` is already true. Not yet deployed.
- **Data Protection Officer's approval** (rubric row 23): the owner states it was given;
  the record and the final wording go here before the merge.

## Public safety

No email address of a person, no unsubscribe token and no message text is in the diff or
in a quoted log. Test data uses `example.org`, `example.com`, `example.net` and
`example.test` addresses and invented names. One address is committed on purpose: the
reply address `discoveryhub@nesta.org.uk` in `infra/pa_config.json`, the unsubscribe page
and the annex (contract § Two parts).

## Review handoff (step-7/8 inputs)

**Executor provenance** (the lead wrote every brief and reviewed each diff before the
commit; Claude built everything, so Codex anchors the review):

| Files | Executor |
|---|---|
| `core/schema.py`, migration `6727acd9234c`, `test_migration_announcements.py`, `test_pa_ops_login.py` | `deep-reasoner` |
| `ops/announcement.html` (layout and words) | lead |
| `ops/mail.py`, `test_mail.py`, settings, `get_mailer`, the `boto3-stubs` extra | `deep-reasoner` |
| `ops/announcements.py`, `test_announcements.py`, `tests/ops/support.py` additions | `deep-reasoner` |
| `api/routers/ops_announcements.py`, contract types, lifespan wiring, `test_ops_announcements_router.py` | `deep-reasoner` |
| `api/routers/email_preferences.py`, `test_email_preferences.py` | `deep-reasoner` |
| `infra/infra/components/email.py`, `test_email.py`, synth test stacks | `deep-reasoner` |
| `frontend/src/ops/**` announcement pages, mock and tests; the agent polish pass | `frontend-designer` (two separate runs) |
| `frontend/src/views/unsubscribe/**`, the `/unsubscribe` routes | `frontend-designer` |
| The simplify fixes | `deep-reasoner` (backend), `frontend-designer` (frontend), to the lead's list |
| `InvalidMessage.field`, the `invalid_message` 422, the fix in `test_ops_environment.py`, `infra/DEPLOYMENT.md`, this file | lead |

**Adjudication items for the review:**

- The seven flagged deviations above that change behaviour or wording (1 to 7).
- A database error in the sender's result write ends the sender thread. Rows still
  `pending` then wait for a retry click or a restart; the page offers the retry button
  only when a row has failed.
- I3 wording: `pa_ops` cannot update the opt-out, but its table-wide INSERT on `app_user`
  (older migration) can create a new person who is already opted out. Harmless: it can
  never opt a person back in.
- A schema downgrade drops everyone's opt-out and token. After a later upgrade, people
  who unsubscribed are subscribed again and old unsubscribe links stop working.
  `infra/DEPLOYMENT.md` § Rollback says so.
- The public OpenAPI document lists a 422 for the two unsubscribe routes (the framework
  adds it); they answer only 204 or 404.
- `tests/api/test_ops_router.py`: the gate sweep skips `/api/v1/ops/announcement*`,
  because the new router's own test pins those routes. No assertion was removed.

**Knowledge candidates:**

- The standard library's `EmailMessage` folds long headers into encoded words; a
  `List-Unsubscribe` address needs `max_line_length=None` at serialisation. The refusal
  of a line break in a header value comes from the default policy at build time.
- SES version 2 refuses the unsubscribe headers on simple content; raw content carries
  them, through the same `ses:SendEmail` action.
- `ses:ListSuppressedDestinations` cannot be limited to one identity (resource `*`).
- Adding a column with a `gen_random_uuid()` default rewrites the table and gives every
  existing row its own value.
- `pa_ops` can run `SELECT … FOR UPDATE` on `app_user` because it holds column updates
  on that table; no extra grant was needed.
- A test that needs `pa_ops`'s grants under eight workers should use `SET ROLE pa_ops` on
  its own engine. The existing `pa_ops_engine` fixture switches the role's login on and
  off, and that switch is shared by every database on the server.
- A foreign key to `app_user` without `ON DELETE CASCADE` breaks the tests that delete
  every user, once another test commits rows in the new table.
- A stale `.mypy_cache` reported `Module "policy_atlas.ops" has no attribute "cli"`; a
  clean cache passed.
- A CloudFront behaviour and its bucket under one switch cannot be rolled back and
  forward without losing the objects' addresses: a retained bucket is not adopted again.
- uvicorn's access record is `(client, method, path with query, version, status)`; a
  `logging.Filter` on `uvicorn.access` can rewrite the third argument before formatting.
- The ops site's Content Security Policy allows `blob:` and `data:` images but not the
  public site's origin, so an ops page cannot show a stored announcement picture.
- Under load from parallel suites, `test_option_searches_run_at_the_configured_width`
  fails with a peak of 9 against 10, and `make verify` then stops before typecheck.

**Deferred candidates** (step 8 writes `docs/deferred.md`):

- The contract's Out list (drafts, scheduled send, templates, attachments, more pictures,
  tracking, email to people without an account, replies from the product addresses, an
  event stream for bounces, row-menu shortcuts, a "What's new" panel, a stricter DMARC
  policy, a shared team inbox, email the product sends by itself).
- Narrow the "no notification channel" entry: operator-sent email now exists.
- Unused pictures stay in the bucket. DMARC is at `p=none` with no report address.
- No stand-in mailer for a local ops server.
- One store factory in `core/uploads.py` for both buckets (found at simplify).
- The unsent announcement text is written to browser storage on each key press.
- The sender has no shutdown hook; a stop during a send can leave one "Not confirmed" row.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md), written at step 8 from the list
above.
