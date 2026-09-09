# ADR 0032 — Portfolio membership is many-to-many

- **Status:** Accepted — 2026-08-24 (owner, with the 033 combined contract+plan
  gate)
- **Date:** 2026-08-24
- **Task:** 033-ux-snags
- **Amends:** [ADR 0031](0031-portfolio-layer-above-the-project.md) decisions 1
  (cardinality of the link) and 4 (PATCH shape). The portfolio still sits
  *above* the project. The screen/code vocabulary split is unchanged.

## Context

ADR 0031 introduced a `portfolio` row above `project`, linked by one nullable
`project.portfolio_id`. Unassigned was a normal state. A task belonged to at
most one project. Many-to-many was deferred.

Users assign one research task to several named projects (strands of work).
The 033 contract requires that.

## Decisions

1. **Membership is a join table, not a column on `project`.**
   `portfolio_membership` holds `(portfolio_id, project_id, created_at)`.
   Primary key `(portfolio_id, project_id)`. Existing `project.portfolio_id`
   rows migrate in, then the column drops.

   Nothing below the project row learns a new parent. Plan, run and artefact
   keep their project. This still does not breach the data-model rule that
   forbids a container *between* project and artefact.

   *Rejected:* keeping `portfolio_id` as a "primary" membership plus a join
   table. Two sources of truth.

   *Rejected:* extra membership HTTP resources. The Share UI always has the
   full set, so replace-all PATCH is enough.

2. **Public read shape is `portfolio_ids: uuid[]`.** Empty list means
   unassigned — still a normal state, not a missing value. The singular
   `portfolio_id` field is removed. The only client is this frontend.

3. **`PATCH /api/v1/projects/{id}` accepts `portfolio_ids`.** Omit = leave
   unchanged. `[]` = unassign all. A list replaces the set. Each id must be
   an owned portfolio or the write is 404 and does not happen — same
   existence-oracle rule as 0031.

4. **Counts.** `task_count` on a portfolio is the number of active member
   tasks. A task in two projects counts in both. `source_count` stays on the
   task and is never summed onto a project.

5. **Assignment does not touch run state.** Membership writes (and rename)
   are not `run_active` conflicts. They serialize on the project row lock
   with other API mutations so the event log cannot mis-order.

## Consequences

- Unassigned tasks still list without a project prefix.
- Share can list and edit memberships from task creation (033 unlocks that
  tab; sharing itself stays coming soon).
- The deferred "membership beyond one" line in `docs/deferred.md` is
  discharged. Portfolio soft-delete and real sharing remain deferred.
