# Task contract: 013-synthesise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 2) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: [0009](../../adr/0009-capability-composes-synthesise-terminus.md) —
> Accepted 2026-07-07 (the terminus architecture; a further step-4 ADR covers
> implementation-level produce-grounded-block decisions if judged
> consequential beyond 0009).
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft — synthesise as deep-only content
>   producer per the then-current spec reading.
> - **rev 1.1** (2026-07-07, user challenges at the gate — adjudicated):
>   **(a) artefact title intent-derived** (bounded verbatim scope intent,
>   deterministic, never generic). **(b) pattern annotations claim-driven** —
>   claims are typed; a pattern annotation exists only where a claim asserts
>   the evidence shape, on that claim's unit, its counts validated
>   deterministically against the code-computed spread. **(c) judge envelope
>   widened to the cited chunks' full frozen text** (deterministic lookup,
>   `synthesis_envelope_v1`). **(d) retrieval position made explicit**
>   (findings-bounded by design; re-gather repair + envelope widening = seams
>   landing with `retrieve`). **(e) clarity fixes** (finding ids defined;
>   presence-check re-run rationale; depth axis stated).
> - **rev 2** (2026-07-07, user spec-challenge at the gate → **spec
>   refinement + [ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md)**,
>   superseding rev 1's framing): **(a) capability-composes** — every
>   capability sub-agent composes its own artefact; the orchestrator shapes
>   sections at plan time only. **(b) synthesise = EB's terminal component at
>   every depth** — landscape rendering always, grounded finding-blocks when
>   the deep chain ran, artefact minting + block binding folded in (a
>   separate compose component rejected as one-capability structure).
>   **(c) components are a library; breadth ⊥ depth** — explicit fail-closed
>   run references carry the structural dependencies; a targeted question
>   compiles to a narrow-and-deep run. **(d) landscape rendering = model
>   prose, pattern-validated** — a third prompt surface
>   (`synthesise_landscape_v1`). **(e) direct chunk-grounded artefact prose
>   sanctioned** (user decision over the drafted recommendation; trade
>   recorded in ADR 0009) — a ⏸ seam landing with `retrieve`, **not built
>   here**. Registry reference becomes `characterisation_run_id` (required) +
>   `grouping_run_id` (optional); schema and budgets reshaped accordingly.
>   Specs updated: capability.md, components §§5/6/9,
>   execution-orchestration; spec log 2026-07-07.

## Goal

Add **synthesise** — EB component 9 and, per
[ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md), **EB's
terminal component at every depth**: the component that **composes the one EB
artefact** — mints it, renders content into grounded blocks, binds them. The
orchestrator shapes the artefact at plan time (sections, facets, depth);
composition itself is capability expertise and happens here.

What it renders depends on what the run produced (the components are a
library; dependencies travel as explicit fail-closed run references):

- **Landscape path (always — the minimum content an artefact needs):**
  model-written prose over the referenced characterisation record (coverage,
  themes). Shape-asserting claims are **deterministically validated against
  the record**; no source citations at this grade — none exist, none are
  faked.
- **Grounded findings path (when the deep chain ran):** over the named groups
  of the referenced grouping run, **per group produce a grounded block**
  reporting what that group's findings show — **descriptive** (the
  direction-spread steer; never a weighted verdict — the ⏸ consensus seam;
  never a recommendation; **never an absence claim**, deep coverage being
  base-labelled and never promoted to corpus absence).
- ⏸ **Direct chunk-grounded narrative** (sanctioned by ADR 0009 for targeted
  pre-findings answers, full produce-grounded-block bar, visibly
  chunk-cited): **not built here** — lands with `retrieve`, its
  chunk-selection substrate.

The findings path's centre of gravity is the **real
`produce-grounded-block` mechanism** (system provenance-grounding):
synthesise → cite → verify → write, with **cite and verify mandatory**.
Citations are **co-emitted, never post-hoc**. Verify = the **deterministic
quote-presence check** against frozen chunks **plus the LLM-as-judge
grounding classifier** (single lane: exactly one of Tier 1–4 /
Unsupported-mis-cited; orthogonal weakly-grounded flag; required free-form
rationale). Verify is a **bounded loop** whose primary repair **rewords the
claim down**; on exhaustion a claim lands **soft-flagged, never dropped,
never silently promoted**. The walking skeleton (001) shipped the
deterministic leg as a stub; this slice lands the settled mechanism.

This is the **first real writer of the 001 information-layer substrate**:
real `block` / `addressable_unit` / `annotation` / `citation` rows at claim
grain, plus the run-scoped `synthesis_result` roll-up row (the 009–012
precedent).

## Deliverable

A PR on `task/013-synthesise` → `dev` that:

- Ships `synthesise.py`: `SynthesiseContext(scope_id, intent, context,
  characterisation_run_id, grouping_run_id=None)`; `synthesise_scope(...)` —
  characterisation load → artefact mint (intent-derived title) → landscape
  render (claims call → typed-claim validation → block/unit/annotation
  writes) → when `grouping_run_id` present: grouping load → member-finding
  load (via `query_findings`) → per named group: claims call → citation
  resolution against extract-verified anchors → deterministic presence
  re-check → batched judge call → one bounded reword-down repair →
  block/unit/annotation/citation writes → roll-up row write → synthesis
  summary in `component.completed`.
- Ships **two backend seams, three prompts** (the standing backend pattern):
  `SynthesisBackend` (+ OpenAI, stub) carrying **`synthesise_landscape_v1`**
  and **`synthesise_block_v1`**, and `GroundingJudgeBackend` (+ OpenAI, stub)
  carrying **`grounding_judge_v1`** — the repo's fifth, sixth and seventh
  product prompts, all lead-authored, versioned, recorded in provenance.
- Ships **`query_findings`** — the scoped, deterministic, project-guarded
  findings-layer read surface, used by the findings path's loader
  (discharges the 012 recorded deviation on its stated terms — decision 9).
- Adds **one table — `synthesis_result`** — via one Alembic migration (gated
  change 1; table count 24 → 25, migration 13), project-scope-guarded.
- Registers `"synthesise"` in `COMPONENT_REGISTRY` (requires
  `evidence_scope_id` + **`characterisation_run_id`**; **`grouping_run_id`
  optional** — both explicit fail-closed references; gated change 2);
  `run_harness` gains **`synthesis_backend`** and
  **`grounding_judge_backend`** (stub defaults — no default egress).
- Extends `skeleton.py`: … group → **synthesise** (the chain's terminus
  live), rendering the synthesis summary; the live check demonstrates
  **both** paths (a landscape-only synthesise run and a full deep run).
- **Factors the traced-call helper into `tracing.py`** — the 012-deferred
  trigger fires (backends four and five land here); the three existing
  OpenAI backends and the two new ones share the factored shape.
- Records/updates the deferred seams in `docs/deferred.md` (incl. re-scoping
  the artefact-composition entry per ADR 0009 and adding the chunk-grounded
  seam); updates `tests/helpers.py` delete order.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md) —
  the terminus architecture this contract implements (capability-composes;
  synthesise terminal at every depth; library model, breadth ⊥ depth; the
  sanctioned chunk-grounded seam and its recorded trade).
- [EB components §9 — synthesise (run terminus)](../../specs/capabilities/evidence-base/components.md)
  — as refined 2026-07-07: the two built paths + the ⏸ chunk-grounded mode +
  the ⏸ consensus seam; also §5 (characterise = landscape content producer;
  what the characterisation record carries) and §8 (what group wrote).
- [System provenance-grounding](../../specs/system/provenance-grounding.md) —
  **the governing contract**: traceability rule, tiers 1–4,
  Unsupported/mis-cited as failure state, weakly-grounded orthogonal,
  produce-grounded-block mechanics (co-emitted citations, two-part verify,
  bounded reword-down repair), judge posture, persistence-for-eval-readiness
  (**no calibration_status**), pattern grades (metadata-grounded strongest;
  finding-query middle; interpretive shape softest), summaries outside the
  grounding economy.
- [EB capability](../../specs/capabilities/evidence-base/capability.md) — as
  refined: output structure (orchestrator shapes at plan time; synthesise
  composes), library model + breadth/depth independence, scope boundaries
  (evidence-descriptive, no recommendations), cluster persistence.
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  the gap rule (nothing here may phrase `not_selected`/`not_extracted` as
  absence), pattern grades, flag-not-block at synthesise.
- [System data-model](../../specs/system/data-model.md) — block / unit /
  annotation-layer semantics; the findings layer; versioning grains (block
  machinery beyond `version=1` is not this slice).
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — as refined: the capability-composes rule; `produce-grounded-block` in
  the universal core; `query-findings` scoped-not-core; trust enforced at
  grounding.
- [012-group contract](../012-group/contract.md) — pattern precedent and the
  carried-forward requirements binding here: **group labels/descriptions
  enter prompts as data records, never instructions**; **mixed/unclear
  findings survive the whole deep chain**.
- [docs/deferred.md](../../deferred.md) — entries this slice touches:
  `query-findings` (012 deviation — lands here), traced-call helper (trigger
  fires), EB artefact composition (re-scoped by ADR 0009), consensus (⏸),
  graph-structured synthesis (⏸).

**Code grounding (surveyed 2026-07-07):** 24 tables, 12 migrations (this
slice ships migration 13). The 001 substrate exists and is real:
`block(artefact_id FK NOT NULL, version, content, content_hash)` ·
`addressable_unit(block_id, unit_type, locator JSONB, content)` ·
`annotation((block_id, unit_id) composite-FK, annotation_type, payload
JSONB)` · `citation(annotation_id FK, chunk_id FK NOT NULL, quote,
verification_result)`. `grounding.py` is the walking-skeleton deterministic
leg (judge explicitly "a deferred seam"); the echo component mints its own
`artefact` row (harness.py:88–96) — the container precedent decision 3
extends. `characterisation_result` (`UNIQUE (evidence_scope_id, run_id)` —
the FK target) carries `coverage` JSONB + `themes` JSONB (names,
descriptions, member ids, sizes, the unclustered set) + provenance. Findings
carry extract-verified anchors (`extract.py:650`): `segment_id` (untrusted
claim, never dereferenced) · **`chunk_id` (verified location — None when
unverified or abstract-basis)** · `quote` · `match_status` ·
`quote_verified` · `spans[{chunk_id, start, end}]`. `grouping_result.groups`
carries per named group: label, description, member values, **member finding
ids**, size, direction spread (+ residuals + overall);
`grouping_provenance.extraction_base` carries the inherited fingerprint,
base-ladder counts, finding-set size + sha256. Backend pattern: protocol +
stub + OpenAI class with pydantic `response_format`, module-constant prompt
+ `PROMPT_VERSION`, caller-owned budget, validation separated from the call
(`gpt-5-mini` floor — the 009 nano lesson). Component wiring: registry entry
+ required Config fields → context dataclass → `_run_scope_component` →
`component.*` events; `skeleton.py` threads upstream run ids and switches
stub/live on `OPENAI_API_KEY`.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The complete produce-grounded-block mechanism lands in one slice** —
   deterministic quote-presence **and** the LLM judge **and** the bounded
   reword-down repair, on the findings path. Shipping tier-less annotations
   would re-migrate annotation semantics one slice later and put ungrounded
   prose on the trust path with no classifier. Judge *calibration* stays
   eval-workstream territory; this slice's bar is mechanism correctness.
2. **Blocks are real information-layer rows at claim grain, on both paths.**
   Per block: one `block` row (content = the claims' prose, joined
   deterministically; `content_hash` per the 001 convention), one
   `addressable_unit` per claim (`unit_type="text_span"`, locator = computed
   char offsets), and per claim-unit the annotation its claim type demands:
   **citation annotation** for finding-citing claims (cited finding ids,
   per-citation verification, judge verdict — tier / weakly_grounded /
   rationale / judge provenance), **pattern annotation** for shape-asserting
   claims (the deterministically validated shape + its grade and base),
   **theme annotation** for landscape theme-descriptive claims (theme id
   reference, interpretive-shape grade). `citation` rows link finding-claim
   units to the frozen chunks their quotes live in.
3. **Synthesise mints the artefact — one per run, titled from the scope
   intent** (verbatim, length-bounded, control-characters stripped,
   deterministic — never generic, never a model call) — and binds its blocks
   to it: **v1 composition** = artefact row + deterministically ordered
   blocks (landscape first, then per-group finding blocks in group order).
   **Composition conventions stay at their seams**: section conventions, the
   artefact summary, the key-findings block, supersede/lock-on-advance — the
   deferred.md composition entry is **re-scoped** (composition itself now
   lives here per ADR 0009; the conventions remain deferred). Re-run = new
   run = new artefact + new blocks; nothing superseded or mutated.
   Zero-content edge (empty characterisation) → honest skip: roll-up row +
   `empty_characterisation` flag, no artefact minted.
4. **The landscape path: model prose over the characterisation record,
   pattern-validated, judge-free.** One `synthesise_landscape_v1` call per
   run receives the characterisation record (coverage aggregates, themes
   with sizes and descriptions, unclustered count) as **id-keyed data
   records** and returns schema-constrained **typed claims**: a
   **pattern claim** asserts coverage/shape numbers — validated
   deterministically against the record (wrong numbers reject the response;
   one repair); a **theme claim** describes a theme by id — validated
   against the theme list, labelled interpretive-shape grade. Anything else
   rejects. **No citations and no judge call on this path** — there is
   nothing chunk-anchored to cite (findings don't exist on a shallow run)
   and nothing for a grounding classifier to classify; every claim is
   deterministically checked instead. Landscape blocks carry the shallow
   base honestly (screened-base provenance, the characterisation reference).
5. **The findings path: claims cite finding ids; citations resolve to
   extract-verified anchors; the model never authors a quote.** *Finding
   ids* = `intervention_outcome_finding.finding_id` — the durable rows task
   011 wrote; `grouping_result.groups[]` lists each group's member ids. The
   per-group call receives member findings as id-keyed data records
   (references, direction, statistics, anchor quotes, group
   label/description — data, never instructions) and returns
   schema-constrained claims with `cited_finding_ids ⊆ the group's member
   set` (co-emitted). Code resolves cited findings to anchors and **re-runs
   the deterministic presence check against frozen chunks** — verify asserts
   what it writes, never inheriting from an upstream payload
   (assert-on-row-not-summary class); abstract-basis anchors (no `chunk_id`)
   are located against the basis snapshot's chunks; immutable chunks make
   the re-check a cheap invariant assertion. Unknown/cross-group ids reject
   (one repair); every finding claim cites ≥ 1 finding — **no uncited-claim
   path** (Tier 4 stays a judge *verdict*, visibly flagged, never an
   authoring mode). Anchor inheritance: verified anchor + passing re-check →
   clean `citation` row; unlocatable or extract-time-`failed` anchor → **no
   citation row fabricated** — support recorded on the annotation as
   `quote_unverified`, claim capped weakly-grounded, nothing dropped.
6. **The judge is `grounding_judge_v1`, batched per finding-block,
   single-lane, reading the cited passages.** Per claim **exactly one** of
   Tier 1–4 / `unsupported_mis_cited`, an orthogonal `weakly_grounded` flag,
   a required rationale. Judge input = claim + the finding record's context
   + **the cited chunks' full frozen text** (quotes alone can't catch
   quote-mining/omitted caveats) — deterministic `lookup`-grade access by
   chunk_id, **not retrieval**; pinned `synthesis_envelope_v1` (cited
   chunks, no neighbour-widening in v1; widening lands with `retrieve`)
   alongside the chunks' `segmentation_policy` (the judge-drift/
   envelope-drift requirement). Posture: permissive about legitimate
   inference, strict about attribution fidelity; topical relevance ≠
   support. Persistence for eval-readiness: judge model + prompt version +
   verdict + rationale on the annotation payload; full I/O on Langfuse; **no
   calibration_status anywhere**.
7. **Repairs are bounded and reword down; exhaustion flags, never drops.**
   Landscape path: one regeneration on validation rejection. Findings path:
   one reword-down regeneration per block on validation rejection or any
   `unsupported_mis_cited` verdict (prompt reused verbatim + judge
   rationales + claim-less instruction), then one re-judge; claims still
   failing land **soft-flagged**. Call budget known pre-run:
   **landscape ≤ 2 calls; findings ≤ 4 × named groups** (synth + judge +
   ≤ 1 repair synth + ≤ 1 re-judge); group count bounded upstream by 012's
   fail-closed `FACET_VALUE_CAP`. Backend failure after retries fails the
   component honestly (`component.failed`, no roll-up row); blocks already
   written remain (real, internally consistent rows) and the failure payload
   names them — a retry is a new run.
8. **Direction spreads stay deterministic; pattern annotations are
   claim-driven** (rev 1.1b, unchanged): the authoritative per-group spread
   is code-computed, cross-checked against the grouping row (mismatch =
   structural failure), and always lands in the roll-up; a pattern claim's
   stated counts must equal it (wrong counts reject); the annotation follows
   the claim actually made. **Mixed/unclear findings are first-class
   throughout** (carried requirement): in the synthesis input, the spread,
   and the prompt's don't-aggregate-away rule.
9. **Descriptive, never evaluative; no absence claims — both paths.** Prompt
   negative rules (deterministically assertable on the built prompts): no
   recommendations; no weighted/consensus verdicts (⏸); no absence/gap
   phrasing — gap annotations and their coverage-base machinery stay out of
   scope. The source/evidence policy object doesn't exist yet; the
   citable-bar flag-not-block rule is honoured by the mechanism that exists
   (weakly-grounded flagging), and policy-conditioned flagging is a recorded
   seam compiling into this same flag surface.
10. **`query-findings` lands as the scoped deterministic read surface; the
    agent-loop realisation stays at the capability-run seam.** The tool
    surface — identifier-addressed, side-effect-free, project-guarded reads
    over the findings layer — lands with its consumer (the findings path's
    loader). The *agent-invoked* form follows the standing skeleton-as-agent
    posture; the deferred.md entry is **updated to say exactly this**, never
    silently closed.
11. **Component wiring mirrors 004–012.** `"synthesise"` requires
    `evidence_scope_id` + `characterisation_run_id`; `grouping_run_id`
    optional (present → the findings path runs; absent → landscape-only) —
    all compile-fail-closed; a missing referenced row → honest structural
    failure. `SynthesiseContext` via `functools.partial`;
    `_run_scope_component`; skeleton threads both run ids per the
    optional-kwarg precedent. The roll-up row is the **last** statement;
    blocks are written before it. Re-run → new run_id; same-run re-execution
    loud via `UNIQUE (evidence_scope_id, run_id)`. `component.completed`
    carries the synthesis summary; **no new event types**.
12. **Stubs are sentinel-driven; the suite is deterministic and
    egress-free.** `StubSynthesisBackend` emits fixture-declared typed
    claims on both paths (quoting real fixture anchor text so the presence
    check exercises for real; asserting real record numbers so pattern
    validation exercises for real); `StubGroundingJudgeBackend` assigns
    verdicts sentinel-driven (every tier, the unsupported path, repair,
    flags). Suite and library defaults are stub + socket-deny.
13. **All three prompts carry the standing injection posture.**
    Characterisation content, finding text, anchor quotes, group
    labels/descriptions (model-generated over source-derived — the 012
    carried requirement) enter as **id-keyed JSON data records under the
    data/instructions separation**; responses schema-constrained; no tools,
    no multi-turn, no free text acting on the world. A hijacked synthesis
    call can at worst write mis-claims — bounded by typed-claim validation,
    the presence check and the judge lane; a hijacked judge call can at
    worst mis-tier — bounded by the closed enum and flagged-not-hidden
    semantics.

### Schema

**Gated change 1 — one new table** (one migration; table count 24 → 25; exact
DDL plan-pinned, shape here binding):

```
synthesis_result  synthesis_result_id PK · project_id FK→project
                  · evidence_scope_id · run_id
                  · characterisation_run_id (executed reference, NOT NULL)
                  · grouping_run_id (executed reference, NULLABLE —
                      landscape-only runs have none)
                  · artefact_id FK→artefact NULLABLE (NULL only on the
                      empty-characterisation honest skip)
                  · synthesis_provenance JSONB NOT NULL (all three prompt
                      versions, models, judge envelope-policy version,
                      backend modes, call/repair counts per path, and the
                      inherited chain base: characterisation reference +
                      theme/coverage summary hash; when deep —
                      grouping_run_id + facet + group count + finding-set
                      size/sha256 + the extraction base carried through)
                  · blocks JSONB NOT NULL (the landscape block entry + per
                      named group: group label, block_id, claim counts by
                      type, tier distribution, unsupported/weakly-grounded
                      counts, citation verified/unverified counts,
                      repair_taken)
                  · counts JSONB NOT NULL (blocks_written, claims_total by
                      type, claims by verdict lane, citations_verified,
                      citations_unverified, findings_cited_distinct,
                      findings_total, groups_total)
                  · flags JSONB NOT NULL (landscape_only ·
                      empty_characterisation · unsupported_claims_present ·
                      weakly_grounded_present · repair_path_taken — where
                      true)
                  · created_at
                  Composite FKs (evidence_scope_id, project_id),
                  (run_id, project_id) — cross-project guards
                  FK (evidence_scope_id, characterisation_run_id) →
                      characterisation_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, grouping_run_id) →
                      grouping_result (evidence_scope_id, run_id)
                  UNIQUE (evidence_scope_id, run_id)
```

No existing-table changes: `block` / `addressable_unit` / `annotation` /
`citation` are used **as built** (001); tier, rationale and judge provenance
ride the annotation `payload` JSONB by that table's design. Downgrade drops
the table. `tests/helpers.py` `delete_project_data` gains it in FK-safe
order.

### Out of scope

- **Direct chunk-grounded artefact prose** — sanctioned by ADR 0009,
  **not built here**: lands with `retrieve` (its chunk-selection substrate);
  recorded seam with the ADR's risk note.
- **Composition conventions** — section conventions, artefact summary,
  grounded key-findings block, supersede/lock-on-advance versioning: their
  seams, re-scoped per ADR 0009 (composition itself now lives here; the
  conventions remain deferred).
- **Gap annotations / coverage-base machinery** — no absence claims are
  authored; the typed gap annotation arrives with its first consumer.
- **Weighted consensus / strength roll-up** (⏸); Unsupported/Tier-4
  never-contribute-positively is the recorded constraint on that future
  roll-up.
- **Block summaries** (⏸ co-versioned column), **artefact summary**,
  faithfulness judging — outside the grounding economy, outside this slice.
- **Block versioning beyond `version=1`** — regeneration, `same_content_as`,
  staleness: deferred with their consumers.
- **Residual-bucket prose** — no blocks for `ungrouped`/`no_value`; their
  visibility is the grouping roll-up + the composition-conventions seam.
- **The landscape→synthesis steer-point** — mode-governed pause machinery
  rides the steering-modes seam.
- **Agent-loop realisation / agent-invoked `query-findings`** — decision 10;
  the capability-run seam.
- **Retrieval inside synthesise** — the built paths are findings- and
  record-bounded; re-gather-targeted-evidence repair + judge-envelope
  widening + the chunk-grounded mode land with `retrieve`.
- **`implementation_context_finding`**, cross-schema linkage,
  graph-structured synthesis — all ⏸, untouched.
- **Judge calibration / synthesis-quality evals** — the eval workstream owns
  the clean/weak line and prose quality; this slice's bar is mechanism
  correctness (named so the review stack doesn't mistake machinery tests
  for a quality claim).

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table count
   24 → 25. No existing-table changes.
2. **Public interface** — the `"synthesise"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `characterisation_run_id` (required for synthesise)
   and `grouping_run_id` (optional; both compile-fail-closed when present
   but unresolvable) + `run_harness` gains optional **`synthesis_backend`**
   and **`grounding_judge_backend`** (stub defaults — no default egress).
   No renames ride this slice.
3. **Runtime egress — three new generation surfaces** (the repo's fifth,
   sixth and seventh product prompts):
   - **`synthesise_landscape_v1`**: the characterisation record — coverage
     aggregates, theme labels/descriptions/sizes (model-generated over
     source-derived text) — as id-keyed data records.
   - **`synthesise_block_v1`**: per group — the group label/description and
     member findings as id-keyed data records: source-named references,
     effect directions, reported statistics, **and the findings' verbatim
     anchor quotes** (source text, the 011 class) — plus the deterministic
     spread.
   - **`grounding_judge_v1`**: per finding-block — the claims, their cited
     findings' context, **and the cited chunks' full frozen text** (source
     text).
   Fixture corpus openly licensed by construction; full-I/O Langfuse traces
   (user-operated dev instance) carry these payloads — the standing 009/011
   trace posture, flagged for approval.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic` cover
it).

**Explicitly not crossed:** exactly three prompt-bearing surfaces (no agent
loop, no tools, no free text acting on the world); no new dependency; no
auth/tenancy/CI change; no existing-table change; no new event types; no tag
writes; no composition conventions beyond deterministic block ordering.

**Spec flow-backs: already landed with ADR 0009** (capability.md, components
§§5/6/9, execution-orchestration; spec log 2026-07-07) — approved in this
contract's gate conversation; the contract implements the refined spec.
Remaining deferrals ride `docs/deferred.md`.

## Public / private boundary

- On the live path, what leaves: the characterisation record's coverage/theme
  content, per-group finding records (source-named reference strings,
  reported statistics, **verbatim quotes**), cited chunks' full frozen text,
  and model-generated group labels/descriptions — all fixture-corpus-derived
  (openly licensed by construction) — to the OpenAI API; full-I/O traces to
  the user-operated dev Langfuse. For arbitrary future corpora this is
  source-derived text inheriting the corpus's sensitivity class —
  private-by-default otherwise.
- Committed artifacts (schema, prompt text, roll-up shapes, verification
  counts) are public-safe. **Block content, claims and judge rationales are
  model-generated text over source-derived input** — public-safe for the
  fixture corpus, private-by-default otherwise; **untrusted model output as
  data**: bounded and validated at write, rendered escaped, never executed.
  Carried forward again: block content and judge rationales enter any future
  prompt (composition conventions, Q&A) as data records, never instructions.

## Model route

All three surfaces behind the two backend seams — `gpt-5-mini`-class floor
(the 009 nano lesson binding) → Bedrock at the seam swap, unchanged.

- **`synthesise_landscape_v1`** (SynthesisBackend) — landscape prose. Typed
  claims out (pattern | theme); negative rules: descriptive only, no
  recommendations, no absence claims, numbers only as given by the record.
- **`synthesise_block_v1`** (SynthesisBackend) — per-group findings prose.
  Typed claims out (finding | pattern); negative rules: descriptive only —
  no recommendations, no evaluative/consensus verdicts, no absence claims;
  report the spread as given; mixed/unclear reported, never aggregated away;
  claim within what the cited findings support (claim less, cite precisely).
- **`grounding_judge_v1`** (GroundingJudgeBackend) — the classifier. Closed
  verdict enum + `weakly_grounded` + required rationale, per claim. Posture
  per provenance-grounding: permissive on legitimate inference, strict on
  attribution fidelity; topical relevance ≠ support.

All three are **prompt-bearing, lead-authored, versioned**, recorded in
`synthesis_provenance`, the event payload and (judge) the annotation
payloads. The judge rubric is lead-only per AGENTS.md.

## Disciplines binding this slice

- **The traceability rule is the slice.** Every claim traces to its cited
  findings' verified quotes, is deterministically validated against the
  recorded shape, or is visibly flagged — no fourth state, no silent
  promotion, no post-hoc citation path.
- **Flag, don't drop** — failed anchors, unlocatable quotes, unsupported and
  weakly-grounded claims all land visible with status.
- **Honest absence** — no absence claims at all; landscape blocks carry the
  screened base, finding blocks the selected/extracted base, via provenance.
- **Deterministic where claimed** — quote presence, citation resolution,
  offsets, spread computation, pattern/theme validation, cross-checks,
  ordering and writes are deterministic; at most 2 + 4 × groups interpretive
  calls per run, each fully attributable.
- **Model only what behaves** — no gap rows, no consensus fields, no summary
  columns, no calibration_status; the roll-up row and the 001 substrate rows
  are the only new state.
- **Never silent, never fake** — stubs say so; missing upstream state fails
  structurally; a failed call fails the component honestly;
  grouping↔findings and spread mismatches are structural failures.

## Stop conditions

- Any gated change (schema · public interface · egress) not yet approved, or
  any change beyond them (existing-table change, a fourth prompt surface,
  new dependency, gap/consensus/summary machinery, new event types).
- Any *suite or library-default* code path would perform network I/O.
- The synthesis wants evaluative output, absence claims, chunk-grounded
  prose (the ⏸ seam), or composition conventions — halt.
- Either backend wants capabilities beyond schema-constrained calls (tools,
  multi-turn, free text acting on the world) — halt.
- The claim/citation model can't express something without weakening
  verification (pressure to accept uncited/unvalidated claims or
  model-authored quotes) — that's a design change; halt, never weaken the
  bar silently.
- `make verify` red with unclear root cause; or the turn/token budget is
  spent.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) — green,
  deterministic, zero egress (socket-deny covers a synthesise round-trip on
  both paths; suite runs on the stubs only).
- **One manual live check, both paths** (evidence in verification.md):
  skeleton end-to-end with `OPENAI_API_KEY` (+ `LANGFUSE_*`) against the
  fixture corpus — (a) a **full deep run**: landscape block + per-group
  grounded blocks written with invariants holding, real citations to frozen
  chunks, tier distribution and any unsupported/weakly-grounded claims shown
  honestly, repair path exercised or its absence noted; (b) a
  **landscape-only synthesise run** (no `grouping_run_id`): artefact +
  landscape block written, `landscape_only` flag set. All three prompts
  visible in dev Langfuse (versions, tokens/cost) with run-level scores
  (claims-valid share, citation-verified share, unsupported share); per-run
  counts and an honest cost note; keys absent from captured output.
- Deterministic vs AI eval: all suite checks deterministic (stub backends);
  prose quality and judge calibration are eval territory — this slice's bar
  is mechanism correctness, invariant enforcement, honest flags and
  provenance fidelity.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 25.
- Named test results: **path selection** (characterisation_run_id required —
  absent → compile fails; grouping_run_id absent → landscape-only, flag set;
  present → both paths; missing referenced rows → structural failure),
  **grouping-set fidelity** (finding blocks == named groups of the
  referenced run; foreign runs never enter; spread cross-check mismatch →
  structural failure), **landscape validation** (pattern claims with wrong
  numbers rejected then repaired-or-failed; theme claims validated against
  the theme list; disallowed claim types rejected; empty characterisation →
  honest skip, no artefact), **citation resolution** (cited ids ⊆ group
  members; unknown/cross-group ids reject; anchors reused verbatim; verified
  chunk_id → citation row; abstract-basis re-location; failed/unlocatable
  anchor → no citation row + `quote_unverified` + weakly-grounded cap, never
  dropped), **presence re-check** (a quote absent from frozen chunks fails
  deterministically — fabricated-quote hard-fail preserved), **claim/unit
  integrity** (every finding claim ≥ 1 citation; pattern-claim counts equal
  the code-computed spread; a pattern/theme annotation exists iff its claim
  does, on that claim's unit; unit offsets exactly address claim text;
  composite-FK integrity; content_hash correct), **judge semantics**
  (single-lane enum enforced; rationale required; verdict + judge provenance
  + envelope version persisted; weakly_grounded orthogonal; judge input
  includes cited chunk text), **repair semantics** (bounded exactly as
  decision 7; budgets test-asserted: ≤ 2 landscape, ≤ 4 × groups findings;
  exhaustion → flags, claims retained), **flag-not-drop** (unsupported and
  weakly-grounded claims persist visibly; mixed/unclear visible in input,
  spread and prose-input data), **descriptive posture** (negative rules
  asserted on all three built prompts; an injection-shaped theme label,
  group label or finding quote lands as inert data), **artefact/composition
  v1** (one artefact per run, intent-derived bounded title; deterministic
  block order landscape-first; re-run → new artefact; same-run re-execution
  loud; backend failure → `component.failed`, no roll-up row, prior blocks
  named), **determinism** (two stub runs → identical payload columns, block
  content and hashes), **provenance required keys** (three prompt versions,
  envelope policy, per-path call counts, the inherited chain base),
  delete-order integrity.
- Live-run evidence per the manual check above (both paths).
- Public-safety confirmation (egress was fixture-corpus text only; traces on
  the user-operated instance; keys clean).
- Deferred seams recorded/updated in `docs/deferred.md`: **direct
  chunk-grounded artefact prose** (ADR 0009 — lands with `retrieve`; risk
  note carried) · **composition conventions** (re-scoped: composition lives
  in synthesise; summary/key-findings/ordering-conventions/versioning
  remain) · gap annotations with coverage-base fields (first consumer) ·
  policy-conditioned citable-bar flagging (compiles into the weakly-grounded
  flag surface) · consensus roll-up (unchanged; never-contribute constraint
  restated) · block summaries + faithfulness judging · agent-loop synthesise
  + agent-invoked `query-findings` (capability-run seam — the 012 entry
  updated, not closed) · retrieval-dependent pieces (re-gather repair,
  envelope widening — land with `retrieve`) · synthesis/judge quality evals
  (envelope-policy calibration included).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate (one new table), three new runtime-egress
generation surfaces ride the slice, and this is the **trust invariant's
landing slice**: produce-grounded-block is the system's most distinctive
contract, and a silent weakening here (uncited claims, post-hoc quotes,
dropped flags, faked landscape numbers) is the cardinal sin the spec exists
to prevent. Contract- and plan-stage adversarial reviews standard; review
stack sized per the review-economy notes (medium `/code-review`, one
security lane, class-split budget, per-angle diff scoping). ADR 0009 covers
the architecture; a step-4 ADR covers implementation-level
produce-grounded-block decisions if judged consequential beyond it.

Review focus:
- **Provenance/honesty (the headline lane)**: co-emitted citations only; the
  presence check runs against frozen chunks; every finding claim's verdict
  single-lane and persisted; landscape numbers deterministically validated;
  unsupported/weak claims flagged, never dropped; spreads deterministic and
  cross-checked; mixed/unclear survive; no absence phrasing; provenance
  carries the inherited chain base per path.
- **Security / prompt surfaces**: three prompts consuming untrusted
  source-derived and model-generated text — id-keyed data records,
  schema-constrained outputs, closed enums, no tools; output bounded and
  validated at write; key hygiene; egress bounded (pre-run budgets,
  socket-deny on suite paths).
- **Correctness**: path selection and reference resolution; citation
  resolution across verified/abstract/failed anchors; offset computation;
  composite-FK integrity; repair semantics; roll-up-last ordering; FK and
  delete order; deterministic ordering everywhere claimed.
- **Scope**: no chunk-grounded prose, no composition conventions, no
  gap/consensus/summary machinery, no fourth prompt, suite egress-free.
