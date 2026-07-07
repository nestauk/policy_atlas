# Task contract: 013-synthesise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 6) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADRs: [0009](../../adr/0009-capability-composes-synthesise-terminus.md)
> (terminus architecture; decision 5 as amended) +
> [0010](../../adr/0010-intent-led-synthesis-sections.md) (intent-led
> sections; three dated Amendments = the rev-4/5/6 rounds) — both Accepted
> 2026-07-07.
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft — synthesise as deep-only content
>   producer per the then-current spec reading.
> - **rev 1.1** (2026-07-07): intent-derived artefact title · claim-driven
>   pattern annotations · judge envelope = cited chunks' full text ·
>   retrieval position explicit · clarity fixes.
> - **rev 2** (2026-07-07 → **ADR 0009**): capability-composes; synthesise
>   = EB's terminal component at every depth; registry + breadth ⊥ depth;
>   `characterisation_run_id` required.
> - **rev 3** (2026-07-07, deep-reasoner interrogation → **ADR 0010**):
>   group-per-block replaced by intent-led sections; intent enters
>   synthesis; selected-set chunk grounding in-slice; pure intent-led;
>   library → registry.
> - **rev 4** (2026-07-07 — ADR 0010 § Amendment): "deep path" retired;
>   claim vocabulary completed (**gap** + **reasoning** claims); windowing
>   replaced by scoped retrieval.
> - **rev 5** (2026-07-07 — ADR 0010 § second Amendment): modes renamed;
>   theme → **cluster claims**; depth = the plan's thoroughness gradation;
>   the section writer = capped agent-loop (`search_chunks` +
>   `query_findings`) — the repo's first agent loop, gated change 4.
> - **rev 6** (2026-07-07, fifth round — ADR 0010 § third Amendment; a net
>   **simplification**): **(a) the mode split itself dissolved** — one
>   substrate-conditional flow; claim types gated by what the referenced
>   runs produced; **chunk claims need only a selection, not extraction**
>   (extract's intervention–outcome schema is deliberately narrow — a
>   question outside it is served by characterise → select → synthesise
>   with no extract); the separate landscape prompt dies → **three prompt
>   surfaces**. **(b) the loop gains `lookup`** — the universal-core
>   canonical-state read tool (appraisals, classifications, selection
>   rationale, coverage records, clusterings; closed query vocabulary,
>   project-guarded) — three read-only tools total. **(c) "writer agent"
>   corrected to "the section loop"** — the loop is the component's
>   internal realisation per the facade principle; the capability
>   sub-agent remains the capability-run seam (no second agent).

## Goal

Add **synthesise** — EB component 9 and, per ADR 0009, **EB's terminal
component: it runs at every depth** and **composes the one EB artefact** —
mints it (intent-derived bounded title), renders content into grounded
blocks, binds them in section order. The orchestrator shapes the artefact
at plan time; composition is capability expertise and happens here. Depth
survives as the plan's thoroughness gradation steering which registry
components fire; **synthesise never hard-wires a component combination —
it adapts to whatever the plan selected** (ADR 0010, third amendment).

**One flow.** Synthesise takes explicit fail-closed run references —
`characterisation_run_id` required; the deepest available of
`selection_run_id` / `extraction_run_id` / `grouping_run_id` optional,
upstream references resolved transitively from the referenced rows' own
provenance and cross-checked — then:

1. **Section proposal** (`synthesise_sections_v1`, one bounded
   schema-constrained call): intent + the available substrate summaries
   (coverage, themes; group summaries when grouping ran) → a validated,
   capped, intent-led section list. A fail-closed `context["synthesis"]`
   directive can supply the list (the plan-shaped-sections seam's compile
   target).
2. **Per section, the section loop** (`synthesise_section_v1` — the
   component-internal realisation execution-orchestration declares:
   "agent-loop over scoped tools"; **the repo's first agent loop, exactly
   one such surface**): a capped tool-calling loop over **three read-only,
   project-guarded tools** —
   - **`search_chunks`** (present when a **selection** is referenced):
     hybrid embedding + lexical retrieval, rank-fused, over the selected
     set's frozen units — the 009 vectors' first reader; the `retrieve`
     seam's first increment;
   - **`query_findings`** (present when an **extraction** is referenced):
     the findings-layer read — the 012 deferral's named consumer,
     discharged in full;
   - **`lookup`** (always): the universal-core canonical-state read —
     appraisal tiers, classifications, selection rationale, coverage
     records, characterisation/grouping rows; closed query vocabulary v1,
     identifier/filter-addressed, side-effect-free —
   under a hard `SECTION_TURN_CAP`, then emits **typed claims whose
   availability is gated by substrate**:
   - **pattern** (always for coverage counts; direction spreads with
     extraction/grouping) — counts must equal the computed values;
   - **cluster** (themes always; facet groups with grouping) — validated
     against the referenced clustering row; softest interpretive grade,
     base-labelled;
   - **gap** (always) — graded, coverage-base-carrying; base-labelled to
     the narrowest base the substrate supports; corpus-level absence
     **only** on a referenced non-`inadequate` `search_coverage_record`
     (else fail-closed degraded and counted); inferred gaps visibly
     labelled, never gated;
   - **reasoning** (always) — uncited, visibly Tier-4-labelled, bounded
     per block, judge strict-routed, never in strength roll-ups;
   - **chunk** (with a **selection**) — verbatim quotes from tool-returned
     selected-set frozen text only; select's coverage discipline bounds
     them;
   - **finding** (with an **extraction**) — cite finding ids →
     extract-verified anchors; the model never authors these quotes.
   A characterisation-only run is the degenerate case
   (pattern/cluster/gap/reasoning sections — the landscape). **Groups,
   where present, are input, not structure** (`groups_unsectioned`
   counted, never silently dropped). **Descriptive always**: no
   recommendations, no weighted verdicts (⏸ consensus seam).
3. **Verify and write.** Every cited claim goes through the **real
   `produce-grounded-block` mechanism**: citations **co-emitted, never
   post-hoc**; verify = deterministic quote-presence against frozen chunks
   **plus** the `grounding_judge_v1` LLM judge (single lane: exactly one
   of Tier 1–4 / Unsupported-mis-cited; orthogonal weakly-grounded flag;
   required rationale; input includes the cited chunks' full frozen text —
   `synthesis_envelope_v1`; "topical relevance ≠ support" — intent and
   tool discretion shape emphasis, never verification). One **loop-free**
   reword-down repair; on exhaustion claims land **soft-flagged, never
   dropped, never silently promoted** — one hard exception: a chunk claim
   whose quote fails presence after repair is **excluded and counted**
   (fabrication is the hard-fail class). Blocks / claim-grain units /
   typed annotations / citation rows are written to the 001 substrate;
   the run-scoped `synthesis_result` roll-up row is the last statement.

⏸ Corpus-wide chunk grounding (unselected documents) stays gated on the
full `retrieve` slice. This slice is the **first real writer of the 001
information-layer substrate**, the **first reader of the 009
embedding-unit vectors**, and the **repo's first agent loop**.

## Deliverable

A PR on `task/013-synthesise` → `dev` that:

- Ships `synthesise.py`: `SynthesiseContext(scope_id, intent, context,
  characterisation_run_id, selection_run_id=None, extraction_run_id=None,
  grouping_run_id=None)`; `synthesise_scope(...)` — reference resolution
  (transitive upstream resolution from referenced rows; consistency
  cross-checks fail-closed) → artefact mint → section proposal (validated;
  directive override) → per section: the section loop (turns ≤
  `SECTION_TURN_CAP`; tools per substrate; gathered-evidence char budget)
  → typed-claim validation (per-type, substrate-gated) → batched judge
  call → one loop-free reword-down repair + one re-judge → block/unit/
  annotation/citation writes → roll-up row (last statement) → synthesis
  summary in `component.completed`.
- Ships **two backend seams, three prompt surfaces**: `SynthesisBackend`
  (+ OpenAI, stub) carrying **`synthesise_sections_v1`** and
  **`synthesise_section_v1`** (system prompt + the three tool schemas,
  versioned as one surface; the OpenAI form runs the bounded tool-calling
  loop), and `GroundingJudgeBackend` (+ OpenAI, stub) carrying
  **`grounding_judge_v1`** — the repo's fifth–seventh product prompts,
  all lead-authored, versioned, recorded in provenance.
- Ships the **three scoped tools**: **`search_chunks`** (hybrid retrieval
  over the referenced selection's documents' stored embedding-unit
  vectors + lexical scoring, rank-fused, top-k under plan-pinned caps;
  in-memory over JSONB vectors — no index, no new dependency; behind a
  swappable helper seam = the `retrieve` seam's first increment; query
  embeddings via the existing 009 `EmbeddingBackend`) ·
  **`query_findings`** (deterministic, project-guarded findings-layer
  reads — also used by the loader; discharges the 012 recorded deviation
  in full, agent-invoked) · **`lookup`** (closed query vocabulary v1 over
  canonical project state: appraisal by doc, classification by doc,
  selection rationale/summary, `search_coverage_record`, characterisation
  coverage/themes, grouping groups — identifier/filter-addressed,
  side-effect-free, scoped to this project and the referenced runs).
- Adds **one table — `synthesis_result`** — via one Alembic migration
  (gated change 1; table count 24 → 25, migration 13),
  project-scope-guarded.
- Registers `"synthesise"` in `COMPONENT_REGISTRY` (requires
  `evidence_scope_id` + **`characterisation_run_id`**; **`selection_run_id`
  / `extraction_run_id` / `grouping_run_id` optional** — deepest-given
  resolves the rest transitively; gated change 2); `run_harness` gains
  **`synthesis_backend`** and **`grounding_judge_backend`** (stub
  defaults — no default egress; the existing `embedding_backend` serves
  the retrieval queries).
- Extends `skeleton.py`: … group → **synthesise** (the terminus live);
  the live check demonstrates **three substrate profiles**
  (characterisation-only · characterisation+selection with **no
  extraction** · the full chain).
- **Factors the traced-call helper into `tracing.py`** (the 012-deferred
  trigger fires); loop turns and tool executions trace as spans (no new
  event types).
- Records/updates the deferred seams in `docs/deferred.md`; updates
  `tests/helpers.py` delete order.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [ADR 0010](../../adr/0010-intent-led-synthesis-sections.md) **including
  all three Amendments** (intent-led sections; full claim vocabulary; the
  agent-loop realisation; the substrate-conditional unification) and
  [ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md)
  (capability-composes; decision 5 as amended).
- [EB components §9](../../specs/capabilities/evidence-base/components.md)
  and [EB capability](../../specs/capabilities/evidence-base/capability.md)
  — as refined 2026-07-07 (five rounds); also components §5 (the
  characterisation record) and §8 (the grouping payload).
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — the **agent-loop-over-scoped-tools realisation this slice finally
  implements**, the facade principle (the loop is component-internal; the
  capability sub-agent is the capability-run seam), **`lookup`'s
  definition in the universal core**, `retrieve`'s full contract (the
  scoped tool here is its first increment), `query-findings`
  scoped-not-core, trust enforced at grounding.
- [System provenance-grounding](../../specs/system/provenance-grounding.md)
  — **the governing contract**: the traceability rule; tiers 1–4 (Tier
  4's strict routing); gaps (grades, coverage base, the
  `search_coverage_record` fail-closed rule); the pattern ladder;
  produce-grounded-block mechanics; judge posture;
  persistence-for-eval-readiness (**no calibration_status**).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  EB's gap rule; pattern grades.
- [System data-model](../../specs/system/data-model.md) — blocks / units /
  annotations; the findings layer; coverage states as gap provenance.
- [012-group contract](../012-group/contract.md) — the grouping payload;
  the carried requirements (**labels as data, never instructions**;
  **mixed/unclear findings survive**); its `query-findings` deferral
  (discharged here).
- [docs/deferred.md](../../deferred.md) — entries this slice touches
  (incl. the 009 vectors-ahead-of-reader entry, discharged here).
- The deep-reasoner interrogation memo (conversation A record).

**Code grounding (surveyed 2026-07-07):** 24 tables, 12 migrations (this
slice ships migration 13). The 001 substrate is real: `block` /
`addressable_unit` / `annotation((block_id, unit_id) composite-FK,
annotation_type, payload JSONB)` / `citation(chunk_id FK NOT NULL, quote,
verification_result)` — gap/pattern/cluster/reasoning annotations are new
`annotation_type` values riding the payload JSONB; chunk-cited claims
write ordinary `citation` rows. Upstream rows carry their own upstream
references (transitive resolution is real): `grouping_result` stores
`extraction_run_id`; `extraction_result` stores `selection_run_id`;
`selection_result` stores `characterisation_run_id`.
`search_coverage_record` (007): the corpus-promotion gate for gap claims.
`chunk_embedding` (009): one JSONB vector per embedding-unit, eager, **no
reader yet**; `EmbeddingBackend` + `embedding_backend` harness param exist
(stub vectors deterministic). `characterisation_result` carries `coverage`
+ `themes` + provenance. Findings carry extract-verified anchors (verified
`chunk_id`, quote, match status, spans). `grouping_result.groups` carries
per group: label, description, member values, member finding ids, size,
direction spread (+ residuals + overall). `quote_verify.py`'s
`build_basis` + `QuoteMatcher.find` verify verbatim quotes against frozen
chunks deterministically. Backend pattern: protocol + stub + OpenAI class
with pydantic `response_format`, module-constant prompt +
`PROMPT_VERSION`, caller-owned budget, validation separated from the call
(`gpt-5-mini` floor). **No agent loop exists anywhere yet** — the loop
runner, tool schemas and per-turn tracing are new machinery. Component
wiring: registry entry + required Config fields → context dataclass →
`_run_scope_component` → `component.*` events.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The complete produce-grounded-block mechanism lands in one slice** —
   deterministic quote-presence **and** the LLM judge **and** the bounded
   loop-free reword-down repair. Judge *calibration* stays eval-workstream
   territory; this slice's bar is mechanism correctness.
2. **Substrate-conditional, never mode-forked.** References:
   `characterisation_run_id` required; optionally the deepest of
   `selection_run_id` / `extraction_run_id` / `grouping_run_id` —
   upstream references resolved transitively from the referenced rows'
   own provenance; explicitly-passed shallower references must match the
   resolved ones (mismatch = structural failure). Claim types, tools and
   sectioning inputs are gated by the resolved substrate (Goal table);
   nothing else about the flow branches. The orchestrator's component
   freedom is preserved by construction: any coherent registry subset
   synthesises.
3. **Blocks are real information-layer rows at claim grain.** Per block:
   one `block` row (claims' prose joined deterministically;
   `content_hash` per 001), one `addressable_unit` per claim, and per
   claim-unit the annotation its type demands: **citation annotation**
   (finding/chunk), **pattern annotation** (validated counts + grade +
   base), **cluster annotation** (referenced clustering + softest-grade
   label + base), **gap annotation** (grade + coverage base + evidence
   refs), **reasoning annotation** (visible Tier-4 label + strict-routing
   verdict). `citation` rows link cited claim-units to frozen chunks.
4. **Synthesise mints the artefact — one per run, titled from the scope
   intent** (verbatim, bounded, deterministic) — and binds blocks in
   proposal order. Composition conventions stay at their seams. Re-run =
   new run = new artefact + new blocks. Empty characterisation → honest
   skip (roll-up + flag, no artefact).
5. **The intent-led section proposal.** `synthesise_sections_v1`
   (+ ≤1 repair): intent + available substrate summaries (id-keyed) →
   validated section list (1..`SECTION_CAP`; bounded non-generic
   titles/focus; group assignments, where groups exist, ⊆ real group ids,
   overlap allowed, exhaustiveness not required — uncovered groups →
   `groups_unsectioned`). The fail-closed **`context["synthesis"]`
   directive** can supply the list; executed source recorded.
6. **The section loop: one agent-loop surface, three read-only tools,
   hard caps.** Per section, `synthesise_section_v1` (system prompt +
   tool schemas, one versioned unit) runs the bounded tool-calling loop
   seeded with (id-keyed data): intent, section spec, available substrate
   summaries and — when extraction ran — the section's member findings +
   computed spread. Tools per decision 2's gating: `search_chunks`
   (hybrid cosine+lexical rank-fused, plan-pinned `SYNTH_CHUNK_TOP_K` /
   `SYNTH_CHUNK_CHAR_BUDGET`, id-keyed frozen chunk records out,
   deterministic given stored vectors + query, selected-set scope only) ·
   `query_findings` (referenced extraction's findings only) · `lookup`
   (closed query vocabulary v1; this project and the referenced runs
   only). Loop bounds, all plan-pinned and enforced in code:
   `SECTION_TURN_CAP` generation turns (tool calls consume turns; the
   claims emission is a turn), per-call and gathered-context budgets,
   closed tool set (unknown tool name = validation error, never
   executed), **read-only always, no egress verb** (`search` remains
   acquire's alone). Cap exhaustion forces the claims emission with
   whatever was gathered (`turn_cap_hit`, flagged) — never an unbounded
   loop, never a silent failure. Every turn and tool execution traces as
   spans; tool-call counts + gathered ids land in provenance. **The loop
   is the component's internal realisation** (facade principle): the
   capability sub-agent — the standing capability-run seam, skeleton
   standing in — invokes synthesise as one tool; there is no second
   agent identity.
7. **Six claim types, each with its own deterministic validation,
   substrate-gated; the model never authors a finding quote.**
   - **finding** (extraction referenced) — `cited_finding_ids ⊆ the
     section's finding set` (the referenced extraction's findings;
     group-scoped when grouping ran); code resolves to extract-verified
     anchors and re-runs the deterministic presence check (abstract-basis
     re-location; unlocatable/`failed` anchors → no fabricated citation
     row, `quote_unverified`, weakly-grounded cap, never dropped).
   - **chunk** (selection referenced) — verbatim quote + source chunk
     record id **from tool-returned results only** (citing an unreturned
     id rejects — co-emission enforced structurally); claimed location
     untrusted — `QuoteMatcher` verifies against the whole document
     basis, verified spans become the citation rows; presence failure
     rejects (one repair), still-failing → **excluded and counted**.
   - **pattern** — stated counts must equal the computed value (coverage
     counts; spreads when extraction/grouping ran).
   - **cluster** — references the clustering by id (themes; facet groups
     when grouping ran), validated against the referenced row; softest
     interpretive grade, base-labelled.
   - **gap** — grade + coverage base required; corpus-level phrasing
     fail-closed on a non-`inadequate` `search_coverage_record` (else
     degraded and counted); acknowledged-gap sparsity validated
     numerically; inferred gaps visibly labelled;
     `not_selected`/`not_extracted` never license absence.
   - **reasoning** — uncited, visibly Tier-4-labelled, bounded per block,
     judge strict-routed, never in roll-ups.
   Claims of a type the substrate doesn't support reject (one repair).
   No silent uncited path: every claim is cited, validated, or visibly
   labelled.
8. **The judge is `grounding_judge_v1`, batched per block, single-lane,
   reading the cited passages.** Judges cited claims (full lane; input
   includes the cited chunks' full frozen text — `synthesis_envelope_v1`)
   and reasoning claims (strict-routing only); pattern/cluster/gap claims
   are deterministically validated, not judged. Persistence for
   eval-readiness on the annotation payload; full I/O on Langfuse; **no
   calibration_status anywhere**.
9. **Repairs are bounded, loop-free, and reword down.** Proposal: one
   regeneration on validation rejection. Per section: one reword-down
   regeneration **over the already-gathered evidence** (no new tool
   calls) on validation rejection or any `unsupported_mis_cited`, then
   one re-judge. Call budget known pre-run as a **maximum**: proposal ≤ 2
   · per section ≤ `SECTION_TURN_CAP` + 2 generation calls + ≤
   `SECTION_TURN_CAP` embedding calls → total ≤ 2 + `SECTION_CAP` ×
   (`SECTION_TURN_CAP` + 2). Backend failure after retries fails the
   component honestly (`component.failed`, no roll-up row); blocks
   already written remain and the failure payload names them.
10. **Descriptive, never evaluative — absence disciplined, not banned.**
    Negative rules deterministically assertable on the built surfaces;
    the citable-bar flag-not-block rule honoured by the weakly-grounded
    mechanism (policy-conditioned flagging = recorded seam).
    **Mixed/unclear findings are first-class throughout.**
11. **`query-findings` is discharged in full** (agent-invoked in the
    loop — the 012 deferral's named consumer; entry closed as landed);
    the orchestrator-level capability-run architecture remains its own
    seam.
12. **Component wiring mirrors 004–012.** Registry entry per decision 2;
    `SynthesiseContext` via `functools.partial`; `_run_scope_component`;
    roll-up row last; re-run → new run_id; same-run re-execution loud;
    `component.completed` carries the summary; **no new event types**.
13. **Stubs are sentinel-driven; the suite is deterministic and
    egress-free.** `StubSynthesisBackend` drives **scripted tool-call
    sequences through the real loop runner** (fixture-declared turns
    across all three tools — exercising the cap, unknown-tool rejection,
    substrate gating, budgets and cap-exhaustion forcing for real) and
    emits typed claims across all six types (real anchor text, real
    record numbers, fabricated-quote and corpus-absence sentinels);
    `StubGroundingJudgeBackend` sentinel-driven; retrieval runs on 009's
    deterministic stub vectors. Determinism tests fix intent as input.
14. **All three prompt surfaces carry the standing injection posture —
    and the loop tightens it.** Intent, substrate summaries,
    coverage-record summaries, finding text, anchor quotes, tool-returned
    chunk text and labels enter as **id-keyed JSON data records**;
    responses and tool calls schema-constrained; the tool set is closed,
    read-only, substrate-scoped and code-enforced. Hijack bounds: a
    hijacked loop reads more in-corpus frozen text (cap-bounded) and
    emits mis-claims that face the unchanged claim bar; a hijacked judge
    mis-tiers within a closed enum; a hijacked proposal mis-shapes
    sections whose every claim is still verified.

### Schema

**Gated change 1 — one new table** (one migration; table count 24 → 25;
exact DDL plan-pinned, shape here binding):

```
synthesis_result  synthesis_result_id PK · project_id FK→project
                  · evidence_scope_id · run_id
                  · characterisation_run_id (executed reference, NOT NULL)
                  · selection_run_id (resolved reference, NULLABLE)
                  · extraction_run_id (resolved reference, NULLABLE)
                  · grouping_run_id (executed reference, NULLABLE)
                  · artefact_id FK→artefact NULLABLE (NULL only on the
                      empty-characterisation honest skip)
                  · synthesis_provenance JSONB NOT NULL (all three
                      prompt-surface versions incl. tool schemas, models,
                      judge envelope-policy version, backend modes,
                      per-phase call/turn/repair counts, the substrate
                      profile (which references resolved), the section
                      set + source [proposal|scope_context] + caps
                      (SECTION_CAP · SECTION_TURN_CAP · SYNTH_CHUNK_TOP_K
                      · SYNTH_CHUNK_CHAR_BUDGET), per-section tool-call
                      counts + gathered-id hash, and the inherited chain
                      base per resolved reference — characterisation
                      record summary hash; selection budget/strategy;
                      extraction fingerprint + base-ladder counts +
                      finding-set size/sha256; grouping facet + group
                      count)
                  · blocks JSONB NOT NULL (per section: title/focus,
                      block_id, assigned group ids where present,
                      tool-call count, claim counts by type
                      [finding|chunk|pattern|cluster|gap|reasoning], tier
                      distribution, unsupported/weakly-grounded counts,
                      citation verified/unverified counts,
                      chunk_claims_rejected, gap_claims_degraded,
                      repair_taken, turn_cap_hit)
                  · counts JSONB NOT NULL (blocks_written, sections_total,
                      claims_total by type, claims by verdict lane,
                      citations_verified, citations_unverified,
                      chunk_claims_rejected, gap_claims_degraded,
                      tool_calls_total, findings_cited_distinct,
                      findings_total where extraction ran, groups_total /
                      groups_unsectioned where grouping ran)
                  · flags JSONB NOT NULL (empty_characterisation ·
                      groups_unsectioned · unsupported_claims_present ·
                      weakly_grounded_present · chunk_claims_rejected ·
                      gap_claims_degraded · turn_cap_hit ·
                      repair_path_taken — where true)
                  · created_at
                  Composite FKs (evidence_scope_id, project_id),
                  (run_id, project_id) — cross-project guards
                  FK (evidence_scope_id, characterisation_run_id) →
                      characterisation_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, selection_run_id) →
                      selection_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, extraction_run_id) →
                      extraction_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, grouping_run_id) →
                      grouping_result (evidence_scope_id, run_id)
                  UNIQUE (evidence_scope_id, run_id)
```

No existing-table changes. Downgrade drops the table. `tests/helpers.py`
`delete_project_data` gains it in FK-safe order.

### Out of scope

- **Corpus-wide chunk-grounded narrative** and the **full `retrieve`
  tool** — the scoped `search_chunks` tool is the recorded first
  increment behind a seam the retrieve slice upgrades.
- **Agent loops anywhere else** — exactly one loop surface (the section
  loop); the proposal and judge stay single-call; the orchestrator-level
  capability-run architecture stays its own seam.
- **Plan-compile section machinery** (the directive is its compile
  target) · **composition conventions** · **weighted consensus /
  strength roll-up** (⏸; never-contribute constraints restated incl.
  gaps + reasoning) · **block summaries / artefact summary /
  faithfulness judging** · **block versioning beyond `version=1`** ·
  **residual-bucket prose** · the **landscape→synthesis steer-point** ·
  judge-envelope widening + re-gather repair (with `retrieve`) ·
  **`implementation_context_finding`**, cross-schema linkage,
  graph-structured synthesis (⏸).
- **Judge calibration / synthesis-quality / retrieval-quality evals** —
  the eval workstream owns them; this slice's bar is mechanism
  correctness.

## Constraints & approval gates

**Four gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table
   count 24 → 25. No existing-table changes.
2. **Public interface** — the `"synthesise"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `characterisation_run_id` (required) and
   `selection_run_id` / `extraction_run_id` / `grouping_run_id`
   (optional, transitively resolved, consistency fail-closed) +
   `run_harness` gains optional **`synthesis_backend`** and
   **`grounding_judge_backend`** (stub defaults). No renames ride this
   slice.
3. **Runtime egress — three new generation surfaces + embedding-query
   use** (the repo's fifth–seventh product prompts; embeddings egress
   opened in 009 — this adds tool-query text to that surface):
   `synthesise_sections_v1` · `synthesise_section_v1` (**multi-turn**:
   each loop turn is a generation call carrying gathered selected-set
   chunk text, finding records incl. verbatim quotes, canonical-state
   lookups and the user's intent — the 011 source-text class,
   relevance-ranked) · `grounding_judge_v1` (cited chunks' full frozen
   text). Fixture corpus openly licensed; full-I/O Langfuse traces
   (every loop turn and tool result) flagged for approval.
4. **The repo's first agent loop** — a capability-class change: the
   section loop gains bounded tool-calling discretion (closed read-only
   three-tool set, hard turn cap, code-enforced substrate scope). Every
   prior contract declared "no agent loop, no tools" — this contract
   deliberately crosses that line for exactly one surface, per the
   spec's own declared realisation and ADR 0010's amendments.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic`
cover it; cosine + lexical scoring are stdlib/in-memory).

**Explicitly not crossed:** exactly three prompt-bearing surfaces and
exactly one loop surface; no tool writes; no egress verb in the tool set;
no new dependency; no auth/tenancy/CI change; no existing-table change;
no new event types; no tag writes; no retrieval index/extension.

**Spec flow-backs: already landed with ADRs 0009 + 0010 (three
amendments)** — approved in this contract's gate conversation. Remaining
deferrals ride `docs/deferred.md`.

## Public / private boundary

- On the live path, what leaves: substrate summaries (coverage, themes,
  group summaries, selection rationale, coverage-record summaries),
  per-section finding records (source-named references, statistics,
  **verbatim quotes**), **tool-retrieved frozen chunk text from selected
  documents** (accumulating across loop turns), canonical-state lookup
  results, cited chunks' text, the user's **intent** (also as tool-query
  text to the embedding API), and model-generated labels — all
  fixture-corpus-derived (openly licensed by construction) — to the
  OpenAI API; full-I/O traces (every loop turn and tool result) to the
  user-operated dev Langfuse. For arbitrary future corpora this is
  source-derived text and user-authored intent inheriting the project's
  sensitivity class — private-by-default otherwise.
- Committed artifacts (schema, prompt text, tool schemas, roll-up shapes,
  verification counts) are public-safe. **Block content, claims, section
  titles/focus, gap texts, tool queries and judge rationales are
  model-generated text over source-derived input** — public-safe for the
  fixture corpus, private-by-default otherwise; **untrusted model output
  as data**: bounded and validated at write, rendered escaped, never
  executed. Carried forward: block content, section specs and judge
  rationales enter any future prompt as data records, never instructions.

## Model route

All three generation surfaces behind the two backend seams —
`gpt-5-mini`-class floor (the 009 nano lesson binding) → Bedrock at the
seam swap, unchanged. Tool-query embeddings ride the existing 009
embedding surface.

- **`synthesise_sections_v1`** — the section proposal; bounded list out;
  sections name aspects of the question and the evidence, never verdicts;
  no generic/catch-all sections; assignments only from supplied ids.
- **`synthesise_section_v1`** — the section-loop surface (system prompt +
  `search_chunks`/`query_findings`/`lookup` tool schemas, versioned as
  one unit); typed claims (finding | chunk | pattern | cluster | gap |
  reasoning, substrate-gated); negative rules: descriptive only; absence
  only as graded gap claims with their base; spreads/counts as given or
  tool-read, never invented; mixed/unclear reported, never aggregated
  away; quotes verbatim from tool-returned text only; claim within what
  the cited evidence supports; gather before writing, stop when
  saturated (the cap enforces it regardless).
- **`grounding_judge_v1`** — the classifier; closed verdict enum +
  `weakly_grounded` + required rationale for cited claims;
  strict-routing for reasoning claims; topical relevance ≠ support.

All three are **prompt-bearing, lead-authored, versioned** (tool schemas
included), recorded in provenance, event payloads and (judge) annotation
payloads. The judge rubric is lead-only per AGENTS.md.

## Disciplines binding this slice

- **The traceability rule is the slice** — every claim is
  cited-and-verified, deterministically validated, or visibly labelled;
  no fourth state, no silent promotion, no post-hoc citation path.
  Intent and tool discretion shape emphasis and evidence-gathering,
  never verification.
- **Honest absence** — absence only as graded gap claims with their
  coverage base; corpus-level fail-closed on the coverage record;
  `not_selected`/`not_extracted` never license absence.
- **Flag, don't drop** — failed anchors, unsupported/weakly-grounded
  claims, degraded gaps, uncovered groups and cap-forced emissions land
  visible with status; the one exclusion is fabricated chunk quotes —
  excluded **and counted**.
- **Bounded agency** — one loop surface; closed read-only three-tool
  set; code-enforced caps and substrate scope; cap exhaustion forces
  emission, never extends.
- **Substrate-conditional, never mode-forked** — claim/tool availability
  derives from the resolved references; the orchestrator's registry
  freedom is preserved by construction.
- **Deterministic where claimed** — presence checks, citation
  resolution, offsets, computed values, per-type validation, tool
  ranking (given stored vectors + query), reference resolution,
  cross-checks, ordering and writes; generation calls bounded by the
  pre-run maximum; determinism tests fix intent as input.
- **Model only what behaves**; **never silent, never fake** — as the
  standing disciplines; grouping↔findings, reference-consistency and
  computed-value mismatches are structural failures.

## Stop conditions

- Any gated change (schema · public interface · egress · the agent loop)
  not yet approved, or any change beyond them (existing-table change, a
  fourth prompt surface, a second loop surface, a new or write-capable
  tool, new dependency, retrieval index/extension, consensus/summary
  machinery, new event types).
- Any *suite or library-default* code path would perform network I/O.
- The loop wants more than the three read-only tools, wants to write,
  wants unselected-corpus chunks, or wants an uncapped turn budget —
  halt.
- The synthesis wants evaluative output, free-phrased absence, or
  composition conventions — halt.
- The claim/citation model can't express something without weakening
  verification — design change; halt, never weaken the bar silently.
- `make verify` red with unclear root cause; or the turn/token budget is
  spent.

## Acceptance checks

- `make verify` — green, deterministic, zero egress (socket-deny covers
  synthesise round-trips across substrate profiles including the
  scripted stub loop).
- **One manual live check, three substrate profiles** (evidence in
  verification.md): skeleton end-to-end with `OPENAI_API_KEY`
  (+ `LANGFUSE_*`) against the fixture corpus — (a)
  **characterisation-only** (the landscape degenerate case: artefact +
  pattern/cluster/gap/reasoning sections); (b) **characterisation +
  selection, no extraction** (the flexibility case this round secured:
  chunk-grounded sections over the selected set, zero extract calls);
  (c) **the full chain** (all claim types; the loop visibly gathering —
  per-section tool-call counts, queries and gathered ids recorded; tier
  distribution, gap grades/bases, degradations/exclusions and any
  `turn_cap_hit` shown honestly; repair path exercised or its absence
  noted; `groups_unsectioned` honest). All three surfaces + tool turns +
  embedding queries visible in dev Langfuse (versions, tokens/cost) with
  run-level scores; per-run counts and an honest cost note; keys absent
  from captured output.
- Deterministic vs AI eval: suite checks deterministic (stubs; scripted
  loop); section/prose/retrieval quality and judge calibration are eval
  territory — this slice's bar is mechanism correctness, invariant
  enforcement, honest flags and provenance fidelity.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 25.
- Named test results: **reference resolution** (characterisation_run_id
  required; deepest-given resolves upstream transitively; explicit
  shallower references must match resolved — mismatch structural;
  missing referenced rows → structural failure; substrate profile
  recorded), **substrate gating** (chunk claims/`search_chunks` absent
  without a selection; finding claims/`query_findings` absent without an
  extraction; group-cluster claims absent without a grouping; a claim of
  an unsupported type rejects), **section proposal validation** (caps,
  bounded non-generic titles, real assignments, `groups_unsectioned`
  counted, malformed directive fails closed, source recorded), **the
  loop** (turn cap enforced — exhaustion forces emission +
  `turn_cap_hit`; unknown tool rejected, never executed; tools read-only
  and scoped — foreign-project or unselected-document content never
  returned, test-enforced; per-call and gathered-context budgets
  enforced; tool-call counts + gathered-id hash in provenance; scripted
  stub sequences drive the real runner; repair is loop-free — no new
  tool calls, test-asserted), **`search_chunks` ranking** (hybrid fusion
  deterministic on stub vectors; top-k and char budgets enforced),
  **`lookup` discipline** (closed vocabulary — unknown query kind
  rejected; project/run-scoped; side-effect-free), **finding-claim
  citation resolution** (ids ⊆ the section's finding set; anchors reused
  verbatim; abstract-basis re-location; failed/unlocatable anchors →
  `quote_unverified` + weakly-grounded cap, never dropped), **chunk-claim
  verification** (quotes only from tool-returned ids; presence-checked
  against the whole document basis; verified spans become the citation
  rows; fabricated quote → reject, one repair, then excluded and
  counted), **gap-claim discipline** (corpus-level phrasing without a
  non-`inadequate` coverage record → fail-closed degradation, counted;
  acknowledged sparsity validated numerically; inferred labelled; base
  always present), **cluster-claim discipline** (referenced clustering
  ids validated; softest-grade label + base), **reasoning-claim
  discipline** (visibly labelled; strict-routing sentinel flagged;
  per-block count bounded), **claim/unit integrity** (every cited claim
  ≥ 1 citation target; annotations exist iff their claim does, on that
  claim's unit; offsets exact; composite-FK integrity; content_hash
  correct), **judge semantics** (single-lane enum; rationale required;
  verdict + judge provenance + envelope version persisted; judge input
  includes cited chunk text; cited and reasoning claims judged;
  pattern/cluster/gap not judged), **repair semantics** (bounded exactly
  as decision 9; budgets test-asserted; exhaustion → flags, claims
  retained except fabricated chunk quotes), **flag-not-drop**
  (unsupported / weakly-grounded / degraded-gap claims persist visibly;
  mixed/unclear visible end-to-end), **descriptive posture** (negative
  rules asserted on all three built surfaces; injection-shaped labels,
  quotes, chunk text, lookup results or coverage summaries land as inert
  data), **artefact/composition v1** (one artefact per run,
  intent-derived bounded title; proposal-ordered binding; re-run → new
  artefact; same-run re-execution loud; backend failure →
  `component.failed`, no roll-up row, prior blocks named),
  **determinism** (two stub runs with fixed intent → identical payload
  columns, block content and hashes; tool ranking deterministic),
  **provenance required keys** (three surface versions incl. tool
  schemas, envelope policy, substrate profile, section set + source, all
  caps, per-section tool-call counts + gathered-id hash, per-phase call
  counts, the inherited chain base per resolved reference), delete-order
  integrity.
- Live-run evidence per the manual check above (three profiles).
- Public-safety confirmation (egress was fixture-corpus text + intent
  only; traces on the user-operated instance; keys clean).
- Deferred seams recorded/updated in `docs/deferred.md`: **corpus-wide
  chunk-grounded narrative** + **full `retrieve` tool** (the
  `search_chunks` tool = its first increment; upgrade path recorded; the
  009 vectors-ahead-of-reader entry discharged) · **`query-findings`
  entry closed as landed** · **plan-compile section machinery**
  (directive = compile target) · **composition conventions** ·
  policy-conditioned citable-bar flagging · consensus roll-up
  (never-contribute constraints restated incl. gaps + reasoning) · block
  summaries + faithfulness judging · judge-envelope widening + re-gather
  repair (with `retrieve`) · synthesis/judge/retrieval quality evals
  (envelope, SECTION_CAP, SECTION_TURN_CAP, top-k and `lookup`-vocabulary
  calibration).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate, three new generation surfaces plus
embedding-query use ride the slice, and it deliberately crosses a
standing line: **the repo's first agent loop** (gated change 4). This is
the trust invariant's landing slice, carrying the full honest-assertion
vocabulary with bounded agency and substrate-conditional flexibility.
Contract- and plan-stage adversarial reviews standard; review stack sized
per the review-economy notes; the security lane's headline target is the
loop. ADRs 0009 + 0010 (three amendments) cover the architecture.

Review focus:
- **Provenance/honesty (the headline lane)**: co-emitted citations only
  (chunk claims cite only tool-returned ids); presence checks for both
  cited claim kinds; verified spans become citation rows; single-lane
  verdicts persisted; pattern/cluster/gap values deterministically
  validated; the gap fail-closed corpus-promotion rule; reasoning claims
  visibly labelled and strict-routed; unsupported/weak/degraded claims
  flagged never dropped; fabricated chunk quotes excluded and counted;
  mixed/unclear survive; uncovered groups counted; cap-forced emissions
  flagged; intent and tool discretion never touch verification;
  provenance carries the inherited chain base per resolved reference.
- **Security / the loop (the second headline)**: closed read-only
  three-tool set, code-enforced scope (this project, the referenced
  runs, the selected set), hard turn and result caps, unknown-tool
  rejection, no egress verb; injection through retrieved frozen text or
  lookup results bounded to more reading + mis-claims facing the
  unchanged claim bar; three prompt surfaces consuming untrusted text as
  id-keyed data records; outputs bounded and validated at write; key
  hygiene; socket-deny on suite paths.
- **Correctness**: reference resolution + substrate gating; section
  validation; loop runner semantics (turn accounting, budget
  enforcement, cap-exhaustion forcing, loop-free repair); hybrid ranking
  determinism; citation resolution across verified/abstract/failed
  anchors and chunk quotes; per-type validation; offsets; composite-FK
  integrity; roll-up-last ordering; FK and delete order.
- **Scope**: one loop surface only; no corpus-wide retrieval or index;
  no composition conventions; no consensus/summary machinery; no fourth
  prompt; suite egress-free.
