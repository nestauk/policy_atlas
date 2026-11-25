# Design annex: 068-ops-announcements

The script for the Announcements pages on the ops site and the unsubscribe page on the
public site. The contract cites this file by version. Looks live here and in the mock, not
in the contract.

> **Version:** 2 · Mock: https://claude.ai/artifact/9eoXRJFp9XeTTKM9tATZmq (private to the
> owner) · Frozen: 2026-11-25 (owner approved the journey; picture field and the cuts below
> added the same day; version 2: the not-signed-in rule) · Polish rounds: log below

## Rules for this slice

- The pages use the ops pages' existing parts (`frontend/src/ops/ui.tsx`): page header,
  table, dialog, field, row menu, toast. No new look.
- One primary button on each page.
- A status is a mark and a word, never a colour alone.
- Every count on a page comes from the server. The page never counts recipients itself.
- No page says "delivered". "Sent" means the mail service accepted the email.
- No announcement is sent without the confirm dialog. A test to the operator's own
  address is the one exception.

## Fixed example data

Every scene and every test uses this one example.

- Operator: Ana Ruiz (has the ops role).
- Announcement: kind **Product update**, subject "What's new: theory of change maps",
  button "Open Policy Atlas".
- Chosen: cohort "Spring pilot" (18 people), organisation "Nesta" (64 people), person
  Tomás Ferreira. One person is in both groups. **82 chosen.**
- Left out: 2 unsubscribed from product updates, 1 deactivated. **79 get the email.**
- Result: 77 sent, 2 failed.
- As a **Service notice** the same choice gives 81 (only the deactivated person is left out).
- All 82 people have signed in at least once.

## Surfaces and states

### Top bar

- A fifth section, **Announcements**, between Cohorts and Waitlist. Address `/announcements`.

### Announcements list (`/announcements`)

- **At rest:** title "Announcements"; line "Email people who have an account. Every email
  you send is recorded here."; primary **New announcement**; a table of sent announcements,
  newest first: Subject · Kind · Who · Sent by · When · Result.
- **Result cell:** "N sent" · "N sent · M failed" · "Sending: N of M".
- **Empty:** "No announcements yet."
- **Row click:** opens the result page.
- **Never:** a draft row. This version stores no drafts (owner ruling 3).

### Compose (`/announcements/new`)

Three numbered groups and a preview.

1. **Kind.** Two choices, Product update first and chosen at the start.
   - Product update: "New features and news. The email has an unsubscribe link. People who
     unsubscribed or have not signed in yet do not get it."
   - Service notice: "Things people must know to use their account: downtime, security,
     changes to terms. No unsubscribe link."
2. **Who gets it.** "Everyone with an account" or "Chosen cohorts, organisations and
   people". The second shows the chosen items as removable chips and one search field,
   "Add a cohort, an organisation or a person".
   - Below: "**N** people get this email", then "M chosen. K left out: …" with the reasons
     and counts, then "A person in two groups gets one email." and a link "See the list".
   - The counts come from the server each time the kind or the choice changes.
   - Reasons, in these words: "unsubscribed from product updates" · "has not signed in yet" · "deactivated" ·
     "no email address" · "the address bounced before" · "marked our email as spam".
3. **Message.** Subject · Message (plain text; help line: "Plain text. Leave an empty line
   between paragraphs. Start a line with "- " to make a list.") · Picture (optional) ·
   Button text (optional) · Button link.
   - **Picture:** a button "Add a picture". After a choice: a small preview, a required
     field "Describe the picture" (help: "People see these words when their mail program
     hides pictures."), and "Remove". Under it: "Anyone with the link can open this
     picture. Do not show private data."
   - A button link must start with `https://`. Button text and link go together.
- **Preview:** the email as the person gets it, with "From: Policy Atlas
  <updates@…>". It follows the fields as the operator types. The footer changes with the
  kind.
- **Send a test to me:** sends the email to the operator's own address. Success shows
  "Test sent to you at HH:MM". An edit to any field after that clears the line.
- **Check and send** (primary): disabled until a test of the current text succeeded.
  Under it while disabled: "You must send yourself a test before you can send."
- **Unsent text:** the browser keeps the fields until the email is sent, so a reload does
  not lose them. Nothing is stored on the server before the send.
- **Errors:** a field error sits under its field. A failed test opens the ops pages'
  failure dialog with "Try again".

### Confirm dialog

- **Title:** "Send this email to N people?"
- **Body:** Subject · Kind · Who gets it · Left out, then the warning "You cannot take an
  email back after you send it."
- **Field:** "Type N to confirm". The send button is disabled until the number matches.
- **Buttons:** "Go back" · primary "Send to N people".
- **The list changed:** if the server's list is no longer the one shown (also when the
  count is the same), the dialog says "The list
  changed: it is now K people. Check it and confirm again." and shows the new numbers.

### Result page (`/announcements/:id`)

- **Head:** the subject; a facts line "Kind · Sent by · When · To …".
- **Summary line:** marks and words: "N sent", "N failed", "N left out", and while a send
  runs "N waiting". Under it: ""Sent" means the mail service accepted the email. We do not
  track who opens it."
- **While sending:** the page reads again every few seconds until nothing waits.
- **Action:** "Try the N failed again", shown only when N > 0 and nothing waits. A row a
  stopped server left in the middle shows "Not confirmed" and has no action.
- **Filter:** All · Sent · Failed · Left out.
- **Table:** Name · Email · Organisation · Result. Result words: "Sent" · "Waiting" ·
  "Failed: <reason>" · "Not confirmed" · "Bounced: the address does not exist" ·
  "Marked as spam" · "Left out: <reason>".
- **Link:** "Show the message that was sent" opens the email preview.
- **Never:** an "opened" or "delivered" count.

### The email

- Head: the wordmark. Then the subject as a heading, the message, the picture, the button.
- Footer, product update: "You get this email because you have a Policy Atlas account.
  Unsubscribe from product updates. We still send service notices about your account."
- Footer, service notice: "You get this email because you have a Policy Atlas account.
  This is a service notice about your account."
- Last line: "Questions? Reply to this email or write to support@…"

### Unsubscribe page (public site, `/unsubscribe`)

No sign-in. The link alone changes nothing, because mail scanners open links.

- **Arrive:** "Stop product updates?" · "We still email you when there is something you
  must know about your account, for example planned downtime." · primary **Unsubscribe**.
- **After Unsubscribe:** "You will get no more product updates" · link "Changed your mind?
  Get product updates again".
- **After the link:** "You will get product updates again".
- **Bad or missing link:** "This link does not work. Write to support@… and we will
  unsubscribe you."

## Scenes (mock)

1. The list, with three sent announcements.
2. Compose with the example filled in and a test sent. A change of kind changes the count
   (79 or 81) and the footer.
3. The confirm dialog for 79 people.
4. The result page: 77 sent, 2 failed, 3 left out.
5. The email, and the unsubscribe page after Unsubscribe.

## Owner rulings

- 2026-11-25 (1): two kinds of email, as scripted.
- 2026-11-25 (2): one optional picture is in this version.
- 2026-11-25 (3, lead's simplification, for the owner to confirm at the contract gate):
  no drafts on the server; the browser keeps unsent text. This replaces the mock's first
  "Draft" row and "Save as draft".
- 2026-11-25 (4): the owner wants product updates to leave out people who have not signed
  in yet. It is a fixed rule, with no box on the page. A service notice still reaches them.

## Polish log

| Round | Phase | Date | Notes applied | Sign-off |
|---|---|---|---|---|
| 1 | build, agent pass | | | lead |
| 2 | build, owner pass | | | owner |
| 3 | review, agent pass | | | lead |
| 4 | review, owner pass | | | owner |

## Deferred polish

None yet.
