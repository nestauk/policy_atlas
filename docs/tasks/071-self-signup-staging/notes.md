# Task 071 — self-signup test on staging: plan for discussion

> **Status:** a plan to discuss, not a contract. Nothing is built or deployed. After the owner
> answers the questions in the last section, this becomes one `contract.md` with numbered steps.

## What you asked

1. Switch on self-signup on staging as a test, for `nesta.org.uk` addresses first.
2. Check that the journey still works when we tell the whole organisation "use Request access
   and you will get your sign-in details".
3. Is the one-minute wait for the automatic invitation a problem? Is a Lambda (a small AWS
   function that runs on demand) the better practice?
4. How do we let in only some people from a domain (for example a government department)?
5. Add person on the ops pages cannot put the new person in a cohort. Fix that.

## Short answer

- The feature is already built (task 065). Switching it on is one config value and one deploy.
- The journey works, but **the words on the public page are wrong for it**, and there is
  **one trap on the first minute after switch-on** (old requests). Both are below.
- Keep the timer. Do not add a Lambda. Make the timer faster (60 s to 15 s, one line) and
  tell the person what to expect.
- For "only some people in a domain": do not list the domain. Use the Requests page (approve)
  or Add person. Both exist. No new mechanism is needed yet.
- Cohorts at Add person and at Approve: a small, additive build.

## How it works today

| Part | Fact | Where |
|---|---|---|
| Public form | "Request access" on the splash page stores one row. Every request gets the same answer. A repeat email stores nothing. | `backend/src/policy_atlas/api/routers/waitlist.py` |
| Internal name | The table is `waitlist_entry`. The public page says "Request access" and the ops pages say "Requests". | `core/schema.py` |
| Automatic invitation ("the sweep") | A loop inside the ops service. Every 60 seconds it looks for requests whose email domain is in the domain table. For each, it creates the account in that organisation. Cognito (the AWS sign-in service) then emails a temporary password. | `ops/sweep.py`, `api/app.py:557` |
| Switch | `self_signup.enabled` in `infra/pa_config.json`. False on staging and production. | `infra/pa_config.json` |
| Hourly cap | At most `max_per_hour` invitations each hour: 100 on staging, 5 on production. Requests over the cap wait for a later tick. | `ops/sweep.py` |
| Domain table | Maps a domain to one organisation. Edited from the command line only (`make org-domain-add`). | `infra/DEPLOYMENT.md` § Self-signup |
| Manual path 1 | Requests page: Approve one or many requests into an organisation. Reject, delete. | `frontend/src/ops/views/RequestsView.tsx` |
| Manual path 2 | People → Add person: email, name, organisation. Sends the invitation at once. | `frontend/src/ops/views/AddPersonView.tsx` |
| Cohorts | Added only from the People list (row menu or multi-select → "Add to cohort…"). Not at Add person. Not at Approve. | `routers/ops.py:606` |

Why the domain match is safe: the temporary password goes to the mailbox. A person who types
a `nesta.org.uk` address they do not own gets nothing.

## Question 2: does the journey still work?

The journey for a Nesta person after switch-on:

1. Open the staging site, fill in Request access, solve the puzzle, submit.
2. See: "Thanks — you're on the list. We'll be in touch."
3. Up to one minute later, get the email "Your Policy Atlas account" with a temporary password.
4. Sign in, set a password, **set up an authenticator app** (required since task 064d).
5. Land in the Nesta organisation.

It works. These are the gaps, most important first.

| # | Gap | Proposed fix |
|---|---|---|
| G1 | **Old requests get invited on the first tick.** The sweep takes every unanswered, unrejected `nesta.org.uk` request in the table, not only new ones. | Before switch-on, open Requests on staging. Approve, reject or delete the old `nesta.org.uk` rows by hand. No code. |
| G2 | **The page tells the person to wait for a human.** The intro says "We review requests and get in touch when a place opens up." The success message says "you're on the list". A Nesta person has no reason to look at their inbox. | New words, the same for everyone (draft below). |
| G3 | **A person who already has an account gets nothing.** A repeat request stores nothing and sends nothing. After an all-staff announcement, current users will try the form. | The new words point to "Sign in". The announcement says the same. |
| G4 | **The invitation email does not mention the authenticator app.** Step 4 is a surprise. | Say it in the announcement. Optional: one more sentence in `infra/email/invitation.html`. |
| G5 | **More than 100 requests in one hour wait.** An all-staff message could do that. The page gives no sign. | Accept it for the test. "Within a few minutes" is still true for the first 100. Raise the staging cap only if you expect more. |
| G6 | **Refused rows are silent.** If the sweep cannot invite a person (already in another organisation, deactivated), the row shows "Check" on Requests. Nobody is told. | An operator looks at Requests once a day during the test. No build. |

The answer must stay the same for every email address. That rule stops a stranger from
learning who has an account. So the new words cannot say "your account is ready".

**Draft words (the owner decides):**

- Intro: "Tell us a little about yourself. If your organisation already has access, we email
  your sign-in details in a few minutes. If not, we review your request and get in touch."
- Success: "Thanks. Check your email in a few minutes. If nothing arrives, we are reviewing
  your request and will get in touch. Already have an account? Use Sign in."

**Draft announcement (the owner decides):**

> Policy Atlas (staging) is open to everyone at Nesta. Go to v3.policyatlas.uk, choose Request
> access and use your nesta.org.uk address. An email with a temporary password arrives in a
> few minutes. The first time you sign in, you set your own password and connect an
> authenticator app (for example Microsoft Authenticator). If you already have an account,
> use Sign in.

Internal naming: keep `waitlist_entry`. A rename is a schema change and buys nothing, because
no user or operator sees the word.

## Question 3: is the one-minute wait a problem?

Not much. The average wait is 30 seconds and the worst is 60, and then the email itself needs
some seconds. People accept a short wait for an email **if the page says an email is coming**.
Today the page does not say so. That is the real problem (G2).

| Option | Worst wait | Cost | Verdict |
|---|---|---|---|
| A. Keep 60 s, fix the words | 60 s | none | The minimum |
| B. Tick every 15 s | 15 s | one line in `api/app.py`. Three small database reads each tick. | **Recommended, with A** |
| C. Invite inside the public request | 0 s | The public service would need the rights to create accounts. ADR 0046 keeps those on the ops service only. The response time would also show which domains are listed. | No |
| D. Lambda, queue, or database notification | about 1 s | New infrastructure, new permissions, new failure cases, to save some seconds | No |

The timer also gives two things for free: a failed invitation is tried again on the next tick,
and the hourly cap holds. A Lambda would have to rebuild both.

## Question 4: only some people from a domain

A domain in the table means "everyone at this domain". So for a department where only some
people get access, **do not list the domain**. Then choose by what you know:

| Situation | Use | Build |
|---|---|---|
| You have the names and addresses | People → Add person. They get the invitation at once and do not use the form. | exists |
| They come to you (you shared the site link) | They use Request access. You approve the right ones on Requests, one or many at a time. | exists |
| A contact in the department hands out access and you do not know the names | An invite code or link tied to an organisation and a cohort | **not built; defer** |

Two ideas I checked and rejected for now:

- **A list of approved addresses** (the request is approved automatically when the address is
  on the list). If you know the address, Add person does the same in one step.
- **Invite codes.** They need a new table, a new field on the public form, and an expiry rule,
  and a code can be forwarded. Build it when a real partner asks for it.

Possible small addition, only if a real list is long: paste many "Name, email" lines into Add
person. Not in this task unless you say so.

## Question 5: cohorts at Add person (and at Approve)

Today the operator adds the person, goes back to the list, finds them, and uses "Add to
cohort…". The fix:

- `POST /api/v1/ops/people` and `POST /api/v1/ops/requests/{id}/approve` accept an optional
  list `cohort_ids` (empty by default, so nothing that calls them today breaks).
- The route calls the existing `commands.add_to_cohort` for each cohort, in the same database
  transaction as the enrolment, and writes one `cohort.add` audit row each, as the People list
  does.
- Add person gets an optional "Cohorts" field. Both Approve dialogs (one request, many
  requests) get the same field.
- No new table and no new command. `frontend/openapi-ops.json` is regenerated by
  `make openapi-sync`.

Not proposed: a default cohort for a self-signup domain (for example "everyone who self-signs
up from nesta.org.uk joins cohort X"). It needs a new column on the domain table. For this
test, filter People by organisation, select all, "Add to cohort…".

## Proposed steps (one contract)

| Step | What | Who | Kind |
|---|---|---|---|
| 1 | New words on the splash page (intro and success message). Optional sentence in the invitation email. | lead (words are owner-approved) | frontend, small |
| 2 | Sweep tick 60 s → 15 s | lead | backend, one line |
| 3 | `cohort_ids` on Add person and Approve: routes, tests, the two pages | agents from a brief | backend + ops pages |
| 4 | Staging pre-flight: confirm the Nesta organisation and its domain (`make org-domain-add ENV=staging DOMAIN=nesta.org.uk ORG=Nesta`); clear old `nesta.org.uk` rows on Requests (G1) | owner or lead with AWS sign-in | operations, no code |
| 5 | Set `self_signup.enabled` to true for staging in `infra/pa_config.json`; deploy | lead, owner approves | config |
| 6 | Live checks on staging (below) | lead + owner | evidence |
| 7 | Announce to Nesta | owner | — |

Steps 1 to 3 can merge and deploy before step 5. Step 5 is a one-line change and its rollback
is the same line set back to false.

**Live checks (step 6):**

1. A new `nesta.org.uk` address requests access → the email arrives in under a minute → sign
   in, new password, authenticator app → the person is in Nesta on the People list.
2. An address from another domain → no email; the row waits on Requests.
3. The same Nesta address requests again → no second email.
4. Add person with two cohorts → the person shows both cohorts on the People list.
5. Approve a request with a cohort → the same.

**Rules this touches (AGENTS.md hard gates):** an addition to the ops interface (step 3) and
a staging config change (step 5). No schema change, no new dependency, no change to who can
sign in to the ops pages. Production stays off. Risk tier: low to medium.

## Questions for the owner

1. **Words.** Are the draft intro, success message and announcement right? Do you want the
   sentence about the authenticator app in the invitation email?
2. **Timer.** 15 seconds, or keep 60?
3. **Old requests.** Who clears the old `nesta.org.uk` rows on staging before switch-on?
4. **Cap.** Is 100 invitations an hour enough for the announcement? How many people do you
   expect in the first hour?
5. **Selective domains.** Is "do not list the domain; approve or add by hand" enough for the
   first government group? If a contact will hand out access for us, say so and invite codes
   become a later task.
6. **Cohort for the test.** Do you want every self-signup account in one cohort (for example
   "Nesta staging test")? If yes: by hand after the fact (no build), or the default-cohort
   column (schema change)?
7. **Bulk add.** Do you need to paste many people into Add person now?
