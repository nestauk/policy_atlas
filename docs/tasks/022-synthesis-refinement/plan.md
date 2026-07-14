# Plan: 022-synthesis-refinement

> **Status:** APPROVED — 2026-07-14 · owner, all eleven gate decisions approved as
> recommended + the v6→v7 retarget ratified (the post-approval contract/rubric
> correction of the stale writer-version premise).
> Plan-stage adversarial review adjudicated 2026-07-14 (codex session 019f5e72,
> 12 findings: 5 blocker · 7 material — ALL adopted: writer bump retargeted
> v6→**v7** (v6 shipped in 021; contract + rubric corrected) · § Payload shapes +
> § Steer schemas + id-mapping now pinned IN the plan · dedicated ICF-rider phase
> added (was DDL-only) · Phase B widened to producer/reader compatibility so its
> full gate is viable · orchestration facet-list mechanics assigned · cost
> protocol = 3 runs with cache controls + v6-runnability harness · new decision 11
> (confidence-boost wire syntax + constants) · Phase F split into bounded briefs
> with lead-pinned message layout · call-budget formula corrected to the inherited
> retry model · review-stack producer named (fresh conversation C) · context-payload
> source pinned (anchor quotes, outside the view) · characterise keeps its own
> min/max bounds policy).
> Contract: [contract.md](contract.md) (approved 2026-07-14 · owner; the v7
> retarget is a factual correction applied post-approval, flagged at this gate).
> Rubric: [rubric.md](rubric.md) (22 boxes). ADR: drafted at Phase H.
> Executor marks default to subagents; lead marks carry justification inline.
> Codex caveat (019–021 precedent): the codex sandbox has no Postgres — the lead
> runs DB-gated acceptance after each codex delivery.

## Phases

**Phase 0 — baseline + gate package** — **lead** *(gate adjudication is judgment)*
- Full `make verify` baseline (mandatory open-gate class; never build on red).
- Present § Plan gate decisions → 🛑 owner adjudication at plan approval. Phase B does
  not start until decision 1 (the DDL set) clears explicitly.

**Phase A — the two-stage clustering engine + characterise refactor** — **codex**
*(judgment-bearing multi-file coherence; done is machine-verifiable: characterise
regression suite green + engine invariant tests)*
- New engine module: ONE shared orchestration/validation core — stage 1 open
  discovery (labels + descriptions only, never an exhaustive id list), stage 2
  batched assignment validated per batch against the deterministically known
  unit-id list; exhaustive coverage = groups + counted residual; unknown/
  double-assigned ids reject at response grain; group-grain label/description
  rejection (013 fix carries over); rejection reasons persist.
- Parameterised by: **unit projection** (id, text, optional context payload,
  optional counterparts) · **eligibility predicate** · **component bound policy**
  (adversarial finding 12 — min AND max are per-component: `group` = min 0 /
  decision-3 ceiling; `characterise` = its existing `MIN_THEMES=3` /
  `min(n, MAX_THEMES=12)` computation and prompt arguments, byte-identical) ·
  assignment batch size + retry/repair caps (decision 8).
- **Characterise refactors onto the engine, behaviour-preserving**: prompts
  byte-identical (test-asserted against current prompt constants), outputs/records
  unchanged — existing suite + a pinned-fixture output-equivalence test. A
  characterise prompt diff is a stop condition.
- `FACET_VALUE_CAP` survives as the fail-closed engine input guard (decision 2).
- Gate: `make verify-fast` (no schema contact; full verify rides Phase B).

**Phase B — schema + compatibility: migration · UNION view · consumer rewrite ·
producer/reader shape-compat** — **codex** *(adversarial finding 4: the schema gate
is only viable when schema, producer and readers are coherent — B lands the
new-shape compatibility at current single-facet behaviour; C adds fan-out)*
- ONE alembic migration on `grouping_result`: stamp each existing row's groups with
  the row's facet → per-facet payload keys (§ Payload shapes) → drop `facet` column
  + `ck_grr_facet`; provenance gains the facet list. `uq_grr_scope_run` +
  `fk_synr_grouping` untouched.
- **Same migration rewrites persisted group-id consumers**: the § Id scheme mapping
  applied to `synthesis_result.blocks` section `group_ids` and grouping-theme
  annotation `referenced_ids` (derivable per row — old rows have exactly one facet).
- **Cross-kind UNION read view** (same approval envelope; columns per decision 5).
- **Downgrade refuses when multi-facet rows exist**; down test covers a pre-upgrade
  dataset.
- **Producer/reader shape-compat**: `group.py` writes the per-facet payload shape
  (still one facet per run at this phase); `synthesise.py` grouping readers +
  `_group_id`/`groups_unsectioned` consume it; loader reads value facets through
  the view. Single-facet behaviour unchanged, test-pinned.
- Gate: **full `make verify`** (schema class — coherent at this exit).

**Phase R — ICF `context_label` rider (beyond the DDL)** — **codex** records/plumbing,
**lead** prompt + vetter text *(adversarial finding 3: the rider had no
implementation phase; extraction-adjacent → its own full gate)*
- The rider column itself lands in Phase B's migration file (second commented op).
- `implementation_context_records.py`: `context_label` wire+stored field,
  `SCHEMA_VERSION` → `icf_v2` (nothing else rides); `field_coverage` key-absence
  semantics (v1 rows read "not recorded under icf_v1"); `render_field_docs` text
  (**lead**-authored field description).
- `extract_icf_v2` (**lead**): ONE rule block — filled only when the source itself
  provides a short name; null otherwise; never extractor-authored summarisation.
- ICF vetter (**lead** text, codex plumbing): `paraphrased_label` flag class —
  a label not groundable in the record's anchors flags (fail-open, IOF-pattern
  storage semantics); knobs unchanged, enters the ICF fingerprint sub-block.
- Memo isolation test: icf_v1 memos stay valid-as-written; icf_v2 extracts fresh;
  IOF memos untouched. Replay probes (share Phase D's tally): label-present doc ·
  no-label doc (null holds) · paraphrase-bait doc (vetter flags).
- Gate: **full `make verify`** (extraction/fingerprint-adjacent class).

**Phase C — multi-facet fan-out + orchestration surface** — **codex** *(mechanics
against pinned invariants; prompts excluded — Phase D)*
- `facet_values.py` / `group.py`: directive facet **list** parse (fail-closed;
  vocabulary = `intervention` · `outcome` · `population` · `barrier_theme` ·
  `enabler_theme` · `mechanism_theme`); per-facet engine runs within one component
  execution, one row; facet-qualified ids minted at payload build (§ Id scheme).
- Unit projections: value facets = normalized value + counterparts + context
  payload (§ Context payloads — anchors loaded per finding-id, OUTSIDE the view);
  claim-theme facets = ICF claim prose read directly from
  `implementation_context_finding`, eligibility = `context_type` match, eligible
  base = matching ICF rows only (never `no_value` for others), base size + hash
  into that facet's provenance.
- **Per-facet failure model** (contract item 6): per-facet outcome object; local
  classes caught + persisted (cap · backend · discovery/assignment exhaustion ·
  validation), siblings continue; component-abort only on corrupt shared input /
  cross-facet invariant violation.
- **Orchestration surface** (adversarial finding 5): `orchestration_plan.py` —
  `GroupingFacet` widens to the six-value literal; `grouping_facet` →
  `grouping_facets: list` (fail-closed validator: requires `group` in components,
  non-empty, known values, no duplicates); `ANALYSIS_DEPTH_TABLE` gains the
  deep-depth default facet set (decision 10); directive compiler emits the facet
  list; plan-compile tests.
- Call budget (adversarial finding 9, the inherited retry model):
  `Σ_f [1 + discovery_retry_cap + ceil(N_f/batch) × (1 + assignment_repair_cap)]`
  with `discovery_retry_cap = 1`, `assignment_repair_cap = 1` (per batch) —
  known before the run, recorded in provenance.
- Gate: `make verify-fast`.

**Phase D — group prompt surfaces + replay** — **lead** *(prompt-bearing is lead-only)*
- Discovery prompt vNext (supersedes `group_facet_v1`): open discovery, per-run
  ceiling number + the recurring-pattern qualitative line, forbidden catch-all
  labels retained; per-projection variants (value vs claim-theme) on one skeleton.
- Assignment prompt (batched; id-keyed data records; context payloads fenced as data).
- **Replay loop** (018 discipline; ≤3 rounds/surface, ≤35 live component replays
  total incl. Phase R's probes, tally in verification.md): granularity across
  differently-sized pinned inputs vs the live over-fragmentation baseline
  (rubric 22); context-payload pin-or-revert (anchoring + dilution probes);
  claim-theme scale replay at ≥200 claims with payloads enabled (live check 2's
  pinned-input precursor).
- Gate: `make verify-fast`.

**Phase E — downstream id + consumption surfaces** — **codex** mechanics, **lead**
tool-description text *(021 Phase-E precedent split)*
- Facet-qualified ids end-to-end: directive `group_ids`, `query_findings` group
  filter, section assignment, per-facet `groups_unsectioned`, envelope carriage —
  unqualified/ambiguous ids reject fail-closed (rubric 11).
- `synthesise.py`: multi-facet payload consumption (one grouping ref, all facets);
  theme-claim validation against per-facet groups; per-facet residual honesty;
  `query_findings` tool-schema description bump (**lead** text).
- Migrated-row + single-facet-run tolerance tests on every read path.
- Gate: `make verify-fast` (schema untouched; B carried the class gate; F2 exits full).

**Phase F — writer/judge mechanics, four bounded briefs** — *(adversarial finding 8:
split; the message-layout design is prompt-bearing and lead-pinned first)*
- **F0 (lead, precedes the briefs):** pin the v7 **message/prefix layout spec** —
  stable system prompt → stable run substrate/intent block → section-varying data →
  task restatement; append-only within a section; exact block boundaries and
  ordering written down for F1/F3 to implement mechanically. *(Layout is a prompt
  concern per doctrine; the builders in `synthesis_backend.py` implement it.)*
- **F1 (codex) — tool-return + retrieval layer:** dedup across all immutable
  records (`{id, already_returned: true}`; citation eligibility = union; budget
  charges new content only) · oversized-only windowed returns (retain winning-unit
  offsets; window = matched unit span ± margin) · skip-and-continue past
  over-budget results · per-argument fail-closed scope filters (doc ids ∈ corpus ·
  group ids resolve · evidence types enum · tags ∈ project tag set) ·
  `_soft_prior` screen-confidence multiplier per decision 11 + final product clamp
  [0.1, 10] + raw-factors/executed-multiplier/suppression provenance.
- **F2 (codex) — repair micro-call:** dependency-complete input assembly (failing
  claim id/reason, replacement span + adjacent prose, per-claim-type dependency
  records), id-carrying replacement schema validated against the failing set;
  full-transcript resend gone (input-content test). Layout per F0.
  Gate at F2 exit: **full `make verify`** (judge-path contact; last heavy writer
  mechanics).
- **F3 (codex) — unspanned lane:** `occupied_claim_spans` (all valid claims,
  all types) separate from `claims_to_judge`; the three counters with pinned
  precedence; supersede-not-concatenate on prose-changing repair.
- **F4 (fast-worker; mechanical, exact specs) — riders:** `lookup` widening to
  screening rows · key-findings cited-only seed filter · batched query embeddings ·
  prompt-facing DTO slimming per the § DTO spec (codex if the DTO split turns out
  multi-file-coherent; fast-worker first).
- **F5 (codex) — steer surface:** side-effect-free `propose_synthesis_plan` +
  deterministic compile per § Steer schemas; no-write test; no runtime pause.

**Phase G — `synthesise_section_v7` + planner sweep + A/B evidence** — **lead**
- `synthesise_section_v7`: F0's layout · id-carrying repair instructions ·
  scoped-search tool description · dedup-reference semantics · slimmed-DTO field
  reference. Conflict audit first. Replay: v6 vs v7 on pinned sections
  (quality-neutrality evidence feeding cost arm (a)).
- Planner prompt sweep (coupled-readers): multi-facet group semantics + facet-list
  directive vocabulary; version-bumped, replay-evidenced.
- **Mandatory 17(i) re-judge-set replay**: same rejudge claim set through old/new
  envelope, verdict-flip inspection (the slice's one judge-envelope change).
- Gate: `make verify-fast`.

**Phase H — records + live checks + review prep** — **lead** judgments,
**fast-worker** sweeps
- Spec flow-back (fast-worker draft, lead review): components §8/§9 · data-model
  (facet grain; UNION view built; **hybrid-indexing line gets the deferral**;
  `context_label` joins the ICF field list) · prompting.md if doctrine-grade
  lessons · spec-bundle `log.md`.
- deferred.md sweep (fast-worker draft, lead review): grammar-v2 discharged ·
  gather/writer-split evidence (post-eval queue head) · D/E sequential-A/B note ·
  unspanned re-baseline note · multi-facet/UNION/ICF-facet entries
  discharged/narrowed · new seams.
- ADR (**lead**): engine design + facet-at-group-grain + claim-theme eligibility +
  context_label reasoning corrections + migration-rewrites-consumers posture.
- **Hygiene audit into verification.md** (adversarial finding 10): generated-files/
  secrets diff check + test-diff review (no deletions/skips/weakenings unjustified)
  — rubric boxes 4/5's named producer.
- **Live checks** (**lead**): the four contract-pinned checks; cost protocol per
  § Cost measurement (three runs).
- verification.md complete. Gate: **full `make verify`** at step-6 exit.

**Step 7–10 (rubric 8's producer — NOT a build phase):** the Tier-3 review stack
(contract verifier · code/security review · adversarial · simplification) runs in a
**fresh review conversation** per the task-cycle spine (the adjudicator must not be
the build chat); findings + adjudications land in verification.md there.

## Payload shapes (pinned — adversarial finding 2; field-level detail is normative)

`grouping_result` after migration (JSONB columns):
- `groups`: `{ "<facet>": [ {"group_id": "<facet>:gNN", "facet": "<facet>",
  "label": str, "description": str, "member_values": [str] (value facets only),
  "member_finding_ids": [str], "size": int, "direction_spread": {...}|null
  (IOF members only, null for claim-theme groups)} ] }`
- `counts`: `{ "<facet>": {"eligible_base": int, "grouped": int, "ungrouped": int,
  "no_value": int (value facets; absent for claim-theme), "groups": int} }`
- `flags`: `{ "<facet>": {"status": "succeeded"|"failed",
  "failure_class": "cap_exceeded"|"backend_error"|"discovery_exhausted"|
  "assignment_exhausted"|"validation_failed"|null, "groups_rejected": bool,
  "value_cap_exceeded": bool} }`
- residuals per facet inside `groups[facet]`'s sibling keys:
  `"ungrouped": {"member_finding_ids": [...], "direction_spread": {...}|null}` and
  (value facets only) `"no_value": {...}` — facet identity is the outer key.
- `grouping_provenance`: existing required keys + `"facets": [str]` +
  per-facet `{"eligible_base_size": int, "eligible_base_sha256": str,
  "call_budget": int, "calls_used": int, "rejection_reasons": [...]}`.
- **Migration transform of an old row**: wrap each JSONB column's current flat
  value under the row's single facet key; mint `group_id`s per § Id scheme; stamp
  `facet` into each group object; provenance gains `facets: [<facet>]`.

## Id scheme + legacy mapping (pinned)

`group_id = "<facet>:g<NN>"` (`NN` = 1-based position in that facet's accepted-group
order, zero-padded to 2). Legacy mapping (migration + readers): an old row's group
with label L at position i in facet f maps to `f:g<i>`; persisted consumer rewrite
replaces label-or-position references in `synthesis_result.blocks[].group_ids` and
theme-annotation `referenced_ids` via that row-local mapping. Directive `group_ids`
and `query_findings` filters accept ONLY qualified ids post-migration (unqualified →
fail-closed error naming the expected form).

## Steer schemas (pinned — shapes normative, Pydantic naming free)

- `propose_synthesis_plan(scope_ref) → {"proposed_sections": [{"title": str,
  "focus": str, "group_ids": [str]}], "available_groups": [{"group_id": str,
  "facet": str, "label": str, "size": int}], "boostable": {"appraisal_tiers": [str],
  "evidence_types": [str], "screen_confidence": {"lo_bounds": [float,float],
  "hi_bounds": [float,float]}}}` — read-only: no artefact mint, no row writes
  (no-write test).
- Compile: accepts a user-response object `{"sections": [...], "group_ids": [...],
  "retrieval_boosts": {...}}` and emits the EXISTING `context["synthesis"]`
  directive verbatim-grammar (plus decision 11's `screen_confidence` key) —
  deterministic, fail-closed, pure function.

## Context payloads (pinned — adversarial finding 11)

Value-facet unit context = up to 2 verbatim **anchor quotes** from the value's
member findings (deterministic: lowest finding_id first; each quote truncated to
240 chars), loaded by finding-id from the finding tables' anchor/grounding columns —
**outside the UNION view** (the view stays reference-columns-only). Claim-theme unit
context = `context_label` (when present) + `intervention`. Missing anchors → empty
context (never blocks). All context enters as id-keyed data records.

## Cost measurement (pinned — adversarial finding 6)

**Three synthesis runs**, all on the same corpus/intent, cold-cache start each
(fresh section prefix; no warm run precedes), executed back-to-back same-day in
this order: (1) legacy arm: v6 prompt + single-facet substrate — the runnable-v6
harness keeps the v6 prompt constants importable and a backend version override
selects them (direct config, no code fork); (2) new arm (a) partner: v7 prompt +
same single-facet substrate → arm (a) = run 1 vs run 2 (Phase-2 isolation);
(3) arm (b): v7 + the final multi-facet configuration → vs the $15.45 / 24%
historical baseline. Each run records: prompt version, facet set, section set,
corpus, model, cache hit/miss split, repair incidence, wall-time. Estimated live
spend: 3 × $5–15 = **$15–45** + grouping runs ~$3–6 + smoke ~$2.

## Plan gate decisions (adjudicate at this plan approval 🛑)

1. **The DDL set**: one migration file — (a) grouping_result facet-to-group-grain +
   consumer rewrites + UNION view, (b) ICF `context_label` column. Downgrade
   refuses on multi-facet rows. *Recommend: approve as scoped.*
2. **`FACET_VALUE_CAP`**: stays 400 as engine input guard. *Recommend: unchanged.*
3. **Granularity ceiling — `group` component ONLY** (characterise keeps its own
   min/max policy, finding 12): `max_groups = clamp(ceil(N/5), 3, 40)` per facet
   run. *Recommend: this formula, plan-pinned; eval owns calibration.*
4. **Payload shapes**: § Payload shapes above, normative. *Recommend: approve.*
5. **UNION view columns**: finding_id · kind · extraction_record_id · project
   scoping legs · the six shared reference columns. *Recommend: as listed.*
6. **Context payloads**: § Context payloads above (anchor-quote source, 2 × 240
   chars, discovery carries context only when facet unit count ≤ 120).
   *Recommend: approve; replay pin-or-revert.*
7. **Group id scheme**: § Id scheme above (`facet:gNN` + row-local legacy mapping).
   *Recommend: yes.*
8. **Engine call caps**: assignment batch = 50 units/call; `discovery_retry_cap=1`;
   `assignment_repair_cap=1` per batch; budget formula per Phase C. *Recommend:
   these values (mirror characterise's proven caps).*
9. **Steer surface**: § Steer schemas above; compile emits the existing directive
   grammar **plus decision 11's one new key** (the earlier "no new grammar" claim
   is corrected — the confidence boost IS a bounded grammar extension).
   *Recommend: approve.*
10. **Deep-depth default facet set**: `intervention` · `outcome` · `barrier_theme` ·
    `enabler_theme` · `mechanism_theme` (population request-only). *Recommend: all
    five; cost visible in live check 2.*
11. **Screen-confidence boost wire syntax + constants** (adversarial finding 7 —
    NEW): directive key `"screen_confidence": {"lo": float, "hi": float}` with
    bounds 0.5 ≤ lo ≤ hi ≤ 4.0; defaults **lo = 1.0, hi = 2.0** (boost-only, the
    `SELECTION_PRIOR_BOOST=2.0` precedent); multiplier = `lo + conf × (hi − lo)`
    over the **effective screen confidence** (highest-stage non-failed row — the
    effective-screen helper); missing confidence → 1.0; **suppression predicate**:
    a resolved selection reference suppresses the confidence multiplier entirely
    (selection already priced confidence, `select.py` reads it), recorded
    `confidence_suppressed: true` in retrieval provenance. Retrieval docs load
    confidence + stage at scope build. *Recommend: approve as specified.*

## Live-check pins

The contract's four acceptance live checks; cost protocol per § Cost measurement
(three runs). Replay budget: ≤35 component replays total (Phases D + R + G share
the tally, per-surface allocation recorded in verification.md).

## Dependencies

Phase A → C, D · Phase B → C, E (B is self-coherent: schema + compat land together,
finding 4) · A ∥ B independent · B → R (the rider column precedes the record field) ·
C → D · C + E before live check 2 · F0 → F1/F2/F3 (layout pinned first) · F* → G ·
E before G's arm (b) · H last. Build order:
`0 → A ∥ B → R ∥ C → D ∥ E → F0 → F1–F5 → G → H`.
