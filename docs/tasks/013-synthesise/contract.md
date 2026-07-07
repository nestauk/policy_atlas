# Task contract: 013-synthesise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 5) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADRs: [0009](../../adr/0009-capability-composes-synthesise-terminus.md)
> (terminus architecture; decision 5 as amended) +
> [0010](../../adr/0010-intent-led-synthesis-sections.md) (intent-led
> sections, mixed grounding, selected-set chunk grounding; two dated
> Amendments = the rev-4 and rev-5 rounds) — both Accepted 2026-07-07.
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft — synthesise as deep-only content
>   producer per the then-current spec reading.
> - **rev 1.1** (2026-07-07, user challenges — adjudicated): intent-derived
>   artefact title · claim-driven pattern annotations (typed claims) · judge
>   envelope = cited chunks' full frozen text · retrieval position explicit
>   · clarity fixes.
> - **rev 2** (2026-07-07, user spec-challenge → **ADR 0009**): terminus
>   refinement — capability-composes; synthesise = EB's terminal component
>   at every depth (landscape mode added); components as a registry,
>   breadth ⊥ depth; `characterisation_run_id` (required) +
>   `grouping_run_id` (optional).
> - **rev 3** (2026-07-07, user challenge on intent-relevance → independent
>   deep-reasoner interrogation → **ADR 0010**): group-per-block replaced
>   by intent-led sections; intent enters synthesis; selected-set chunk
>   grounding pulled in-slice (only corpus-wide is retrieve-gated); pure
>   intent-led (no rendered backbone); library → registry.
> - **rev 4** (2026-07-07, third round — ADR 0010 § Amendment): "deep
>   path" retired (content modes by available references); claim
>   vocabulary completed — **gap claims** (graded, coverage-base,
>   fail-closed corpus promotion) + **reasoning claims** (visible Tier-4
>   authoring, judge strict-routing); whole-document windowing replaced by
>   scoped retrieval.
> - **rev 5** (2026-07-07, fourth round — ADR 0010 § second Amendment):
>   **(a) modes renamed** — **landscape synthesis** / **findings-grounded
>   synthesis**, both intent-led ("findings" = the findings *layer*; a
>   targeted question typically runs narrow-and-deep, so most
>   intent-answering runs carry findings; landscape-only is the broad-scan
>   case). **(b) cluster claims unified** — the rev-4 theme claim was a
>   cluster claim restricted to landscape; one cluster-claim type now
>   spans both modes (characterise themes / facet groups), validated
>   against the referenced clustering, softest interpretive grade.
>   **(c) depth clarified** — the plan's thoroughness gradation survives;
>   only the shallow/deep fork died. **(d) the section writer is a capped
>   agent-loop (agentic retrieval)** — execution-orchestration's declared
>   realisation and the exact consumer 012's `query-findings` deferral
>   named: two read-only selected-set-scoped tools (`search_chunks`
>   hybrid + `query_findings`), hard per-section turn cap, loop-free
>   repair; **the repo's first agent loop**, and this contract's largest
>   gate item.

## Goal

Add **synthesise** — EB component 9 and, per ADR 0009, **EB's terminal
component: it runs at every depth** and **composes the one EB artefact** —
mints it (intent-derived bounded title), renders content into grounded
blocks, binds them in section order. The orchestrator shapes the artefact
at plan time; composition is capability expertise and happens here. Per
ADR 0010, the output is **shaped by what was asked, not by what was
studied** — and depth itself survives as the plan's thoroughness
**gradation** (plan-as-object: orchestrator-inferred from intent, the
lighter/deeper nudge), steering which registry components fire; synthesise
adapts to whatever the plan selected.

Synthesise renders **content modes by available references** (both
intent-led; dependencies travel as explicit fail-closed run references):

- **Landscape synthesis (always — the minimum an artefact needs):** model
  prose over the referenced characterisation record, intent as emphasis
  input; typed claims deterministically validated — **pattern** (counts
  must equal the record), **cluster** (the characterise themes; softest
  interpretive grade), **gap** (screened base, graded per decision 7) and
  **reasoning** (visibly labelled). No citations — nothing chunk-anchored
  exists in this mode, and none is faked.
- **Findings-grounded synthesis (when the referenced chain includes
  extract → group): intent-led sections written by a capped agent-loop.**
  The section set derives from the **user's intent** (one bounded
  schema-constrained proposal call over intent + group summaries;
  fail-closed `context["synthesis"]` directive override; plan-compile
  sectioning = the recorded seam). Per section, the **writer is an
  agent-loop over scoped read-only tools** — the realisation
  execution-orchestration declares for synthesise: it gathers evidence
  iteratively via **`search_chunks`** (hybrid embedding-cosine + lexical,
  rank-fused, over the **selected set's** frozen units — the 009 vectors'
  first reader; the `retrieve` seam's first increment) and
  **`query_findings`**, under a hard **`SECTION_TURN_CAP`**, then emits
  typed claims spanning the full honest assertion vocabulary:
  - **finding claims** — cite finding ids → extract-verified anchors; the
    model never authors these quotes;
  - **chunk claims** — verbatim quotes from retrieved selected-set frozen
    text (select's coverage discipline inherited; the
    mechanisms/context/caveat texture the narrow IOF schema cannot carry);
  - **pattern claims** — counts must equal computed spreads (the
    direction-spread steer; v2's `effect_consensus` counts as this steer);
  - **cluster claims** — the clustering shape (facet groups here),
    validated against the referenced clustering row; softest interpretive
    grade, base-labelled;
  - **gap claims** — graded, coverage-base-carrying; base-labelled to the
    **selected/extracted base** by default; corpus-level absence **only**
    on a referenced non-`inadequate` `search_coverage_record` (else
    fail-closed degraded); inferred gaps visibly labelled, never gated;
  - **reasoning claims** — uncited, **visibly labelled Tier 4** at
    authoring, judge strict-routed, bounded per block, never in strength
    roll-ups.
  **Groups are input, not structure**: summaries steer sectioning and
  emphasis; uncovered groups counted (`groups_unsectioned`), never
  silently dropped. **Descriptive always**: no recommendations, no
  weighted verdicts (⏸ consensus seam).

Every cited claim goes through the **real `produce-grounded-block`
mechanism**: synthesise → cite → verify → write, cite/verify mandatory,
citations **co-emitted, never post-hoc**. Verify = the **deterministic
quote-presence check** against frozen chunks **plus the LLM-as-judge
grounding classifier** (single lane: exactly one of Tier 1–4 /
Unsupported-mis-cited; orthogonal weakly-grounded flag; required
rationale; "topical relevance ≠ support" — intent shapes emphasis, never
verification). Verify is a **bounded loop**: one loop-free reword-down
repair; on exhaustion a claim lands **soft-flagged, never dropped, never
silently promoted** — one hard exception: a **chunk claim whose quote
fails the presence check after repair is excluded and counted**
(fabrication is the hard-fail class). ⏸ Corpus-wide chunk grounding
(unselected documents) stays gated on the full `retrieve` slice.

This is the **first real writer of the 001 information-layer substrate**,
the **first reader of the 009 embedding-unit vectors**, the **repo's first
agent loop** (exactly one such surface — the section writer), and it ships
the run-scoped `synthesis_result` roll-up row.

## Deliverable

A PR on `task/013-synthesise` → `dev` that:

- Ships `synthesise.py`: `SynthesiseContext(scope_id, intent, context,
  characterisation_run_id, grouping_run_id=None)`; `synthesise_scope(...)`
  — characterisation load → artefact mint → landscape render (single
  intent-aware claims call → typed-claim validation → block/unit/
  annotation writes) → when `grouping_run_id` present: grouping + findings
  load → **section proposal** (validated; directive override) → per
  section: the **writer agent-loop** (tool turns ≤ `SECTION_TURN_CAP`,
  read-only `search_chunks` + `query_findings`, gathered-evidence char
  budget) → typed-claim validation (six types, per-type rules) → batched
  judge call → one loop-free reword-down repair + one re-judge →
  block/unit/annotation/citation writes → roll-up row (last statement) →
  synthesis summary in `component.completed`.
- Ships **two backend seams, four prompt surfaces**: `SynthesisBackend`
  (+ OpenAI, stub) carrying **`synthesise_landscape_v1`**,
  **`synthesise_sections_v1`** and **`synthesise_section_v1`** (the
  section writer: system prompt + the two tool schemas, versioned as one
  surface; the OpenAI form runs the bounded tool-calling loop), and
  `GroundingJudgeBackend` (+ OpenAI, stub) carrying
  **`grounding_judge_v1`** — the repo's fifth–eighth product prompts, all
  lead-authored, versioned, recorded in provenance.
- Ships the **two scoped tools**: **`search_chunks`** — hybrid retrieval
  over the selected set's stored embedding-unit vectors + lexical scoring,
  rank-fused, top-k under plan-pinned caps, id-keyed chunk records out
  (in-memory over JSONB vectors; no index, no new dependency; behind a
  swappable helper seam = the `retrieve` seam's first increment; query
  embeddings via the existing 009 `EmbeddingBackend`) — and
  **`query_findings`** — the deterministic, project-guarded findings-layer
  read (also used by the loader; **fully discharges the 012 recorded
  deviation**: the tool lands agent-invoked inside synthesise's loop,
  exactly the consumer that deferral named).
- Adds **one table — `synthesis_result`** — via one Alembic migration
  (gated change 1; table count 24 → 25, migration 13),
  project-scope-guarded.
- Registers `"synthesise"` in `COMPONENT_REGISTRY` (requires
  `evidence_scope_id` + **`characterisation_run_id`**; **`grouping_run_id`
  optional**; gated change 2); `run_harness` gains **`synthesis_backend`**
  and **`grounding_judge_backend`** (stub defaults — no default egress;
  the existing `embedding_backend` serves the retrieval queries).
- Extends `skeleton.py`: … group → **synthesise** (the terminus live); the
  live check demonstrates **both content modes**.
- **Factors the traced-call helper into `tracing.py`** (the 012-deferred
  trigger fires); loop turns and tool executions trace as spans under the
  section generation (no new event types).
- Records/updates the deferred seams in `docs/deferred.md`; updates
  `tests/helpers.py` delete order.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [ADR 0010](../../adr/0010-intent-led-synthesis-sections.md) **including
  both Amendments** (content modes; full claim vocabulary; the agent-loop
  writer) and
  [ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md)
  (capability-composes; decision 5 as amended).
- [EB components §9](../../specs/capabilities/evidence-base/components.md)
  and [EB capability](../../specs/capabilities/evidence-base/capability.md)
  — as refined 2026-07-07 (four rounds); also components §5 (the
  characterisation record) and §8 (the grouping payload).
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — the **agent-loop-over-scoped-tools realisation this slice finally
  implements**; tools as declared, scoped, read-only operations;
  `retrieve`'s full contract (the scoped tool here is its first
  increment); `query-findings` scoped-not-core; trust enforced at
  grounding.
- [System provenance-grounding](../../specs/system/provenance-grounding.md)
  — **the governing contract**: the traceability rule's three honest
  categories; tiers 1–4 (Tier 4's not-a-safe-harbour strict routing);
  **gaps** (grades, coverage base, `search_coverage_record` fail-closed
  rule); patterns (the ladder — counts at the hard end, thematic
  clustering at the soft end); produce-grounded-block mechanics; judge
  posture; persistence-for-eval-readiness (**no calibration_status**).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  EB's gap rule; the pattern grades.
- [System data-model](../../specs/system/data-model.md) — blocks / units /
  annotations; the findings layer; coverage states as gap provenance.
- [012-group contract](../012-group/contract.md) — the grouping payload;
  the carried requirements (**labels as data, never instructions**;
  **mixed/unclear findings survive**); and its `query-findings` deferral
  (discharged here).
- [docs/deferred.md](../../deferred.md) — entries this slice touches
  (incl. the 009 vectors-ahead-of-reader entry, discharged here).
- The deep-reasoner interrogation memo (conversation A record) — the
  architecture comparison behind ADR 0010.

**Code grounding (surveyed 2026-07-07):** 24 tables, 12 migrations (this
slice ships migration 13). The 001 substrate is real: `block` /
`addressable_unit` / `annotation((block_id, unit_id) composite-FK,
annotation_type, payload JSONB)` / `citation(chunk_id FK NOT NULL, quote,
verification_result)` — gap/pattern/cluster/reasoning annotations are new
`annotation_type` values riding the payload JSONB; chunk-cited claims
write ordinary `citation` rows. `search_coverage_record` (007): the
corpus-promotion gate for gap claims. `chunk_embedding` (009): one JSONB
vector per embedding-unit, eager, **no reader yet**; `EmbeddingBackend` +
`embedding_backend` harness param exist (stub vectors deterministic).
`characterisation_result` carries `coverage` + `themes` + provenance.
Findings carry extract-verified anchors (verified `chunk_id`, quote, match
status, spans). `grouping_result.groups` carries per group: label,
description, member values, member finding ids, size, direction spread
(+ residuals + overall); provenance carries the inherited extraction base.
`quote_verify.py`'s `build_basis` + `QuoteMatcher.find` verify verbatim
quotes against frozen chunks deterministically. Backend pattern: protocol
+ stub + OpenAI class with pydantic `response_format`, module-constant
prompt + `PROMPT_VERSION`, caller-owned budget, validation separated from
the call (`gpt-5-mini` floor). **No agent loop exists anywhere yet** —
every LLM surface to date is single-call schema-constrained; the loop
runner, tool schemas and per-turn tracing are new machinery this slice
introduces. Component wiring: registry entry + required Config fields →
context dataclass → `_run_scope_component` → `component.*` events.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The complete produce-grounded-block mechanism lands in one slice** —
   deterministic quote-presence **and** the LLM judge **and** the bounded
   loop-free reword-down repair. Judge *calibration* stays eval-workstream
   territory; this slice's bar is mechanism correctness.
2. **Blocks are real information-layer rows at claim grain, in both
   content modes.** Per block: one `block` row (claims' prose joined
   deterministically; `content_hash` per 001), one `addressable_unit` per
   claim, and per claim-unit the annotation its type demands: **citation
   annotation** (finding/chunk claims), **pattern annotation** (validated
   counts + grade + base), **cluster annotation** (the referenced
   clustering + softest-grade label + base), **gap annotation** (grade +
   coverage base + evidence refs), **reasoning annotation** (visible
   Tier-4 label + the judge's strict-routing verdict). `citation` rows
   link cited claim-units to frozen chunks.
3. **Synthesise mints the artefact — one per run, titled from the scope
   intent** (verbatim, bounded, deterministic) — and binds blocks in
   section order (landscape first). Composition conventions stay at their
   seams. Re-run = new run = new artefact + new blocks. Empty
   characterisation → honest skip (roll-up + flag, no artefact).
4. **Landscape synthesis: one intent-aware call, deterministically
   validated, judge-free except reasoning claims.**
   `synthesise_landscape_v1` (+ ≤1 repair): intent + the record + the
   scope's `search_coverage_record` summaries as id-keyed data. Claims:
   pattern · cluster (themes) · gap (screened base) · reasoning. Anything
   else rejects.
5. **Findings-grounded synthesis opens with an intent-led section
   proposal.** `synthesise_sections_v1` (+ ≤1 repair): intent + group
   summaries → validated section list (1..`SECTION_CAP`; bounded
   non-generic titles/focus; `group_ids` ⊆ real groups, overlap allowed,
   exhaustiveness not required; uncovered groups → `groups_unsectioned`).
   A fail-closed **`context["synthesis"]` directive** can supply the list
   (the plan-shaped-sections seam's compile target); executed source
   recorded.
6. **The section writer is a capped agent-loop over two scoped read-only
   tools — the repo's first agent loop, and exactly one such surface.**
   Per section, the `synthesise_section_v1` surface (system prompt + tool
   schemas, one versioned unit) runs a bounded tool-calling loop seeded
   with (id-keyed data): intent, section spec, assigned groups' member
   findings, the section's computed spread, coverage-record summaries.
   Tools:
   - **`search_chunks(query, k?)`** — hybrid retrieval over the **selected
     set only**: query embedded via the existing `EmbeddingBackend`;
     embedding-cosine over the stored unit vectors (in-memory JSONB, ~10³
     scale) rank-fused with a lexical score; top-k under plan-pinned
     `SYNTH_CHUNK_TOP_K` / per-section gathered-context
     `SYNTH_CHUNK_CHAR_BUDGET`; id-keyed frozen chunk records out.
     Deterministic given stored vectors + query. Behind a swappable helper
     seam — the **`retrieve` seam's first increment** (grounding profile,
     selected-set scope), upgraded not duplicated by the future retrieve
     slice; also the 009 vectors' **first reader** (that deferred entry is
     discharged).
   - **`query_findings(...)`** — identifier-addressed, side-effect-free,
     project-guarded findings-layer reads (the 012 deferral's named
     consumer — **discharged in full**, agent-invoked).
   Loop bounds, all plan-pinned and enforced in code, not prompt:
   `SECTION_TURN_CAP` generation turns per section (tool calls consume
   turns; the final claims emission is a turn), per-call and per-section
   result budgets, tool set closed (an unknown tool name is a validation
   error, never executed), **read-only always** (tools cannot write, and
   they see only this project's selected set). Cap exhaustion forces the
   claims emission with whatever was gathered — never an unbounded loop,
   never a silent failure. Every turn and tool execution traces as spans;
   gathered chunk ids land in provenance.
7. **Six claim types, each with its own deterministic validation; the
   writer never authors a finding quote.** As rev 4, with cluster claims
   replacing theme claims:
   - **finding** — `cited_finding_ids ⊆ the section's finding set`; code
     resolves to extract-verified anchors and re-runs the deterministic
     presence check (abstract-basis re-location; unlocatable/`failed`
     anchors → no fabricated citation row, `quote_unverified`,
     weakly-grounded cap, never dropped).
   - **chunk** — verbatim quote + source chunk record id **from the
     gathered tool results only** (citing an id never returned by a tool
     call rejects — co-emission enforced structurally); claimed location
     untrusted — `QuoteMatcher` verifies against the whole document basis,
     verified spans become the citation rows; presence failure rejects
     (one repair), still-failing → **excluded and counted**.
   - **pattern** — stated counts must equal the computed spread/record.
   - **cluster** — references the clustering by id (facet groups /
     landscape themes), validated against the referenced row; softest
     interpretive grade, base-labelled.
   - **gap** — grade + coverage base required; corpus-level phrasing
     fail-closed on a non-`inadequate` `search_coverage_record` (else
     degraded and counted); acknowledged-gap sparsity validated
     numerically; inferred gaps visibly labelled;
     `not_selected`/`not_extracted` never license absence.
   - **reasoning** — uncited, visibly Tier-4-labelled, bounded per block,
     judge strict-routed, never in roll-ups.
   No silent uncited path: every claim is cited, validated, or visibly
   labelled.
8. **The judge is `grounding_judge_v1`, batched per block, single-lane,
   reading the cited passages.** Judges cited claims (full lane; input
   includes the cited chunks' full frozen text — `synthesis_envelope_v1`)
   and reasoning claims (strict-routing only). Pattern/cluster/gap claims
   are deterministically validated, not judged. Persistence for
   eval-readiness on the annotation payload; full I/O on Langfuse; **no
   calibration_status anywhere**.
9. **Repairs are bounded, loop-free, and reword down.** Landscape and
   section proposal: one regeneration on validation rejection. Per
   section: one reword-down regeneration **over the already-gathered
   evidence** (no new tool calls) on validation rejection or any
   `unsupported_mis_cited`, then one re-judge. Call budget known pre-run
   as a **maximum**: landscape ≤ 2 · sections ≤ 2 · per section ≤
   `SECTION_TURN_CAP` + 2 generation calls + ≤ `SECTION_TURN_CAP`
   embedding calls → total ≤ 4 + `SECTION_CAP` × (`SECTION_TURN_CAP` + 2)
   generation calls. Backend failure after retries fails the component
   honestly (`component.failed`, no roll-up row); blocks already written
   remain and the failure payload names them.
10. **Descriptive, never evaluative — absence disciplined, not banned.**
    Negative rules deterministically assertable on the built prompts; the
    citable-bar flag-not-block rule honoured by the weakly-grounded
    mechanism (policy-conditioned flagging = recorded seam).
    **Mixed/unclear findings are first-class throughout.**
11. **`query-findings` is discharged in full** — the scoped read tool
    lands agent-invoked inside synthesise's loop, exactly as the 012
    deferral recorded; the deferred.md entry is closed as landed (the
    orchestrator-level capability-run architecture remains its own,
    separate seam).
12. **Component wiring mirrors 004–012.** `"synthesise"` requires
    `evidence_scope_id` + `characterisation_run_id`; `grouping_run_id`
    optional (present → findings-grounded synthesis; absent →
    landscape-only, flagged) — compile-fail-closed; missing referenced
    rows → structural failure. Roll-up row last; re-run → new run_id;
    same-run re-execution loud; `component.completed` carries the
    summary; **no new event types** (loop turns are trace spans, not
    events).
13. **Stubs are sentinel-driven; the suite is deterministic and
    egress-free.** `StubSynthesisBackend` drives **scripted tool-call
    sequences** through the real loop runner (fixture-declared turns:
    search queries, findings reads, then claims — exercising the cap, the
    unknown-tool rejection, the gathered-context budget and cap-exhaustion
    forcing for real) and emits typed claims across all six types (real
    anchor text, real record numbers, fabricated-quote and corpus-absence
    sentinels); `StubGroundingJudgeBackend` sentinel-driven; retrieval
    runs on 009's deterministic stub vectors. Determinism tests fix intent
    as input.
14. **All four prompt surfaces carry the standing injection posture — and
    the loop tightens it.** Intent, characterisation content,
    coverage-record summaries, finding text, anchor quotes, retrieved
    chunk text and group labels enter as **id-keyed JSON data records**;
    responses and tool calls schema-constrained; the tool set is closed,
    read-only, selected-set-scoped and code-enforced. Hijack bounds: a
    hijacked writer can call read-only tools more (cap-bounded) and emit
    mis-claims (validation + presence + judge); retrieved adversarial
    chunk text can only surface in-corpus frozen text that then faces the
    same claim bar; a hijacked judge mis-tiers within a closed enum; a
    hijacked proposal mis-shapes sections whose every claim is still
    verified. **No tool writes; no egress verb exists in the tool set**
    (`search` remains acquire's alone).

### Schema

**Gated change 1 — one new table** (one migration; table count 24 → 25;
exact DDL plan-pinned, shape here binding):

```
synthesis_result  synthesis_result_id PK · project_id FK→project
                  · evidence_scope_id · run_id
                  · characterisation_run_id (executed reference, NOT NULL)
                  · grouping_run_id (executed reference, NULLABLE)
                  · artefact_id FK→artefact NULLABLE (NULL only on the
                      empty-characterisation honest skip)
                  · synthesis_provenance JSONB NOT NULL (all four prompt-
                      surface versions, models, judge envelope-policy
                      version, backend modes, per-mode call/turn/repair
                      counts, the section set + source
                      [proposal|scope_context] + caps
                      (SECTION_CAP · SECTION_TURN_CAP · SYNTH_CHUNK_TOP_K
                      · SYNTH_CHUNK_CHAR_BUDGET), per-section tool-call
                      counts + gathered-chunk-id hash, and the inherited
                      chain base: characterisation reference + record
                      summary hash; when findings-grounded —
                      grouping_run_id + facet + group count + finding-set
                      size/sha256 + the extraction base carried through)
                  · blocks JSONB NOT NULL (the landscape block entry + per
                      section: title/focus, block_id, assigned group ids,
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
                      findings_total, groups_total, groups_unsectioned)
                  · flags JSONB NOT NULL (landscape_only ·
                      empty_characterisation · groups_unsectioned ·
                      unsupported_claims_present · weakly_grounded_present
                      · chunk_claims_rejected · gap_claims_degraded ·
                      turn_cap_hit · repair_path_taken — where true)
                  · created_at
                  Composite FKs (evidence_scope_id, project_id),
                  (run_id, project_id) — cross-project guards
                  FK (evidence_scope_id, characterisation_run_id) →
                      characterisation_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, grouping_run_id) →
                      grouping_result (evidence_scope_id, run_id)
                  UNIQUE (evidence_scope_id, run_id)
```

No existing-table changes. Downgrade drops the table. `tests/helpers.py`
`delete_project_data` gains it in FK-safe order.

### Out of scope

- **Corpus-wide chunk-grounded narrative** and the **full `retrieve`
  tool** (index-backed hybrid corpus-wide retrieval with profiles) — the
  scoped `search_chunks` tool is the recorded first increment behind a
  seam the retrieve slice upgrades.
- **Agent loops anywhere else** — exactly one loop surface ships (the
  section writer); landscape, proposal and judge stay single-call; the
  orchestrator-level capability-run architecture stays its own seam.
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
  correctness (named so the review stack doesn't mistake machinery tests
  for a quality claim).

## Constraints & approval gates

**Four gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table
   count 24 → 25. No existing-table changes.
2. **Public interface** — the `"synthesise"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `characterisation_run_id` (required) and
   `grouping_run_id` (optional) + `run_harness` gains optional
   **`synthesis_backend`** and **`grounding_judge_backend`** (stub
   defaults). No renames ride this slice.
3. **Runtime egress — four new generation surfaces + embedding-query
   use** (the repo's fifth–eighth product prompts; embeddings egress
   opened in 009 — this adds tool-query text to that surface):
   `synthesise_landscape_v1` · `synthesise_sections_v1` ·
   `synthesise_section_v1` (**multi-turn**: each loop turn is a
   generation call carrying gathered selected-set chunk text — the 011
   source-text class, relevance-ranked) · `grounding_judge_v1` (cited
   chunks' full frozen text). Fixture corpus openly licensed; full-I/O
   Langfuse traces flagged for approval.
4. **The repo's first agent loop** — a capability-class change beyond any
   single surface: the section writer gains bounded tool-calling
   discretion (closed read-only tool set, hard turn cap, code-enforced
   scope). Every prior contract declared "no agent loop, no tools" —
   this contract deliberately crosses that line for exactly one surface,
   per the spec's own declared realisation and ADR 0010's second
   amendment.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic`
cover it; cosine + lexical scoring are stdlib/in-memory).

**Explicitly not crossed:** exactly four prompt-bearing surfaces and
exactly one loop surface; no tool writes; no egress verb in the tool set;
no new dependency; no auth/tenancy/CI change; no existing-table change; no
new event types; no tag writes; no retrieval index/extension.

**Spec flow-backs: already landed with ADRs 0009 + 0010 (both
amendments)** — approved in this contract's gate conversation. Remaining
deferrals ride `docs/deferred.md`.

## Public / private boundary

- On the live path, what leaves: the characterisation record's content,
  coverage-record summaries, group summaries, per-section finding records
  (source-named references, statistics, **verbatim quotes**),
  **tool-retrieved frozen chunk text from selected documents**
  (accumulating across loop turns), cited chunks' text, the user's
  **intent** (also as tool-query text to the embedding API), and
  model-generated labels — all fixture-corpus-derived (openly licensed by
  construction) — to the OpenAI API; full-I/O traces (including every
  loop turn and tool result) to the user-operated dev Langfuse. For
  arbitrary future corpora this is source-derived text and user-authored
  intent inheriting the project's sensitivity class — private-by-default
  otherwise.
- Committed artifacts (schema, prompt text, tool schemas, roll-up shapes,
  verification counts) are public-safe. **Block content, claims, section
  titles/focus, gap texts, tool queries and judge rationales are
  model-generated text over source-derived input** — public-safe for the
  fixture corpus, private-by-default otherwise; **untrusted model output
  as data**: bounded and validated at write, rendered escaped, never
  executed. Carried forward: block content, section specs and judge
  rationales enter any future prompt as data records, never instructions.

## Model route

All four generation surfaces behind the two backend seams —
`gpt-5-mini`-class floor (the 009 nano lesson binding) → Bedrock at the
seam swap, unchanged. Tool-query embeddings ride the existing 009
embedding surface.

- **`synthesise_landscape_v1`** — landscape prose; typed claims (pattern |
  cluster | gap | reasoning); descriptive only, numbers as given, absence
  only as graded gap claims.
- **`synthesise_sections_v1`** — the section proposal; bounded list out;
  sections name aspects of the question and the evidence, never verdicts.
- **`synthesise_section_v1`** — the section writer **agent-loop surface**
  (system prompt + `search_chunks`/`query_findings` tool schemas,
  versioned as one unit); typed claims (finding | chunk | pattern |
  cluster | gap | reasoning); negative rules: descriptive only; absence
  only as graded gap claims with their base; spreads as given;
  mixed/unclear reported, never aggregated away; quotes verbatim from
  tool-returned text only; claim within what the cited evidence supports;
  gather before writing, stop gathering when saturated (the cap enforces
  it regardless).
- **`grounding_judge_v1`** — the classifier; closed verdict enum +
  `weakly_grounded` + required rationale for cited claims; strict-routing
  for reasoning claims; topical relevance ≠ support.

All four are **prompt-bearing, lead-authored, versioned** (tool schemas
included in the versioned surface), recorded in provenance, event payloads
and (judge) annotation payloads. The judge rubric is lead-only per
AGENTS.md.

## Disciplines binding this slice

- **The traceability rule is the slice** — every claim is
  cited-and-verified, deterministically validated, or visibly labelled;
  no fourth state, no silent promotion, no post-hoc citation path. Intent
  and tool discretion shape emphasis and evidence-gathering, never
  verification.
- **Honest absence** — absence only as graded gap claims with their
  coverage base; corpus-level fail-closed on the coverage record;
  `not_selected`/`not_extracted` never license absence.
- **Flag, don't drop** — failed anchors, unsupported/weakly-grounded
  claims, degraded gaps, uncovered groups and cap-forced emissions land
  visible with status; the one exclusion is fabricated chunk quotes —
  excluded **and counted**.
- **Bounded agency** — one loop surface; closed read-only tool set;
  code-enforced caps; cap exhaustion forces emission, never extends.
- **Deterministic where claimed** — presence checks, citation resolution,
  offsets, spreads, per-type validation, tool ranking (given stored
  vectors + query), cross-checks, ordering and writes; generation calls
  bounded by the pre-run maximum; determinism tests fix intent as input.
- **Model only what behaves** — no consensus fields, no summary columns,
  no calibration_status; the roll-up row and the 001 substrate rows are
  the only new state.
- **Never silent, never fake** — stubs say so; missing upstream state
  fails structurally; a failed call fails the component honestly;
  grouping↔findings and spread mismatches are structural failures.

## Stop conditions

- Any gated change (schema · public interface · egress · the agent loop)
  not yet approved, or any change beyond them (existing-table change, a
  fifth prompt surface, a second loop surface, a new or write-capable
  tool, new dependency, retrieval index/extension, consensus/summary
  machinery, new event types).
- Any *suite or library-default* code path would perform network I/O.
- The loop wants more than the two read-only tools, wants to write, wants
  the unselected corpus, or wants an uncapped turn budget — halt.
- The synthesis wants evaluative output, free-phrased absence, or
  composition conventions — halt.
- The claim/citation model can't express something without weakening
  verification — design change; halt, never weaken the bar silently.
- `make verify` red with unclear root cause; or the turn/token budget is
  spent.

## Acceptance checks

- `make verify` — green, deterministic, zero egress (socket-deny covers
  synthesise round-trips in both modes including the scripted stub loop).
- **One manual live check, both content modes** (evidence in
  verification.md): skeleton end-to-end with `OPENAI_API_KEY`
  (+ `LANGFUSE_*`) against the fixture corpus — (a) a **full run**:
  intent-led sections proposed; the writer loop visibly gathering
  (per-section tool-call counts, queries and gathered chunk ids recorded);
  all claim types present with real citations to frozen chunks; tier
  distribution, gap grades/bases, degradations/exclusions and any
  `turn_cap_hit` shown honestly; repair path exercised or its absence
  noted; `groups_unsectioned` honest; (b) a **landscape-only run**:
  artefact + landscape block written, flag set. All four surfaces + tool
  turns + embedding queries visible in dev Langfuse (versions,
  tokens/cost) with run-level scores (claims-valid share,
  citation-verified share, unsupported share, chunk-rejection share);
  per-run counts and an honest cost note; keys absent from captured
  output.
- Deterministic vs AI eval: suite checks deterministic (stubs; scripted
  loop); section quality, prose quality, retrieval quality and judge
  calibration are eval territory — this slice's bar is mechanism
  correctness, invariant enforcement, honest flags and provenance
  fidelity.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 25.
- Named test results: **mode selection** (characterisation_run_id
  required; grouping_run_id absent → landscape-only + flag; missing
  referenced rows → structural failure), **landscape validation** (wrong
  pattern numbers rejected; cluster claims validated against themes; gap
  grades enforced; disallowed types rejected; empty characterisation →
  honest skip, no artefact), **section proposal validation** (caps,
  bounded non-generic titles, real group_ids, `groups_unsectioned`
  counted, malformed directive fails closed, source recorded), **the
  agent loop** (turn cap enforced — cap exhaustion forces emission with
  gathered evidence + `turn_cap_hit`; unknown tool name → validation
  error, never executed; tools read-only and selected-set-scoped — a
  foreign project's or unselected document's chunks/findings never
  returned; per-call and gathered-context budgets enforced; tool-call
  counts + gathered-chunk-id hash in provenance; scripted stub sequences
  drive the real loop runner), **`search_chunks` ranking** (hybrid
  fusion deterministic on stub vectors; top-k and char budgets enforced),
  **finding-claim citation resolution** (ids ⊆ section findings; anchors
  reused verbatim; abstract-basis re-location; failed/unlocatable anchors
  → `quote_unverified` + weakly-grounded cap, never dropped),
  **chunk-claim verification** (quotes only from tool-returned ids —
  citing an unreturned id rejects; presence-checked against the whole
  document basis; verified spans become the citation rows; fabricated
  quote → reject, one repair, then excluded and counted), **gap-claim
  discipline** (corpus-level phrasing without a non-`inadequate`
  coverage record → fail-closed degradation, counted; acknowledged
  sparsity validated numerically; inferred labelled; base always
  present), **cluster-claim discipline** (referenced clustering ids
  validated; softest-grade label + base present), **reasoning-claim
  discipline** (visibly labelled; strict-routing sentinel flagged;
  per-block count bounded), **claim/unit integrity** (every cited claim
  ≥ 1 citation target; annotations exist iff their claim does, on that
  claim's unit; offsets exact; composite-FK integrity; content_hash
  correct), **judge semantics** (single-lane enum; rationale required;
  verdict + judge provenance + envelope version persisted; judge input
  includes cited chunk text; cited and reasoning claims judged;
  pattern/cluster/gap not judged), **repair semantics** (loop-free — no
  new tool calls on repair, test-asserted; bounded exactly as decision 9;
  budgets test-asserted; exhaustion → flags, claims retained except
  fabricated chunk quotes), **flag-not-drop** (unsupported /
  weakly-grounded / degraded-gap claims persist visibly; mixed/unclear
  visible end-to-end), **descriptive posture** (negative rules asserted
  on all four built surfaces; injection-shaped labels, quotes, chunk text
  or coverage summaries land as inert data — including inside
  tool-returned text), **artefact/composition v1** (one artefact per run,
  intent-derived bounded title; section-ordered binding; re-run → new
  artefact; same-run re-execution loud; backend failure →
  `component.failed`, no roll-up row, prior blocks named),
  **determinism** (two stub runs with fixed intent → identical payload
  columns, block content and hashes; tool ranking deterministic),
  **provenance required keys** (four surface versions, envelope policy,
  section set + source, all caps, per-section tool-call counts +
  gathered-chunk-id hash, per-mode call counts, the inherited chain
  base), delete-order integrity.
- Live-run evidence per the manual check above (both modes).
- Public-safety confirmation (egress was fixture-corpus text + intent
  only; traces on the user-operated instance; keys clean).
- Deferred seams recorded/updated in `docs/deferred.md`: **corpus-wide
  chunk-grounded narrative** + **full `retrieve` tool** (the
  `search_chunks` tool = its first increment; upgrade path recorded; the
  009 vectors-ahead-of-reader entry discharged) · **`query-findings`
  entry closed as landed** (agent-invoked in synthesise's loop — its
  named consumer; orchestrator-level capability-run architecture stays
  its own seam) · **plan-compile section machinery** (directive = compile
  target) · **composition conventions** · policy-conditioned citable-bar
  flagging · consensus roll-up (never-contribute constraints restated
  incl. gaps + reasoning) · block summaries + faithfulness judging ·
  judge-envelope widening + re-gather repair (with `retrieve`) ·
  synthesis/judge/retrieval quality evals (envelope, SECTION_CAP,
  SECTION_TURN_CAP and top-k calibration).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate, four new generation surfaces plus
embedding-query use ride the slice, and it deliberately crosses a standing
line: **the repo's first agent loop** (gated change 4). This is the trust
invariant's landing slice, now carrying the full honest-assertion
vocabulary and bounded agency. Contract- and plan-stage adversarial
reviews standard; review stack sized per the review-economy notes; the
security lane's headline target is the loop (tool scope, caps,
injection-through-retrieved-text). ADRs 0009 + 0010 (both amendments)
cover the architecture.

Review focus:
- **Provenance/honesty (the headline lane)**: co-emitted citations only
  (chunk claims cite only tool-returned ids); presence checks for both
  cited claim kinds; verified spans become citation rows; single-lane
  verdicts persisted; pattern/cluster/gap numbers deterministically
  validated; the gap fail-closed corpus-promotion rule; reasoning claims
  visibly labelled and strict-routed; unsupported/weak/degraded claims
  flagged never dropped; fabricated chunk quotes excluded and counted;
  mixed/unclear survive; uncovered groups counted; cap-forced emissions
  flagged; intent and tool discretion never touch verification;
  provenance carries the inherited chain base per mode.
- **Security / the loop (the second headline)**: closed read-only tool
  set, code-enforced scope (this project, selected set only), hard turn
  and result caps, unknown-tool rejection, no egress verb; injection
  through retrieved frozen text bounded to more reading + mis-claims that
  face the unchanged claim bar; four prompt surfaces consuming untrusted
  text as id-keyed data records; outputs bounded and validated at write;
  key hygiene; socket-deny on suite paths.
- **Correctness**: mode/reference resolution; section validation; loop
  runner semantics (turn accounting, budget enforcement, cap-exhaustion
  forcing, loop-free repair); hybrid ranking determinism; citation
  resolution across verified/abstract/failed anchors and chunk quotes;
  per-type validation; offsets; composite-FK integrity; roll-up-last
  ordering; FK and delete order.
- **Scope**: one loop surface only; no corpus-wide retrieval or index; no
  composition conventions; no consensus/summary machinery; no fifth
  prompt; suite egress-free.
