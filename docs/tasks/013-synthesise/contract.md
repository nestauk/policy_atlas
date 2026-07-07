# Task contract: 013-synthesise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 4) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADRs: [0009](../../adr/0009-capability-composes-synthesise-terminus.md)
> (terminus architecture; decision 5 as amended) +
> [0010](../../adr/0010-intent-led-synthesis-sections.md) (intent-led
> sections, mixed grounding, selected-set chunk grounding; § Amendment =
> the rev-4 round) — both Accepted 2026-07-07.
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
>   at every depth (landscape path added); components as a registry,
>   breadth ⊥ depth; chunk-grounded prose sanctioned as a retrieve-gated
>   seam; `characterisation_run_id` (required) + `grouping_run_id`
>   (optional).
> - **rev 3** (2026-07-07, user challenge on intent-relevance → independent
>   deep-reasoner interrogation → **ADR 0010**): group-per-block replaced
>   by intent-led sections; intent enters synthesis (sections + emphasis
>   data); selected-set chunk grounding pulled in-slice (ADR 0009 d5
>   amended — only corpus-wide is retrieve-gated); pure intent-led (user
>   choice — no rendered backbone); four prompt surfaces; library →
>   registry.
> - **rev 4** (2026-07-07, third round of user challenges — adjudicated,
>   ADR 0010 § Amendment): **(a) "deep path" terminology retired** —
>   synthesise always runs; it renders **content modes by available
>   references** (landscape always; question-led grounded synthesis when
>   the run produced findings). **(b) Claim vocabulary completed to the
>   spec's full set** — **gap claims** (graded, coverage-base-carrying,
>   corpus-promotion fail-closed on `search_coverage_record`) and
>   **reasoning claims** (visibly-labelled Tier-4 authoring, judge
>   strict-routing guard) join finding/chunk/pattern/theme; the rev-2/3
>   blanket "no absence claims" rule is replaced by the spec's own
>   fail-closed gap discipline (EB's most consequential claim class,
>   restored). **(c) Whole-document windowing replaced by scoped
>   retrieval** — per section: cited findings' anchor chunks always +
>   top-k selected-set chunks by embedding relevance to the section focus
>   (the 009 unit vectors' **first reader**; in-memory over JSONB vectors,
>   no index, no new dependency) — recorded as the **first increment of
>   the `retrieve` seam** (grounding profile, selected-set scope),
>   upgraded not duplicated by the future retrieve slice.

## Goal

Add **synthesise** — EB component 9 and, per ADR 0009, **EB's terminal
component: it runs at every depth** and **composes the one EB artefact** —
mints it (intent-derived bounded title), renders content into grounded
blocks, binds them in section order. The orchestrator shapes the artefact
at plan time; composition is capability expertise and happens here. Per
ADR 0010, the output is **shaped by what was asked, not by what was
studied**.

Synthesise renders **content modes by available references** (the
components are a registry; dependencies travel as explicit fail-closed run
references — there is no "deep path", only content a run did or didn't
produce):

- **Landscape content (always — the minimum an artefact needs):** model
  prose over the referenced characterisation record, intent as emphasis
  input; typed claims deterministically validated (pattern counts must
  equal the record; theme claims reference real themes; **gap claims**
  over the screened base validated against the coverage data and the 007
  `search_coverage_record` machinery).
- **Question-led grounded synthesis (when the run produced findings):
  intent-led sections.** The section set derives from the **user's
  intent** (one bounded schema-constrained proposal call over intent +
  group summaries; fail-closed `context["synthesis"]` directive override;
  plan-compile sectioning = the recorded seam). Each section's typed
  claims span the system's **full honest assertion vocabulary**:
  - **finding claims** — cite finding ids → extract-verified anchors; the
    model never authors these quotes;
  - **chunk claims** — verbatim quotes from the **selected set's** frozen
    text, chosen by **scoped retrieval** (anchor chunks always + top-k by
    embedding relevance to the section focus — relevance-ranked, not
    whole-document context-crowding; select's coverage discipline
    inherited); the texture the narrow IOF schema cannot carry;
  - **pattern claims** — counts must equal computed spreads (the
    direction-spread steer; v2's `effect_consensus` counts as this steer);
  - **gap claims** — the absence dual, graded per the provenance specs
    with deterministic per-grade validation and a required coverage base:
    base-labelled to the **selected/extracted base** by default; promoted
    to corpus-level absence **only** on a referenced non-`inadequate`
    `search_coverage_record` (else fail-closed degraded to base-labelled);
    inferred domain gaps ship visibly labelled as inference, never gated;
  - **reasoning claims** — uncited framing/context, **visibly labelled
    Tier 4 at authoring**; the judge applies the spec's strict-routing
    rule (policy-specific / empirical / causal / evaluative content must
    not hide there); never counts toward strength roll-ups.
  **Groups are input, not structure**: summaries steer sectioning and
  emphasis; uncovered groups counted (`groups_unsectioned`), never
  silently dropped. **Descriptive always**: no recommendations, no
  weighted verdicts (⏸ consensus seam).

Every cited claim goes through the **real `produce-grounded-block`
mechanism**: synthesise → cite → verify → write, cite/verify mandatory,
citations **co-emitted, never post-hoc**. Verify = the **deterministic
quote-presence check** against frozen chunks **plus the LLM-as-judge
grounding classifier** (single lane: exactly one of Tier 1–4 /
Unsupported-mis-cited; orthogonal weakly-grounded flag; required rationale;
"topical relevance ≠ support" — intent shapes emphasis, never
verification). Verify is a **bounded loop**: one reword-down repair; on
exhaustion a claim lands **soft-flagged, never dropped, never silently
promoted** — one hard exception: a **chunk claim whose quote fails the
presence check after repair is excluded and counted** (fabrication is the
hard-fail class, not below-bar support). ⏸ Corpus-wide chunk grounding
(unselected documents) stays the retrieve-gated seam.

This is the **first real writer of the 001 information-layer substrate**
(real `block` / `addressable_unit` / `annotation` / `citation` rows at
claim grain), the **first reader of the 009 embedding-unit vectors**, and
it ships the run-scoped `synthesis_result` roll-up row.

## Deliverable

A PR on `task/013-synthesise` → `dev` that:

- Ships `synthesise.py`: `SynthesiseContext(scope_id, intent, context,
  characterisation_run_id, grouping_run_id=None)`; `synthesise_scope(...)`
  — characterisation load → artefact mint → landscape render (intent-aware
  claims call → typed-claim validation incl. gaps → block/unit/annotation
  writes) → when `grouping_run_id` present: grouping + findings load (via
  `query_findings`) → **section proposal** (validated; directive override)
  → per section: **scoped retrieval** (anchor chunks + top-k
  embedding-relevant selected-set chunks under plan-pinned k/char budgets)
  → writer call → typed-claim validation (six claim types, per-type rules)
  → batched judge call (cited + reasoning claims) → one bounded
  reword-down repair + one re-judge → block/unit/annotation/citation
  writes → roll-up row (last statement) → synthesis summary in
  `component.completed`.
- Ships **two backend seams, four prompts**: `SynthesisBackend` (+ OpenAI,
  stub) carrying **`synthesise_landscape_v1`**, **`synthesise_sections_v1`**
  and **`synthesise_section_v1`**, and `GroundingJudgeBackend` (+ OpenAI,
  stub) carrying **`grounding_judge_v1`** — the repo's fifth–eighth product
  prompts, all lead-authored, versioned, recorded in provenance. Scoped
  retrieval reuses the **009 `EmbeddingBackend`** for the section-focus
  query embedding (no new backend).
- Ships **`query_findings`** — the scoped, deterministic, project-guarded
  findings-layer read surface (discharges the 012 recorded deviation on
  its stated terms — decision 11) — and the **scoped-retrieval helper**
  (in-memory cosine over the selected set's stored unit vectors; the
  `retrieve` seam's first increment, behind a swappable function seam).
- Adds **one table — `synthesis_result`** — via one Alembic migration
  (gated change 1; table count 24 → 25, migration 13),
  project-scope-guarded.
- Registers `"synthesise"` in `COMPONENT_REGISTRY` (requires
  `evidence_scope_id` + **`characterisation_run_id`**; **`grouping_run_id`
  optional**; gated change 2); `run_harness` gains **`synthesis_backend`**
  and **`grounding_judge_backend`** (stub defaults — no default egress;
  the existing `embedding_backend` param covers the retrieval query).
- Extends `skeleton.py`: … group → **synthesise** (the terminus live),
  rendering the synthesis summary; the live check demonstrates **both
  content modes**.
- **Factors the traced-call helper into `tracing.py`** (the 012-deferred
  trigger fires).
- Records/updates the deferred seams in `docs/deferred.md`; updates
  `tests/helpers.py` delete order.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [ADR 0010](../../adr/0010-intent-led-synthesis-sections.md) **including
  § Amendment** (the rev-4 round: content modes, full claim vocabulary,
  scoped retrieval) and
  [ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md)
  (capability-composes; decision 5 as amended).
- [EB components §9](../../specs/capabilities/evidence-base/components.md)
  and [EB capability](../../specs/capabilities/evidence-base/capability.md)
  — as refined 2026-07-07 (three rounds); also components §5 (the
  characterisation record) and §8 (the grouping payload).
- [System provenance-grounding](../../specs/system/provenance-grounding.md)
  — **the governing contract**: the traceability rule's three honest
  categories; tiers 1–4 (Tier 4 "honest only because visibly labelled",
  with the not-a-safe-harbour strict-routing rule); **gaps** (three
  grades; the coverage base; `search_coverage_record` fail-closed rule);
  patterns (grades); produce-grounded-block mechanics; judge posture;
  persistence-for-eval-readiness (**no calibration_status**).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  EB's gap rule (the pipeline-ladder coverage base; `not_selected` /
  `not_extracted` never license absence; the shallow landscape as the
  structural check on a deep absence).
- [System data-model](../../specs/system/data-model.md) — blocks / units /
  annotations (gaps and patterns are typed annotations in the same layer);
  the findings layer; coverage states as gap provenance.
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — capability-composes; `retrieve`'s contract (what the full tool is —
  the scoped helper here is its first increment, not its replacement);
  `query-findings` scoped-not-core.
- [012-group contract](../012-group/contract.md) — the grouping payload
  and the carried requirements: **labels as data, never instructions**;
  **mixed/unclear findings survive**.
- [docs/deferred.md](../../deferred.md) — entries this slice touches
  (incl. the 009 "vectors ahead of their first reader" entry — discharged
  here).
- The deep-reasoner interrogation memo (conversation A record) — the
  architecture comparison behind ADR 0010.

**Code grounding (surveyed 2026-07-07):** 24 tables, 12 migrations (this
slice ships migration 13). The 001 substrate is real: `block` /
`addressable_unit` / `annotation((block_id, unit_id) composite-FK,
annotation_type, payload JSONB)` / `citation(chunk_id FK NOT NULL, quote,
verification_result)` — gap/pattern/reasoning annotations are new
`annotation_type` values riding the payload JSONB by design; chunk-cited
claims write ordinary `citation` rows. `search_coverage_record` (007): one
fail-closed record per acquire run — boundary, stop condition, adequacy
verdict + origin; the corpus-promotion gate for gap claims.
`chunk_embedding` (009): one vector per embedding-unit (JSONB), eager over
all ingested snapshots, **no reader yet**; `EmbeddingBackend` +
`embedding_backend` harness param exist. `characterisation_result` carries
`coverage` + `themes` + provenance. Findings carry extract-verified
anchors (verified `chunk_id`, quote, match status, spans).
`grouping_result.groups` carries per group: label, description, member
values, member finding ids, size, direction spread (+ residuals +
overall); provenance carries the inherited extraction base.
`quote_verify.py`'s `build_basis` + `QuoteMatcher.find` verify verbatim
quotes against frozen chunks deterministically. Backend pattern: protocol
+ stub + OpenAI class with pydantic `response_format`, module-constant
prompt + `PROMPT_VERSION`, caller-owned budget, validation separated from
the call (`gpt-5-mini` floor). Component wiring: registry entry + required
Config fields → context dataclass → `_run_scope_component` →
`component.*` events.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The complete produce-grounded-block mechanism lands in one slice** —
   deterministic quote-presence **and** the LLM judge **and** the bounded
   reword-down repair. Judge *calibration* stays eval-workstream
   territory; this slice's bar is mechanism correctness.
2. **Blocks are real information-layer rows at claim grain, in both
   content modes.** Per block: one `block` row (claims' prose joined
   deterministically; `content_hash` per 001), one `addressable_unit` per
   claim, and per claim-unit the annotation its type demands: **citation
   annotation** (finding/chunk claims — cited ids/chunks, per-citation
   verification, judge verdict + rationale + judge provenance), **pattern
   annotation** (validated shape + grade + base), **theme annotation**
   (landscape theme claims), **gap annotation** (grade + coverage base +
   evidence refs — the `search_coverage_record` id for corpus-level, the
   sparsity signal for acknowledged), **reasoning annotation** (the
   visible Tier-4 label + the judge's strict-routing verdict). `citation`
   rows link cited claim-units to frozen chunks.
3. **Synthesise mints the artefact — one per run, titled from the scope
   intent** (verbatim, bounded, deterministic) — and binds blocks in
   section order (landscape first). Composition conventions (artefact
   summary, key-findings block, ordering conventions,
   supersede/lock-on-advance) stay at their seams. Re-run = new run = new
   artefact + new blocks. Empty characterisation → honest skip (roll-up +
   flag, no artefact).
4. **Landscape content: model prose over the characterisation record,
   intent as emphasis, deterministically validated, judge-free except
   reasoning claims.** One `synthesise_landscape_v1` call (+ ≤1 repair):
   intent + the record (coverage aggregates, themes, unclustered count) +
   the scope's `search_coverage_record` summaries as id-keyed data.
   Claims: **pattern** (numbers must equal the record) · **theme**
   (validated against the theme list) · **gap** (screened-base; grade
   validated per decision 7) · **reasoning** (labelled). Anything else
   rejects. No citations — nothing chunk-anchored exists in this mode, and
   none is faked.
5. **Grounded synthesis opens with an intent-led section proposal.** One
   `synthesise_sections_v1` call (+ ≤1 repair): intent + group summaries
   (id-keyed data) → validated section list: 1..`SECTION_CAP` sections,
   each `{title, focus, group_ids}` — bounded non-generic titles/focus;
   `group_ids` ⊆ real groups (overlap allowed; exhaustiveness not
   required). Uncovered groups → `groups_unsectioned`, counted and
   flagged. A fail-closed **`context["synthesis"]` directive** (the
   select/group precedent) can supply the section list — the compile
   target of the plan-shaped-sections seam; executed source recorded.
6. **Section inputs come from scoped retrieval, not whole-document
   windows.** Per section, the writer's chunk context =
   (a) the section's cited-finding **anchor chunks** (the evidence spine —
   always included), plus (b) the **top-k selected-set chunks by embedding
   relevance**: the section focus (+ intent) is embedded via the existing
   `EmbeddingBackend`; cosine ranks the selected documents' stored
   embedding-unit vectors **in memory** (JSONB vectors, ~10³ scale — no
   index, no new dependency); the top-k under plan-pinned
   `SYNTH_CHUNK_TOP_K` / `SYNTH_CHUNK_CHAR_BUDGET` enter as id-keyed chunk
   records. Deterministic given stored vectors + the query embedding
   (memoised per section; provenance records the retrieval parameters and
   chosen chunk ids). This is the **`retrieve` seam's first increment**
   (grounding/citation profile, selected-set scope) behind a swappable
   helper seam — the future retrieve slice upgrades it to index-backed
   hybrid corpus-wide retrieval; it is **not** a parallel retrieval
   system. It also makes this slice the 009 vectors' **first reader**
   (that deferred entry is discharged, not duplicated).
7. **Six claim types, each with its own deterministic validation; the
   writer never authors a finding quote.** Per section, one
   `synthesise_section_v1` call receives (id-keyed data): intent, section
   spec, assigned groups' member findings (references, direction,
   statistics, anchor quotes, labels), the scoped-retrieval chunk records,
   the section's computed direction spread, and the scope's
   `search_coverage_record` summaries. Claims:
   - **finding** — `cited_finding_ids ⊆ the section's finding set`
     (unknown/out-of-section reject); code resolves to extract-verified
     anchors and **re-runs the deterministic presence check** (verify
     asserts what it writes; abstract-basis anchors re-located;
     unlocatable/`failed` anchors → no fabricated citation row,
     `quote_unverified`, weakly-grounded cap, never dropped).
   - **chunk** — verbatim quote + source chunk record id; the claimed
     location is untrusted — `QuoteMatcher` runs against the whole
     document basis and **verified spans become the citation rows**;
     presence failure rejects (one repair); still-failing → **excluded
     and counted** (`chunk_claims_rejected`).
   - **pattern** — stated counts must equal the section's computed spread.
   - **gap** — grade ∈ {coverage, acknowledged, inferred} + a coverage
     base ∈ the pipeline ladder, both required. Validation per grade:
     *corpus-level phrasing* requires a referenced non-`inadequate`
     `search_coverage_record` — absent/`inadequate` → the claim is
     **fail-closed degraded** to its base-labelled form (or rejected if
     the model refuses the degradation on repair); *acknowledged* requires
     the sparsity signal to hold against the coverage/spread data
     (validated numerically); *inferred* ships visibly labelled as
     inference — never gated, never phrased as proven absence (phrasing
     rules prompt-enforced + judge-checked). In grounded-synthesis
     sections the default base is **selected/extracted, base-labelled**
     (`not_selected`/`not_extracted` never license absence — the EB gap
     rule).
   - **reasoning** — uncited, **visibly labelled Tier 4** at authoring;
     bounded count per block; the judge applies strict routing (empirical
     / causal / policy-specific / evaluative content → flagged
     `unsupported_mis_cited`, never allowed to hide in Tier 4); never
     counts toward any future strength roll-up (the recorded constraint).
   - **theme** — landscape mode only.
   There is **no silent uncited path**: every claim is cited, validated,
   or visibly labelled.
8. **The judge is `grounding_judge_v1`, batched per block, single-lane,
   reading the cited passages.** Judges **cited claims** (finding + chunk:
   full verdict lane, Tier 1–4 / `unsupported_mis_cited` + weakly_grounded
   + required rationale; input includes the cited chunks' full frozen
   text — pinned `synthesis_envelope_v1`) and **reasoning claims**
   (strict-routing check only). Gap/pattern/theme claims are
   deterministically validated, not judged. Posture: permissive about
   legitimate inference, strict about attribution fidelity; topical
   relevance ≠ support. Persistence for eval-readiness: judge model +
   prompt version + verdict + rationale on the annotation payload; full
   I/O on Langfuse; **no calibration_status anywhere**.
9. **Repairs are bounded and reword down; exhaustion flags (or, for
   fabricated chunk quotes, excludes and counts).** Landscape and section
   proposal: one regeneration on validation rejection. Per section: one
   reword-down regeneration (+ judge rationales + claim-less instruction)
   on validation rejection or any `unsupported_mis_cited`, then one
   re-judge. Call budget known pre-run: **landscape ≤ 2 · sections ≤ 2 ·
   per section ≤ 4 generation calls + 1 embedding call** → total
   ≤ 4 + 5 × `SECTION_CAP`. Backend failure after retries fails the
   component honestly (`component.failed`, no roll-up row); blocks already
   written remain and the failure payload names them.
10. **Descriptive, never evaluative — and absence is disciplined, not
    banned.** Prompt negative rules (deterministically assertable): no
    recommendations; no weighted/consensus verdicts (⏸); absence only as
    validated gap claims per decision 7 — never free-phrased. The
    source/evidence policy object doesn't exist yet; the citable-bar
    flag-not-block rule is honoured by the weakly-grounded mechanism;
    policy-conditioned flagging stays a recorded seam. **Mixed/unclear
    findings are first-class throughout** (carried requirement).
11. **`query-findings` lands as the scoped deterministic read surface; the
    agent-loop realisation stays at the capability-run seam.** The
    deferred.md entry is updated to say exactly this, never silently
    closed.
12. **Component wiring mirrors 004–012.** `"synthesise"` requires
    `evidence_scope_id` + `characterisation_run_id`; `grouping_run_id`
    optional (present → grounded synthesis; absent → landscape-only,
    flagged) — compile-fail-closed; missing referenced rows → structural
    failure. Roll-up row last; re-run → new run_id; same-run re-execution
    loud (`UNIQUE (evidence_scope_id, run_id)`); `component.completed`
    carries the summary; **no new event types**.
13. **Stubs are sentinel-driven; the suite is deterministic and
    egress-free.** `StubSynthesisBackend` emits fixture-declared typed
    claims across all six types (real anchor text → presence checks
    exercise for real; real record numbers → pattern/gap validation
    exercises for real; fabricated-quote and corpus-absence sentinels →
    the exclusion and degradation paths exercise for real);
    `StubGroundingJudgeBackend` sentinel-driven (every tier, unsupported,
    strict-routing, repair, flags); the stub embedding path reuses 009's
    deterministic stub vectors so scoped retrieval is fully exercised
    egress-free. Determinism tests fix intent as input.
14. **All four prompts carry the standing injection posture.** Intent,
    characterisation content, coverage-record summaries, finding text,
    anchor quotes, retrieved chunk text and group labels enter as
    **id-keyed JSON data records**; responses schema-constrained; no
    tools, no multi-turn, no free text acting on the world. Hijack bounds:
    a writer emits mis-claims (bounded by per-type validation, presence
    checks, the judge); a judge mis-tiers (bounded by the closed enum and
    flag-not-hide); a section proposal mis-shapes (bounded by validation
    and unchanged claim verification); retrieval poisoning via adversarial
    chunk text mis-ranks context (bounded: it can only surface
    in-corpus frozen text, which then faces the same claim bar).

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
                  · synthesis_provenance JSONB NOT NULL (all four prompt
                      versions, models, judge envelope-policy version,
                      backend modes, per-mode call/repair counts, the
                      section set + source [proposal|scope_context] + caps,
                      the scoped-retrieval parameters (embedding profile,
                      top-k, char budget, per-section chosen chunk ids
                      hash), and the inherited chain base:
                      characterisation reference + record summary hash;
                      when grounded — grouping_run_id + facet + group
                      count + finding-set size/sha256 + the extraction
                      base carried through)
                  · blocks JSONB NOT NULL (the landscape block entry + per
                      section: title/focus, block_id, assigned group ids,
                      claim counts by type [finding|chunk|pattern|gap|
                      reasoning|theme], tier distribution, unsupported/
                      weakly-grounded counts, citation verified/unverified
                      counts, chunk_claims_rejected, gap_claims_degraded,
                      repair_taken)
                  · counts JSONB NOT NULL (blocks_written, sections_total,
                      claims_total by type, claims by verdict lane,
                      citations_verified, citations_unverified,
                      chunk_claims_rejected, gap_claims_degraded,
                      findings_cited_distinct, findings_total,
                      groups_total, groups_unsectioned)
                  · flags JSONB NOT NULL (landscape_only ·
                      empty_characterisation · groups_unsectioned ·
                      unsupported_claims_present · weakly_grounded_present
                      · chunk_claims_rejected · gap_claims_degraded ·
                      repair_path_taken — where true)
                  · created_at
                  Composite FKs (evidence_scope_id, project_id),
                  (run_id, project_id) — cross-project guards
                  FK (evidence_scope_id, characterisation_run_id) →
                      characterisation_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, grouping_run_id) →
                      grouping_result (evidence_scope_id, run_id)
                  UNIQUE (evidence_scope_id, run_id)
```

No existing-table changes: the 001 substrate is used as built (gap /
pattern / theme / reasoning annotations are `annotation_type` values with
JSONB payloads; chunk claims write ordinary `citation` rows). Downgrade
drops the table. `tests/helpers.py` `delete_project_data` gains it in
FK-safe order.

### Out of scope

- **Corpus-wide chunk-grounded narrative** — quoting *unselected*
  documents: needs real corpus-scale retrieval → lands with the full
  `retrieve` slice (ADR 0009 d5 as amended; risk note carried).
- **The full `retrieve` tool** — index-backed hybrid lexical+dense
  corpus-wide retrieval with profiles and the adapter seam; the scoped
  helper here is its recorded first increment, behind a seam it upgrades.
- **Plan-compile section machinery** — the `context["synthesis"]`
  directive is its compile target; the seam stays recorded.
- **Composition conventions** — artefact summary, grounded key-findings
  block, ordering conventions, supersede/lock-on-advance (their seams).
- **Weighted consensus / strength roll-up** (⏸); Unsupported/Tier-4/
  gap/reasoning never-contribute constraints restated on it.
- **Block summaries** (⏸), **artefact summary**, faithfulness judging.
- **Block versioning beyond `version=1`**; **residual-bucket prose**; the
  **landscape→synthesis steer-point**; **agent-loop realisation /
  agent-invoked `query-findings`** (decision 11); judge-envelope widening
  + re-gather-targeted-evidence repair (land with `retrieve`);
  **`implementation_context_finding`**, cross-schema linkage,
  graph-structured synthesis (⏸).
- **Judge calibration / synthesis-quality / retrieval-quality evals** —
  the eval workstream owns them; this slice's bar is mechanism
  correctness (named so the review stack doesn't mistake machinery tests
  for a quality claim).

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table
   count 24 → 25. No existing-table changes.
2. **Public interface** — the `"synthesise"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `characterisation_run_id` (required) and
   `grouping_run_id` (optional) + `run_harness` gains optional
   **`synthesis_backend`** and **`grounding_judge_backend`** (stub
   defaults). The existing `embedding_backend` param serves the retrieval
   query — no new kwarg for it. No renames ride this slice.
3. **Runtime egress — four new generation surfaces + one embedding use**
   (the repo's fifth–eighth product prompts; embeddings egress was opened
   in 009 — this adds section-focus/intent query text to that existing
   surface class):
   - **`synthesise_landscape_v1`**: intent + the characterisation record +
     coverage-record summaries as id-keyed data.
   - **`synthesise_sections_v1`**: intent + group summaries as id-keyed
     data.
   - **`synthesise_section_v1`**: intent + section spec + member findings
     (references, directions, statistics, **verbatim anchor quotes**) +
     **scoped-retrieval chunk records** (selected-set frozen text — the
     011 source-text class, relevance-ranked, budget-bounded) + computed
     spreads + coverage-record summaries.
   - **`grounding_judge_v1`**: claims + cited findings'/chunks' context +
     **the cited chunks' full frozen text**.
   - **Embedding query**: the section focus + intent embedded via the 009
     embedding surface.
   Fixture corpus openly licensed by construction; full-I/O Langfuse
   traces (user-operated dev instance) carry these payloads — flagged for
   approval.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic`
cover it; cosine is stdlib/in-memory).

**Explicitly not crossed:** exactly four prompt-bearing surfaces (no agent
loop, no tools, no free text acting on the world); no new dependency; no
auth/tenancy/CI change; no existing-table change; no new event types; no
tag writes; no index/extension for retrieval (in-memory over stored JSONB
vectors).

**Spec flow-backs: already landed with ADRs 0009 + 0010 (incl. the
amendment)** — approved in this contract's gate conversation. Remaining
deferrals ride `docs/deferred.md`.

## Public / private boundary

- On the live path, what leaves: the characterisation record's content,
  coverage-record summaries, group summaries, per-section finding records
  (source-named references, statistics, **verbatim quotes**),
  **relevance-ranked frozen chunk text from selected documents**, cited
  chunks' text, the user's **intent** (also to the embedding API), and
  model-generated labels — all fixture-corpus-derived (openly licensed by
  construction) — to the OpenAI API; full-I/O traces to the user-operated
  dev Langfuse. For arbitrary future corpora this is source-derived text
  (and user-authored intent) inheriting the project's sensitivity class —
  private-by-default otherwise.
- Committed artifacts (schema, prompt text, roll-up shapes, verification
  counts) are public-safe. **Block content, claims, section titles/focus,
  gap texts and judge rationales are model-generated text over
  source-derived input** — public-safe for the fixture corpus,
  private-by-default otherwise; **untrusted model output as data**:
  bounded and validated at write, rendered escaped, never executed.
  Carried forward: block content, section specs and judge rationales enter
  any future prompt as data records, never instructions.

## Model route

All four generation surfaces behind the two backend seams —
`gpt-5-mini`-class floor (the 009 nano lesson binding) → Bedrock at the
seam swap, unchanged. Retrieval query embeddings ride the existing 009
embedding surface (`text-embedding-3-small`).

- **`synthesise_landscape_v1`** — landscape prose; typed claims (pattern |
  theme | gap | reasoning); negative rules: descriptive only, numbers only
  as given, absence only as graded gap claims, reasoning visibly framing.
- **`synthesise_sections_v1`** — the section proposal; bounded list out;
  sections name aspects of the question and the evidence, never verdicts;
  no generic/catch-all sections; assignments only from supplied ids.
- **`synthesise_section_v1`** — section prose; typed claims (finding |
  chunk | pattern | gap | reasoning); negative rules: descriptive only —
  no recommendations, no evaluative/consensus verdicts; absence only as
  graded gap claims with their base; spreads as given; mixed/unclear
  reported, never aggregated away; quotes verbatim from supplied text
  only; claim within what the cited evidence supports.
- **`grounding_judge_v1`** — the classifier; closed verdict enum +
  `weakly_grounded` + required rationale for cited claims; strict-routing
  check for reasoning claims; permissive on legitimate inference, strict
  on attribution fidelity; topical relevance ≠ support.

All four are **prompt-bearing, lead-authored, versioned**, recorded in
provenance, event payloads and (judge) annotation payloads. The judge
rubric is lead-only per AGENTS.md.

## Disciplines binding this slice

- **The traceability rule is the slice** — every claim is cited-and-
  verified, deterministically validated, or visibly labelled; no fourth
  state, no silent promotion, no post-hoc citation path. Intent shapes
  emphasis, never verification.
- **Honest absence, restored in full** — absence claims exist only as
  graded gap claims carrying their coverage base; corpus-level absence is
  fail-closed on the `search_coverage_record`; `not_selected` /
  `not_extracted` never license absence.
- **Flag, don't drop** — failed anchors, unsupported/weakly-grounded
  claims, degraded gaps and uncovered groups land visible with status;
  the one exclusion is fabricated chunk quotes — excluded **and counted**.
- **Deterministic where claimed** — presence checks, citation resolution,
  offsets, spreads, per-type validation, retrieval ranking (given stored
  vectors + memoised query embedding), cross-checks, ordering and writes;
  at most 4 + 4 × `SECTION_CAP` generation calls + `SECTION_CAP` embedding
  calls per run, each fully attributable. Determinism tests fix intent as
  input.
- **Model only what behaves** — no consensus fields, no summary columns,
  no calibration_status; the roll-up row and the 001 substrate rows are
  the only new state.
- **Never silent, never fake** — stubs say so; missing upstream state
  fails structurally; a failed call fails the component honestly;
  grouping↔findings and spread mismatches are structural failures.

## Stop conditions

- Any gated change (schema · public interface · egress) not yet approved,
  or any change beyond them (existing-table change, a fifth prompt
  surface, new dependency, retrieval index/extension, consensus/summary
  machinery, new event types).
- Any *suite or library-default* code path would perform network I/O.
- The synthesis wants evaluative output, free-phrased absence,
  corpus-wide chunk grounding, or composition conventions — halt.
- Either backend wants capabilities beyond schema-constrained calls —
  halt.
- The claim/citation model can't express something without weakening
  verification — design change; halt, never weaken the bar silently.
- `make verify` red with unclear root cause; or the turn/token budget is
  spent.

## Acceptance checks

- `make verify` — green, deterministic, zero egress (socket-deny covers
  synthesise round-trips in both content modes; suite runs on the stubs
  only, including stub-vector scoped retrieval).
- **One manual live check, both content modes** (evidence in
  verification.md): skeleton end-to-end with `OPENAI_API_KEY`
  (+ `LANGFUSE_*`) against the fixture corpus — (a) a **full run**:
  intent-led sections proposed and rendered; all claim types present with
  real citations to frozen chunks; scoped retrieval visibly ranking
  (chosen chunk ids recorded); tier distribution, gap grades/bases and any
  degradations/exclusions shown honestly; repair path exercised or its
  absence noted; `groups_unsectioned` honest; (b) a **landscape-only run**:
  artefact + landscape block written, flag set. All four prompts + the
  embedding query visible in dev Langfuse (versions, tokens/cost) with
  run-level scores (claims-valid share, citation-verified share,
  unsupported share, chunk-rejection share); per-run counts and an honest
  cost note; keys absent from captured output.
- Deterministic vs AI eval: suite checks deterministic (stubs); section
  quality, prose quality, retrieval quality and judge calibration are
  eval territory — this slice's bar is mechanism correctness, invariant
  enforcement, honest flags and provenance fidelity.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 25.
- Named test results: **mode selection** (characterisation_run_id
  required; grouping_run_id absent → landscape-only + flag; present →
  grounded synthesis; missing referenced rows → structural failure),
  **landscape validation** (wrong pattern numbers rejected; theme claims
  validated; gap grades enforced; disallowed types rejected; empty
  characterisation → honest skip, no artefact), **section proposal
  validation** (caps, bounded non-generic titles, real group_ids,
  `groups_unsectioned` counted, malformed directive fails closed, source
  recorded), **scoped retrieval** (anchor chunks always present; top-k
  ranking deterministic on stub vectors; budgets enforced; chosen ids in
  provenance; only selected-set chunks reachable — a foreign or
  unselected document's chunks never enter), **finding-claim citation
  resolution** (ids ⊆ section findings; anchors reused verbatim;
  abstract-basis re-location; failed/unlocatable anchors →
  `quote_unverified` + weakly-grounded cap, never dropped),
  **chunk-claim verification** (presence-checked against the whole
  document basis; claimed location untrusted — verified spans become the
  citation rows; fabricated quote → reject, one repair, then excluded and
  counted), **gap-claim discipline** (corpus-level phrasing without a
  non-`inadequate` coverage record → fail-closed degradation, counted;
  acknowledged-gap sparsity validated numerically; inferred gaps labelled;
  base always present; `not_selected`/`not_extracted` never appear as
  absence grounds), **reasoning-claim discipline** (visibly labelled;
  strict-routing: an empirical/causal sentinel claim → flagged
  `unsupported_mis_cited`; per-block count bounded), **claim/unit
  integrity** (every cited claim ≥ 1 citation target; pattern counts equal
  computed spreads; annotations exist iff their claim does, on that
  claim's unit; offsets exact; composite-FK integrity; content_hash
  correct), **judge semantics** (single-lane enum; rationale required;
  verdict + judge provenance + envelope version persisted; judge input
  includes cited chunk text; cited and reasoning claims judged;
  gap/pattern/theme not judged), **repair semantics** (bounded exactly as
  decision 9; budgets test-asserted; exhaustion → flags, claims retained
  except fabricated chunk quotes), **flag-not-drop** (unsupported /
  weakly-grounded / degraded-gap claims persist visibly; mixed/unclear
  visible end-to-end), **descriptive posture** (negative rules asserted on
  all four built prompts; injection-shaped labels, quotes, chunk text or
  coverage summaries land as inert data), **artefact/composition v1** (one
  artefact per run, intent-derived bounded title; section-ordered binding;
  re-run → new artefact; same-run re-execution loud; backend failure →
  `component.failed`, no roll-up row, prior blocks named), **determinism**
  (two stub runs with fixed intent → identical payload columns, block
  content and hashes; retrieval ranking deterministic), **provenance
  required keys** (four prompt versions, envelope policy, section set +
  source, retrieval parameters + chunk-id hash, per-mode call counts, the
  inherited chain base), delete-order integrity.
- Live-run evidence per the manual check above (both modes).
- Public-safety confirmation (egress was fixture-corpus text + intent
  only; traces on the user-operated instance; keys clean).
- Deferred seams recorded/updated in `docs/deferred.md`: **corpus-wide
  chunk-grounded narrative** (retrieve-gated; risk note carried) · **full
  `retrieve` tool** (the scoped helper = its first increment; upgrade
  path recorded; the 009 vectors-ahead-of-reader entry discharged) ·
  **plan-compile section machinery** (directive = compile target) ·
  **composition conventions** · policy-conditioned citable-bar flagging ·
  consensus roll-up (never-contribute constraints restated incl. gaps +
  reasoning) · block summaries + faithfulness judging · agent-loop
  synthesise + agent-invoked `query-findings` (updated, not closed) ·
  judge-envelope widening + re-gather repair (with `retrieve`) ·
  synthesis/judge/retrieval quality evals (envelope, SECTION_CAP and
  top-k calibration).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate, four new generation surfaces plus an
embedding-query use ride the slice, and this is the **trust invariant's
landing slice** — now carrying the full honest-assertion vocabulary
(citations, patterns, gaps, labelled reasoning). Contract- and plan-stage
adversarial reviews standard; review stack sized per the review-economy
notes. ADRs 0009 + 0010 (incl. amendment) cover the architecture.

Review focus:
- **Provenance/honesty (the headline lane)**: co-emitted citations only;
  presence checks for both cited claim kinds; verified spans (never
  model-claimed locations) become citation rows; single-lane verdicts
  persisted; pattern/gap numbers deterministically validated; the gap
  fail-closed corpus-promotion rule; reasoning claims visibly labelled and
  strict-routed; unsupported/weak/degraded claims flagged never dropped;
  fabricated chunk quotes excluded and counted; mixed/unclear survive;
  uncovered groups counted; intent shapes emphasis never verification;
  provenance carries the inherited chain base per mode.
- **Security / prompt surfaces**: four prompts + an embedding query
  consuming untrusted source-derived text and model-generated labels —
  id-keyed data records, schema-constrained outputs, closed enums, no
  tools; outputs bounded and validated at write; retrieval poisoning
  bounded to in-corpus frozen text; key hygiene; egress bounded (pre-run
  budgets, socket-deny on suite paths).
- **Correctness**: mode/reference resolution; section validation; scoped
  retrieval determinism + budgets; citation resolution across
  verified/abstract/failed anchors and chunk quotes; per-type validation;
  offsets; composite-FK integrity; repair semantics; roll-up-last
  ordering; FK and delete order.
- **Scope**: no corpus-wide retrieval or index, no composition
  conventions, no consensus/summary machinery, no fifth prompt, suite
  egress-free.
