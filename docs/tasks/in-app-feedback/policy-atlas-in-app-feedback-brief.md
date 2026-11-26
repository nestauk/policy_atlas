# Policy Atlas — in-app feedback: implementation brief

You are implementing in-app feedback for Policy Atlas (PA), an LLM-powered evidence synthesis tool for UK policy analysts. Work in this repository. Read CLAUDE.md and then DS_GUIDELINES.md. Then read this whole brief before touching anything, then follow the phases in order. Phase 0 ends with you stopping and reporting back; do not start Phase 1 until I confirm.

## Why this exists

Feedback has two consumers and must serve both:

1. **Evals.** Every feedback event must attach to a pipeline artefact (run, report, section, claim, citation, document) and join to the run's Langfuse trace, so it can drive error analysis, populate recall anchor sets, and calibrate the grounding/summary LLM judges. Feedback that attaches only to a session or a user is not useful here.
2. **User research.** Every event must be cuttable by the user's department and primary job, which come from a one-time onboarding profile.

If an implementation choice makes either join harder, it is the wrong choice.

## Pipeline context (verify against the code)

A run is: user chat → Planner → TaskPlan (user approves) → runner executes steps 1–12. Steps that matter here, with the artefacts they emit:

| Step | Name | Artefact | Removes documents? |
|---|---|---|---|
| 1 | acquire | `source_snapshot` | no |
| 2 | screen (title + abstract, LLM ×3) | `source_screening_result` | **yes** |
| 6 | screen_full (full text) | `screening_result` (stage 2) | **yes** |
| 8 | select | `selection_result` | no (prioritises) |
| 11 | synthesise | report with sections → claims (tiered) → verified citations | — |
| 12 | report | `artefact · block · annotation · citation` | — |

Each run has a Langfuse trace. Backend is Python with SQLAlchemy 2.0 / psycopg against Postgres (Supabase). Frontend: discover it. The report UI has (at least) **Result** and **Sources** tabs; Sources has **All sources** with screened-in and screened-out views.

## Phase 0 — discovery (stop and report at the end)

Explore the codebase and produce a short written report (in chat, not committed) covering each item below. Quote file paths. Where an assumption is wrong, say what is true instead and what it changes about the plan. Do not write code in this phase.

1. Frontend stack, component structure for the report view, references list, All sources table, planner, and app header.
2. **Per-user identity.** Does V3 have one stable `user_id` per real person? (V2 used shared logins, which made attribution impossible.) Where is it available server-side and client-side?
3. Are **claims** rendered as discrete, addressable elements with a stable `claim_id`, and do they carry `citation_ids` and a tier? If not, what is the cheapest path to that?
4. Are **citations/references** rendered per row with a stable document identifier (OpenAlex ID or equivalent)?
5. How are run artefacts stored and queryable: can I, given a `run_id` and a document ID, cheaply answer "was it acquired / screened out at stage 1 / screened out at stage 2 / selected / cited"?
6. Langfuse integration: how is the trace ID obtained per run, and is there an existing scores API wrapper?
7. PostHog: is it integrated? Does it `identify()` users? Are person properties set anywhere?
8. Existing feedback or survey code (there may be earlier attempts: thumbs, an evidence-search feedback form, source flagging). List it; propose what to keep, replace or delete.
9. Existing DB migration tooling (Alembic or other) and test setup.
10. Any feature-flag mechanism.

Then list the assumptions in this brief that you could not verify, and stop.

## Cross-cutting requirements

**Event envelope.** Every feedback record carries: `id`, `user_id`, `run_id`, `trace_id` (Langfuse), `surface` (where in the UI it was raised), `kind`, `target_type`, `target_id`, `pa_version`, `created_at`, `retracted_at` (nullable; toggles and undo are retractions, never deletes).

**System of record.** Postgres is the source of truth for every record. In addition:
- Records attached to a trace/artefact (citation flags, claim flags, missing-paper reports, use-intent answers, problem reports) are mirrored as **Langfuse scores** on the trace, named per kind, with the Postgres `id` in the score comment/metadata so the two can be reconciled.
- Timed prompts and funnel events go to **PostHog** as events. Do not duplicate artefact-level feedback into PostHog beyond a lightweight "feedback_submitted" event with `kind` and `surface`.
- The onboarding **profile** is a row in Postgres and is also written to PostHog person properties.

**Schema.** Propose it in Phase 0, but the intended shape is one `feedback_event` table with a `kind` enum and a `payload jsonb` column validated per kind in application code, plus one `missing_paper_resolution` table (see B below) and one `user_profile` table. Use enums for `kind`, `surface`, `reason`, `use_intent`, `failure_stage`. Index on `(run_id)`, `(user_id)`, `(kind, created_at)`, `(target_type, target_id)`.

**Behaviour.** No feedback control may be a modal except Report a problem. Nothing is required except the onboarding profile's first two questions and the claim flag's reason. Every control works with keyboard and screen reader: real `<button>`, `<input>` + `<label>`, `aria-pressed` on toggles, `aria-label` on icon-only buttons. Touch targets ≥44px. Submits are idempotent per `(user_id, target_type, target_id, kind)` where the kind is a toggle.

**Privacy.** No query text or free text goes to PostHog. Free text goes to Postgres and to the Langfuse score comment only.

**Tests.** Unit tests for the resolution logic (B), the show-once rules (C), and the profile gating (F). One integration test per kind that posts an event and asserts the Postgres row and the Langfuse score call.

**Feature flag** every element independently so they can ship separately.

## Elements, in build order

### A. Per-citation "Useful" / "Not relevant" flag

**Where:** every row of the References list at the end of the report (`surface = report_references`) and every screened-in row in Sources › All sources (`surface = sources_all`).

**UI:** two icon buttons per row (thumbs up "Useful", thumbs down "Not relevant"), one click, no text. On "Not relevant", an inline panel appears under the row with optional reason chips — `Off topic`, `Wrong population or setting`, `Not evidence (e.g. methods paper)`, `Duplicate`, `Other` — an optional note input, `Save`, `Undo`. The flag is saved on the first click; chips refine it. Second click on the same button retracts.

**Record:** `kind = citation_flag`, `target_type = document`, `target_id = <OpenAlex ID>`, `payload = {action: useful|not_relevant, reason?, note?}`.

**Acceptance:** flag persists per user per run across reloads; retraction sets `retracted_at`; Langfuse score `citation_flag` written with value 1/−1.

### B. "A paper I expected is missing" + "Should have been kept"

**Where:** (1) a card at the foot of the References list (`surface = report_foot`); (2) a `+ A paper is missing` button in the Sources › All sources toolbar (`surface = sources_tab`) opening the same form inline; (3) a `Should have been kept` button on every row of the **screened-out** view (`surface = screened_out_row`). (3) is a separate kind: it attaches to an existing document ID and has no free text.

**Form:** one input accepting DOI, URL or title; optional "Why does it matter?" textarea; `Report missing paper`; `Add another` resets the form.

**Resolution (server-side, synchronous if <1.5s, else async with a pending state):**

```
resolved_id = resolve(raw_input)          # DOI → OpenAlex; URL → DOI/OpenAlex; title → OpenAlex search, accept top hit only above a similarity threshold you choose and record
if resolved_id is None:  failure_stage = unresolved
elif resolved_id in cited(run):           failure_stage = cited          # user is wrong; still record
elif resolved_id in selected(run):        failure_stage = not_cited
elif resolved_id in screened_in(run):     failure_stage = not_selected
elif resolved_id in screened_out_s2(run): failure_stage = screened_out_s2
elif resolved_id in screened_out_s1(run): failure_stage = screened_out_s1
elif resolved_id in acquired(run):        failure_stage = acquired_only  # should be impossible; log it
else:                                     failure_stage = not_retrieved
```

The user never chooses a stage. Show one of three confirmations: found-but-not-cited (link to the paper in All sources), found-but-screened-out ("recorded as a screening override"), not retrieved ("added to the checks we run on every search update"). `unresolved` shows "Thanks — we couldn't match this automatically; we'll review it."

**Records:** `kind = missing_paper`, `target_type = run`, `payload = {raw_input, why?, query_text}`; row in `missing_paper_resolution` with `resolved_id`, `failure_stage`, `resolver_confidence`, `resolved_at`. For (3): `kind = screening_override`, `target_type = document`, `target_id = <document ID>`, `payload = {stage: s1|s2}`.

**Acceptance:** resolution unit-tested for every branch with fixture runs; same paper reported across different runs creates separate records (only dedupe within a run); Langfuse score `missing_paper` carries `failure_stage` in metadata.

### C. Report-level use-intent question

**Where:** inline card immediately below the Key findings section (`surface = report_key_findings`). Not a modal.

**Copy:** "Would you use this report in your work?" — three full-width buttons: `Yes, as it is` / `Yes, with edits` / `No`; a `Not now` link. On `with_edits` or `no`, a follow-up appears in place: "What would need to change? (optional)" with multi-select chips `Missing evidence`, `Wrong emphasis`, `Accuracy concern`, `Length`, `Tone or format`, `Other`, an optional textarea, `Send` / `Skip`. After answering, collapse to one line: "Thanks — recorded as “Yes, with edits · Missing evidence”." with a `change` link.

**Show-once rules:** shown once per `(user_id, report_id)` on first open of the report; `Not now` records `use_intent = dismissed` and never re-prompts for that report; answers are editable via `change`. Record `shown_at` and `answered_at`.

**Record:** `kind = use_intent`, `target_type = report`, `payload = {use_intent: as_is|with_edits|no|dismissed, change_reasons?: [...], note?}`. Langfuse score `use_intent` with values 2/1/0 and `dismissed` recorded as a score with value null.

### D. Claim-level flag (inside the "Where this comes from" sidebar)

**Where:** clicking a claim already opens the "Where this comes from" sidebar, which shows the claim and each cited source with its supporting span. The flag lives at the **bottom of that sidebar** (`surface = report_claim_sidebar`). There is no separate popover. Add a small hover/focus affordance on each claim in the report body that opens the sidebar scrolled to the flag block — one entry point, one record. Depends on Phase 0 item 3; if claims are not addressable, implement the minimal change that makes them so before this element.

**Sidebar changes:**
- Each cited-source block gains a checkbox `Doesn't support the claim`, ticked with the span in view.
- A `Flag this claim` block at the foot: required radio "What's wrong with it?" — `Wrong` (factually incorrect) / `Overstated` (stronger than the evidence supports, e.g. certainty where the source is mixed) / `Citation doesn't support it` (tick which above); optional note; `Submit flag` / `Cancel`. Choosing `Citation doesn't support it` with no citation ticked is a validation error ("tick at least one source above").
- Track which source spans the user expanded or scrolled into view before submitting.

**Record:** `kind = claim_flag`, `target_type = claim`, `target_id = <claim_id>`, `payload = {reason: wrong|overstated|unsupported, failing_citation_ids: [...], provenance_viewed: [...citation_ids], note?, section_id, citation_ids, claim_tier}`. Also store the grounding judge's verdict for that claim (and per claim–span pair, if available) at submission time, so each flag is a labelled calibration case at the granularity the judge grades.

**Acceptance:** one flag per `(user, claim)`; re-opening the sidebar on a flagged claim shows the existing flag and allows change or retraction; `failing_citation_ids` ⊆ the claim's `citation_ids`; Langfuse score `claim_flag` with `reason` and `failing_citation_ids` in metadata.

### E. Report a problem

**Where:** persistent button in the app header on every page, including the planner and while a run is in progress. Opens a modal (the only modal in this brief).

**Modal:** "Report a problem"; radio "What kind of problem?" — `Something broke or errored` / `Search stalled or took too long` / `Output isn't usable` / `Something else`; textarea "What happened?"; a read-only "Attached automatically" box showing run ID (short), PA version, current page, pipeline step reached and its status, browser and time; a checkbox `Include my research question text` (default on); `Send report` / `Cancel`; footer "Goes to the Policy Atlas team".

**Routing:** `error` and `stalled` → engineering alert channel with a direct Langfuse trace link; `unusable` and `other` → eval backlog. Implement routing as a single function with a clear seam; stub the destinations if none exist and say so.

**Record:** `kind = problem_report`, `target_type = run` (nullable if raised on the planner before a run exists), `payload = {problem_kind, description, page, step_reached, step_status, query_text?, client}`.

### F. Onboarding profile (first access)

**Where:** full-screen card over the planner on first login (`source = signup | migration | waitlist`), before the first task. Required to proceed, with exactly one `Skip for now` allowed; re-shown at next login until completed. Editable afterwards in profile settings.

**Questions:**
1. "Where do you work?" — department `<select>` prefilled from the gov.uk email domain (maintain a domain → department map; unknown domains default to `Other…`), plus team-type chips `Policy` / `Analysis / evidence` / `Strategy & finance` / `Private office / No.10` / `Other`.
2. "What will you mainly use Policy Atlas for? (pick one)" — single-select radio: `Build or defend a spending bid` (J1), `Pressure-test someone else's bid or numbers` (J2), `Test claims in a policy proposal` (J3), `Turn evidence into briefing, fast` (J4), `Bring in international evidence and ideas` (J5), `Compare interventions across countries` (J6), `Get up to speed on a new policy area` (J7), `Something else`. An optional `+ add a second use` reveals a second single-select.
3. "Would you take part in a 45-minute hands-on session with the team?" — `Yes, contact me` / `Not now`.

The J1–J7 labels will be revised after user testing; keep them in one constants file.

**Record:** `user_profile` row: `user_id`, `department`, `team_type`, `primary_job`, `secondary_job?`, `panel_opt_in`, `source`, `completed_at`, `skipped_once_at?`. Mirror `department`, `team_type`, `primary_job`, `source` to PostHog person properties. This is a profile, not a feedback event.

## Analytics events (PostHog)

Emit, with `user_id` identified and no free text: `planner_opened`, `taskplan_approved`, `run_started`, `run_completed`, `run_failed`, `report_opened`, `report_exported`, `sources_tab_opened`, `feedback_submitted {kind, surface}`, `onboarding_completed {source}`, `onboarding_skipped`. These feed abandonment analysis; do not add more without reason.

## Deliverables and sequence

1. Phase 0 report. Stop.
2. Migration + models + envelope + Langfuse score wrapper + feature flags. PR.
3. F (onboarding) — needed first so every subsequent event is job-taggable. PR.
4. A + E. PR.
5. B, including resolution and its tests. PR.
6. C. PR.
7. D. PR.
8. Analytics events. PR.

Each PR: small, one element, tests included, a short description listing which assumptions it relies on. If anything in this brief conflicts with what you find in the code, stop and ask rather than guessing; the joins (user → profile, event → trace → artefact) are the point of the work and are not negotiable.
