# Task contract: 070-review-remainders

> **Status:** contract approved 2026-11-25 by the owner (scope A1 to A3). Revised the same
> day after the adversarial review (Codex, read-only; rulings in [plan.md](plan.md)): A2 no
> longer claims to close M-05 in full. Plan approved: not yet. ADR: none. No code is
> written yet.

## Goal

Close the three small, essential items that are still open from the project review of
2026-10-19 (`docs/tasks/064-security-hardening/original_review.md`). Keep the slice to a
minimum. Everything large has its own task.

## Deliverable

One pull request into `dev`. Each item below is one small change with one focused test.

## Terms

| Term | Meaning |
|---|---|
| **H-nn, M-nn, L-nn** | Finding ids from the review file (High, Medium, Low). |
| **WAF** | Web Application Firewall: the AWS service in front of the API (task 064b). |
| **Decompression bomb** | A small compressed file that expands to gigabytes when it is opened. |
| **Embedding** | A list of numbers that represents the meaning of a text, so the app can search by meaning. |

## Scope (checked against `dev` at `1c0d18f3`)

| # | Finding | What is still open | Fix |
|---|---|---|---|
| A1 | H-02 | The API accepts a request body of any size, and reads it before sign-in. The WAF body-size rule only counts (`SizeRestrictions_BODY`), because chat bodies can exceed 8 KB. `question`, `description`, chat `title` and free-text `text` have no maximum length. | One middleware that refuses bodies above a limit with HTTP 413: about 1 MB by default, and a larger named limit for each upload route. It applies to the public API and to the ops service. The theory of change upload (`TocUploadIn`, a 10 MB file sent as base64 text, about 14 MB) keeps working and gets a test. `max_length` on the open text fields; the plan proposes the numbers. |
| A2 | M-05 | The document fetcher accepts zstd compression and checks the 25 MB limit only after the data is expanded (`fetch_live.py`). | Send `Accept-Encoding: gzip, deflate` from both HTTP clients of the fetcher (documents and Europe PMC). This changes only how our server downloads documents from other websites. It does not touch uploads from users. **Accepted gap:** gzip can still expand one network chunk about 1,000 times (64 KB to about 66 MB) before the size check. That is bounded; zstd was not. The full fix (the fetcher expands data itself with an output limit) goes to `docs/deferred.md`. |
| A3 | H-12 | `_embed_units_with_isolation` splits a failed batch in half for every error except throttling. A provider outage or timeout turns one batch into up to 255 calls, each with its own retries. | Keep the split, but stop when both halves fail with an outage error: a network failure, a timeout, a server error or a malformed reply, from a fixed list in the plan. The remaining texts fail at once. Tests for each embedding provider (OpenAI, Bedrock). **Accepted gap:** a missing credential or region is still reported as failed texts, as today; it goes to `docs/deferred.md`. |

## Out of scope

Owner rulings of 2026-11-25:

- **M-01 (backend switch for options scoping):** not done. Options scoping launches soon.
- **H-05 (budget and alarms):** skipped for now.
- **Tasks tab with no tasks:** no change. The list page keeps sending a user with no tasks
  to "New task".
- **Counts of tasks and projects:** not in this task.
- **Small optional items:** database timeouts (M-19, part), CI pinning (L-04, L-05), banner
  wording (L-24), raw error text in 422 replies (L-19).
- **Stays in the review:** H-04 (spend caps), M-07, M-08 to M-10, M-18, M-22, and the
  remaining lows.

Other tasks:

- **Load and scaling task:** H-16 (rest), H-13, M-19 (rest), M-21 (long routes), M-25 to M-29.
- **Privacy notice task (069) and the Data Protection Officer:** H-07, H-08, M-12, M-14.
- **Waitlist and sign-up journey task:** M-30 privacy link.

Checks outside the code, for a person with account access (no pull request):

- **M-15:** which database user does the live Metabase use? No read-only role exists in the code.
- **H-09:** does production send Langfuse traces to its own project, and who can read it?
- **H-06:** was the CloudWatch log search for `"locals"`, `api_key`, `password` done?

## Constraints & approval gates

- **A2** changes what the product sends to outside servers (one request header). Approved
  by the owner on 2026-11-25.
- **A1** changes the public interface: new maximum lengths appear in the API description
  (`make openapi-sync` regenerates `frontend/openapi.json` and the frontend types), and
  oversized requests get HTTP 413. The owner approves the numbers with the plan.
- No schema change. No new dependency. No infrastructure or config change.
