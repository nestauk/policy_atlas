# Task contract: 020-extract-v2

Pre-eval **Slice B** of the owner-adjudicated sequencing (2026-07-12): the IOF
extraction-schema bump. All pending extraction wire/row/prompt-surface changes land in
**one** version bump, **before** any extraction-quality ground truth is authored — ground
truth written against the v1 record shape would need re-authoring, and every fingerprint
change re-extracts the corpus fresh (one bump = one memo invalidation, not three).

> **Status:** drafted. Contract approved (before planning): _date · owner_ ·
> Plan approved (before implementation): _date · owner_ · ADR: expected (effect-basis
> dimension decision — see step 4).

## Goal

Give the findings layer the structured fields the 018/019 live runs showed it lacks, and
close the recorded prompt-envelope injection seam, so eval ground truth is authored once
against the final pre-eval record shape:

1. **`effect_basis`** (`observed` | `modelled`, null if indeterminate) on the IOF wire +
   row — nothing structured today lets a surface render "this is a projection, not
   something that happened" (deferred.md § Extract, owner 2026-07-11). Extending
   `causality_by_design` was considered and disliked: causal identification and evidence
   basis are different dimensions (a model calibrated on RCTs is still modelled).
2. **Prompt-envelope fencing** (011 review, security) — the envelope title/abstract are
   interpolated inline in the user template today, so a hostile abstract can structurally
   spoof the template; fence the envelope as an id-keyed JSON data object, the treatment
   segments already get. Recorded to ride "the next version bump" — this is that bump.
3. **`study_geography`** (rev 3.2, user; named in 019's out-list as Slice B cargo) — no
   search API supplies study geography; a source-named extraction field is the recorded
   remedy, feeding the 010 selection-diversity seam, characterise's post-extraction
   coverage dimensions and the Transferability capability. This slice lands the field
   and its render surfaces only — the diversity consumers stay deferred.

## Deliverable

One PR to `dev` landing the schema v2 bump end-to-end: wire + stored models, DB columns +
CHECKs with an alembic migration, `extract_iof_v6` prompt (fencing + new-field guidance,
lead-authored, replay-evidenced), field-rules v2, fingerprint bumps, and the new fields
carried through the writer envelope (`query_findings`) and the annotation payload. The
three source deferrals discharged or narrowed in `docs/deferred.md`; the data-model spec's
findings-layer base-field list updated by flow-back (the task-011 pattern).

## Read first

- `docs/deferred.md` — the three entries this discharges: § Extract (modelled-vs-observed
  effect basis · prompt envelope fencing) and § Live search (study-geography extraction
  field, near the rev-3.10 seams).
- [data-model](../../specs/system/data-model.md) § The findings layer — the base-field
  rationale and the "upgrades never invalidate existing findings" rule this slice must
  honour; this spec receives the flow-back.
- [EB capability](../../specs/capabilities/evidence-base/capability.md) § extraction +
  [provenance](../../specs/capabilities/evidence-base/provenance.md) — coverage-state and
  anchor discipline for the new nullable fields.
- `docs/specs/system/prompting.md` — binding for the prompt work.
- `docs/tasks/011-extract/contract.md` — pattern precedent (the schema's own contract).
- Code spine: `extraction_records.py` (wire/stored + `SCHEMA_VERSION`),
  `extract_prompt.py` (`PROMPT_VERSION`, user template), `quote_verify.py`
  (`iof_rules_v1`, field coverage), `schema.py` (`intervention_outcome_finding`),
  `extract.py` (fingerprint components), `synthesis_tools.py` (`FindingRecord`,
  `query_findings`), `synthesise.py` (`_load_findings` → annotation payload).

## Scope / Out of scope

**In:**

1. **Wire + stored models** (`extraction_records.py`): `effect_basis` Literal
   (`observed` | `modelled`) | null and `study_geography` source-named nullable field on
   `IOFRecordWire`/`IOFRecord`; field descriptions (they generate the prompt's field
   reference); `SCHEMA_VERSION` → `iof_v2`; import-time CHECK-vocabulary asserts extended.
   ❓ `study_geography` wire shape — single source-named string (as the document reports
   it, e.g. "12 OECD countries") vs structured list — adjudicated at plan approval;
   default: single source-named string, canonicalisation stays downstream (the data-model
   source-named-reference discipline).
2. **DB schema + migration** (`schema.py`, `alembic/versions/`): two nullable columns on
   `intervention_outcome_finding`, CHECK on `effect_basis`, up/down migration. **No
   backfill** — existing v1 rows keep null (the spec's upgrades-never-invalidate rule);
   new fingerprints create records alongside, never rewrite. **Schema gate — see
   Constraints.**
3. **Field rules v2** (`quote_verify.py`): `iof_rules_v2` — coercion + `field_coverage`
   markers for the two new nullable fields; version constant bump.
4. **Prompt `extract_iof_v6`** (`extract_prompt.py`) — **prompt-bearing: lead-only,
   replay-evidenced**: (a) envelope fencing — title/abstract leave the inline template
   and enter as a JSON data object; (b) `effect_basis` guidance (observed vs
   modelled/projected; the existing aspiration exclusions stand — a modelled *result* is
   a finding with `effect_basis` "modelled", a target is still not a finding);
   (c) `study_geography` guidance (where conducted, as the document names it — not
   publisher country); (d) few-shot example updated (pre-flight validation binding).
5. **Fingerprint + memo**: version-constant bumps flow into `extraction_fingerprint`
   (components map already carries profile/schema/prompt/rules). ❓ whether `PROFILE_ID`
   `eb_iof_base_v1` also bumps — plan decision. Test pins: old-fingerprint records reuse;
   new fingerprint extracts fresh alongside.
6. **Downstream carriage**: `FindingRecord` + the `query_findings` SELECT/mapping
   (`synthesis_tools.py`) and `_load_findings` (`synthesise.py`) carry the new fields, so
   the writer envelope (terse-adjacent, omit-if-absent stays as-is for metadata; the new
   fields are record fields, always-present-nullable like `study_design`) and the
   annotation payload render them. Read side tolerates old rows (null) by construction.
7. **Finding vetter**: new fields flow through its input records; ❓ whether the vetter
   prompt gains an effect-basis line (lead-only if touched; `extract_finding_vetter_v2`
   bumps only if its text changes) — plan decision.
8. **Spec flow-back + deferrals**: data-model findings-layer base fields gain the two
   fields with a task-020 flow-back note + `log.md` line; the three deferred.md entries
   discharged (effect_basis, fencing) or narrowed (study-geography: field landed,
   diversity consumers remain).

**Out:** extraction-quality evals and ground truth themselves (next after Slice C) ·
Slice C surfaces (multi-facet grouping, cost/surface work) · multi-pass recall,
retrieval-augmented extraction, per-intervention decomposition (eval-gated, unchanged) ·
`implementation_context_finding` · geography canonicalisation/ISO mapping and any
selection-diversity or characterise consumer of it · annotation *widget* rendering
(web-app slice; this slice makes the payload carry the fields) · vetter behaviour changes
beyond the optional guidance line · Bedrock · everything else in `docs/deferred.md`.

## Constraints & approval gates

- **Schema (needs human approval):** item 2 — two columns + one CHECK on
  `intervention_outcome_finding`, with down-migration. No other table changes.
- **No backfill / no invalidation:** existing findings rows and extraction records are
  untouched; the old fingerprint's memo entries stay valid for the old shape. Any
  temptation to rewrite v1 rows is a stop condition.
- **Prompt-bearing surfaces are lead-only** (AGENTS.md): `extract_iof_v6`, any vetter
  guidance line. Delegation of the mechanical carriage (models, migration, SELECTs,
  tests) is expected — routing marked at plan time.
- **Egress:** none new — same OpenAI route, same model (`gpt-5.4-mini` floor unchanged);
  replay probes are pennies (018 live-check pin).
- **Deps/CI/public interfaces:** untouched.

## Public / private boundary

All code, migrations and spec changes are public-safe. Replay evidence lands as summaries
in `verification.md`; raw traces stay in Langfuse.

## Model route

Extraction stays `gpt-5.4-mini` via the OpenAI route (contracted floor; a step-up remains
a recorded option, not a silent switch). One prompt-bearing change: `extract_iof_v6`
(lead-authored). Replay set: recorded extraction probes over fixture/real corpus docs,
including at least one modelled-projection document, one document with reported study
geography, and one hostile-envelope (instruction-like abstract) fencing probe.
**Honesty pin:** prompt changes are eval-blind until the extraction-quality evals exist —
replay evidence shows shape and non-regression on probes, it does not certify quality;
that is exactly why this bump precedes ground truth.

**Live-check scope (contract-time pin):** replay probes above + one scoped live
extract → synthesise pass over a small already-screened selection from an existing
project (evidences fingerprint-fresh extraction and envelope/annotation carriage). No
composed full-chain e2e; D2's rehearsal owns that separately.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — both fields ship with their render surfaces (writer
  envelope + annotation payload); no speculative enrichment beyond that.
- **Flag, don't drop** — null `effect_basis` is honest indeterminacy, never guessed;
  `field_coverage` records absence per field.
- **Honest absence** — old rows render as "not recorded under v1", never as "observed".
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: the schema gate is hit without recorded approval · the wire-shape
❓s resolve toward anything beyond two fields (scope growth into Slice C or eval
territory) · fencing turns out to require restructuring the windowing/payload seam rather
than the message template · any pressure to backfill or rewrite v1 rows · budget spent.

## Acceptance checks

- `make verify` green.
- Deterministic tests: migration up/down · CHECK vocabulary ↔ Literal asserts ·
  `iof_rules_v2` coercion + coverage for the new fields · fingerprint change (old memo
  reused under old fingerprint, v2 extracts fresh alongside) · `render_field_docs`
  carries the new fields · user template contains no inline title/abstract interpolation
  (structural fencing check) · few-shot pre-flight still binding · `query_findings` /
  `_load_findings` / annotation payload carry the fields; old-row null tolerance.
- Replay evidence (AI-behaviour, honestly eval-blind): the probe set above, summarised in
  verification.md — including the modelled-projection doc yielding `effect_basis`
  "modelled" and the fencing probe leaving fields unaffected.
- Manual: the scoped live check named under Model route.

## Verification evidence expected

`verification.md`: command results, migration up/down evidence, replay summaries, the
schema-gate approval with owner sign-off date, deferred.md + spec flow-back diff summary,
known gaps.

## Risk tier & review focus

**Tier 3** — schema hard gate + prompt-bearing change + a security-motivated fencing fix.
Contract- and plan-stage adversarial reviews per the design skill; review stack per
[review-stack economy]: medium `/code-review`, one security lane (fencing completeness —
does any envelope text still reach the prompt outside a data object; migration
correctness), contract verifier fresh-context, per-angle diff scoping.

Focus: no invalidation of existing findings · fencing completeness · prompt guidance not
weakening the aspiration exclusions (the vetter's ground) · fingerprint completeness
(every output-affecting change versioned) · no scope creep into eval or Slice C surfaces.
