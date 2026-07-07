# Task contract: 013-synthesise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 1) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: due at step 4 (the
> produce-grounded-block realisation + block-substrate decisions are
> consequential).
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft.

## Goal

Add **synthesise** — EB component 9, the deep terminus, closing the chain
`acquire → … → extract → group → synthesise`. Over the **named groups** of an
explicitly referenced grouping run, **per group produce a grounded block**
reporting what that group's findings show.

The output is **descriptive**: it surfaces the direction-spread steer ("5 of 7
findings positive on tenancy, two null" — v2's `effect_consensus` counts as
this steer), populations, designs and reported effects — never a weighted
verdict ("the evidence supports X at strength Y" is the ⏸ consensus seam),
never a recommendation (EB is evidence-descriptive by scope), and **never an
absence claim** (deep coverage rests on the selected/extracted base, is
base-labelled, and is never promoted to corpus absence; the shallow landscape
is the structural check — EB provenance).

The slice's centre of gravity is the **real `produce-grounded-block`
mechanism** (system provenance-grounding): synthesise → cite → verify → write,
with **cite and verify as mandatory internal steps**. Citations are
**co-emitted, never post-hoc** — a claim is generated *from* its evidence;
there is no attach-citation-to-prose path. Verify has two parts: the
**deterministic quote-presence check** (verbatim quote must occur in the cited
source's frozen chunks) and the **LLM-as-judge grounding classifier** (exactly
one of Tier 1–4 / Unsupported-mis-cited — a single lane, no separate
`is_supported`; plus the orthogonal weakly-grounded completeness flag and a
free-form grounding rationale). Verify is a **bounded loop whose job is
claim↔evidence convergence, not pass/fail**: primary repair rewords the claim
*down* to what the evidence supports; on exhaustion the claim lands
weakly-grounded or Unsupported/mis-cited — **soft-flagged, never dropped,
never silently promoted to a clean tier**. The walking skeleton (001) shipped
the deterministic leg as a stub over one snapshot; this slice lands the
mechanism the spec calls settled.

This is also the **first real writer of the 001 information-layer substrate**:
real `block` / `addressable_unit` / `annotation` / `citation` rows — the
grounding economy's home — rather than another JSONB-only roll-up. The
run-scoped `synthesis_result` row records the run (provenance, block map,
counts, flags), exactly as 009–012's roll-ups do.

## Deliverable

A PR on `task/013-synthesise` → `dev` that:

- Ships `synthesise.py`: `SynthesiseContext(scope_id, intent, context,
  grouping_run_id)`; `synthesise_groups(...)` — grouping-roll-up load →
  member-finding load (via the `query-findings` read surface) → per named
  group: schema-constrained claims call → citation resolution against the
  findings' extract-verified anchors → deterministic quote-presence re-check →
  batched judge call → one bounded reword-down repair → block / unit /
  annotation / citation writes → roll-up row write → synthesis summary in
  `component.completed`.
- Ships **two backend seams** (the `ExtractionBackend`/`FacetGroupingBackend`
  pattern): `SynthesisBackend` (+ `OpenAISynthesisBackend`, stub) with the
  **`synthesise_block_v1`** prompt, and `GroundingJudgeBackend`
  (+ `OpenAIGroundingJudgeBackend`, stub) with the **`grounding_judge_v1`**
  prompt — the repo's fifth and sixth product prompts, both lead-authored,
  versioned, recorded in provenance.
- Ships **`query_findings`** — the scoped, deterministic, project-guarded
  findings-layer read surface (findings by extraction-record/finding ids),
  used by synthesise's loader (discharges the 012 recorded deviation on its
  stated terms — see decision 9).
- Adds **one table — `synthesis_result`** — via one Alembic migration (gated
  change 1; table count 24 → 25, migration 13), project-scope-guarded.
- Registers `"synthesise"` in `COMPONENT_REGISTRY` (requires
  `evidence_scope_id` + **`grouping_run_id`** — the explicit-reference pattern
  from 010/011/012); `run_harness` gains **`synthesis_backend`** and
  **`grounding_judge_backend`** (stub defaults — no default egress; gated
  change 2).
- Extends `skeleton.py`: … group → **synthesise** (the deep terminus
  complete), rendering the synthesis summary (blocks written, claims by tier,
  citation verification counts, flags).
- **Factors the traced-call helper into `tracing.py`** — the 012-deferred
  trigger fires (backends four and five land here); the three existing OpenAI
  backends (`extraction_backend.py`, `ranking.py`, `facet_grouping.py`) and
  the two new ones share the factored parse-once traced-call shape.
- Records the deferred seams in `docs/deferred.md`; updates
  `tests/helpers.py` delete order for the new table.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [EB components §9 — synthesise](../../specs/capabilities/evidence-base/components.md)
  — the component contract: per-group grounded blocks, descriptive
  direction-spread, produce-grounded-block with deterministic + judge legs,
  flag-not-block citable bar, base-labelled deep gaps, the ⏸ consensus seam.
  Also §8 (what group wrote — the substrate this reads) and the tool-wiring
  table (synthesise declares `query-findings`; realisation "agent-loop").
- [System provenance-grounding](../../specs/system/provenance-grounding.md) —
  **the slice's governing contract**: the traceability rule (three honest
  categories; Unsupported/mis-cited as the cardinal-sin failure state),
  grounding tiers 1–4, weakly-grounded as an orthogonal flag,
  produce-grounded-block mechanics (co-emitted citations, two-part verify,
  bounded reword-down repair), judge posture (permissive about legitimate
  inference, strict about attribution fidelity; topical relevance ≠ support),
  persistence-for-eval-readiness (judge prompt/model id+version + I/O,
  segmentation/envelope-policy versions; **no calibration_status field**),
  and what stays out (summaries are outside the grounding economy).
- [EB capability](../../specs/capabilities/evidence-base/capability.md) —
  output structure (sections composed by the orchestrator — *not this slice*;
  blocks are the substrate), scope boundaries (evidence-descriptive, no
  recommendations; option resolution is Options Assessment's), the
  landscape→synthesis steer-point (mode-governed; modes are ⏸), cluster
  persistence (groups run-local; blocks are where durable content lives).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) — the
  gap rule (nothing here may phrase `not_selected`/`not_extracted` as
  absence), pattern grades (finding-query patterns = middle grade, carry the
  extraction dependency), flag-not-block at synthesise.
- [System data-model](../../specs/system/data-model.md) — block / addressable
  unit / annotation-layer semantics (annotations keyed `(block, unit, type)`;
  citations hang off units; provenance anchor = `(source, verbatim quote,
  recorded location)`), the findings layer (what a finding row carries),
  versioning grains (block versioning machinery beyond `version=1` is not
  this slice).
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — `produce-grounded-block` in the universal core (a facade over a
  substantial workflow *is* a tool); `query-findings` scoped-not-core; the
  agent-loop realisation for deliberative work; trust enforced at grounding.
- [012-group contract](../012-group/contract.md) — pattern precedent
  (explicit upstream-run reference, roll-up shape, injection posture,
  call-budget discipline) and the two carried-forward requirements binding
  here: **group labels/descriptions enter prompts as data records, never
  instructions** (rev 1.3) and **mixed/unclear findings survive the whole
  deep chain** (011 → 012 → here).
- [docs/deferred.md](../../deferred.md) — the entries this slice touches:
  `query-findings` (recorded 012 deviation — lands here), the traced-call
  helper (trigger fires here), EB artefact composition (stays deferred — this
  slice writes blocks, not sections), consensus roll-up (⏸), graph-structured
  synthesis (⏸).

**Code grounding (surveyed 2026-07-07):** 24 tables, 12 migrations (this
slice ships migration 13). The 001 substrate exists and is real:
`block(artefact_id FK NOT NULL, version, content, content_hash)` ·
`addressable_unit(block_id, unit_type, locator JSONB, content)` ·
`annotation((block_id, unit_id) composite-FK, annotation_type, payload
JSONB)` · `citation(annotation_id FK, chunk_id FK NOT NULL, quote,
verification_result)`. `grounding.py` is the walking-skeleton deterministic
leg (stub synthesis where quote == whole content; LLM judge explicitly "a
deferred seam"); the echo component mints its own `artefact` row
(harness.py:88–96) — the container precedent decision 3 reuses. Findings
carry extract-verified anchors (`extract.py:650`): `segment_id` (the model's
untrusted location *claim*, never dereferenced) · **`chunk_id` (the verified
location — None when unverified or abstract-basis)** · `quote` ·
`match_status` · `quote_verified` · `spans[{chunk_id, start, end}]`.
`grouping_result.groups` carries per named group: label, description, member
values, **member finding ids**, size, direction spread — plus `ungrouped` and
`no_value` residuals and `overall_direction_spread`;
`grouping_provenance.extraction_base` carries the inherited fingerprint,
base-ladder counts, finding-set size + sha256. Backend pattern: protocol +
stub + OpenAI class with pydantic `response_format`, module-constant prompt +
`PROMPT_VERSION`, caller-owned budget, validation separated from the call
(`gpt-5-mini` floor — the 009 nano lesson). Component wiring: registry entry
+ required Config field → context dataclass → `_run_scope_component` →
`component.*` events; `skeleton.py` threads upstream run ids and switches
stub/live on `OPENAI_API_KEY`.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The complete produce-grounded-block mechanism lands in one slice** —
   deterministic quote-presence **and** the LLM judge **and** the bounded
   reword-down repair. Components §9 names the mechanism settled and both
   legs mandatory; provenance-grounding makes cite/verify mandatory internal
   steps. Shipping synthesise with a deterministic-only verify would mint
   blocks whose annotations carry no tier — a second annotation-semantics
   migration one slice later — and would put ungrounded prose on the trust
   path with no classifier. The judge's *calibration* (where the clean/weak
   line falls) stays eval-workstream territory per the spec; this slice's bar
   is mechanism correctness, not judge quality.
2. **Blocks are real information-layer rows at claim grain.** Per named
   group: one `block` row (content = the claims' prose, joined
   deterministically; `content_hash` per the 001 convention), one
   `addressable_unit` per claim (`unit_type="text_span"`, locator = computed
   char offsets into the block content), one **citation annotation** per
   claim-unit (payload: cited finding ids, per-citation verification, judge
   verdict — tier / weakly_grounded / rationale / judge provenance) and one
   **pattern annotation** per block (the deterministic direction spread —
   decision 7). `citation` rows link claim-units to the frozen chunks their
   quotes live in. This is the substrate the artefact-composition seam
   composes from; no new store, the 001 tables as designed.
3. **One artefact row per synthesise run as the v3.0 container.**
   `block.artefact_id` is NOT NULL by design; the echo component already
   mints its artefact (the standing precedent). Synthesise mints one honestly
   titled artefact row per run ("Evidence Base synthesis — run …") and
   attaches its blocks. **Artefact semantics stay deferred**: no sections, no
   ordering, no artefact summary, no key-findings block, no
   supersede/lock-on-advance — the composition seam owns all of it
   (deferred.md, 009 entry). Re-run = new run = new artefact + new blocks;
   nothing is superseded or mutated.
4. **Claims cite finding ids; citations resolve to the findings'
   extract-verified anchors; the model never authors a quote.** The
   synthesis call receives the group's member findings as **id-keyed data
   records** (references, direction, statistics, anchor quotes, group
   label/description — data, never instructions) and returns
   schema-constrained claims, each carrying `cited_finding_ids ⊆ the group's
   member set` (co-emitted citations — the claim is generated *from* the
   finding records). Code then resolves each cited finding to its anchor
   quotes and chunks and **re-runs the deterministic presence check against
   the frozen basis chunks** (matches stored passage text, not a snapshot
   reload). Validation is deterministic and fail-closed: unknown or
   cross-group finding ids reject the response (one repair); every claim must
   cite ≥ 1 finding — there is **no uncited-claim path in v3.0 synthesise**
   (Tier 4 remains a judge *verdict* a claim can land in, visibly flagged —
   never an authoring mode). This closes the fabricated-quote path
   structurally: the model can only point at findings whose quotes extract
   already verified.
   **Anchor-inheritance posture:** an anchor with a verified `chunk_id` and a
   passing re-check → a clean `citation` row (`verification_result="pass"`).
   An abstract-basis anchor (`chunk_id` None) is re-located against the basis
   snapshot's DB chunks — locatable → cited normally; unlocatable, or an
   anchor whose extract-time match already `failed` → **no citation row is
   fabricated**; the support is recorded on the annotation payload as
   `quote_unverified`, the claim is capped at weakly-grounded, and nothing is
   dropped (flag-don't-drop; extract's honest anchor failures stay honest
   here).
5. **The judge is `grounding_judge_v1`, batched per block, single-lane.** One
   call per block judges all its claims: per claim **exactly one** of Tier
   1–4 / `unsupported_mis_cited` (no separate is_supported), an orthogonal
   `weakly_grounded` flag, and a required free-form grounding rationale.
   Judge input = claim text + its cited findings' quotes + the finding
   record's context (references, direction, statistics) — the **evidence
   envelope**, pinned and versioned as `synthesis_envelope_v1` alongside the
   chunks' `segmentation_policy` (the spec's judge-drift/envelope-drift
   requirement). Judge posture in the prompt: permissive about legitimate
   inference, strict about attribution fidelity (scope, caveats, population,
   comparator, direction, magnitude, uncertainty); topical relevance ≠
   support; empirical markers are strict-routing heuristics, not the
   definition. Persistence for eval-readiness: judge model + prompt version +
   verdict + rationale on the annotation payload; full I/O on the Langfuse
   telemetry plane; **no calibration_status field anywhere** (spec).
6. **The repair is bounded and rewords down; exhaustion flags, never drops.**
   If validation rejects a response or the judge lands any claim
   `unsupported_mis_cited`: **one** reword-down regeneration for that block
   (the synthesis prompt reused verbatim plus the judge rationales and the
   instruction to claim less), then **one** re-judge. Claims still failing
   land in the block **soft-flagged** (`unsupported_mis_cited` /
   `weakly_grounded` visible on the annotation), never silently promoted,
   never removed — the composition seam decides presentation. Call budget is
   known pre-run: **≤ 4 × named groups** (synth + judge + ≤ 1 repair synth +
   ≤ 1 re-judge per group); the group count is already bounded upstream by
   012's fail-closed `FACET_VALUE_CAP`. Backend failure after retries fails
   the component honestly (`component.failed`, no partial roll-up row);
   blocks already written for earlier groups remain (they are real,
   internally consistent information-layer rows) and the failure payload
   names them — a retry is a new run, new artefact, new blocks.
7. **Direction spreads stay deterministic — a pattern annotation, not model
   prose.** The authoritative per-group spread is code-computed (it already
   sits in `grouping_result.groups[]`); synthesise re-derives it from the
   loaded findings, cross-checks it against the grouping row (mismatch =
   structural failure — the referenced grouping must describe the findings
   read), and writes it as the block's **pattern annotation** with its
   provenance: finding-query grade (middle — deterministic *given* the
   recorded finding-set/coverage/profile, extraction-dependent, **not
   metadata-grade**), the inherited extraction base, and the grouping run
   reference. The model receives the spread as data and may restate it in
   prose; the judge's fidelity posture covers misstatement. **Mixed/unclear
   findings are first-class throughout** (the carried requirement): they
   enter the synthesis input, appear in the spread, and the prompt forbids
   aggregating them away.
8. **Descriptive, never evaluative; no absence claims.** Prompt negative
   rules (deterministically assertable on the built prompt): no
   recommendations or should-statements; no weighted/consensus verdicts (the
   ⏸ seam); no absence/gap phrasing ("no evidence on…", "little research
   exists…") — deep coverage is base-labelled counts, and **gap annotations
   are out of scope this slice** (the gap machinery's coverage-base fields
   arrive with their consumer). The source/evidence **policy** object does
   not exist yet (no policy slice has landed): the citable-bar
   flag-not-block rule is honoured by the mechanism that exists —
   weakly-grounded/below-bar support is flagged, never hidden — and
   policy-conditioned flagging is recorded as a seam that compiles into this
   same flag surface when the policy slice lands.
9. **`query-findings` lands as the scoped deterministic read surface; the
   agent-loop realisation stays at the capability-run seam.** 012 recorded
   the deviation as "the scoped read tool lands with its deliberative
   consumer, synthesise's agent-loop". This slice lands the tool surface —
   `query_findings(conn, project_id, …)`: identifier-addressed,
   side-effect-free, project-guarded reads over the findings layer — and
   synthesise's loader consumes it. The *agent-invoked* form (LLM tool-call
   discretion mid-synthesis) follows the standing skeleton-as-agent posture:
   like characterise, select and group before it, v3.0 realises the
   component as a bounded procedure invoked as one facade, and the
   capability-run seam owns the agent upgrade. The deferred.md entry is
   **updated to say exactly this** (surface landed, agent invocation at the
   capability-run seam), never silently closed.
10. **Component wiring mirrors 004–012.** `"synthesise"` in
    `COMPONENT_REGISTRY` requiring `evidence_scope_id` + `grouping_run_id`
    (compile fails closed; no `grouping_result` row for `(scope,
    grouping_run_id)` → honest structural failure). `SynthesiseContext` via
    `functools.partial`; `_run_scope_component`; skeleton chain extends to
    synthesise, threading `grouping_run_id` per the optional-kwarg precedent.
    The roll-up row is the **last** statement after all fallible work; blocks
    are written before it (decision 6 names the partial-blocks-on-failure
    posture). Re-run → new run_id; same-run re-execution loud via
    `UNIQUE (evidence_scope_id, run_id)`. `component.completed` carries the
    synthesis summary; **no new event types**. Zero-groups grouping run
    (empty extraction, all-residual partition) → honest skip: roll-up row
    with zero blocks + `empty_groups` flag; no artefact minted.
11. **Stubs are sentinel-driven; the suite is deterministic and egress-free.**
    `StubSynthesisBackend` emits fixture-declared claims (quoting real
    fixture anchor text so the presence check exercises for real);
    `StubGroundingJudgeBackend` assigns verdicts sentinel-driven (exercising
    every tier, the unsupported path, the repair path and the flags). Suite
    and library defaults are stub + socket-deny.
12. **Both prompts carry the standing injection posture.** Finding text
    (source-derived), anchor quotes, group labels/descriptions
    (model-generated over source-derived — the 012 carried requirement) enter
    both prompts as **id-keyed JSON data records under the
    data/instructions separation**, never interpolated as instructions;
    responses are schema-constrained; no tools, no multi-turn, no free text
    acting on the world. A hijacked synthesis call can at worst write
    mis-claims — which the judge lane, presence check and validation bound;
    a hijacked judge call can at worst mis-tier — bounded by the closed
    verdict enum and flagged-not-hidden semantics.

### Schema

**Gated change 1 — one new table** (one migration; table count 24 → 25; exact
DDL plan-pinned, shape here binding):

```
synthesis_result  synthesis_result_id PK · project_id FK→project
                  · evidence_scope_id · run_id
                  · grouping_run_id (the executed reference)
                  · artefact_id FK→artefact (the minted container)
                  · synthesis_provenance JSONB NOT NULL (both prompt versions,
                      models, judge envelope-policy version, backend modes,
                      call/repair counts, and the inherited chain base:
                      grouping_run_id + facet + group count + finding-set
                      size/sha256 + the extraction base carried through from
                      grouping_provenance — the (finding-set, coverage-state,
                      extraction-profile) provenance the spec requires,
                      now two links deep)
                  · blocks JSONB NOT NULL (per named group: group label,
                      block_id, claim count, tier distribution,
                      unsupported/weakly-grounded counts, citation
                      verified/unverified counts, repair_taken)
                  · counts JSONB NOT NULL (groups_total, blocks_written,
                      claims_total, claims by verdict lane, citations_verified,
                      citations_unverified, findings_cited_distinct,
                      findings_total)
                  · flags JSONB NOT NULL (empty_groups ·
                      unsupported_claims_present · weakly_grounded_present ·
                      repair_path_taken — where true)
                  · created_at
                  Composite FKs (evidence_scope_id, project_id),
                  (run_id, project_id) — cross-project guards
                  FK (evidence_scope_id, grouping_run_id) →
                      grouping_result (evidence_scope_id, run_id) — the
                      executed grouping must exist for this scope
                  UNIQUE (evidence_scope_id, run_id)
```

No existing-table changes: `block` / `addressable_unit` / `annotation` /
`citation` are used **as built** (001); tier, rationale and judge provenance
ride the annotation `payload` JSONB by that table's design. Downgrade drops
the table. `tests/helpers.py` `delete_project_data` gains it in FK-safe order.

### Out of scope

- **Artefact composition** — sections, ordering, the artefact summary, the
  grounded key-findings block, supersede/lock-on-advance versioning: the
  recorded composition seam (009), untouched. This slice writes blocks; the
  composition slice arranges them.
- **Gap annotations / coverage-base machinery** — no absence claims are
  authored, so no gap rows; the typed gap annotation with its required
  coverage-base field arrives with its first consumer.
- **Weighted consensus / strength roll-up** — spreads are counts, never
  verdicts (⏸); Unsupported/Tier-4-never-contribute-positively is the
  recorded constraint on that future roll-up, not machinery now.
- **Block summaries** (the co-versioned summary column: ⏸), **artefact
  summary**, faithfulness judging — summaries are outside the grounding
  economy and outside this slice.
- **Block versioning beyond `version=1`** — regeneration, `same_content_as`,
  staleness: deferred with their consumers.
- **Residual-bucket prose** — no blocks for `ungrouped`/`no_value`; their
  visibility is the grouping roll-up's counts + spreads (already recorded)
  and the composition seam's job to surface.
- **The landscape→synthesis steer-point** — mode-governed pause machinery
  rides the steering-modes seam; the crossing happens silently in the
  skeleton today, as every component boundary does.
- **Agent-loop realisation / agent-invoked `query-findings`** — decision 9;
  the capability-run seam.
- **`implementation_context_finding`**, cross-schema linkage,
  graph-structured synthesis, hybrid retrieval / `retrieve` — all ⏸,
  untouched.
- **Judge calibration / synthesis-quality evals** — the eval workstream owns
  the clean/weak line and prose quality; this slice's bar is mechanism
  correctness (named explicitly so the review stack doesn't mistake machinery
  tests for a quality claim).

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table count
   24 → 25. No existing-table changes.
2. **Public interface** — the `"synthesise"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `grouping_run_id` (required for synthesise, compile
   fails closed) + `run_harness` gains optional **`synthesis_backend`** and
   **`grounding_judge_backend`** (stub defaults — no default egress). No
   renames ride this slice.
3. **Runtime egress — two new generation surfaces** (the repo's fifth and
   sixth product prompts):
   - **`synthesise_block_v1`** sends, per group: the group label/description
     and the member findings as id-keyed data records — source-named
     references, effect directions, reported statistics, **and the findings'
     verbatim anchor quotes** (source text, the 011 class) — plus the
     deterministic spread.
   - **`grounding_judge_v1`** sends, per block: the claims and their cited
     findings' quotes/context (the same source-text class).
   Fixture corpus openly licensed by construction; full-I/O Langfuse traces
   (user-operated dev instance) carry these payloads — the standing 009/011
   trace posture, flagged for approval.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic` cover
it).

**Explicitly not crossed:** exactly two prompt-bearing surfaces (no agent
loop, no tools, no free text acting on the world); no new dependency; no
auth/tenancy/CI change; no existing-table change; no new event types; no tag
writes; no artefact semantics beyond the minted container row.

**Spec flow-backs:** none anticipated. The 012 `query-findings` deviation
entry in deferred.md is updated per decision 9 (surface landed,
agent-invocation at the capability-run seam) — an honest narrowing of a
recorded deviation, not a new one. Other deferrals ride `docs/deferred.md`.

## Public / private boundary

- On the live path, what leaves: per-group finding records — source-named
  reference strings, reported statistics and **verbatim quotes from the
  fixture corpus** (openly licensed by construction) — plus model-generated
  group labels/descriptions, to the OpenAI API; full-I/O traces to the
  user-operated dev Langfuse. For arbitrary future corpora this is
  source-derived text and inherits the corpus's sensitivity class —
  private-by-default otherwise.
- Committed artifacts (schema, prompt text, roll-up shapes, verification
  counts) are public-safe. **Block content, claims and judge rationales are
  model-generated text over source-derived input** — public-safe for the
  fixture corpus, private-by-default otherwise; and **untrusted model output
  as data**: length/control-character-bounded and validated at write,
  rendered escaped, never executed. The carried 012 requirement is discharged
  here and **carries forward again**: block content and judge rationales
  enter any future prompt (composition, Q&A) as data records, never
  instructions.

## Model route

Both surfaces behind their backend seams — `gpt-5-mini`-class floor (the 009
nano lesson is binding) → Bedrock at the seam swap, unchanged.

- **`synthesise_block_v1`** (SynthesisBackend) — the block writer. Schema-
  constrained claims out (claim text + cited finding ids per claim).
  Negative rules in the prompt: descriptive only — no recommendations, no
  evaluative/consensus verdicts, no absence claims; report the spread as
  given, never re-derive or round it; mixed/unclear findings reported, never
  aggregated away; claims must stay within what the cited findings'
  quotes/statistics support (claim less, cite precisely).
- **`grounding_judge_v1`** (GroundingJudgeBackend) — the classifier. Closed
  verdict enum (tier_1 | tier_2 | tier_3 | tier_4 | unsupported_mis_cited) +
  `weakly_grounded` + required rationale, per claim. Posture per
  provenance-grounding: permissive on legitimate inference, strict on
  attribution fidelity; topical relevance ≠ support.

Both prompts are **prompt-bearing, lead-authored, versioned** and recorded in
`synthesis_provenance`, the event payload and the annotation payloads (judge).
The judge rubric is a judge-rubric surface — lead-only per AGENTS.md.

## Disciplines binding this slice

- **The traceability rule is the slice.** Every claim traces to its cited
  findings' verified quotes or is visibly flagged — no third state, no silent
  promotion, no post-hoc citation path.
- **Flag, don't drop** — failed anchors, unlocatable quotes, unsupported and
  weakly-grounded claims all land visible with status; nothing is removed to
  make a block look clean.
- **Honest absence** — no absence claims at all this slice; spreads and
  counts are base-labelled via provenance (selected/extracted base, two
  links deep).
- **Deterministic where claimed** — quote presence, citation resolution,
  offsets, spread computation, cross-checks, validation and writes are
  deterministic; exactly two interpretive calls per group (+ bounded repair),
  each fully attributable (provenance, traces).
- **Model only what behaves** — no gap rows, no consensus fields, no summary
  columns, no calibration_status; the roll-up row and the 001 substrate rows
  are the only new state.
- **Never silent, never fake** — stubs say they're stubs; missing upstream
  state fails structurally; a failed judge/synthesis call fails the component
  honestly; grouping↔findings mismatch is a structural failure, never a
  quiet re-derivation.

## Stop conditions

- Any gated change (schema · public interface · egress) not yet approved, or
  any change beyond them (existing-table change, a third prompt surface, new
  dependency, gap/consensus/summary machinery, new event types).
- Any *suite or library-default* code path would perform network I/O.
- The synthesis wants evaluative output, absence claims, section composition
  or artefact semantics — that's seam territory; halt.
- Either backend wants capabilities beyond one schema-constrained call
  (tools, multi-turn, free text acting on the world) — halt.
- The claim/citation model can't express something without weakening
  verification (e.g. pressure to accept uncited claims or model-authored
  quotes) — that's a design change; halt, never weaken the bar silently.
- `make verify` red with unclear root cause; or the turn/token budget is
  spent.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) — green,
  deterministic, zero egress (socket-deny covers a synthesise round-trip;
  suite runs on the stubs only).
- **One manual live check** (evidence in verification.md): skeleton
  end-to-end with `OPENAI_API_KEY` (+ `LANGFUSE_*`) against the fixture
  corpus — real `synthesise_block_v1` + `grounding_judge_v1` calls over a
  real grouping run; per-group blocks/units/annotations/citations written
  with the invariants holding; tier distribution and any
  unsupported/weakly-grounded claims shown honestly; the repair path
  exercised or its absence noted; both prompts visible in the dev Langfuse
  trace (prompt versions, tokens/cost) with run-level scores (claims-valid
  share, citation-verified share, unsupported share — the 009
  `score_summary` pattern); per-run counts and an honest cost note; keys
  absent from captured output.
- Deterministic vs AI eval: all suite checks are deterministic (stub
  backends). Synthesis prose quality and judge calibration are eval
  territory — the grounding/synthesis-quality eval seam; this slice's bar is
  mechanism correctness, invariant enforcement, honest flags and provenance
  fidelity.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 25.
- Named test results: **grouping-set fidelity** (blocks == named groups of
  the referenced run; a foreign run's groups never enter; grouping row
  missing → structural failure; spread cross-check mismatch → structural
  failure), **citation resolution** (cited ids ⊆ group members — unknown or
  cross-group ids reject the response; anchors reused verbatim; verified
  chunk_id → citation row; abstract-basis re-location; failed/unlocatable
  anchor → no citation row + `quote_unverified` + weakly-grounded cap, never
  dropped), **presence re-check** (a quote absent from the frozen chunks
  fails deterministically — fabricated-quote hard-fail preserved),
  **claim/unit integrity** (every claim ≥ 1 citation; unit offsets exactly
  address their claim text in block content; composite-FK annotation
  integrity; content_hash correct), **judge semantics** (single-lane enum
  enforced; rationale required; verdict + judge provenance persisted on the
  annotation; weakly_grounded orthogonal), **repair semantics** (one
  reword-down + one re-judge, never more; budget ≤ 4 × groups test-asserted;
  exhaustion → flags, claims retained), **flag-not-drop** (unsupported and
  weakly-grounded claims persist visibly; mixed/unclear findings visible in
  input, spread and prose-input data), **descriptive posture** (negative
  rules asserted on both built prompts; an injection-shaped group label or
  finding quote lands as inert data), **edge scopes** (zero-groups run →
  honest skip, no artefact; same-run re-execution loud; backend failure →
  `component.failed`, no roll-up row, prior blocks named in the failure
  payload), **determinism** (two stub runs → identical payload columns,
  identical block content and hashes), **provenance required keys** (both
  prompt versions, envelope policy, the two-links-deep inherited base),
  delete-order integrity.
- Live-run evidence per the manual check above.
- Public-safety confirmation (egress was fixture-corpus text only; traces on
  the user-operated instance; keys clean).
- Deferred seams recorded in `docs/deferred.md`: gap annotations with
  coverage-base fields (first consumer) · policy-conditioned citable-bar
  flagging (compiles into the weakly-grounded flag surface when the policy
  slice lands) · artefact composition (unchanged, now with real blocks to
  compose) · consensus roll-up (unchanged; Unsupported/Tier-4
  never-contribute constraint restated) · block summaries + faithfulness
  judging · agent-loop synthesise + agent-invoked `query-findings` (the
  capability-run seam — the 012 deviation entry updated, not closed) ·
  synthesis/judge quality evals (extends the eval seam; envelope policy
  calibration).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate (one new table), two new runtime-egress
generation surfaces ride the slice, and this is the **trust invariant's
landing slice**: the produce-grounded-block mechanism is the system's most
distinctive contract, and a silent weakening here (uncited claims, post-hoc
quotes, dropped flags) is exactly the cardinal sin the spec exists to
prevent. Contract- and plan-stage adversarial reviews standard; review stack
sized per the review-economy notes (medium `/code-review`, one security lane,
class-split budget, per-angle diff scoping). ADR at step 4 (the
produce-grounded-block realisation, the claim-cites-findings design and the
artefact-container decision are consequential).

Review focus:
- **Provenance/honesty (the headline lane)**: co-emitted citations only —
  no path attaches a citation to already-written prose; the presence check
  runs against frozen chunks; every claim's verdict is single-lane and
  persisted; unsupported/weak claims flagged, never dropped or reworded
  into invisibility; spreads deterministic and cross-checked; mixed/unclear
  survive; no absence phrasing; provenance carries the two-links-deep base.
- **Security / prompt surfaces**: two prompts, both consuming untrusted
  source-derived and model-generated text — id-keyed data records,
  schema-constrained outputs, closed enums, no tools; output bounded and
  validated at write; key hygiene; egress bounded (pre-run call budget,
  socket-deny on suite paths).
- **Correctness**: citation resolution across verified/abstract/failed
  anchors; offset computation; composite-FK integrity; repair-path
  semantics; roll-up-last ordering; FK and delete order; deterministic
  ordering everywhere claimed.
- **Scope**: no composition reach-through, no gap/consensus/summary
  machinery, no third prompt, suite egress-free.
