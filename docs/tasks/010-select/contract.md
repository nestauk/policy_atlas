# Task contract: 010-select

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 2) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: 0006 (selection strategy + rationale record) — due at step 4.
>
> **Revision history:**
> - **rev 1** (2026-07-06): initial draft — deterministic stratified strategy,
>   budget + must-includes as scope-context parameters.
> - **rev 2** (2026-07-06, user-steered): the LLM-vs-deterministic question
>   adjudicated against the specs (components §6 realisation = *procedure*; the
>   reasoning belongs to the capability agent's just-in-time **commit**, which
>   *parameterises* the tool — plan-as-object § forecast-vs-commit). Adopted:
>   **selection directive** as a first-class facade argument (the future agent's
>   tool-call surface, designed for the agent-interaction architecture now) ·
>   **soft boosts/filters over columns + tags** (the scoping vocabulary — what the
>   tag layer was built for) · seams recorded (agent-authored directive at the
>   commit layer · `llm_assisted` strategy, eval-gated · the missing
>   **capability-run entity** spanning components). Rev 2.1 clarified the
>   directive-authoring seam as invocation-time (just-in-time, post-characterise).
> - **rev 3** (2026-07-06, user-decided): **generative LLM rerank pulled
>   in-slice** as `llm_rerank_v1` (decision 10) — 009 made the marginal cost small
>   (seam pattern, batching/validation/repair, injection posture, tracing all
>   exist; whole 009 live run ≈ $0.10). Cross-encoder relevance models
>   (Cohere-class, available on Bedrock) judged **more apt for `retrieve`** than
>   select — recorded at that seam, not this one. Gates grew (user-confirmed at
>   this gate): `ranking_backend` parameter · the **second product prompt surface**
>   (`select_rerank_v1`) + its generation egress · one spec flow-back (components
>   §6 select realisation: procedure → procedure with bounded generative rerank,
>   hard rules staying code-side).
> - **rev 4** (2026-07-06, user challenge: "is cosine matching appropriate here at
>   all?"): **embedding-cosine relevance cut.** By select time the semantic
>   dimension is spent twice (screening judged relevance; stratification grouped
>   semantically) — within-stratum cosine-to-intent discriminates weakly, and its
>   live role was only the fallback, which recency·tier·origin serves honestly.
>   The spec's relevance signal reads "embeddings / **screening**" — the screening
>   leg stands. Cuts with it: the intent-embed call (egress gate shrinks to the
>   rerank surface only), vector reads + cosine code, the max-over-units bias, and
>   null-relevance handling. Vectors' first reader reverts to `retrieve` as
>   designed; embedding-relevance-for-select recorded as a declined seam
>   (revisit only with rerank-quality evals). Rev 4.1 pinned the rerank basis:
>   envelope uniformly (title + abstract), never full text; the LLM ranks, never
>   selects.
> - **rev 5** (2026-07-06, user-caught gap): **full-text availability joins
>   select** — extract works on what select chooses, so the selection must know
>   and say how much of it has full text. `text_basis` enters the deterministic
>   composite (soft tilt toward `full_text`, flag-not-block — abstract-only docs
>   stay fully selectable), the bidirectional rationale carries per-doc
>   `text_basis` + per-stratum full-text shares, and a **`thin_full_text` trigger
>   flag** joins the steer-point signals (selected set's full-text share below a
>   floor — extraction-shaping, so the steer-point must see it). The rerank input
>   stays content-only (title + abstract + intent): metadata and tags are weighed
>   arithmetically or via directive boosts, never fed to the ranker — signals
>   stay attributable, never double-counted.

## Goal

Add **select** — EB component 6, the gate that opens the deep terminus. After
characterise has measured the corpus shape, select chooses the subset for Tier-1
extraction: **coverage-aware stratified selection over the run's characterisation
strata**, breadth-adaptive (the landscape has already measured breadth — stratify
across whatever strata exist; the budget sets how deep per stratum), guarding against
horizon scans collapsing onto a narrow top-k.

The slice ships **two strategies over one code-owned structure**. The structure —
stratification, breadth floor, budget arithmetic, must-include bypass — is
deterministic and identical under both. **`coverage_stratified_v1`** (the default and
the suite's path) is deterministic end-to-end: same inputs → byte-identical selection,
test-enforced. **`llm_rerank_v1`** (decision 10; the live skeleton path) replaces only
the *within-stratum ordering* with bounded, batched, schema-constrained judgment calls
— purpose-sensitive ranking with per-doc reasons, the repo's **second product prompt
surface** — degrading per-document to the deterministic composite (flagged, never
failed). No new dependencies; generation egress grows by this one bounded surface
(user-confirmed, rev 3).

The judgment select *does* need — which emphases matter for this intent and this
synthesis purpose — enters through the **selection directive**: a first-class,
declarative parameter surface (budget, must-includes, soft boosts/filters over
columns + tags, signal-weight emphasis) that steers the deterministic scan. This is
the spec's own split (plan-as-object § forecast-vs-commit): the **capability agent**
reasons and authors the directive at commit time; the **tool** executes it as an
auditable procedure. The agent layer doesn't exist yet — v3.0 sources the directive
from the scope context — but the facade signature is designed as the tool call that
agent will make, so its arrival is a parameter-authoring change, not a re-plumb.

Select writes **content, not presentation**: one run-scoped selection record carrying
the directive it executed and the **bidirectional rationale** the spec makes
mandatory — what was selected (why, per document) and what was not (aggregate
exclusion reasons + notable flagged exclusions). That rationale is exactly what the
pre-declared **deepening-selection steer-point** reads; this slice computes its
escalation-trigger *signals* now (as flags in the rationale and summary payload)
while the mode-governed *pause* machinery stays a recorded seam (plan-as-object).

## Deliverable

A PR on `task/010-select` → `dev` that:

- Ships `select.py`: the shared strategy-parameterised `select` function
  (*(candidates, signals, strategy, directive) → chosen subset + bidirectional
  rationale*, per the spec's tool contract) with two strategies —
  **`coverage_stratified_v1`** (deterministic, default) and **`llm_rerank_v1`**
  (decision 10); the **`SelectionDirective`** (first-class facade argument —
  budget, must-includes, column/tag soft boosts, weight emphasis);
  `SelectContext`; `select_scope(...)` — directive resolution → signal assembly →
  stratification → allocation → ranking → rationale → the `selection_result` row →
  the selection summary in `component.completed`.
- Ships the `RankingBackend` seam (mirroring `GroupingBackend`): protocol +
  `OpenAIRankingBackend` (batched structured scoring) + deterministic stub, and
  the **`select_rerank_v1` prompt** (lead-authored, versioned, recorded in
  provenance) — the slice's only prompt-bearing surface.
- Adds **one table — `selection_result`** — via one Alembic migration (gated
  change 1; table count 19 → 20), project-scope-guarded per repo discipline.
- Registers `"select"` in `COMPONENT_REGISTRY` (requires `evidence_scope_id`); wires
  `_run_select`; `run_harness` gains one optional **`ranking_backend`** parameter
  (defaults to the stub — no default egress; gated change 2). No embeddings use
  (rev 4).
- Extends `skeleton.py`: … characterise → **select**, rendering the selection
  summary (strata, per-stratum picks, exclusion aggregates, trigger flags).
- Records the deferred seams in `docs/deferred.md`; updates `tests/helpers.py`
  delete order for the new table.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [EB components §6 — select](../../specs/capabilities/evidence-base/components.md)
  — the component contract: stratified-over-clusters, breadth-adaptive, the signal
  list, must-includes as the one hard rule, bidirectional rationale, the shared-tool
  realisation. Also §5's cluster double-duty note (corpus shape *and* stratification
  basis) and §4's Tier-1 gating (extraction is gated by select).
- [EB capability](../../specs/capabilities/evidence-base/capability.md) — the
  deepening-selection steer-point (always log the rationale; escalation triggers;
  the strongest surface even in Minimal) and the cluster-persistence rule
  (clusters are **run-local** — select reads the *same run's* characterisation row).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) +
  [system provenance-grounding](../../specs/system/provenance-grounding.md) — the
  gap-provenance ladder: `not_selected` **never** licenses an absence claim; the gap
  select creates must stay visible as coverage, not silence.
- [System data-model](../../specs/system/data-model.md) — coverage states as gap
  provenance (`not_selected` is doc-level, screened-in-but-not-chosen); scoping as
  soft prior; origin drives default priority via scoping, not hidden re-weights.
- [System execution-orchestration](../../specs/system/execution-orchestration.md) —
  component realisation classes (select is pure "procedure"); `search` stays the
  only agent-invocable egress verb (select adds none).
- [docs/deferred.md](../../deferred.md) — the 009 seams this slice touches:
  steer-point pause (stays deferred), unclustered-as-stratum (lands here);
  pgvector/retrieval and the chunk vectors untouched (retrieve stays their first
  reader, rev 4).
- [009-characterise contract](../009-characterise/contract.md) — pattern precedent
  (run-scoped result row, project-scoped composite FKs, component wiring,
  edge-scope handling, honest failure).

**Code grounding (surveyed 2026-07-06):** 19 tables. `characterisation_result` is
per `(evidence_scope_id, run_id)` with `themes` JSONB (`themes[]` = name /
description / member_ids / size + `unclustered_ids`) and `coverage` JSONB carrying
base counts — select's stratification input, same-run. Cheap Tier-0 signals in
place: `origin`, metadata year, `source_appraisal_result` quality tier, screen
confidence, `text_basis`/`full_text_status`; titles + abstracts for the rerank ride
the same envelope reads characterise uses. `run_harness(conn, *, config, project_id, run_id,
provider, search_backends, document_fetcher, embedding_backend, grouping_backend)` —
`embedding_backend` already threads through `HarnessState`. Component wiring pattern:
registry entry → context dataclass `(scope_id, intent, context)` → `_run_scope_component`
→ `component.started/completed/failed`. The skeleton chain ends at characterise.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The selection structure is procedure — hard rules never leave code.**
   Stratification, the breadth floor, budget arithmetic, must-include bypass,
   exhaustive accounting: all deterministic, identical under both strategies, with
   stable ordering and deterministic tie-breaks (snapshot id). Under the default
   `coverage_stratified_v1` the whole component is deterministic end-to-end (same
   input → byte-identical selection row, test-enforced — this is the suite's
   path). `llm_rerank_v1` (decision 10) bounds its judgment to within-stratum
   *ordering* only, inside that structure — a spec flow-back records the
   realisation refinement (components §6: procedure → procedure with bounded
   generative rerank). Every signal stays cheap and **pre-extract** (titles +
   abstracts at most — never full text; that's extraction's side of the line).

2. **Relevance signal = the screening leg; embedding-cosine declined** (rev 4).
   The spec names relevance-to-intent via "embeddings / screening" — the
   **screening leg** lands: screened-in status is the base relevance judgment
   (it defines the candidate set) and screen confidence folds into the composite
   (honestly stub-constant today; it becomes discriminating when the LLM screen
   tool lands at its own seam).
   - **Embedding-cosine relevance was drafted (revs 1–3) and cut at the gate**:
     by select time the semantic dimension is already spent twice — screening
     judged every candidate relevant, and stratification grouped them
     semantically (the themes are the LLM's semantic read against the intent) —
     so within-stratum cosine-to-intent compares already-similar,
     already-relevant documents and discriminates weakly. Purpose-fit, the
     judgment that *does* discriminate there, is `llm_rerank_v1`'s job
     (decision 10). Cutting it also cuts the intent-embed call (the egress gate
     shrinks to the rerank surface), the vector-read/cosine code, its
     full-text-vs-abstract-only bias, and null-relevance handling.
   - The 009 chunk vectors stay untouched and unread here; their first reader
     remains `retrieve`, as designed (the ahead-of-reader exception stands
     unchanged). **Embedding-relevance-for-select is a declined seam** —
     recorded in `docs/deferred.md`, revisited only if rerank-quality evals show
     the fallback/deterministic ordering needs a semantic leg.
3. **Strategy mechanics: `coverage_stratified_v1` — breadth floor, proportional
   remainder, weighted within-stratum ranking.**
   - **Strata = this run's themes + `unclustered`** (a partition — assignment is
     single-theme-or-unclustered; the 009 contract pre-committed unclustered to
     "form their own stratum when select lands"). Select reads the **same run's**
     `characterisation_result` row; no row for `(scope, run)` → honest failure
     (clusters are run-local — a previous run's grouping is never silently reused).
   - **Allocation:** must-includes first (outside the budget — decision 4). Then
     every non-empty stratum gets **one slot** (the breadth floor — this is the
     anti-top-k guard) while budget remains, in deterministic stratum order (size
     descending, name); the remainder is allocated **proportionally to stratum
     size** (largest-remainder method — deterministic, sums exactly to budget).
     Budget ≥ candidates → select all (still recorded, with rationale).
   - **Within-stratum ranking (the deterministic composite):** a weighted
     composite over the normalised cheap signals — recency (year, bounded decay) ·
     light appraisal tier · origin/upload priority (`uploaded` favoured, per the
     spec's default-priority-via-scoping posture) · screen confidence (the
     relevance leg, decision 2) · **full-text availability** (`text_basis`, a
     soft tilt toward `full_text` — extract works on what select chooses;
     abstract-only docs stay fully selectable, flag-not-block, rev 5) — plus the
     directive's **soft boosts**
     (decision 4), folded into the same composite. Default weights are named
     constants pinned at the plan gate; the effective weights (defaults ⊕
     directive emphasis) are recorded in `selection_provenance`. Ties break on
     snapshot id. This composite is `coverage_stratified_v1`'s ordering **and**
     `llm_rerank_v1`'s per-document fallback (decision 10) — it always exists.
   - Publication-country stratification and study-geography/population diversity:
     **not built** — the spec itself marks them rough/cluster-approximated and
     properly post-extraction; recorded as the selection-diversity seam.
4. **The selection directive — the agent-facing parameter surface, designed for
   the orchestrator/sub-agent architecture now** (user-steered, rev 2). The
   reasoning select needs is intent- and purpose-dependent; the spec locates it in
   the capability agent's just-in-time **commit**, which *parameterises* the tool
   (plan-as-object § forecast-vs-commit; the facade principle). So the directive
   is a **first-class field of `SelectContext` / argument of the `select` facade**
   — the exact tool-call signature the future agent will author — not buried
   configuration. A declarative object (exact schema plan-pinned):
   - **`budget`** — Tier-1 slot count; default a named constant.
   - **`must_include_ids`** — the one **hard** rule: hard-includes bypassing the
     budget, never counted against it, never displaced; validated against the
     scope's screened-in set (an id outside it is a flagged, non-fatal rationale
     entry — `must_include_not_in_scope` — honest, not silently obeyed or dropped).
   - **Soft boosts/filters over columns + tags** — the data-model's **scoping
     vocabulary** ("queries over columns + tags alike; a soft retrieval prior"),
     which is what the tag layer was built for: predicates over Tier-0 columns
     (e.g. `primary_evidence_type`, `origin`, year ranges) and tag assertions
     (by `tag_type` / `tag` / optionally `asserted_by`), each carrying a weight.
     **Soft means flag-not-block**: a boost re-weights within the composite score,
     never excludes; a directive cannot manufacture a hard gate (must-includes
     stay the only hard rule). Unknown columns/tags referenced by a directive are
     flagged in the rationale, never fatal. Provider tags (009) give boosts real,
     live data to act on today.
   - **Signal-weight emphasis** — optional multipliers over the default weights
     (e.g. recency-heavy for a "latest evidence" intent).
   An **empty directive is the default**: the plain stratified scan. In v3.0 the
   directive is *sourced* from the evidence-scope `context` JSONB (user/plan
   authored; the skeleton demonstrates one) — no new `run_harness` parameter, no
   schema column — and when the capability-agent layer lands, the agent authors it
   directly at commit time: a parameter-authoring change, zero re-plumbing. The
   executed directive is recorded whole in `selection_provenance` (decision 5).
   The source/evidence **policy** signal (soft prior, never a gate) structurally
   cannot fire — no policy object exists in v3.0; recorded seam, not built.
5. **Persistence: one run-scoped `selection_result` row — selection is run-local.**
   Mirrors `characterisation_result`: one row per `(evidence_scope_id, run_id)`,
   recomputable, superseded by the next run, never canonical corpus state. Extract
   (the next slice) reads its run's row. `not_selected` remains **derivable**
   coverage state (screened-in minus selected) — no doc-level status column, no
   status writes; the findings-layer coverage vocabulary arrives with extract.
   Row: `strategy` · `budget` · `selection_provenance` JSONB (strategy version,
   the **executed directive recorded whole** + its source, effective weights,
   signal availability, rerank provenance where applicable — prompt version,
   model, batch size, fallback/retry counts) ·
   `selected` JSONB (per doc: pss id, stratum, signal scores, `text_basis`,
   selection reason — `must_include` | `breadth_floor` | `ranked`) · `excluded`
   JSONB (aggregate per stratum: counts by reason class — `budget_exhausted`,
   `ranked_below_cut` — plus **notable flagged exclusions** by name) · `flags`
   JSONB (the escalation triggers, decision 6) · `created_at`.
6. **The steer-point's trigger signals are computed now; the pause is not.** The
   capability spec pre-declares deepening selection as EB's one conditional
   steer-point. This slice lands its read surface: the bidirectional rationale
   (always logged) and the computed **trigger flags** — `large_stratum_excluded`
   (a stratum with zero selections above a size share), `must_include_conflict`
   (decision 4's validation flag; the user-nominated integrity signal),
   `thin_base` (screened-in below a floor — the screen thin-base trigger read at
   selection time), and `thin_full_text` (the **selected set's** full-text share
   below a floor — extraction-shaping, rev 5: downstream extraction must know
   whether it works from full text or abstracts before it starts).
   The policy-unmeetable trigger cannot fire (no policy object).
   Thresholds are named constants pinned at the plan gate. The mode-governed pause
   (Frequent/Moderate/Minimal routing, escalation UX) is plan-as-object machinery —
   already a recorded seam, unchanged here. No new event types; the
   `component.completed` payload (selection summary: per-stratum picks/exclusions
   with **full-text shares per stratum, selected vs candidate**, reason
   aggregates, flags) is the surface, mirroring 009's landscape summary.
7. **The shared tool is a function, not a framework — and its signature is the
   future agent's tool call.** The spec fixes the verb's contract — *(candidate
   set, cheap signals, strategy, directive) → chosen subset + rationale* — and
   that lands as a pure function with a `strategy` parameter validated against the
   registry of shipped strategies (exactly one: `coverage_stratified_v1`). No
   protocol class, no plugin machinery for a second strategy that doesn't exist
   (Transferability's dependency-scoping strategy is that capability's problem,
   ⏸ deferred — note the strategy *registry* now holds two entries, decision 10,
   still with no plugin machinery). The seam is the signature — deliberately
   shaped as the facade the capability agent invokes as one tool. Recorded seams
   sitting on it: **agent-authored directives** (the capability agent authors the
   directive **just-in-time at invocation, once the characterisation row exists**
   — reading this run's landscape + the intent; per plan-as-object the up-front
   plan is a non-compiling *forecast*, never the executed directive — the LLM
   reasoning over selection, at the seam the spec built for it); the
   **rerank-quality eval seam** (decision 10 — deterministic-ranked vs
   LLM-reranked on downstream consequence, once extract exists); and the **capability-run
   entity** (today a run = one component execution and the chain order lives only
   in `skeleton.py`, the agent's stand-in; the agent layer needs a durable run
   spanning components — the recorded Langfuse detached-trace warts are early
   symptoms).
8. **Component wiring mirrors 004–009.** `"select"` in `COMPONENT_REGISTRY`
   requiring `evidence_scope_id`; `SelectContext(scope_id, intent, context)`;
   `_run_select` via `_run_scope_component`; conditional-edge wiring;
   `component.started/completed/failed`. Invariants:
   `screened_in == selected + not_selected` (must-includes ⊆ selected; each
   selected doc in exactly one stratum bucket);
   `selected == must_include + breadth_floor + ranked`; one selection row per
   `(scope, run)`. Skeleton chain extends to select and renders the summary.
9. **Edge scopes and failure semantics — honest, tested.** `n = 0` → skip honestly
   (`empty_scope` flag, no selection row pretending otherwise); missing
   characterisation row → `component.failed` with a structural error (run
   characterise first — the chain owns ordering, the component owns honesty);
   budget ≥ n → select-all with rationale; unclustered-only grouping (zero themes)
   → one stratum, still stratified formally; all-must-include scopes → budget
   untouched, flagged if that exhausts the scope. Under `coverage_stratified_v1`
   there are no retries and no partial writes; re-running is clean (run-local row).
10. **`llm_rerank_v1` — purpose-sensitive within-stratum ordering, in-slice**
    (user-decided, rev 3). The generative judgment layer, bounded to the one thing
    arithmetic can't do: weighing candidates against the intent (and the synthesis
    purpose it implies) — preferring the systematic review for an overview intent,
    recognising the pivotal document similarity can't express.
    - **Contested strata only**: strata whose allocation < stratum size. Wholly
      selected strata need no ranking — no calls spent on them (test-asserted).
    - **Mechanics — 009's assignment stage transplanted**: batched concurrent
      calls on a judgment-capable model; each batch = id-keyed
      `(id, title, abstract)` data records + the intent + the fixed scoring
      instruction; output **schema-constrained to per-doc
      `(doc_id, score, reason)`** — no tools, no free text acting on the world.
      **The judged basis is the envelope, uniformly**: title + abstract (the
      surface the grouping calls read; degrading to title-only where the
      envelope did, flagged) — never full-text chunks, which sit on extraction's
      side of the pre-extract line. Uniform basis = abstract-only and full-text
      documents compete fairly. The LLM **ranks; it never selects**: strata,
      budget, must-includes and the breadth floor are code — the ranker only
      orders candidates within contested strata.
      Call budget known pre-run: `ceil(contested/batch) × (1 + retry_cap)`
      (caps plan-pinned), checked before any live call.
    - **Fallback, never failure — exhaustiveness in code**: a doc the ranker
      misses, duplicates or mangles falls back to its deterministic-composite
      score, flagged `rank_fallback` and counted in the rationale; an entire
      failed batch falls back the same way. The rerank can degrade to exactly
      `coverage_stratified_v1`, never to a partial or silent state. LLM scores
      order candidates; they never exclude (the structure of decision 1 is
      untouched).
    - **`RankingBackend` seam** mirroring `GroupingBackend`:
      `rank(batch, intent) -> scores+reasons` + `mode`; `OpenAIRankingBackend`
      (structured outputs) + deterministic stub for the suite. `run_harness
      ranking_backend` parameter, stub default.
    - **The `select_rerank_v1` prompt** — the repo's **second product prompt
      surface**, lead-authored, versioned, recorded in `selection_provenance` and
      the event payload. Injection posture identical to 009's (the standing
      rules): corpus text enters as id-keyed data records under data/instructions
      separation; **reasons are untrusted model output** (length/charset
      constraints, stored and rendered as data, re-enter prompts only as data);
      a hijacked model can at worst mis-order within a stratum, bounded by the
      code-owned structure.
    - **Model route**: a mini-class judgment model, plan-pinned — 009's recorded
      lesson applies (nano-class emits schema-valid empty output on batched
      structured tasks; start at gpt-5-mini-class).
    - **Honest softness**: reranked ordering is interpretive — recorded per doc
      (LLM score, reason, fallback flag) alongside the deterministic scores, so
      the rationale carries both and every ordering is attributable
      (`selection_provenance`: prompt version, model, batch size, fallback/retry
      counts). Rerank *quality* is eval territory once extract gives selection a
      consequence (the promoted eval seam: compare deterministic-ranked vs
      LLM-reranked selections on downstream yield, using the eval-ready traces).
    - **Strategy routing**: suite and library default = `coverage_stratified_v1`
      (stub, deterministic); the skeleton uses `llm_rerank_v1` on a configured
      key (egress is the product — the rev-6.1 posture). Cross-encoder relevance
      models (Cohere-class, on Bedrock) were considered and routed to the
      **`retrieve` seam** instead — they score query-relevance, not
      purpose-fit; recorded there, not here.

### Out of scope

- **`extract` and everything deeper** — select's consumer; subsequent slices.
- **Agent-authored directives** — the capability-agent commit layer (an LLM
  reading intent + landscape summary and authoring the `SelectionDirective`) is
  the agent-layer slice; this slice ships the surface it will drive (decision 4).
- **Rerank-quality evals** — machinery correctness is this slice's bar
  (decision 10); ranked-vs-reranked comparison on downstream yield needs extract.
- **Cross-encoder relevance models** (Cohere-class rerank, on Bedrock) — routed
  to the `retrieve` seam (query-relevance scoring, retrieval's upgrade — not
  select's purpose-fit judgment).
- **The capability-run entity** (a durable run spanning components) — recorded
  seam (decision 7); this slice keeps the one-run-per-component model.
- **The steer-point pause** (steering modes, escalation UX) — plan-as-object seam;
  the flags it will read ship now (decision 6).
- **`retrieve` / pgvector / hybrid retrieval** — still the vectors' committed
  first reader (rev 4 restored the clean line: select reads no vectors).
- **Source/evidence policy object** (the soft-prior tilt) and **dual-view
  coverage** — the policy trigger and tilt are structurally inert until it exists.
- **Selection-diversity extensions** — publication-country stratification,
  abstract-inferred population/intervention tags (spec: flagged, not baked).
- **Full appraisal pass on the selected subset** (the appraisal-improvement seam) —
  select creates the subset it will run on; the pass stays deferred.
- **Second `select` strategies** (Transferability dependency-scoping et al.).
- **EB artefact composition** — unchanged from 009; select writes no blocks.

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — one new table (`selection_result`, project-scope-guarded: composite
   FKs `(evidence_scope_id, project_id)` and `(run_id, project_id)`, UNIQUE
   `(evidence_scope_id, run_id)`). One migration; table count 19 → 20. No
   existing-table changes.
2. **Public interface** — the `"select"` `COMPONENT_REGISTRY` entry (compile
   surface widens) + `run_harness` gains optional `ranking_backend` (stub default —
   no default egress; the `grouping_backend` precedent). The selection directive
   rides the evidence-scope context (a first-class facade argument internally, not
   a harness signature change).
3. **Runtime egress — one new generation surface (user-confirmed, rev 3):** the
   `select_rerank_v1` calls send titles + abstracts (+ the scope intent) to the
   chat API under the repo's **second product prompt** (the 009-approved
   generation front, one new bounded surface on it: schema-constrained scores +
   reasons, contested strata only, pre-run call budget, fallback-not-failure).
   Traced by the existing Langfuse wiring. No embeddings call — the intent-embed
   site was cut at rev 4. Suite and library defaults stay stub + socket-deny;
   `make verify` remains egress-free.

No new dependency rides this slice (`openai` and `langfuse` land it all).

**Explicitly not crossed:** exactly one prompt-bearing surface (the
`select_rerank_v1` prompt — no agent loop, no free text acting on the world, no
directive-authoring generation); no new dependency; no auth/tenancy/CI change; no
pgvector/extension; no doc-level status column; no artefact/block writes; no new
event types.

**One spec flow-back approved with this contract** (user-decided, rev 3):
components §6 select realisation — "procedure" refined to *procedure with an
optional bounded generative rerank of within-stratum ordering* (stratification,
budget and hard rules stay code-side; scores order, never exclude; fallback to the
deterministic composite). `log.md` entry rides the slice. A second candidate
clarification — naming `unclustered` a first-class stratum — folds into the same
edit (it's already implied by §5's counted-unclustered + §6's "whatever clusters
exist").

## Public / private boundary

- No credentials beyond the existing env keys. On the live path, what leaves:
  the scope intent string and titles + abstracts of contested-strata candidates
  (the rerank calls) — the same text class and posture as 009's grouping calls;
  fixture-corpus content is openly licensed, so live verification sends only
  committable text. Full-I/O traces to the user-operated Langfuse instances,
  per the 009 posture.
- Committed artifacts (strategy names, weights, prompt text, table/column names,
  verification counts, rationale shapes) are public-safe. Selection rationale
  contains ids, scores, reason enums and the ranker's short reason strings
  (code-constrained, stored as data) — no source text.

## Model route

**Rerank**: a mini-class judgment model behind the `RankingBackend` seam (exact pin
at the plan gate; gpt-5-mini-class per 009's nano lesson; → Bedrock at the seam
swap). **Prompt-bearing surface: `select_rerank_v1`** — the repo's second product
prompt, lead-authored, versioned, recorded in `selection_provenance` and the event
payload; the only prompt in the slice. No embeddings use (rev 4).

## Disciplines binding this slice

- **Deterministic where claimed, honestly soft where not** — under
  `coverage_stratified_v1`: same corpus, same characterisation row, same
  parameters → byte-identical selection row, test-enforced (the 009 two-run
  determinism check). The structure (strata, allocation, budget, hard rules) is
  deterministic under *both* strategies; `llm_rerank_v1`'s ordering is
  interpretive by design and fully attributable (prompt version, model, per-doc
  scores + fallbacks recorded). Neither live path is inside `make verify`.
- **Flag, don't drop** — no signal gates: missing appraisal or unknown year
  lower a score or flag a doc, never exclude it; directive boosts
  re-weight, never exclude; ranker misses fall back to the deterministic
  composite, flagged `rank_fallback`, never dropped; must-includes are the only
  hard rule and they *include*.
- **Exactly one prompt-bearing surface** — the `select_rerank_v1` prompt,
  lead-authored; no other generation exists in the slice.
- **Honest absence** — `not_selected` is coverage, never silence: the bidirectional
  rationale makes every exclusion countable, and nothing in the payload phrases an
  exclusion as corpus absence.
- **Run-local means run-local** — selection lives in its run's row; nothing
  promotes it to canonical state; no cross-run reuse of groupings.
- **Model only what behaves** — no policy fields, no diversity dimensions the
  strategy doesn't read, no second-strategy machinery.
- **Never silent, never fake** — out-of-scope must-includes flagged; empty scopes
  skipped loudly; missing upstream state fails, not improvises.

## Stop conditions

- Any gated change (schema · public interface · egress) not yet approved, or any
  change beyond the gated items (existing-table change, new dependency, a second
  prompt surface beyond `select_rerank_v1`, doc-level status writes).
- Any *suite or library-default* code path would perform network I/O.
- The strategy needs a signal that isn't cheaply pre-extract (full text, anything
  requiring extraction) — that's the next component's side of the line; halt,
  don't reach.
- The rerank needs capabilities beyond per-doc scores + reasons (tool use, free
  text, multi-turn, excluding documents) — a different design; halt.
- The directive surface tempts a generation call (authoring directives from
  intent) or a hard exclude — the former is the agent-layer slice, the latter a
  design violation; halt, don't grow either.
- Extract-shaped scope creep (reading full text, writing findings, coverage-state
  vocabulary) — the next slice, not this one.
- `make verify` red with unclear root cause; or the turn/token budget is spent.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green, deterministic, zero
  egress (socket-deny covers a select round-trip; the suite runs on stubs only).
- **One manual live check** (evidence in verification.md): skeleton end-to-end with
  `OPENAI_API_KEY` (+ `LANGFUSE_*`) against the fixture corpus — **real
  `llm_rerank_v1` calls on the contested strata** (scores + reasons + any
  fallbacks recorded), selection summary rendered, rerank calls visible in
  the dev Langfuse trace (prompt version, tokens/cost); per-run counts and an
  honest cost note recorded; keys absent from captured output.
- Deterministic vs AI eval: all suite checks are deterministic tests (stub
  ranker; `coverage_stratified_v1` byte-identity). Rerank
  *quality* (are the right docs ranked up?) is eval territory once extract gives
  it a consequence; this slice's bar is machinery correctness + honest rationale.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 20.
- Named test results: stratified-allocation math (hand-computed fixture),
  breadth-floor anti-top-k case (a dominant stratum cannot starve the rest),
  must-include bypass + out-of-scope flag, counting invariants, determinism
  (two-run byte-identical), edge scopes (n=0, missing characterisation row,
  budget ≥ n, unclustered-only), missing-signal flag-not-block, text-basis tilt
  (soft — an abstract-only doc still selectable; hand-computed weight effect),
  trigger flags (large-stratum-excluded and thin-full-text fixtures), rationale
  bidirectionality (selected + excluded
  aggregates present and summing), directive semantics (a tag/column boost
  deterministically reorders a stratum · a boost can never exclude — the boosted-
  against doc still selectable · unknown column/tag in a directive flagged,
  non-fatal · empty directive = default scan, byte-identical to the no-directive
  path · executed directive + source recorded in `selection_provenance`), rerank
  semantics (contested-strata-only calls asserted against a counting double ·
  call-budget maximum enforced pre-call · per-doc fallback on missing/invalid
  scores, flagged and counted, batch fallback on batch failure — selection always
  completes · LLM scores order but never exclude · reasons length/charset
  constrained, injection-shaped reason stored as inert data · prompt hygiene:
  id-keyed data records under data/instructions separation, asserted structurally
  on the built prompt · provenance keys — prompt version, model, fallback counts —
  present on row and event payload).
- Live-run evidence per the manual check above.
- Public-safety confirmation (no credentials; live path sent the intent string
  only).
- Deferred seams recorded in `docs/deferred.md` (steer-point pause reading the
  flags · **agent-authored directives at the commit layer** · **rerank-quality
  evals** (ranked vs reranked on downstream yield, once extract exists) ·
  **cross-encoder relevance models (Cohere-class, Bedrock) at the `retrieve`
  seam** · **capability-run entity spanning components** · **embedding-relevance
  for select, declined** (rev 4 — revisit only via rerank-quality evals) ·
  selection-diversity extensions · policy soft-prior tilt · second strategies ·
  full appraisal on the selected subset — pointer updates where 009 entries
  already exist). The 009 "ahead of its first reader" vectorisation entry stands
  unchanged (retrieve remains the first reader).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate (one new table), the component sits on the
gap-provenance trust path (`not_selected` must never masquerade as absence), and
rev 3 adds the repo's second product prompt surface (generation egress + the
injection posture's second exercise). Still a markedly smaller slice than 009 (one
table, one prompt, no new dependency) — size the review stack accordingly (the 009
retro note applies: fewer finder angles on the smaller diff). ADR 0006 (selection
strategy · directive · rerank seam · rationale record) due at step 4; contract-
and plan-stage adversarial reviews standard.

Review focus:
- **Provenance/honesty (the headline lane)**: the bidirectional rationale
  complete and countable; `not_selected` derivable and never phrased as absence;
  flag-not-block on every signal; run-local selection not leaking canonical;
  trigger flags computed from the right bases; LLM scores/reasons attributable
  and never load-bearing for exclusion.
- **Security / prompt surface**: `select_rerank_v1` injection posture (id-keyed
  data records, schema-constrained scores+reasons, no tools; reasons as untrusted
  data); key hygiene unchanged; egress bounded (contested strata only, pre-run
  budget, socket-deny on suite paths).
- **Correctness**: largest-remainder allocation (sums to budget, deterministic);
  breadth floor under adversarial size distributions; must-include bypass
  arithmetic; directive semantics (boosts fold into scores and can never exclude;
  no directive shape can manufacture a hard gate; unknown references flagged);
  rerank fallback semantics (every contested doc scored or flagged, budget
  enforced pre-call); counting invariants; edge scopes.
- **Determinism**: stable orderings everywhere; two-run byte-identity; no
  set/dict-iteration-order leaks into the row.
- **Schema**: migration roundtrip; composite FKs; FK-safe deletes; unique
  constraint.
- **Scope**: no extract reach-through, no status columns, no policy machinery, no
  second strategy, suite egress-free.
