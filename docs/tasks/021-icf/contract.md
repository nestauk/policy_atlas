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
plan-visible composition toggle, and the synthesis read surface (unified kind-typed
writer tool + envelope carriage + deterministic validators) that makes EB synthesis the
first reader. Plus the bounded **IOF `setting` rider** (`iof_v3`, item 11 — one column,
one prompt line, deliberate pre-ground-truth fingerprint bump) and the shared reference
vocabulary defined once with a cross-schema drift guard. Spec flow-back (data-model ⏸
entry becomes built; components §7/§8 narrowed) + deferred.md discharge/narrowing.

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
- **Design research (2026-07-12, this contract's review — owner-commissioned):** the
  transferability/appraisal frameworks whose source-extractable demands ground the
  field set — TRANSFER (NIPH), PIET-T, Wang/Moss/Hiller, CICI, RE-AIM, PRECIS-2, GRADE
  indirectness + Evidence-to-Decision, HM Treasury Green Book options appraisal, CFIR
  2.0 coding practice, FRAME (adaptations), Carroll/TIDieR (fidelity) — and the V2
  repo survey (implementation-profile extraction, three transferability surfaces, the
  forecast CMO layer). Both summarised in this task's `design-research.md`. The design
  line they converge on: extract the SOURCE side of every comparative judgment;
  target-context values and transfer verdicts are analyst/capability work, never
  extraction.
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
     `implementation_condition` | `delivery_process` | `adaptation` | `fidelity`. The
     core closed vocabulary — barriers and enablers are distinct values (how sources
     speak; polarity lives in the type, no separate direction field);
     **`adaptation`** (a modification made to the intervention — what/planned-vs-
     reactive/why carried in the claim prose; FRAME's existence proves modifications
     are chronically under-documented, making them high-value when reported) and
     **`fidelity`** (delivered-vs-planned observations — Carroll/TIDieR 11–12; the
     difference between "the intervention failed" and "the implementation failed")
     added at the 2026-07-12 research review (V2 forecast + frameworks evidence).
     CHECK-backed, Literal-asserted at import (the IOF drift-guard pattern).
   - `claim` (NOT NULL Text): the finding as the source states it — source-named prose,
     one claim per record (ICF content is inherently propositional; unlike IOF there is
     no statistics block for the content to live in). The record stays one coherent
     typed unit: claim + dimensions + anchors.
   - **Source-named references (the shared vocabulary):** `intervention` (NOT NULL —
     implementation context is context *of* something), `outcome` (nullable — a
     mechanism may name the outcome it explains; barriers usually don't), `population`
     (nullable), **`setting`** (nullable — new to the stored vocabulary, the CFIR
     inner-setting rule made source-named: the delivery setting exactly as the source
     names it, e.g. "primary care", "social housing retrofit"; never inferred. The
     prompt carries V2's inner-setting rule near-verbatim: the setting where
     recipients EXPERIENCE the intervention, not the institution that created or
     mandated it — a parliament passing a school nutrition policy means "school").
     The setting/population/geography references at finding grain are the **source
     side of every comparative transferability judgment** (GRADE indirectness, Wang,
     TRANSFER stage 4) — the target side and the comparison itself stay with the
     future capability, never in extraction.
   - `study_geography` (nullable, source-named, finding grain — the 020 field's exact
     semantics; implementation context is where transferability lives, and consistency
     with IOF keeps the eval ground-truth instructions uniform).
   - `study_design` (nullable, source-named — IOF-parity, owner 2026-07-12: the
     review-grain logic is identical — a review's implementation findings come from
     different included studies; `claim_basis` doesn't cover it, design is what kind
     of study produced the claim, basis is its epistemic grounding).
   - **`claim_level`** (`study` | `pooled` | null — owner 2026-07-12): the IOF
     `estimate_level` logic applied to context claims — a review's pooled barrier
     ("most cited across 12 studies") and a primary study's own barrier observation
     are different evidence shapes that must not double-count, and ICF's first-reader
     payoff is deterministic pattern-claim COUNTS, so count honesty is load-bearing.
     Joins the claim key (the estimate_level precedent). CHECK-backed.
   - **Shared reference vocabulary defined ONCE (owner, 2026-07-12):** the shared
     source-named columns (`intervention` / `outcome` / `population` / `setting` /
     `study_geography` / `study_design`) get a single code definition (shared column
     set / model mixin both record modules import) plus a cross-schema drift-guard
     test — nothing may let IOF's and ICF's semantics or coercion for the same-named
     reference drift apart (grouping and the future dimension index depend on it).
     Storage stays parallel tables (payloads are disjoint; a merged table is the
     generic-container failure mode); the cross-kind UNION read view goes to Slice C
     with its first reader (cross-schema grouping).
   - **CFIR profile fields (❓ gate decision 2):** `resource_requirements` and
     `workforce_requirements` — nullable source-named Text, only what the source
     reports (cost/funding; staffing/skills/training). Framework-backed at the
     2026-07-12 research review: GRADE EtD's resources criterion and Green Book cost
     benchmarks — the only economic input a primary document can supply (downstream
     repricing reads setting/geography off the same record + the document's year).
     V2's `complexity` does NOT carry (a judgment scale, not a source-groundable
     report — it fails the base-field line; V2's High/Moderate/Low ordinals under
     "infer from context if not explicit" are the recorded anti-pattern).
     Alternative: fold both into `claim` + `context_type=implementation_condition` and
     ship a lighter v1.
   - **`level` (❓ gate decision 2, rides with the profile fields):** closed nullable
     enum `system` | `organisation` | `provider` | `recipient` — the socio-ecological
     level the claim operates at, as the source frames it. CFIR coding practice codes
     every barrier/enabler with its level; EtD feasibility wants "barriers cluster at
     organisation level" as a deterministic aggregation. CHECK-backed.
   - **`claim_basis` (❓ gate decision 3):** `studied` | `author_assertion` |
     `cited_theory` | null — whether the source *studied* the context claim (process
     evaluation, qualitative arm), asserts it in discussion/commentary, or carries it
     from cited literature/theoretical framing. Three-way per V2's forecast
     `EvidenceBasis` (`empirical | author_hypothesis | theory_background` — the one V2
     extraction design worth pulling through) and realist practice (mechanisms are
     usually stated-as-theory, not demonstrated; extraction records the stated basis,
     never forces CMO completeness). The effect_basis precedent: a different dimension
     from the claim itself, structurally honest about the large author-commentary
     share of implementation material. Null = indeterminate, never guessed.
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
   composite FK as IOF; CHECKs on `context_type` and `claim_level` (+ `claim_basis` and
   `level` if adopted); one up/down migration, which also carries item 11's single IOF
   column. **`source_extraction_record` and `extraction_result` are reused unchanged**
   — ICF rows key on their own fingerprint. IOF table changes: **only** item 11's
   approved `setting` column, nothing else (test-pinned).
3. **Extraction profile + fingerprint domain:** `implementation_context_records.py`
   (wire/stored models, `PROFILE_ID = "eb_icf_base_v1"`, `SCHEMA_VERSION = "icf_v1"`,
   own `render_field_docs`; payload types reused). **Pipeline shape pinned (owner,
   2026-07-12): the doc pipeline in `extract.py` (`_process_doc` / `_write_docs` /
   vetter invocation / fingerprint assembly) goes profile-parameterised** — a
   per-domain bundle (models + prompt + rules + vetter + table writer) is the plug, so
   a future third schema is content work, not plumbing. Bounded to what the two real
   instances force: no profile registry, no plugin machinery, no speculative
   abstraction (the plan 🛑 reviews the parameterisation seam). ICF fingerprints
   compose from ICF constants only. **IOF's fingerprint changes exactly once, via item
   11's approved rider** (deliberate, pre-ground-truth); beyond the rider's named
   version bumps, IOF constants are untouched — test pin per the 020 pattern: old
   memos reuse under the old fingerprint, `iof_v3` extracts fresh alongside.
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
   carrying the recommendation/finding line, the claim_basis lines (if adopted), the
   inner-setting rule (item 1), source-named-never-canonicalised discipline for all
   reference fields, and an explicit **never-infer / never-grade line** (the V2
   lesson: no "infer from context if not explicit", no High/Moderate/Low judgment
   ordinals, no transferability verdicts — reported-or-null, always anchored).
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
   - **Reader shape preserved (owner, 2026-07-12):** the as-built pattern holds for
     both kinds — one scoped setup query per kind into process memory
     (`make_findings_reader`), ALL filtering server-side in the reader closure,
     results-only into model context, truncation-capped and flagged. ❓ plan decision:
     the cap arithmetic once two kinds share a return — leaning **per-kind caps** (a
     barrier-rich document must not crowd effects out of the return, or vice versa).
   - **No free-text dimension filter in 021 (owner, 2026-07-12):** filters stay
     id/group/closed-attribute-keyed. A naive keyword match over source-named
     `intervention` values would silently miss differently-worded companion documents
     — the exact V2 lesson the data-model's committed hybrid dimension indexing
     exists for. Cross-wording resolution stays with `group` (the designed
     identity-resolver; cross-schema at Slice C) and, when scale outgrows
     envelope-plus-bare-call reads, with hybrid dimension search — **a Slice C
     contract-agenda item, not 021 work** (it owns the writer's retrieval surface and
     must land pre-eval if built). ICF's source-named reference values are shaped to
     ride the same committed dimension index when it lands (shared vocabulary =
     shared index target — free by construction).
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
    capability's contract (the IOF precedent). Research-review additions (owner,
    2026-07-12): **`intervention_specification`** joins the candidate list
    (TIDieR-shaped delivery facets — dose/mode/provider/training; the most demanded
    AND most under-reported cluster, 39% adequacy; first readers Transferability +
    Options Assessment — a specification record, not a context claim, hence not ICF
    bloat); and a **companion-document retrieval seam** for the future transferability
    capability (process evaluations publish separately from their trial results 76% of
    the time, median 15.5 months later — the capability's acquire step should hunt
    companion process evaluations; ICF's nullable-outcome + reference-mediated design
    already absorbs findings arriving in different documents than their effects).
    The sweep also places **hybrid dimension search over finding reference values**
    (the data-model's committed intervention/outcome dimension indexing, with ICF's
    source-named values as co-riders on the same index target) on the **Slice C
    contract agenda** — build-or-defer decided there, where the writer's retrieval
    surface is being reworked and pre-eval sequencing still holds — alongside the
    **cross-kind UNION reference view** (item 1's shared-vocabulary read surface;
    first reader = C's cross-schema grouping). The flow-back also records the
    **presentation-grain design note** (owner, 2026-07-12): finding kinds are
    production/validation categories, never reader-facing navigation — reader
    surfaces pivot on the shared references and on `group`'s facet clusters (one
    card/section per intervention or theme, effects and implementation context as
    facets of one entity; the V2 InterventionCard precedent) — recorded so the
    web-app slice inherits it.
11. **IOF `setting` rider — `iof_v3` (owner-approved 2026-07-12; supersedes this
    contract's earlier "IOF untouched" pin):** the shared reference vocabulary was
    always intervention/outcome/population/setting, but IOF never got the setting
    column (setting exists only as a stratum qualifier scoping specific claims) —
    and setting is what GRADE indirectness/Wang/TRANSFER compare for EFFECT evidence
    too. Ground truth is not yet authored, so this is the one cheap moment (the 020
    rationale, applied once more). Scope, deliberately minimal: one nullable
    source-named `setting` column on `intervention_outcome_finding` (same semantics
    + inner-setting rule as ICF's, via the shared vocabulary definition) · wire +
    stored model field · `SCHEMA_VERSION` → `iof_v3` · `iof_rules_v3` (coverage
    mapping for the new nullable field) · `extract_iof_v7` (lead-only: the setting
    guidance line + few-shot touch — nothing else changes in the prompt) ·
    fingerprint bump (deliberate memo invalidation, mini-priced re-extraction) ·
    carriage through the surfaces item 8 already touches. v2-null vs v3-null
    distinguish via `field_coverage` key-absence (the 020 old-row pattern; no
    backfill, existing rows stay valid). **Nothing else rides this bump** — any
    temptation to add further IOF fields is a stop condition.

**Out:** **cross-schema facet grouping** — `group` stays IOF-only this slice; the design
property (shared source-named vocabulary) now exists in both tables, but the multi-table
facet read lands with Slice C's facet rework (`FindingFacetView.effect_direction` has no
ICF analogue — the C multi-facet redesign is the right place to solve that shape, not a
bolt-on here) · implementation-shaped **theme** claims (follow facet grouping) ·
hybrid-indexing any ICF dimension (the dimension-promotion gate is observed behaviour,
not schema enthusiasm) · ICF ground truth + extraction-quality evals (eval slice — this
slice is honestly eval-blind) · downstream capability consumers (Options/Impact/
Transferability/VfM read it later; EB synthesis is the reader now) · any IOF change
beyond item 11's approved `setting` rider (one column, one prompt line, the named
version bumps — nothing else rides; test-pinned) · geography/setting
canonicalisation · Slice C cost/surface work · Bedrock · everything else in
`docs/deferred.md`.

## Constraints & approval gates

- **Schema (needs human approval):** item 2 — one new table + CHECKs, plus item 11's
  single approved IOF column, in one migration. No other changes to existing tables.
- **Bounded invalidation:** the IOF fingerprint bump happens exactly once, via item
  11's rider, before ground truth — deliberate and owner-approved. Existing IOF rows
  are never rewritten (no backfill; v2 rows read as "not recorded under v2" via
  `field_coverage` key-absence). Any OTHER change to IOF constants — including
  "quickly parameterising" an IOF surface in a way that alters its fingerprint beyond
  the rider's named bumps — is a stop condition.
- **Prompt-bearing surfaces are lead-only:** `extract_icf_v1`, the ICF vetter prompt,
  `extract_iof_v7` (the rider's setting line), any synthesise guidance line.
  Mechanical carriage (models, migration, SELECTs, tests, stub payloads) delegates —
  routing marked at plan time.
- **Egress:** none new — same OpenAI route; ICF adds one mini-priced extraction call
  (+ vetter call) per selected document. Cost context: extract+vet was <3% of the $15
  synthesis-run anatomy; doubling it is noise next to Slice C's writer-side work.
- **Deps/CI/public interfaces:** untouched.

## Public / private boundary

All code, migrations and spec changes public-safe. Replay evidence as summaries in
`verification.md`; raw traces stay in Langfuse. Fixture documents openly licensed.

## Model route

Extraction + vetter on `gpt-5.4-mini` via the OpenAI route (the IOF floor; same
step-up-is-recorded rule). Prompt-bearing changes: `extract_icf_v1` +
`extract_icf_vetter_v1` + `extract_iof_v7` (the rider's setting line only), all
lead-authored. Replay set: at least one process-evaluation / qualitative-arm document
rich in implementation material (ideally carrying reported adaptations and a
fidelity/dose observation, exercising the two new vocabulary values) · one effects-only
RCT (expect few/zero ICF records —
honest absence, not manufactured findings) · one document whose implementation content
is author-recommendation-shaped (the vetter line) · one review pooling implementation
findings across settings (setting/geography at finding grain) · one hostile-envelope
fencing probe · **one dual-kind document (owner, 2026-07-12)**: the same passage feeds
both passes and is judged differently by design — an aspiration sentence ("the pilot
aims to cut bills") flagged by the IOF vetter while an adjacent implementation
condition ("rollout stalled where installer training was unfunded") extracts cleanly
as ICF — pinning that the two exclusion lines are independent, not one shared vet ·
**one IOF v3 probe** (a study with a clearly reported delivery setting yields the new
`setting` field; the inner-setting rule holds — mandating institution never recorded).
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
grouping, canonicalisation or eval territory) · any IOF change beyond item 11's rider
(further fields riding the v3 bump, or the profile parameterisation altering IOF's
fingerprint beyond the rider's named version bumps) · any pressure to backfill or
rewrite existing IOF rows · any pressure to blend kinds inside the
unified tool's return (one homogeneous findings list, or any single record mixing
schemas) · budget spent.

## Acceptance checks

- `make verify` green.
- Deterministic tests: migration up/down (incl. the IOF `setting` column) ·
  `context_type` + `claim_level` (+ `claim_basis`, `level`) CHECK ↔
  Literal asserts · `icf_rules_v1` coercion + full coverage mapping + grain gate ·
  claim-key dedup (context_type/intervention/claim twins collapse; distinct types and
  study-vs-pooled `claim_level` twins don't)
  · **IOF fingerprint changes only via the rider** (old memos reuse under the old
  fingerprint; `iof_v3` extracts fresh alongside; v2-null vs v3-null distinguished by
  `field_coverage` key-absence; `iof_rules_v3` coverage for `setting`) ·
  **cross-schema shared-vocabulary drift guard** (one definition, both models import
  it, semantics/coercion asserted equal) · ICF
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
schema-gate approval with owner sign-off date, the bounded-invalidation evidence (old
IOF memos reusable under the old fingerprint; only the rider's bumps in the v3
fingerprint diff), deferred.md + spec flow-back diff summary, known gaps.

## Risk tier & review focus

**Tier 3** — schema hard gate + two new prompt-bearing surfaces + a writer-facing tool
extension. Contract- and plan-stage adversarial reviews per the design skill; review
stack per [review-stack economy]: medium `/code-review`, one security lane (fencing
completeness on the new prompt; migration correctness; the extended tool's read scope
stays project-guarded), contract verifier fresh-context, per-angle diff scoping.

Focus: IOF invalidation bounded to the rider exactly (the one catastrophic failure is
an unintended second invalidation path) · the recommendation/finding
exclusion line · fingerprint completeness for the new domain (every output-affecting
constant versioned) · related-but-distinct held at every surface (kind-segregated tool
returns; no record, envelope entry or claim blending schemas) · shared-vocabulary
drift-guard real, not cosmetic · no scope creep into
facet grouping or eval territory.

## Decisions for the owner at this gate

1. **`context_type` vocabulary** — the seven proposed values (mechanism · barrier ·
   enabler · implementation_condition · delivery_process · adaptation · fidelity;
   the last two added at the research review — FRAME and Carroll/TIDieR make them
   first-class, and folding them into delivery_process would lose the queryability
   the future consumers want). This is the schema's load-bearing closed vocabulary;
   ground truth and evals will be authored against it.
2. **CFIR profile fields + level** — `resource_requirements` + `workforce_requirements`
   in v1 (recommended: in — framework-backed: EtD resources, Green Book benchmarks;
   transferability/VfM are their eventual readers), plus the `level` enum
   (system·organisation·provider·recipient — CFIR coding practice; recommended: in);
   or fold the texts into `claim` for a lighter v1. `complexity` dropped either way.
3. **`claim_basis`** — three-way studied · author_assertion · cited_theory (· null),
   per V2's forecast EvidenceBasis and realist practice (recommended: in — the
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
7. **IOF `setting` rider — SETTLED (owner, 2026-07-12): in** (item 11; the "IOF
   untouched" pin released for this one bounded rider — pre-ground-truth is the cheap
   moment; nothing else rides the bump). With it, folded the same day: `study_design`
   and `claim_level` (study·pooled) onto ICF, and the shared reference vocabulary
   defined once with a cross-schema drift guard (storage stays parallel tables; the
   UNION read view rides Slice C with its first reader).
