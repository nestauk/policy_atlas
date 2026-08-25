# ADR 0031 — A portfolio layer above the project, and the screen/code vocabulary split

- **Status:** Accepted — 2026-08-17 (owner, with the 032 plan approval and the
  schema gate). **Amended 2026-08-24** by [ADR 0032](0032-portfolio-membership-many-to-many.md)
  on membership cardinality (decision 1) and PATCH shape (decision 4). The
  portfolio still sits *above* the project; the screen/code vocabulary split
  is unchanged.
- **Date:** 2026-08-17
- **Task:** 032-task-lifecycle-ia · contract approved 2026-08-17 · plan approved
  2026-08-17 (with two owner reductions: standard review, three full verify runs)
- **Binding design records:** `docs/tasks/032-task-lifecycle-ia/contract.md`
  (§ Terms, § The gaps this slice closes G13), `plan.md` (§ Decisions D6),
  `rubric.md` (items 9, 10, 33–36), and the owner's prototype frozen at
  `docs/specs/sources/task-lifecycle-ux/`

## Context

The app had exactly one level of structure: a `project` row is one research
question, carrying its plan, its run and its artefact. Related questions could
not be grouped or named, so a person running several strands of work on one
policy area had no way to say they belonged together (gap G13).

The prototype the owner supplied shows two levels. At the top, a person sees
all their work and sees it grouped. Inside one piece of work, a fixed
lifecycle runs. The question this ADR settles is where the new level goes, and
what it is called.

Two constraints bound the answer:

1. `docs/specs/system/data-model.md` § Entity hierarchy states the rule:
   *whole-item organisation is just columns, tags and scoping — no special
   container between project and artefact.*
2. The workspace-cluster slice, which would re-parent plan, run and artefact
   onto a new task entity, is deferred (`docs/deferred.md` § Web app) and was
   explicitly out of scope for 032.

## Decisions

1. **The new entity sits ABOVE the project, not between project and
   artefact.** A `portfolio` row groups `project` rows; the link is one
   nullable `project.portfolio_id`. Plan, run and artefact keep the project
   they always had, and no existing route, read model or migration changes
   meaning.

   This does not breach the data-model rule. That rule forbids a container
   *between* the project and its artefact — it exists to stop someone
   inserting a folder layer inside a project's own evidence, which would make
   every read model ask "which sub-container?" before it could answer. A
   portfolio sits on the other side of the project entirely: nothing below the
   project row learns a new parent, and no read model gains a level.

   *Rejected:* re-parenting plan, run and artefact onto a new task entity.
   That is the workspace-cluster slice. It would rewrite every read model and
   every route for a change whose whole user-visible effect this slice gets
   from one nullable column.

   *Rejected:* a tag or a column on `project`. A portfolio has a name and a
   description a person maintains, and pages of its own; a free-text tag gives
   no identity to rename and no row to hang a description on.

2. **The screen word and the code word deliberately differ, and the mapping is
   fixed.** On screen, a `project` row is a **Task** and a `portfolio` row is a
   **Project**. In the code, `project` and `portfolio` keep their names.

   This is the uncomfortable part of the decision, and it was taken with open
   eyes. The alternative — renaming the `project` table to `task` and the new
   table to `project` — would touch every route under
   `/api/v1/projects/{id}`, every read model, every event-log `kind`, every
   migration and every test, for zero behaviour change, and would break every
   existing client and bookmark. The owner's product vocabulary and the
   database's vocabulary have simply drifted apart, which is ordinary in a
   system that outlives its first naming.

   The mitigation is that **the mapping is written down in exactly one place
   in the code** (`frontend/src/lib/vocabulary.ts`) and every user-visible
   string comes from there. A view that writes "Task" or "Project" as a
   literal has leaked one vocabulary into the other, and that is a defect, not
   a style preference (rubric 9).

3. **The portfolio row carries a name, a description and an owner — nothing
   else.** No status, no lifecycle, no cached task count. The count is derived
   per read.

   *Model only what behaves.* A portfolio changes how work is grouped and
   navigated; it does not run, fail, pause or complete, so giving it a status
   would invent a state nothing could set and nothing could read honestly. A
   cached count would be a second source of truth for something one `GROUP BY`
   answers.

   The plan's column list also named `archived_at`. It was **not** built:
   nothing in this slice writes it, because the slice adds no archive route,
   and rubric 36 forbids lifecycle on the row. Adding soft-delete later is one
   nullable column in the same migration that adds the archive route.

4. **Assignment is a PATCH on the project, not a field on create.**
   `PATCH /api/v1/projects/{id}` additively accepts `portfolio_id`, including
   an explicit `null` to unassign. `POST /api/v1/projects` is left alone,
   which keeps the gated public-interface surface smaller (plan D6).

   Assigning a portfolio the caller does not own is a 404 and does not write,
   matching the existing project rule — otherwise the PATCH would be an
   existence oracle for another owner's rows.

## Consequences

- **Every existing project reads `portfolio_id: null` and behaves exactly as
  before.** Unassigned is a normal state, not a missing value to be fixed. No
  backfill, no migration of existing data beyond adding the column.
- **A cold reader meets the vocabulary split immediately**, which is why it is
  recorded here and in the contract's § Terms rather than left to be inferred.
  Anyone reading `project` in the code should assume the screen says Task.
- **The tenancy rule is now duplicated in two helpers** (`owned_project`,
  `owned_portfolio`). Both raise the same indistinguishable 404. If a third
  owner-scoped resource appears, they should collapse into one helper
  parameterised by table.
- **The deferred workspace-cluster slice is unchanged and still deferred.**
  This ADR deliberately does not pre-empt it: if plan, run and artefact are
  ever re-parented onto a task entity, the portfolio layer sits above that
  too, and the screen vocabulary would finally match the code.
