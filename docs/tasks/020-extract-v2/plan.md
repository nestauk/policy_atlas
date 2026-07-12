# Plan: 020-extract-v2

> **Status:** DRAFTED — plan-stage adversarial review adjudicated (codex, 2026-07-12,
> 9 findings all folded; the vetter recommendation flipped to a guidance line), awaiting
> owner approval with four gate decisions to adjudicate (§ Gate decisions).
> Contract: [contract.md](contract.md) (approved 2026-07-12, adversarial-reviewed,
> owner checks folded). Rubric: [rubric.md](rubric.md).
> Executor marks default to subagents (orchestrator-delegation convention); lead marks
> carry justification inline. Codex caveat (019 precedent): the codex sandbox has no
> Postgres — the lead runs DB-gated acceptance after each codex delivery.

## Phases

**Phase 0 — baseline + gate package** — **lead** *(gate adjudication is judgment)*
- Full `make verify` baseline (mandatory open-gate class; never build on red).
- Present § Gate decisions → 🛑 owner adjudication at plan approval. Phase A does not
  start until decisions 0–3 clear (they shape its diff). Decision 0 is the schema gate
  itself, named explicitly — approval of decisions 1–3 alone does NOT license the
  migration (adversarial finding 3).

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
  `SCHEMA_VERSION` → `iof_v2`. **Wire-enum posture (adversarial finding 1):**
  `effect_basis` is a strict Literal on the wire, the `causality_by_design` precedent —
  schema-constrained structured output makes an invalid enum value unrepresentable at
  the API boundary, so `iof_rules_v2` carries NO invalid-enum recovery row for it (the
  contract's coverage mapping is amended to match); string-tolerance stays a numerics
  pattern. Field description text: **§ Field descriptions below, verbatim into the
  codex brief** (lead-authored — descriptions generate the prompt's field reference;
  the plumbing is mechanical, the words are not).
- `quote_verify.py`: `claim_key` gains `effect_basis` (settled: basis twins are
  distinct claims; geography stays out) + dedup twin tests (basis twins do NOT
  collapse; geography-only twins DO, first-wins pinned). `iof_rules_v2`
  (`FIELD_RULES_VERSION` bump): coercion + the full coverage mapping per new field —
  valid value · null/unreported (`not_extracted`) · unclear · invalid enum value
  (coerce-and-flag, never reject the record) — with table-driven tests; v1-null vs
  v2-null distinguisher test (coverage key-absence).
- `extract.py`: record the evidence type actually sent on the extraction-record
  insert — **only when a prompt call was attempted** (adversarial finding 4):
  pre-prompt failure rows (`empty_basis`, `basis_mismatch`) record null, never a
  fabricated `Unclassified` — the column means "what the prompt saw", and no prompt
  saw anything. Tests cover attempted-call (value or `Unclassified` default) and
  pre-prompt-failure (null) rows. Fingerprint tests (old memo reused under old
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
- Vetter guidance line per decision 2 (lead): modelled/projected RESULTS are findings,
  not aspirations → `extract_finding_vetter_v3`; vetter verdicts replayed pre/post on
  the modelled-projection probes, flips hand-inspected.
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
  absent from the payload; the guidance-line half of decision 2 is Phase B lead work).
- Evidence-type divergence test (adversarial finding 5): a fixture where the recorded
  provenance value ≠ the current classification asserts the writer envelope's
  `evidence_type` still reads from `source_classification_result`, never the new
  column.
- Deterministic annotation join-path test (adversarial finding 6): a synthesise fixture
  mints a finding-claim annotation and resolves `effect_basis` + `study_geography` via
  the `cited_finding_ids` → row join (not payload) — the resolve-via-row promise tested
  without the live check.
- Mixed/unclear carry-through tests: `mixed`/`unclear` effect-direction findings
  survive `group` and `synthesise` end-to-end (fixture-driven; behaviour fixes only if
  a test exposes a drop — larger is the contract's stop condition).
- Old-row null tolerance tests on both read paths.
- Gate: `make verify-fast`, lead-run against Postgres (it is DB-backed and runs the
  migration head — the consolidation rationale is that B/C introduce no NEW schema
  contact, not that the gate skips the DB; adversarial finding 7). Full verify already
  ran at A exit and runs again at step-6 exit.

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

0. **The schema gate itself** (explicit, per adversarial finding 3 — decisions 1–3
   alone do not license the migration): approve the exact DB change set — two nullable
   columns on `intervention_outcome_finding` (`effect_basis` Text + CHECK over
   `EFFECT_BASES`, `study_geography` Text) · one nullable column on
   `source_extraction_record` (`primary_evidence_type` Text, + CHECK per decision 3) ·
   one alembic migration with symmetric down · NO backfill, existing rows untouched.
   *Recommend: approve as scoped.*
1. **`PROFILE_ID` bump** (`eb_iof_base_v1` → v2?): *Recommend NO bump, with the
   semantics documented* (adversarial finding 9 names the honest counter-position:
   adding base fields arguably changes the requirement identity). Adopted reading —
   the profile is a stable **requirement-family id** ("EB's base IOF extraction");
   field-set evolution is carried by the schema/prompt/rules version components, which
   already enter the fingerprint and the recorded components map, so provenance
   remains fully reconstructable per record. This reading lands as a `PROFILE_ID`
   docstring note + an ADR line + a provenance test asserting the components map
   records all three bumped versions. The alternative (bump to v2) is a redundant
   second invalidation lever — but it is the owner's call if profile-name-tracks-shape
   is preferred.
2. **Vetter payload + guidance**: *Recommendation FLIPPED by adversarial finding 2 —
   payload UNCHANGED, guidance line ADDED.* Verified against the prompt: the
   aspiration rule flags what "states a target … rather than something that happened",
   and a modelled projection is literally not-something-that-happened — the current
   text protects reported delivery/monitoring results but NOT modelled results, which
   v6 will now deliberately extract. One lead-authored guidance line (modelled or
   projected RESULTS the document reports are findings, not aspirations; targets stay
   flagged) → `extract_finding_vetter_v3`, replay-evidenced on the modelled-projection
   probe set (vetter verdicts diffed pre/post, flips hand-inspected). Payload still
   excludes the new fields (self-label bias risk stands); shape-snapshot test pins it.
3. **Evidence-type CHECK on `source_extraction_record.primary_evidence_type`**:
   *Recommend YES* — CHECK against the existing `EVIDENCE_TYPES` tuple +
   `'Unclassified'` (the prompt default). The vocabulary is closed and
   developer-controlled (the classification table already CHECKs the same tuple);
   fail-loud beats silently recording a typo'd provenance value. Null stays legal
   (pre-prompt failure rows, Phase A semantics).

## Field descriptions (lead-authored, verbatim into the Phase A codex brief)

These generate the prompt's field reference via `render_field_docs()` — treat as
prompt text, byte-exact (adversarial finding 8: committed here so conversation B needs
no unstated context).

- `effect_basis`: "Whether this finding's effect was observed ('observed' — measured
  after something happened: trial results, administrative or monitoring data,
  evaluation measurements) or modelled ('modelled' — projected, simulated or forecast:
  model outputs, scenario projections, calibrated estimates of what would happen), or
  null if the document does not make this determinable. A modelled estimate is still
  'modelled' even when built on observed inputs."
- `study_geography`: "Where the evidence underlying this finding was conducted,
  exactly as the document reports it (e.g. 'United Kingdom', '12 OECD countries'), or
  null if not reported. This is the study's own setting — never inferred from
  publisher, venue or author affiliation. A geographic subgroup that scopes the claim
  belongs in stratum_qualifiers; this field records where the underlying study or
  studies took place."

## Live-check pins

Extraction replay probes: pennies, unrestricted; probe docs drawn from the recorded
018 replay substrates and the fixture corpus, selections + trace ids recorded in
verification.md. ONE scoped live extract → synthesise pass (Phase D; substrate = an
existing dev-DB 018 replay project — `91d2d684` or `e8ac8418`, reuse the screened
selection, never re-search; ~$10–20 expected, synthesise dominates). NO composed
full-chain e2e runs.

## Dependencies

Decisions 1–3 → Phase A. A → B (models generate the field reference the prompt embeds)
and A → C (readers need the columns). B → the Phase D live check (it exercises v6).
C's carriage → the live check's synthesise leg. D's sweeps close last. Phases B and C
are independent of each other and can overlap once A lands.
