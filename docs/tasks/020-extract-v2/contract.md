# Task contract: 020-extract-v2

Pre-eval **Slice B** of the owner-adjudicated sequencing (2026-07-12): the IOF
extraction-schema bump. All pending extraction wire/row/prompt-surface changes land in
**one** version bump, **before** any extraction-quality ground truth is authored — ground
truth written against the v1 record shape would need re-authoring, and every fingerprint
change re-extracts the corpus fresh (one bump = one memo invalidation, not three).

> **Status:** approved. Contract approved (before planning): 2026-07-12 · owner
> (with contract-review amendments: three riders folded in; study_geography settled at
> finding grain; window ceiling declined; ICF promoted to slice 021) ·
> Contract-stage adversarial review: codex session 019f565f (2026-07-12), 8 findings all
> adjudicated in — semantics sharpenings, no material scope change (claim-key and
> annotation-carriage decisions flagged below for the plan 🛑) ·
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
carried through the writer envelope (`query_findings`) and the annotation payload. Three
riders folded in at contract review (owner, 2026-07-12): the evidence-type provenance
column on `source_extraction_record`, mixed/unclear carry-through tests, and the
`_load_findings` batch load. The source deferrals discharged or narrowed in
`docs/deferred.md`; the data-model spec's findings-layer base-field list updated by
flow-back (the task-011 pattern).

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
   **`study_geography` grain settled (owner, 2026-07-12, contract review): finding
   grain**, single source-named string — "the geography of the evidence underlying this
   finding, exactly as the document reports it" (e.g. "United Kingdom", "12 OECD
   countries"), null when unreported, never inferred. Rationale: geography is
   document-constant only for primary studies; in reviews (the corpus's dominant shape)
   it varies per finding — the same usually-constant-but-review-variable pattern
   `population`/`study_design`/`comparator` already sit at finding grain for. A
   document-grain field would need a new doc-level wire surface + cross-window
   reconciliation; document-level geography is instead a derived aggregation, deferred
   with the diversity consumers. Canonicalisation stays downstream (source-named-reference
   discipline).
   **Claim-key/dedup (adversarial finding 1, lead-adjudicated — plan 🛑 reviews):**
   `effect_basis` JOINS `claim_key` — an observed claim and a modelled projection of the
   same effect are different claims; collapsing them under first-wins would silently
   drop the basis distinction the field exists to make. `study_geography` does NOT join
   the key, matching `population`/`study_design` (descriptive study metadata,
   first-wins); geography-scoped *claims* are already stratum territory. Tests pin both
   behaviours.
2. **DB schema + migration** (`schema.py`, `alembic/versions/`): two nullable columns on
   `intervention_outcome_finding`, CHECK on `effect_basis`, up/down migration. **No
   backfill** — existing v1 rows keep null (the spec's upgrades-never-invalidate rule);
   new fingerprints create records alongside, never rewrite. **Schema gate — see
   Constraints.**
3. **Field rules v2** (`quote_verify.py`): `iof_rules_v2` — coercion + `field_coverage`
   markers for the two new nullable fields; version constant bump. The rules define the
   full coverage mapping per field (adversarial finding 6): valid value · null/unreported
   (`not_extracted`) · unclear/indeterminate · invalid enum value (coerce-and-flag, never
   reject the record) — so a null is never ambiguous within v2.
   **Old-row distinguisher (adversarial finding 3):** a v1 row's `field_coverage` lacks
   the new keys entirely — key-absence (plus the extraction record's schema version) IS
   the "not recorded under v1" signal, distinct from a v2 null. Readers must not conflate
   them; tests cover v1-null vs v2-null separately.
4. **Prompt `extract_iof_v6`** (`extract_prompt.py`) — **prompt-bearing: lead-only,
   replay-evidenced**: (a) envelope fencing — title/abstract AND `primary_evidence_type`
   leave the inline template and enter as one JSON data object (adversarial finding 8:
   evidence type is closed-vocabulary today, but uniform fencing is free and removes the
   structural exception); (b) `effect_basis` guidance (observed vs
   modelled/projected; the existing aspiration exclusions stand — a modelled *result* is
   a finding with `effect_basis` "modelled", a target is still not a finding);
   (c) `study_geography` guidance carrying two distinctions: stratum-vs-geography (a
   geographic subgroup estimate is a `stratum_qualifiers` entry scoping the *claim*;
   `study_geography` records where the underlying evidence was *conducted* — they
   coexist) and study-vs-publisher (never inferred from publisher, venue or author
   affiliation; reported-or-null); (d) few-shot example updated (pre-flight validation
   binding).
5. **Fingerprint + memo**: version-constant bumps flow into `extraction_fingerprint`
   (components map already carries profile/schema/prompt/rules). ❓ whether `PROFILE_ID`
   `eb_iof_base_v1` also bumps — plan decision. Test pins: old-fingerprint records reuse;
   new fingerprint extracts fresh alongside.
6. **Downstream carriage**: `FindingRecord` + the `query_findings` SELECT/mapping
   (`synthesis_tools.py`) and `_load_findings` (`synthesise.py`) carry the new fields in
   the writer envelope (terse-adjacent, omit-if-absent stays as-is for metadata; the new
   fields are record fields, always-present-nullable like `study_design`).
   **Annotation-layer carriage corrected (adversarial finding 2):** the finding-claim
   annotation payload today carries claim text + anchors + cited finding ids, NOT
   record metadata — the new fields are *reachable* at the annotation layer via the
   cited finding row (read surfaces resolve `finding_id`). Whether the citation payload
   additionally embeds the two fields is a ❓ plan decision, with a recorded leaning
   (🟡 owner-checked, 2026-07-12): don't embed in 020 — resolve-via-row is the shipped
   read-surface pattern (demo readmodels), 018's metadata work landed on the *writer*
   envelope + judge envelope v2 (quote/chunk-text/context, no record metadata), and no
   recorded C-slice work touches annotation payloads; the consumer slice that builds the
   surface decides, and nothing in 020 blocks embedding later. Read side tolerates old
   rows per item 3's distinguisher.
   Also in scope (adversarial finding 7): the stub/fixture surface — the stub extraction
   backend's sentinel payloads and shared test record factories gain the new wire fields
   (default null), named here so they're scope, not mid-build creep.
7. **Finding vetter**: corrected (adversarial finding 5) — `_judge_payload_entry`
   serializes a fixed field subset today, so the new fields do NOT reach the vetter
   automatically. ❓ plan decision, decided explicitly and test-pinned either way:
   whether the vetter payload gains `effect_basis` (note the interaction risk: showing
   the model its own basis label could bias aspiration flagging) and whether the vetter
   prompt gains a guidance line (lead-only if touched; `extract_finding_vetter_v2` bumps
   only if its text changes).
8. **Spec flow-back + deferrals**: data-model findings-layer base fields gain the two
   fields with a task-020 flow-back note + `log.md` line; deferred.md entries discharged
   (effect_basis, fencing, `_load_findings` batch) or narrowed (study-geography: field
   landed, diversity consumers remain; evidence-type: column landed, memo-match rule
   remains; mixed/unclear: carry-through pinned). The sweep also ADDS one seam entry
   (docs only, no build): **`effect_basis` as a judge-envelope candidate** — the
   grounding judge seeing the structured basis signal (prose asserting an effect while
   citing a modelled projection is a faithfulness question); any judge-envelope change
   is bound by 018's verification-grade A/B protocol, so it lands at the C/eval gate,
   never silently.
9. **Evidence-type provenance rider (011 review, Codex — folded in at contract review)**:
   record the `primary_evidence_type` actually sent to the prompt on
   `source_extraction_record` (nullable Text; rides the same migration). Honest
   provenance for ground-truth annotation. The memo-match rule stays deferred — its
   trigger (extract-before-classify plans) still doesn't exist. ❓ whether the column
   gets a CHECK against the classify vocabulary + `Unclassified` — plan decision.
   **Consumption semantics pinned (adversarial finding 4):** the column is
   extraction-call provenance only (audit + ground-truth annotation); writer/annotation
   surfaces keep reading the live joined classification value — the two may legitimately
   diverge and no surface silently substitutes one for the other.
10. **Mixed/unclear carry-through tests (V2 requirement carried forward)**: tests pinning
    that `mixed`/`unclear` effect-direction findings survive `group` and `synthesise`
    (never dropped at aggregation — the V2 silent-zeroing autopsy). Expected
    already-correct behaviour; the tests must exist before eval baselines regardless.
    Behaviour fixes only if a test exposes a drop — anything larger is a stop condition.
11. **`_load_findings` batch-load rider (013 review, confirmed N+1)**: replace the
    per-snapshot basis query loop with one batched `IN (...)` query — mechanical,
    behaviour-preserving, in the function item 6 already touches.

**Out:** extraction-quality evals and ground truth themselves (next after Slice C) ·
Slice C surfaces (multi-facet grouping, cost/surface work) · multi-pass recall,
retrieval-augmented extraction, per-intervention decomposition (eval-gated, unchanged) ·
`implementation_context_finding` — **promoted to its own pre-eval slice 021 (owner,
2026-07-12)**: EB synthesis is its first reader (the deterministic validator for
implementation-shaped pattern claims); posture pinned — a separate extraction
call/profile with its own fingerprint domain, so nothing in 020 couples to it and its
later arrival never invalidates 020's memo · geography canonicalisation/ISO mapping and any
selection-diversity or characterise consumer of it · annotation *widget* rendering
(web-app slice; this slice makes the payload carry the fields) · vetter behaviour changes
beyond the optional guidance line · the per-run window/call ceiling (owner call,
2026-07-12: select's budget + fetch size caps bound the exposure and extraction is
mini-priced — stays deferred on its "arbitrary corpora" trigger) · the memo-match rule
for evidence type (trigger unfired) · Bedrock · everything else in `docs/deferred.md`.

## Constraints & approval gates

- **Schema (needs human approval):** items 2 + 9 — two columns + one CHECK on
  `intervention_outcome_finding`, one provenance column on `source_extraction_record`,
  one migration with down-migration. No other table changes.
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
including at least one modelled-projection document, one primary study with reported
study geography, one review-shaped document where geography attaches at finding grain
(pooled scope or per-included-study), and one hostile-envelope (instruction-like
abstract) fencing probe.
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
  `_load_findings` / annotation payload carry the fields; old-row null tolerance ·
  evidence type recorded on the extraction record matches what the prompt was sent
  (incl. the `Unclassified` default) · mixed/unclear findings survive group + synthesise
  end-to-end · `_load_findings` batch load is behaviour-preserving (same output, one
  basis query) · dedup: observed-vs-modelled twins do NOT collapse, geography-only
  twins DO (first-wins recorded) · v1-null vs v2-null distinguishable via
  `field_coverage` key-absence · vetter payload shape pinned per the plan decision.
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
