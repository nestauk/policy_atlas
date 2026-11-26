# Verification: 068-ops-announcements, part 068a (send)

Evidence for the build of part 068a. Part 068b (receive) is not built. Contract:
[contract.md](contract.md) revision 3 with the picture-switch ruling. Plan: [plan.md](plan.md).

> **State:** build in progress. Sections marked *(open)* are filled at the step-6 exit.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` at build-open (Phase 0) | pass, with 2 load failures | 4,993 backend tests passed. `tests/runtime/test_option_search.py::test_option_searches_run_at_the_configured_width` failed (9 == 10) and one frontend test timed out at 5 s. Three test suites ran on the machine at the same time. Both pass alone (3 runs of 29; 43 of 43). Not this task's code. |
| `make verify` after Phase 1 (schema) | pass, with the same 1 load failure | 4,997 passed; the timing test passed alone. `make` stops at the first failure, so the remaining steps ran one by one: typecheck, lint, eval-check, infra tests, audit-paths, rules-check, prompt-guard, font-guard, drift-check, frontend-verify: all pass. |
| `make verify-fast` after Phases 2, 3, 4, 5 | pass | Phase 5: 5,048 passed. The timing test failed once in Phases 2 and 3 and passed alone. |
| `make openapi-sync`, `make drift-check` | pass | After Phases 4 and 5 and after the field-name change. |
| `make -C infra test` after Phase 8 | pass | 178 tests. |
| `make frontend-verify-fast` after Phase 6 | pass | 151 files, 2,041 tests. |
| `make verify` at the step-6 exit | *(open)* | |

Every backend run used its own test database (`TEST_DATABASE_URL=…/policy_atlas_068_test`
or `…_068v_test`), because other checkouts ran tests on the default one.

## Checks beyond the build

- **Deterministic tests:** listed by rubric row in § Rubric status. No AI eval applies.
- **Manual / browser:** the ops pages against the mock, screenshots at 1280 and 400 wide
  (build and polish rounds). *(open: the unsubscribe page)*
- **Live checks on staging (contract § Acceptance checks):** **not run in the build.**
  They need a deploy, which is the owner's. See § Known unverified items.

## End-to-end command

*(open)*

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
  *(open: the page)*
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

*(open)*

## Review findings

Added after the review stack (step 7). The owner approved running the first Codex review
in the build session; its findings are recorded here. *(open)*

## Rubric status

*(open: filled at the step-6 exit)*

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
| `frontend/src/ops/**` announcement pages, mock and tests | `frontend-designer` |
| `InvalidMessage.field`, the `invalid_message` 422, the fix in `test_ops_environment.py`, `infra/DEPLOYMENT.md`, this file | lead |

**Adjudication items for the review:**

- The seven flagged deviations above that change behaviour or wording (1 to 7).
- `routers/ops_announcements.py` imports two private names (`_queue_log`,
  `_failure_code`) and looks the audit row's id up again after `create_announcement` and
  `retry_failed` (they do not return it).
- A sender that crashes is logged by the shared helper as `titles.background_failed`.
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
- `frontend/src/ops/views/ComposeAnnouncementView.tsx` imports `ChoiceRow` from the
  public app's `views/workspace/PartCard.tsx`.

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
- `in_background` lives in `api/titles.py` and logs under a titles event name.
- The sender has no shutdown hook; a stop during a send can leave one "Not confirmed" row.
- `ChoiceRow` shared between the public app and the ops pages by a cross-import.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md), written at step 8 from the list
above.
