# Ops pages: sections, states and copy (task 065, B6, B12, C5)

The lead's script for the ops pages, from the owner's explainer and wireframes (an artifact,
not committed; direction settled 2026-11-16). The `frontend-designer` agent builds from it.
Copy here is final unless the owner changes it; layout, spacing and motion are the agent's
within `DESIGN.md`. Voice: short label, then one plain sentence. Sentence case. No pills or
chips except the ones named here.

## Addresses and shell

- The pages live at `https://ops.<domain>` (staging `ops.v3.policyatlas.uk`, production
  `ops.policyatlas.uk`), served by the ops service. Routes: `/people`, `/people/new`,
  `/people/:userId/quota`, `/organisations`, `/organisations/:orgId/quota`, `/requests`.
  `/` redirects to `/people`.
- Sign-in is the same Cognito sign-in as the app (the shared `AuthProvider`). Signed out: the
  shell shows one button, "Sign in".
- Top bar (its own, not the app's): the wordmark, a chip "Ops" (blue tone, like BETA), the
  sections **People · Organisations · Requests** (Requests carries a count of waiting rows when
  it is above zero), a link "Back to Policy Atlas" to `https://<domain>` at the right, and the
  signed-in person's initials. No New, Tasks or Projects.
- Every page: a title (Display size), one primary action at the right where the page has one,
  a filter row with a search field, then a plain table.

## States every page shares

- **Loading:** "Loading…" (role status), nothing else.
- **No ops role (403 on the first call):** the shell, then one paragraph: "Your account does
  not have the ops role." and one sentence under it: "Ask an operator to grant it from the
  command line." Nothing else renders. No retry button.
- **Unauthenticated (401 after refresh):** the "Sign in" button.
- **Request failed (5xx or network):** a line under the table that names what failed, then
  an inline "Try again" link (§ Owner pass 1).
- **Toast after a write:** "<Summary> · recorded" where recorded means the audit row was
  written (the response carries `action_id`). On a bulk action: "<n> done, <m> failed ·
  recorded"; the failed rows show their message inline in the table under the person.

## People (`/people`)

- Title "People". Primary "Add person" → `/people/new`. Search placeholder "Find by name,
  email or organisation" (filters the loaded list client-side; the route takes `q` too).
- Columns: Name · Email · Organisation · Flags · Tasks this year · Invited · (row menu).
  - Organisation: the name, or "not enrolled" in grey.
  - Flags: chips "Admin" and "Ops" when true; otherwise empty.
  - Tasks this year: "12 of 50", or "no limit" when `limits.task_quota_per_year` is null.
  - Invited: relative time of `invited_at` ("2 h ago"), or "—".
- Row menu (one person): "Enrol or move to an organisation…", "Set quota…",
  "Resend invitation", "De-enrol", "Offboard…".
  - "Resend invitation" is disabled inside the hour, with the hint "sent 2 h ago, try again
    after 15:40" (the time one hour after `invited_at`, local time).
  - "De-enrol" is disabled when the person is not enrolled and holds no flag.
- Selection: a checkbox per row and one in the header. With one or more ticked, a bar above
  the table: "<n> selected" · "Set quota…" · "Move to…" · "Resend invitation" · "De-enrol" ·
  "Offboard…" · "Clear selection". The bar's actions use the bulk routes with every ticked
  subject.
- **Enrol or move dialog:** title "Move <name> to an organisation" (or "Move <n> people to an
  organisation"); a select of organisations; help "Their tasks and projects move with them and
  become private."; buttons "Move" (primary) and "Cancel".
- **De-enrol dialog:** title "De-enrol <name>?" (or "<n> people"); sentence "They stay signed in
  but leave their organisation. Their tasks and projects stay with them and leave the
  organisation too."; buttons "De-enrol" and "Cancel".
- **Offboard dialog (one person):** title "Offboard <name>?"; sentence "This stops them signing
  in, signs them out everywhere, removes them from their organisation and takes down any public
  links to their tasks. Their tasks stay in the database. This cannot be undone from here.";
  field label "Type the email to confirm" with the address as placeholder; the button
  "Offboard" is red (the one red button, DESIGN.md) and disabled until the typed value equals
  the address; "Keep the account" cancels.
- **Offboard dialog (several):** the same sentence, then a list of every person's name and
  address, then the field "Type the number of people to confirm" (the button enables when the
  typed value equals the count).
- **Resend (bulk) outcome:** rows with `too_soon` show "Sent less than an hour ago" under the
  name.

## Add a person (`/people/new`)

- Back link "People". Title "Add a person".
- Fields: "Email" · "Display name" · "Organisation" (the organisation picker, required). Buttons "Create and send invitation" (primary) and "Cancel".
- Side panel "What happens": three sentences: "Policy Atlas emails them a temporary password.
  It is valid for 30 days." · "If the email already has an account that is in no organisation,
  that account is added to this organisation. No email is sent, because they can already sign
  in." · "If the email already belongs to another organisation, nothing changes."
- Errors: 409 `enrolled_elsewhere` → a red line under the email field: "Already in <org>. Use
  Enrol or move from the People list."; 409 `ops_refused` → the message under the form; the
  form keeps what was typed.
- Success: toast "Invitation sent to <email> · recorded" or "Added to <org>, no email sent ·
  recorded"; navigate to `/people`.

## Set a quota (`/people/:userId/quota`, `/organisations/:orgId/quota`)

- Back link "People" (or "Organisations"). Title "Quota for <name>".
- Under the title, one line of facts: "<Organisation> · <n> tasks created in the last 365 days"
  (person page only).
- Field "Tasks per year": number input; placeholder shows the inherited value, e.g. "Inherits
  Nesta · 100" or "Inherits the default · 50"; help "Leave empty to inherit. Enter 0 for no
  limit."
- Field "Simultaneous tasks": number input; placeholder "Inherits the default · 3"; help
  (warning tone, yellow tint band, the Word Beside the Colour Rule): "Warning: this limit
  protects the shared run capacity. A higher number lets this person take more of it at the
  same time, which can slow other people's runs." Editable all the same.
- Organisation form: the same two fields; help "Applies to everyone in <org> who has no number
  of their own."
- Buttons "Save quota" (primary) and "Clear and inherit" (ghost; sends both fields null).
- Side panel "Currently applied limits" (person page): three rows: "Tasks per year: <value or
  no limit> · from <this person | <org> | the default>", "Simultaneous tasks: … · …",
  "Admin exemption: yes | no".
- Toast: "Quota saved · recorded".

## Requests (`/requests`)

- Title "Access requests". No primary. Search placeholder "Find by name or email".
- Above the table, one line: "Self-signup on for <domains> · <sent> of <max> invitations sent
  this hour", or "Self-signup off" when disabled.
- Columns: Name · Email · Requested (relative time) · Status · (action).
  - Status chips (the word beside the colour): green "Invited <time>"; yellow "Waiting";
    orange "Check: already in <org>".
  - Action: "Approve into…" for Waiting (opens the organisation select, then calls approve);
    nothing for Invited; "Open person" for Check (links to `/people?q=<email>`).
- Approve dialog: title "Approve <name>"; select "Organisation"; sentence "Cognito emails them a
  temporary password. If the address already has an account, it is enrolled without an email.";
  buttons "Approve" and "Cancel". 409 `enrolled_elsewhere` → the row turns to Check with the
  message.

## Organisations (`/organisations`)

- Title "Organisations". Primary "Add organisation" (opens a dialog: field "Name", buttons
  "Create" and "Cancel"; 409 → "An organisation with that name already exists.").
- Search placeholder "Find an organisation".
- Columns: Name · People · Tasks per year · Simultaneous tasks · Self-signup domain · Created ·
  (row menu).
  - Tasks per year / Simultaneous tasks: the override, or "default · <settings value>" in grey
    (the settings values are the defaults the server reports through a person's limits; show
    "default" alone when unknown).
  - Self-signup domain: the domains joined with ", ", or "—". Read-only.
- Row menu: "Set quota defaults…" only.

## Not in this slice

The audit log on the pages; editing the domain table; cohorts and the revision-2 pages. The
explainer's revision 2 is a later task.

## Rulings during the build (lead, 2026-11-17)

The `frontend-designer` agent proposed wording where the script gave none. All of it
is accepted and is now part of the script:

- Toast summaries: "Moved <name> to <org> · recorded", "De-enrolled <name> · recorded",
  "Offboarded <name> · recorded", "Invitation sent to <email> · recorded",
  "<name> approved · recorded", "Created <org> · recorded". The move toast uses real
  plurals ("1 project and 4 tasks").
- Offboard dialog title for several people: "Offboard <n> people?". Bulk "Set quota…"
  opens a dialog "Quota for <n> people" with the same two fields, the name list and empty
  placeholders. The Move and De-enrol dialogs for several people list every name and
  address (B6).
- Account menu: the person's name and email, then "Sign out".
- Relative times: "<n> min ago", "<n> h ago", "<n> d ago", then the short date after
  30 days. Page title "Policy Atlas Ops". The Move dialog's select is labelled
  "Organisation".
- Add a person with no organisation chosen: "Choose an organisation." Empty lists:
  "No people match." / "No requests yet." / "No organisations match."
- Where the script and `DESIGN.md` disagree (relative times, chips in a table, a red
  button, no orange chip tone), the script wins for the ops pages; `DESIGN.md` gains a
  red-button entry in a later pass if the owner wants one.
- "· recorded" after a create, an organisation quota save or an approve rests on the
  2xx alone: those routes write the audit row in the same transaction as the response,
  so a 2xx means recorded; they return no `action_id`.

## Owner pass 1 (owner, 2026-11-18)

- Add a person: the display name has no help line. "What happens" names no sender address
  (the page guessed it from its own host, so it read `no-reply@localhost` locally); its second
  and third sentences are reworded as above.
- Quota: the side panel is "Currently applied limits", and each row is "<label>: <facts>".
- The organisation picker, in every form (Add a person, Approve into, Move to): a field trigger that opens a popover with a filter field "Find or create an
  organisation" (focused) over the organisations it matches. When the typed name matches no
  organisation exactly, a last row "Create organisation “<name>”" creates it (toast "Created
  <name> · recorded") and chooses it. Enter takes the only match, or creates. A taken name says
  "An organisation with that name already exists." under the list. An empty list says "No
  organisations yet. Type a name to create one."
- An account is always created in an organisation (lead recommendation, for the owner to confirm).
- A failed load or action: one line, "<what failed>." then a bold Blue "Try again" link in the
  same size, which repeats the load or the action. The words name what failed: "Could not load
  the people list.", "Could not load the access requests.", "Could not load the
  organisations.", "Could not load this person's quota.", "Could not load this organisation's
  quota.", "Could not finish the action.", "Could not approve the request.", "Could not save
  the quota.". A failed form submit says "Could not create the account. Try again." (or "the
  organisation") under the form; its own button is the retry.
- The top bar (owner pass 2, 2026-11-18) matches the main app's: the wordmark, then an "OPS"
  chip in BETA's shape tinted Nesta orange; People, Organisations and Requests pinned right;
  the account icon (the main app's person glyph) at the far right opens the name, email and
  Sign out. No "Back to Policy Atlas" link.
- Organisation quota help: "Applies to everyone in <org> who doesn't have a personalised
  quota."
- Organisations: no "Move a task or project" panel (removed by the owner; the CLI keeps
  `rows assign`).
- Organisations table headers (owner pass 3, 2026-11-18): an info hint beside "Tasks per year"
  ("The number of tasks each person in this organisation can create in a year. It is per
  person, not shared by the organisation."), "Simultaneous tasks" (the same, "can run at the
  same time") and "Self-signup domain" ("People who request access with an email at this
  domain get an account in this organisation without approval. An administrator adds or
  removes a domain from the command line."). Domains stay command-line only (owner ruling).
- The Requests section is "Waitlist" (owner pass 3): the tab, the page title, the table's name
  and its failed line; the address is `/waitlist`.
