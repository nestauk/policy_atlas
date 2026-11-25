# Task contract: 069-privacy-notice

> **Status:** built 2026-11-25. Scope given by the owner in chat (2026-11-25). Tier 1: text
> on one public page and its test. No plan, rubric or ADR.

## Goal

The privacy notice at `/privacy` says what the product does today, and covers three things
that are new or coming: PostHog (product analytics), the waitlist, and email announcements.
The changes are the smallest set that makes the notice true.

## Deliverable

One PR that changes `frontend/src/views/legal/PrivacyView.tsx` and its test.

## Terms

| Term | Meaning |
|---|---|
| **PostHog** | The product analytics service in draft PR #144. It is not turned on in staging or production. |
| **Waitlist** | The rows of table `waitlist_entry`, written by the "Request access" form on the splash page. |
| **Email announcements** | Task 068 (design notes only, not built): service notices and product updates sent from the ops pages. |
| **DPO** | Data Protection Officer: the person at Nesta who answers data protection questions. |
| **PECR** | Privacy and Electronic Communications Regulations: the UK rules for cookies and marketing email. |

## Scope / Out of scope

- **In:** the notice text, a "Last updated" date, the notice test.
- **Out:** the terms of use, a cookie banner or an opt-out control, PostHog settings
  (PR #144), the announcement build (task 068), and all backend code.

## What was wrong, and the fix

| Notice said | Fact in the code | Fix |
|---|---|---|
| The email address is the only identifier we store. | `app_user` also holds a name and an organisation. | "Account details" lists all three. |
| We do not collect IP addresses or device information. | The firewall logs each request for one month (`infra/infra/components/waf.py`). Cognito, the sign-in service, also sees them. PostHog will collect them. | Section 4 now says what is recorded and why. |
| Nothing about analytics. | PR #144 adds PostHog in the browser and the API. | A "Usage data" paragraph, a line on cookies, PostHog in the provider list, a retention line. |
| "Access requests" without the word waitlist. | The form writes to the waitlist. | The paragraph names the waitlist. |
| Nothing about email. | Cognito sends invitations and resets through Amazon Simple Email Service. Task 068 adds announcements. | An "Emails" paragraph with the opt-out for product updates; the email service in the provider list. |
| Nothing about data that leaves the UK. | PostHog stores data in the EU; the model route uses a global Bedrock profile. | One sentence on transfers. |
| No date. | — | "Last updated: 25/11/2026". |

## Constraints & approval gates

No hard gate: no schema, auth, egress, dependency, CI or config change. The notice is a
public, legal text, so **the DPO should read it before PostHog or announcements go live.**

## Open points for the owner and the DPO

The notice describes PostHog and announcements before they are live. These lines are true
only if the build matches them:

1. **PostHog host.** The notice says the data is stored in the EU. Production must use
   `https://eu.i.posthog.com`.
2. **PostHog runs with no cookie (owner ruling, 2026-11-25).** The notice says that
   product analytics does not use cookies or browser storage, so the site needs no cookie
   banner. PR #144 must set `persistence: "memory"` in `frontend/src/lib/analytics.ts`; its
   default today is a cookie plus local storage. The cost: a visitor who is not signed in
   counts as a new person on each page load, and feature flags load again each time.
3. **PostHog must match the owner ruling (2026-11-25).** PostHog identifies a signed-in
   person by email address, and records only how people use the app, never their content.
   PR #144 does not do this yet. It must: identify by email (it uses the token `sub` today);
   stop sending model prompts and answers (`privacy_mode=False` today); and hide click text
   (`mask_all_text: true`), because a click can carry a task name. Page addresses must not
   carry content either.
   The notice also says that PostHog does not store the IP address. This is a setting in
   the PostHog console, not in our code: turn on "Discard client IP data" in the production
   project before go-live. Check two things then: that location (country, city) is not
   kept either, and that events from the API carry no IP address.
4. **Deletion.** The notice promises to delete personal data "from our systems and from
   PostHog" on request (owner wording, 2026-11-25: data is kept while the account is active). No command does this today. Someone must
   delete by hand in each place: the database, the upload storage, Cognito (the sign-in
   service), Langfuse (the tool that records model calls) and PostHog.
5. **Product updates.** The notice promises an unsubscribe link on each product update.
   Task 068 must build it before the first send. The DPO should confirm that legitimate
   interest with an opt-out is the right basis.
6. **Transfer safeguards.** The notice says transfers outside the UK have recognised
   safeguards. The DPO should confirm the agreements with AWS and PostHog.

## OpenAI removed (owner ruling, 2026-11-25)

The product does not call OpenAI's own service: staging and production use the `bedrock`
model route. The OpenAI line is removed from the notice and from the terms of use (whose
"Last updated" date changes too). The Bedrock line still says that Bedrock runs OpenAI
models. The `openai-direct` route and its key stay in the code and the deployment as a
fallback. **If someone switches to that route, both pages are wrong until OpenAI is added
back.**

## Left as it was, on purpose

- Reading of tasks by organisation colleagues and by admins is not described (task 033
  decided not to change the notice for it).

## Adversarial review (one round, 2026-11-25)

A separate reviewer checked each claim against the code. Six findings, all accepted, all
small:

1. Usage data can also include the content of uploaded files (PR #144 sends full model
   prompts to PostHog).
2. Retention named only the database and PostHog. It now says "our systems", and states
   the 35-day life of production database backups (`infra/db_config.json`).
3. "Anonymised search queries" was false: nothing in the code anonymises a query. It now
   says "your search queries and uploaded files". **This changes owner-supplied wording.**
4. The transfers sentence now says how to get details of the safeguards (a legal
   requirement).
5. PostHog gives a random identifier to a visitor who is not signed in; the notice said
   "account identifier".
6. "We collect only the following" contradicted section 4; "only" is removed.

The owner ruling in open point 3 came after the review and replaces findings 1 and 5:
the notice now says that no content goes to PostHog and that the identifier is the email
address.

The reviewer was not sure if the analytics-cookie exemption in the Data (Use and Access)
Act 2025 is in force. The question no longer matters: PostHog runs with no cookie (open
point 2).

## Verification

`make frontend-verify-fast`; result in the PR.
