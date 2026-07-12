# Task contract: 021-icf

The promoted pre-eval ICF slice of the owner-adjudicated sequencing (2026-07-12, amended
at the 020 contract review): `implementation_context_finding` — the second reusable
finding schema (mechanisms, barriers, implementation conditions — the "how / why / under
what conditions", not "what effect"). Promoted from "other capabilities' reader" because
**EB synthesis is its first reader**: ICF records are the deterministic validator that
makes implementation-shaped pattern claims possible (content-scan pattern claims are
prohibited in v1 precisely for lack of one); full-read coverage + honest absence beat
top-k RAG for diffuse implementation material; and the eval slice's synthesis baselines
must be cut on the intended composition (the select-at-standard precedent). Lands before
ground truth: the eval slice authors ICF ground truth alongside IOF's, with a
with/without-ICF composition comparison as an explicit axis.

> **Status:** drafted. Contract approved (before planning): _pending · owner_ ·
> Contract-stage adversarial review: _pending (after owner approval)_ ·
> Plan approved (before implementation): _pending_ · ADR: _expected (second finding
> schema + composition shape)_.

## Goal

Give the findings layer its second reusable schema so grounded synthesis can make and
deterministically validate implementation-shaped claims ("planning delays recur as a
barrier across heat-pump programmes"), with the same trust machinery IOF has: verbatim
quote anchors, field coverage, honest absence, flag-not-drop.

Posture pinned at the 020 gate (owner, 2026-07-12) — these are context, not open
questions: **separate extraction call/profile with its own fingerprint domain** — nothing
couples to IOF's fingerprint, ICF's arrival never invalidates IOF memos; **same
source-named reference vocabulary** (intervention / outcome / population / setting) so
cross-schema linkage stays **reference-mediated via `group`** — no link objects; the two
evidence kinds stay **related-but-distinct** (never a barrier blended into an effect
claim).

## Deliverable

One PR to `dev` landing the ICF domain end-to-end: wire + stored models (`icf_v1`), the
`implementation_context_finding` table + migration, `extract_icf_v1` prompt + ICF field
rules + ICF vetter, a second extraction profile through the extract component behind a
plan-visible composition toggle, and the synthesis read surface (writer tool + envelope
carriage + deterministic validators) that makes EB synthesis the first reader. Spec
flow-back (data-model ⏸ entry becomes built; components §7/§8 narrowed) + deferred.md
discharge/narrowing.

## Read first

- `docs/deferred.md` § Extract — the ICF promotion entry (posture pins, CFIR design
  input) and § EB internals — cross-schema reference-mediated linkage.
- [data-model](../../specs/system/data-model.md) § The findings layer — the IOF grain /
  base-field precedent, the source-groundability line, upgrades-never-invalidate; this
  spec receives the flow-back.
- [EB components](../../specs/capabilities/evidence-base/components.md) §7 extract, §8
  group, §9 synthesise — the claim-type availability ladder this slice extends.
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) — coverage-state
  and anchor discipline.
- `docs/specs/system/prompting.md` — binding for the prompt work.
- V2 CFIR implementation-profile field definitions (recorded design input, 011:
  cost/staffing/complexity + the inner-setting rule) — input, not a template; no field
  enters ICF without passing the source-groundability line.
- `docs/tasks/011-extract/contract.md` + `docs/tasks/020-extract-v2/contract.md` —
  pattern precedents (the schema's own contract; the fencing/field-rules idiom).
- Code spine: `extraction_records.py` (the wire/stored + `render_field_docs` pattern to
  parallel), `extract.py` (fingerprint/memo machinery to parameterise or parallel),
  `extract_prompt.py` (fencing + few-shot pre-flight idiom), `quote_verify.py` (`qv_v1`
  reused as-is; `iof_rules_v2` as the rules pattern), `schema.py`
  (`source_extraction_record` — reused unchanged), `finding_vetter.py` (protocol/stub
  seam), `synthesis_tools.py` + `synthesise.py` (writer read surface), `group.py`
  (facet machinery — OUT of scope, see below).

## Scope / Out of scope

**In:**

1. **ICF record design — the schema decision this contract exists for.** Grain: **one
   implementation-context claim about a named intervention, grounded in a single
   source.** Proposed field set (🛑 gate decision 1 reviews the vocabulary; ❓ items are
   named where open):
   - `context_type` (closed enum, NOT NULL): `mechanism` | `barrier` | `enabler` |
     `implementation_condition` | `delivery_process`. The core closed vocabulary —
     barriers and enablers are distinct values (how sources speak; polarity lives in the
     type, no separate direction field). CHECK-backed, Literal-asserted at import (the
     IOF drift-guard pattern).
   - `claim` (NOT NULL Text): the finding as the source states it — source-named prose,
     one claim per record (ICF content is inherently propositional; unlike IOF there is
     no statistics block for the content to live in). The record stays one coherent
     typed unit: claim + dimensions + anchors.
   - **Source-named references (the shared vocabulary):** `intervention` (NOT NULL —
     implementation context is context *of* something), `outcome` (nullable — a
     mechanism may name the outcome it explains; barriers usually don't), `population`
     (nullable), **`setting`** (nullable — new to the stored vocabulary, the CFIR
     inner-setting rule made source-named: the delivery setting exactly as the source
     names it, e.g. "primary care", "social housing retrofit"; never inferred).
   - `study_geography` (nullable, source-named, finding grain — the 020 field's exact
     semantics; implementation context is where transferability lives, and consistency
     with IOF keeps the eval ground-truth instructions uniform).
   - **CFIR profile fields (❓ gate decision 2):** `resource_requirements` and
     `workforce_requirements` — nullable source-named Text, only what the source
     reports (cost/funding; staffing/skills/training). V2's `complexity` does NOT carry
     (a judgment scale, not a source-groundable report — it fails the base-field line).
     Alternative: fold both into `claim` + `context_type=implementation_condition` and
     ship a 5-field-lighter v1.
   - **`claim_basis` (❓ gate decision 3):** `studied` | `author_assertion` | null —
     whether the source *studied* the context claim (process evaluation, qualitative
     arm) or asserts it in discussion/commentary. The effect_basis precedent: a
     different dimension from the claim itself, structurally honest about the large
     author-commentary share of implementation material. Null = indeterminate, never
     guessed.
   - **Anchors + machinery (settled, IOF pattern):** ≥1 verbatim quote anchor (`qv_v1`
     reused unchanged), `field_coverage` per nullable field, `grounding` JSONB,
     `stratum_qualifiers` NOT carried (no ICF analogue of effect strata — declined, not
     deferred). Grain gate: `context_type` + `intervention` + `claim` + ≥1 anchor.
   - Excluded content the vetter enforces: **recommendations and aspirations are not
     findings** ("policymakers should fund training" — no; "the programme stalled where
     training was unfunded" — yes). Question-relative judgements (severity, importance
     rankings) are analysis enrichment, never base fields.
2. **DB schema + migration (schema gate):** one new table
   `implementation_context_finding` hanging off `source_extraction_record` via the same
   composite FK as IOF; CHECKs on `context_type` (+ `claim_basis` if adopted); one
   up/down migration. **`source_extraction_record` and `extraction_result` are reused
   unchanged** — ICF rows key on their own fingerprint; no IOF table or column changes
   of any kind (test-pinned).
3. **Extraction profile + fingerprint domain:** `implementation_context_records.py`
   (wire/stored models, `PROFILE_ID = "eb_icf_base_v1"`, `SCHEMA_VERSION = "icf_v1"`,
   own `render_field_docs`; payload types reused). **Pipeline shape pinned (owner,
   2026-07-12): the doc pipeline in `extract.py` (`_process_doc` / `_write_docs` /
   vetter invocation / fingerprint assembly) goes profile-parameterised** — a
   per-domain bundle (models + prompt + rules + vetter + table writer) is the plug, so
   a future third schema is content work, not plumbing. Bounded to what the two real
   instances force: no profile registry, no plugin machinery, no speculative
   abstraction (the plan 🛑 reviews the parameterisation seam). ICF fingerprints
   compose from ICF constants only; **IOF's fingerprint components are byte-identical
   before/after this slice** (test pin: existing IOF memos hit; a fixture project's
   IOF fingerprint string is unchanged).
4. **Composition shape (🛑 gate decision 4):** ICF extraction runs **inside the existing
   extract component as a second per-source pass over the same selection** — one
   component, two profiles; no new component, no second selection. Plan-visible toggle:
   the extract directive gains a `profiles` field (default at deep depth: both; IOF-only
   remains expressible — the eval slice's with/without-ICF axis needs exactly this
   switch). Fail-closed: an unknown profile name is a compile error. ❓ whether the
   shared `extraction_result` run roll-up row carries per-profile counts or stays
   aggregate — plan decision.
5. **Prompt `extract_icf_v1`** — **prompt-bearing: lead-only, replay-evidenced**:
   envelope fenced as an id-keyed JSON data object from day one (the 020 pattern — no
   inline title/abstract, structural test); field reference generated from the wire
   models; few-shot example with import-time pre-flight anchor validation; guidance
   carrying the recommendation/finding line, the studied/author_assertion line (if
   `claim_basis` adopted), and source-named-never-canonicalised discipline for all
   reference fields.
6. **Field rules `icf_rules_v1`** (`quote_verify.py`): null-like coercion of the
   free-text fields, full `field_coverage` mapping per nullable field (valid ·
   `not_extracted` · `unclear` — a null is never ambiguous within v1), grain gate,
   `claim_key` + dedup (key proposal: `context_type` + normalised `intervention` +
   normalised `claim`; first-wins on descriptive metadata — plan reviews the exact
   key). No invalid-enum recovery rows: `context_type`/`claim_basis` are strict wire
   Literals under schema-constrained output (the 020 precedent).
7. **ICF vetter (❓ gate decision 5):** a parallel vetter with ICF flag classes —
   proposal: `recommendation` (should/ought content), `aspiration` (targets), 
   `vague_context` (no named intervention or actionable content), `deictic_naming`
   (carried from IOF — "the programme"). Same protocol/stub/live seam, own prompt
   version (`extract_icf_vetter_v1`, lead-only), own fingerprint sub-block,
   flag-not-drop, fail-open. Alternative if declined: ship without a vetter and let the
   eval slice measure whether one is needed (the prompt's exclusion guidance still
   binds). Recommendation: in — the recommendation/finding line is ICF's single
   biggest quality risk and it is exactly what vetters are for.
8. **Synthesis read surface — the first-reader payoff (gate decision 6 SETTLED —
   owner, 2026-07-12): ONE unified writer tool.** `query_findings` extends to serve
   both schemas in a single call — the dominant writer query is "effects AND
   implementation context of intervention X", and one call instead of two saves a
   whole writer turn each time (writer turns = ~74% of the $15-run anatomy; each turn
   resends ~93k input tokens — the single-call shape is a direct cost lever, the
   Slice C direction). Design requirements, non-negotiable:
   - **Kind-segregated typed return**: `iof_findings` and `icf_findings` as separate
     typed sections — never interleaved into one homogeneous list, no record ever
     blends kinds (related-but-distinct moves from the tool boundary to the return
     shape, where the record-level fences — typed records, deterministic validators,
     id-resolved anchors — were always the real guarantee).
   - **Kind filter + fail-closed params**: a `kinds` parameter (default: all kinds
     present); kind-specific filters (`effect_direction` IOF-only, `context_type`
     ICF-only) rejected loudly on a mismatched kind/filter combo.
   - **Honest per-kind availability**: in a run whose extraction lacks the ICF
     profile, the tool answers "context findings: not extracted in this run" — a
     visible coverage fact, not a silently absent tool (and the with/without-ICF eval
     arms differ by less surface). Tool present, as today, only when an extraction is
     referenced at all.
   Carriage: ICF records enter the writer envelope alongside IOF findings (same terse,
   always-present-nullable idiom); finding claims may cite ICF finding ids resolved to
   extract-verified anchors (the model never authors these quotes — same rule, same
   annotation resolve-via-row pattern); **pattern claims** over ICF records (counts by
   `context_type` / intervention) validate deterministically against the referenced
   extraction — the claim-type ladder in components §9 gains its implementation-shaped
   rung. **Theme claims over ICF stay unavailable** — facet grouping is out of scope
   (below); until then implementation *themes* remain landscape-grade. The tool-shape
   change touches the writer's prompt surface (tool description + any guidance line):
   prompt-bearing, lead-only, version-bumped — ❓ plan decision on whether a synthesise
   prompt guidance line is strictly needed beyond the tool description itself.
9. **Stub/fixture surface:** stub extraction backend sentinel payloads for the ICF
   profile, shared test record factories, replay fixtures (openly-licensed real
   documents per the sanitized-fixtures policy).
10. **Spec flow-back + deferrals:** data-model findings-layer ⏸ ICF entry becomes the
    built schema (grain + base fields + the setting addition to the reference
    vocabulary); components §7 loses "second schema is a deferred seam", §8 gains the
    narrowed "ICF facets await facet machinery" pointer, §9's claim-type ladder gains
    the ICF pattern/finding rungs; deferred.md ICF entry discharged, replaced by the
    narrowed seams (ICF facet grouping · dimension-promotion for ICF fields ·
    downstream capability consumers). The formerly-mooted per-schema-writer-tools seam
    is **pre-discharged by gate decision 6**: the unified kind-typed `query_findings`
    IS the schema-typed query interface — a future third schema adds a kind section +
    filters (content work), not a new tool. The sweep also ADDS the
    **schema-candidate ladder** entry (owner adjudication, 2026-07-12, this contract's
    review): generic findings container and runtime intent-shaped custom extraction
    REMAIN declined (the 011 rulings hold — typed records are what deterministic
    validation, ground truth, memo reuse and cross-question interpretability rest on;
    the long tail is served by verified chunk-grounded synthesis, ADR 0010); named
    candidates `reported_statistic` and `case_example` (V2 question-taxonomy categories
    4 + 6), **first reader = the Baseline analysis / problem-identification capability**
    (quantitative + qualitative — its qualitative half may name a further kind, e.g. a
    `reported_problem`; the candidate list is open, not exhaustive); trigger = Baseline's
    contract committing the extraction profile, with per-category eval evidence (the
    eval intent set keeps categories 4/6 in and scores chunk-grounded synthesis on them)
    as the demonstration; sequencing note — **additive schemas never invalidate eval
    baselines** (no existing record shape or ground truth changes; a new kind is a new
    eval arm, the with/without-ICF axis pattern repeated), so these land with Baseline
    post-eval, no pre-eval promotion pressure. Schema design stays with the committing
    capability's contract (the IOF precedent).

**Out:** **cross-schema facet grouping** — `group` stays IOF-only this slice; the design
property (shared source-named vocabulary) now exists in both tables, but the multi-table
facet read lands with Slice C's facet rework (`FindingFacetView.effect_direction` has no
ICF analogue — the C multi-facet redesign is the right place to solve that shape, not a
bolt-on here) · implementation-shaped **theme** claims (follow facet grouping) ·
hybrid-indexing any ICF dimension (the dimension-promotion gate is observed behaviour,
not schema enthusiasm) · ICF ground truth + extraction-quality evals (eval slice — this
slice is honestly eval-blind) · downstream capability consumers (Options/Impact/
Transferability/VfM read it later; EB synthesis is the reader now) · any IOF schema,
prompt, rules or fingerprint change (zero — test-pinned) · geography/setting
canonicalisation · Slice C cost/surface work · Bedrock · everything else in
`docs/deferred.md`.

## Constraints & approval gates

- **Schema (needs human approval):** item 2 — one new table + CHECKs + one migration.
  No changes to existing tables.
- **No invalidation:** IOF memos, fingerprints, records and prompts are untouched.
  Any temptation to "quickly parameterise" an IOF surface in a way that changes its
  fingerprint string is a stop condition.
- **Prompt-bearing surfaces are lead-only:** `extract_icf_v1`, the ICF vetter prompt,
  any synthesise guidance line. Mechanical carriage (models, migration, SELECTs, tests,
  stub payloads) delegates — routing marked at plan time.
- **Egress:** none new — same OpenAI route; ICF adds one mini-priced extraction call
  (+ vetter call) per selected document. Cost context: extract+vet was <3% of the $15
  synthesis-run anatomy; doubling it is noise next to Slice C's writer-side work.
- **Deps/CI/public interfaces:** untouched.

## Public / private boundary

All code, migrations and spec changes public-safe. Replay evidence as summaries in
`verification.md`; raw traces stay in Langfuse. Fixture documents openly licensed.

## Model route

Extraction + vetter on `gpt-5.4-mini` via the OpenAI route (the IOF floor; same
step-up-is-recorded rule). Prompt-bearing changes: `extract_icf_v1` + `extract_icf_vetter_v1`
(lead-authored). Replay set: at least one process-evaluation / qualitative-arm document
rich in implementation material · one effects-only RCT (expect few/zero ICF records —
honest absence, not manufactured findings) · one document whose implementation content
is author-recommendation-shaped (the vetter line) · one review pooling implementation
findings across settings (setting/geography at finding grain) · one hostile-envelope
fencing probe · **one dual-kind document (owner, 2026-07-12)**: the same passage feeds
both passes and is judged differently by design — an aspiration sentence ("the pilot
aims to cut bills") flagged by the IOF vetter while an adjacent implementation
condition ("rollout stalled where installer training was unfunded") extracts cleanly
as ICF — pinning that the two exclusion lines are independent, not one shared vet.
**Honesty pin:** eval-blind until ICF ground truth exists — replay evidence shows shape
and the exclusion lines holding on probes, it does not certify extraction quality; that
is exactly why this slice precedes ground truth.

**Live-check scope (contract-time pin):** replay probes above + one scoped live
extract-both-profiles → synthesise pass over a small already-screened selection from an
existing dev project (evidences the second profile extracting alongside IOF under its
own fingerprint, envelope carriage, and one implementation-shaped pattern claim
validating). No composed full-chain e2e.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — every ICF field ships with its render surface (writer
  envelope + annotation resolve-via-row); a field with no reader doesn't ship.
- **Flag, don't drop** — vetter flags never delete; below-bar material stays visible.
- **Honest absence** — zero ICF records from an effects-only source is coverage, not
  failure; `field_coverage` records absence per field.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: the schema gate is hit without recorded approval · the field-set
❓s resolve toward anything beyond the proposed record shape (scope growth into facet
grouping, canonicalisation or eval territory) · the profile parameterisation cannot be
done without touching IOF's fingerprint string · any pressure to blend kinds inside the
unified tool's return (one homogeneous findings list, or any single record mixing
schemas) · budget spent.

## Acceptance checks

- `make verify` green.
- Deterministic tests: migration up/down · `context_type` (+ `claim_basis`) CHECK ↔
  Literal asserts · `icf_rules_v1` coercion + full coverage mapping + grain gate ·
  claim-key dedup (context_type/intervention/claim twins collapse; distinct types don't)
  · **IOF fingerprint unchanged** (byte-identical components; existing memo hits) · ICF
  fingerprint fresh-extracts alongside an IOF memo hit on the same document · profiles
  directive compiles fail-closed (unknown profile errors; IOF-only expressible; default
  both at deep) · `render_field_docs` for ICF wire models · structural fencing check
  (no inline envelope interpolation) · few-shot pre-flight binding · vetter payload
  shape + flag-not-drop pinned · unified `query_findings`: kind-segregated typed return
  (never one homogeneous list) · kind-specific filters fail closed on a mismatched kind
  · honest per-kind availability ("not extracted in this run" when the ICF profile
  didn't fire; tool absent only when no extraction is referenced at all) · envelope
  carriage + annotation
  resolve-via-row for ICF finding ids · pattern-claim validator counts ICF records
  correctly · stub backend round-trip.
- Replay evidence (AI-behaviour, honestly eval-blind): the probe set above summarised in
  verification.md — including the effects-only doc yielding honest near-absence and the
  recommendation-shaped doc's content flagged, not extracted (or extracted-and-flagged
  per the vetter's flag-not-drop), and the fencing probe leaving fields unaffected.
- Manual: the scoped live check named under Model route.

## Verification evidence expected

`verification.md`: command results, migration up/down evidence, replay summaries, the
schema-gate approval with owner sign-off date, IOF-fingerprint-unchanged evidence,
deferred.md + spec flow-back diff summary, known gaps.

## Risk tier & review focus

**Tier 3** — schema hard gate + two new prompt-bearing surfaces + a writer-facing tool
extension. Contract- and plan-stage adversarial reviews per the design skill; review
stack per [review-stack economy]: medium `/code-review`, one security lane (fencing
completeness on the new prompt; migration correctness; the extended tool's read scope
stays project-guarded), contract verifier fresh-context, per-angle diff scoping.

Focus: IOF non-invalidation (the one catastrophic failure) · the recommendation/finding
exclusion line · fingerprint completeness for the new domain (every output-affecting
constant versioned) · related-but-distinct held at every surface (kind-segregated tool
returns; no record, envelope entry or claim blending schemas) · no scope creep into
facet grouping or eval territory.

## Decisions for the owner at this gate

1. **`context_type` vocabulary** — the five proposed values (mechanism · barrier ·
   enabler · implementation_condition · delivery_process). This is the schema's load-bearing
   closed vocabulary; ground truth and evals will be authored against it.
2. **CFIR profile fields** — `resource_requirements` + `workforce_requirements` in v1
   (recommended: in — they are the CFIR design input's surviving source-groundable
   fields, and transferability/VfM are their eventual readers), or fold into `claim`
   for a lighter v1. `complexity` dropped either way.
3. **`claim_basis`** — studied vs author_assertion enum in v1 (recommended: in — the
   effect_basis precedent; implementation material is where author commentary
   dominates, and the eval slice will want the axis).
4. **Composition shape** — second profile inside the extract component, plan-visible
   `profiles` directive, default both-at-deep (recommended as written).
5. **ICF vetter** — in scope with the proposed flag classes (recommended: in).
6. **Read surface — SETTLED (owner, 2026-07-12): one unified `query_findings`** serving
   both schemas in a single call (kind-segregated typed return, kind filters fail-closed,
   honest per-kind availability). Rationale: the dominant query is "effects AND context
   of intervention X"; one call saves a ~93k-input writer turn each time (the Slice C
   cost direction); the record-level fences, not the tool boundary, are what hold
   related-but-distinct. Supersedes the drafted two-tool proposal; pre-discharges the
   N-schema writer-tool seam.
