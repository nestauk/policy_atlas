# ADR 0036 — One vocabulary across code, schema, API and screen

- **Status:** Drafted 2026-09-04 — **Accepted on the 038 plan gate** (owner;
  date filled at sign-off). The contract it records was approved and
  re-approved after adversarial review on 2026-09-04.
- **Date:** 2026-09-04
- **Task:** 038-vocabulary-alignment
- **Supersedes:** [ADR 0031](0031-portfolio-layer-above-the-project.md)
  decision 2 (the screen/code vocabulary split). **Amends:**
  [ADR 0035](0035-public-task-read-access.md) decision 5 (the concrete
  public paths); `docs/specs/system/web-api.md` § Deprecations (the
  additive-only rule, for this one break); `docs/specs/system/prompting.md`
  rule 12 (prompt versioning), narrowly and once.
- **Binding design records:** `docs/tasks/038-vocabulary-alignment/contract.md`
  (§ Terms, defects V1–V12, § Forks, § Adversarial findings), `plan.md`
  (§ Decisions D1–D8), `schema-manifest.md`, and the living vocabulary
  `docs/specs/vocabulary.md`.

## Context

Three vocabularies had grown up side by side. The screen said Task, Project
and Evidence search. The code and the database said `project`, `portfolio`
and `evidence_base`. The persona users talk to had no name on screen and was
`orchestrator` in the backend and in every prompt. ADR 0031 made the split
deliberate in 2026-08 because renaming the `project` table then would have
buried task 032's product work; it named the rename as its own later slice,
and the owner scheduled it after task 033 (2026-08-24).

On 2026-09-04 the team fixed its definitions
(`docs/specs/vocabulary.md`): a **Task** is one use of a capability; a
**Project** is a collection of Tasks; **Evidence search** is the capability
and "evidence base" is the collection of documents it collects; the
**Agent** is the persona, the **Task Agent** is a Task's primary chat, and
other conversations are **chats**. The owner ruled that consistency, not
minimal churn, is the goal.

## Decisions

1. **The screen word is the code word.** `project` → `task`, `portfolio` →
   `project`, `evidence_base` → `evidence_search`, `orchestrator` → `agent`
   in the schema, the code, the API, the prompts, the configuration and
   the living docs. `frontend/src/lib/vocabulary.ts` stops being a mapping
   and becomes the copy module it always also was. ADR 0031 decision 2 is
   superseded; its reasoning (cost of the rename) was right for its moment
   and is paid here on purpose.

   *Rejected:* API and screen only, tables kept behind a documented
   mapping. It leaves the split in place for every new backend reader.

   *Rejected:* renaming the persona on screen and on the wire but not in
   the backend. The orchestrator preamble serves planning, steering, watch
   and chat alike, so it *is* the Agent; two names for one thing is the
   defect being fixed.

2. **One migration, two ordered steps, names and stored values.** Step 1
   renames every `project*` object (including `project_source_snapshot`)
   and `orchestration_plan` → `plan`; step 2 renames `portfolio*` →
   `project*`. The order is the collision guard: `project_id` is free when
   step 2 claims it. Constraint and index names follow, so the catalog
   tells the truth. The objects come from a manifest generated from
   `core/schema.py`, never typed. Stored values: `capability_run.capability`
   is updated in the migration; append-only rows (`event_log` kinds and
   JSONB `decided_by`/`authored_by` and steer-point ids) are **not**
   rewritten — new writes use the new words and every reader canonicalises
   the old ones at deserialisation, through three helpers with tests.

   *Rejected:* rewriting `event_log`. It is the audit trail.

   *Rejected:* keeping the old constraint names. A `fk_*_project` on a
   `task` table would teach the next reader the same confusion.

3. **The `/api/v1` paths break once, without a deprecation window.**
   `/api/v1/projects/**` → `/api/v1/tasks/**`; `/api/v1/portfolios/**` →
   `/api/v1/projects/**`; `Project*`/`Portfolio*` schemas follow. This
   supersedes `web-api.md`'s additive-only rule for this change only: the
   frontend and the e2e specs are the only consumers and ship with it. The
   frontend routes make the same move, with **no legacy redirects** (owner,
   F3): public sharing (ADR 0035) is on staging only, and every copied link
   is regenerated. ADR 0035 decision 5's concrete paths are amended to
   `/tasks/{id}/result` and `/tasks/{id}/sources/*`; its invariant — signed-in
   and public viewers share one URL — is unchanged.

4. **Prompt text changes words, not meaning, and needs no version bump —
   this once.** `prompting.md` rule 12 requires a suffix bump and a paired
   replay for every prompt change. For an enumerated set of one-to-one
   substitutions (`orchestrator` → `agent`, `project` → `task`,
   `evidence_base_coverage` → `evidence_search_coverage`, and no others)
   the owner ruled (R1) that the meaning is unchanged and the replay buys
   nothing. The prompt hash guard is re-pinned and the review reads the
   prompt diff as words only. No stored row carries the `orchestrator_v1`
   family id (checked: `prompt_version` values are component prompts), so
   nothing memoised is invalidated. **This sets no general precedent**: the
   next prompt change that is not on this list follows rule 12.

5. **Conversation kinds stay `planning | chat`.** The Task Agent is a screen
   label on the active planning conversation (else the newest closed one);
   exactly one row carries it; older lineages read "Earlier plan". The
   listing stays owner-relative; no authorization changes. A phase model
   for the primary thread (plan → steer → follow-up in one conversation)
   is recorded in `docs/deferred.md` for the "chat more functional" task.

6. **The vocabulary lives in `docs/specs/vocabulary.md`, not under
   `sources/`.** ADR 0002's frozen-sources rule stands unamended: the
   2026-09-04 definitions are a frozen snapshot under
   `sources/vocabulary/`, and the owner edits the living Product spec.

7. **Four riders travel with the rename** because they touch the same
   files or shrink the diff: every Langfuse trace of a Task carries the
   task id as its session (V9); `http_budget` → `call_budget` and the dead
   `RunPane`/`JourneyPane` go (V10); the post-sign-in landing bug is fixed
   by navigating the freshly mounted router (V11); AGENTS.md is trimmed to
   protocol and landmines and the tool-found dead files go (V12). V11 is
   the slice's one user-visible behaviour change and is reviewed as auth
   code. Judgment-bearing dead code is a separate pass.

## Rollback

The migration is reversible in names **and** values. The runbook:

1. Quiesce: scale the API service to zero so no run or turn is in flight
   (`make deploy-check` shows the state; the one-shot migration task is the
   only writer during the window).
2. `alembic downgrade -1` from the 038 revision. `downgrade()` runs the
   manifest in reverse, then rewrites the values the new image may have
   written in the window: `capability_run.capability` → `evidence_base`;
   `event_log.event_type` `task.*` → `project.*`; JSONB
   `decided_by`/`authored_by` `agent` → `orchestrator`; steer-point id
   `evidence_search_coverage` → `evidence_base_coverage` in plan payloads
   and pause records.
3. Deploy the previous image; run the verification queries from the
   manifest (no object carries the new names; no row carries a new value).
4. Public links copied during the window are dead after rollback too; they
   are regenerated. There is no other point of no return.

Staging first, then production, in that order; a brief outage between the
migration task and the new image is accepted (no dual-name window).

## Consequences

- Every new reader of the code, the schema, the API or a trace meets one
  word per concept. `vocabulary.ts` no longer explains a split.
- Saved Metabase questions on `project`/`portfolio` and Langfuse filters on
  `orchestrator:*` spans and `project_id` metadata stop matching; the owner
  re-points them after merge (the PR names both).
- Two env var names change (`POLICY_ATLAS_AGENT_MODEL`,
  `POLICY_ATLAS_AGENT_TRIAGE_MODEL`); the stack sets neither, so only a
  local override needs renaming.
- Historical task docs, ADRs and frozen sources keep the old words; the
  spec index carries a one-line mapping so a cold reader can read them.
- The workspace-cluster re-parenting stays deferred and is unaffected; when
  it lands, plan, run and artefact re-parent onto a row already called
  `task`.
