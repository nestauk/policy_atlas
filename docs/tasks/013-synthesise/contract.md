# Task contract: 013-synthesise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 3) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADRs: [0009](../../adr/0009-capability-composes-synthesise-terminus.md)
> (terminus architecture) + [0010](../../adr/0010-intent-led-synthesis-sections.md)
> (intent-led sections, mixed grounding, selected-set chunk grounding) —
> both Accepted 2026-07-07.
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft — synthesise as deep-only content
>   producer per the then-current spec reading.
> - **rev 1.1** (2026-07-07, user challenges — adjudicated): intent-derived
>   artefact title · claim-driven pattern annotations (typed claims) · judge
>   envelope = cited chunks' full frozen text (`synthesis_envelope_v1`) ·
>   retrieval position explicit · clarity fixes (finding ids defined;
>   presence-check re-run rationale; depth axis stated).
> - **rev 2** (2026-07-07, user spec-challenge → **ADR 0009**): terminus
>   refinement — capability-composes; synthesise = EB's terminal component
>   at every depth (landscape path added, model prose pattern-validated);
>   components as a registry, breadth ⊥ depth; chunk-grounded prose
>   sanctioned as a retrieve-gated seam; registry references became
>   `characterisation_run_id` (required) + `grouping_run_id` (optional).
> - **rev 3** (2026-07-07, user challenge on intent-relevance → independent
>   deep-reasoner interrogation → **ADR 0010**, superseding rev 2's deep
>   path): **(a) group-per-block replaced by intent-led sections** — the
>   rev-2 structure contradicted ADR 0009's plan-shapes-sections authority
>   and the spec's own "sections mix grounding modes, composed from intent";
>   **(b) intent enters synthesis** (section derivation + prompt emphasis
>   data; 012's intent-exclusion was grouping-specific — the recompute unit
>   here is `(config-incl-intent, evidence)`); **(c) selected-set chunk
>   grounding lands in this slice** (user decision) — the selected
>   documents' frozen text is already in hand, needs no `retrieve`, and
>   carries the texture the narrow IOF schema cannot (mechanisms, context,
>   caveats); only **corpus-wide** chunk grounding stays retrieve-gated
>   (ADR 0009 decision 5 amended); **(d) pure intent-led** (user choice
>   over the recommended hybrid): no rendered group-spread backbone —
>   groups demoted to input, uncovered groups counted, spreads live in
>   roll-ups and validated pattern claims; **(e)** prompt surfaces grow to
>   **four** (`synthesise_sections_v1` added; `synthesise_block_v1` →
>   `synthesise_section_v1`); "library" → **registry** terminology fixed
>   throughout. Trust machinery of rev 2 retained unchanged (the
>   interrogation defended it).

## Goal

Add **synthesise** — EB component 9 and, per ADR 0009, **EB's terminal
component at every depth**: it **composes the one EB artefact** — mints it
(intent-derived bounded title), renders content into grounded blocks, binds
them. The orchestrator shapes the artefact at plan time; composition is
capability expertise and happens here. Per **ADR 0010**, the deep output is
**shaped by what was asked, not by what was studied**.

Two paths build now (the components are a registry; dependencies travel as
explicit fail-closed run references):

- **Landscape path (always — the minimum content an artefact needs):**
  model prose over the referenced characterisation record, **intent as
  emphasis input**; shape-asserting claims **deterministically validated
  against the record**; no citations at this grade — none exist, none are
  faked.
- **Deep path (when the deep chain ran): intent-led sections.** The section
  set derives from the **user's intent** (one bounded schema-constrained
  proposal call over intent + group summaries; fail-closed
  `context["synthesis"]` directive override; plan-compile sectioning = the
  recorded seam). Each section's prose mixes grounding modes:
  **finding claims** (cite finding ids → extract-verified anchors; the
  model never authors these quotes) · **chunk claims** (verbatim quotes
  from the **selected set's** windowed frozen text — already in hand,
  select's coverage discipline inherited, no retrieval) · **pattern
  claims** (deterministically validated against computed spreads).
  **Groups are input, not structure**: summaries steer sectioning and
  emphasis; uncovered groups are counted (`groups_unsectioned`), never
  silently dropped. **Descriptive always**: no recommendations, no weighted
  verdicts (⏸ consensus seam), **no absence claims** (deep coverage is
  base-labelled, never promoted to corpus absence).

Every cited claim goes through the **real `produce-grounded-block`
mechanism**: synthesise → cite → verify → write, cite/verify mandatory,
citations **co-emitted, never post-hoc**. Verify = the **deterministic
quote-presence check** against frozen chunks **plus the LLM-as-judge
grounding classifier** (single lane: exactly one of Tier 1–4 /
Unsupported-mis-cited; orthogonal weakly-grounded flag; required rationale;
"topical relevance ≠ support" — intent shapes emphasis, never
verification). Verify is a **bounded loop**: one reword-down repair; on
exhaustion a claim lands **soft-flagged, never dropped, never silently
promoted** — with one hard exception: a **chunk claim whose quote fails the
presence check after repair is excluded and counted** (a fabricated quote
is the cardinal sin, not below-bar support; exclusion of fabrication is not
evidence-hiding). ⏸ Corpus-wide chunk grounding (unselected documents,
pre-findings answers) stays the retrieve-gated seam.

This is the **first real writer of the 001 information-layer substrate**:
real `block` / `addressable_unit` / `annotation` / `citation` rows at claim
grain, plus the run-scoped `synthesis_result` roll-up row.

## Deliverable

A PR on `task/013-synthesise` → `dev` that:

- Ships `synthesise.py`: `SynthesiseContext(scope_id, intent, context,
  characterisation_run_id, grouping_run_id=None)`; `synthesise_scope(...)` —
  characterisation load → artefact mint → landscape render (intent-aware
  claims call → typed-claim validation → block/unit/annotation writes) →
  when `grouping_run_id` present: grouping + findings load (via
  `query_findings`) → **section proposal** (validated; directive override) →
  per section: input assembly (assigned groups' findings + windowed frozen
  text of those findings' basis documents + computed spreads) → writer call
  → typed-claim validation (finding ids ⊆ section findings; chunk-quote
  presence check; pattern counts exact) → batched judge call → one bounded
  reword-down repair + one re-judge → block/unit/annotation/citation writes
  → roll-up row (last statement) → synthesis summary in
  `component.completed`.
- Ships **two backend seams, four prompts**: `SynthesisBackend` (+ OpenAI,
  stub) carrying **`synthesise_landscape_v1`**, **`synthesise_sections_v1`**
  and **`synthesise_section_v1`**, and `GroundingJudgeBackend` (+ OpenAI,
  stub) carrying **`grounding_judge_v1`** — the repo's fifth–eighth product
  prompts, all lead-authored, versioned, recorded in provenance.
- Ships **`query_findings`** — the scoped, deterministic, project-guarded
  findings-layer read surface (discharges the 012 recorded deviation on its
  stated terms — decision 10).
- Adds **one table — `synthesis_result`** — via one Alembic migration (gated
  change 1; table count 24 → 25, migration 13), project-scope-guarded.
- Registers `"synthesise"` in `COMPONENT_REGISTRY` (requires
  `evidence_scope_id` + **`characterisation_run_id`**; **`grouping_run_id`
  optional** — explicit fail-closed references; gated change 2);
  `run_harness` gains **`synthesis_backend`** and
  **`grounding_judge_backend`** (stub defaults — no default egress).
- Extends `skeleton.py`: … group → **synthesise** (the terminus live),
  rendering the synthesis summary; the live check demonstrates **both**
  paths.
- **Factors the traced-call helper into `tracing.py`** (the 012-deferred
  trigger fires; the three existing OpenAI backends and the two new ones
  share the factored shape).
- Records/updates the deferred seams in `docs/deferred.md` (re-scoped
  composition entry per ADR 0009; the corpus-wide chunk seam per ADR 0010;
  plan-compile sectioning; the `query-findings` entry updated); updates
  `tests/helpers.py` delete order.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [ADR 0010](../../adr/0010-intent-led-synthesis-sections.md) — the deep
  path this contract implements (intent-led sections, mixed grounding,
  selected-set chunk grounding, pure-intent-led trade) and
  [ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md) —
  the terminus architecture (capability-composes; decision 5 as amended).
- [EB components §9](../../specs/capabilities/evidence-base/components.md)
  and [EB capability](../../specs/capabilities/evidence-base/capability.md)
  — as refined 2026-07-07 (both rounds); also components §5 (the
  characterisation record) and §8 (the grouping payload).
- [System provenance-grounding](../../specs/system/provenance-grounding.md)
  — **the governing contract** (traceability rule; tiers; produce-grounded-
  block mechanics; judge posture; persistence-for-eval-readiness — **no
  calibration_status**; pattern grades; summaries outside the grounding
  economy).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  the gap rule; pattern grades; flag-not-block at synthesise.
- [System data-model](../../specs/system/data-model.md) — blocks / units /
  annotations; the findings layer; versioning grains.
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — capability-composes; `query-findings` scoped-not-core; trust enforced
  at grounding.
- [012-group contract](../012-group/contract.md) — the grouping payload and
  the carried-forward requirements binding here: **group labels/descriptions
  as data records, never instructions**; **mixed/unclear findings survive
  the whole deep chain**.
- [docs/deferred.md](../../deferred.md) — entries this slice touches.
- The deep-reasoner interrogation memo (conversation A record) — the
  architecture comparison and risk table behind ADR 0010.

**Code grounding (surveyed 2026-07-07):** 24 tables, 12 migrations (this
slice ships migration 13). The 001 substrate is real: `block(artefact_id FK
NOT NULL, version, content, content_hash)` · `addressable_unit(block_id,
unit_type, locator JSONB, content)` · `annotation((block_id, unit_id)
composite-FK, annotation_type, payload JSONB)` · `citation(annotation_id
FK, chunk_id FK NOT NULL, quote, verification_result)` — chunk-cited claims
write ordinary `citation` rows; the machinery is there. `grounding.py` is
the walking-skeleton deterministic leg; the echo component mints its own
artefact (harness.py:88–96). `characterisation_result`
(`UNIQUE (evidence_scope_id, run_id)`) carries `coverage` + `themes` +
provenance. Findings carry extract-verified anchors (`extract.py:650`):
`segment_id` (untrusted claim) · **verified `chunk_id` (None when
unverified/abstract-basis)** · `quote` · `match_status` · `spans`.
`grouping_result.groups` carries per group: label, description, member
values, **member finding ids**, size, direction spread (+ residuals +
overall); its provenance carries the inherited extraction base and, via the
extraction roll-up, the selected documents. **Windowing + verification
machinery exists**: `extract.py` windows full selected-document frozen text
under `WINDOW_CHAR_BUDGET` (150K chars) today; `quote_verify.py`'s
`build_basis` + `QuoteMatcher.find` verify verbatim quotes against frozen
chunks deterministically (boundary-spanning tolerant, abstract-basis aware,
graded match status) — chunk claims reuse this, not new machinery. Backend
pattern: protocol + stub + OpenAI class with pydantic `response_format`,
module-constant prompt + `PROMPT_VERSION`, caller-owned budget, validation
separated from the call (`gpt-5-mini` floor). Component wiring: registry
entry + required Config fields → context dataclass → `_run_scope_component`
→ `component.*` events; `skeleton.py` threads upstream run ids and switches
stub/live on `OPENAI_API_KEY`.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The complete produce-grounded-block mechanism lands in one slice** —
   deterministic quote-presence **and** the LLM judge **and** the bounded
   reword-down repair. Judge *calibration* stays eval-workstream territory;
   this slice's bar is mechanism correctness.
2. **Blocks are real information-layer rows at claim grain, on both
   paths.** Per block: one `block` row (claims' prose joined
   deterministically; `content_hash` per 001), one `addressable_unit` per
   claim (`text_span`, computed char offsets), and per claim-unit the
   annotation its type demands: **citation annotation** (finding and chunk
   claims — cited ids/chunks, per-citation verification, judge verdict +
   rationale + judge provenance), **pattern annotation** (shape-asserting
   claims — the validated shape, its grade and base), **theme annotation**
   (landscape theme claims). `citation` rows link claim-units to frozen
   chunks.
3. **Synthesise mints the artefact — one per run, titled from the scope
   intent** (verbatim, bounded, deterministic) — and binds blocks in
   **section order** (landscape block first, then the proposal's section
   order). Composition conventions (artefact summary, key-findings block,
   ordering conventions, supersede/lock-on-advance) stay at their seams.
   Re-run = new run = new artefact + new blocks. Empty characterisation →
   honest skip (roll-up + flag, no artefact).
4. **The landscape path: model prose over the characterisation record,
   intent as emphasis, pattern-validated, judge-free.** One
   `synthesise_landscape_v1` call (+ ≤1 repair) receives intent + the
   record (coverage aggregates, themes, unclustered count) as id-keyed data
   records; returns typed claims: **pattern claims** (numbers must equal
   the record's — wrong numbers reject) and **theme claims** (validated
   against the theme list, interpretive-shape grade). Anything else
   rejects. No citations, no judge — nothing chunk-anchored exists on this
   path, and every claim is deterministically checked instead. Landscape
   blocks carry the screened base via provenance.
5. **The deep path opens with an intent-led section proposal.** One
   `synthesise_sections_v1` call (+ ≤1 repair) receives **intent** + group
   summaries (labels, descriptions, sizes, spreads — id-keyed data) and
   returns a validated section list: 1..`SECTION_CAP` sections, each
   `{title, focus, group_ids}` — titles/focus bounded (length, control
   chars, non-generic), `group_ids` ⊆ real groups (overlap allowed — a
   group may inform several sections; exhaustiveness **not** required).
   Uncovered groups are counted and flagged (`groups_unsectioned`) — their
   findings stay visible in the roll-ups, never silently dropped. A
   fail-closed **`context["synthesis"]` directive** (the select/group
   precedent: object-only, allowed keys, caps, closed validation) can
   supply the section list instead — the compile target for the
   plan-shaped-sections seam; the executed source (`proposal` |
   `scope_context`) is recorded in provenance.
6. **Sections mix grounding modes; the writer never authors a finding
   quote.** Per section, one `synthesise_section_v1` call receives, as
   id-keyed data records: **intent** (emphasis, never instruction), the
   section spec, the assigned groups' member findings (references,
   direction, statistics, anchor quotes, labels), the **windowed frozen
   text of those findings' basis documents** (id-keyed chunk records under
   a plan-pinned `SYNTH_WINDOW_CHAR_BUDGET`; deterministic given the
   assignments — chunk scope derives from findings, inheriting
   select + extract discipline), and the section's computed direction
   spread. It returns typed claims:
   - **finding claim** — `cited_finding_ids ⊆ the section's finding set`
     (unknown/out-of-section ids reject); code resolves ids to
     extract-verified anchors and **re-runs the deterministic presence
     check** against frozen chunks (verify asserts what it writes — the
     assert-on-row-not-summary class; abstract-basis anchors located
     against the basis snapshot's chunks; unlocatable or extract-time-
     `failed` anchors → no citation row fabricated, `quote_unverified`,
     claim capped weakly-grounded, never dropped).
   - **chunk claim** — a verbatim quote + the source chunk record id; the
     claimed location is untrusted (the grounding-location-from-verification
     lesson): code runs `QuoteMatcher` against the whole document basis —
     verified spans become the `citation` rows. Presence failure rejects
     the claim (one repair); **still-failing chunk claims are excluded and
     counted** (`chunk_claims_rejected`) — fabricated quotes are the
     hard-fail class, not below-bar support.
   - **pattern claim** — stated counts must equal the section's computed
     spread (wrong counts reject; annotation on that claim's unit).
   Every cited claim must cite ≥ 1 finding or chunk — **no uncited-claim
   path** (Tier 4 stays a judge verdict, visibly flagged, never an
   authoring mode).
7. **The judge is `grounding_judge_v1`, batched per section, single-lane,
   reading the cited passages.** Per cited claim **exactly one** of Tier
   1–4 / `unsupported_mis_cited`, an orthogonal `weakly_grounded` flag, a
   required rationale. Judge input = claim + cited findings' context and/or
   cited chunk records + **the cited chunks' full frozen text**
   (deterministic lookup — pinned `synthesis_envelope_v1`, no
   neighbour-widening in v1; widening lands with `retrieve`) alongside the
   chunks' `segmentation_policy`. Posture: permissive about legitimate
   inference, strict about attribution fidelity; **topical relevance ≠
   support** — the guard that intent cannot buy a claim past verify.
   Persistence for eval-readiness: judge model + prompt version + verdict +
   rationale on the annotation payload; full I/O on Langfuse; **no
   calibration_status anywhere**.
8. **Repairs are bounded and reword down; exhaustion flags (or, for
   fabricated chunk quotes, excludes and counts).** Landscape and section
   proposal: one regeneration on validation rejection. Per section: one
   reword-down regeneration (prompt reused verbatim + judge rationales +
   claim-less instruction) on validation rejection or any
   `unsupported_mis_cited`, then one re-judge. Call budget known pre-run:
   **landscape ≤ 2 · sections ≤ 2 · per section ≤ 4** → total
   ≤ 4 + 4 × `SECTION_CAP` (plan-pinned; sections also bounded by the
   proposal validation). Backend failure after retries fails the component
   honestly (`component.failed`, no roll-up row); blocks already written
   remain (real, internally consistent) and the failure payload names them.
9. **Descriptive, never evaluative; no absence claims — both paths.**
   Prompt negative rules (deterministically assertable on the built
   prompts): no recommendations; no weighted/consensus verdicts (⏸); no
   absence/gap phrasing — gap annotations stay out of scope. The
   source/evidence policy object doesn't exist yet; the citable-bar
   flag-not-block rule is honoured by the weakly-grounded mechanism, and
   policy-conditioned flagging is a recorded seam. **Mixed/unclear findings
   are first-class throughout** (carried requirement): in the synthesis
   input, the spreads, and the prompts' don't-aggregate-away rule.
10. **`query-findings` lands as the scoped deterministic read surface; the
    agent-loop realisation stays at the capability-run seam.** The tool
    surface lands with its consumer (the deep path's loader); the
    agent-invoked form follows the standing skeleton-as-agent posture; the
    deferred.md entry is **updated to say exactly this**, never silently
    closed.
11. **Component wiring mirrors 004–012.** `"synthesise"` requires
    `evidence_scope_id` + `characterisation_run_id`; `grouping_run_id`
    optional (present → deep path; absent → landscape-only, flagged) — all
    compile-fail-closed; missing referenced rows → honest structural
    failure. `SynthesiseContext` via `functools.partial`;
    `_run_scope_component`; skeleton threads both run ids. Roll-up row is
    the **last** statement. Re-run → new run_id; same-run re-execution loud
    via `UNIQUE (evidence_scope_id, run_id)`. `component.completed` carries
    the synthesis summary; **no new event types**.
12. **Stubs are sentinel-driven; the suite is deterministic and
    egress-free.** `StubSynthesisBackend` emits fixture-declared typed
    claims on all three surfaces (real fixture anchor text so presence
    checks exercise for real; real record numbers so pattern validation
    exercises for real; fabricated-quote sentinels so the exclusion path
    exercises for real); `StubGroundingJudgeBackend` assigns verdicts
    sentinel-driven (every tier, unsupported, repair, flags). Determinism
    tests fix intent as input (the recompute unit is
    `(config-incl-intent, evidence)`). Suite and library defaults are stub
    + socket-deny.
13. **All four prompts carry the standing injection posture.**
    Characterisation content, finding text, anchor quotes, **windowed
    document text**, group labels/descriptions and **intent itself** enter
    as **id-keyed JSON data records under the data/instructions
    separation**; responses schema-constrained; no tools, no multi-turn, no
    free text acting on the world. A hijacked writer call can at worst emit
    mis-claims — bounded by typed-claim validation, the presence check and
    the judge lane; a hijacked judge call can at worst mis-tier — bounded
    by the closed enum and flagged-not-hidden semantics; a hijacked section
    proposal can at worst mis-shape sections — bounded by proposal
    validation and the unchanged verification of every claim within them.

### Schema

**Gated change 1 — one new table** (one migration; table count 24 → 25;
exact DDL plan-pinned, shape here binding):

```
synthesis_result  synthesis_result_id PK · project_id FK→project
                  · evidence_scope_id · run_id
                  · characterisation_run_id (executed reference, NOT NULL)
                  · grouping_run_id (executed reference, NULLABLE —
                      landscape-only runs have none)
                  · artefact_id FK→artefact NULLABLE (NULL only on the
                      empty-characterisation honest skip)
                  · synthesis_provenance JSONB NOT NULL (all four prompt
                      versions, models, judge envelope-policy version,
                      backend modes, per-path call/repair counts, the
                      section set + its source [proposal|scope_context] +
                      SECTION_CAP + window budget + groups_unsectioned, and
                      the inherited chain base: characterisation reference
                      + record summary hash; when deep — grouping_run_id +
                      facet + group count + finding-set size/sha256 + the
                      extraction base carried through)
                  · blocks JSONB NOT NULL (the landscape block entry + per
                      section: section title/focus, block_id, assigned
                      group ids, claim counts by type [finding|chunk|
                      pattern], tier distribution, unsupported/
                      weakly-grounded counts, citation verified/unverified
                      counts, chunk_claims_rejected, repair_taken)
                  · counts JSONB NOT NULL (blocks_written, sections_total,
                      claims_total by type, claims by verdict lane,
                      citations_verified, citations_unverified,
                      chunk_claims_rejected, findings_cited_distinct,
                      findings_total, groups_total, groups_unsectioned)
                  · flags JSONB NOT NULL (landscape_only ·
                      empty_characterisation · groups_unsectioned ·
                      unsupported_claims_present · weakly_grounded_present ·
                      chunk_claims_rejected · repair_path_taken — where
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

No existing-table changes: the 001 substrate is used **as built** — chunk
claims write ordinary `citation` rows (chunk_id + quote +
verification_result); tier/rationale/judge provenance ride the annotation
`payload` JSONB by design. Downgrade drops the table. `tests/helpers.py`
`delete_project_data` gains it in FK-safe order.

### Out of scope

- **Corpus-wide chunk-grounded narrative** — quoting *unselected*
  documents for pre-findings targeted answers: genuinely needs chunk
  selection → lands with `retrieve` (ADR 0009 decision 5 as amended by
  ADR 0010; risk note carried).
- **Plan-compile section machinery** — sections are proposal-derived or
  directive-supplied in v3.0; the plan-object compile of section specs is
  the recorded seam (the directive is its compile target).
- **Composition conventions** — artefact summary, grounded key-findings
  block, ordering conventions, supersede/lock-on-advance (their seams,
  re-scoped per ADR 0009).
- **Gap annotations / coverage-base machinery** — no absence claims are
  authored; the typed gap annotation arrives with its first consumer.
- **Weighted consensus / strength roll-up** (⏸); Unsupported/Tier-4
  never-contribute-positively is the recorded constraint on it.
- **Block summaries** (⏸), **artefact summary**, faithfulness judging —
  outside the grounding economy, outside this slice.
- **Block versioning beyond `version=1`**; **residual-bucket prose**; the
  **landscape→synthesis steer-point** (steering-modes seam); **agent-loop
  realisation / agent-invoked `query-findings`** (decision 10);
  judge-envelope widening + re-gather-targeted-evidence repair (land with
  `retrieve`); **`implementation_context_finding`**, cross-schema linkage,
  graph-structured synthesis (⏸).
- **Judge calibration / synthesis-quality evals** — the eval workstream
  owns the clean/weak line and prose quality; this slice's bar is
  mechanism correctness (named so the review stack doesn't mistake
  machinery tests for a quality claim).

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table
   count 24 → 25. No existing-table changes.
2. **Public interface** — the `"synthesise"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `characterisation_run_id` (required) and
   `grouping_run_id` (optional; both compile-fail-closed when present but
   unresolvable) + `run_harness` gains optional **`synthesis_backend`** and
   **`grounding_judge_backend`** (stub defaults — no default egress). No
   renames ride this slice.
3. **Runtime egress — four new generation surfaces** (the repo's
   fifth–eighth product prompts):
   - **`synthesise_landscape_v1`**: intent + the characterisation record
     (coverage aggregates, theme labels/descriptions/sizes) as id-keyed
     data records.
   - **`synthesise_sections_v1`**: intent + group summaries (labels,
     descriptions, sizes, spreads) as id-keyed data records.
   - **`synthesise_section_v1`**: intent + section spec + member findings
     (source-named references, directions, statistics, **verbatim anchor
     quotes**) + **windowed frozen text of the section's basis documents**
     (the 011 source-text class, full document text) + computed spreads.
   - **`grounding_judge_v1`**: claims + cited findings'/chunks' context +
     **the cited chunks' full frozen text**.
   Fixture corpus openly licensed by construction; full-I/O Langfuse traces
   (user-operated dev instance) carry these payloads — the standing
   009/011 trace posture, flagged for approval.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic` cover
it).

**Explicitly not crossed:** exactly four prompt-bearing surfaces (no agent
loop, no tools, no free text acting on the world); no new dependency; no
auth/tenancy/CI change; no existing-table change; no new event types; no
tag writes; no composition conventions beyond section-ordered block
binding.

**Spec flow-backs: already landed with ADRs 0009 + 0010** (capability.md,
components §§5/6/9, execution-orchestration; spec log 2026-07-07, two
entries) — approved in this contract's gate conversation; the contract
implements the refined spec. Remaining deferrals ride `docs/deferred.md`.

## Public / private boundary

- On the live path, what leaves: the characterisation record's
  coverage/theme content, group summaries, per-section finding records
  (source-named references, statistics, **verbatim quotes**), **windowed
  full frozen text of selected documents**, cited chunks' text, the user's
  **intent**, and model-generated labels — all fixture-corpus-derived
  (openly licensed by construction) — to the OpenAI API; full-I/O traces to
  the user-operated dev Langfuse. For arbitrary future corpora this is
  source-derived text (and user-authored intent) inheriting the project's
  sensitivity class — private-by-default otherwise.
- Committed artifacts (schema, prompt text, roll-up shapes, verification
  counts) are public-safe. **Block content, claims, section titles/focus
  and judge rationales are model-generated text over source-derived
  input** — public-safe for the fixture corpus, private-by-default
  otherwise; **untrusted model output as data**: bounded and validated at
  write, rendered escaped, never executed. Carried forward again: block
  content, section specs and judge rationales enter any future prompt as
  data records, never instructions.

## Model route

All four surfaces behind the two backend seams — `gpt-5-mini`-class floor
(the 009 nano lesson binding) → Bedrock at the seam swap, unchanged.

- **`synthesise_landscape_v1`** — landscape prose; typed claims
  (pattern | theme); negative rules: descriptive only, no recommendations,
  no absence claims, numbers only as given by the record; intent = emphasis
  data.
- **`synthesise_sections_v1`** — the section proposal; bounded list out;
  negative rules: sections name aspects of the question and the evidence,
  never verdicts; no generic/catch-all sections; group assignments only
  from the supplied ids.
- **`synthesise_section_v1`** — section prose; typed claims
  (finding | chunk | pattern); negative rules: descriptive only — no
  recommendations, no evaluative/consensus verdicts, no absence claims;
  report spreads as given; mixed/unclear reported, never aggregated away;
  claim within what the cited evidence supports (claim less, cite
  precisely); quotes verbatim from the supplied text only.
- **`grounding_judge_v1`** — the classifier; closed verdict enum +
  `weakly_grounded` + required rationale per claim; permissive on
  legitimate inference, strict on attribution fidelity; topical relevance ≠
  support.

All four are **prompt-bearing, lead-authored, versioned**, recorded in
`synthesis_provenance`, the event payload and (judge) the annotation
payloads. The judge rubric is lead-only per AGENTS.md.

## Disciplines binding this slice

- **The traceability rule is the slice.** Every claim traces to verified
  quotes (finding anchors or presence-checked chunk quotes), is
  deterministically validated against the recorded shape, or is visibly
  flagged — no fourth state, no silent promotion, no post-hoc citation
  path. Intent shapes emphasis, never verification.
- **Flag, don't drop** — failed anchors, unsupported and weakly-grounded
  claims land visible with status; uncovered groups counted. The one
  exclusion is fabricated chunk quotes — excluded **and counted**, never
  silently.
- **Honest absence** — no absence claims at all; landscape blocks carry
  the screened base, deep sections the selected/extracted base, via
  provenance.
- **Deterministic where claimed** — quote presence, citation resolution,
  offsets, spread computation, pattern/theme/section validation,
  windowing, cross-checks, ordering and writes are deterministic; at most
  4 + 4 × `SECTION_CAP` interpretive calls per run, each fully
  attributable. Determinism tests fix intent as input.
- **Model only what behaves** — no gap rows, no consensus fields, no
  summary columns, no calibration_status; the roll-up row and the 001
  substrate rows are the only new state.
- **Never silent, never fake** — stubs say so; missing upstream state
  fails structurally; a failed call fails the component honestly;
  grouping↔findings and spread mismatches are structural failures.

## Stop conditions

- Any gated change (schema · public interface · egress) not yet approved,
  or any change beyond them (existing-table change, a fifth prompt
  surface, new dependency, gap/consensus/summary machinery, new event
  types).
- Any *suite or library-default* code path would perform network I/O.
- The synthesis wants evaluative output, absence claims, corpus-wide chunk
  grounding (the ⏸ seam), or composition conventions — halt.
- Either backend wants capabilities beyond schema-constrained calls —
  halt.
- The claim/citation model can't express something without weakening
  verification (pressure to accept uncited/unvalidated claims, or finding
  quotes authored by the writer) — design change; halt, never weaken the
  bar silently.
- `make verify` red with unclear root cause; or the turn/token budget is
  spent.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) — green,
  deterministic, zero egress (socket-deny covers synthesise round-trips on
  both paths; suite runs on the stubs only).
- **One manual live check, both paths** (evidence in verification.md):
  skeleton end-to-end with `OPENAI_API_KEY` (+ `LANGFUSE_*`) against the
  fixture corpus — (a) a **full deep run**: intent-led sections proposed
  and rendered; finding-, chunk- and pattern-claims present with real
  citations to frozen chunks; tier distribution and any
  unsupported/weakly-grounded claims shown honestly; any rejected chunk
  claims counted; repair path exercised or its absence noted;
  `groups_unsectioned` honest; (b) a **landscape-only run** (no
  `grouping_run_id`): artefact + landscape block written, `landscape_only`
  flag set. All four prompts visible in dev Langfuse (versions,
  tokens/cost) with run-level scores (claims-valid share,
  citation-verified share, unsupported share, chunk-rejection share);
  per-run counts and an honest cost note; keys absent from captured
  output.
- Deterministic vs AI eval: all suite checks deterministic (stub
  backends); section quality, prose quality and judge calibration are eval
  territory — this slice's bar is mechanism correctness, invariant
  enforcement, honest flags and provenance fidelity.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 25.
- Named test results: **path selection** (characterisation_run_id required;
  grouping_run_id absent → landscape-only + flag; present → deep path;
  missing referenced rows → structural failure), **landscape validation**
  (wrong pattern numbers rejected then repaired-or-failed; theme claims
  validated; disallowed types rejected; empty characterisation → honest
  skip, no artefact), **section proposal validation** (1..SECTION_CAP;
  bounded non-generic titles; group_ids ⊆ real groups; uncovered groups →
  `groups_unsectioned` counted; malformed directive fails closed; directive
  override recorded as source), **finding-claim citation resolution**
  (cited ids ⊆ section findings — unknown/out-of-section reject; anchors
  reused verbatim; verified chunk_id → citation row; abstract-basis
  re-location; failed/unlocatable anchor → no fabricated citation row +
  `quote_unverified` + weakly-grounded cap, never dropped), **chunk-claim
  verification** (verbatim quote presence-checked against the whole
  document basis; claimed chunk id treated as untrusted — verified spans
  become the citation rows; boundary-spanning quotes located; fabricated
  quote → claim rejected, one repair, then excluded and counted —
  `chunk_claims_rejected`), **claim/unit integrity** (every cited claim ≥ 1
  citation target; pattern counts equal computed spreads; annotations exist
  iff their claim does, on that claim's unit; offsets exact; composite-FK
  integrity; content_hash correct), **judge semantics** (single-lane enum;
  rationale required; verdict + judge provenance + envelope version
  persisted; weakly_grounded orthogonal; judge input includes cited chunk
  text; chunk and finding claims both judged), **repair semantics**
  (bounded exactly as decision 8; budgets test-asserted: ≤ 2 landscape,
  ≤ 2 sections, ≤ 4 × sections; exhaustion → flags, claims retained —
  except fabricated chunk quotes, excluded and counted), **flag-not-drop**
  (unsupported and weakly-grounded claims persist visibly; mixed/unclear
  visible in inputs, spreads and prose-input data), **descriptive posture**
  (negative rules asserted on all four built prompts; an injection-shaped
  theme label, group label, finding quote or document chunk lands as inert
  data — including inside the windowed text), **artefact/composition v1**
  (one artefact per run, intent-derived bounded title; section-ordered
  block binding; re-run → new artefact; same-run re-execution loud; backend
  failure → `component.failed`, no roll-up row, prior blocks named),
  **determinism** (two stub runs with fixed intent → identical payload
  columns, block content and hashes; windowing deterministic),
  **provenance required keys** (four prompt versions, envelope policy,
  section set + source, window budget, per-path call counts, the inherited
  chain base), delete-order integrity.
- Live-run evidence per the manual check above (both paths).
- Public-safety confirmation (egress was fixture-corpus text + intent
  only; traces on the user-operated instance; keys clean).
- Deferred seams recorded/updated in `docs/deferred.md`: **corpus-wide
  chunk-grounded narrative** (ADR 0009 as amended; lands with `retrieve`;
  risk note carried) · **plan-compile section machinery** (directive = its
  compile target) · **composition conventions** (re-scoped: composition
  lives in synthesise; summary/key-findings/ordering-conventions/versioning
  remain) · gap annotations (first consumer) · policy-conditioned
  citable-bar flagging · consensus roll-up (never-contribute constraint
  restated) · block summaries + faithfulness judging · agent-loop
  synthesise + agent-invoked `query-findings` (capability-run seam — the
  012 entry updated, not closed) · judge-envelope widening +
  re-gather-targeted-evidence repair (land with `retrieve`) ·
  synthesis/judge quality evals (incl. envelope-policy and SECTION_CAP
  calibration).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate, four new runtime-egress generation
surfaces ride the slice (windowed full document text now enters product
prompts twice over), and this is the **trust invariant's landing slice**.
Contract- and plan-stage adversarial reviews standard; review stack sized
per the review-economy notes. ADRs 0009 + 0010 cover the architecture; a
step-4 ADR only if implementation decisions prove consequential beyond
them.

Review focus:
- **Provenance/honesty (the headline lane)**: co-emitted citations only;
  presence checks against frozen chunks for both claim kinds; verified
  spans (never model-claimed locations) become citation rows; single-lane
  verdicts persisted; landscape/pattern numbers deterministically
  validated; unsupported/weak claims flagged never dropped; fabricated
  chunk quotes excluded **and counted**; mixed/unclear survive; uncovered
  groups counted; no absence phrasing; intent shapes emphasis never
  verification; provenance carries the inherited chain base per path.
- **Security / prompt surfaces**: four prompts consuming untrusted
  source-derived text (including full windowed documents) and
  model-generated labels — id-keyed data records, schema-constrained
  outputs, closed enums, no tools; outputs bounded and validated at write;
  key hygiene; egress bounded (pre-run budgets, socket-deny on suite
  paths).
- **Correctness**: path/reference resolution; section validation; window
  assembly determinism; citation resolution across verified/abstract/
  failed anchors and chunk quotes; offsets; composite-FK integrity; repair
  semantics; roll-up-last ordering; FK and delete order.
- **Scope**: no corpus-wide chunk grounding, no composition conventions,
  no gap/consensus/summary machinery, no fifth prompt, suite egress-free.
