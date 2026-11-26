# Verification: 071-self-signup-staging

Evidence for the build of parts A to D (steps 5 and 6). Part E (the staging switch and its
seven live checks) runs after the merge and is recorded here then. Terms are those of
[contract.md](contract.md) § Terms.

## Commands run

All test runs used a separate local Postgres for this task (container `pa071-db`, port 5433),
because other checkouts ran their suites on the shared one at the same time.

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, before any edit) | pass | 4,994 backend, 173 infra, 2,025 frontend tests. A first run was red with 30 "too many clients" errors from three suites on one Postgres; the rerun was green. |
| Phase 1 full check | pass | 5,015 backend tests. The backend suite and the other parts of `make verify` ran as two commands on the same tree. |
| Phases 2 to 5 fast check, each | pass | 4,986 / 5,002 / 5,025 / 5,028 backend tests; type check, lint, `make openapi-sync`, `make drift-check`; phase 4 also the infra tests (173). |
| Phase 6 full check | pass | 5,091 backend tests (the whole suite), then the non-frontend parts of `make verify`. |
| Phases 7 and 8 frontend check | pass | 2,041 frontend tests (149 files); type check; lint (0 errors, 1 older warning in `SplashField.tsx`). |
| `make verify` (exit, on the simplified code) | pass | On commit `c6a39a7f`: 5,091 backend tests, 173 infra tests, 2,041 frontend tests; type check, lint, build, drift check and the guards all green. |
| `make verify` (review baseline, commit `467435f6`) | pass | 5,091 backend, 173 infra, 2,041 frontend tests. |
| `make verify` (after the review fixes) | pass | 5,101 backend, 173 infra, 2,051 frontend tests; type check, lint, build, drift check and the guards green. The knowledge records were written during this run; `make okf-validate` was run again after them and is green. |

Command for the exit run (the test database is the only non-default):

```bash
COMPOSE_PROJECT_NAME=policy_atlas \
TEST_DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5433/policy_atlas_071_test \
make verify
```

Known flake, not from this task: `tests/ops/test_pa_ops_login.py` turns the cluster-wide
`pa_ops` login on and off, so a run that puts its tests on several workers at once can fail
with "tuple concurrently updated". It passed in every whole-suite run and passes alone.

## Checks beyond the build

- **Deterministic tests.** One focused test for each behaviour and invariant; the names are
  in § Rubric status. No AI eval (no inference in this task).
- **Mutation check (phase 6).** With the re-check under the link lock turned off, and then
  with the tick lock turned off, three tests failed as they should (the tick-lock test, the
  one-use-left test, the two-connection test). The code was restored.
- **Browser, mock mode.** The public form and the ops pages were opened in the mock app and
  captured at 1280 and 400 pixels wide (two rounds for the ops pages). Round 1 found two
  layout faults at 400 pixels (the tab row made the page wider than the screen; an email
  broke in the middle of a word); both are fixed.
- **Rollback rehearsal (E4, rubric 43).** On a scratch local database with one link and one
  redeemed request: `alembic upgrade head`, `alembic downgrade a3c9e1f7b2d4`, `alembic upgrade
  head`. After the downgrade the link table and the two request columns were gone and the
  request row was still there. **Parent revision: `a3c9e1f7b2d4`. This task's revision:
  `9c5cdd050525`.** The switch rollback is covered by the existing test
  `test_ops_self_signup_task_is_optional_and_cancelled` (the sweep loop does not start with
  the switch off).

## End-to-end command

Not run at build. The contract pins the live run to staging after the merge (E3, seven
checks, about 30 minutes). Locally the flow is covered at the boundaries: the public route
(`tests/api/test_waitlist.py`), the sweep on a real `pa_ops` login
(`test_pa_ops_sweep_redeems_a_request_through_an_invite_link`), and the pages against the
mock API.

## Diff summary

One migration, three operator features, one public field, one sweep change, the pages.

- **Schema (D1).** `invite_link`, `invite_link_cohort`, `waitlist_entry.invite_code` and
  `.invite_link_id`, two partial indexes, the `pa_ops` grants. `core/invite_code.py` makes,
  normalises and shows a code.
- **Cohorts at Add person and Approve (B).** Both routes take `cohort_ids`, resolve every
  cohort before the Cognito call, and add the memberships on the same transaction.
- **File check (C).** `POST /api/v1/ops/people/import-check` reads CSV text and answers rows
  and faults; it writes nothing. The page creates people one at a time through the existing
  route.
- **Invite links (D2, D6, D9).** Commands and four ops routes; `PUBLIC_APP_ORIGIN` on the ops
  container; Delete organisation counts links.
- **Public route (D3).** One `INSERT … ON CONFLICT DO UPDATE` with no `RETURNING`; the route
  reads no link.
- **Sweep (D5, D8).** One candidate statement, a tick-wide advisory lock, `redeem_request`
  with the link row locked first, the 15-minute wait, the reason on the Requests list.
- **Pages (A, B7, C4, D7, D8).** The public form reads `#invite=`; the ops pages get
  `CohortsField`, Add many, Invite links and the Requests line.
- **Docs.** `web-api.md`, `infra/DEPLOYMENT.md`, the living copy file, the email sentence.

### Deviations, flagged

1. **The code alphabet has 31 characters, not 32.** Digits without 0 and 1 are 8; letters
   without I, L and O are 23. The contract (D2) and plan now say 31. About 59 bits.
2. **The end date may be up to 91 days ahead on the server** (`INVITE_AHEAD_MAX`), so that
   "day 90, end of day, in the operator's time zone" passes. The page words still say 90.
3. **A second revoke is refused** with "A revoked link cannot be changed." The contract does
   not say.
4. **Requests refused for good are left out in the sweep's query**, before the limit of 200,
   not inside the loop as before. This keeps I5 for them too. It goes a little past seam 3.
5. **`redeem_request` checks more than seam 2 lists** under both locks: the request still
   carries this link's code, has no account, and is not rejected (I9; a new code can arrive
   through the public form between the query and the lock).
6. **A redemption writes one `invite` audit row plus one `cohort.add` row for each new
   membership** (actor `sweep`). Rubric 28's "one sweep audit row" is read as one `invite`
   row.
7. **The `ops.sweep_enrolled_elsewhere` log line** now names the organisation the person is
   already in. Its old value (the listed domain's organisation) has no source for a link
   request.
8. **Two older sweep tests changed their expected values** because of D5 rule 13:
   `test_sweep_retries_a_failed_row` (the second try is at +15 minutes) and
   `test_failed_attempts_spend_the_hourly_budget` (`skipped_for_cap` 1, not 2).
9. **Add person's 422 messages changed**: its email and name rules now come from
   `validate_person_fields`, so the generated schema shows no `minLength`/`maxLength` on the
   two fields. The status is still 422.
10. **The Waitlist table gained an Organisation column** (the organisation the person typed),
    as in the mock, because the annex puts the invite line "under the organisation".
11. **`scripts/ops_e2e_local.sh` sets `PUBLIC_APP_ORIGIN`**; the ops service does not start
    without it.
12. **`docs/deferred.md` is not written in the build.** The plan's phase 9 lists it, but the
    build skill reserves durable records for step 8. The entries are in § Review handoff.
13. **Seam 4 signature**: `invite_request_reason` lost its `invite_code` parameter in the
    simplify pass (its only callers always have a code).

## Simplification (build step 5c)

Four read-only reviewers (reuse, simplification, efficiency, altitude) read
`git diff dev...HEAD`; one agent applied the chosen fixes. Commit: `c6a39a7f`.

**Applied:** one `email_domain` reader (was written out three times); one grouped use
counter (was copied in two route helpers); one cohort-join function for the routes and the
sweep; `redeem_request` uses `invite_request_reason` for the link test, and that function
lost a dead parameter; a file line is validated once, not twice; the read-only file check no
longer refreshes every ops list; three small frontend repeats named once.

**Found, not applied:** see Deferred candidates in § Review handoff. Also left as taste or
out of the diff: a general `_refused` helper for the route error mapping (touches older
routes); moving `localDay` beside `dayKey` (touches the product app); the type of the create
dialog's mutation; a shared "lock an unrevoked link" helper.

## Review findings

The review stack ran on 2026-11-26 in a fresh conversation, on commit `467435f6`, after a
green baseline `make verify` (5,091 backend, 173 infra, 2,041 frontend tests). All product
code was written by Claude agents, so the Codex review is the anchor (family flip). The
review diff left out the generated files (`frontend/openapi*.json`, `frontend/src/api/gen`);
`make drift-check` covers them.

| Lane | Reader | Result |
|---|---|---|
| Contract verifier | `contract-verifier` (Opus) | No rubric row fails. 7 findings, 2 notes. |
| Security | a fresh Opus agent with an audit brief. The `agent-skills:security-auditor` subagent was not available in the session. | No critical, high or medium. 2 low, 4 notes. |
| Adversarial | Codex, read-only (thread `01a217bb-9750-7192-a2df-db1a64c8e1ab`), plus the first Codex run in § Review handoff | 4 findings and 1 test gap; 4 from the first run. |
| Code review | `/code-review` at `medium`. It ran as one forked job, so the finder angles did not get their own pathspecs. | 10 findings. |
| Design | `frontend-designer`, read-only, mock app at 1280 and 400 pixels | 11 fixes, 6 word proposals. |
| Over-engineering | `ponytail-review` (Opus) | 7 items, about 45 lines. |
| Re-review of the fixes | Codex, read-only, on the uncommitted fixes | 2 findings, both declined. |

No live-trace lane: the task has no live run before part E.

### Convergent findings (two lanes or more)

- **A made-up code replaces a valid one** (security L1, code review 2). The public route
  cannot tell a real code from a made-up one, so anyone who knows an address can replace the
  code on that person's waiting request. Contract D11 said a code "cannot stop or delay an
  account"; that is true for a listed domain only. **Owner ruling 15: the rule stays.** D11,
  the ADR amendment and `web-api.md` now state the limit. Options are in `docs/deferred.md`.
- **A file run goes on unseen when the form is left** (first Codex run 1, verifier 1,
  design 1). Adopted: the switch is disabled during a run, a move inside the app asks first,
  and a confirmed leave stops the run before the next person.
- **A second file chosen quickly shows and creates the first file's people** (code review 9,
  Codex 2). Adopted: only the latest check sets the result; the chooser is off during a check.
- **A long value is reported as bad quoting** (first Codex run 2, verifier 5, code review 9).
  Adopted: the reader's field limit is the route's limit, so the name rule answers.
- **`PUBLIC_APP_ORIGIN` is not checked for host or port** (security N2, code review 10).
  Declined: the infrastructure code is its only source. In `docs/deferred.md`.

### Adopted, by lane

**Code review (unique to it).**
- Add many: a Cognito throttle answered 409 and was final. Passing Cognito failures now answer
  503 on Add person and Approve, from the one list the sweep uses (`TRANSIENT_COGNITO_CODES`).
- Add many turned deactivated people back on without a sign. **Owner ruling 16: a file run
  never reactivates.** The route takes `reactivate` (default true); a file run sends false and
  lists the person with the reason.
- An organisation with any invite link could never be deleted. **Owner ruling 17: Delete
  organisation removes its revoked links that have no uses.** This adds one grant outside the
  first contract: `DELETE` on `invite_link` for `pa_ops`, and `ON DELETE CASCADE` from
  `invite_link_cohort` to its link. The owner approved the gate in the review; contract D1 and
  D9, the ADR amendment and the grant test carry it.
- The edit dialog sent the end date again on every save, so a label-only edit could move the
  end, or be refused on an expired link. The update route now takes any of the three values
  and checks only a value the call changes (ruling 18); the page sends only what changed.
- The public page sent the raw text after `#invite=`. The page now keeps letters and digits
  only and treats anything that is not 12 characters as no code. The server rule is unchanged.

**Contract verifier (unique to it).**
- Three behaviours had no test: D5 rule 6 (a person who already has the account), D5 rule 7
  through a link (another organisation), and the cohort cascade of D1. Added; no defect found.
- The ADR amendment and D5 rule 4 said "the next tick completes" a write that failed after
  Cognito. With rule 13 it is after the 15-minute wait. Both texts corrected.
- `web-api.md` still said "listed domains only" in two places. Corrected.
- A wrong comment in `core/schema.py`. Corrected.
- No test asserted the running count of Add many. Added.

**Codex (unique to it).**
- The migration round-trip test compared the schema with itself, so a lost index would pass.
  The test now asserts both partial indexes and their predicates by name.

**Design lane.** All eleven adopted: the leave guard (above); the Waitlist table fits 1280
pixels again with Status in view; a refusal in the link dialogs shows in the footer and marks
the domain field; focus returns to the row menu or to "Create link" when a dialog closes; a
disabled Cohorts field keeps its chips, and the file, organisation and cohorts lock from the
first Create; the public success message takes focus and "Sign in" inside it is a link (the
words did not change); one status region for the file run; "Create link" stays enabled and
names the missing organisation; the Add many footer at 400 pixels; four small layout points.

**Annex.** The Delete organisation refusal now has singular forms and a final "and"
("DHSC still has 3 people and 1 invite link. Nothing was deleted."). Three older tests
changed their expected sentence; the refusal itself is still asserted.

**Over-engineering.** Adopted items 2 to 6 (a dead method, two reads made one, a simpler
loop, a fixed code in the mock, a repeated model config).

### Declined, with the reason

- *Codex: the server accepts 91 days ahead* (deviation 2). The page sends the end of the
  chosen day in the operator's zone, so day 90 needs up to one more day on the server. Only
  operators can call the route.
- *Codex: the file check accepts a header with spaces around a name.* It is the same column;
  a strict reading helps no one.
- *Security L2: a link may name a domain that is listed to another organisation.* This is the
  precedence the contract asks for (D5 rule 3) and live check E3.7 tests it.
- *Security N3: some non-ASCII letters upper-case into code characters.* They reach the same
  code only.
- *Verifier: the Requests line shows a dead link's reason on a listed-domain request; the
  public route can wait for a redemption in progress.* Both are inside D8 and I1. The first
  is in `docs/deferred.md`.
- *Over-engineering 1 and 7.* The mock's file check stays, because the owner's polish pass
  uses the mock app with a faulty file. `update_invite_link` keeps its return value.
- *Re-review 1: a deadlock between Delete organisation and the sweep.* It needs the sweep to
  enrol a person through a revoked link. The sweep checks the link again under its row lock
  and stops, so it never asks for the organisation in that state.
- *Re-review 2: `null` in a link edit counts as left out.* Nothing is cleared or changed.
- *First Codex run 3 and 4:* the placeholder row was filled in the build; `docs/deferred.md`
  is written now.

### Deferred to `docs/deferred.md`

The sweep's candidate query has no index path for a very large waitlist (Codex 3); the pages
do not say when the sweep is off (code review 6); a request refused for good never redeems a
new code (code review 7); a database error could carry the code (security N1); a link with a
use keeps its organisation for good; the candidates listed in § Review handoff.

### The thirteen deviations

The verifier judged all thirteen inside the contract; the lead confirms each as built.
Deviation 2 was contested by Codex and stays (above). Deviation 9 (no length bounds in the
generated schema of Add person) is a small change of the ops interface; the 422 stays.
Deviation 12 is closed: `docs/deferred.md` is written. Deviation 3 (a second revoke is
refused) and deviation 6 (one `invite` row plus one `cohort.add` row for each membership)
are adopted as the reading of the contract.

### Handoff points

- *Any text after `#invite=` counts as a code:* changed (above).
- *Leaving during a file run:* changed (above).
- *Public page at 400 pixels, and "Use Sign in":* changed (design lane).
- *Codex had not read the several-domains change:* both Codex runs read it and found no defect.
- *Words written during the build and the review:* they wait for the owner, in
  `docs/tasks/065-accounts/ops-pages-copy.md`. Three were added in the review: " · <n>
  deactivated" in the finished line, the reason for a deactivated person, and the question
  before leaving a run.

### Fake-done checks

No test was deleted or skipped. Changed expectations: three tests of the Delete organisation
sentence (the new words); `test_delete_organisation_refuses_one_with_an_invite_link` became
two tests for the new rule (a live or used link refuses; a revoked unused link is deleted);
one `MultiSelect` test now uses an empty disabled field and a new test covers a disabled
field with chosen items, because the old expectation (chips hidden when disabled) was the
fault; the sweep test fixture also removes waiting requests with a code that other test
files leave. No swallowed error and no stub was added.

### Not covered by any lane

The lock time of the migration on a live staging database, and the downgrade with data
(Codex gave no report; the build rehearsed the downgrade on a scratch database). A real
screen reader. The firewall puzzle on the public form. These go to the live checks of part E.

### Open for the owner

- The polish pass on the pages (second round) and the words above.
- Design proposals that change words or direction, not built: a styled file chooser
  ("Choose a file"); "Already have an account? Sign in." as an alternative; zero counts in
  the finished line; the colour of the REVOKED chip (red today; red means failed elsewhere);
  "Approve 1 requests" (older code).

Screenshots of the changed surfaces after the fixes are in the session scratch folder
(`design-fixes/`, mock data only); they are not committed.

## Rubric status

Build-side rows. Rows 2 (live checks), 8, 41 and 42 belong to the review and part E.

| Row | Evidence |
|---|---|
| 3, 4 | No gate outside the contract's table; `make drift-check` green. |
| 5 | No test deleted or skipped; two expectations changed (deviation 8). |
| 9, 10 | `SplashView.test.tsx`: "shows the intro and, once sent, the same success message to everyone"; "with an invite link, says so, sends the code and clears it from the address". |
| 11 | `test_create_person_joins_the_chosen_cohorts_and_audits_each` |
| 12 | `test_an_unknown_cohort_is_not_found_before_any_cognito_call`; `test_cohort_ids_refuse_more_than_ten_or_a_repeat`; `test_an_existing_membership_writes_no_audit_row` |
| 13 | `test_a_refused_create_leaves_no_membership`; `test_a_failed_cohort_write_undoes_the_enrolment_and_a_retry_sends_no_second_invitation` |
| 14 | `test_approve_joins_the_chosen_cohorts` |
| 15 | `AddPersonView.test.tsx` "sends the chosen cohorts and names them in the toast"; `RequestsView.test.tsx` two approve tests |
| 16, 17, 18 | `test_import_check_answers_rows_for_a_good_file`; `test_import_check_names_each_fault_with_its_line` (14 cases); `test_import_check_writes_nothing` |
| 19, 20 | `AddManyForm.test.tsx`, three tests |
| 21 | `test_adding_the_same_person_again_sends_no_second_invitation` |
| 22 | `test_invite_link_round_trip_restores_the_fresh_upgrade_schema`; `test_pa_ops_grants_are_exactly_the_contract_list`; `test_invite_link_refuses_a_row_outside_its_checks` |
| 23 | `test_new_code_is_twelve_alphabet_characters_and_codes_differ`; `test_normalise_keeps_only_a_well_formed_code` |
| 24, 36 (public) | `test_waitlist_answer_is_the_same_for_every_invite_code` |
| 25 | `test_a_waiting_request_takes_a_new_code_and_a_decided_one_does_not` |
| 26 | `test_the_public_route_never_reads_invite_links` (it records every SQL statement of the request). Note: the `api.contract` package already imports `contract.ops` for every route, so the test checks statements, not imports. |
| 27 | `test_an_unredeemable_code_in_an_unlisted_domain_waits_untouched` (5 cases); `test_an_unredeemable_code_in_a_listed_domain_gets_the_listed_domain_account` (5 cases); `test_a_redeemable_code_in_a_listed_domain_gives_the_link_organisation`; `test_sweep_redeems_a_link_when_no_domain_is_listed` |
| 28 | `test_sweep_redeems_a_link_when_no_domain_is_listed` (stored rows); `test_a_link_with_two_domains_redeems_a_request_from_each` |
| 29 | `test_a_link_with_one_use_left_redeems_one_of_two_requests`; `test_two_redemptions_of_one_link_at_once_end_with_one_use`; `test_a_tick_that_finds_another_running_does_nothing` |
| 30 | `test_unknown_codes_never_crowd_out_a_redeemable_request`; `test_sweep_retries_a_failed_row`; `test_a_request_that_always_fails_spends_at_most_four_of_the_hour` |
| 31 | `test_a_deactivated_person_and_a_rejected_request_get_no_account_through_a_link` |
| 32 | `test_raising_the_maximum_makes_a_waiting_request_redeemable` |
| 33 | `test_redemptions_and_listed_domain_invitations_share_the_hourly_cap` |
| 34 | `test_manual_approve_of_a_request_with_a_code_counts_no_use` |
| 35 | `test_invite_link_create_list_update_and_revoke_are_audited_and_never_log_the_code`; `test_invite_link_create_refuses_values_outside_the_rules` (8 cases); `test_invite_link_maximum_cannot_go_below_its_uses`; `test_a_revoked_invite_link_cannot_be_changed`; the role-gate test (`_OPS_ROUTES`); `test_pa_ops_creates_updates_and_revokes_an_invite_link`; `test_pa_ops_sweep_redeems_a_request_through_an_invite_link` |
| 36 (ops, sweep) | the create/list/update/revoke test above; `test_the_invite_code_is_in_no_sweep_log_line_or_audit_row` |
| 37 | `test_ops_mode_requires_a_public_app_origin_and_the_api_ignores_it` (10 cases); `infra/tests/unit/test_service_wiring.py` |
| 38 | `InviteLinksView.test.tsx`, six tests |
| 39 | `test_requests_list_says_why_a_request_with_a_code_has_no_account`; `RequestsView.test.tsx` "shows under the organisation why a request's invite link made no account yet" |
| 40 | `test_delete_organisation_refuses_a_live_or_used_invite_link`; `test_delete_organisation_removes_its_revoked_unused_invite_links`; `OrganisationsView.test.tsx` |
| 43 | § Checks beyond the build, rollback rehearsal |
| 44 | Done; `docs/deferred.md` written in the review. |
| Polish row | Agent pass done inside phase 8 (two screenshot rounds against the annex and mock). **Owner pass: open.** |

## Intent & assumptions

- The Postgres connection of the ops service is a direct session (no transaction-mode
  pooler). The tick lock is a session-level advisory lock and needs that.
- The deploy updates the infrastructure before the new ops image starts (ADR 0046 order);
  the new image refuses to start without `PUBLIC_APP_ORIGIN`.

## Known unverified items

- The seven live checks of E3 (staging, after the merge).
- A failed call and the running count in Add many were not seen in the browser (the mock
  cannot fail there); the component tests cover them.
- The owner's polish pass on the pages and on the words listed in the living copy file.

## Public safety

Safe to publish. Tests use made-up addresses (`*.example`). The screenshots show mock data
only and stay in the session scratch folder. No real invite code exists yet.

## Review handoff (step-7/8 inputs)

**Executor provenance.** All code was written by Claude agents; no Codex doer.

| Phase | Executor | Commit |
|---|---|---|
| 1 Schema | deep-reasoner | `15c6eaf1` |
| 2 Cohorts at add and approve | deep-reasoner | `26368f45` |
| 3 File check | deep-reasoner | `8acb13c0` |
| 4 Invite link commands and routes | deep-reasoner | `4945b090` |
| 5 Public route | deep-reasoner | `b934ceb0` |
| 6 Sweep | deep-reasoner (a second, fresh one) | `57efb137` |
| 7 Public form | frontend-designer | `3be12e81` |
| 8 Ops pages | frontend-designer | `a91d6927` |
| 9 Docs, email sentence, the revoke singular | lead | `04ea0c53` |
| 5c Simplify | four general-purpose reviewers (Opus), deep-reasoner applied | `c6a39a7f` |

**For adjudication.**

- The thirteen deviations above.
- **Words written during the build**, listed in
  `docs/tasks/065-accounts/ops-pages-copy.md` § Cohorts at add, Add many, Invite links. They
  wait for the owner.
- **The Delete organisation refusal** keeps the server's existing format ("still has 3
  people, 1 invite links"). The annex says "Still has 3 people and 1 invite link." The
  existing format has no singular for any count and older tests pin it.
- **Public page, two points from the phase 7 agent:** at 400 pixels the success message
  appears below the fold and the page does not scroll to it (older behaviour); the success
  words say "Use Sign in" while the button is a screen above.
- **Any text after `#invite=` counts as a code on the page** (the line shows, the value is
  sent). The server judges it. Read as what A2 asks.
- **Leaving during a file run:** only leaving the browser page asks for confirmation; a move
  to another ops tab does not, and the run carries on.
- The contract says Codex has not read the several-domains change (D1, D5 rule 1, D6, D11).

**First Codex code review (read-only, run in the build session with the owner's approval,
on commit `c6a39a7f`; Codex thread `01a21784-e431-7070-8061-dc72b1244985`).** Raw findings,
**not adjudicated and not fixed**; the review conversation decides.

1. *Medium.* A file run goes on unseen when the operator leaves the form. The "One person" ·
   "Many from a file" switch stays enabled during a run and unmounts `AddManyForm`; the loop
   keeps creating people, but the count, the outcomes and Try again are lost, and the leave
   confirmation is gone (`AddPersonView.tsx:31`, `:42`; `AddManyForm.tsx:88`, `:114`).
   Suggested fix: disable the switch while a run is in progress, or keep the run state above
   the switch. (Related to the build's own note on leaving during a run.)
2. *Low.* A valid file under 200,000 characters with one very long quoted value (over about
   128,000 characters) is reported as bad quoting, because Python's `csv` reader has its own
   field-size limit and every `csv.Error` gets the quoting message (`api/routers/ops.py`,
   `check_people_file`). Suggested fix: raise the reader's field-size limit to the route's
   limit so the name rule answers. Rubric 17's long-name case uses 201 characters only.
3. *Low.* The exit `make verify` row held placeholder text when Codex read this file. It is
   filled now (§ Commands run).
4. *Low.* `docs/deferred.md` is not updated (deviation 12 above; rubric row 7).

Codex checked and found correct: I1 and I2 (the public route), I3, I4, I9 and I11 (the lock
order, the re-check under the locks, the tick lock on its own autocommit connection), I5 (the
candidate query filters before the limit), I6, I8, I10, the authorisation of the new ops
routes, and the several-domains change end to end. It gave no report on the end-of-day time
zone maths of the Invite links page, the Requests line, or weak tests (items 9 and 10 of its
brief), so those are not covered by this run.

**Knowledge candidates.**

- Three suites on one local Postgres give "too many clients" (limit 100), which looks like
  30 unrelated failures. A second Postgres container on another port, with
  `TEST_DATABASE_URL` set, removes it. `make reset-test-db` still talks to the compose
  database, which is harmless because each worker makes its own copy.
- `tests/ops/test_pa_ops_login.py` flakes when its tests land on several workers: the
  `pa_ops` login switch is cluster-wide.
- A session-level advisory lock for a periodic job belongs on its own autocommit
  connection, or the holder sits idle in a transaction for the whole run.
- Lock order for redemption: link row, then request row. Manual Approve never locks a link.
- "Refused for good" and "failed recently" must be filtered in the candidate query, before
  the limit. A filter inside the loop lets 200 dead rows hide a live one.
- A waiting request's newest sweep row is always a failure or terminal (a success stamps
  it), so "any terminal row or a recent failure" equals "the newest row says wait".
- The public route can stay constant-answer with an upsert only because it uses no
  `RETURNING` and builds its answer from its own values.
- An alphabet "without 0 O 1 I L" has 31 characters. Count before writing "32".
- The page sends "end of day, local time"; a server limit of N days must allow N+1.
- `PersonCreate` as a subclass with a model validator drops field bounds from the generated
  schema; the 422 stays.
- The `deep-reasoner` definition says "never commit"; a brief must say plainly that the lead
  asks for the commit, or the agent keeps work uncommitted.
- A laptop on battery with the lid closed wakes for seconds every 15 minutes; a background
  agent restarts and is cut each time. `caffeinate` does not stop lid sleep.
- An ops-only required setting breaks every script that starts ops mode
  (`scripts/ops_e2e_local.sh`).

**Deferred candidates** (step 8 writes them into `docs/deferred.md`).

- Contract § Out items a user may ask for: an invite link with no domain rule; a per-row
  organisation or cohort in the file; a default cohort for a listed domain; email to
  operators when a request needs a check; changing a link's domains after it is made.
- Reword "Self-signup works for one email domain": invite links now cover a second
  organisation without a listed domain.
- The file check lives in the route module (`check_people_file`); the CLI cannot reuse it.
  Condition: a CLI import is wanted.
- The "redeemable" rule exists in SQL (the candidate query) and in Python
  (`invite_request_reason`). The plan accepts this; a change to one must change the other.
- The `retry_wait` reason is worked out in the route, with a copy of the sweep's "failed in
  the last 15 minutes" test. Condition: the retry rule changes.
- The label and domain-count limits are raw numbers in the database checks and named
  constants in the contract and the commands.
- Each Add many row builds a full person answer that the page does not read (about 500 × a
  few small queries for the largest file). Condition: files get slow.
- The Delete organisation refusal has no singular forms.
- On a phone the ops tab row scrolls, but the active tab is not scrolled into view.

## Deferred work

Written: [docs/deferred.md](../../deferred.md) § Accounts, organisations and administration
(Decisions put off, and Limits in the code).
