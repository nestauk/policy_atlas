---
type: Capability spec
title: Evidence Base — component skeleton
description: The nine EB components — declared I/O, tool wiring, realisation and gating.
tags: [capability, evidence-base, components]
timestamp: 2026-07-06
---

# Evidence Base — component skeleton

The nine components, their declared I/O, tool wiring, realisation and gating. Distilled from
[backend-evidence-base-build-spec.md](../../sources/backend/backend-evidence-base-build-spec.md) §2; the
shared tools and findings schema are owned by
[../../system/execution-orchestration.md](../../system/execution-orchestration.md) and
[../../system/data-model.md](../../system/data-model.md).

```
acquire → screen → classify → appraise → ingest(fetch) → synthesise   (the mandatory spine)
        + characterise (landscape content)                            (discretionary)
        + [select → extract → group]   (the deep chain, plan-selected) (discretionary)
```

**The mandatory EB spine** ([ADR 0013](../../../adr/0013-mandatory-eb-spine.md), task 016
flow-back): every EB run executes acquire(`search`) → screen → classify → appraise →
ingest(fetch) → synthesise; every other component — characterise · select · extract · group ·
stage-2 screen — is **orchestrator-discretionary**, chosen per the depth gradation. Mandatory
ingest is a mandatory **attempt**, not a substrate guarantee: live fetching can fail per
document (in the worst corpus, for every document); what the spine guarantees is that the
attempt was made and every outcome is reason-coded, with unfetchable documents entering the
substrate on labelled abstract text (§4). Beyond the spine, the components are a **registry the
plan selects from** (task 013 flow-back): which fire is the orchestrator's plan-time selection
from intent; **data dependencies stay structural** (extract needs a selection; group and
finding claims need an extraction; the artefact needs **at least one groundable substrate** —
every upstream reference is optional, ADR 0010), expressed as explicit run references compiling
fail-closed. Breadth and depth are independent — a targeted question compiles to a
*narrow-and-deep* run.

## Tool wiring (consolidated)

**Universal core, ambient to every component:** `search`, `retrieve`, `lookup`, `appraise`,
`produce-grounded-block`, `escalate`, `clarify`.

| # | Component | Centres on | Declares (beyond core) | Realisation |
|---|---|---|---|---|
| 1 | acquire | `search` (only egress verb); ingestion follows | — | procedure |
| 2 | screen | `screen`; re-invokes `search` on the thin-base hatch | `screen` | per-doc fan-out |
| 3 | classify | `classify` (single-label doc type + open tags) | `classify` | per-doc fan-out |
| 4 | appraise | `appraise` (steerable rubric → quality tier) | — (core) | per-doc fan-out |
| 5 | characterise | `cluster` (topic) + deterministic metadata patterns | `cluster` | procedure + agent |
| 6 | select | `select` (strategy-parameterised) | `select` | procedure (+ optional bounded generative rerank) |
| 7 | extract | `extract` → `intervention_outcome_finding` / `implementation_context_finding` | `extract` | per-source fan-out |
| 8 | group | `cluster` (facet, over findings) + `query-findings` | `cluster`, `query-findings` | agent |
| 9 | synthesise | `produce-grounded-block` (intent-led sections over available substrate) | `query-findings`, `search_chunks` (the `retrieve` increment) | agent-loop |

## 1 — acquire (front edge)

Gather a **broad corpus** via `search` over configured backends (OpenAlex, Overton) + any
uploaded corpus — at this point **metadata only** (title, abstract, metadata), **no full text**.
Bounded by configured backends / trust classes (the acquisition constraint). Breadth is
**intent-derived**, not fixed. **Full-text fetch + Tier-0 ingestion does not happen here** — it
is gated by `screen`. Ingestion is *not* a tool; this component's verb is `search`.
In v3.0 acquire snapshots the metadata envelope itself as text-in-hand
(`text_basis="abstract_only"`); full-text fetch + Tier-0 ingestion remain post-screen.

**As-built, task 015 ([ADR 0012](../../../adr/0012-depth-graded-agentic-search.md)):**
search is **depth-graded** — acquire reads `context["search"]["depth"]`
(`rapid` default | `deep`, fail-closed; every depth constant lives in an extensible
per-depth table). **Rapid** = LLM multi-query fan-out per backend idiom (OpenAlex
keyword-lexical queries + SR/RCT variants; Overton verbatim intent + ≤2 NL paraphrases,
semantic `squery`) with no single query load-bearing (validated generation; all-zero →
loud verbatim fallback; per-call result quotas distribute the cap). **Deep** = bounded
acquire↔screen rounds (cap 3) where the loop's relevance judge IS the production
screen — acquire itself writes **no** screening rows and holds no shadow relevance
judgment; steering reads persisted consensus rows via the effective-screen helper.
Round arms (reformulate over graded exemplars anchored to the fixed intent · citation
snowball · suggested-paper grounding · an un-steered diversity reserve) run on fixed
call caps. Stops are honest (`target_reached` / `short_circuit` / `budget_exhausted`,
thin overlay `re_searched_still_thin`); every egress call emits `search.executed`; each
acquire round writes a fail-closed coverage record carrying depth + executed
`scope_filters` (the empirically-pinned directive grammar). `search_backend_scope`
(Plan+Config) selects backends. Transport is first-party httpx, hardened
(timeouts · Overton limiter · retry cap 1 · redacted errors · sanitizers · no citation
floor).

## 2 — screen

A distinct **recall-oriented** relevance filter, **per-document fan-out**. The dangerous failure
for a broad scan is the **false negative**, so the screen is deliberately inclusive.
- **v3.0: a two-stage realisation of the ONE screen component**, stage-parameterised via the
  plan's directive (the thoroughness gradation selects; a deep run = two runs of the component,
  a rapid run stage 1 only — the canonical systematic-review two-stage, task 014):
  - **Stage 1 (always)** screens on **metadata** — title + abstract, **degrading to title-only**
    where no abstract — **fail-open** ("no abstract" must never behave like "not relevant";
    title-only exclusion requires unanimity across consensus reps).
  - **Stage 2 (at depth, post-ingestion)** re-screens on **full text** where text is available
    (ingested or envelope-carried), **demote-only** (it can confirm or demote, never rescue a
    stage-1 exclude — recall is won at stage 1 or not at all); docs without full text keep
    their stage-1 result, stage-stamped. Both stages' results persist ("screened-in" always
    means *effective* screened-in: highest-stage non-failed).
- Emits `is_relevant` + relevance **`confidence`** + a **`screen_basis`** flag (`title_abstract` |
  `title_only` | `full_text`) + a **`screen_stage`** + a retryable **`screen_failed`** state
  (distinct from not-relevant; failures never block retry).
- **Confidence is load-bearing (light):** feeds the **thin-base re-search trigger** (thin = too
  few *sufficiently-confident* relevant docs) and flags/orders borderline inclusions — but is
  **never a hard exclusion cutoff** (preserves recall). Adds the escape hatch v2 lacked
  (re-search when the screened base is too thin) — may re-invoke `search`. **As-built
  (task 015):** the trigger dissolved into the depth-graded loop's stopping rule — a
  rapid run below the confident-relevant threshold escalates (`should_escalate`) to one
  bounded deep continuation, and any non-target stop below target records
  `re_searched_still_thin` on the coverage record. Screen is also the **deep loop's
  judge**: every in-loop relevance judgment is the same durable 3-rep consensus
  admission decision (one calibration, one eval surface — ADR 0012 decision 3);
  stage-1 prompt inputs grew `title_source` provenance and (classify likewise) the
  tag-layer label priors with visible `asserted_by` (task 015 revs 3.7–3.8).
- ⏸ The richer **tiered content peek** (exec-summary / headings / passage scan for poor-metadata
  grey lit) is **deferred** (largely superseded by the stage-2 windowed full-text pass).

## 3 — classify

Cheap classification on the screened-in set, **per-document fan-out**; distinct from appraisal
(*what kind* vs *how good*). Produces two things:
- a single-valued **`primary_evidence_type`** — a **closed column** (routing/appraisal key; a
  study has one primary design). **Carries v2's categories for parity** (rubric maps off them, no
  migration churn). The **`Non-evidence`** value is a landscape label that **excludes from
  `select`/`extract`**; **`Unknown`** is **kept-and-eligible** (label stays metadata-based; ⏸
  resolving Unknowns on full text mirrors the appraisal seam). ⏸ **grey-lit category granularity**
  (splitting v2's coarse Policy-Guidance / Expert-Opinion) is a deferred refinement (with
  policy-team input).
- proposed **methodological / structural tags** — **open, inferred tags, not a closed column**
  (LLM-inferred; grey-lit variety unbounded; job is scoping/description) → the open tag layer,
  seeded + namespace-consolidated. *Not* flat multi-label on the primary type.

## 4 — appraise

Cheap **document-level** quality tier, **per-document fan-out**, applying a **steerable,
default-first rubric** (document type + typed dimensions → quality tier — **not** a fixed global
hierarchy; the **rubric version travels with each appraisal**). **v3.0 = a single light pass**
from metadata + title/abstract, document-type-based, over all screened-in — coverage
clarification (task 006): the pass scores classified **evidence** types; Non-evidence and
Unknown are skipped-and-counted (Unknown re-enters via the deferred full-text resolution
seam). Deferred seams (see
[../../system/provenance-grounding.md](../../system/provenance-grounding.md)): ⏸ the full
full-text pass (methods quality / risk-of-bias, gated to the selected subset; two-stage with the
light tier) + modifier-tag-driven dimensions; ⏸ relative-to-feasible tier; the cross-document
roll-up stays **out of EB's appraise** (EB appraises per document).

**Full-text ingestion — gated by screen, built for all screened-in**. After screen/classify/
appraise (which run on the cheap envelope), full text is fetched and fully Tier-0-ingested
(snapshot → parse → segment → embed) for the **entire screened-in set** — the cheap, shared
substrate downstream capabilities/retrieval/Q&A reuse. Only Tier-1 extraction is further gated by
`select`. **When full text can't be fetched (paywall, dead link) the source is *not* dropped** —
it is snapshotted/ingested on the text in hand (abstract + metadata), carrying a per-source
**`text_basis`** (`full_text` | `abstract_only`) so grounding and coverage see which a finding
rests on. *As enacted (task 016, contract rev 2.5 — spec text 008's fixture era never
reached):* the failed-fetch document's substrate IS its envelope snapshot's abstract chunks,
already chunked and embedded at acquire; they join grounded retrieval as labelled substrate,
every chunk record and citation carrying `text_basis` (`abstract_only`), so an all-fetch-failed
corpus still synthesises — visibly abstract-labelled — and the access-failure vocabulary stays
honest (401 → paywall; 403 → paywall only with corroboration, else `blocked_by_host`; refused
URLs `blocked`; bot-blocks are never counted as paywalls). Full-text fetch is egress but
mechanical execution of the governed `search` (telemetry
plane + run-record summary, *not* a per-document audit event). Vectorisation is **eager and
uniform** (lazy/on-demand rejected — biases retrieval toward what was vectorised early). In v3.0
Tier-0 ingestion lands as fetch → parse → segment → embed: the embed seam opened in task 009
**ahead of its first reader** (approved exception to "vectorise at the first vector reader" —
chunk vectors are certain retrieval/synthesis substrate, and landing them with the egress
gate beat relitigating egress in a third slice). Vectorisation is eager and uniform over all
ingested snapshot classes, at **embedding-unit grain** (a named, versioned unit policy over
the immutable canonical chunks — units attach alongside; chunks are never re-segmented), each
unit stamped with the embedding profile (the substrate-key leg for embedding-model version). ⏸
budget cap + lazy vectorisation for very large relevant sets is a possible later refinement.

## 5 — characterise (landscape content)

Produces the evidence-landscape **content, not presentation**: a run-scoped characterisation
record + topic/theme tags (task 009 clarification, decision 7). Characterise does **not** mint
an artefact or blocks — EB produces **one** artefact, composed once at the run terminus **by
synthesise** (task 013 flow-back, superseding the earlier orchestrator-composes reading; the
orchestrator shapes sections at plan time — see [capability.md](capability.md)). Two parts:
- **Coverage / patterns over metadata** — deterministic distributions and gaps over Tier-0
  columns (study-type, geography, recency, population, category). **Source/evidence policy is
  flag-not-block here** — EB reads and counts *all* relevant in-corpus evidence, so coverage/gaps
  reflect what **exists**, with below-policy evidence present-but-flagged (no false gaps). When
  the user has supplied a policy, characterise computes **two coverage views** — the **overall**
  landscape and the **policy-filtered ("well-evidenced")** landscape — side by side, the **delta**
  showing where the base thins under the citable bar (descriptive **dual-view coverage**, cheap
  and deterministic — *not* the deferred weighted-strength roll-up). These shallow gaps rest on
  the **screened base** (never read `not_selected` / `not_extracted` as absence).
- **Thematic shape — graded by depth.** At the shallow landscape: a **bounded two-stage LLM
  grouping** (task 009 clarification, decision 4) — one judgment-model call discovers the
  scope's themes from all titles + abstracts, then batched cheap-model calls assign every
  screened-in document against the fixed theme list. Exhaustiveness is **code-enforced**
  (schema-constrained outputs, per-batch validation with targeted repair); a document may
  land explicitly in a counted **`unclustered`** bucket — never silently dropped, no
  placeholder themes representable. Call budget is known before the run
  (`1 + ceil(n/batch)`, retry-capped maximum enforced). Honest about being the softest
  grade — an interpretive shape, recomputable, never a deterministic fact. Per-theme labels
  persist as **topic/theme tags**; the run's grouping memberships stay **run-local** (in the
  run's characterisation record only). ⏸ Embedding-based clustering over the landed chunk
  vectors (and discovery-sampling) is the recorded very-large-corpus seam.

Facet-level thematic grouping is a **deeper product** (component 8 `group`), not part of the
shallow terminus.

## 6 — select (the deep chain opens)

Chooses the subset for Tier-1 extraction — a clean departure from v2 (which had **no** select
step and extracted the whole screened set). **Coverage-aware stratified selection over the
characterisation clusters**, breadth-adaptive (the landscape has already *measured* breadth, so
no separate broad/narrow mode — stratify across whatever clusters exist; depth sets how deep per
cluster). Guards against horizon scans collapsing onto a narrow top-k. Realised as the shared
**`select`** tool (strategy-parameterised: *(candidate set, cheap signals, strategy, budget) →
chosen subset + rationale*); EB's coverage-aware-stratified-over-clusters is one strategy.
Strata are the characterisation's clusters plus the counted **`unclustered`** set as a
first-class stratum (already implied by §5's counted-unclustered and "whatever clusters exist").
**Realisation: procedure with an optional bounded generative rerank** — stratification, the
breadth floor, budget arithmetic and the hard rules (must-includes) stay code-side; the rerank
replaces only the *within-stratum ordering* with schema-constrained per-document purpose-fit
scores + reasons against the intent. Scores **order, never exclude**; a document the ranker
misses falls back to the deterministic composite (flagged, never dropped), so the rerank can
degrade to the fully deterministic strategy, never to a partial or silent state.

**Selection signals (cheap, pre-extract only)**: cluster coverage (breadth skeleton) +
relevance to intent (embeddings/screening) + recency + origin/upload-priority + light appraisal
tier + **must-includes** (user-nominated / official docs as a **hard-include bypassing the
budget** — the one hard rule). The **source/evidence policy tilts but never gates** (soft prior;
a hard exclude would re-manufacture false gaps). Diversity is reliable only on cheaply-known
dimensions (topic clusters + clean metadata; publication country is cheap, but study geography /
population / intervention-type live in the text → cluster-approximated, properly post-extraction).
**Rationale is bidirectional** — records what was selected (why) and what was *not* (aggregate
exclusion reasons + notable flagged exclusions); this is exactly what the **deepening-selection
steer-point** reads (see [capability.md](capability.md)).

## 7 — extract (Tier-1)

Per selected document, extracts finding records under a **plan-visible `profiles`
directive** — **two profiles running through one component, over the same selection; no
second component, no second selection** (task 021, ADR 0017): **`intervention_outcome_finding`**
(`eb_iof_base_v1`) and **`implementation_context_finding`** (`eb_icf_base_v1`) — see
[../../system/data-model.md](../../system/data-model.md) for grain + base fields of each.
**EB's extraction profile(s)** (the EB-specific part) = its commitment to extract those **base
fields** over the **selected** subset, per selected profile. Question-relative judgements
(normalised magnitude, causal weighting, is-beneficial) are **not** extracted by EB — they are
analysis enrichment for Impact/VfM.

**Composition, as built:** the `profiles` directive compiles **fail-closed** — an unknown
profile name is a compile error — and **defaults to both profiles at deep depth**
(`ANALYSIS_DEPTH_TABLE`; extract stays deep-only, and `findings_chain` — extract + group — is
only ever meaningful once `select` has run). IOF-only remains expressible; **ICF-only is not**
this slice (`docs/deferred.md` § Extract names the seam). Each profile is its own fingerprint
domain (own schema version, own prompt, own field rules, own vetter) hanging off
`source_extraction_record` via the same composite FK — a profile's arrival or version bump
never invalidates the other profile's memoised findings. `extraction_result` stays one row per
`(evidence_scope_id, run_id)`; its provenance/counts/per-doc statuses are keyed per profile, so
"profile not selected" (absent) and "profile fired, zero findings" (present, count 0) stay
distinguishable. The two-profile extract semantics are **plan-visible**: the planner prompt
describes them, so composition is never silently compiled.

⏸ **v3.0 deep-synthesis scope remains schema-bound:** deep grounded synthesis reads whichever
of the two schemas' records a run produced; a facet or claim shape outside both schemas is
still shallow-landscape-only (topic clusters/tags/metadata). A future third schema is content
work (a new profile bundle plugged into the profile-parameterised pipeline), not plumbing —
see `docs/deferred.md` § Extract / findings layer for the schema-candidate ladder.

## 8 — group (facet-level theming)

A distinct component between extract and synthesise (not folded into the write-up). Groups the
extracted findings **per facet, across a directive facet LIST in one run** (task 022, owner's
in-component fan-out shape): one `group` execution runs separate clustering passes per
requested facet — never one call spanning facets — and writes **one** `grouping_result` row
whose payloads are facet-keyed at **group grain** (each group carries its `facet`; ids are
facet-qualified `facet:gNN`, collision-safe end-to-end). The v3.0 facet vocabulary:
**intervention / outcome / population** (value facets over the source-named references) plus
the **claim-theme facets** **barrier_theme / enabler_theme / mechanism_theme** (ICF claim
prose scoped by `context_type` — each theme facet's eligible base is exactly the ICF rows of
its type; IOF and non-matching ICF rows are outside the base, never residual members; the
remaining four context_types are config, not machinery). The **second clustering** in the
chain (topic-level at characterise; facet-level here), now on the **shared two-stage
clustering engine** (ADR 0018): open discovery (labels + descriptions only — never an
exhaustive id list, the ~184-value capacity cliff the redesign retired) + batch-validated
exhaustive assignment against the deterministically known unit list, parameterised by unit
projection; characterise runs on the same engine, behaviour-preserving. Per-facet honesty:
per-facet residuals, CAP accounting and failure outcomes (`status`/`failure_class` per facet
— one facet fails closed while siblings survive; component-abort only for corrupt shared
input or cross-facet invariant violations). Discovery granularity is steered by a
corpus-relative ceiling (`clamp(ceil(N/5), 3, 40)`, computed per run and injected into the
prompt) with **no lower target**; per-unit context payloads (bounded anchor quotes for value
facets; `context_label` + intervention for claim themes) are on by default, gated out of
discovery above 120 units.

**Kind-spanning membership (task 021, ADR 0017, gate decision 8 — the minimal bridge):** the
loader reads **both finding tables** via the shared reference columns, so a facet group's
members can span IOF and ICF records — the cross-schema linkage the shared vocabulary was
designed for, made real. (021 widened membership reach only; task 022 then moved facet to
group grain and added the multi-facet fan-out above.) The value-facet loader reads the
shared reference columns through the **`finding_reference_union` view**; claim-theme loading
reads the ICF table directly (its unit needs `context_type` + `claim`, deliberately not
shared vocabulary).
`FindingFacetView` tolerates kind-specific fields (`effect_direction` nullable, a `kind` tag
carried); `direction_spread` is computed over **IOF members only** (ICF members have no
direction — never zero-filled into the spread); the group payload carries per-kind member
counts. Closes the hole where, on a deep grouped run, ICF findings would never reach the
synthesise envelope's `member_findings`.

**ICF claim-theme facets are BUILT** (task 022 — the high-value trio above; grouping BY the
`context_type` predicate, never `context_type` itself as a facet: the bare deterministic
partition by the seven-value enum already exists as `icf_context_type_count`). The membership
principle (members join by shared reference, regardless of kind) survived the rework as
designed.

## 9 — synthesise (run terminus)

**EB's terminal component at every depth** (task 013 flow-back): it **composes the one artefact**
— mints it, renders content into blocks, binds them — with the orchestrator shaping the sections
at plan time (capability-composes; see [capability.md](capability.md)). What it renders depends
on what the run produced:

- **One substrate-conditional flow — intent-led sections whose claim types are gated by
  what the run produced** ([ADR 0010](../../../adr/0010-intent-led-synthesis-sections.md),
  ): synthesise takes explicit fail-closed references (**all optional** —
  characterisation, and the deepest available of selection / extraction / grouping,
  upstream references resolved transitively from the referenced rows and cross-checked;
  the requirement is **at least one groundable substrate**, else structural failure —
  as-built (task 016) the groundable substrate is the screened-in corpus's chunks at
  their honest grain: **full-text chunks where ingested, else the document's labelled
  abstract-basis envelope chunks** (§4's flag-not-drop clause enacted; every chunk
  record and citation carries `text_basis`), so `no_groundable_substrate` fires only
  on the genuinely empty case — no upstream references AND a screened-in corpus of
  zero — the true miscomposition backstop, unreachable in a composed run under the
  mandatory spine (ADR 0013; the envelope-only refusal the 015 chain smoke hit is
  closed by composition; see the synthesise-is-run-terminus knowledge concept)) and
  never hard-wires a component combination — the orchestrator selects any coherent
  registry subset and synthesise adapts. **Retrieval scope = the screened-in corpus
  always** (screen is the relevance discipline that bounds reading); **a referenced
  selection is a soft ranking prior, never a hard boundary** — the data-model's scoping
  principle ("look here first, widen when thin; agents are never penned in"); select
  gates *extraction cost*, not reading; every chunk citation records its origin
  (selected | unselected_screened) so widening is visible. Scope guarded by a fail-closed
  in-memory retrieval ceiling (beyond it, the index-backed `retrieve` slice is required —
  loudly, never a degraded pass). A rapid run (acquire → screen → classify → appraise →
  ingest → synthesise — appraise precedes chunk-cited claims: produce-grounded-block cites
  only appraised evidence, and the v3.0 appraise pass is deterministic)
  is fully served; a run without characterise yields an artefact with no landscape — a
  grounded answer, not an evidence report; the plan's legitimate choice. The section set is shaped from the
  user's **intent** (a bounded schema-constrained section proposal over intent + the
  available substrate summaries, overridable by a fail-closed scope directive; plan-compile
  section machinery is the recorded seam). Per section, **the section loop** — a capped
  agent-loop over scoped read-only tools, the realisation
  [execution-orchestration](../../system/execution-orchestration.md) declares, running
  *inside* the component per the facade principle (the capability sub-agent invokes
  synthesise as one tool; no second agent) — gathers evidence via **`search_chunks`**
  (a staged pipeline: content-only hybrid relevance [embedding + lexical, rank-fused] →
  arithmetic soft priors [the selection prior where referenced + fail-closed directive
  boosts over columns/tags/appraisal tier — re-weight, never exclude] → a cross-encoder
  reranker slot [pass-through until Bedrock Rerank lands] → caps; over the **screened-in
  corpus's** frozen units, each returned chunk carrying its origin — the 009 vectors'
  first reader; the `retrieve` seam's first increment),
  **`query-findings`** (present only when an extraction is referenced) and **`lookup`**
  (the universal-core read tool: appraisals, classifications, selection rationale,
  coverage records, characterisation/grouping rows, **and the tag layer** — per its own
  definition, aggregate queries over columns/tags included; closed query vocabulary,
  project-guarded), under a hard per-section turn cap, then emits typed claims.
  **Availability by substrate**: **pattern claims** (coverage counts with a
  characterisation; direction spreads with extraction/grouping — **IOF-only**,
  deterministically validated; v2's `effect_consensus` counts as this steer — plus, with an
  ICF extraction referenced, the **`icf_context_type_count`** pattern (counts by
  `context_type` / intervention over the referenced extraction's ICF records, with a
  group-scoped variant — task 021, ADR 0017: the deterministic validator that makes
  implementation-shaped pattern claims possible, content-scan pattern claims being
  prohibited in v1 for lack of one)) · **theme claims** (characterise themes with a
  characterisation; facet groups with grouping — validated against the referenced
  clustering row, **available over kind-spanning groups at their existing grade** now that
  `group`'s membership reach spans both finding schemas (task 021, item 12); softest
  interpretive grade, base-labelled) · **gap claims** (always; graded per
  [provenance.md](provenance.md) with deterministic per-grade validation and the required
  coverage base — sparsity-grade gaps need the characterisation coverage; base-labelled to
  the narrowest base the substrate supports, promoted to corpus absence only on a
  non-`inadequate` `search_coverage_record`, else fail-closed degraded) · **reasoning
  claims** (always; visibly-labelled Tier 4 authoring; judge strict-routing keeps empirical
  content out; never counts toward strength roll-ups) · **chunk claims** (with screened-in
  ingested documents — screen's relevance discipline bounds them, the selection prior
  steers them, each citation carries its origin; not extraction — so a question outside
  both finding schemas is served without extract) · **finding claims** (with an
  **extraction** — cite IOF or ICF finding ids resolved to extract-verified anchors; the
  model never authors these quotes). **IOF and ICF findings never blend**: the writer's
  `query_findings` serves both schemas behind one unified, kind-typed tool call
  (`iof_findings` / `icf_findings` as separate typed sections, never interleaved), a `kinds`
  filter defaulting to all kinds present, kind-specific filters (`effect_direction` IOF-only,
  `context_type` ICF-only) requiring `kinds` to name exactly their own kind — rejected
  loudly otherwise, **including on the omitted-`kinds` default** (021 review stack) — and honest
  per-kind availability ("context findings: not extracted in this run" when a run's
  extraction lacks the ICF profile — a visible coverage fact, not a silently absent tool). A characterisation-only
  run is the landscape degenerate case (pattern/theme/gap/reasoning sections).
  **Groups, where present, are input, not structure** (uncovered groups counted, never
  silently dropped). Every cited claim goes through the settled `produce-grounded-block`
  mechanism (deterministic quote-presence + LLM judge; Unsupported/mis-cited a real state)
  — *not* v2's permissive post-hoc fuzzy matching. Intent shapes emphasis, never
  verification ("topical relevance ≠ support"). The source/evidence policy's citable bar
  is applied **flag-not-block** (below-bar support flagged weakly-grounded/below-policy,
  never hidden/dropped).
- ⏸ **Corpus-scale retrieval** (ADR 0009 decision 4): in-corpus chunk grounding
  over the **screened-in corpus** is part of grounded synthesis above (a referenced selection
  is only a soft ranking prior) — what remains gated on the index-backed `retrieve` slice is
  retrieval **beyond the in-memory ceiling** (`RETRIEVAL_UNIT_CAP`, fail-closed) or over
  **unscreened** content, with ADR 0009's recorded risk note.

⏸ **Consensus seam:** the *weighted* verdict (strength-weighted "the evidence supports X at
strength Y") is deferred to the same roll-up seam; candidate mechanism = the deferred
graph-structured synthesis.
