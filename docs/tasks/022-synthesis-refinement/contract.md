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
facet at group grain — one `grouping_result` migration), facet-qualified group ids
through directive / `query_findings` / envelope, the per-call value-list scale fix
(live-proven mandatory — see Read first), the ICF `context_type` facet; and the
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
  machinery, `FACET_VALUE_CAP`, `GROUPING_FACETS`), `schema.py` (`grouping_result` —
  `facet` column, `ck_grr_facet`, `uq_grr_scope_run`, `fk_synr_grouping`),
  `synthesise.py` (grouping payload read, `group_ids`, `groups_unsectioned`),
  `synthesis_tools.py` (`query_findings` group filter, `search_chunks`, tool returns),
  `grounding.py`/`grounding_judge.py` (repair path, judge envelope), `orchestration_plan.py`
  (depth table, directive compile), `planner_prompt.py` (coupled reader).

## Scope / Out of scope

**In — Phase 1 (multi-facet grouping):**

1. **In-component facet fan-out.** The grouping directive names a facet **list**; one
   `group` run partitions the (kind-spanning) finding set once-loaded, per facet.
   One run row; synthesise keeps **one** grouping-run reference (`fk_synr_grouping`
   untouched). This dissolves the recorded multi-run design questions (reference
   shape, share-one-extraction rule, capability-run-entity dependency) by
   construction — record that in the ADR.
2. **Facet moves to group grain** (🛑 schema gate — decision 1): each group carries
   its `facet`; the row-level `facet` column + `ck_grr_facet` are replaced by the
   run's facet list (provenance) + per-facet payload keys. One migration on
   `grouping_result`. `uq_grr_scope_run` stays (one row per scope+run).
3. **Facet-qualified group ids** — labels collide across facets; ids become
   facet-qualified everywhere they travel: directive `group_ids`, `query_findings`
   `group_id` filter, section assignment, `groups_unsectioned`, envelope carriage.
   The id scheme is co-designed with the scale fix (duplicate-proof ids serve both).
4. **Value-list scale fix** (🛑 design decision 2): bound the per-call value list so
   the live-proven ~184-value failure passes. Candidate shapes: batched partitioning
   with cross-batch merge · hierarchical (discover-then-assign, weighing the recorded
   tail-discovery risk + partition-exactness invariant) · shorter duplicate-proof id
   scheme. `FACET_VALUE_CAP` semantics (fail-closed, loud) survive whatever lands —
   the cap may rise, never silently degrade.
5. **Facet vocabulary this slice** (🛑 decision 3): `intervention` / `outcome` /
   `population` (existing) + **the first ICF facet — whose shape is the decision**
   (owner probe, 2026-07-14). ICF stores no short open-vocabulary content values
   (deliberate 021 call: no extraction-time canonicalisation) — the content is
   `claim` prose scoped by the closed `context_type` enum. So "what distinct
   barriers/mechanisms were extracted" does NOT fit the value-string partition
   machinery. Candidates:
   - **(a) Claim-theme clustering scoped by `context_type`** (e.g. `barrier_theme`):
     discover themes across the type's claim texts, assign every claim — the lens
     that delivers the promised payoff ("planning delays recur as a barrier across
     heat-pump programmes" backed by a validated group). New machinery: a claim-text
     projection (prose, not value strings) and likely the characterise-style
     two-stage discover/assign split (the owner's recorded candidate, deferred.md
     § Group), designed against the tail-discovery risk and the partition-exactness
     invariant. Its scale story is claim count (203 live), distinct from the
     value-list limit.
   - **(b) No ICF-content facet this slice** — kind-spanning membership already
     puts ICF findings in intervention/outcome groups, and `icf_context_type_count`
     already validates type × intervention counts; claim-theme clustering
     re-defers explicitly.
   - (c) A short source-named ICF label field: **rejected, not open** —
     extraction-time canonicalisation plus a pre-ground-truth fingerprint
     invalidation.
   (A bare deterministic partition BY the seven-value enum is not a facet — that
   read surface already exists as `icf_context_type_count`; named here so nobody
   ships it as one.) Which facets a given run requests stays
   orchestrator-discretionary; the deep-depth default facet set is a plan-time
   constant (named in the plan, not silently compiled).
6. **Per-facet honesty** (🛑 decision 4): per-facet residuals, per-facet CAP
   accounting, per-facet `groups_unsectioned`; and **per-facet failure isolation** —
   flag-not-drop argues one facet's partition failure lands an honest per-facet
   failure row (rejection reasons persisted, the 013 lesson) while sibling facets
   survive, not all-or-nothing. The gate confirms this shape.
7. **Cross-kind UNION read view — build-or-defer** (🛑 decision 5): the recorded seam
   whose named first reader is this slice's cross-schema grouping. Build only if the
   multi-facet loader actually reads through it; otherwise re-defer explicitly with
   the honest reason (the loader already reads both tables directly).
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

- **Schema** 🛑: the `grouping_result` migration (decision 1) — the slice's one
  schema gate. No other table changes expected; a second one is a stop condition.
- **Prompt-bearing surfaces are lead-only** (AGENTS.md): `synthesise_section_v6`,
  the group partition prompt bump, the planner-prompt sweep (coupled-readers rule —
  multi-facet changes group semantics the planner describes), steer-point compile
  text. Every change bumps its version string; replay-evidenced.
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
description), group partition prompt vNext (facet fan-out · id scheme · batching),
planner prompt sweep for group-semantics vocabulary. Judge prompt/envelope changes
only via decisions B/E under the A/B protocol.

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
2. **Value-list scale design** — batched partition + merge vs hierarchical
   discover/assign vs id-scheme-only (or a combination); what `FACET_VALUE_CAP`
   becomes.
3. **First ICF facet shape** — claim-theme clustering scoped by `context_type`
   (new machinery, the payoff lens) vs explicit re-defer (kind-spanning membership
   + `icf_context_type_count` already serve the cheap half); a short ICF label
   field is rejected. Plus the deep-depth default facet set.
4. **Per-facet failure isolation** — honest per-facet failure rows (proposed) vs
   all-or-nothing.
5. **Cross-kind UNION view** — build (if the loader reads through it) or explicit
   re-defer.
6. **Hybrid dimension search** — build or defer, decided against item 13's scoped
   `search_chunks` alternative.
7. **Screen-confidence boost** — gate the pre-decided grammar in; constants
   plan-pinned, calibration eval-owned.
8. **Agenda A–E** — grammar-v2 boundary · judge-envelope clamp · unspanned coverage
   half · 018 metadata A/B queue · effect_basis judge-envelope candidate.
