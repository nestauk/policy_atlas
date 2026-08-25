# Rubric: 033-ux-snags

The task is **done only if every box holds**. Terms and S-numbers are in
[contract.md](contract.md).

## Standard

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] The three full `make verify` runs passed — baseline, end of schema/API,
       step-6 exit ([plan.md](plan.md) § Gates). Frontend phases gated on
       `make frontend-verify`. Declared manual checks pass or are recorded as
       not run, with the reason.
3. [ ] No approval-gated change snuck in unapproved. The three gates in the
       contract (schema · public API · prompt) are exactly what shipped.
4. [ ] No generated files or secrets edited by hand. `api/gen/types.ts` was
       regenerated via `make openapi-sync`. Prompt hashes updated only for
       `planner_prompt.py` via `prompt_hash_guard.py --update`.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps listed in [docs/deferred.md](../../deferred.md). The
       many-to-many membership line is discharged. Real sharing stays deferred.
8. [ ] Review stack ran: contract verifier · `/code-review` ·
       `/security-review` · `/simplify`. Findings in `verification.md`.
8a. [ ] **Adversarial review is recorded as waived**, not silently missing.

## S1 Source count

9. [ ] Task-list `source_count` equals funnel `relevant` (Included), not
       snapshot-row count. `null` iff no run. Asserted by test.

## S2 BETA

10. [ ] A BETA chip sits next to the wordmark on every authenticated chrome
        page. It is not a nav item and has no route.

## S3 Membership

11. [ ] A task can belong to 0, 1, or many projects. `portfolio_ids` is the
        public field. `project.portfolio_id` is gone.
12. [ ] PATCH `portfolio_ids` omit / replace / `[]` behave as the contract.
        Unowned ids are 404 and write nothing. Same-owner 404 equality holds.
13. [ ] A task in two projects increments both `task_count`s. `source_count`
        is not summed onto a project.
14. [ ] Share lists memberships, adds, and removes, and is open from task
        creation. "Sharing coming soon" remains. Mock `/portfolios` works.

## S4 First-time user

15. [ ] `/` with zero active tasks redirects to `/new`. Deep-links are not
        stolen. Archived-only accounts are not treated as first-time.

## S5 Rounds

16. [ ] Broad/Broadest running cards show every search and screen round, labelled
        `Searching (Round N)` / `Screening (Round N)` when N > 1. Full-text
        ingest is not a Searching row. Focused (one round) stays unnumbered.

## S6 Queries

17. [ ] All-sources, under the table, lists the coverage queries grouped by
        backend. Empty coverage is an honest absence, not a fabricated list.

## S7 Rename / membership while running

18. [ ] PATCH name and PATCH `portfolio_ids` during `running`/`paused` return
        200 and leave the walk in that status. Asserted by test.

## S8 Findings pager and group filter

19. [ ] Findings paginate at page size 50 with Previous/Next and `?page=`.
        Filter changes reset the page. Totals match `pagination.total_items`.
20. [ ] Clicking an intervention-group chip sends `facet` and `group` in one
        URL update. The live API does not 422. If a remaining mismatch is
        found, it is fixed or recorded — not dropped.

## S9 Quote in context

21. [ ] Findings with a `chunk_id` show the quote highlighted in the chunk
        context on expand. Abstract-only findings stay quote-only
        (`chunk_id` null).

## S10 OECD default

22. [ ] New planning conversations default `country_group` to `"OECD members"`
        and say so in the reply and scope chip, unless the user asked for a
        different geography or cleared it. `planner_v9` is pinned.
23. [ ] The plan document labels the field Source geography. Empty reads
        "None selected". The default is origin, not study setting — the
        planner does not silently add a UK/HIC screening criterion.
