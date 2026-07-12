# Plan: 020-extract-v2

> **Status:** DRAFTED — awaiting plan-stage adversarial review + owner approval, with
> three gate decisions to adjudicate (§ Gate decisions).
> Contract: [contract.md](contract.md) (approved 2026-07-12, adversarial-reviewed,
> owner checks folded). Rubric: [rubric.md](rubric.md).
> Executor marks default to subagents (orchestrator-delegation convention); lead marks
> carry justification inline. Codex caveat (019 precedent): the codex sandbox has no
> Postgres — the lead runs DB-gated acceptance after each codex delivery.

## Phases

**Phase 0 — baseline + gate package** — **lead** *(gate adjudication is judgment)*
- Full `make verify` baseline (mandatory open-gate class; never build on red).
- Present § Gate decisions → 🛑 owner adjudication at plan approval. Phase A does not
  start until decisions 1–3 clear (they shape its diff).

**Phase A — schema core (the gated centre)** — **codex** *(judgment-bearing multi-file
coherence with a machine-verifiable done: tests + mypy/ruff pin every semantic)*
- `schema.py`: `EFFECT_BASES` vocabulary tuple (`observed`, `modelled`) · two nullable
  columns on `intervention_outcome_finding` (`effect_basis` Text + CHECK,
  `study_geography` Text) · `primary_evidence_type` nullable Text on
  `source_extraction_record` (+ CHECK per decision 3).
- Alembic migration (one file, both tables) + symmetric down-migration; migration
  up/down test (precedent: `test_screen_step_rename_migration.py`). No backfill —
  v1 rows keep null; test pins existing rows untouched across up/down.
- `extraction_records.py`: `EffectBasis` Literal + the two fields on
  `IOFRecordWire`/`IOFRecord`; import-time CHECK-vocabulary assert extended;
  `SCHEMA_VERSION` → `iof_v2`. **Field description text is supplied verbatim in the
  codex brief by the lead** — descriptions generate the prompt's field reference
  (prompt-bearing; the plumbing is mechanical, the words are not).
- `quote_verify.py`: `claim_key` gains `effect_basis` (settled: basis twins are
  distinct claims; geography stays out) + dedup twin tests (basis twins do NOT
  collapse; geography-only twins DO, first-wins pinned). `iof_rules_v2`
  (`FIELD_RULES_VERSION` bump): coercion + the full coverage mapping per new field —
  valid value · null/unreported (`not_extracted`) · unclear · invalid enum value
  (coerce-and-flag, never reject the record) — with table-driven tests; v1-null vs
  v2-null distinguisher test (coverage key-absence).
- `extract.py`: record the evidence type actually sent (incl. `Unclassified` default)
  on the extraction-record insert; fingerprint tests (old memo reused under old
  fingerprint; v2 extracts fresh alongside — the components map picks up the version
  constants with no structural change).
- Stub/fixture surface: stub extraction backend sentinel payloads + shared test record
  factories gain the wire fields (default null).
- Gate: **full `make verify`** at Phase A exit (schema/ingest-adjacent mandatory class).

**Phase B — prompt `extract_iof_v6`** — **lead** *(prompt-bearing: product prompt +
few-shot example are lead-only by AGENTS.md)*
- Fencing: title + abstract + `primary_evidence_type` leave the inline user template
  and enter one id-keyed JSON data object; structural test pins that the template
  retains no inline envelope interpolation.
- Guidance: `effect_basis` (observed vs modelled/projected; the aspiration exclusions
  stand — a modelled *result* is a finding, a target still is not) · `study_geography`
  (conducted-in, reported-or-null; the stratum-vs-geography and study-vs-publisher
  distinctions per the contract).
- Few-shot example gains the new fields (pre-flight validation binding);
  `PROMPT_VERSION` → `extract_iof_v6`.
- Replay evidence (pennies, unrestricted per the 018 pin): recorded extraction probes —
  one modelled-projection doc · one primary study with geography · one review-shaped
  doc (geography at finding grain: pooled scope or per-included-study) · one
  hostile-envelope fencing probe (instruction-like abstract; fields unaffected).
  Eval-blind honesty line rides the verification.md summary.
- Gate: `make verify-fast` (prompt + tests only; no schema contact).

**Phase C — downstream carriage** — **fast-worker** *(mechanical transcription of a
precise spec: the contract names every field, file and behaviour; tests pin each)*
- `synthesis_tools.py`: `FindingRecord` + the `query_findings` SELECT/mapping carry
  `effect_basis` + `study_geography` (record fields, always-present-nullable like
  `study_design`).
- `synthesise.py`: `_load_findings` SELECT + record dict carry both fields; the
  **batch-load rider** — replace the per-snapshot basis query loop with one batched
  `IN (...)` query; behaviour-preserving test (same output, one basis query).
  Annotation payload untouched (settled: no embedding).
- Vetter payload pin test per decision 2 (shape snapshot — new fields deliberately
  absent; no vetter prompt/version change).
- Mixed/unclear carry-through tests: `mixed`/`unclear` effect-direction findings
  survive `group` and `synthesise` end-to-end (fixture-driven; behaviour fixes only if
  a test exposes a drop — larger is the contract's stop condition).
- Old-row null tolerance tests on both read paths.
- Gate: `make verify-fast` (readers + tests; no schema contact — consolidated per the
  gate-consolidation rule, full verify already ran at A and runs again at exit).

**Phase D — records + live check + review prep** — **lead** judgments,
**fast-worker** sweeps
- Spec flow-back (fast-worker draft, lead review): data-model.md findings-layer base
  fields gain both fields with a task-020 note; spec-bundle `log.md` line.
- deferred.md sweep (fast-worker draft, lead review): discharge effect_basis + fencing
  + `_load_findings` batch; narrow study-geography (field landed, diversity consumers
  remain) · evidence-type (column landed, memo-match rule remains) · mixed/unclear
  (carry-through pinned); ADD the two seam entries — `effect_basis` as judge-envelope
  candidate (018 A/B protocol binds, C/eval gate) · 018's dangling A/B-gated
  writer-envelope metadata queue (institutions → FWCI → further fields).
- ADR 0016 (**lead** — design-decision record is judgment): effect basis as its own
  dimension (not a `causality_by_design` extension), finding-grain geography, the
  claim-key adjudication, no-backfill posture. Status Accepted at plan sign-off date.
- **Scoped live check** (**lead** — live env + adjudication): fresh-fingerprint live
  extract over a small already-screened selection from an existing dev-DB project
  (018 replay substrate; reuse, don't re-search) → verify rows carry the new fields +
  coverage keys + evidence-type provenance → one synthesise referencing that extraction
  run → verify writer-envelope carriage and annotation resolve-via-row on the minted
  artefact. NO composed full-chain e2e (D2 owns that).
- verification.md complete: command results, migration up/down evidence, replay
  summaries, gate decisions with sign-off dates, deferred/spec diff summary, known gaps.
- Gate: **full `make verify`** at step-6 exit (mandatory final-exit class).

## Gate decisions (adjudicate at this plan approval)

1. **`PROFILE_ID` bump** (`eb_iof_base_v1` → v2?): *Recommend NO bump.* The profile
   names EB's extraction-requirement identity ("EB's base IOF extraction"), which is
   unchanged; the schema, prompt and rules version bumps already enter the fingerprint
   separately, so reuse semantics are fully covered — a profile bump would be a
   redundant second invalidation lever with no distinct meaning. Rationale recorded in
   the ADR.
2. **Vetter payload + guidance**: *Recommend UNCHANGED on both.* No vetter flag class
   (aspiration, deictic naming, …) consumes the new fields; showing the model its own
   `effect_basis` label risks biasing aspiration flagging (contract-noted); the
   modelled-results-are-kept rule already lives in the vetter prompt. No payload
   change → no `extract_finding_vetter_v2` bump. A shape-snapshot test pins the
   decision either way.
3. **Evidence-type CHECK on `source_extraction_record.primary_evidence_type`**:
   *Recommend YES* — CHECK against the existing `EVIDENCE_TYPES` tuple +
   `'Unclassified'` (the prompt default). The vocabulary is closed and
   developer-controlled (the classification table already CHECKs the same tuple);
   fail-loud beats silently recording a typo'd provenance value.

## Live-check pins

Extraction replay probes: pennies, unrestricted. ONE scoped live
extract → synthesise pass (Phase D; bounded substrate, ~$10–20 expected — synthesise
dominates). NO composed full-chain e2e runs.

## Dependencies

Decisions 1–3 → Phase A. A → B (models generate the field reference the prompt embeds)
and A → C (readers need the columns). B → the Phase D live check (it exercises v6).
C's carriage → the live check's synthesise leg. D's sweeps close last. Phases B and C
are independent of each other and can overlap once A lands.
