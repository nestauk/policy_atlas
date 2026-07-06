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
>   **capability-run entity** spanning components).

## Goal

Add **select** — EB component 6, the gate that opens the deep terminus. After
characterise has measured the corpus shape, select chooses the subset for Tier-1
extraction: **coverage-aware stratified selection over the run's characterisation
strata**, breadth-adaptive (the landscape has already measured breadth — stratify
across whatever strata exist; the budget sets how deep per stratum), guarding against
horizon scans collapsing onto a narrow top-k.

This is a **fully deterministic slice** — the counterweight to 009. No prompts, no
generation, no new dependencies, no new egress front. Same inputs → same selection,
test-enforced. The one interpretive-adjacent input is the embedding-relevance signal,
and that is a cosine computation over already-landed vectors, not a judgment call.

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
  rationale*, per the spec's tool contract) with **`coverage_stratified_v1`** as the
  one shipped strategy; the **`SelectionDirective`** (first-class facade argument —
  budget, must-includes, column/tag soft boosts, weight emphasis);
  `SelectContext`; `select_scope(...)` — directive resolution → signal assembly →
  stratification → allocation → ranking → rationale → the `selection_result` row →
  the selection summary in `component.completed`.
- Adds **one table — `selection_result`** — via one Alembic migration (gated
  change 1; table count 19 → 20), project-scope-guarded per repo discipline.
- Registers `"select"` in `COMPONENT_REGISTRY` (requires `evidence_scope_id`); wires
  `_run_select`; **no new `run_harness` parameter** (the intent embedding reuses the
  existing `embedding_backend`).
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
  steer-point pause (stays deferred), unclustered-as-stratum (lands here), pgvector
  at the retrieve slice (unchanged — select reads vectors in code, builds no index).
- [009-characterise contract](../009-characterise/contract.md) — pattern precedent
  (run-scoped result row, project-scoped composite FKs, component wiring,
  edge-scope handling, honest failure).

**Code grounding (surveyed 2026-07-06):** 19 tables. `characterisation_result` is
per `(evidence_scope_id, run_id)` with `themes` JSONB (`themes[]` = name /
description / member_ids / size + `unclustered_ids`) and `coverage` JSONB carrying
base counts — select's stratification input, same-run. `chunk_embedding` holds unit
vectors as JSONB float arrays keyed by profile/policy (no pgvector — reading them in
Python is cheap at 10s–100s docs). Cheap Tier-0 signals in place: `origin`,
metadata year, `source_appraisal_result` quality tier, screen confidence,
`text_basis`/`full_text_status`. `run_harness(conn, *, config, project_id, run_id,
provider, search_backends, document_fetcher, embedding_backend, grouping_backend)` —
`embedding_backend` already threads through `HarnessState`. Component wiring pattern:
registry entry → context dataclass `(scope_id, intent, context)` → `_run_scope_component`
→ `component.started/completed/failed`. The skeleton chain ends at characterise.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **Select is procedure-only — the spec's realisation class, taken literally.** No
   LLM, no prompts, no `GroupingBackend`-style seam, no new dependency. Every signal
   is cheap and pre-extract (the spec's explicit constraint); combining them is
   arithmetic. Deterministic end-to-end: stable ordering, deterministic tie-breaks
   (snapshot id), same input → byte-identical selection row, test-enforced.

2. **Relevance signal = embedding cosine against the scope intent — the 009 vectors'
   first reader.** The spec names relevance-to-intent via "embeddings / screening";
   both land, with embeddings primary:
   - One intent-embedding call per run through the **existing `embedding_backend`**
     (stub in the suite — deterministic, egress-free; live under the 009-approved
     embeddings gate — a **new call site on an approved front, not a new front**).
   - Document relevance = **max cosine over the document's embedding units** for the
     active profile (small-to-big: match at unit grain, score the document). Computed
     in Python over the JSONB vectors — no pgvector, no index (that stays with
     `retrieve`, the committed first *retrieval* reader; select is a batch read of a
     bounded scope, not a search).
   - Screen confidence folds in as a secondary signal. It is stub-constant today
     (screen's LLM tool is a deferred seam), which is exactly why embeddings lead:
     the vectors are the only live-discriminating relevance signal the corpus
     actually carries. Documents with no embedding rows (embed-failure stragglers)
     get a null relevance score and are flagged, never dropped (flag-not-block).
   - Declined: screening-confidence-only (zero new call sites, but no live
     discrimination — and it leaves the landed vectors unread for another slice);
     deferring relevance entirely (the spec names it as a core signal).
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
   - **Within-stratum ranking:** a weighted composite over the normalised cheap
     signals — relevance (embedding cosine; screen-confidence secondary) · recency
     (year, bounded decay) · light appraisal tier · origin/upload priority
     (`uploaded` favoured, per the spec's default-priority-via-scoping posture) —
     plus the directive's **soft boosts** (decision 4), folded into the same
     composite. Default weights are named constants pinned at the plan gate; the
     effective weights (defaults ⊕ directive emphasis) are recorded in
     `selection_provenance`. Ties break on snapshot id.
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
   signal availability incl. embedding profile + null-relevance counts) ·
   `selected` JSONB (per doc: pss id, stratum, signal scores,
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
   selection time). The policy-unmeetable trigger cannot fire (no policy object).
   Thresholds are named constants pinned at the plan gate. The mode-governed pause
   (Frequent/Moderate/Minimal routing, escalation UX) is plan-as-object machinery —
   already a recorded seam, unchanged here. No new event types; the
   `component.completed` payload (selection summary: per-stratum picks/exclusions,
   reason aggregates, flags) is the surface, mirroring 009's landscape summary.
7. **The shared tool is a function, not a framework — and its signature is the
   future agent's tool call.** The spec fixes the verb's contract — *(candidate
   set, cheap signals, strategy, directive) → chosen subset + rationale* — and
   that lands as a pure function with a `strategy` parameter validated against the
   registry of shipped strategies (exactly one: `coverage_stratified_v1`). No
   protocol class, no plugin machinery for a second strategy that doesn't exist
   (Transferability's dependency-scoping strategy is that capability's problem,
   ⏸ deferred). The seam is the signature — deliberately shaped as the facade the
   capability agent invokes as one tool. Three recorded seams sit on it:
   **agent-authored directives** (the capability agent authors the directive
   **just-in-time at invocation, once the characterisation row exists** — reading
   this run's landscape + the intent; per plan-as-object the up-front plan is a
   non-compiling *forecast*, never the executed directive — the LLM reasoning over
   selection, at the seam the spec built for it); an **`llm_assisted` strategy**
   (eval-gated: reopen with
   evidence once extract gives selection quality a consequence — the pattern that
   legitimately flipped characterise); and the **capability-run entity** (today a
   run = one component execution and the chain order lives only in `skeleton.py`,
   the agent's stand-in; the agent layer needs a durable run spanning components —
   the recorded Langfuse detached-trace warts are early symptoms).
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
   untouched, flagged if that exhausts the scope. Deterministic component —
   no retries, no partial writes; re-running is clean (run-local row).

### Out of scope

- **`extract` and everything deeper** — select's consumer; subsequent slices.
- **Agent-authored directives** — the capability-agent commit layer (an LLM
  reading intent + landscape summary and authoring the `SelectionDirective`) is
  the agent-layer slice; this slice ships the surface it will drive (decision 4).
  No prompt-bearing work here.
- **`llm_assisted` selection strategies** — eval-gated at the strategy seam
  (decision 7); reopen with selection-quality evidence, not speculation.
- **The capability-run entity** (a durable run spanning components) — recorded
  seam (decision 7); this slice keeps the one-run-per-component model.
- **The steer-point pause** (steering modes, escalation UX) — plan-as-object seam;
  the flags it will read ship now (decision 6).
- **`retrieve` / pgvector / hybrid retrieval** — still the vectors' committed
  retrieval reader; select's batch cosine read changes nothing there.
- **Source/evidence policy object** (the soft-prior tilt) and **dual-view
  coverage** — the policy trigger and tilt are structurally inert until it exists.
- **Selection-diversity extensions** — publication-country stratification,
  abstract-inferred population/intervention tags (spec: flagged, not baked).
- **Full appraisal pass on the selected subset** (the appraisal-improvement seam) —
  select creates the subset it will run on; the pass stays deferred.
- **Second `select` strategies** (Transferability dependency-scoping et al.).
- **EB artefact composition** — unchanged from 009; select writes no blocks.

## Constraints & approval gates

**Two gated changes (approval needed at this gate):**

1. **Schema** — one new table (`selection_result`, project-scope-guarded: composite
   FKs `(evidence_scope_id, project_id)` and `(run_id, project_id)`, UNIQUE
   `(evidence_scope_id, run_id)`). One migration; table count 19 → 20. No
   existing-table changes.
2. **Public interface** — the `"select"` `COMPONENT_REGISTRY` entry (compile
   surface widens). **No new `run_harness` parameter** — the intent embedding rides
   the existing `embedding_backend`, and the selection directive rides the
   evidence-scope context (a first-class facade argument internally, not a harness
   signature change).

**Runtime egress — no new front (flagged for the record, not gated as new):** one
new call site on the 009-approved embeddings front — a single intent-string
embedding per run through the existing seam, traced by the existing Langfuse wiring.
What leaves on the live path: the scope's intent text, nothing else. Suite and
library defaults stay stub + socket-deny; `make verify` remains egress-free. If the
human reads this as a gate reopening rather than an approved-front call site, that
is exactly what this checkpoint is for.

**Explicitly not crossed:** no generation surface (zero prompts in the slice); no
new dependency; no auth/tenancy/CI change; no pgvector/extension; no doc-level
status column; no artefact/block writes; no new event types.

Spec flow-backs: none anticipated. One candidate clarification — components §6
naming `unclustered` as a first-class stratum (the 009 contract already commits to
it) — folded in only if the adversarial review or the human wants it recorded; it
reads as already implied by §5's counted-unclustered + §6's "whatever clusters
exist".

## Public / private boundary

- No credentials beyond the existing env keys; nothing new leaves the machine
  except the scope intent string on the live embed path (openly authored, not
  corpus text). Fixture corpus unchanged.
- Committed artifacts (strategy name, weights, table/column names, verification
  counts, rationale shapes) are public-safe. Selection rationale contains only
  ids, scores and reason enums — no source text.

## Model route

`n/a` — no inference. The only model-adjacent touch is the intent embedding through
the existing `EmbeddingBackend` seam (profile already stamped and recorded in
`selection_provenance`). Zero prompt-bearing surfaces.

## Disciplines binding this slice

- **Deterministic where claimed** — the whole component: same corpus, same
  characterisation row, same parameters → byte-identical selection row.
  Test-enforced (the 009 two-run determinism check, applied here).
- **Flag, don't drop** — no signal gates: null relevance, missing appraisal,
  unknown year lower a score or flag a doc, never exclude it; directive boosts
  re-weight, never exclude; must-includes are the only hard rule and they
  *include*.
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

- Either gated change (schema · public interface) not yet approved, or any change
  beyond them (existing-table change, new dependency, new egress front, doc-level
  status writes, a generation surface).
- Any *suite or library-default* code path would perform network I/O.
- The strategy needs a signal that isn't cheaply in Tier-0 (anything requiring
  text interpretation) — that's extraction's side of the line; halt, don't reach.
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
  `OPENAI_API_KEY` (+ `LANGFUSE_*`) against the fixture corpus — real intent
  embedding, cosine relevance over the 009-landed real vectors, selection summary
  rendered, the embed call visible in the dev Langfuse trace; per-run counts
  recorded; keys absent from captured output. (Cost ≈ one embedding call.)
- Deterministic vs AI eval: everything here is a deterministic test. Selection
  *quality* (are the right docs chosen?) is eval territory once extract gives it a
  consequence; this slice's bar is machinery correctness + honest rationale.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 20.
- Named test results: stratified-allocation math (hand-computed fixture),
  breadth-floor anti-top-k case (a dominant stratum cannot starve the rest),
  must-include bypass + out-of-scope flag, counting invariants, determinism
  (two-run byte-identical), edge scopes (n=0, missing characterisation row,
  budget ≥ n, unclustered-only), null-relevance flag-not-block, trigger flags
  (large-stratum-excluded fixture), rationale bidirectionality (selected + excluded
  aggregates present and summing), directive semantics (a tag/column boost
  deterministically reorders a stratum · a boost can never exclude — the boosted-
  against doc still selectable · unknown column/tag in a directive flagged,
  non-fatal · empty directive = default scan, byte-identical to the no-directive
  path · executed directive + source recorded in `selection_provenance`).
- Live-run evidence per the manual check above.
- Public-safety confirmation (no credentials; live path sent the intent string
  only).
- Deferred seams recorded in `docs/deferred.md` (steer-point pause reading the
  flags · **agent-authored directives at the commit layer** · **`llm_assisted`
  strategy, eval-gated** · **capability-run entity spanning components** ·
  selection-diversity extensions · policy soft-prior tilt · second strategies ·
  full appraisal on the selected subset — pointer updates where 009 entries
  already exist), and the 009 "ahead of its first reader" vectorisation entry
  updated: first read landed (select's relevance signal; retrieval remains the
  indexed reader).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate (one new table) and the component sits on the
gap-provenance trust path (`not_selected` must never masquerade as absence). But
the slice is deliberately narrow: no generation, no new dependency, no new egress
front — the review stack should be sized accordingly (the 009 retro note applies:
fewer finder angles on the smaller diff). ADR 0006 (selection strategy + rationale
record) due at step 4; contract- and plan-stage adversarial reviews standard.

Review focus:
- **Provenance/honesty (the headline lane this time)**: the bidirectional rationale
  complete and countable; `not_selected` derivable and never phrased as absence;
  flag-not-block on every signal; run-local selection not leaking canonical;
  trigger flags computed from the right bases.
- **Correctness**: largest-remainder allocation (sums to budget, deterministic);
  breadth floor under adversarial size distributions; must-include bypass
  arithmetic; directive semantics (boosts fold into scores and can never exclude;
  no directive shape can manufacture a hard gate; unknown references flagged);
  cosine relevance (profile-matched units, max-over-units, null handling);
  counting invariants; edge scopes.
- **Determinism**: stable orderings everywhere; two-run byte-identity; no
  set/dict-iteration-order leaks into the row.
- **Schema**: migration roundtrip; composite FKs; FK-safe deletes; unique
  constraint.
- **Scope**: no extract reach-through, no status columns, no policy machinery, no
  second strategy, suite egress-free.
