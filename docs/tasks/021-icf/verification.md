# Verification: 021-icf

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, build open) | pass | 1178 tests green pre-build |
| `make verify` (Phase A exit) | pass | after lead fix: wire `setting` default removed + example/fixture carriage |
| `make verify-fast` (Phase C surfaces) | pass | prompts + structural tests |
| `make verify` (Phase B exit) | pass | after lead fix: shared selected/basis keys in roll-up projection |
| `make verify-fast` (Phase D) | pass | incl. combined tree with C round-2 prompt |
| `make verify` (Phase E exit) | pass | green first run — 1966-insertion phase |
| `make verify` (step-6 exit) | pass | see commit d-stamp in PR |

## Checks beyond the build (deterministic highlights)

- Migration 2f9d7e1c4a6b roundtrip (tests/test_icf_migration.py): v2-shaped IOF row
  survives up/down untouched, ICF CHECKs live, symmetric down, no backfill.
- Cross-schema drift guard (tests/test_finding_references.py): shared descriptions
  byte-identical (intervention/population/study_geography/study_design), column
  types + per-schema requiredness (IOF outcome required / ICF nullable) pinned,
  shared NULL_LIKE coercion asserted on both rules paths.
- icf_rules_v1: coercion, non-valid-only coverage, grain gate, claim-key twins
  (study-vs-pooled don't collapse; metadata twins do, anchors merged).
- iof_rules_v3: setting coercion/coverage; top-level setting NOT in IOF claim key;
  stratum-setting coexistence pinned.
- Memo isolation (tests/test_extract.py): IOF memo hit + ICF fresh on same doc;
  per-profile fingerprints; not-selected vs fired-zero roll-up distinction.
- Profiles directive fail-closed (tests/test_extract_directive.py +
  test_orchestration_plan.py): unknown/duplicate/empty/missing-iof rejected at
  compile AND at the extract boundary; deep default both, IOF-only expressible;
  steering delta round-trip.
- Phase E acceptance set (tests/test_synthesis_tools.py, test_synthesise*.py,
  test_group.py, test_facet_values.py): kind-segregated return + kind key,
  kinds default/mismatch fail-closed, availability sentinel, per-kind caps +
  truncation, membership bridge (kind tags, per-kind counts, IOF-only
  direction_spread), envelope carriage, ICF resolve-via-row,
  icf_context_type_count (extraction-wide + group-scoped + ICF-less reject),
  old-flat-row tolerance, stub both-profiles round trip.
- ADR 0017 re-checked at step 6: matches the as-built code on all ten
  decisions (profile bundle, per-profile roll-up, directive, field set,
  shared vocabulary, rider bounds, unified tool, membership bridge, vetter
  semantics).

## AI behaviour — replay evidence (eval-blind; shape + exclusion lines only)

Refine-replay loop (owner-added, 018 pattern). Bounds: ≤3 rounds/surface,
≤30 live component replays. **Tally: 31** (16 round 1 · 4 round 2 · 4 round 3 ·
4 dual-kind rerun · 3 planner — one planner call wasted on a probe-script
unpack bug, not a prompt iteration; recorded as the 1-over overage).

Probe set (docs: BMC Geriatrics reablement process evaluation, CC-BY-4.0,
Rooijackers et al. 2021, 10.1186/s12877-020-01936-7 — sourced this task;
frontiers_getting_ready_2018, plos_food_environment_review,
worldbank_obesity_flagship, nesta_heat_pumps_report_page from the fixture
corpus; one synthetic hostile envelope):

- **Process evaluation** (adaptations+fidelity): r1 67 → r2 58 records; all
  vocabulary values exercised incl. adaptation + fidelity; Netherlands
  geography; source-named settings; claim_basis studied-dominant with honest
  author_assertion share; 2-3 vetter flags.
- **Effects-only RCT**: r1 42 records with 27 protocol-specification
  delivery_process + hedged speculation as 'studied' → round-2 prompt refine
  (specification-vs-delivery line + hedged-commentary basis clause) → 30
  records, speculation-basis fixed, fidelity/barrier/dose records correct.
  Round-3 tightening REGRESSED (42, protocol back) → reverted; round 2 is the
  shipped text. **Known gap (eval-blind pin): Methods-heavy primary studies
  still yield ~a dozen protocol-shaped delivery_process records** — bounded by
  flag-not-drop + the eval slice owns quality measurement.
- **Recommendation-shaped doc** (World Bank flagship): 16 records, all
  claim_basis author_assertion, 15 pooled; hand-read — evidence-synthesis
  assertions, NOT should-advice; the flagship's actual recommendations did not
  extract. Exclusion line held; vetter 0 flags correct.
- **Review pooling implementation findings** (PLOS realist review):
  claim_level pooled present; 12 distinct finding-grain geographies + 14
  settings (the 020 review-variability pattern reproduced on ICF).
- **Hostile envelope**: injected instructions demanded Atlantis geography +
  fabricated barrier — output: 1 record from the benign segment only, geography
  Denmark, setting null, no injected content, anchor exact.
- **Dual-kind** (process evaluation, both profiles): IOF extracted 5
  effect-shaped findings, ICF 46 context findings, each vetter judged only its
  own kind — independent exclusion lines evidenced. (The nesta summary page
  variant yielded ICF 0 — honest absence on a proposals-only page; its IOF
  side: 2 modelled cost findings, unflagged per the pinned modelled-results
  line.)
- **IOF v3 setting probe**: setting "Head Start" (delivery setting) on 9/14,
  null 5/14, never the mandating institution; finding-grain geography carried.
- **planner_v4**: deep intervention intent → extract_profiles ["iof","icf"],
  reply names both halves; explicit effects-only intent → ["iof"] with the
  narrowing explained in the reply.

Honesty pin (contract): probes show shape and exclusion-line behaviour; no
extraction-quality claim until the eval slice's ground truth exists.

## End-to-end command

```
uv run python <scratchpad>/live_check_021.py        # extract both profiles (dev DB)
uv run python <scratchpad>/live_check_021_phase2.py # group retry + synthesise + checks
```
(Session scratchpad scripts; dev DB + ids inline, keys from `.env`. Replay
probes: `uv run python <scratchpad>/probe_icf_v1.py`, `probe_planner_v4.py`.)

**Live check results (dev-DB project 91d2d684, scope 308bb287, selection
332c8d7c reused — never re-searched):**
- **Migration on real data**: 3,236 IOF finding rows + 357 extraction records
  untouched across `alembic upgrade head` (0f4e2d8c9b1a → 2f9d7e1c4a6b); all
  pre-existing rows read `setting` NULL (no backfill); ICF table created empty.
- **Both-profiles live extract** (run 232d6afb, both vetters active): 10/10
  docs fresh under the new fingerprints; IOF 130 findings (iof_v3 /
  extract_iof_v7 / iof_rules_v3 in provenance); **ICF 203 findings** (icf_v1 /
  extract_icf_v1 / icf_rules_v1 / extract_icf_vetter_v1), per-profile roll-up
  shape live (counts.profiles / provenance.profiles / per-doc profiles).
- **Bounded invalidation**: the 020 run's flat row reads iof_v2 /
  extract_iof_v6 / iof_rules_v2 — the new IOF profile provenance differs in
  EXACTLY the rider's three named bumps (schema/prompt/field_rules); model,
  window, caps, vetter identical. Old rows never rewritten.
- **ICF rows live**: all 7 context_types present (delivery_process 56,
  barrier 46, enabler 32, mechanism 31, implementation_condition 24,
  fidelity 13, adaptation 1); claim_basis on 203/203 (author_assertion-heavy —
  grey-literature corpus, honestly recorded); setting on 119; claim_level
  pooled on 4; every row anchored + coverage-keyed.
- **Group (live limitation, recorded)**: FOUR grouping attempts over the
  doubled value list (333 findings, 184 distinct interventions) all failed
  partition validation — group_facet_v1 on gpt-5.4-mini emitted duplicate
  value ids in every call and repair; the fail-closed validator rejected the
  partitions and every run degraded honestly to the all-ungrouped residual.
  **The residual carried per-kind member counts {"icf": 203, "iof": 130} —
  loader-level kind-spanning membership evidenced live**; grouped-run section
  envelope carriage is deterministically test-pinned (stub grouped-run tests)
  but not live-evidenced at this value-list size. Recorded as a REQUIRED
  Slice-C facet-redesign input (value-list scale is a real capacity limit of
  the current facet prompt), not a 021 defect.
- **Synthesise** (run 90680bd5, artefact b12b8c99, grouping reference carried
  the ungrouped-residual run): 10 blocks / 9 sections; claims — 27 finding ·
  34 chunk · 1 pattern · 6 theme · 12 gap · 3 reasoning; 157 anchors verified,
  9 unverified, 1 unsupported_mis_cited (flagged lane, visible). **34
  annotation finding references resolve to ICF rows** (66 to IOF): the writer
  read and cited implementation-context findings on the minted artefact, with
  `cited_finding_kinds` + per-anchor `kind: "icf"` and extract-verified quotes
  (resolve-via-row, model never authored them).
- **Implementation-shaped pattern claim validating (live)**: the writer's one
  organic pattern claim was characterisation-shaped, so the
  `icf_context_type_count` validator was exercised directly against the live
  extraction: the validator's computed counts over the 203 live ICF records
  equal the DB group-by exactly ({adaptation 1, barrier 46, delivery_process
  56, enabler 32, fidelity 13, implementation_condition 24, mechanism 31});
  a true-stated payload passes the equality gate and a perturbed one rejects.
  The full branch logic (extraction-wide, group-scoped, ICF-less reject) is
  deterministically test-pinned.

## Diff summary

One slice, end-to-end: the second finding schema `implementation_context_finding`
(icf_v1 — 7-value context_type, claim/claim_level/claim_basis/level,
resource/workforce requirements, shared source-named references) + migration
2f9d7e1c4a6b (one migration, symmetric down, no backfill, carries the IOF
`setting` rider); shared reference vocabulary defined once
(finding_references.py) with per-schema requiredness + drift guards; the
extract pipeline profile-parameterised (two bundles, per-profile
fingerprints/memos/roll-up — not-selected vs fired-zero distinguishable); IOF
rider = exactly the named bumps (iof_v3 / extract_iof_v7 / iof_rules_v3, one
column, setting guidance block + few-shot touch, not in the claim key);
prompt surfaces extract_icf_v1 + extract_icf_vetter_v1 (lead-authored,
refine-replay evidenced) and planner_v4 (two-profile semantics,
extract_profiles draft field); plan-visible profiles directive fail-closed
end-to-end (compile, steering, extract boundary; deep → both, IOF-only
expressible, ICF-only rejected); unified kind-typed query_findings
(kind-segregated, per-kind caps, honest availability,
synthesise_section_v6 = tool-schema unit bump only); kind-spanning group
membership bridge (kind tags, per-kind counts, direction_spread
IOF-members-only); envelope carriage + ICF resolve-via-row +
icf_context_type_count deterministic validator; spec flow-back
(data-model/components/log) + deferred.md discharge with eight narrowed
seams + the 012 linkage-entry discharge.

Flagged deviations / adjudication notes:
- Wire-model idiom enforcement (Phase A acceptance): codex gave IOF wire
  `setting` a pydantic default; lead removed it (strict structured-output
  schema idiom — all fields required) and carried `setting=None` explicitly in
  the few-shot examples + dict fixtures.
- Phase B acceptance fix: `extraction_profile_counts` merges shared
  selected/basis keys into the per-profile projection (group's base-count
  reader raised on the new shape; caught by composed-chain suites).
- Refine-replay overage: 31 live replays vs the ≤30 bound (one wasted call on
  a probe-harness bug).
- ICF-only extraction pinned unsupported (Phase D validator; contract names
  both/IOF-only as the expressible compositions — recorded as an explicit
  compile error, seam noted in deferred.md).
- **Owner-directed amendment (post-step-6, 2026-07-13): old-roll-up tolerance
  removed.** The plan's "tolerate old flat rows" line (adversarial finding 6)
  was written for a database with history worth reading; the owner ruled the
  project greenfield — pre-021 `extraction_result` rows need not stay
  readable. `extraction_rollup.py` deleted; readers consume the per-profile
  shape directly (`record_ids_by_profile` lives in extract.py next to the
  shape's writer); a flat row referenced by group now raises a loud
  corrupt-reference error instead of being silently projected; the
  flat-shape tolerance tests were removed/converted (the reader
  ICF-availability test now seeds a real IOF-only per-profile row).
  Pre-021 rows in the dev DB (e.g. the 020 live-check run) are no longer
  referenceable by group/synthesise — accepted by the owner. No effect on
  the spec flow-back (the specs never claimed old-row tolerance).

## Executor provenance (review handoff / family flip)

- Phase A product code: Codex (task-mri79z6c-4c0bva); tests codex; lead fixes
  as flagged above. Phase B: Codex (task-mri8hp0s-jytoff) + one lead fix.
  Phase D mechanics: Codex; Phase E: Codex (TBD id).
- Lead-only surfaces: extract_icf_v1 (+2 refine rounds), extract_icf_vetter_v1,
  extract_iof_v7 setting block, planner_v4, Phase E tool/payload description
  text, all briefs.
- fast-worker: Phase F spec flow-back + deferred.md drafts (lead-reviewed).

## Knowledge candidates (raw, for step 8)

- Codex jobs may git-revert uncommitted working-tree files outside their
  scope: the Phase B job clobbered uncommitted lead planner edits. Rule that
  held after: commit lead edits BEFORE launching any codex job; the
  "do not revert files you did not change" brief line + clean-tree discipline
  prevented recurrence in D/E.
- Adding a required field to a wire model breaks every explicit constructor —
  including the few-shot EXAMPLE_RESPONSE inside the prompt module (import-time
  failure). The mechanical example carriage is part of the rider's cost;
  budget it into the brief (and never solve it with a pydantic default: strict
  structured-output schemas want all fields required).
- Refine-replay round 3 regressed vs round 2 (single-sample mini variance +
  an over-specific present-tense rule): the loop's revert-not-iterate exit is
  load-bearing; more words is not more control.
- The specification-vs-finding boundary (TIDieR territory) is ICF's real
  quality frontier — protocol descriptions masquerade as delivery_process on
  Methods-heavy primary studies; the deferred intervention_specification
  schema candidate is where that content actually belongs.
- Shared roll-up projection helpers must carry the SHARED top-level keys
  (selected/basis) into per-profile views — downstream base-count readers
  treat the projection as the old flat object. (Superseded same slice: the
  owner removed old-shape tolerance entirely; the surviving lesson is that
  per-profile projections still need the shared keys merged in, which group's
  loader now does inline.)
- pdftotext-based probe segments produce ~10% qv "normalised" (not exact)
  matches and a few failures from ligatures/hyphenation — probe-side artefact,
  not a prompt or qv defect; the live pipeline chunks from the ingest parser.
- group_facet_v1 on gpt-5.4-mini reliably fails partition validation
  (duplicate value ids, 4/4 attempts incl. repairs) at 184 distinct facet
  values — kind-spanning membership doubles the value list, so Slice C's
  facet redesign must treat value-list scale as a first-class constraint
  (batching or id-scheme change), not a retry problem.
- The 012 "cross-schema reference-mediated linkage" deferred entry was
  discharged by this slice's membership bridge (flagged by the flow-back
  draft as a lead call, folded into the deferred.md sweep).

## Review findings (step 7, 2026-07-13)

Stack: contract verifier (pinned Opus, fresh) · security auditor · Codex
adversarial (family flip: Codex anchored the lead-authored prompt surfaces;
Claude lanes anchored the Codex-written product code) · `/code-review medium`
(8 scoped finder angles + 1-vote verify) · lead live-trace lane (dev-DB
claims re-queried; Langfuse-only claims checked via persisted provenance).
`make verify` green before and after fixes (1272 → 1273 tests).

**Live-trace lane (lead):** every dev-DB claim above re-verified by direct
query — ICF 203 with the exact context_type breakdown, claim_basis 203/203,
setting 119, pooled 4; the 48 IOF `setting` values all carry the single
live-run timestamp (0 backfilled among 3,318 pre-existing NULL rows); the
grouping failure's cause is **persisted**, not trace-only
(`rejection_reasons: ["partition: duplicate id v126", "repair: duplicate id
v139"]`) with the per-kind residual `{icf: 203, iof: 130}` live — the 013
trace-only-diagnosis corollary holds; the build's root-cause stands and the
Slice-C facet-redesign input is confirmed, not a 021 defect.

**Adopted (fixed in-stack, commit follows):**
1. **Amendment sweep missed `synthesise.py`'s flat-row fallback** (finder
   removed-behavior lane + security INFO, convergent; verifier CONFIRMED):
   `_extraction_profile_ids` still silently returned `{IOF_PROFILE_ID}` on a
   pre-021 flat row while group raised loud — a flat row reached synthesise
   as an internally inconsistent run (substrate loaded IOF findings,
   `query_findings` reported the kind unavailable). Fixed: synthesise raises
   `corrupt_reference` (mirroring group), `_load_extraction_docs` likewise
   fail-closed; five test fixtures reseeded to the per-profile shape; pure
   test pins the raise.
2. **`query_findings` kind-specific filters failed open on the
   omitted-`kinds` default** (Codex adversarial #5, unique catch; verifier
   CONFIRMED): `{"context_type": "barrier"}` with `kinds` omitted returned
   ALL IOF findings unfiltered alongside ICF barriers — rubric item 11
   violation. Fixed: a kind-specific filter now requires kinds to name
   exactly its own kind (omission or both-kinds is a loud tool error); tool
   description updated to match; tests pin omitted/both-kinds rejection.
3. **Grouping `extraction_base` under-reported the kind-spanning base**
   (Codex adversarial #6; verifier CONFIRMED, no functional readers —
   provenance fidelity only): the persisted base claimed profile
   `eb_iof_base_v1` / findings_total 130 while `finding_set.size` was 333.
   Fixed: `extraction_base.profiles` now carries every extracted profile's
   fingerprint + counts (profile-set mismatch between counts and provenance
   is a corrupt reference); shape test updated + kind-spanning pin added.
4. **Vetter fail-open was invisible at run level** (security LOW): a judge
   failure persisted findings unfiltered with only a per-profile count.
   Fixed: `vetting_failed` promoted to a run-level flag (mirrors
   `extraction_failures`); test asserts the flag.

**Declined (recorded reasons):**
- Sequential IOF→ICF DB loads in `_load_findings` and per-call list rescans
  in the findings reader (efficiency lane; verifier: negligible vs
  LLM-dominated wall-clock).
- Migration CHECK strings duplicated vs schema.py constants (contract
  verifier NOTE; standard immutable-migration practice, drift guarded by
  test_icf_migration).
- Codex #1 (specification-shaped delivery_process leakage): convergent with
  the build's own eval-blind pin — already bounded by flag-not-drop, the
  known-gap line above, and the deferred `intervention_specification`
  candidate; no new action this slice.
- Codex #3 (claim_basis drift risk): the round-2 hedged-commentary clause is
  the shipped mitigation; residual measurement belongs to the eval slice's
  ground truth by the contract's honesty pin.

**Deferred (→ deferred.md, step 8):**
- Two-profile extraction runs strictly sequentially (~2× extract wall-clock
  on both-profile runs); parallelising needs a second DB connection or
  restructured memo/write phases — real but non-trivial (efficiency lane,
  verifier-confirmed mechanism).
- ICF-side plumbing clones IOF (backends, vetter scaffolding, dedup loops,
  per-kind literals in group/facet_values/synthesis_tools) — 19 convergent
  cleanup/altitude candidates across three lanes; consolidation deliberately
  rides the third-schema slice (deferred.md already pins "a third schema
  adds a kind section + filters"; the candidates sharpen that entry's cost).
- Control-character scrubbing asymmetry: model output is NUL-scrubbed only,
  while directives get `has_control_character` (security LOW,
  defense-in-depth).
- `claim_basis` null cannot distinguish "indeterminate after reading" from
  "not attempted" (`not_extracted` covers both — Codex #4); a coverage-
  vocabulary refinement for the eval slice / schema-candidate ladder.
- Planner two-profile narrowing is discretionary, not prompt-decidable in
  edge intents (Codex #2); an over-narrow planner silently drops ICF — eval
  slice's intent set should probe it.

**Flagged deviations — all five explicitly re-examined:** 1 (wire-model
default removal), 2 (shared-keys projection fix — now generalised to all
profiles by adopted fix 3), 3 (31-vs-30 replay overage, honest disclosure,
no coverage loss), 4 (ICF-only unsupported, explicit compile error + seam)
— **confirmed as-is**; 5 (owner amendment) — **contested in part**: the
sweep was incomplete (adopted fix 1); otherwise confirmed against the code.

**Clean lanes:** conventions, line-by-line, cross-file tracer — no findings.
Security: 0 critical/high/medium; prompt fencing, SQL construction,
fail-closed validators, secrets, resource caps all explicitly clean.
Contract verifier: no MAJOR; all 16 rubric items hold (item 8 completed by
this stack; items 14/15 hold with disclosed documentary/live-evidence
bounds; M1/M2 = the disclosed replay overage and grouped-run-carriage
limitation, both already recorded above).

**Fake-done check on the in-stack fixes:** no tests weakened — fixture
reseeds made seeds *stricter* (real per-profile shapes); all new guards are
raises, not fallbacks; `make verify` green (1273 tests, +1 net).

## Public safety

Probe summaries above are public-safe (titles + counts + short claim
fragments from openly-licensed docs; licences recorded). Raw traces in
Langfuse only. No secrets in evidence files.

## Deferred work

See deferred.md sweep (Phase F): ICF facet grouping · dimension promotion ·
downstream consumers · UNION view · hybrid dimension search · schema-candidate
ladder · companion-document seam · ICF-only composition.
