# Database tables

`schema.py` is the source of truth for the database's shape — this file is the
source of truth for what each table is *for*. Read them side by side: the code
tells you the columns and constraints, this tells you why they exist and what a
row means.

Scope: 32 tables plus one read view (`finding_reference_union`), all in one
`MetaData()` in `schema.py`. Tables are grouped below exactly as `schema.py`
groups them, in file order, so anything you find here is findable there. Two
tables sit in older sections than they belong to — `conversation` and
`chat_turn` are both part of the task 029 conversation model — because the
section comments predate them.

## Keeping this honest [Claude's instructions]

- A new table means a new entry here, in the same section as `schema.py` puts it.
- Changing what a column *means* means editing its row here, even when the type
  doesn't change. A stale description is worse than no description.
- Don't restate the column type or the constraint expression — the code already
  says that, and a copy will drift. Say what the value *means* and what it is
  for. Where a constraint encodes a rule that isn't obvious, name the rule.

## The template

Each entry looks like this.

```markdown
### `table_name`

One or two sentences: what one row represents, and who writes it.

| Column | What it holds |
| --- | --- |
| `column_name` | Plain-English meaning. |

**Rules worth knowing** — constraints that encode a decision rather than a type.
```

---

## User feedback (task 032)

### `user_feedback`

One row is one piece of feedback a **human** typed or clicked in the app. Both
in-app feedback surfaces write here, told apart by `kind`:

- `source_not_relevant` — someone pressed the flag button on a source in the
  Sources table or the source dossier, saying the pipeline shouldn't have
  treated it as relevant.
- `issue_report` — someone wrote free text into "Report an issue" in the
  project nav.

Two things to hold onto. **No model is involved on either path** — the text is
stored exactly as typed and nothing generates, summarises or answers it.
And **nothing in the analysis pipeline reads this table**: flagging a source
does not change its status on the evidence ladder, whether it gets selected, or
whether it gets cited. Later on, we could update the methodology so that sources flagged as not relevant get deleted from downstream analysis.

| Column | What it holds |
| --- | --- |
| `user_feedback_id` | The row's own identity. |
| `project_id` | The project the feedback is about. Always set — feedback is only offered on project pages, so every row belongs to exactly one project. |
| `kind` | Which of the two feedback surfaces wrote this row: `source_not_relevant` or `issue_report`. Everything else on the row depends on this. `issue_report` = free-text bug report; `source_not_relevant` = the flag toggle was clicked to indicate that a source was deemed not relevant. |
| `user_id` | Who said it — the Cognito token's `sub`, an opaque identifier, *not* an email address. Locally this is always `dev-user`. Kept for audit; today's single-owner projects make it nearly redundant, but it is what makes the flag per-person if projects ever gain collaborators. |
| `project_source_snapshot_id` | Which source was flagged. Set on `source_not_relevant` rows, empty on `issue_report` rows. This is the same source identity the API exposes as `source_id`. |
| `body` | The free text of an issue report, whitespace-trimmed, 1–4000 characters. Empty on flag rows — a flag carries no words. |
| `page_path` | The in-app path the reporter was looking at, e.g. `/projects/<id>/sources`. The most useful column for triage: it tells you which screen a complaint is about without the reporter having to describe it. Empty on flag rows. |
| `created_at` | When the feedback was recorded. |

**Rules worth knowing**

- `ck_ufb_kind` pins `kind` to exactly those two values, so a third kind of
  feedback cannot appear without a migration. If you are grouping by `kind`,
  those are the only two buckets you will ever get from today's schema.
- `ck_ufb_shape` makes the two kinds mutually exclusive at the database level: a
  flag must name a source and carry no text; a report must carry text and name
  no source. A row can never be half of each, whatever the API does.
- `ux_ufb_source_flag` is a partial unique index over
  `(project_source_snapshot_id, user_id)` covering flag rows only. It is what
  makes flagging idempotent — pressing the button twice cannot produce two rows,
  and that guarantee lives in the database rather than in the handler.
- `fk_ufb_pss_project` is a composite foreign key on
  `(project_source_snapshot_id, project_id)` with `MATCH SIMPLE`. The
  `MATCH SIMPLE` is what lets issue reports, which have no source, satisfy it:
  a row with a null in the pair is accepted. For flag rows both halves are set,
  so the pair is fully enforced and a flag cannot point at a source in another
  project.

**A caveat for anyone analysing this table.** Un-flagging *deletes* the row, so
`source_not_relevant` rows are current state, not history: you can ask what is
flagged right now, but not what was ever flagged, or how often people change
their minds. Issue reports are append-only, so those are full history. If flag
history is ever needed, that's a schema change (a `cleared_at` column instead of
a delete, or an `event_log` entry per toggle). A worked analysis of both kinds,
including the join that compares a human flag against what screening decided,
is in `scripts/scratchpad/user_feedback/feedback_analysis.ipynb`.

---

## Core artefact + run model (tasks 001–002)

### `project`

_TODO: what one row represents, and who writes it._

| Column | What it holds |
| --- | --- |
| _TODO_ | _TODO_ |

### `artefact`

_TODO. Note `capability_run_id` links the artefact to the walk that produced it._

### `conversation`

_TODO. Part of the task 029 conversation model: a project holds many
conversations — one planning conversation per plan lineage, plus follow-up
chats. Worth covering the `kind`/`status` vocabulary and the
one-active-planning-conversation rule._

### `block`

_TODO._

### `addressable_unit`

_TODO._

### `annotation`

_TODO._

### `runs`

_TODO. Worth distinguishing from `capability_run` below — this is the component
run, that is the orchestrated walk._

### `event_log`

_TODO. The append-only project event stream. Worth covering what belongs in a
payload, and that several read models recover detail from here that exists
nowhere else (screening and classification reasons, for instance)._

---

## Corpus / source model (task 003)

### `source_snapshot`

_TODO. Content-identified and deliberately **not** project-scoped — identity is
content, not project. Worth listing what lives in the `metadata` envelope._

### `project_source_snapshot`

_TODO. Corpus membership, and the public identity of a source (the API's
`source_id`). Worth covering `origin` and the full-text attachment triple
(`full_text_snapshot_id` / `full_text_status` / `full_text_error`) and the rules
tying them together._

### `chunk`

_TODO._

### `citation`

_TODO._

---

## Screening model (task 004)

### `evidence_scope`

_TODO._

### `source_screening_result`

_TODO. Append-only: re-screens add rows rather than updating them, so "the"
verdict for a source is derived, not stored. Worth explaining the effective-row
rule (newest generation first, then highest stage) and pointing at
`effective_screen_rows()`, which every consumer should join instead of filtering
on raw `status`._

---

## Classification model (task 005)

### `source_classification_result`

_TODO._

---

## Appraisal model (task 006)

### `source_appraisal_result`

_TODO._

---

## Acquisition model (task 007)

### `search_coverage_record`

_TODO._

---

## Characterise model (task 009)

### `chunk_embedding`

_TODO._

### `characterisation_result`

_TODO._

---

## Select model (task 010)

### `selection_result`

_TODO._

### `source_tag`

_TODO. Pipeline-owned, not user-owned: every row carries the run that asserted
it. Worth explaining why the same tag from two asserters is two rows
(corroboration, not duplication)._

---

## Extract / findings layer (task 011)

### `source_extraction_record`

_TODO._

### `intervention_outcome_finding`

_TODO._

### `implementation_context_finding`

_TODO._

### `finding_reference_union`

_TODO. **A read view, not a table**, despite being declared as one in
`schema.py` so queries can join it. Created and dropped by migration
`7a4d9c2e1f6b`. Worth explaining what it unions and why the two finding kinds
need a common surface._

### `extraction_result`

_TODO._

---

## Group / facet-level theming (task 012)

### `grouping_result`

_TODO._

---

## Synthesise model (task 013)

### `synthesis_result`

_TODO._

---

## Orchestration plan (task 017)

### `orchestration_plan`

_TODO._

---

## Durable planning transcript (task 027)

### `planning_transcript`

_TODO. Worth explaining why the raw planner state and the projected HTTP
response are stored separately, and that `turn_index` — not `created_at` — is
the ordering coordinate._

---

## Capability run (task 024)

### `capability_run`

_TODO. One row per orchestrated walk. Worth covering the status vocabulary and
how `runs.capability_run_id` attributes component runs to the walk they ran
inside._

### `chat_turn`

_TODO. Part of the task 029 conversation model rather than task 024 — it sits
here because the section comments predate it._
