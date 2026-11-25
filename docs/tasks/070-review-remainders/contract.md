# Task contract: 070-review-remainders

> **Status:** drafted 2026-11-25. Not approved. No code is written yet. The owner picks
> the items first; the rubric and the plan follow the pick.

## Goal

Close the small, essential items that are still open from the project review of 2026-10-19
(`docs/tasks/064-security-hardening/original_review.md`), and two small bugs the owner
reported. Keep the slice to a minimum. Everything large has its own task.

## Deliverable

One pull request into `dev`. Each item below is one small change with one focused test.

## Terms

| Term | Meaning |
|---|---|
| **H-nn, M-nn, L-nn** | Finding ids from the review file (High, Medium, Low). |
| **WAF** | Web Application Firewall: the AWS service in front of the API (task 064b). |
| **Decompression bomb** | A small compressed file that expands to gigabytes when it is opened. |

## Candidate items (checked against `dev` at `1c0d18f3`)

### A. Proposed for this task

| # | Finding | What is still open | Fix |
|---|---|---|---|
| A1 | H-02 | The API accepts a request body of any size, and reads it before sign-in. The WAF body-size rule only counts (`SizeRestrictions_BODY`), because chat bodies can exceed 8 KB. `question`, `description`, chat `title` and free-text `text` have no maximum length. | One middleware that refuses bodies above a limit with HTTP 413: about 1 MB by default, and a larger named limit for each upload route. The theory of change upload (`TocUploadIn`, a 10 MB file sent as base64 text, about 14 MB) keeps working and gets a test. `max_length` on the open text fields. |
| A2 | M-05 | The document fetcher accepts zstd compression and checks the 25 MB limit only after the data is expanded (`fetch_live.py`). | Send `Accept-Encoding: gzip, deflate`. This changes only how our server downloads documents from other websites. It does not touch uploads from users. |
| A3 | H-12 | `_embed_units_with_isolation` splits a failed batch in half for every error except throttling. A provider outage or timeout turns one batch into up to 255 calls. | Split only for input errors (HTTP 400, invalid vector). Fail the batch at once for the others. |
| A4 | M-01 | Options scoping is switched off only in the browser (`VITE_OPTIONS_SCOPING`). The backend accepts `"capability": "options_scoping"` in every environment. Theory of change already has a backend switch. | A backend switch in the same shape as the theory of change one. |
| A5 | H-05 (part) | The deploy rollback is on. There is no spend budget, and no alarm for server errors or an unhealthy container. Three alarms exist (database CPU credit, NAT traffic, ingest dead-letter queue). | An AWS Budget with email alerts, and two alarms (load balancer 5xx count, unhealthy host count). |
| A6 | bug | Tasks tab with no tasks. As built: the tab is always a link, and the list page sends the user to "New task" when they have no tasks (`TasksListView.tsx`). | Check in the browser that this still holds for every case (own, archived, organisation). Fix only what fails. |
| A7 | bug | Counts of tasks, projects, and tasks in a project. As built: a project's count is the active tasks the caller may read in their own organisation (`_task_counts`); the yearly quota counts tasks created (`tasks_created_since`). | Compare each number on screen with the database for a few real accounts. Fix only what is wrong. |

### B. Small, optional (owner decides)

| # | Finding | What is still open |
|---|---|---|
| B1 | M-19 (part) | The database connection has no `statement_timeout`, `idle_in_transaction_session_timeout` or `pool_timeout`. A cheap safety net before the scaling task. |
| B2 | L-04, L-05 | `verify.yml` uses tag-pinned actions and has no frontend package audit. The deploy workflows are already pinned. |
| B3 | L-24 | The banner says "sensitive or confidential" and not "personal". One line of copy; it can go with the privacy notice task. |
| B4 | L-19 | Three routes return raw Pydantic error text in a 422 reply. |

### C. Checks outside the code (no pull request)

- **M-15:** which database user does the live Metabase use? No read-only role exists in the code.
- **H-09:** does production send Langfuse traces to its own project, and who can read it?
- **H-06:** was the CloudWatch log search for `"locals"`, `api_key`, `password` done?

## Out of scope

- **Load and scaling task:** H-16 (rest), H-13, M-19 (rest), M-21 (long routes), M-25 to M-29.
- **Privacy notice task (069) and the Data Protection Officer:** H-07, H-08, M-12, M-14.
- **Waitlist and sign-up journey task:** M-30 privacy link.
- **Not picked, stays in the review:** H-04 (spend caps), M-07, M-08 to M-10, M-18, M-22, and
  the remaining lows.

## Constraints & approval gates

- A4 and A5 change production config (`infra/pa_config.json`, CDK). A2 changes what the
  product sends to outside servers (one request header). B2 changes CI. Each needs the
  owner's approval.
- No schema change. No new dependency.
- Staging leads production by one release, as in programme 064.
