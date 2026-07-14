# Task contract: 022-synthesis-refinement — Synthesis Refinement

Slice C of the owner-adjudicated pre-eval sequencing (2026-07-12): the last
schema/composition slice before the eval slice. Shipped as **one slice, two phases**
(owner call, 2026-07-14 — the adjudicated shape stands; no split).

> **Status:** drafted. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: expected (multi-facet design).

## Goal

Two things, one slice:

**Phase 1 — multi-facet grouping.** One `group` run themes the findings across
*several* facets at once (in-component fan-out — owner shape, 2026-07-12), so one
synthesis reads intervention-, outcome- and implementation-context lenses together
instead of the current one-facet-per-run limit (the 013 live run's motivating hole:
the outcome facet's 13 healthy groups were structurally invisible to a synthesis
referencing the intervention facet's 0). This is also where ICF earns its facet:
grouping BY `context_type` (barrier / mechanism / condition), the 021 seam.

**Phase 2 — cost + surface.** Quality-neutral cost work on the synthesis loop, so the
eval slice scores a launch-plausible config, not the $15.45/run shape (2026-07-11
anatomy: writer turns ~74% — 30 × ~93k input; repair ~21% — full-transcript resends;
prompt cache only 24% on a strictly-growing transcript). Plus the writer/steer surface
items the owner confirmed: read-tool scoping plumbing, the pre-synthesise steer point,
the id-carrying repair schema, and the screen-confidence boost gate.

## Deliverable

One PR to `dev` landing: the multi-facet `group` component (fan-out within one run,
facet at group grain — one `grouping_result` migration) on the **two-stage
clustering engine** (open discovery + batch-validated assignment — the value-list
scale fix; characterise refactored onto it, behaviour-preserving), facet-qualified
group ids through directive / `query_findings` / envelope, the **ICF claim-theme
facets** (barrier/enabler/mechanism), the **cross-kind UNION read view** as the
loader's read surface, the bounded **ICF `context_label` rider** (`icf_v2`); and the
phase-2 cost/surface set under **one** writer prompt-version bump
(`synthesise_section_v6`) with replay evidence and a before/after cost measurement on
the cache-discounted curve. Spec flow-back (components §8/§9, data-model) +
deferred.md discharge/narrowing + an ADR for the multi-facet design.

## Read first

- `docs/knowledge/facet-partition-value-list-scale-limit.md` — **required design
  input**: `group_facet_v1` on gpt-5.4-mini emits duplicate value ids at ~184 distinct
  facet values (4/4 live attempts, honest degradation to all-ungrouped). Kind-spanning
  membership doubles the list. The redesign must bound the per-call value list
  (batched partitioning / hierarchical merge / duplicate-proof id scheme) — a
  first-class constraint, not a retry problem.
- `docs/deferred.md` — § Group (facet seams, large-corpus grouping, agent-authored
  directive), § Synthesise (pre-synthesise steer point · writer read-tool scoping ·
  018's A/B-gated writer-envelope metadata queue · unspanned-lane coverage half ·
  id-carrying repair schema), § Extract/ICF (ICF facet grouping · UNION view · hybrid
  dimension search — both "decide at the Slice C gate"), the multi-facet grouping
  entry under capability-run orchestration (~line 1079 — the five recorded design
  questions), the citation-context char clamp entry (~line 489), retrieval-boost
  grammar v2 (~line 328), `effect_basis` judge-envelope candidate (~line 727),
  screen-confidence multiplier grammar (~line 1110).
- [EB components](../../specs/capabilities/evidence-base/components.md) §8 group, §9
  synthesise — kind-spanning membership is an inherited requirement of the redesign.
- [data-model](../../specs/system/data-model.md) § findings layer — hybrid-queryable
  dimensions (the committed intervention/outcome indexing), UNION-view seam,
  presentation-grain note.
- [prompting doctrine](../../specs/system/prompting.md) — binds all phase-2 prompt
  work: versioned bumps, refine-replay loop (≤3 rounds/surface), cache-prefix layout
  rules, **cost judged on the cache-discounted curve** (the 31%-tokens/64%→23%-cache
  lesson), provider-neutral caching (no OpenAI-specific coupling — Bedrock constraint),
  and the coupled-readers rule (a group-semantics change MUST sweep the planner prompt).
- `docs/tasks/021-icf/contract.md` — pattern precedent; its gate decisions 6–8 are
  pinned context (unified `query_findings`, kind-spanning membership).
- Owner steer, pre-eval plan (2026-07-12): **reopened rulings are agenda items** —
  earlier deferrals (grammar v2, judge-envelope clamp, unspanned coverage) don't bind;
  decide at this gate. Select-at-standard regrade moved OUT to 019 (done); this slice
  keeps the screen-confidence boost gate + the cost-work wall-time band re-measure.
- Code spine: `group.py` + `facet_values.py` + `facet_grouping.py` (partition
  machinery, `FACET_VALUE_CAP`, `GROUPING_FACETS`, `FacetValueRecord` — the unit
  projection the engine generalises), `characterise.py` / `grouping.py`
  (`_discover_themes` + batched assignment — the two-stage shape precedent the
  engine adopts), `schema.py` (`grouping_result` —
  `facet` column, `ck_grr_facet`, `uq_grr_scope_run`, `fk_synr_grouping`),
  `synthesise.py` (grouping payload read, `group_ids`, `groups_unsectioned`),
  `synthesis_tools.py` (`query_findings` group filter, `search_chunks`, tool returns),
  `grounding.py`/`grounding_judge.py` (repair path, judge envelope), `orchestration_plan.py`
  (depth table, directive compile), `planner_prompt.py` (coupled reader).

## Scope / Out of scope

**In — Phase 1 (multi-facet grouping):**

1. **In-component facet fan-out.** The grouping directive names a facet **list**; one
   `group` run clusters the (kind-spanning) finding set once-loaded, **per facet —
   separate calls per facet, never one call spanning facets** (owner-confirmed,
   2026-07-14). One run row; synthesise keeps **one** grouping-run reference
   (`fk_synr_grouping` untouched). This dissolves the recorded multi-run design
   questions (reference shape, share-one-extraction rule, capability-run-entity
   dependency) by construction — record that in the ADR.
2. **Facet moves to group grain** (🛑 schema gate — decision 1): each group carries
   its `facet`; the row-level `facet` column + `ck_grr_facet` are replaced by the
   run's facet list (provenance) + per-facet payload keys. One migration on
   `grouping_result`. `uq_grr_scope_run` stays (one row per scope+run).
3. **Facet-qualified group ids** — labels collide across facets; ids become
   facet-qualified everywhere they travel: directive `group_ids`, `query_findings`
   `group_id` filter, section assignment, `groups_unsectioned`, envelope carriage.
   The id scheme is co-designed with the scale fix (duplicate-proof ids serve both).
4. **The two-stage clustering engine — the scale fix and the machinery convergence,
   one decision** (🛑 design decision 2; owner-settled direction, 2026-07-14).
   `group` adopts the **two-stage open-discovery / validated-assignment shape**
   (characterise's proven split, the owner's recorded candidate in deferred.md
   § Group): stage 1 discovers groups openly (labels + descriptions — never an
   exhaustive id list, which is exactly the one-call capacity cliff that produced
   duplicate ids 4/4 at ~184 values); stage 2 assigns every unit in small batches,
   **validated against the deterministically-known unit list** (no fabricated ids,
   no double assignment, unplaced units land in the counted residual — the
   exhaustive-assignment honesty everything downstream leans on; discovery stays
   open, validation binds assignment, per the owner's clustering model). The engine
   is parameterised by **unit projection**: a value facet's unit = the normalized
   value string + counterparts (today's `FacetValueRecord`); a claim-theme facet's
   unit = the claim's prose. Components stay distinct — characterise and group keep
   their own substrates, gates and consumers; the *engine* is shared or
   shape-identical (ADR records the boundary). `FACET_VALUE_CAP` survives as the
   fail-closed input guard; the per-call bound becomes an internal batch size.
   **Characterise refactors onto the shared engine in this slice** (owner call,
   2026-07-14) — behaviour-preserving only: characterise's prompt surfaces stay
   byte-identical (no version bumps there), its outputs/records unchanged,
   regression-covered; the refactor is code-level convergence, never a
   characterise redesign. **Per-unit context payloads are built and ON by
   default** (owner call, 2026-07-14), generalising the existing counterpart
   mechanism (a value facet's units already carry up to `COUNTERPART_CAP` paired
   reference surfaces): bounded char-capped source snippets per unit, id-keyed
   data records under the standing data/instructions separation, **source content
   only — never intent** (the facet-relative recomputability pin holds).
   Enrichment is pin-or-revert on build-time replay evidence (the refine-replay
   loop, ≤3 rounds — not deferred to evals); known risks the replay checks:
   context anchoring (clustering by snippet topic instead of value identity) and
   discovery-stage dilution at full-list scale. Full calibration stays eval work.
   **Granularity is a named design input** (owner Langfuse observation,
   2026-07-14): the shipped one-call partition over-fragments — too many
   too-granular groups. The exhaustive-partition framing is a plausible cause
   (every value must land somewhere in one response, so singleton-ish groups
   emerge); open discovery removes that pressure. Steering (owner-shaped,
   2026-07-14 — corpus sizes vary too much for an absolute target): a
   **corpus-relative numeric ceiling, never an absolute target** — a bound
   expressed as a function of unit count (ratio pinned at plan time), computed
   per run in code and injected into the discovery prompt as that run's number;
   **no lower target** (a corpus with three genuine themes gets three groups);
   direction carried by qualitative guidance ("a group is a recurring pattern
   across sources, not a restatement of one value"). Never fixed by catch-all
   buckets (`FORBIDDEN_GROUP_LABELS` stands) or code-side forced merges —
   coarseness is asked for in discovery, honesty stays in assignment. Replay
   evidence must show granularity behaviour across **differently-sized pinned
   inputs** against the observed live over-fragmentation, not just id-integrity;
   ratio calibration is eval work.
5. **Facet vocabulary this slice** (decision 3 — **SETTLED: build**, owner
   2026-07-14): `intervention` / `outcome` / `population` (existing value facets,
   now running on the engine) + **claim-theme facet(s) scoped by `context_type`**
   (e.g. `barrier_theme`): discover themes across the type's claim texts, assign
   every claim — the lens that delivers the promised payoff ("planning delays
   recur as a barrier across heat-pump programmes" backed by a validated group).
   On the item-4 engine this is a second unit projection (claim prose; known
   list = claim ids; scale story = claim count, 203 live), not new machinery.
   Context: ICF stores no short open-vocabulary content values (deliberate 021
   call: no extraction-time canonicalisation) — the content is `claim` prose
   scoped by the closed `context_type` enum, so "what distinct barriers/mechanisms
   were extracted" is claim-theme clustering, not value-string partitioning.
   **The high-value trio only this slice** (owner call, 2026-07-14):
   `barrier_theme` / `enabler_theme` / `mechanism_theme`; the remaining four
   `context_type`s are a config addition later (same engine, same projection —
   recorded in deferred.md, not machinery).
   **ICF `context_label` rider (owner, 2026-07-14 — reopens and supersedes the
   earlier rejection; the 021 setting-rider shape):** one nullable Text column on
   `implementation_context_finding`, **strictly source-named** — filled only when
   the source itself provides a short name for the claim's theme (a subheading, a
   named barrier in the source's own table); null otherwise, **never
   extractor-authored summarisation** (authorship stays with the source — the
   line that distinguishes it from the rejected free-label shape; adherence is a
   named ICF-vetter flag class). `icf_v1 → icf_v2` fingerprint bump (ICF's own
   domain — IOF memos untouched), one prompt-rule block in `extract_icf_v2`,
   `field_coverage` per the nullable-field pattern; v1 rows read "not recorded
   under icf_v1" — no backfill. **Nothing else rides the bump.** Reasoning
   corrections recorded for the ADR: cross-source naming variance was never the
   objection (value clustering absorbs it — same as intervention/outcome);
   clustering-noise dissolves with claim prose riding as unit context; and
   pre-ground-truth is the CHEAP fingerprint moment (the pre-eval sequencing
   criterion itself) — the eval slice authors ICF ground truth next, so the field
   gets ground-truthed alongside the rest, which is exactly why it lands now or
   never cheaply. Readers: grouping unit context now; the finding explorer at the
   web-app slice (the data-model presentation-grain note).
   (A bare deterministic partition BY the seven-value enum is not a facet — that
   read surface already exists as `icf_context_type_count`; named here so nobody
   ships it as one.) Cross-kind clustering on the shared-reference facets is
   **already built** (021 membership bridge) and owner-ratified 2026-07-14: the same
   document's IOF and ICF rows naming one intervention normalize to one value
   record with kind-spanning finding ids; ICF rows with null `outcome` land in the
   outcome facet's counted `no_value` residual, never force-joined. Which facets a
   given run requests stays orchestrator-discretionary; the deep-depth default
   facet set is a plan-time constant (named in the plan, not silently compiled).
6. **Per-facet honesty** (🛑 decision 4): per-facet residuals, per-facet CAP
   accounting, per-facet `groups_unsectioned`; and **per-facet failure isolation** —
   flag-not-drop argues one facet's partition failure lands an honest per-facet
   failure row (rejection reasons persisted, the 013 lesson) while sibling facets
   survive, not all-or-nothing. The gate confirms this shape.
7. **Cross-kind UNION read view** (decision 5 — **SETTLED: build**, owner
   2026-07-14): the recorded seam whose named first reader is this slice's
   cross-schema grouping. The multi-facet loader reads through it (retiring the
   direct two-table read), making it the one shared-reference read surface over
   both finding tables — the improved reader for anything downstream that queries
   across kinds.
8. **Hybrid dimension search over finding reference values — build-or-defer**
   (🛑 decision 6): the data-model's committed intervention/outcome dimension
   indexing (ICF's source-named values co-ride free by construction), recorded for
   decision "on the Slice C contract agenda, alongside the writer's retrieval-surface
   rework". Interacts with item 12 (scoped `search_chunks` may be the cheaper way to
   reach the same behaviour).

**In — Phase 2 (cost + surface; ONE writer prompt bump, `synthesise_section_v6`):**

9. **Cache-prefix engineering** — the biggest quality-neutral lever (24% hit rate on
   a strictly-growing transcript). Deterministic append-only prefix layout per
   prompting.md (stable instructions first, tagged data, task restated last),
   provider-neutral (suits OpenAI automatic + Bedrock `cachePoint`; no
   `prompt_cache_key`-class coupling). Measured on the cache-discounted curve.
10. **Repair-input scoping** — repair calls receive the failing claims + their cited
    chunks, not the full transcript resend (~21% of run cost today). Interface
    shaped so the deferred re-gather repair plugs in later without rework.
11. **Id-carrying repair schema** (013 seam) — replacements carry the failing claim's
    id, validated against the failing set; kills the positional-binding fragility.
    Rides the same prompt bump.
12. **Tool-return hygiene** — chunk dedup across turns (the writer re-reads what it
    already saw) + the character clamp at **tool-return** surfaces, windowed around
    the relevant span. The **judge envelope stays unclamped** unless the owner
    reopens it (agenda item B).
13. **Writer read-tool scoping plumbing** — `search_chunks` gains optional
    fail-closed scope filters (tags · doc ids · facet-group members · evidence
    types), validated against the closed vocabularies like the directive boosts.
    Plumbing + minimal tool-description text this slice; WHEN-to-scope prompt
    guidance is post-eval tuning (lead-only, replay-evidenced when it comes).
14. **Pre-synthesise steer point** — the owner-confirmed seam: after group /
    characterise, surface proposed sections + discovered themes/facet groups; the
    response compiles into the **existing** fail-closed `context["synthesis"]`
    directive (sections + group_ids + retrieval_boosts — its first author).
    Parameter authoring on built machinery; mode-governed pause UX stays deferred
    (plan-as-object seam).
15. **Screen-confidence retrieval boost — this contract is its gate** (🛑 decision 7):
    the pre-decided grammar (linear clamped functional multiplier, product clamped
    [0.1, 10], steerable-never-baked) wired as a directive boost over screen
    confidence. Constants plan-pinned; calibration is eval-slice work.
16. **Riders:** `lookup` widening to screening rows · the cost-work wall-time band
    re-measure (D1's ~10–20 min band re-measured on the post-phase-2 config, so the
    rehearsal numbers stay honest).

**Agenda — owner-reopened rulings, decided at this gate (🛑 decisions A–E; "don't
inherit the deferral" is the owner's own instruction):**

- **A. Grammar-v2 boundary vs writer tag-scoping** — does item 13 subsume
  retrieval-boost grammar v2's tag-scoping half (leaving only the confidence
  multiplier, now item 15), retiring the separate grammar-v2 slice — or does grammar
  v2 stay its own eval-gated slice?
- **B. Judge-envelope char clamp** — keep the judge envelope unclamped (013 call) or
  clamp it too. Any judge-envelope change binds to 018's verification-grade A/B
  protocol (replay the same claim set through both envelopes, hand-inspect flips).
- **C. Unspanned-lane coverage half** — build the dedicated judge call for
  judge-skipped blocks now, or keep it eval-slice work (flag-volume calibration
  lives there). 018 already closed the honesty half (`unspanned_lane_skipped`).
- **D. 018's dangling writer-envelope metadata A/B queue** — run the first queued
  field (author institutions) under the A/B protocol in this slice, or explicitly
  re-defer. Contracted in 018, never run; silent inheritance is not an option.
- **E. `effect_basis` as judge-envelope candidate** — adopt under the same A/B
  protocol, or re-defer to the eval gate. (Pairs with B: both are judge-envelope
  changes; adopting either forces one re-baseline event.)

**Out:**

- Bedrock migration (post-eval by design; standing constraint binds: nothing new
  couples to OpenAI-specific API surface — including the caching work).
- Retrieval-boost grammar v2 beyond decision A's boundary call.
- Steering-mode / plan-as-object machinery (the steer point lands as directive
  compile, not pause UX) · facet-theme promotion (canonical groupings — the
  entity-resolution bar stands) · multi-execution fan-in (dissolved for grouping by
  the in-component shape; the general seam stays deferred).
- Re-gather repair (item 10 shapes the interface only) · corpus-scale retrieval /
  index-backed `retrieve` · cross-encoder reranker (pass-through stands).
- Prompt tuning beyond the one versioned bump; all plan-pinned constant calibrations
  (eval work); the evals themselves.
- The 19 ICF cleanup/altitude candidates (deferred to the third-schema slice).
- Two-profile extraction parallelism (extract wall-clock — eval-slice cost-axis
  input, not this slice's surface).
- Demo surface (C4, codex lane) · anything web-app.

## Constraints & approval gates

- **Schema** 🛑: two approved migrations — the `grouping_result` migration
  (decision 1) and the ICF `context_label` rider column (owner-approved
  2026-07-14, `icf_v2`). Any further table change is a stop condition.
- **Prompt-bearing surfaces are lead-only** (AGENTS.md): `synthesise_section_v6`,
  the group prompt surfaces (discovery + assignment — supersede `group_facet_v1`),
  the claim-theme facet prompts, the planner-prompt sweep (coupled-readers rule —
  multi-facet changes group semantics the planner describes), steer-point compile
  text. Every change bumps its version string; replay-evidenced.
  **Characterise's prompt surfaces are byte-identical this slice** — the engine
  refactor is code-level; a characterise prompt change is a stop condition.
- **Egress unchanged**: existing approved OpenAI routes only; no new backends.
- **No OpenAI-specific coupling** in the cache work (Bedrock constraint).
- Upgrades-never-invalidate: the group prompt bump changes future grouping runs
  only; existing `grouping_result` rows are readable as-written (the migration must
  keep old rows queryable or migrate them honestly — plan decides which, gate
  approves).

## Public / private boundary

Committable: contract/rubric/plan/ADR, code, migrations, prompt text, spec flow-back,
replay *summaries* and cost figures. Private: raw model transcripts, live-run
document text, traces, credentials. Cost anatomy numbers ($, token counts, cache
rates) are public-safe.

## Model route

OpenAI under approved controls (Bedrock post-eval). Prompt-bearing changes (all
lead-authored): `synthesise_section_v6` (cache layout · repair schema · scoping tool
description), the group discovery + assignment prompts (superseding
`group_facet_v1`), the claim-theme facet prompts, `extract_icf_v2` (the
`context_label` rule block — nothing else changes in that prompt), the ICF-vetter
label flag class, planner prompt sweep for group-semantics vocabulary. Judge
prompt/envelope changes only via decisions B/E under the A/B protocol.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no facet machinery beyond what this slice's readers use.
- **Flag, don't drop** — per-facet failures are honest rows, never silent absences;
  rejection reasons persist (the 013/021 diagnosability property).
- **Honest absence** — per-kind, per-facet availability stays visible.
- Deferred seams stay seams in [docs/deferred.md](../../deferred.md).
- Quality-neutral means **measured** neutral: phase-2 changes are judged on replay
  evidence, not asserted.

## Stop conditions

Halt and escalate when: a second schema change beyond the `grouping_result` migration
appears · any judge-envelope change is tempted outside decisions B/E · the cache work
tempts provider-specific API surface · scope grows past this contract (e.g. re-gather
repair, pause UX, canonicalisation) · a spec is wrong enough to block · budget spent.

## Acceptance checks

- `make verify` green (test · typecheck · lint · build · okf-validate).
- Deterministic: migration up/down; facet-qualified id collision tests; per-facet
  residual/failure-row invariants; repair-id binding validation; scope-filter
  fail-closed tests; dedup/clamp unit tests.
- **Live checks (contract-time pin — scoped, not full e2e):**
  1. Live grouped run at the previously-failing scale (both-profiles corpus,
     ≥184 distinct values) — healthy partitions, no duplicate-id rejection; the
     knowledge doc's failure mode demonstrably closed.
  2. Live multi-facet run (≥2 facets incl. `context_type`) — per-facet groups +
     residuals land; synthesise consumes both lenses via one grouping ref.
  3. One cheap full-chain smoke (mandatory-spine composition).
  4. **Cost re-measure**: same-shape synthesis run vs the $15.45 / 24%-cache
     baseline — report $, cache hit rate, and the wall-time band (rider 16), on the
     cache-discounted curve.
- Replay evidence per bumped prompt surface (refine-replay loop, ≤3 rounds,
  pin-or-revert); A/B verdict-flip inspection if B/E adopt a judge-envelope change.

## Verification evidence expected

`verification.md` with: exact commands + run/trace ids for the four live checks, the
cost before/after table, replay-round records per surface, migration evidence
(up/down + old-row readability), diff summary, public-safety confirmation, gaps →
deferred.md.

## Risk tier & review focus

**Tier 3** — schema migration + prompt-bearing surfaces + untrusted-document text
flowing through tool returns and repair inputs. Review stack per tier (contract
verifier · code review · security lane · adversarial · simplification), within the
review-stack economy pins (medium effort, one security lane, per-angle diff scoping —
and data files excluded from review diffs). Focus: partition-exactness invariants
under the new scale machinery · facet-id collision/fail-closed discipline ·
cost-change measurement honesty (cache-discounted, not raw tokens) · repair binding
correctness · scope creep toward the Out list.

## Decisions for the owner at this gate

1. **Facet-at-group-grain migration shape** (schema 🛑) — facet list in provenance +
   per-facet payload keys, row-level `facet` column retired; old rows' readability
   posture.
2. **The two-stage clustering engine — SETTLED in full (owner, 2026-07-14)**: open
   discovery + batch-validated exhaustive assignment, parameterised by unit
   projection; **characterise refactors onto the engine this slice**
   (behaviour-preserving, prompts byte-identical); **context payloads built and on
   by default** (bounded, source-content-only, build-time replay pin-or-revert).
   Residual for the gate: what `FACET_VALUE_CAP` becomes.
3. **First ICF content facet — SETTLED in full (owner, 2026-07-14)** — claim-theme
   facets on the item-4 engine, **high-value trio only**: `barrier_theme` /
   `enabler_theme` / `mechanism_theme` (remaining four context_types = later
   config, deferred.md). **Plus the `context_label` rider** (owner, same day,
   reopening the earlier rejection): nullable, strictly source-named, `icf_v2`
   bump, nothing else rides — the 021 setting-rider precedent. Residual for the
   plan: the deep-depth default facet set.
4. **Per-facet failure isolation** — honest per-facet failure rows (proposed) vs
   all-or-nothing.
5. **Cross-kind UNION view — SETTLED: build (owner, 2026-07-14)** — the multi-facet
   loader reads through it; the shared-reference read surface over both finding
   tables.
6. **Hybrid dimension search** — build or defer, decided against item 13's scoped
   `search_chunks` alternative.
7. **Screen-confidence boost** — gate the pre-decided grammar in; constants
   plan-pinned, calibration eval-owned.
8. **Agenda A–E** — grammar-v2 boundary · judge-envelope clamp · unspanned coverage
   half · 018 metadata A/B queue · effect_basis judge-envelope candidate.
