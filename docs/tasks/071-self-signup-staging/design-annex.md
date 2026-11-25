# Design annex: 071-self-signup-staging

The states and words for the surfaces of [contract.md](contract.md). Terms: contract § Terms.

> **Version:** 2 · Mock: https://claude.ai/artifact/GqkMxEqCd6W6EfkB6EdS2g (private, six scenes) ·
> Frozen: _pending the owner_ · Polish rounds: _log below_

## Rules for this slice

- The public page says the same words to everyone. No word depends on a server answer.
- Ops pages: a short label, then one plain sentence. Reuse the existing parts
  (`OrganisationSelect`, `SearchSelect`, `Dialog`, `FailedDialog`, `Panel`, the table parts).
- A count is shown only when the total is known before the loop starts.
- Every failure names what failed and offers Try again where a retry can help.

## Fixed example data

- Organisation "DHSC", cohort "DHSC pilot 2027", domains `dhsc.example` and `ukhsa.example`.
- Link label "DHSC pilot", code `K7Q2-M9XD-3FHP`, 63 of 120 used, expires 14 Feb 2027.
- File `pilot.csv` with 100 people; line 7 has a bad email; line 12 repeats line 3.

## Surfaces and states

### Public page: Request access (contract A1, A2)

- **Intro:** "Tell us a little about yourself. If your organisation already has access, we
  email your sign-in details in a few minutes. If not, we review your request and get in
  touch."
- **With an invite code in the address** (`/#invite=…`): the page scrolls to the form and
  removes the code from the address bar. One line above the first field: "You are using an
  invite link."
- **Success:** "Thanks. Check your email in a few minutes. If nothing arrives, we are
  reviewing your request and will get in touch. Already have an account? Use Sign in."
- **Never:** a word that says whether the address, the domain or the code was accepted.

### Invitation email (contract A3)

- One sentence after "You set your own password the first time you sign in.": "You also
  set up an authenticator app on your phone."

### Ops: Add person (contract B7)

- New optional field under Organisation: "Cohorts (optional)". Several can be chosen; each
  shows as a removable chip.
- **Toast:** "Invitation sent to <email>. Added to <cohort>, <cohort>." The other toasts of
  today gain the same second sentence when cohorts were chosen.
- "What happens" panel, new line: "The person joins the cohorts you choose here."

### Ops: Approve a request (contract B7)

- Both dialogs get "Cohorts (optional)" under Organisation.
- **Toast (one):** "<name> approved. Added to <cohort>." **Toast (many):** as today.

### Ops: Add many (contract C4)

A switch at the top of Add person: "One person" · "Many from a file".

- **At rest:** "File" (a file chooser, `.csv`), "Organisation", "Cohorts (optional)". Help
  text: "A CSV file with a header line and two columns: email and name." Link: "Download an
  example file".
- **Checking:** "Checking the file…"
- **Check failed (errors):** "This file has <n> problems. Correct the file and choose it
  again." Then a list: "Line 7: this is not an email address." · "Line 12: this email is
  already on line 3." · "This file is not saved as UTF-8. Save it as CSV UTF-8 and choose it
  again." · "Line 9: a name cannot hold a line break." · "The file needs the columns email and name." · "A file can hold at
  most 500 people." Create is disabled.
- **Check passed:** "<n> people are ready to add to <organisation>." A table of the first 10
  rows (email, name) and "and <n> more". Button: "Create <n> accounts and send invitations".
- **Running:** "Adding people: <done> of <n>." The button is disabled. A line: "Keep this
  page open until it finishes."
- **Finished:** "<a> invited · <b> added, no email · <c> already in another organisation ·
  <d> failed." Then a table of the people who were not added, with the reason. "Try again"
  (only when a call got no answer or a server error) runs those people again. A person
  who is in another organisation, or whose address was refused, is listed and not retried. "Done" goes to People.
- **Leaving during a run:** the browser asks for confirmation.
- **Never:** a second invitation to a person who has an account; a stored copy of the file.

### Ops: Invite links (contract D7)

Tab "Invite links" between Cohorts and Waitlist (the Requests page shows as "Waitlist"). Title "Invite links"; primary "Create
link". Under the title: "An invite link lets people from the email domains you choose request
access and get an account without approval, until the link is full, expires or is revoked."

- **Table:** Label · Organisation · Cohorts · Email domains · Used ("63 of 120") · Expires ·
  Status (`ACTIVE`, `EXPIRED`, `FULL`, `REVOKED`) · actions. Empty: "No invite links yet."
- **Row menu:** "Copy link" (toast "Link copied") · "Edit…" · "Revoke…".
- **Create dialog ("Create invite link"):** "Label" · "Organisation" · "Cohorts (optional)" ·
  "Email domains" (a text box, help: "Only addresses at these domains can use the link. One
  domain on each line, for example dhsc.gov.uk. At most 10.") · "Maximum uses" · "Expires on". Button "Create link". After: the dialog
  shows the link with "Copy link" and "Anyone with this link and an address at one of these domains can
  get an account. Share it only with the group."
- **Edit dialog:** "Label", "Maximum uses", "Expires on". The organisation, cohorts and
  domains are shown and cannot be changed, with: "To change these, revoke this link and
  create a new one." A revoked link has no "Edit…".
- **Revoke dialog:** "Revoke <label>? People who use the link after this get no account
  through it. The <n> accounts already made stay." Button "Revoke link".
- **Refusals:** "Line <n>: enter a domain such as dhsc.gov.uk, with no @." · "Enter at least one domain." ·
  "A link can have at most 10 domains." · "This domain is on the list twice." · "Maximum uses must be
  from 1 to 1,000." · "Choose a date in the next 90 days." · "This link already has <n>
  uses. The maximum cannot be lower." · "A revoked link cannot be changed."
- **Expires on:** a date. The link works to the end of that day in the operator's time zone.
- **Never:** the code in a toast, a log or an audit row.

### Ops: Requests (contract D8)

- A waiting request that carries a code shows a second line under the organisation they
  typed: "Invite link: <label> — <reason>". Reasons: "expired" · "full" · "revoked" ·
  "wrong email domain" · "waiting for the next run" · "last try failed, next try in a few
  minutes". An unknown code shows "Invite link:
  code not recognised".

### Ops: Organisations (contract D9)

- The Delete refusal counts links: "Still has 3 people and 1 invite link."

## Scenes (mock)

Built, round 1: (1) the list with one link of each status and the row menu, (2) the create
dialog, (3) the created link, (4) a file with two errors, (5) a file run with one failure,
(6) the Waitlist page with each reason.

## Owner rulings

- 2026-11-25: scope of the task (contract § Owner rulings). The words are not yet approved.
- 2026-11-25: several domains for each link; the email sentence names no product; a mock
  round.

## Polish log

- Mock round 1 (2026-11-25): six scenes published; waits for the owner.
