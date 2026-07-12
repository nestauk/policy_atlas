# Plan: 021-icf

> **Status:** DRAFTED — plan-stage adversarial review **adjudicated 2026-07-12**
> (codex session 019f57c6, 6 findings: 1 blocker · 4 major · 1 minor — ALL adopted:
> drift-guard requiredness overrides · Phase E prompt surfaces split to lead
> (tool-schema + pattern-payload descriptions, `synthesis_backend.py` added) ·
> `tracing.py` rides the roll-up shape change · claim_basis/claim_level independence
> clarified in the field text · dependencies corrected A→C, A→D). Awaiting 🛑 owner
> approval (gate decisions § below).
> Contract: [contract.md](contract.md) (approved 2026-07-12, adversarial review
> adjudicated 8/8). Rubric: [rubric.md](rubric.md). Design provenance:
> [design-research.md](design-research.md).
> Executor marks default to subagents (orchestrator-delegation convention); lead marks
> carry justification inline. Codex caveat (019/020 precedent): the codex sandbox has
> no Postgres — the lead runs DB-gated acceptance after each codex delivery.

## Phases

**Phase 0 — baseline + gate package** — **lead** *(gate adjudication is judgment)*
- Full `make verify` baseline (mandatory open-gate class; never build on red).
- Present § Gate decisions → 🛑 owner adjudication at plan approval. Phase A does not
  start until decision 0 (the schema gate itself) clears explicitly.

**Phase A — ICF domain core + IOF rider mechanics (the gated centre)** — **codex**
*(judgment-bearing multi-file coherence with a machine-verifiable done)*
- `schema.py`: `implementation_context_finding` table (columns per contract item 1:
  `finding_id` PK · `project_id` · `extraction_record_id` + the composite FK to
  `source_extraction_record` · `context_type` NOT NULL + CHECK · `claim` NOT NULL ·
  `intervention` NOT NULL · `outcome` · `population` · `setting` · `study_geography` ·
  `study_design` · `claim_level` + CHECK · `claim_basis` + CHECK · `level` + CHECK ·
  `resource_requirements` · `workforce_requirements` · `field_coverage` JSONB ·
  `grounding` JSONB · `created_at`; index on `extraction_record_id`) + vocabulary
  tuples (`CONTEXT_TYPES`, `CLAIM_BASES`, `CLAIM_LEVELS`, `CONTEXT_LEVELS`) · the IOF
  rider column (`setting` nullable Text on `intervention_outcome_finding`).
- ONE alembic migration (both tables) + symmetric down; up/down test; no backfill —
  existing IOF rows untouched across up/down (test-pinned).
- `implementation_context_records.py`: wire/stored models (`ICFRecordWire`/`ICFRecord`
  + anchor reuse), `PROFILE_ID = "eb_icf_base_v1"`, `SCHEMA_VERSION = "icf_v1"`,
  `render_field_docs` over the ICF wire models, import-time Literal↔CHECK asserts.
  Field description text: **§ Field descriptions below, verbatim into the codex
  brief** (lead-authored — they generate the prompt's field reference).
- **Shared reference vocabulary defined once**: one column/field definition set
  (mixin or shared constants) imported by BOTH record modules + the cross-schema
  drift-guard test — shared source-named MEANING and coercion, with **per-schema
  requiredness overrides** pinned explicitly (IOF `outcome` required · ICF `outcome`
  nullable; adversarial finding 1 — "same null semantics" was wrong: requiredness is
  legitimately per-schema, semantics and coercion are not).
- `extraction_records.py`: IOF `setting` wire+stored field (description below),
  `SCHEMA_VERSION` → `iof_v3`.
- `quote_verify.py`: `icf_rules_v1` — null-like coercion of ICF free-text fields ·
  `field_coverage` markers for non-valid outcomes only · grain gate (`context_type` +
  `intervention` + `claim` + ≥1 anchor) · ICF `claim_key` (`context_type` +
  `claim_level` + normalised `intervention` + normalised `claim`; first-wins
  descriptive metadata; anchor-merge on dedup, the IOF pattern) with twin tests
  (study-vs-pooled don't collapse; metadata-only twins do). `iof_rules_v3` — coverage
  for IOF `setting`; **top-level `setting` does NOT join the IOF claim key**
  (test-pinned; stratum setting participates via canonical strata as today; a
  coexistence test covers a setting-scoped stratum + top-level setting on one record).
- Stub extraction backend ICF sentinel payloads + shared test record factories.
- Gate: **full `make verify`** at Phase A exit (schema class).

**Phase B — extraction pipeline parameterisation** — **codex** *(the profile-bundle
seam is lead-DESIGNED here in the plan; its implementation is multi-file with every
semantic test-pinned)*
- `extract.py`: the doc pipeline (`_process_doc` / `_write_docs` / vetter invocation /
  fingerprint assembly) parameterised over a **profile bundle** (models + prompt +
  rules + vetter + table writer + judge-payload builder). Exactly two instances; no
  registry. `extraction_fingerprint` composes per profile; memo lookups keyed per
  profile fingerprint.
- **Roll-up per-profile shape** (contract item 4 pin): provenance keyed by profile id
  → {fingerprint + version components}; per-profile counts/finding totals; per-doc
  per-profile statuses. "Not selected" (absent) vs "fired, zero findings" (present,
  0, `no_findings`) test-pinned.
- **`tracing.py` rides the shape change** (adversarial finding 6): the Langfuse
  extraction score/root-span outputs currently assume the flat
  `summary["findings"]["total"]` / `summary["counts"]` shape — update to per-profile
  summaries, tolerating old flat rows; tests cover both shapes.
- Memo isolation tests: existing IOF memo hits under its (v3) fingerprint while ICF
  extracts fresh on the same document; ICF prompt-constant change re-extracts ICF
  only.
- Gate: **full `make verify`** (pipeline centre; memo/fingerprint semantics are
  ingest-adjacent).

**Phase C — prompts + vetter** — **lead** *(prompt-bearing surfaces are lead-only by
AGENTS.md)*
- `extract_icf_v1` (`implementation_context_prompt.py`): envelope fenced as the
  id-keyed JSON data object from day one (structural no-inline-interpolation test) ·
  field reference from `render_field_docs` · few-shot example with import-time
  pre-flight anchor validation · guidance: the recommendation/finding line ·
  claim_basis three-way · claim_level (own observation vs pooled-across-included-
  studies) · the inner-setting rule · stratum-vs-geography + study-vs-publisher
  (inherited semantics) · source-named-never-canonicalised · the never-infer/
  never-grade line (the V2 lesson, verbatim in the contract).
- `extract_icf_vetter_v1`: flag classes `recommendation` · `aspiration` ·
  `vague_context` · `deictic_naming`; IOF storage semantics (vetted-out excluded from
  insert, recorded in doc summary); fail-open; effort/knobs mirror the IOF vetter and
  enter the ICF fingerprint sub-block.
- `extract_iof_v7`: the setting guidance line + few-shot touch ONLY (description
  below; the two-distinction pattern).
- Replay evidence (pennies, unrestricted): the contract's probe set — process
  evaluation (adaptations + fidelity) · effects-only RCT (honest near-absence) ·
  recommendation-shaped doc (vetter line) · review pooling implementation findings
  (claim_level=pooled + finding-grain setting/geography) · hostile-envelope fencing ·
  dual-kind document (independent exclusion lines) · IOF v3 setting probe.
- Gate: `make verify-fast` (prompt + tests; no new schema contact).

**Phase D — composition: profiles directive end-to-end** — **codex** mechanics,
**lead** planner prompt *(the prompt is lead-only; the compile machinery is precise
spec)*
- `plan.py` / config: extract `profiles` field; compile + directive validation
  fail-closed (unknown profile = compile error); depth defaults from
  `ANALYSIS_DEPTH_TABLE` (deep → both; IOF-only expressible; extract stays deep-only).
- Planner prompt update (**lead**): describe two-profile extract semantics —
  version-bumped, replay-evidenced (the 019 planner precedent: plan-visible
  composition, no silent compilation).
- Gate: `make verify-fast`.

**Phase E — read surfaces: unified tool + envelope + validators + membership bridge**
— **codex** mechanics, **lead** prompt surfaces *(adversarial finding 2: the
`query_findings` tool schema description and the pattern-payload schema description
in `synthesis_backend.py` are model-facing prompt surfaces — lead-authored,
version-bumped; codex owns the readers, SQL, validators and tests)*
- `synthesis_backend.py` (adversarial finding 3): `PatternPayloadWire.computed_from`
  gains `icf_context_type_count` (+ group-scoped variant); the `query_findings` tool
  schema gains the kind-typed params/return — description text **lead-authored**.
- `synthesis_tools.py`: `make_findings_reader` → two scoped setup queries (one per
  kind present in the referenced extraction), server-side filtering preserved;
  unified `query_findings` return `{iof_findings, icf_findings, ...}` kind-segregated;
  `kinds` param + kind-specific filters fail-closed on mismatch; per-kind caps +
  per-kind truncation flags (gate decision 2); honest per-kind availability from the
  roll-up's per-profile provenance ("not extracted in this run" vs absent tool).
- `group.py` / `facet_values.py`: loader unions both tables over the shared reference
  columns; `FindingFacetView.effect_direction` nullable + `kind` tag;
  `direction_spread` over IOF members only; per-kind member counts in the group
  payload; validators updated + test-pinned.
- `synthesise.py`: envelope `member_findings` spans kinds (kind-typed carriage,
  terse idiom); `icf_context_type_count` pattern payload + deterministic validator
  (+ group-scoped variant); existing direction-spread payloads pinned IOF-only;
  annotation resolve-via-row for ICF finding ids; ICF finding-claim citation path.
- Old-row and IOF-only-run tolerance tests on every read path.
- Gate: **full `make verify`** at Phase E exit (last code phase).

**Phase F — records + live check + review prep** — **lead** judgments,
**fast-worker** sweeps
- Spec flow-back (fast-worker draft, lead review): data-model findings-layer — ICF ⏸
  entry rewritten as built (grain, base fields, setting joins the stored reference
  vocabulary on BOTH schemas) · components §7/§8/§9 updates per contract item 10 ·
  spec-bundle `log.md` lines.
- deferred.md sweep (fast-worker draft, lead review): ICF entry discharged; the
  narrowed seams + Slice C agenda items (hybrid dimension search · UNION view ·
  judge-envelope candidates) + the schema-candidate ladder + companion-document seam +
  presentation-grain note — all per contract item 10.
- ADR (**lead**): second finding schema + parallel-domain posture + composition shape +
  the IOF setting rider + kind-spanning membership. Accepted at plan sign-off date.
- **Scoped live check** (**lead**): both-profiles live extract over a small
  already-screened selection from an existing dev-DB project (018/020 substrate;
  reuse, never re-search) → ICF rows + coverage + per-profile roll-up verified → one
  synthesise referencing that extraction → kind-spanning group membership, envelope
  carriage, one implementation-shaped pattern claim validating, ICF finding-claim
  anchors resolving on the minted artefact. (~$10–20 expected, synthesise dominates.)
  NO composed full-chain e2e.
- verification.md complete. Gate: **full `make verify`** at step-6 exit.

## Gate decisions (adjudicate at this plan approval)

0. **The schema gate itself**: approve the exact DDL set — the
   `implementation_context_finding` table as listed in Phase A · one nullable
   `setting` column on `intervention_outcome_finding` · one migration, symmetric
   down, no backfill. *Recommend: approve as scoped.*
1. **ICF vetter knobs**: mirror the IOF vetter (`gpt-5.4-mini`, effort high, same
   token ceiling), all in the ICF fingerprint sub-block. *Recommend: yes — one
   calibration story until evals say otherwise.*
2. **Unified-tool caps**: per-kind caps (100 per kind, per-kind `truncated` flags)
   rather than one shared 100. *Recommend: per-kind — one kind can never crowd out
   the other; the cap arithmetic is visible per kind.*
3. **Synthesise prompt**: NO guidance-line change this slice — the unified tool's
   (prompt-surface) description carries the new semantics; writer behaviour tuning is
   post-eval work. *Recommend: no change (tool description bump only).*
4. **IOF `PROFILE_ID`**: no bump (the 020 decision-1 reading — requirement-family id;
   the v3 schema/prompt/rules bumps carry the change identity in the fingerprint).
   *Recommend: no bump, same provenance test pattern.*

## Field descriptions (lead-authored, verbatim into the Phase A codex brief)

Prompt text, byte-exact. ICF wire fields:

- `context_type`: "The kind of implementation-context claim: 'mechanism' (why or how
  the intervention produces its effects, as the source explains it), 'barrier'
  (something that hindered delivery or uptake), 'enabler' (something that helped
  delivery or uptake), 'implementation_condition' (a condition the source states the
  intervention depends on to work), 'delivery_process' (how the intervention was
  actually delivered or operated), 'adaptation' (a modification made to the
  intervention, including why and whether core elements were kept), or 'fidelity'
  (how delivery compared to what was planned — dose, adherence, quality)."
- `claim`: "The implementation-context finding as one self-contained sentence, stated
  the way the source states it — a report of what happened or what the source
  asserts, never a recommendation, aspiration or target."
- `intervention`: (shared vocabulary — identical text to IOF's field.)
- `outcome`: "The outcome this context claim relates to, exactly as the source names
  it, or null — a mechanism may explain a specific outcome; most barriers and
  conditions name none."
- `population`: (shared vocabulary — identical text to IOF's field.)
- `setting`: "The setting where recipients experience the intervention, exactly as
  the source names it (e.g. 'primary care', 'secondary schools', 'social housing'),
  or null if not reported. Use the delivery setting, not the institution that created
  or mandated the intervention: if a parliament passes a school nutrition policy, the
  setting is the school, not parliament. Never inferred."
- `study_geography`: (shared vocabulary — identical text to IOF's field.)
- `study_design`: (shared vocabulary — identical text to IOF's field.)
- `claim_level`: "'study' if this is the source's own observation from its own
  fieldwork or data; 'pooled' if the source synthesises the claim across multiple
  included studies (e.g. 'the most cited barrier across included trials'); null if
  indeterminate."
- `claim_basis`: "'studied' if the claim rests on empirical implementation data —
  the source's own fieldwork (a process evaluation, qualitative arm, implementation
  data) OR implementation data the source synthesises from its included studies;
  'author_assertion' if the source's authors assert it in discussion or commentary
  without empirical grounding; 'cited_theory' if the source carries it from cited
  literature or theoretical framing; null if indeterminate. Never guess. (A review's
  pooled empirical barrier is 'studied' + claim_level 'pooled' — the two fields are
  independent.)"
- `level`: "The level the claim operates at, as the source frames it: 'system'
  (policy, legal, funding environment), 'organisation' (the delivering organisation),
  'provider' (the staff delivering), 'recipient' (the people receiving), or null."
- `resource_requirements`: "Costs, funding or material resources the source reports
  for implementing the intervention, exactly as reported, or null. Only what the
  source states — never estimated or graded."
- `workforce_requirements`: "Staffing, skills or training the source reports the
  intervention requires, exactly as reported, or null. Only what the source states —
  never estimated or graded."

IOF v3 rider field:

- `setting` (IOF): "The setting where the intervention underlying this finding was
  delivered, exactly as the document reports it (e.g. 'primary care', 'secondary
  schools'), or null if not reported. Use the delivery setting, not the mandating
  institution. A setting-scoped subgroup estimate belongs in stratum_qualifiers; this
  field records where the underlying evidence was conducted — they can coexist."

## Live-check pins

Replay probes: pennies, unrestricted; probe docs from the recorded replay substrates +
openly-licensed fixtures (one process evaluation with adaptations/fidelity content
must be sourced — record its licence). ONE scoped live both-profiles extract →
synthesise pass (Phase F; substrate = an existing dev-DB project, reuse the screened
selection, never re-search; ~$10–20). NO composed full-chain e2e.

## Dependencies

Decision 0 → Phase A. A → B (pipeline needs the tables/models). **A → C and A → D
directly** (adversarial finding 5: the few-shot preflight is prompt-local against
`quote_verify` helpers, and the profile ids live in the record modules — B is needed
only for the integrated extraction-execution tests, which sit in B itself). A+B → E
(readers need columns + the per-profile roll-up). C, D, E are mutually independent
and can overlap once their inputs land. F closes last (live check exercises C+D+E).
