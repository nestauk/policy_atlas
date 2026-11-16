# Task 064a: security quick wins

## What / why

In October 2026 a security review of Policy Atlas listed seventeen small problems. This PR fixes
all of them. It is the first part of a wider security programme
(`docs/tasks/064-security-hardening/programme.md`). The later parts (bot protection, a content
security policy, two-factor login) come in their own PRs.

Task folder: `docs/tasks/064a-security-quick-wins/`. Decision record:
`docs/adr/0045-per-user-run-cap-task-quota-offboarding.md`.

### The seventeen fixes

**Keeping private data out of logs and error messages**

1. When the server logs an error, it no longer prints the contents of every variable in the
   failing code. Those variables could hold user text or secrets, and the logs go to AWS.
2. The waitlist form gives the same "thanks" reply whether or not the email is already on the
   list. Before, someone could use the form to check which emails were registered.
3. When a run fails, the user sees only the type of error (for example "TimeoutError"), not the
   full message. Full messages can contain internal details. Our own error messages, which are
   written for users, still show in full. The full detail still goes to the server log.

**Stopping one person from using up the whole server**

4. One person can have at most 3 runs going at the same time. The server has 10 slots in total,
   so before this one person could take all of them.
5. One person can create at most 50 tasks in a year. Administrators are exempt. The app shows a
   banner when someone reaches the limit.

**Fixing things that broke or hung**

6. The load balancer (the AWS service that sends traffic to our server) used to check the server
   by asking the database. A short database hiccup made it think the server was dead, and it
   killed the server and every run on it. It now only checks that the server process is alive.
   The deploy script still checks the database once after each release.
7. When a run crashed between two steps, the task stayed marked "running" forever and the user
   could not start another. It is now marked "interrupted".
8. One error (`confirm_expired`) used to come back as a generic server error. It now comes back
   as a normal "conflict" message that the app can explain.
9. The server closed idle connections after 5 seconds, but the load balancer expected them to
   stay open for 120 seconds. This caused random "502 Bad Gateway" errors. The server now waits
   125 seconds.
10. The screening query (the one that ranks screened documents) used to read every task's rows
    on every call. It now reads only the rows of the one task it is asked about, with a new
    database index. On the development database this went from 37 ms to 2 ms.

**Login and accounts**

11. Minimum password length goes from 8 to 12 characters. Existing passwords are not affected.
12. Our login provider (AWS Cognito) publishes the keys we use to check that a login token is
    real. The server used to go and fetch those keys again every time it saw a token with a key
    name it did not recognise. Anyone could trigger that by sending made-up tokens, which could
    flood Cognito and get us blocked. The server now fetches the keys at most once every 30
    seconds, whatever the token says. If a fetch fails, the server keeps using the keys it
    already has. The fetch no longer blocks other requests while it runs.
13. A new operator command, `user offboard`, closes a person's account: it disables their login,
    logs them out everywhere, removes them from their organisation, and turns off any public
    links on their tasks. Before, there was no proper way to do this.
14. The Cognito user pool (the list of all accounts) can no longer be deleted by accident.

**Infrastructure settings**

15. Anyone who types `http://` is sent to the `https://` site.
16. The load balancer and the content delivery network (CloudFront) use the current recommended
    encryption settings for HTTPS.
17. The server trusts the "real client address" header only when it comes from inside our own
    network. The server also stops announcing which software it runs.
18. Production database backups are kept for 35 days instead of 7. Staging stays at 7.

(Fixes 9 and 17 both come from one review finding about the server's start-up flags, so the list
has eighteen lines for seventeen findings.)

**Also**: the dependency check (`make audit`) was red on `dev` because of two library
advisories. Both libraries are updated to their patched versions in the lock file:
`opentelemetry-api` 1.45.2 and `tornado` 6.6.1. The check is green.

## Proof it works

Evidence: `docs/tasks/064a-security-quick-wins/verification.md`.

- The full test suite (`make verify`) passes on the final tree. The build had claimed a pass
  earlier, but when the review re-ran it, two tests were red. Both are fixed and the wrong claim
  is recorded as a finding.
- Each fix has at least one test.
- For the screening query, the database's own timing shows it read 1,221 rows instead of 39,682
  and gave the same 51 results.
- The checks on the live staging site cannot run until this is deployed. The list is in the
  contract under "Acceptance checks".

## Risk tier

Tier 4 (the highest). This PR changes a database index, production configuration, how login
tokens are checked, and the API's public error codes. Each of these is listed in the approved
contract.

## AI role

The agent (Claude) wrote the contract, rubric, plan and decision record, each approved by the
owner. It built the code in seven phases. A separate, fresh conversation then ran the review
stack and fixed what it found. The owner decided: continuing a paused run does not count towards
the 3-run limit; people already over the 50-task limit are told, not cut off; the task count uses
a rolling 365 days; the waitlist's "already registered" reply is removed without notice; and the
search of old logs for leaked secrets is done after this PR.

## Review focus

- **The 3-run limit** is checked in three places where a run can start. All three count the same
  way: runs that are already running plus runs that are about to start. The count is done while
  holding the lock that guards run starts, so two requests at the same moment cannot both pass.
- **The 50-task limit** is checked in the one function that creates tasks. The administrator
  exemption is the fifth place in the code that reads the "is admin" flag, so the earlier
  decision record (ADR 0033) is updated to say so.
- **Offboarding** handles four cases: the person is in an organisation, has left it, has no row
  in our database, or has no Cognito account any more. Each case reports what it did. If Cognito
  refuses, nothing in our database is changed.
- **Login keys**: the 30-second limit on fetches, keeping the old keys on failure, and giving
  the 30-second slot back when the first fetch fails.

## Reviews run

Findings and decisions in `verification.md` § Review findings.

- [x] Contract verifier (a fresh Claude Opus agent, read-only)
- [x] `/code-review` (medium)
- [x] `/security-review` (nothing above the reporting bar)
- [x] Adversarial review by Codex (a different model family, read-only)
- [x] `/simplify` (its checks were covered by `/code-review`, reason recorded)

What the reviews found and this PR fixes:

- Offboarding refused to run when the person's Cognito account was already deleted. It now still
  cleans up the database and turns off the public links.
- A theory-of-change check counted as two runs instead of one against the per-user limit, for as
  long as it ran. It now counts as one.
- If Cognito returned a key list with no usable key, the server threw away the keys it had. It
  now keeps them. Also, if the very first fetch failed, the server waited 30 seconds before
  trying again, so every login failed in that window. It now retries at once.
- The rule for which error messages are safe to show accepted any error with a "reason" field.
  Some standard library errors have one too, with internal detail in it. The rule now accepts
  only short code words.
- One function could be called without the per-user limit and then refused everyone with a
  confusing message. It now fails loudly to the developer instead.
- Three tests were repaired, one test was made stricter, two missing test cases were added, and
  the documentation of the operator's AWS permissions was corrected.

## Known gaps & deferred seams

`docs/deferred.md` § Security quick wins lists what was left for later. After this is merged and
deployed, the owner still needs to run the staging checks and the search of the AWS logs for
leaked secrets (the query is in `infra/DEPLOYMENT.md`).

## Public safety

- [x] No secrets, credentials, or real source text in the diff or evidence.
- [x] Logs and screenshots are public-safe (the query timing output is from the local development database).
- [x] No change that needs approval was added without it: the migration, configuration keys, infrastructure settings, server command, error codes and the new `/me` field are all in the approved contract.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
