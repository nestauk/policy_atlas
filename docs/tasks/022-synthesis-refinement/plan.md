# Plan: 022-synthesis-refinement

> **Status:** DRAFTED — pending plan-stage adversarial review + owner approval (🛑).
> Contract: [contract.md](contract.md) (approved 2026-07-14 · owner; contract-stage
> adversarial review adjudicated 15/15). Rubric: [rubric.md](rubric.md) (22 boxes).
> ADR: drafted at Phase H (multi-facet clustering-engine design + the reasoning
> corrections recorded in contract item 5).
> Executor marks default to subagents (orchestrator-delegation convention); lead marks
> carry justification inline. Codex caveat (019/020/021 precedent): the codex sandbox
> has no Postgres — the lead runs DB-gated acceptance after each codex delivery.
> Pattern precedent: [021 plan](../021-icf/plan.md), mirrored against as-built code
> (grouping machinery verified at `group.py` / `facet_values.py` / `facet_grouping.py`;
> synthesis surfaces at `synthesise.py` / `synthesis_tools.py` / `synthesis_backend.py`;
> unit policy at `embeddings.py`; all line-level claims re-verified in the design
> conversation and by two Codex passes, 2026-07-14).

## Phases

**Phase 0 — baseline + gate package** — **lead** *(gate adjudication is judgment)*
- Full `make verify` baseline (mandatory open-gate class; never build on red).
- Present § Plan gate decisions → 🛑 owner adjudication at plan approval. Phase B does
  not start until decision 1 (the DDL set) clears explicitly.

**Phase A — the two-stage clustering engine + characterise refactor** — **codex**
*(judgment-bearing multi-file coherence; done is machine-verifiable: characterise
regression suite green + engine invariant tests)*
- New engine module (e.g. `clustering_engine.py`): ONE shared orchestration/validation
  core — stage 1 open discovery (labels + descriptions only, never an exhaustive id
  list), stage 2 batched assignment validated per batch against the deterministically
  known unit-id list; exhaustive coverage = groups + counted residual; unknown /
  double-assigned ids reject at response grain; group-grain label/description rule
  rejection (the 013 fix carries over); rejection reasons persist.
- Parameterised by: **unit projection** (id, text, optional context payload,
  optional counterparts) · **eligibility predicate** · **adapter minima** (group
  discovery min = 0, zero themes → all eligible units residual, assignment skipped;
  characterise keeps its ≥1 bound) · **granularity ceiling** (computed per run from
  unit count — decision 3 — injected into the discovery prompt as that run's number;
  no lower target) · assignment batch size (decision 8).
- **Characterise refactors onto the engine, behaviour-preserving**: prompts
  byte-identical (test-asserted against the current prompt constants), outputs/records
  unchanged — regression evidence = existing characterise suite + a pinned-fixture
  output-equivalence test. A characterise prompt diff is a stop condition.
- `FACET_VALUE_CAP` survives as the fail-closed engine input guard (posture: value
  unchanged at 400 — decision 2); per-call pressure moves to the batch size.
- Gate: `make verify-fast` (new module + refactor; no schema contact — the
  characterise regression suite is the load-bearing check here; full verify rides
  Phase B's schema gate immediately after).

**Phase B — schema: migration + UNION view + persisted-consumer rewrite** — **codex**
*(exact spec below + § Payload shapes; machine-verifiable via up/down + rewrite tests)*
- ONE alembic migration on `grouping_result`: stamp each existing row's groups with
  the row's single facet → per-facet payload keys (§ Payload shapes, decision 4) →
  drop `facet` column + `ck_grr_facet`; provenance gains the run facet list.
  `uq_grr_scope_run` + `fk_synr_grouping` untouched.
- **Same migration rewrites persisted group-id consumers** (contract item 2):
  deterministic old-label → facet-qualified-id mapping applied to
  `synthesis_result.blocks` section `group_ids` and grouping-theme annotation
  `referenced_ids`. Mapping is derivable per row (old rows have exactly one facet).
- **Cross-kind UNION read view** in the same migration's approval envelope:
  shared reference columns + kind discriminator + finding id + project/extraction
  scoping (decision 5 pins the column list). Value-facet loading reads through it;
  claim-theme loading reads `implementation_context_finding` directly.
- **Downgrade refuses when multi-facet rows exist**; down test covers a pre-upgrade
  dataset (contract item 2).
- **ICF `context_label` rider**: nullable Text column on
  `implementation_context_finding` — rides this migration file as a second,
  clearly-commented op (one migration file, two approved DDL groups — decision 1).
- Gate: **full `make verify`** (schema class).

**Phase C — multi-facet `group` component on the engine** — **codex** *(mechanics
against pinned invariants; prompts excluded — Phase D)*
- `facet_values.py` / `group.py`: directive facet **list** parse (fail-closed; facet
  vocabulary = `intervention` · `outcome` · `population` · `barrier_theme` ·
  `enabler_theme` · `mechanism_theme`); per-facet fan-out — separate engine runs per
  facet within one component execution, one `grouping_result` row.
- Unit projections: value facets = normalized value + counterparts (+ context
  payload, decision 6) via the UNION view; claim-theme facets = ICF claim prose,
  eligibility = `context_type` match, **eligible base = matching ICF rows only**
  (IOF + non-matching ICF are outside the base, never `no_value`), base size + hash
  into that facet's provenance.
- **Facet-qualified group ids** (id scheme: `facet:LNN` shape or equivalent —
  duplicate-proof, short, decision 7) minted at payload build.
- **Per-facet failure model** (contract item 6): per-facet outcome object within the
  single row; facet-local failure classes caught + persisted (cap · backend ·
  discovery/assignment exhaustion · validation), siblings continue; component-abort
  only on corrupt shared input / cross-facet invariant violation.
- Call budget known before the run: `Σ_facets (1 + ceil(N_f/batch) + repair_cap)`.
- Gate: `make verify-fast`.

**Phase D — group prompt surfaces + replay** — **lead** *(prompt-bearing is lead-only)*
- Discovery prompt vNext (supersedes `group_facet_v1`): open discovery, granularity
  ceiling as that run's number + the recurring-pattern qualitative line, forbidden
  catch-all labels retained; per-projection variants (value vs claim-theme) sharing
  one skeleton.
- Assignment prompt (batched; id-keyed data records; context payloads fenced as data).
- **Replay loop** (018 discipline; bounds: ≤3 rounds/surface, ≤35 live component
  replays total, tally in verification.md): granularity checked across
  **differently-sized pinned inputs** against the live over-fragmentation baseline
  (rubric 22); context-payload pin-or-revert (anchoring + dilution probes); the
  claim-theme scale arm at ≥200 claims with payloads enabled (acceptance live check 2
  pins the live version; the replay version runs on pinned inputs first).
- Gate: `make verify-fast`.

**Phase E — downstream id + consumption surfaces** — **codex** mechanics, **lead**
tool-description text *(prompt-surface split per the 021 Phase-E precedent)*
- Facet-qualified ids end-to-end: directive `group_ids`, `query_findings` group
  filter, section assignment, per-facet `groups_unsectioned`, envelope carriage —
  unqualified/ambiguous ids reject fail-closed (rubric 11).
- `synthesise.py`: multi-facet grouping payload consumption (one grouping ref covers
  all facets); theme-claim validation against per-facet groups; per-facet residual
  honesty in coverage claims; `query_findings` tool-schema description bump
  (**lead**-authored text).
- Old-row (migrated) + single-facet-run tolerance tests on every read path.
- Gate: `make verify-fast` (consumption surfaces; schema untouched — consolidation
  argued: Phase B carried the schema-class full verify; Phase F exits full).

**Phase F — writer/judge cost + surface mechanics** — **codex** *(precise specs, all
test-pinned; every item has a contract line and most were twice-verified in code)*
- Tool-return layer (`synthesis_tools.py`): dedup across ALL immutable records
  (chunks/findings/lookups; repeat = `{id, already_returned: true}`; citation
  eligibility = union; budget charges new content only) · oversized-only windowed
  returns (retain winning-unit offsets through candidate construction; window =
  matched unit span ± margin) · skip-and-continue past over-budget results ·
  per-argument fail-closed scope filters (doc ids ∈ corpus · group ids resolve ·
  evidence types enum · tags ∈ project tag set).
- `_soft_prior`: screen-confidence multiplier (grammar per contract item 15) + final
  product clamp [0.1, 10] + raw factors/executed multiplier/suppression provenance.
- Repair micro-call (`synthesis_backend.py` + `synthesise.py`): dependency-complete
  input assembly (failing claim id/reason, replacement span + adjacent prose,
  per-claim-type dependency records), id-carrying replacement schema validated
  against the failing set; full-transcript resend gone (input-content test).
- Layered cache prefix assembly (`synthesis_backend.py`): stable system → stable run
  substrate/intent → section-varying data → task restated; append-only within a
  section; provider-neutral.
- Unspanned lane: span map from ALL valid claims (`occupied_claim_spans` separate
  from `claims_to_judge`) · three counters with pinned precedence · supersede-not-
  concatenate on prose-changing repair.
- DTO slimming (prompt-facing group/characterisation summaries + slim ledger) ·
  key-findings cited-only seed filter · batched query embeddings · `lookup`
  screening-row widening · steer surface: side-effect-free `propose_synthesis_plan`
  + deterministic directive compile (schemas: decision 9), no-write test.
- Gate: **full `make verify`** at Phase F exit (last heavy code phase; judge-path
  contact).

**Phase G — `synthesise_section_v6` + planner sweep + A/B evidence** — **lead**
*(prompt-bearing; the one writer bump carries items 9/10/11/12/13/18's prompt halves)*
- `synthesise_section_v6`: cache-layout restructure · id-carrying repair
  instructions · scoped-search tool description · dedup-reference semantics ("you
  have already seen record X") · slimmed-DTO field reference. Conflict audit first
  (prompting.md rule 1). Replay: v5 vs v6 on pinned sections (quality-neutrality
  evidence for the two-arm cost check's arm (a)).
- Planner prompt sweep (coupled-readers rule): multi-facet group semantics +
  facet-list directive vocabulary; version-bumped, replay-evidenced.
- **Mandatory 17(i) re-judge-set replay**: same rejudge claim set through old/new
  envelope, verdict-flip inspection (the slice's one judge-envelope change).
- Gate: `make verify-fast`.

**Phase H — records + live checks + review prep** — **lead** judgments,
**fast-worker** sweeps
- Spec flow-back (fast-worker draft, lead review): components §8 (multi-facet engine,
  claim-theme facets, per-facet honesty) + §9 (theme-claim availability over
  claim-theme groups; tool-return semantics) · data-model (facet grain; UNION view
  built; **hybrid-indexing line receives the deferral adjudication**; context_label
  joins the ICF field list) · prompting.md if the loop yields doctrine-grade lessons ·
  spec-bundle `log.md`.
- deferred.md sweep (fast-worker draft, lead review): grammar-v2 entry discharged
  (subsumed) · gather/writer split evidence recorded post-eval-queue-head · D/E
  sequential-A/B note · unspanned re-baseline note · multi-facet/UNION/ICF-facet
  entries discharged/narrowed · new seams from the build.
- ADR (**lead**): the clustering-engine design (components distinct, machinery
  converged), facet-at-group-grain, claim-theme eligibility identity, the
  context_label reasoning corrections, migration-rewrites-consumers posture.
- **Live checks** (**lead**): the four contract-pinned checks — scale run (≥184
  values) · multi-facet run incl. a claim-theme facet at ≥200 claims with payloads ·
  full-chain smoke · **two-arm cost measurement** (arm (a) v5-vs-v6 legacy substrate;
  arm (b) final config vs $15.45 baseline; full run-metadata recording; wall-time
  band re-measure rides arm (b)).
- verification.md complete. Gate: **full `make verify`** at step-6 exit.

## Plan gate decisions (adjudicate at this plan approval 🛑)

1. **The DDL set**: one migration file carrying (a) grouping_result facet-to-group-
   grain + consumer rewrites + UNION view, (b) the ICF `context_label` column.
   Downgrade refuses on multi-facet rows. *Recommend: approve as scoped.*
2. **`FACET_VALUE_CAP`**: stays 400 as the engine input guard (scale pressure now
   lives in the batch size, not the one-call partition). *Recommend: unchanged;
   eval owns the ceiling.*
3. **Granularity ceiling**: `max_groups = clamp(ceil(N/5), 3, 40)` computed per
   facet run, injected into discovery; no lower target. *Recommend: this formula,
   plan-pinned constant; eval owns calibration.*
4. **Payload shapes**: per-facet keys under `groups` / `counts` / `flags`
   (`{facet: {...}}`), per-facet outcome object with `status` · groups · residuals
   (facet-tagged) · rejection_reasons · call accounting; provenance carries facet
   list + per-facet eligible-base size/hash. Exact JSON in the Phase B codex brief.
   *Recommend: approve shape class; field-level review at Phase B delivery.*
5. **UNION view columns**: finding_id · kind · extraction_record_id · project scoping
   legs · the six shared reference columns (intervention/outcome/population/setting/
   study_geography/study_design). *Recommend: as listed — reference-columns-only per
   the data-model commitment.*
6. **Context payloads**: assignment batches always carry per-unit context (≤2
   snippets × ≤240 chars, id-keyed, source content only); discovery carries context
   only when the facet's unit count ≤ 120 (dilution guard). *Recommend: these
   numbers, replay pin-or-revert.*
7. **Group id scheme**: `"autonomy:g07"`-style `facet:gNN` ids (short, duplicate-proof
   across facets, human-scannable in directives). *Recommend: yes.*
8. **Assignment batch size**: 50 units/call (mirrors characterise's batched
   assignment scale). *Recommend: 50, plan-pinned.*
9. **Steer surface schemas**: `propose_synthesis_plan` returns proposed sections +
   available facet groups/themes + boostable vocabularies; compile accepts the
   existing directive grammar verbatim (no new grammar). *Recommend: approve;
   exact Pydantic shapes at Phase F delivery.*
10. **Deep-depth default facet set**: `intervention` · `outcome` · `barrier_theme` ·
    `enabler_theme` · `mechanism_theme` (population stays request-only). The trio is
    the slice's payoff; each facet's marginal cost is small (mini-model discovery +
    batched assignment). *Recommend: all five; cost visible in live check 2.*

## Live-check pins

The contract's four acceptance live checks, unchanged (contract § Acceptance).
Estimated live spend: scale + multi-facet runs ~$3–6 (grouping is mini-tier);
two-arm cost measurement = two synthesis runs ~$10–25 total (arm (a) legacy substrate,
arm (b) final config); smoke ~$2. Replay budget: ≤35 component replays (Phase D+G
tally shared).

## Dependencies

Phase A → C, D (engine before its consumers) · Phase B → C, E (ids/view before
consumers) · A and B are independent of each other · C → D (prompts replay against
real machinery) · C+E before live check 2 · F → G (v6 describes F's mechanics) ·
Phase-1 phases (A–E) and F are independent except E's envelope carriage lands before
G's replay arm (b) · H last. Build order: 0 → A ∥ B → C → D ∥ E → F → G → H.
