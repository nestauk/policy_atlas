# Deferred seams

Recorded, not built *yet* — seams left open per "build light, leave seams." Each is a real
architectural decision to defer, not an omission. Sources: architecture reference §§3–11
(Appendix A; Appendix B), briefing Appendix A, EB build spec, EB handoff §7. Grouped by area.

**Two kinds of entry live here — don't conflate them** (user clarification, 2026-07-05):

1. **Sequenced v3.0 capabilities** — required for v3.0 to function as intended, waiting only
   on their approval gates (runtime egress · LLM/inference). The specs are explicit that
   **v3.0 has live egress** (briefing §Security: inference calls via the configured route,
   first pass OpenAI → target Bedrock; search queries to configured evidence backends —
   "accepted as a documented v3.0 risk because external evidence gathering is core to the
   product", arch-ref §3.3). "Zero runtime egress" in task docs is a *build-stage discipline*
   (each slice introducing product egress needs explicit approval — harness.md), never a v3.0
   scope statement. In this class: **live `SearchBackend`s** · **live `DocumentFetcher`** ·
   the **LLM screen / classify tools** · the **LLM grounding tier** — the product cannot
   search, fetch, ingest or reason without them. **Vectorisation** left this class in
   task 009: live OpenAI embeddings shipped at ingest, deliberately *ahead of* their first
   reader (approved exception — see the discharged entry under Full-text ingestion).
2. **Deferred beyond v3.0** — everything else below: doors deliberately left open (other
   capabilities, branch parallelism, per-item egress controls, private deployments, …).

## Capabilities

- **All capabilities except Evidence Base** — Options Assessment, Impact, Transferability, Value
  for Money, Theory of Change, Risk, Scrutinise/Red-team (Appendix A). v3.0 builds EB only.
- **Options Assessment** consumes EB output + the findings layer to resolve descriptive
  intervention clusters into named, comparable options — the decision-relative step EB explicitly
  leaves out.
- **Question-shape → future-capability mapping (user posture, 2026-07-10, recorded at the
  018 gate).** Two real-user question shapes from the V2 taxonomy have their ideal homes in
  capabilities that don't exist yet: **opinions / stakeholder mapping** (a proposed
  public-opinion / stakeholder-mapping capability) and **statistics / fact-finding**
  (potentially a baseline-analysis capability). Interim posture: EB — the most
  general-purpose capability — must still produce **something somewhat useful** for these
  shapes (honest intent-fit composition, evidence-descriptive output), but v3.0 prompt/eval
  work deliberately does NOT overbias toward them; optimisation for these shapes arrives
  with their capabilities.

## Product / output

- **Export & sharing** — share CTAs, read-only/public links, version-pinned external deep links
  back into the body (handoff §7.3). The primary surface is the tool itself.
- **Cross-boundary traceability** — statement-to-statement cross-artefact tracing; chain-strength
  composition; chain display; version-pinned cross-artefact staleness (behind the
  addressable-span seam).
- **Body-level coherence** — semantic-pass contradiction detection across a selected
  decision-support-body view (never auto-edits locked artefacts).
- **Chart view-types** over structured-content blocks.
- **Summaries as a retrieval-routing signal**
  (route-never-substitute recorded).
- **Artefact-level confidence badge / `ArtefactVersion.confidence`** and aggregate cross-source
  confidence scores (handoff §7.2) — use descriptive factual-snapshot metadata + finding-strength
  language instead.

## Evidence Base internals

- **Consensus / weighted-strength roll-up** — the strength-weighted verdict ("supports X at
  strength Y") and divided-evidence *direction* verdict (synthesise component 9). Task 013
  confirms the boundary as the intended v3.0 line (contract rev 7.4, user-affirmed): the
  artefact describes the spread, never "the evidence supports X", until this seam lands.
  Never-contribute constraints restated for the eventual roll-up: Unsupported/mis-cited and
  Tier-4 **reasoning claims** never contribute positively; weakly-grounded only at a
  discount; **gap claims** never contribute (absence is coverage, not strength).
- **Relative-to-feasible appraisal tier** + the **full two-stage appraisal pass** (richer
  full-text methods/risk-of-bias on the selected subset — which exists as of task 010:
  select's run-scoped `selection_result` row defines it) + modifier-tag-driven rubric dimensions
  (appraise component 4). Typed dimensions (`dimensions` column/bag) arrive with that second
  pass — nothing populates or reads them in v3.0, so no half-built column shipped (task 006).
- **Steerable / plan-carried appraisal rubric** — the orchestrator compiles a provisional
  evidence hierarchy into the plan; the user inspects/adjusts before the run. v3.0 is
  default-rubric-only (`DEFAULT_RUBRIC` in `appraise.py`), with provenance carried by
  `rubric_version` (`v2-hierarchy-v1`) on every row and event — the seam a plan-carried rubric
  plugs into. Validation that a stored `rubric_version` names a rubric that actually exists
  belongs to this seam too (review note, task 006).
- **Re-appraisal under a new rubric version** — `uq_sar_scope_source` deliberately blocks a
  second appraisal per `(scope, source)`; the re-run seam relaxes it to
  `(scope, source, rubric_version)`. That slice must also revisit the counting semantics:
  `already_appraised` counts all appraisal rows for the scope, so if re-classification ever
  changes a source's evidence type after it was appraised, a rerun double-counts it (one
  appraisal row + one skip bucket for the same classification row) and the counting invariant
  breaks (adversarial-review finding, task 006).
- **v2's small-sample penalty** — v2 applied −1 to causal studies with sample size < 100.
  Needs sample size, which v3.0's acquire-stage metadata doesn't carry; deferred with the
  richer full-text appraisal pass, not silently dropped (contract decision 3, task 006).
- **`source_appraisal_result` → `source_classification_result` FK — deliberately absent, not
  just deferred** (mirrors the classify→screen entry below). A composite FK onto
  classification's `(evidence_scope_id, project_source_snapshot_id)` unique key would
  DB-enforce "only classified rows are appraised", but both result tables' unique constraints
  are slated to gain re-run/rubric-version columns, which the FK would hard-block. The
  invariant lives in the read path (`appraise_sources` selects *from*
  `source_classification_result`) and is covered by the round-trip tests; rationale also at
  the table definition in `schema.py` (task 006, contract-adjudicated).
- **Grey-lit category granularity** — splitting v2's coarse Policy-Guidance / Expert-Opinion
  primary types (classify component 3; needs policy-team input). `source_classification_result`
  and `primary_evidence_type` check constraint are durable; column split is additive when ready.
- **LLM-based classify tool — DISCHARGED (task 014).** `OpenAIClassificationBackend`
  (`classify_v1`, judgment-class model) classifies over the closed 9-value list with
  provider priors as allowlisted data fields; the stub survives as the zero-egress default
  behind the `ClassificationBackend` seam. Classify-consensus voting and threshold-gating
  remain open (task-014 section below).
- **Open tags → `source_tag`** (revised, task 009): the stub-empty
  `source_classification_result.open_tags` column and its array CHECK were **retired** by
  migration 9 — `source_tag` (item × tag, typed, assertion provenance in the unique key) is
  the single tag home. **The seam opened in task 014**: classify writes bounded
  `source_tag` rows directly (`asserted_by='classify'`,
  `tag_type='methodological_structural'`; `ck_stag_tag_type` widened by migration 14; all
  writes through `tags.insert_source_tags`). Nothing left to do here.
- **`Unknown / Insufficient information` resolution** — sources landing `Unknown` are kept-and-eligible;
  full-text re-classification is a deferred seam mirroring the appraisal path (shares
  decision 11's windowing + staged-result pattern when it lands, task 014). The
  Unknown-vs-Other boundary itself was settled by contract rev 1.11: `Other` requires
  positively recognising a non-evidence artefact; doubt → `Unknown`.
- **`source_classification_result` → `source_screening_result` FK — deliberately absent, not just
  deferred.** No composite FK ties a classification row to its screening result; the "only relevant
  sources are classified" discipline is enforced only in `classify_sources`, not durably at the
  schema level. This is low-risk today (no direct writer to the table exists besides
  `classify_sources`), but a hard FK here may be the *wrong* direction long-term, not merely
  incomplete hardening: `project_source_snapshot.origin` already distinguishes `"uploaded"` from
  `"acquired"` sources, and uploaded documents are plausibly relevant by user intent alone — a
  future slice may let them skip `screen` entirely and go straight to `classify`, which a FK to
  `source_screening_result` would hard-block. **Confirmed direction: `acquired` sources always
  screen** (search/acquisition provides no relevance signal, so screen's recall-oriented filter
  still applies); whether `uploaded` sources skip screen is the open question for that future
  slice — needs its own spec refinement (`docs/specs/capabilities/evidence-base/components.md`
  currently describes classify as running on "the screened-in set" unconditionally) before any
  component is built against it.
- **`characterise`+ EB components** — subsequent slices (screen, classify, appraise, acquire
  and full-text ingestion landed: tasks 004–008). The task-007 note that retained provider URL
  fields "for slice 008" is discharged: 008 consumed them with an **updated precedence** —
  OpenAlex `best_oa_location.pdf_url` → `primary_location.pdf_url` → `open_access.oa_url` →
  `primary_location.landing_page_url` (contract-stage adversarial finding 4 superseded v2's
  `primary_location`-first order); Overton `pdf_url` → `document_url`. v2's **parse caps were
  not carried** — truncation is abolished (full text or honest failure; `too_large`/`timeout`
  fail loudly, contract decision 6) — and v2's fragilities (fetch errors swallowed at debug
  level; thin landing-page text reported `ok`) are structurally closed (reason-coded
  `full_text_status`/`full_text_error`, thin-text guard). Snapshot identity resolved as a
  **new immutable `full_text` snapshot linked at the project-source link** (ADR 0003).
- **`implementation_context_finding` — DISCHARGED (task 021, ADR 0017).** The second
  reusable finding schema (mechanisms, barriers, implementation conditions) shipped:
  the `implementation_context_finding` table + `eb_icf_base_v1` extraction profile (own
  fingerprint domain — never invalidates IOF memos), `extract_icf_v1` + the ICF vetter, the
  unified kind-typed `query_findings` read surface, and the `icf_context_type_count`
  deterministic pattern validator — EB synthesis's first-reader payoff realised, per the
  posture pinned at the 020 gate. Eval slice ground truth (with/without-ICF composition
  comparison) is unstarted — this slice was deliberately eval-blind. Extract-side design
  input from task 011 (V2's CFIR implementation-profile field definitions:
  cost/staffing/complexity + the inner-setting rule) is folded into the shipped field set —
  `resource_requirements` / `workforce_requirements` / the inner-setting rule on `setting`;
  `complexity` did not carry (a judgment scale, not source-groundable — the recorded
  anti-pattern). Narrowed seams left open by this slice (contract item 10):
  - **ICF facet grouping** — **BUILT (task 022)**: the claim-theme trio
    `barrier_theme` / `enabler_theme` / `mechanism_theme` runs on the shared two-stage
    clustering engine (claim-prose unit projection, eligibility = `context_type` match).
    Remaining seam (owner call, 2026-07-14): the other four `context_type`s
    (`implementation_condition` / `delivery_process` / `adaptation` / `fidelity`) are a
    **config addition on the same engine and projection** — add when a reader wants the
    lens, no new machinery.
  - **Dimension-promotion for ICF fields** — hybrid-indexing any ICF dimension is gated on
    the same **observed-query-behaviour** promotion gate as IOF's dimensions
    (data-model.md), not shipped by schema existence alone.
  - **Downstream capability consumers** — Options Assessment / Impact / Transferability /
    Value for Money read ICF records later; EB synthesis is the reader now.
  - **Cross-kind UNION reference view** — **BUILT (task 022, owner decision 5)**:
    `finding_reference_union` (kind discriminator + the six shared reference columns,
    reference-columns-only); first reader = group's value-facet loader. Discharged.
  - **Hybrid dimension search over finding reference values** — **adjudicated DEFER at the
    022 contract gate (owner, 2026-07-14)**: stays behind the observed-query-behaviour
    promotion gate for ALL dimensions (the data-model's committed-for-v3.0
    intervention/outcome line was corrected in the same flow-back); no observed behaviour
    exists yet — the eval slice generates it; 022's scoped `search_chunks` + kind-typed
    `query_findings` cover every current reader. ICF values still co-ride free by
    construction when promoted.
  - **The schema-candidate ladder** (owner adjudication, 2026-07-12, task 021 contract
    review): the generic findings container and runtime intent-shaped custom extraction
    REMAIN declined (the task-011 rulings hold — typed records are what deterministic
    validation, ground truth, memo reuse and cross-question interpretability rest on; the
    long tail is served by verified chunk-grounded synthesis, ADR 0010); named candidates
    `reported_statistic` and `case_example` (V2 question-taxonomy categories 4 + 6), **first
    reader = the Baseline analysis / problem-identification capability** (quantitative +
    qualitative — its qualitative half may name a further kind, e.g. a `reported_problem`;
    the candidate list is open, not exhaustive); trigger = Baseline's contract committing
    the extraction profile, with per-category eval evidence (the eval intent set keeps
    categories 4/6 in and scores chunk-grounded synthesis on them) as the demonstration;
    sequencing note — **additive schemas never invalidate eval baselines** (no existing
    record shape or ground truth changes; a new kind is a new eval arm, the with/without-ICF
    axis pattern repeated), so these land with Baseline post-eval, no pre-eval promotion
    pressure. Schema design stays with the committing capability's contract (the IOF
    precedent). Research-review additions (owner, 2026-07-12): **`intervention_specification`**
    joins the candidate list (TIDieR-shaped delivery facets — dose/mode/provider/training;
    the most demanded AND most under-reported cluster, 39% adequacy; first readers
    Transferability + Options Assessment — a specification record, not a context claim,
    hence not ICF bloat).
  - **Companion-document retrieval seam** for the future Transferability capability:
    process evaluations publish separately from their trial results 76% of the time, median
    15.5 months later — the capability's acquire step should hunt companion process
    evaluations. ICF's nullable-outcome + reference-mediated design already absorbs findings
    arriving in different documents than their effects.
  - **ICF-only extraction composition** — unsupported this slice (`extract_profiles` must
    include `iof`; ICF-only is not expressible), noted at the Phase D directive validator.
  - **Two-profile extraction parallelism** (021 review stack, efficiency lane): profile
    bundles run strictly sequentially — IOF's whole window batch completes before ICF's
    starts (~2× extract wall-clock on both-profile runs). Real but non-trivial: both
    profiles share one SQLAlchemy `Connection` for memo reads/roll-up writes, so
    parallelising needs a second connection or memo/write phases restructured out of the
    parallel region. Revisit when extract wall-clock matters (eval-slice cost axis input).
  - **`claim_basis` coverage cannot distinguish "indeterminate after reading" from
    "not attempted"** (021 review stack, Codex adversarial): the prompt instructs
    `null if indeterminate` but every nullable-enum null lands as `not_extracted` — a
    coverage-vocabulary refinement (e.g. an `indeterminate` marker) for the eval slice /
    schema-candidate ladder, decided against ground truth, not speculatively.
  - **Planner two-profile narrowing decidability** (021 review stack, Codex adversarial):
    an over-narrow planner (`extract_profiles=["iof"]` on an ordinary "what works" ask)
    silently drops the ICF pass — the compile only rejects ICF-only. The eval slice's
    intent set should probe narrowing behaviour across phrasings before any tightening of
    the planner prompt.
  - **Model-output control-character scrubbing** (021 security lane, LOW): extraction and
    vetter output is NUL-scrubbed only, while directive strings get
    `has_control_character`; a document's ANSI escapes copied verbatim into a claim ride
    into DB rows and operator surfaces. Defense-in-depth: extend the backend-boundary
    scrub to C0/C1 controls (except `\n`/`\t`) — note `prompt_fields.scrub_nul` and
    `extract._scrub_nul` are parallel implementations to change together.
  The formerly-mooted **per-schema-writer-tools seam is pre-discharged by gate decision 6**:
  the unified kind-typed `query_findings` IS the schema-typed query interface — a future
  third schema adds a kind section + filters (content work), not a new tool. **Cost note
  (021 review stack, three lanes convergent):** the ICF build cloned IOF plumbing rather
  than generalising it — backends, vetter scaffolding, dedup loops, and per-kind literals
  in group/facet_values/synthesis_tools/synthesise (19 verified cleanup/altitude
  candidates). Deliberate for two kinds; the third schema's slice should budget a
  consolidation pass (profile registry / shared judge scaffolding) rather than a third
  hand-written copy.
- **Saturation-based search stopping** — `saturated` is still not a
  `search_coverage_record` stop value (kept out by migration 15's widening, task 015):
  within-run discovery-RATE collapse now stops honestly as `short_circuit`, but
  *corpus* saturation (nothing new exists to find) remains a distinct, deferred concept.
- **Budget cap + lazy vectorisation** for very large relevant sets. The **tiered content peek**
  in its original exec-summary/headings form is **superseded in practice** by task 014's
  stage-2 windowed full-text screen (decision 11); revisit only if windowing proves
  insufficient for poor-metadata grey lit.
- **LLM-based screen tool — DISCHARGED (task 014).** `OpenAIScreeningBackend` (`screen_v1`,
  mini ×3-rep consensus; `screen_fulltext_v1` stage-2 precision confirmation) replaced the
  stub, which survives as the zero-egress default behind the `ScreeningBackend` seam.
  Follow-on seams live in the task-014 section below.
- **Thin-base re-search trigger — DISCHARGED (task 015).** The trigger dissolved into the
  depth-graded loop's stopping rule (ADR 0012 decision 5): any non-target stop below the
  confident-relevant target records `re_searched_still_thin` (the 007 vocabulary, finally
  fired — observed live); rapid-thin runs escalate via `should_escalate` to one bounded
  deep continuation.
- **Re-screening of successful results** — superseding a `relevant`/`not_relevant` decision
  is still blocked by design: `uq_ssr_scope_source_stage` (task 014's partial unique) admits
  failed-row retries and one row per stage, never a second non-failed row per
  `(scope, source, stage)`. Follow-on seam when deliberate re-screening is wanted.
- **`screen_failed` recovery loop** — the failed-row rerun retry itself is **DISCHARGED
  in-slice (task 014, revs 1.1/1.6)**: failed docs are re-attempted as new rows on the next
  screen run (attempt history preserved; counts failure-aware). The remaining seam is an
  **automated recovery sweep** that notices and re-runs failures without an operator-initiated
  rerun.
- **Graph-structured synthesis** — query-time multi-hop / community / contradiction-location over
  the findings graph (run-local → project-scoped persistent → graph datastore), gated on an
  entity-resolution-quality bar; **never** an ingestion-time global / cross-project KG.

## Search / acquisition (task 007 seams)

- **Live `SearchBackend` implementations — DISCHARGED (task 015).** `search_live.py` ships
  hardened first-party httpx transport for both backends (ADR 0012 decision 6): explicit
  timeouts on every request, Overton 1.2 s limiter on every path including validated
  `next_page_url` follows, retry cap 1 then honest failure, structural error redaction to
  status+host, both sanitizers on the production path (commas fully excluded from the
  OpenAlex wire — the v2 note's commas-in-quotes scope was widened at the 015 review:
  commas are the filter-clause separator, an injection surface), per-depth per-provider
  result caps *with per-call distribution quotas*, credit-responsible `select=`, no
  citation floor, and a zero-progress page guard on pagination. The stub remains the
  zero-egress default; the 007 guard now names `search_live.py` as the sole sanctioned
  HTTP-import home.
- **Arm-B agentic search loop — DISCHARGED (task 015, ADR 0012).** The R&D direction landed
  as the deep depth: query reformulation from judged exemplars (via the production screen —
  the loop's judge IS `screen_v1`, no shadow relevance judgment), citation snowballing
  (forward + backward through the decision-16 protocol verbs + `lookup_dois`),
  LLM-suggested-paper grounding (ID/DOI-preferred, drop-and-count when ungrounded), honest
  stop vocabulary (`target_reached` / `short_circuit` / `budget_exhausted` + the
  `re_searched_still_thin` overlay). Deliberately NOT carried: Thompson-sampling adaptive
  judging (fixed allocation won — a ≤3-round loop leaves a 3-arm bandit in permanent
  cold-start; TS survives as an eval-gated seam that must beat round-robin, task-015
  section) and blend ranking (screen / retrieval-rerank seams own relevance weighting).
  v2's central lesson is structurally honoured: no single LLM query is load-bearing
  (validated multi-query fan-out, all-zero → verbatim fallback).
- **User-selectable backend scope — DISCHARGED (task 015).** `search_backend_scope`
  (`academic_only` / `grey_lit_only` / `both`) compiles on Plan AND Config (unknown values
  rejected on both), driving the 007 `search_backends` parameter; the harness resolves
  defaults from compiled config.
- **Per-backend query mode — DISCHARGED as built, exploration seams remain (task 015).**
  Shipped per-idiom: Overton semantic (`squery` + `min_similarity=0.3` on every call) with
  verbatim intent + ≤2 NL paraphrases; OpenAlex keyword-lexical multi-query fan-out with
  SR/RCT variants. The richer filters shipped as the fail-closed `scope_filters` grammar
  over wire-verified vocabularies (revs 3.3–3.4 pinning). Still open, now in the task-015
  section: whether Overton's semantic mode is hybrid under the hood (unverified), and the
  filter-vocabulary growth seams.
- **Injection screening of acquired text** — posture recorded at task 007 (contract decision 9):
  acquired titles/abstracts/snippets are third-party text entering the corpus ("ingestion is not
  a tool"); v3.0's deterministic stubs never interpret them (security-review-confirmed), but the
  LLM screen/classify seams will — enforcement lands with those seams / the live backends.
  Overton's `llm_document_description`/`llm_document_theme` are provider-LLM text, persisted
  visibly (`abstract_source="llm_description"`; theme retained under `provider_fields`) and
  never mixed into document-own-words fields — when grounding lands, claims resting on
  `llm_description` text are flagged distinctly (flag-not-drop).
- **Downstream consumers of the acquired envelope — largely DISCHARGED (tasks 014–015).**
  Screen reads `abstract_source` and (015) `title_source`; classify consumes property
  priors (`record_type`, source typing, `indexed_in`, `title_source`) plus the tag layer
  as its uniform label-prior surface (`{tag, tag_type, asserted_by}` visible — ADR 0012
  decision 8; OpenAlex keywords deliberately exited the prompt). `is_retracted`
  retained-but-unread — **DISCHARGED (task 019):** retracted docs exclude at
  stage-1 screening as the distinct `excluded_retracted` status (owner decision
  2; visible, attributed, never conflated with relevance). Still open: the
  appraisal-second-pass visible-flag reading, and non-English handling beyond
  English-first title selection.

## Live search / depth-graded loop (task 015 seams)

- **Country filter allowlists + deterministic country-group expansion —
  DISCHARGED (task 019).** Fail-closed ISO-3166 + probed Overton
  display-name allowlists (186 names, probe 2026-07-12); Tier-1 pinned
  provenance-stamped group tables (OECD members/G7/G20/EU27/EEA + M49
  continentals Europe/North America/Oceania, UK∈Europe); Tier-2
  planner-proposed explicit lists persisted as `{label, countries,
  authorship}`; Overton multi-country = deterministic post-filter + deeper
  pagination with exclusion counts on coverage (owner decision 5); planner_v3
  capability line. Note what did NOT ship: "developing"-specific support
  (`is_global_south` DROPPED, owner de-scope) — see the filter-vocabulary
  growth entry below.

Recorded per contract § Verification (rev 3.14 list) + the 015 review stack.

- **Retrieval-boost grammar v2 — SUBSUMED AND RETIRED (022 agenda A, owner, 2026-07-14).**
  The multiplier half shipped as 022's screen-confidence directive boost (clamped
  functional multiplier + product clamp + suppression, decision 7/11); the tag-scoping
  half is delivered better by 022's call-level `search_chunks` scope filters (item 13).
  ONE narrow seam survives: **directive-level tag-boost vocabulary on the
  `context["synthesis"]` grammar** — trigger = observed steer-point demand for it (no
  author exists today; the recorded steer examples compile against the existing grammar).
- **Select-as-tool / shared purpose-fit-ranking tool** — the rev-3 spec-level seam:
  select's ranking machinery exposed as a tool other components (and the deep loop) could
  call, instead of each growing its own fitness heuristics.
- **Overton arm-B cross-backend snowball** — Overton has `has_snowball=False` in v3.0; the
  documented edges when this opens: `plain_dois_cited` + `generate_id_set.php` +
  `open_cited_institution_authors`; reverse policy-inbound citation = confirm-with-support.
- **Semantic Scholar third backend** — dense `/snippet/search`, `x-api-key`, ~1 req/s.
  Registration duties recorded at the 009 tag-consolidation entry (mapper + tag extractor +
  caps flags — and the review note that the diversity arm currently selects its backend by
  name, not a caps flag; backend #3 is the trigger to add one).
- **Filter-vocabulary growth** — OpenAlex topic-hierarchy / keyword / venue / funder
  name→id resolution; Overton `source_region` `_:` code mapping table; COFOG
  classifications reference table; Overton open-vocabulary `topics`/`document_type` once
  token lists are pinnable. (Live scale note: Overton's publisher tag layer runs ~29
  tags/record — bounds sized on fixtures now genuinely bind.) **Country-group seams
  left out at task 019 (contract item 3c):** `Very high human development`
  (a candidate Tier-1 group, not built); `APAC` (not continental,
  definitionally fuzzy); V2-style exclusion groups ("All but UK", untested).
  Also parked: OpenAlex `authorships.institutions.is_global_south:true`
  exists as a one-boolean native option (probed 2026-07-12, 40.8M works) if
  "developing"-shaped groups are ever wanted.
- **Caching (cache-before-throttle) — DISCHARGED (task 019).** In-process
  TTL+LRU response cache keyed by full non-credential request params, checked
  before the rate limiter, 2xx-only, env-tunable
  (`POLICY_ATLAS_SEARCH_CACHE_TTL_S`).
- **Citation-floor knob** — no citation floor is the recall-first default (decision 12,
  user-approved); a steerable floor, if ever wanted, is a directive knob — never a silent
  transport filter (the V2 lesson).
- **Tool-wide depth/time-budget gradation** (rev 3.12, user direction) — the depth axis is
  a spectrum (really-rapid → intermediate → deep → long-running report-grade); the
  orchestrator compiles a user time/quality preference into per-component depth directives
  + budgets (search depth+wall-clock · screen stage · the 008 parser-tier seam · select
  budget · synthesis caps) at the plan-as-object compile surface. 015's per-depth constants
  table is the extensible compile target. Two 015 observations join this seam: whether the
  user-facing "deep ≈ 2–3 min" should include the round-1 rapid-leg screening (a full live
  episode ran 343 s end-to-end while the loop driver honoured its 150 s budget), and the
  **coverage-record stop-condition grain — DISCHARGED (task 019).** Migration
  `921d3a781f3f` widens the stop-value vocabulary: clean completion now records
  `completed`, a rapid wall-clock breach records `wall_clock_exceeded`;
  `breadth_truncated` is retained for historical rows only. The deep-path
  vocabulary is unchanged.
- **Rev-3.10 loop seams** — calibrated recall estimate (Chao capture-recapture /
  Undermind exponential-saturation fit → a user-facing "estimated % of relevant found" on
  the coverage record); sliding-window Thompson-sampling arm allocation (eval-gated, must
  beat round-robin); RCS-style abstract compression before screen (only if screen tokens
  bind the wall-clock); best-of-N query selection.
- **Study-geography extraction field** (rev 3.2, user) — **field + render surfaces
  landed (task 020, ADR 0016):** `study_geography` is a source-named, finding-grain
  string (`iof_v2`/`extract_iof_v6`), null when unreported, never inferred from
  publisher/venue/affiliation. Still open: the 010 selection-diversity consumer,
  characterise's post-extraction coverage dimensions, the Transferability capability,
  and canonicalisation/ISO-mapping (raw source-named strings today, no normalisation).
- **Eval-reuse pointers** (the eval slice's search seed): PaperFindingBench zero-adapter
  first run · the parity-tested `metrics.py` recall@k_est port · SYNERGY true-recall ·
  CODEC policy topics · the Campbell/3ie/EPPI "unzip" golden-dataset build · the
  per-backend coverage-vs-recall split · OpenAlex `sample`+`seed` as the eval-set sampling
  primitive · the AstaBench scoring stance (cost-normalized estimated-recall + nDCG on a
  Pareto frontier) · MetaSyn stage-attributed metrics (retrieval vs screening failures
  diagnosed separately) · the **mini-class judge comprehension-threshold gate** (measure
  the screen's relevance-judge quality before trusting loop-steered "adequate" — ADR 0012
  names this the loop's single biggest un-eval'd dependency) · suggest-arm live yield
  (0 proposals in the one live deep run; machinery scripted-test-covered).
- **Review-stack cleanup candidates — DISCHARGED (task 019, items 10a/10c/10d).**
  `acquire_sources`' legacy no-executed-calls branch collapsed into the
  executed-calls path; the two wire-validator families in `search_loop.py`
  unified; the duplicated `oa_record`/scripted-generation test doubles hoisted
  into `tests/helpers.py`.

## Full-text ingestion (task 008 seams)

- **Live `DocumentFetcher` — DISCHARGED (task 016).** Every pre-registered requirement from
  this entry shipped in `fetch_live.py` + the ingest pipeline, with one named exception kept
  below: explicit timeouts · manual per-hop-validated redirects with the full SSRF guard set
  (scheme allowlist, userinfo refusal, every A/AAAA answer classified with IPv4-mapped forms
  unwrapped, pinned-IP connect at the httpcore NetworkBackend seam) · per-host politeness +
  global bounded concurrency · retry/backoff (015 retry set, cap 1) · magic-byte content-type
  sniffing (%PDF wins over any header) · charset handling (bytes pass to trafilatura
  undecoded; UTF-8-replace only on the plain-text path) · landing-page PDF-link discovery +
  DOI-URL fallback (the one constructed URL, validated + encoded + fully guarded) · the
  access-failure ladder (401 → paywall; 403 → paywall only with corroboration, else
  `blocked_by_host`; 200+markers → paywall) with the OA cross-check · per-link exception
  isolation (an escaped raise becomes reason-coded `fetch_error`, never a component failure) ·
  streaming size caps + reservation-based in-flight byte accounting (deadlock-impossible
  backpressure) · bounded-parallel fetch feeding the parse pool. `make verify` stays
  deterministic and egress-free (fixture default unchanged; the import guard sanctions
  `fetch_live.py` alongside `search_live.py` and pins that `ingest_full_text.py` never
  imports it). The `pip-audit` CI pre-registration also **discharged** (016 rev 2.2:
  `make audit` + an independent CI job, ignore-list policy documented in the Makefile).
  **Fixture-corpus relocation discharged** (016 decision 12, per the 2026-07-05 trigger):
  corpus moved to `tests/data/fulltext` (out of the wheel, wheel-check test-pinned);
  `FixtureFetcher` resolves via explicit root / `POLICY_ATLAS_FIXTURE_CORPUS` / repo-relative
  default with a loud missing-corpus error; the ≤30 MB budget guard moved with it; a
  live-flagged run never silently falls back to fixture replay (test-pinned).
- **OS-level CI egress guard** (`unshare -n`-style) — the one 016 exception, **explicitly
  deferred with rationale** (016 rev 2.4, adversarial finding 8): the pre-registered
  test-level control exists as-built (the socket-deny guard covers parent + workers; the
  import-boundary guard pins the transport homes), and the OS-level CI variant — the stronger
  durable control — is a CI change beyond 016's one approved addition (the pip-audit job).
  Lands as its own CI-gated change.
- **Per-depth fetch budgets** (016 contract, decision 9 note) — a recorded lever of the
  tool-wide depth/time-budget gradation seam, not hard-wired in the fetcher: depth selects
  how much fetch wall-clock/volume a run buys. Arrives with the gradation seam's allocator.
- **Landing-page boilerplate heuristic** (016 review stack, Codex adversarial finding —
  declined as-designed): when landing HTML parses ≥ the thin threshold *and* a
  `citation_pdf_url` was discovered, the cascade accepts the HTML parse and never follows
  the PDF. Correct for full-text HTML articles that also carry pdf meta (the BMC/Frontiers
  shape — reordering would demote real articles); wrong for verbose landing pages, which
  then ingest as boilerplate `full_text`. Eval territory: content-quality evals decide
  whether a boilerplate detector / conditional PDF preference pays its complexity.
- **Bounded DNS resolution** (016 review stack, Codex adversarial finding): `getaddrinfo`
  runs outside the 30 s per-request timeout in both `_guard_url` and the pinned-IP connect;
  OS resolver defaults bound it near the same order in practice. A thread-wrapped resolver
  timeout lands only if live telemetry ever shows resolver stalls tying up fetch workers.
- **Destination-port allowlist** (016 review stack, security lane LOW): the SSRF guard
  permits any port on public IPs; an 80/443 allowlist would close public-host port probing
  at the cost of rare odd-port OA hosts. Revisit with live-corpus telemetry.
- **Stage-2 hydration as one window-function query** (016 review stack): per-snapshot
  streaming queries are the deliberate memory-bound trade (server-side early stop); a
  `SUM(length) OVER (PARTITION BY …)` single-query form gets both if stage-2 telemetry ever
  shows DB round-trips (not LLM calls) dominating wall-clock.
- **Shared live-HTTP retry vocabulary** (016 review stack, reuse finder): `fetch_live` and
  `search_live` duplicate the retryable-status set and retry-once/backoff shape; their
  control flows differ enough (status-outcome objects vs exception-only) that unification
  waits for a third live client to prove the seam.
- **Concurrent-run write guard** — **DISCHARGED (task 025)**: the API enforces at most one
  active run per project in Postgres at dispatch (`SELECT … FOR UPDATE` on the project row,
  `policy_atlas.api.locks.project_lock`); the same primitive serialises check-in answers and
  continuation claims. *Review amendment (2026-07-21):* the one residual same-project race —
  the walk executor and a project-locked API mutation (rename) are two unserialized writer
  families sharing the `max+1` event-sequence allocator — was found by the 025 review stack
  and closed with a SAVEPOINT-retry in `events.append` (collision → re-read, never a failed
  component commit; misordering remains impossible). Original note: eligibility selection takes no row locks and final writes
  are unconditional, so two simultaneous ingest runs over **one scope** could interleave
  (mirrors 007's concurrent-run dedup note; Codex adversarial finding, task 008). Scoped
  precisely (user question, 2026-07-05): the load-bearing invariant is **at most one active
  run per project**, not a single-process deployment. Everything the pipeline components
  mutate is project-scoped (eligibility filters on `project_id`; updates hit
  `project_source_snapshot`; result-table unique constraints are per-scope; the event-log
  sequence is `(project_id, sequence)`), so a **multi-user web app with users on different
  projects is already safe** — the spec's "single active writer" is a per-project property.
  The hazard is two writers on the *same* project (double-submit, retry racing the original,
  two queue workers claiming one run). **Pre-registered requirement for the web-app /
  durable-execution slice:** enforce one-active-run-per-project at run dispatch (Postgres
  advisory lock on project id, or a partial unique index allowing one `running` run per
  project) — or add row-level guards (`SELECT … FOR UPDATE` / status-guarded `UPDATE … WHERE`)
  in the components.
- **ML-layout parse escalation (docling)** — the quality tier for documents where pymupdf4llm's
  font-size heading heuristic fails. Observed at 008's /verify: four heading-light academic
  PDFs (Nature Comms ×2, Frontiers ASHP, PLOS) collapse into 2–3 very large chunks — content
  complete and locators honest, but exactly the heuristic-vs-ML gap this seam exists for; gate
  escalation on parse-quality evals. Sizing note: docling on CPU misses the couple-of-minutes
  wall-clock target (~5–20 min fanned out per ~100 docs) — GPU (AWS) sizing is part of this
  seam. The **pymupdf-layout tier is licence-blocked** for distribution: PolyForm
  Noncommercial / Artifex commercial — a further restriction AGPL-3.0 §7 cannot carry
  (investigated 2026-07-05; offline operation proven, so it slots in here if commercial
  licensing is ever bought). The determinism source-patch
  (`_install_deterministic_column_boxes`) deliberately no-ops if upstream's source changes —
  the fan-out determinism test is the backstop, the pin floor is `>=0.3.4`, and an upstream
  bug report is filed as follow-up. Task-011 pointer: extraction yield/failure rates on the
  collapsed-chunk PDFs (extract handles them via deterministic oversize subsegment splitting,
  so the full-read guarantee holds) are the **first downstream consumer signal** for gating
  this escalation — the parse-quality eval now has a measurable customer.
- **Citation-context character clamp for oversized chunks** (016 design conversation, user
  call 2026-07-09) — the chunk is the citation/locator grain, so a collapsed heading-light
  chunk (tens of thousands of chars) makes clunky provenance context wherever a citation is
  resolved to its chunk. Chunks are frozen (never re-segmented), so the fix is a character
  clamp at the **consumption** surfaces, windowed around the cited span (embedding units
  carry offsets — the natural anchor). Two named consumers: (a) the grounding-judge envelope
  (`synthesis_envelope_v1` carries cited chunks' full frozen text, no clamp — a deliberate
  013 plan call; changing judge input is prompt-bearing and eval-sensitive, so it lands with
  eval coverage, not as a rider); (b) **DISCHARGED (task 025)** — the web API's chunk-context read model
  (`GET …/citations/{id}/context`) clamps to an 800-char window each side of the cited
  span (consumer (a), the judge envelope, remains deferred with eval coverage). Cheaper mitigation than (and complementary to) the docling escalation
  above. Trigger: live corpora making collapsed chunks common, or judge token-cost
  observations. **022 adjudication (agenda B, owner, 2026-07-14): the JUDGE envelope
  stays UNCLAMPED** (every envelope change forces a re-baseline); the tool-return half
  shipped as 022's oversized-only WINDOWED returns (matched unit's span ± margin,
  a substring of the frozen chunk, offsets retained through retrieval — never a
  universal truncation). Remaining consumers of this seam: the web-app read surfaces.
- **Time-budget-aware parser selection** — the user's stated time horizon picks the parser
  (tight → pymupdf4llm, long → ML layout); `parse_profile`-per-snapshot (ADR 0004) is the hook.
- **Chunk-volume bias controls at the retrieve seam** — full-text documents contribute tens of
  chunks vs one abstract chunk; per-document caps / MMR / document-grain grouping when
  retrieval lands. Token-budgeted re-chunking at the embed seam subdivides the oversized
  heading-light sections above regardless.
- **OCR for `no_text_layer` documents** — scanned-only PDFs are reason-coded and kept, never
  parsed; an OCR tier (with its own honesty label) is the follow-on. Text-layer detection is
  Unicode-aware (`\w`), so non-Latin scripts don't false-positive into this bucket.
- **Vectorisation at the first vector reader — DISCHARGED ahead of the reader (task 009,
  approved exception).** The eager-and-uniform discipline (EB components §4) now runs: every
  chunk on all three ingestion paths gets unit-grain vectors (`embedding_unit_policy_v1`,
  ~2000-char sentence-boundary units, ~200-char overlap, one vector per unit, offsets into
  the untouched canonical chunk) via the `EmbeddingBackend` seam, live
  `text-embedding-3-small` behind the runtime-egress gate. The *reader* (retrieve/pgvector)
  is still the deferred piece — see the 009 section below. Token-budgeted re-chunking of
  oversized heading-light sections remains at the embed/eval seam.
- **Multi-PDF Overton assembly** — `grouped_pdf_ids_in_result` is retained; v3.0 ingests the
  primary `pdf_url` only.
- **Injection-screening posture extended to fetched full text** — same posture as acquired
  abstracts (007 entry above): full-text chunks are third-party content-of-record; nothing in
  v3.0 interprets them; enforcement lands with the LLM seams that read them.
- **Cross-project full-text snapshot reuse** — same shape as the acquired-envelope dedup entry
  (Data model section): `source_snapshot` is project-free, so reuse is additive. Note: today
  concurrent ingest of one document in two projects merely duplicates snapshots (wasteful, not
  corrupting); the reuse seam turns that into the system's first genuinely **cross**-project
  write race (two projects deduping onto one snapshot) — that slice inherits the concurrency
  design, alongside the per-project run guard above.

## Characterise / embeddings / telemetry (task 009 seams)

- **Langfuse trace grouping — first half DISCHARGED (task 019).**
  `contextvars.copy_context` propagation via `tracing.submit_with_context` on
  every traced/LLM executor fan-out closes the per-doc/window DETACHED-root-trace
  wart (extract windows, screening fan-outs now nest under the component root
  instead of minting separate traces). Second half stays open: planner turns
  are deliberately separate traces (B2 record), session-correlated — consider
  one conversation-root trace per orchestrate process with turn spans, or
  accept the session view as the grouping. Bounded telemetry rider; the
  capability-run entity (§ Select) — **DISCHARGED task 024** — is now the
  structural home; the trace-grouping work itself (turn-span consolidation)
  remains open.

- **EB artefact composition — LANDED with revised ownership (task 013, ADRs 0009 + 0010).**
  Synthesise (not the orchestrator) composes the one EB artefact at the run terminus —
  capability-composes; the orchestrator shapes sections at plan time. What remains
  deferred is the **composition-conventions** seam (block ordering/summary/key-findings
  conventions beyond proposal-order binding; citation renumbering-by-first-appearance —
  the V2-autopsy composition-seam note) and supersede + lock-on-advance versioning
  (blocks ship at `version=1`).
- **`retrieve` / pgvector / hybrid retrieval — first increment LANDED (task 013).**
  The 009 vectors' first reader is synthesise's scoped `search_chunks` tool: in-memory
  hybrid (cosine + lexical, RRF-fused) over JSONB vectors, guarded by a fail-closed
  `RETRIEVAL_UNIT_CAP` (20k units — beyond it the component fails structurally naming
  the cap, never a degraded sample), behind a swappable helper seam. Still deferred:
  **corpus-scale retrieval** (beyond the cap, or over unscreened content) and the full
  index-backed `retrieve` tool — pgvector-vs-alternatives, retrieval profiles,
  storage migration, and the chunk-volume-bias controls (per-doc caps / MMR /
  doc-grain grouping, 008 entry). Also at this seam: **judge-envelope widening +
  re-gather repair** (the repair alternative that re-gathers targeted evidence needs
  `retrieve`; v1 repair is reword-down over already-gathered evidence only).
  **`_load_findings` batch loading — DISCHARGED (task 020).** The per-snapshot N+1
  basis-query loop (013 review stack) is now one batched `IN (...)` query; the
  surrounding corpus-scale retrieval seams above remain open.
- **Contextual retrieval, late chunking, exact-token budgeting, semantic re-chunking** —
  retrieval-eval seams on the embedding-unit layer (contract decision 2, rev-8 research).
  The unit policy is versioned (`embedding_unit_policy_v1`) so any of these lands as a new
  co-existing policy, not a rewrite.
- **Embed-pass live robustness — DISCHARGED (task 019)** for the two
  pre-registered items: explicit 429 backoff outside the SDK's own retries,
  and recursive split-on-failure isolation (one poisoned unit now fails only
  its own chunk, not every chunk sharing its API batch). Remaining open
  residual: concurrent multi-batch behaviour at n ≫ batch (review adjudication,
  2026-07-06).
- **Very-large-corpus grouping** — **NARROWED (task 022)**: the two-stage engine closed
  the one-call exhaustive-partition cliff for `group` (184 distinct values live-proven
  healthy; duplicate-id failure mode gone — facet-partition-value-list-scale-limit.md);
  `FACET_VALUE_CAP=400` stays the fail-closed input guard, now at FACET grain. The
  remaining seam is discovery INPUT scale beyond the cap (discovery-sampling and/or
  embedding-based clustering over landed chunk vectors) and characterise's own
  all-titles discovery read. Assignment already scales (batched, budget-enforced). **Live-corpus robustness observations (015 live check —
  the first component to wobble when inputs got real):** a 206-doc corpus produced an
  `APITimeoutError` batch failure and an 85-doc corpus a double `InvalidDiscoveryOutput`
  rejection before a ~60-doc pass succeeded; retry caps and batch sizes are eval-slice
  calibration targets. Compounding gap — DISCHARGED (task 019): `str(exc)`,
  truncated to 500 chars, is now carried in logs and failure records on both
  the discovery and assignment paths (previously only `error_type` reached
  the logs).
- **Grouping-quality + adversarial-content evals** — theme quality is *not* asserted by
  the build (sanitized fixture corpora make it meaningless by construction); the eval seam
  owns: quality bars, adversarial/injection-shaped corpora beyond the shipped unit tests,
  **zero-support theme pruning** (discovery can emit themes assignment gives no members;
  they persist honestly with `size: 0` — pruning is a quality call, review adjudication
  2026-07-06), and a **two-scopes-one-project coverage fixture** (semantics verified
  correct, untested combination).
- **TopicGPT extensions** — topic refinement (merge/split against assignment evidence) and
  quotation-verified assignment, at the grouping-quality eval seam (contract § Research
  grounding).
- **Provider-signal prompt enrichment** — provider topics as per-doc grouping hints;
  taxonomy-bias risk → enters via the eval seam, never as a silent default. Same family
  (user, 2026-07-10, recorded at the 018 gate): **characterise theme outputs as
  facet-grouping hints** (cross-component enrichment — quality unmeasurable before the
  grouping-quality evals) and **mapper-produced per-document open tags for the document
  layer** — the latter additionally aggravates the tag-fragmentation trigger recorded at
  the tag-consolidation entry (more open-vocabulary tag writers before consolidation
  exists); both enter via the eval seam.
- **`group`-component inheritance — discharged (task 012)** — v2's theming lessons
  transferred when `group` was built; each recorded defect closed structurally: dead
  critique stage → no critique stage built (one schema-constrained partition + one
  validated repair is the entire call surface); silent concept drops → code-enforced
  exhaustiveness (counted `ungrouped`/`no_value` residuals, sum identities
  test-enforced); "General Theme" collapse → exact forbidden-generic-label validation
  rejects the response (prompt negative rule *and* code check); no scale guard →
  fail-closed `FACET_VALUE_CAP`; unseeded runs → deterministic sorted value
  ordering/ids (identical inputs yield identical prompts).
- **Tag namespace consolidation** — pruning/merging accreted `source_tag` assertions
  (re-runs accrete by design; provenance classes never merge) — an orchestrator-seam
  follow-on once real tag spaces emerge (contract decisions 5, 10). A third search backend
  also registers its tag extractor next to its mapper — `_provider_tags` dispatches by
  backend name and silently yields no tags for unknown names (`_MAPPERS` and the tag
  branches are two structures today; unify or add exhaustiveness enforcement when backend
  #3 lands — review adjudication, 2026-07-06). **Sharpened trigger (user live
  observation, 2026-07-10, recorded at the 017 gate):** classify's open
  methodological/structural tag vocabulary fragments at live scale, isolating
  documents — consolidation becomes useful there first; still an orchestrator-family
  seam with the trigger unfired in v1 (one run per project).
- **Langfuse follow-ons** (decision 13 ships the baseline: env-gated client, full-I/O
  spans, in-span scores, no-op with nothing configured, loud on partial config / missing
  host): runtime prompt-registry deployment (labels/environments, emergency-edit
  reconciliation), retention/sampling/masking/access policies, trace→eval-dataset
  promotion, and **two detached-trace warts** (span content complete in both; verified
  against the live instance, 2026-07-06): (a) OTel context does not propagate into
  `ThreadPoolExecutor` workers, so the first concurrent `assign` call surfaces as a
  detached trace — fix is context capture/attach at submit; (b) the **upload-ingest embed
  pass** runs outside any `component_span` (`ingest_upload` is app-boundary, not a run
  component), so its `embed:batchN` observations mint their own root traces — resolves
  with the upload audit-event seam below, which gives uploads their own observability
  surface.
- **Steering modes / landscape→synthesis steer-point pause — DISCHARGED (task 017 shipped
  the modes; task 024, 2026-07-16 shipped this exact pause).** The payload this entry
  flagged (the structured landscape summary in `component.completed`) was always going
  to ship (contract decision 8); the pause built on it is now P4 in 024's steer-point
  lattice ("the synthesis shape", post-group/pre-synthesise, which subsumes the
  post-characterise/landscape crossing when characterise is composed) — see the
  "Re-grouping / steering UX" entry (§ Group). The deepening-selection steer-point's
  read surface followed in task 010, then the pause itself in 017, then full
  enrichment in 024 (see the Select section).
- **Dual-view coverage** — corpus-view vs evidence-view distributions need the
  source/evidence policy object (contract decision 9); v3.0 ships single-view with the
  explicit `base` ladder and **no absence claims** (test-asserted).
- **Bedrock routes** — both seams (`EmbeddingBackend`, `ThemeGroupingBackend`) swap
  implementations; first pass OpenAI → target Bedrock is the documented v3.0 posture.
  **Infra ready on the DevOps side (user, 2026-07-10)** — the migration is now a pull
  decision, deliberately sequenced **after the eval slice**: it is a model-family swap
  (Bedrock does not serve the OpenAI models), which re-opens every empirically-settled
  model-routing choice, so the eval harness is the regression net that licenses it.
  Standing constraint until then (018 contract): nothing new couples to
  OpenAI-specific API surface (e.g. no Responses-API server-side conversation state).
- **Upload audit-event seam** — when the web-app slice gives uploads a real surface they
  get their own audit event + observable processing (incl. embed counts, currently a
  structured log line `ingest_upload.embed_counts`) — an app-boundary event, not a run
  component (user Q&A at the 009 plan gate). Its tracing rides along: a live upload's
  embed batches currently surface as detached root traces (no surrounding span — wart (b)
  in the Langfuse entry above); the seam wraps them in an upload-scoped span.

## Select (task 010 seams)

- **Deepening-selection steer-point pause — DISCHARGED (task 017; enriched task 024,
  2026-07-16).** The mode-governed pause itself shipped in 017 as the *only* live
  steer point in the system (the single-steer-point limitation this entry
  originally described). 024's P3 ("deepening selection") enriches it in full:
  the trigger set gains S0; the payload gains a **selection preview** (top
  selected docs with strata/scores/reasons + notable exclusions); options gain
  extraction profiles (ICF), re-extract refresh (D3), strata scoping (D6) and
  doc exclusion (D7) alongside the five original options; combined free-text
  asks compile through the router into one confirmed multi-lever delta. Original
  read surface (bidirectional rationale + trigger flags — `large_stratum_excluded`,
  `priority_stratum_excluded`, `must_include_conflict`, `thin_base`, `thin_full_text`,
  as recorded at task 010) is unchanged and still the trigger substrate.
- **Corpus-conditioned selection budget (owner, 2026-07-11, 018 review conversation)** —
  `ANALYSIS_DEPTH_TABLE`'s `selection_budget: 25` at deep is a plan-pinned cost CEILING
  (allocation fills up to it, capped by eligible capacity), not a quality judgment.
  The evolution: condition the executed budget on the corpus (screened/full-text counts,
  strata shape, question breadth) rather than a constant — it lands naturally in the
  agent-authored `SelectionDirective` seam below (the just-in-time post-characterise
  author sees exactly those signals), with the depth-table constant demoted to the hard
  ceiling. Needs eval evidence for the conditioning function; the steer-point flags
  (`thin_base`, `large_stratum_excluded`, …) are the ready-made inputs.
- **Agent-authored directives** — the capability agent authors the `SelectionDirective`
  **just-in-time at invocation, post-characterise** (plan-as-object § forecast-vs-commit:
  the up-front plan is a non-compiling forecast, never the executed directive). v3.0
  sources the directive from `evidence_scope.context["selection"]`; the `select` facade
  signature is deliberately the tool call the agent will make, so arrival is a
  parameter-authoring change, zero re-plumbing.
- **Rerank-quality evals** — deterministic-ranked vs LLM-reranked selections compared on
  downstream yield once extract gives selection a consequence; the eval-ready Langfuse
  traces (full I/O, `rank_batch_valid` scores) exist now. **Listwise ordering** (the model
  emits a ranking, not per-doc scores) is the known-better method with a cross-batch merge
  cost — it lands at this seam, competing with the shipped pointwise 0–10 +
  composite-tie-break baseline.
- **Embedding-relevance for select — declined seam** (010 contract rev 4): by select time
  the semantic dimension is spent twice (screening judged relevance; stratification grouped
  semantically), so within-stratum cosine-to-intent discriminates weakly. Revisit **only**
  if rerank-quality evals show the deterministic composite/fallback needs a semantic leg.
  The 009 chunk vectors' first reader remains `retrieve`, unchanged.
- **Cross-encoder relevance models (Cohere-class, available on Bedrock)** — they score
  query-relevance, not purpose-fit: recorded at the **`retrieve` seam** (retrieval's
  rerank upgrade), deliberately not select's.
- **Capability-run entity — DISCHARGED (task 024, decision 2, 2026-07-16).** The
  `capability_run` table shipped: `capability_run_id` · `project_id` ·
  `evidence_scope_id` · `capability` · `plan_id`+`plan_version` at approval ·
  `status` (running/succeeded/degraded/failed/aborted) · `session_id` (nullable,
  the 025 anchor) · `started_at`/`ended_at`, plus nullable `runs.capability_run_id`
  (composite FK). The runner opens/threads/closes the walk row across every
  component execution in a run — the "one run = one component execution" gap
  this entry described is closed. Deliberately not modelled: composition fields,
  artefact back-refs (derivable), turn tables (still 025). The recorded Langfuse
  detached-trace warts (009's executor threads; 010's `rank:batch` generation
  spans) are unaffected by this entity alone — those need actual trace-grouping
  work (§ Characterise, "Langfuse trace grouping").
- **Policy soft-prior tilt** — integration shape recorded, not deferred-blind: when the
  source/evidence policy object lands, it **compiles into directive boosts**
  (provenance-stamped as policy-sourced), becoming one more directive author beside the
  user and the capability agent. Select's code is untouched by construction — the boost
  surface is the ground-up design for it.
- **Selection-diversity extensions** — publication-country stratification and
  study-geography/population diversity dimensions: the spec itself marks them rough,
  cluster-approximated and properly post-extraction.
- **Second `select` strategies** — Transferability dependency-scoping et al. (other
  capabilities' problem); the strategy registry validates exactly the two built-ins.
- **Suite-wide socket deny — DISCHARGED (task 019).** `pytest-socket` 0.8.0
  deny-by-default with a loopback allowlist in `pyproject.toml` `addopts`;
  per-test deny patterns retired. The 016 worker-process guard is deliberately
  kept alongside it — `pytest-socket` is in-process only.

## Extract / findings layer (task 011 seams)

- **Modelled vs observed effect basis at the finding grain — DISCHARGED (task 020,
  ADR 0016).** `effect_basis` enum (`observed` | `modelled`, null if indeterminate)
  landed on the IOF wire + row + `iof_rules_v2` coverage, its own dimension (never
  folded into `causality_by_design` — causal identification and evidence basis are
  different axes). Lands in the writer envelope (terse-adjacent) and is reachable at
  the annotation layer via resolve-via-row (not embedded — owner call, purely additive
  later). `extract_iof_v6` carries extraction guidance; `extract_finding_vetter_v3`
  gains one guidance line so modelled/projected results aren't mis-flagged as
  aspirations (payload itself unchanged — self-label bias risk). No backfill; v1 rows
  stay null (`field_coverage` key-absence reads as "not recorded under v1", distinct
  from a genuine v2 null). One candidate deliberately NOT riding, entered as its own
  seam below.
- **`effect_basis` as a judge-envelope candidate (task 020 sweep).** The grounding
  judge seeing the structured basis signal — prose asserting an effect while citing a
  modelled projection is a faithfulness question the judge cannot see today. Any
  judge-envelope change is bound by 018's verification-grade A/B protocol (replay the
  same claim set through both envelopes, hand-inspect every flipped verdict).
  **Re-deferred to the EVAL gate at the 022 contract (agenda E, owner, 2026-07-14)**,
  with the Codex-refined rule (owner-confirmed): eval-gate envelope A/Bs run
  **sequentially per envelope change**, never one merged baseline — in particular this
  A/B must not share a baseline with 022's 17(i) span-map change (whose re-judge replay
  ran in 022) or the writer-envelope metadata queue below.
- **Length bound on free-text finding fields (task 020 security lane, LOW).** No cap
  exists between model output and storage on the finding free-text class
  (`study_geography`, and pre-existing `intervention`/`outcome`/`study_design`/
  `comparator`/`population`) — all prompt-feeding columns re-serialized into every
  downstream synthesis seed and `query_findings` result, so a hostile document can
  induce prompt bloat / cost amplification (not breakout — carriage is JSON-fenced
  throughout). One bound applied in `validate_record` (coerce-with-coverage-marker,
  `DIRECTIVE_STRING_MAX = 200` precedent in `schema.py`) covers the whole class.
  Practical exposure is limited today (schema-constrained structured output + the
  document's own influence bound size); a `iof_rules` version bump when picked up.
- **Finding-vetter per-doc calls run sequentially — DISCHARGED (task 019).**
  Parallelized on the extract executor width with context propagation; workers
  judge, the parent applies in input order; usage is accumulated in the
  submitting thread.

- **The extraction service + evidence dataset snapshots** — profile resolution against
  existing records, per-source task objects, capability commits declaring extraction
  profiles, and pinned point-in-time dataset consumption. 011 shipped the minimal honest
  form: a per-document extraction record with a partial-unique memo key over the success
  states, checked before any call; EB's profile is the named constant `eb_iof_base_v1`.
  `group` will read the run roll-up (`extraction_result` by `extraction_run_id`), not a
  pinned dataset, until this seam lands.
- **Extraction-quality evals** — finding-level ground truth over the fixture corpus; the
  slice's bar was machinery correctness, schema fidelity, honest coverage accounting and
  verified anchoring — extraction *quality* (right/complete findings) is unmeasurable
  without this. Gates most seams below; also **unblocks 010's recorded rerank-quality
  eval seam** (same eval workstream).
- **Multi-pass recall extraction** (contract rev 1.3) — a second identical-prompt pass
  raises recall on long documents (LangExtract's recipe: char-interval overlap merge,
  first-pass-wins recorded at the seam); can't be measured without ground truth →
  eval-gated. `extraction_provenance.pass_count` records 1 from day one so the seam opens
  cheaply. One named recall gap for the evals to weigh (011 review, Codex): when a single
  segment fills a whole window, the greedy windowing must advance without overlap (the
  no-regress progress guarantee), so a claim spanning the boundary between two
  window-filling chunks is never seen whole by any one call.
- **Retrieval-augmented extraction** (contract rev 1.1c) — full read + targeted in-doc
  retrieval repair / cross-window context assembly (incl. cross-window naming consistency,
  cut at rev 1.2). Composable and legitimate — the full read licenses coverage — but
  eval-gated behind `retrieve` + extraction-quality evals showing a field-completeness gap
  on multi-window documents.
- **Retrieval-scoped extraction — declined** (contract rev 1.1b) — reading a retrieved
  subset makes `no_findings`/`not_extracted` unverifiable (a silent new base-ladder rung —
  false-absence machinery EB exists to prevent) and inverts the recall-critical trade. Any
  future retrieval scoping must be an explicit, recorded coverage-base rung, never silent.
- **RAG-based findings layer for quick/standard runs** (user, 2026-07-10, recorded at the
  018 gate) — a retrieval-grounded findings/extraction surface for runs that skip the deep
  extract chain (and a more generic variant for non-intervention-shaped intents). This is
  exactly the explicit coverage-base rung the entry above reserves: legitimate only with
  its own recorded rung and honest absence semantics, so it needs its own design gate —
  never a silent quick-run shortcut. Adjacent gradation fact (018): standard analysis
  depth no longer runs select/extract/group, so this seam is the recorded path to
  findings-shaped content at sub-deep depths if evals show envelope-basis synthesis
  insufficient there.
- **Generic finding container — declined** (contract rev 1.1a) — typed tables with
  CHECK-enforced vocabularies won ("coherent typed record, dimensions intact and
  queryable"); revisit only if a third finding schema is specced.
- **Reason-then-constrain extraction** (rev 1.3) — draft free-form then bind to schema;
  demonstrated gains are on small open-weight models and closed-weight API models resist
  the format tax; eval-gated remedy if judgment-heavy fields show errors.
- **LangExtract dependency — declined** (rev 1.3) — techniques absorbed (raw-offset span
  recording, negative rules, pre-flight example validation, multi-pass merge recipe); the
  library itself is Gemini-first and outside our provenance model.
- **Per-intervention focused-call decomposition** (rev 1.4) — V2's cross-contamination
  remedy (one intervention per call); eval-gated remedy if quality evals show cross-finding
  contamination in the per-doc call. Same trigger family as multi-pass.
- **Bounded fuzzy quote fallback** (rev 1.4) — LangExtract's coverage+density-gated LCS
  tier, fuzzy-only-on-failure; adopt only if evals show exact+normalised recall
  insufficient, and never inside the verified-verbatim guarantee (a fuzzy match can flag,
  never verify).
- **Failed-extraction recovery loop** — beyond the in-run window retry, a failed doc
  re-enters via a new run (the screen_failed precedent); failure rows are attempt history
  and never block the memo. A dedicated recovery sweep is unbuilt.
- **Cross-window dedup** — windows are independent; the 1-chunk overlap can in principle
  yield near-duplicate findings across windows that exact claim-key dedup already collapses
  when identical; heuristics beyond that are out until observed in practice (the contract's
  stop condition: bring it back to a plan gate, never grow silently).
- **Hybrid-indexing of `intervention`/`outcome`** — committed for v3.0; the mechanism is
  the `retrieve` adapter's second index target and lands with `retrieve`. Columns are
  filterable now.
- **Mixed/unclear findings are first-class — requirement carried forward; test-pinned
  (task 020).** V2 extracted `mixed`/`unclear` effect directions and then aggregation
  silently zeroed them; flag-not-drop must survive the whole deep chain: `group` and
  `synthesise` must carry these findings, never discard them at aggregation. Tests now
  pin this behaviour end-to-end across the chain — already-correct, no drop existed to
  fix.
- **Intra-run shared-basis-snapshot memo** — two selected docs whose basis resolves to the
  *same* content-keyed snapshot (identical full text dedup'd across docs) would both
  fresh-extract and collide on the memo key (IntegrityError → honest loud failure).
  Impossible with the current corpus (pss is unique per project+snapshot; full-text
  snapshots are per-doc); if content-hash full-text dedup ever lands, add an in-run memo
  update so the second doc reuses the first's record. Same posture for **concurrent
  extract runs** over the same project/fingerprint (011 review, Codex): the memo read is
  not atomic with the insert, so two simultaneous runs can both extract fresh and the
  second fails loudly on `uq_ser_memo` — wasted spend, never corruption; a single-writer
  operating model makes this a non-path today.
- **Evidence type is prompt input but not a memo/record key component** (011 review,
  Codex) — **provenance column landed (task 020, ADR 0016 decision 7):**
  `source_extraction_record.primary_evidence_type` now records what was actually sent
  to the prompt (CHECK'd against `EVIDENCE_TYPES` + `'Unclassified'`; null on
  pre-prompt failure rows only — `empty_basis`/`basis_mismatch` never fabricate a
  value). The memo-match rule stays deferred: the memo still keys on (project, basis
  snapshot, fingerprint) only, and its trigger — a hand-rolled plan that extracts
  *before* classifying — still doesn't exist. If such plans become supported, make
  memo hits require an evidence-type match too.
- **Per-run window/call ceiling** (011 review, security) — the enforced call budget is
  `windows × (1 + retry_cap)`, which scales with document length; there is no absolute
  per-run cap, so a pathological oversized corpus drives spend linearly ("within
  budget"). Bounded today by `select`'s budget (the designed cost control) and the
  fixture corpus. If arbitrary corpora land, add an absolute window ceiling as a
  fingerprint component with a per-doc `window_cap_exceeded` failure reason.
- **Prompt envelope fencing — DISCHARGED (task 020, ADR 0016 decision 6).** Title,
  abstract AND `primary_evidence_type` now enter `extract_iof_v6` as one id-keyed JSON
  data object (the same treatment the segment text already got), closing the
  structural spoof-around-template seam identified here. Evidence type was
  closed-vocabulary already but is fenced too, for a uniform envelope shape.
- **`thin_extraction` roll-up flag** — named in the contract "where computed"; no
  definition was pinned and v1 deliberately does not compute it. Define (e.g. findings per
  extracted full-text doc below a floor) when a consumer needs it.

## Group / facet-level theming (task 012 seams)

- **All-or-nothing partition validation — FIXED in the 013 PR** (root-caused
  and fixed 2026-07-08, 013 step-7 trace replay). One group label over
  `LABEL_MAX=80` made `validate_partition` (`facet_values.py`) reject the
  ENTIRE partition; both live intervention-facet runs lost 16 coherent,
  id-clean groups to a single 89–92-char label, twice each, landing 0 groups
  (outcome runs survived at 78 chars — luck). Fixed as: label/description
  rule violations reject at **group grain** (the violating group's members
  join `missing_ids` for the repair); unknown/double-assigned ids stay
  whole-response (id integrity); rejection reasons persist into
  `grouping_provenance.rejection_reasons` + a `groups_rejected` flag
  (previously the reason existed only in the Langfuse trace). Regression
  tests replay the live shape (`test_validate_partition_one_long_label_keeps_other_groups`,
  `test_one_bad_label_never_zeroes_the_run`).
- **`query-findings` tool — DISCHARGED in full (task 013).** The scoped read tool landed
  with its deliberative consumer exactly as recorded: agent-invoked in synthesise's
  section loop (`make_findings_reader` behind the closed tool set), deterministic and
  project/run-scoped. Group's deterministic read stands unchanged; the 012 deviation
  from components §8's tool table is closed.
- **Facet-grouping quality evals** — extends the 009 grouping-quality eval seam:
  partition coherence/usefulness on real reference sets, negative-rule adherence beyond
  the shipped unit tests, and **`FACET_VALUE_CAP` calibration** (150 is plan-pinned; the
  eval owns the real ceiling). The 012 bar was machinery correctness, exhaustiveness
  invariants, honest residuals and provenance fidelity — grouping *quality* is not
  asserted by the build.
- **Large-corpus grouping algorithm** — beyond the fail-closed `FACET_VALUE_CAP`
  (`value_cap_exceeded`, loud, never a degraded pass): tail-group-capable discovery
  and/or embedding-assisted value clustering over the landed chunk vectors. Eval-gated —
  a head sample cannot discover tail-only groups, which is why the sample-discover/assign
  shape was rejected at contract rev 1.3 and stays rejected until evals exist.
  **Owner note (2026-07-11, during 018 C):** characterise's discovery-model +
  assignment-model split works well in practice — when the eval slice reopens this seam,
  weigh that two-stage shape as a candidate for facets too, against the recorded
  tail-discovery risk and the partition-exactness invariant a split must preserve.
- **Agent-authored grouping directive** — the same seam as select's agent-authored
  directives (above): the capability agent authors `context["grouping"]` just-in-time at
  invocation; the `group` facade signature is already the tool call, so arrival is a
  parameter-authoring change, zero re-plumbing.
- **EB report-shape boundary vs future capabilities (owner steer, 2026-07-11, 018 C)** —
  V2's templated report grammar (core answer ending in an imperative directive,
  fixed background section, interventions table, "exactly 3-4 actionable policy
  recommendations") is the recorded anti-pattern: too intervention-focused and too
  rigid for v3.0's intent diversity. v3.0 EB stays intent-led discovery with an
  evidence-descriptive role menu (synthesise_sections_v2: policy/delivery context
  under specific titles, cross-cutting patterns, enablers-and-barriers-as-described).
  Several V2 template sections belong to FUTURE capabilities, not EB:
  recommendations → options assessment; stakeholder perspectives → stakeholder
  capability; impact framing → impact assessment; cost comparisons → value-for-money.
  When those capability contracts are drafted, they should reclaim their section
  types from the V2 template rather than EB growing them. The `section_role` seam
  (SectionSpec, 018 B) is the extension point — roles extend without schema change.
  Eval slice: judge composition quality across the 7 intent shapes with this
  boundary in mind.
- **Cross-schema reference-mediated linkage — DISCHARGED (task 021, item 12):** the
  membership bridge landed — `group`'s loader reads both finding tables via the shared
  reference columns, `FindingFacetView` carries a `kind` tag with nullable
  `effect_direction`, `direction_spread` stays IOF-members-only, and group payloads
  carry per-kind member counts. The design property 012 shipped is now machinery.
  What remains deferred rides the EB-internals ICF entry (ICF facets, UNION view —
  Slice C).
- **Re-grouping / steering UX — DISCHARGED (task 024, 2026-07-16).** A different facet
  is still simply a new run with a different directive (shipped semantics,
  unchanged). The mode-governed pause around grouping is now P4 ("the synthesis
  shape", post-group/pre-synthesise): triggers from grouping per-facet flags;
  options include only-these-themes / section edits, evidence-emphasis boosts,
  re-group coarser/finer (D8 `grouping.granularity`), re-group with guidance
  (B3 `grouping.guidance`), or as-proposed — routed through `propose_synthesis_plan`.
- **Facet-theme promotion** (012 contract rev 1.2) — canonical/queryable facet groupings
  for downstream capability agents. The data-model's staged ladder: run-local (shipped —
  rung 1) → project-scoped persistent → graph datastore, gated on an
  entity-resolution-quality bar (a facet-group label bundling different sources' strings
  asserts cross-source identity, often question-relative — never trusted canonically
  before that bar exists). Options Assessment reads run-referenced groupings by
  `grouping_run_id` until then.
- **Shared traced-call helper across OpenAI backends — DISCHARGED (task 013).** The
  recorded trigger fired: `tracing.traced_call` factors the shape and all five OpenAI
  backends (`extraction_backend.py`, `ranking.py`, `facet_grouping.py`,
  `synthesis_backend.py`, `grounding_judge.py`) ride it, heterogeneous call-sites
  preserved (ranking's in-span trace score via the `after` hook).
- **Harness failure-event append dies inside an aborted transaction — DISCHARGED
  (task 017).** The EB capability-runner's failure path rolls back the component
  transaction first and appends `component.failed`/`run.failed` idempotently on a
  fresh transaction against the pre-committed run row (`runner.py::
  _record_failure_backstop`; contract rev 2.5 adversarial finding 7). Honestly
  scoped: the fix lives at the runner layer (the product path); a component driven
  directly through `run_harness` outside the runner (the zero-egress skeleton smoke)
  retains the old behaviour — acceptable, the runner is the product path.

## Synthesise (task 013 seams)

- **Gather/writer model split — HEAD OF THE POST-EVAL COST QUEUE (022 contract Out
  list; owner 2026-07-12 quality-sensitive-cost-routing pin, re-confirmed 2026-07-14).**
  Routing tool-selection (gather) turns to a cheaper model: the 022 Codex trace
  investigation measured gather turns ≈ **43% of writer input tokens for ~4.7k output**,
  est. 20–30% run-cost saving. Deliberately post-eval: it is semi-neutral (a weaker
  gatherer can fetch worse evidence) and evals are its regression net.
- **Old `group_facet_v1` partition machinery retirement — DISCHARGED (022 review
  stack, simplification pass)** — deleted: the one-call partition prompt, backends
  and their test file (`facet_grouping.py` 656→~80 lines; `test_facet_grouping.py`
  removed). The module keeps only the live-imported constants (`FACET_VALUE_CAP`,
  label bounds, `FORBIDDEN_GROUP_LABELS`) and the value/partition wire TypedDicts.
- **Group assignment fan-out concurrency (022 build note)** — group's engine runs
  assignment batches serially (`max_concurrent_batches=1`; characterise uses 4).
  Acceptable at ≤5 batches/facet live; revisit if wall-time observations say otherwise.
- **Unspanned-lane full decoupling (018 review stack, security lane MEDIUM)** — the
  unspanned-assertion judge scan rides the grounding-judge call, so a block whose final
  prose no judge call scanned (no judged-type claims; or a splice rebuilt the prose and
  the rejudge had nothing to judge) mints unscanned. 018 closed the *honesty* half:
  `unspanned_lane_skipped` on the accounting + rollup distinguishes "not looked at" from
  "clean". The *coverage* half — a judge call fired solely for the unspanned lane on
  those paths — is eval-slice work (it adds a per-affected-section LLM call and needs
  the flag-volume calibration that workstream owns). Until then, consumers of
  `unspanned_assertions == 0` must check the skip flag.
  **022 adjudication (agenda C, owner, 2026-07-14): the coverage half STAYS PARKED for
  the eval slice** — the 404-observation live-trace scan showed the lane's problem was
  precision, not coverage; 022 shipped the precision fixes instead (all-types span map,
  the three named counters, supersede-not-concatenate). **Eval re-baseline note:**
  `unspanned_assertions` counts before/after 022's item-17 fixes are NOT comparable —
  the eval slice must re-baseline that metric.
- **Pre-synthesise steer point → `context["synthesis"]` directive (owner-confirmed seam,
  2026-07-11, 018 review conversation)** — a check-in after grouping/characterise and
  before synthesise (or at section-proposal time): show the proposed sections and
  discovered themes/facet groups; the user prunes/boosts ("only these themes", "prefer
  strongest evidence types"); the response compiles into the EXISTING fail-closed
  `context["synthesis"]` directive (sections + `group_ids` + `retrieval_boosts`) — the
  compile target below that nothing authors yet. Parameter authoring on built machinery,
  zero re-plumbing; pairs with the `deepening_selection` steer point the same way select
  pairs with extract. **BUILT (task 022, item 14)** as the side-effect-free surface pair:
  `propose_synthesis_plan` (no artefact minted, no rows written) + the deterministic
  fail-closed `compile_synthesis_directive` — an external caller collects the user's
  response out-of-band and submits the compiled directive on a later invocation.
  Remaining seam **mode-governed pause UX — DISCHARGED (task 024, 2026-07-16)**: this
  is P4 in the 024 steer-point lattice, live in-run (Moderate always pauses here);
  see the "Re-grouping / steering UX" entry above.
- **Selection prior at standard depth — DISCHARGED (task 019, owner
  amendment).** Select now runs at standard (plan-pinned budget 15); synthesise
  references it via `deepest_successful_reference`; prior + origin accounting
  apply by construction. Still open: the `SELECTION_PRIOR_BOOST` calibration
  question — the prior itself is a flat 2.0× multiplicative boost on the fused
  retrieval score, which could over-suppress an unselected-but-highly-relevant
  chunk for a specific section. Mitigations already in place: it is a soft
  prior never a filter, unselected docs stay in both retrieval legs, and
  citations record `origin: selected|unselected_screened` so the effect is
  measurable. Eval-slice measurement: citation quality/rate by origin as a
  function of the boost value.
- **Writer read-tool scoping arguments (owner direction, 2026-07-11)** — `search_chunks`
  takes only a query today; `query_findings` already scopes (`group_id`, `finding_ids`,
  `effect_direction`) and `lookup` by `doc_id`/`tag`. Give `search_chunks` optional
  fail-closed scope filters (tags, doc ids, facet-group members, evidence types —
  validated against the closed vocabularies like the directive boosts) so the writer can
  gather strategically per section instead of relying on global boosts — "act like a
  researcher". Interacts with the Cohere/Bedrock cross-encoder rerank recorded at the
  `retrieve` seam. **Plumbing BUILT (task 022, item 13)** — per-argument fail-closed
  filters (doc ids ∈ corpus · group ids resolve · evidence types enum · tags ∈ project
  set; the earlier "like the directive boosts" precedent was corrected at the 022
  adversarial review — boosts record unmatched values, these REJECT) + the v7 tool
  description. Remaining seam: **WHEN-to-scope prompt guidance** — post-eval tuning
  (lead-only, replay-evidenced).
- **018's A/B-gated writer-envelope metadata queue — dangling, recorded here (owner
  check, 2026-07-12; task 020 sweep).** Contracted in 018 (contract § Writer envelope
  widening) but never run and never discharged: author institution(s) (first in the
  queue) · FWCI · further loop-suggested fields, each adopted only on replay evidence.
  (018's *default-adopt* set — publication year, evidence type, appraisal label,
  venue/publisher, cited-by count — already shipped and is not part of this seam.)
  Silent omission is not deferral; this entry is the explicit seam at the C/eval gate.
  **022 adjudication (agenda D, owner, 2026-07-14): explicitly RE-DEFERRED to the eval
  gate** — Phase 2 already rebuilt the writer surface (`synthesise_section_v7`);
  stacking an envelope-content A/B on the cache/repair changes would muddy attribution
  of both, and 022's cost measurement wanted a clean before/after. The "dangling" state
  is discharged by this decision; at the eval gate it runs as its own SEQUENTIAL A/B
  (never merged with effect_basis's or any other envelope change).
- **Plan-compile section machinery** — the fail-closed `context["synthesis"]` directive
  (sections + retrieval_boosts, normative grammar per contract rev 8 M5) is the compile
  target the future plan-shaped-sections machinery and the source/evidence policy compile
  into (the 010 pin); nothing compiles into it yet.
- **Cross-encoder chunk reranking** — the `ChunkRerankerBackend` stage ships pass-through
  (`reranker: "none"` recorded in provenance); the live Bedrock Rerank backend + its
  `run_harness` injection point land with the Bedrock integration slice (the retrieval
  contract's inference-trust-boundary line; the 010 Cohere-class note). No public kwarg
  ships while nothing live exists — the V2 dead-config lesson.
- **Content-scan pattern claims** (contract rev 8 M9) — the spec's soft pattern rung ("a
  shape the agent reads across the corpus") is prohibited in v1: no deterministic
  validator and no judge-lane fit exists yet; a cross-corpus-shape assertion without
  computable counts rejects, and the prompt says so. The type arrives with its
  verification mechanism, never silently absorbed.
- **Unappraised chunks in the retrieval scope — contamination measurement + soft-prior
  fallback** (user question during the 014 rev-1.11 adjudication, 2026-07-08). The
  read/cite split is deliberate ("screen bounds reading, appraise bounds citing"):
  unappraised docs (classified Unknown/Other, or unclassified) are retrievable but a
  chunk claim citing one is hard-rejected (`unappraised_doc_citation`,
  `synthesise.py`). The open question is whether readable-but-uncitable chunks
  *contaminate context* — occupying top-k slots under `TOP_K`/char budget and priming
  prose nothing can cite. Two-part seam: (1) **eval measurement first** — the eval
  workstream measures the share of retrieved chunks that are unappraised and whether
  their presence correlates with weaker or less-cited sections (turns the intuition
  into a number). (2) **Soft-prior fallback if it bites** — a standing default
  down-weight of unappraised chunks in retrieval ranking. The per-run mechanism
  already exists (`retrieval_boosts` over appraisal tier, clamped multiplicative,
  re-weight-never-exclude); promoting it to a *default* is a baked prior and needs its
  own 013-surface gate (the rev-7.5 steerable-never-baked ruling). An appraised-only
  retrieval *boundary* was considered and REJECTED (2026-07-08): it would make
  envelope-grain classification a hard reading gate (a wrong `Unknown` silently
  removes a doc from the writer's world, unflagged), systematically penalise
  thin-metadata grey literature (compounding the 014 11(iv-b) asymmetry), and
  recreate the reading-boundary perversity the select-as-soft-prior ruling fixed.
  Related shrink-the-set path: the classify-Unknown full-text resolution seam (014
  family) — re-classified Unknowns become appraisable and citable, reducing the
  readable-but-uncitable set by adding information rather than cutting reading.
- **Policy-conditioned citable-bar flagging** — the source/evidence policy's citable bar
  applies flag-not-block; v1 honours the rule through the weakly-grounded mechanism only.
  Policy-conditioned flagging (below-policy support visibly flagged as such) lands with
  the policy surface.
- **Block summaries / artefact summary / faithfulness judging** — the navigation layer
  (provenance-grounding § Summaries): co-versioned block summary column, the artefact
  summary field, flat faithfulness judging. Blocks ship summary-free at `version=1`.
- **Synthesis structure discovery** (contract rev 7.2 — declined-for-now bundle):
  recon-informed section proposal, structure-mismatch signals, a bounded revision
  checkpoint. Revisit with evidence if one-shot sectioning proves a real problem on live
  corpora.
- **Regeneration-time coherence** — the data-model's original seam: a coherence pass when
  blocks regenerate. Deliberately not a write-time pass — the rolling claim ledger owns
  write-time coherence (rev 7.2).
- **Synthesis / judge / retrieval quality evals** — the eval workstream owns judge
  calibration (clean/weak line, repair round count), section/prose quality, retrieval
  quality, and the calibration of every plan-pinned constant (`SECTION_CAP`,
  `SECTION_TURN_CAP`, `SYNTH_CHUNK_TOP_K`, `SYNTH_CHUNK_CHAR_BUDGET`,
  `RETRIEVAL_UNIT_CAP`, `REPAIR_ROUND_CAP`, retrieval-boost weights, the `lookup`
  vocabulary, `EMISSION_CLAIMS_MAX`, `CLAIM_TEXT_MAX`). The 013 bar was mechanism
  correctness, invariant enforcement, honest flags and provenance fidelity; the field's
  loudest warning (rev 7.3 scan) — shipping without an eval harness — makes this the
  recommended next slice. **Review-stack hardening candidates for this seam
  (013 step 7, 2026-07-08):** (a) pattern/theme/gap claim *text* is
  deterministically validated but never judged (contracted design) — injected
  corpus prose can ride an unjudged claim type into the artefact; candidate:
  route those texts through the judge's strict lane or a deterministic
  evaluative/imperative screen, decided with judge-calibration evidence.
  (b) An adversarial judge-calibration case: a chunk whose text self-certifies
  claims citing it ("classify as tier_1") must not sway the verdict — the
  judge prompt now carries the rule; the eval proves it.
- **Id-carrying repair schema — DISCHARGED (task 022, item 11).** `RepairItemWire`
  carries the failing claim's `claim_id`, validated against the failing set (unknown or
  duplicate ids reject structurally); positional binding is gone, and the repair call is
  a dependency-complete micro-call (no transcript resend). The deferred **re-gather
  repair** (tool turns inside repair) plugs into the same interface — still deferred.
  Two 022 review-stack riders on that seam: (a) a wrong-chunk citation (quote
  actually matched a different, uncited chunk) cannot be re-pointed by the
  micro-call — the prompted honest-drop path covers it today; quote_verify's
  match evidence (spans/match_status, currently stripped by `_wire_claim_data`'s
  wire projection) is the natural repair input if re-gather is built. (b) Repair
  dependency records resend oversized cited chunks un-windowed (the section loop
  windows them; repair doesn't) — bounded by `REPAIR_ROUND_CAP`, re-measure on
  the eval cost axis; windowing repair deps needs the same match-evidence spans.
- **Trace-store trust boundary** (013 review stack, 2026-07-08) — Langfuse
  traces are deliberately full-I/O: pre-validation emissions (including
  fabricated quotes later excluded from the domain model) and repair inputs
  land in trace storage. The persistence invariant is DB-scoped by contract;
  if trace access ever widens beyond the operator, a redaction policy becomes
  a slice.
- **Multi-execution fan-in for consumers + capability-run orchestration**
  (user direction, 2026-07-08, post-013-build) — the registry's multiplicity,
  made plan-expressible. The two load-bearing halves already exist: component
  executions are run-scoped (N runs of the same component per scope coexist as
  durable rows — 012's skeleton runs `group` twice over different facets) and
  consumption is by explicit fail-closed run reference (nothing reads "the
  latest"). What's missing: **(a) multi-reference fan-in** — every consumer
  today accepts exactly ONE execution per upstream kind (synthesise: one
  grouping/selection/characterisation; the reference shape generalises to a
  coherent *set* of run ids, cross-checked against the same chain by the
  transitive-resolution machinery 013 built); **(b) the capability-run
  entity + its compile surface** (the 010 run-model seam) — no persistent
  object yet expresses "this capability run = characterise ×1, group ×2
  [intervention, outcome], synthesise ×1 over all of it"; `run_harness` is a
  one-component dispatcher and the skeleton hand-sequences as the capability
  sub-agent's stand-in. Motivating instance: **multi-facet grouping references
  for synthesise** — the 013 live full-chain run referenced the
  intervention-facet grouping (0 groups, all 179 findings ungrouped) while the
  same project's outcome-facet grouping (13 healthy groups) was structurally
  invisible; both lenses feeding one synthesis means richer theme claims and
  spreads per facet family. **The grouping instance is DISSOLVED (task 022, owner's
  in-component fan-out shape)**: one `group` run clusters per facet across a directive
  facet LIST into ONE facet-keyed row, so the five recorded design questions (reference
  shape, share-one-extraction rule, facet-namespaced ids, per-facet
  `groups_unsectioned`, roll-up schema) were answered by construction — facet-qualified
  `facet:gNN` ids, per-facet residuals/`groups_unsectioned`, one `fk_synr_grouping`
  untouched (ADR 0018). The GENERAL fan-in seam — (a) multi-reference consumers beyond
  grouping and (b) the capability-run entity + compile surface — stays deferred as
  described above. **Update (task 024, 2026-07-16):** (b) the capability-run
  entity itself is now **DISCHARGED** (decision 2, see the Select-section entry
  above); its compile surface (a durable object expressing "this capability run
  = characterise ×1, group ×2, synthesise ×1") is not built — the walk row
  records identity/status, not composition. (a) multi-reference consumers
  beyond grouping stays open exactly as described.
- **Artefact capability-discriminator + versioning grain** — `synthesis_result` is the
  run-scoped roll-up pointing at its artefact; future capabilities mint artefacts into
  the same 001 substrate with their own roll-ups. The discriminator column and the
  versioning grain arrive with their first readers.

## LLM screen + classify (task 014 seams)

- **Classify-consensus voting** (contract rev 1.3) — screen got 3-rep consensus (decision
  10); classify runs single-call. Whether classify needs the same treatment is eval-gated:
  measure single-call error structure first.
- **Heterogeneous-model screening ensemble** (rev 1.3) — reps across model families instead
  of 3× one model; needs the Bedrock/routing seam (v3.0 is single-provider OpenAI).
- **Structured inclusion-criteria screening directive** (rev 1.2) — a plan-compile seam
  mirroring select's directive pattern: explicit inclusion/exclusion criteria compiled into
  the screening directive instead of free-text intent-as-data (the v3.0 surface).
- **Screen-confidence retrieval boost** (user, 2026-07-08; contract rev 1.8) — in
  no-selection runs `search_chunks` has no doc-level prior; `screen_decision_confidence`
  (meaningful since 014) is the natural directive-expressible boost. **Grammar pre-decided:
  clamped functional multiplier** — linear `lo + conf × (hi − lo)`, parameters bounded,
  product clamped [0.1, 10]; banding rejected (threshold cliffs); steerable-never-baked →
  directive column, never a standing prior; double-count guard where a selection reference
  already prices confidence in; stage-provenance aware (never mix stage-1/stage-2
  confidences in one multiplier without the `screen_stage` column). A **013-surface change —
  lands via its own gate**, not as screen work.
- **Concurrent-run hardening** — the stage-row insert's NOT-EXISTS + partial-unique-index
  pattern (contract M8) relies on v3.0's single-process/serial posture; concurrent screen
  runs of one scope could race it. Recorded, not hardened.
- **013 `lookup` vocabulary widening** — the synthesis `lookup` tool's closed vocabulary
  does not include screening rows, so in-loop sub-agents can't query either stage; a
  one-line 013-surface widening when a consumer wants it.
- **Demotion-asymmetry survivorship measurement** (decision 11 iv-b) — abstract-only docs
  are unejectable past stage 1 (no full text to confirm against), so stage-2 precision
  accrues only to text-available docs; measure the survivorship skew in the eval slice.
- **Screening/classification eval seam** (the eval slice's seed, all pointers recorded):
  LLM4SCREENLIT-style metrics (full confusion matrix · lost-evidence/recall · WSS ·
  WMCC · the deterministic stub as the non-LLM baseline) · the **V2 screening-eval
  baseline** (13,740 docs, recall 0.836 / precision 0.634 / WSS@95 0.187, committed in V2
  `backend/testing/evals/screening/`; must include hard corpora, where V2 recall fell to
  0.400) · the **stage-pair dataset by construction** (both stage rows persist on every
  deep run — stage-1 vs stage-2 label pairs are free) · the **stage-1 vs stage-2 estimator
  difference** (consensus probability vs single-rep self-report, rev 1.10) · the
  **unsure-at-0.5 calibration question** (rev 1.11: should a no-information doc sit at the
  corpus base rate instead of 0.5? — first calibration target) · the heat_pump
  manual-vs-automated study re-scoped as search/coverage-recall evidence for 015/016 (it
  measures document identity, not screening accuracy) · **live-model injection
  semantic-invariance eval** (014 review: the paired fixtures pin prompt *structure*; live
  behavioural invariance is probe-only today — fold into the injection metrics).
- **Classify-confidence threshold-gating** (rev 1.5, V2 `strength.py` precedent) —
  confidence is event-payload-only today; a gate that acts on it arrives with its first
  consumer.
- **Stage-2 windowing scale efficiency — DISCHARGED (task 016, decision 11: the
  pre-registered trigger fired).** `_load_stage2_docs` now hydrates only the chunk prefix the
  first window can read (per-snapshot streamed query, stop at the budget-crossing chunk);
  peak memory is bounded by window budgets + split-boundary slack, never corpus full-text
  size. Behaviour-preserving, test-pinned (byte-identical first-window payload + the
  prefix-hydration proof).

## Orchestrator (task 017 seams)

- **`_REGISTRY_COMPONENT_BY_STEP` simplification candidate — DISCHARGED
  (task 019).** Collapsed to the `registry_component_for()` one-liner; the
  startup parity assert is kept.

- **The LLM EB-expert capability agent** — the JIT directive-authoring expert
  sub-agent (system-prompted as an evidence-review expert; reads upstream
  outputs to author each component's directive; makes reasoned
  surface-vs-settle calls; carries domain expertise into a more cohesive
  artefact). Its drop-in seam is `runner.py::leg_directive(plan, step,
  upstream_state)` — v1 returns the composer's directive delta unchanged. Own
  slice, recommended post-eval (directive quality is unmeasurable before
  evals). Contract rev 2c, user + lead converged. **Still open after task 024
  (2026-07-16)** — the agent itself stays post-eval as pinned, but 024 built
  its walk-forward sockets (author-blind compile, `authored_by`/`decided_by`
  attribution, the authoring-seam protocol at the orchestrator watch + the
  `leg_directive` slot) so arrival is a backend swap; see the "EB-expert
  capability agent" entry in the Steering surface section below.
- **Plan-field ↔ chat-turn provenance** — v1 persists the approved plan
  object (`orchestration_plan` rows), not per-field conversation
  back-references; the planning transcript is ephemeral CLI state. The
  spec's provenance rule (plan-as-object) waits for the workspace cluster.
  017 review addendum: a steer-point reselect's plan version row carries
  attribution but no *pointer* to the commit-layer directive that motivated
  it (the substance lives in `selection_result.selection_provenance` —
  durable and reachable via the `plan.compiled` chain, confirmed as-designed
  per decision 4; a version row that names its cause would make the audit
  one hop shorter).
- **Resume-engine design requirement** — 017 ships per-component commits, no
  resume engine (re-run-from-top accepted for 017/018; contract decision 7).
  The engine's requirement recorded from the 2026 durable-execution
  consensus (rev 2.4b): checkpoint state serialization + an **idempotency
  key persisted before any interruption** so a resumed action runs exactly
  once.
- **Steering conversational half — PARTIALLY DISCHARGED (task 024, 2026-07-16).**
  Originally: narration voice (the demo's second posture) · `clarify`/`escalate`
  parking on durable signals · `agent_judgement_routed` residual events
  (require runtime agent discretion the deterministic runner lacks) · free-text
  steering → replanning · mid-run mode *suppression* rules. All stayed out of
  017 by contract (Out-of-scope); check-in content stayed deterministic renders.
  024 resolves three of these: **`agent_judgement_routed` residual events** ship
  in full (the orchestrator watch emits them for every triage/decision/authoring
  verdict, `decided_by: user | orchestrator | standing_default` attributed) ·
  **`clarify`/`escalate` parking on durable signals** ships as the watch's
  bias-to-escalate rule over the persisted trigger floor, event-backed · **free-text
  steering** ships as the router (fan-out compile across not-yet-run components,
  partial-compile-with-honest-refusal, confirm-before-apply) — but **not
  replanning**: the router never recomposes the chain (adds/removes components
  mid-run), which stays its own deferred surface (see "Free-text replanning" in
  the Steering surface section below). **Narration voice** and **mid-run mode
  *suppression* rules** are untouched and stay open.
- **Runner-visible token-usage aggregate** — as-built, every LLM backend
  discards `_usage` after Langfuse tracing, so 017's dev summary log
  carries wall-clocks only; per-component tokens are read in Langfuse. A
  runner-visible single-line usage aggregate needs a usage-return refactor —
  arrives with that refactor or the component-progress protocol (contract
  decision 11, rev 2.6). **Scheduled: 018 Phase A telemetry sweep** (usage-return
  refactor + durable per-component wall-clock/counts).
- **Component-name rename `screen`→`screen_abstract` / `screen_stage2`→`screen_full`
  — DISCHARGED (task 019).** Renamed, with a one-time data migration
  `b7f3d9a2c5e1` (owner decision 3); no read-side alias.
- **Direct plan editing on the plan pane** (user, 2026-07-10; **re-deferred past 025 —
  owner, 2026-07-20**) — editing the proposed plan directly (not only conversationally),
  with edits synced back to the planner conversation and a confirm-changes step before
  the run button arms. Considered for 025-web-app-foundation and deliberately held:
  conversational editing is demo-validated and sufficient for v1; the plan-patch grammar
  + the planner's acknowledgement turn are their own design surface. The conversational
  half stays the only editing path until then.

## Data model / evidence

- **`supersedes` edge on `source_snapshot`** — human-asserted pointer from a corrected re-upload
  to its predecessor; deferred until the re-upload UX is scoped. The schema shape (content-addressed
  snapshots without project_id) already supports it; no data migration needed.
- **Content-hash dedup for acquired cross-project snapshots** — the schema shape supports sharing
  (no `project_id` on `source_snapshot`); task 007 built **project-scoped** dedup only (three
  guards: `backend_record_id` · normalized DOI · content hash, preloaded in-memory per call).
  Cross-project snapshot reuse, **fuzzy near-dup matching** (title similarity — DOI-only
  cross-backend identity in v3.0), and **concurrent-run dedup hardening** (two simultaneous
  acquire runs for one project could double-insert past the in-memory preload; a DB-level guard
  is a gated schema change; v3.0 execution is single-process/serial — Codex adversarial finding,
  task 007) are the follow-ons.
- **LLM-as-judge grounding tier on `citation`** — `citation.verification_result` is set by the
  deterministic verbatim quote-presence check only; the full grounding tier classification
  (confident / uncertain / fabricated) is deferred to when a real inference provider lands.
- **Boundary-spanning quote → `citation_chunk` join table** — task 013 pins the interim
  shape within the approved schema (contract rev 8 B2): a boundary-spanning verified quote
  writes **one citation row per spanned chunk** (same annotation, same quote; exact span
  offsets on the annotation payload — the 011 anchor precedent). The join-table
  normalisation remains the recorded seam. (The 001 echo path's first-matching-chunk
  behaviour stands until that path is retired.)

- **`Library`** (curated cross-project collection: per-user → team/org) and **`Connected`**
  (auth'd departmental-repository ingest) — the public/acquired dedup slice is *un*-deferred; the
  curated collection + access layers are not. **Source-class lifecycles** stay collapsed to
  `origin`.
- **Source-document versioning lifecycle** beyond immutable snapshots + a human-asserted
  `supersedes` edge — diffing, upstream-change monitoring, automatic propagation.
- **Open-web `search` backend** (trust class: untrusted open web) — behind the same `search` verb,
  declaration-scoped, with mandatory injection screening; ingests as frozen chunks (no
  cite-the-live-web path).
- **Cross-project finding reuse** (sits next to the rejected global KG).
- **Editing UX** — human amendment is representable in provenance now; the editing *UX* is
  deferred to user testing.
- **Support-direction relations** (supports / caveats / contradicts) + user counter-evidence
  search.
- **Multi-question-project reuse seams (workspace-cluster design input, owner
  conversation, 2026-07-12)** — docs-only, no build. Project = a container for
  MULTIPLE EB questions (see `project-multi-question-intent.md`); three
  recorded reuse questions for when the workspace-cluster contract is drafted:
  **project-grain classify label reuse** — an extraction-memo-style seam
  (classify's per-(scope, source) result reused across questions in one
  project rather than re-run per question), which must respect the
  Unknown-resolution staged-result pattern (§ Evidence Base internals) rather
  than bypass it; **appraisal reuse keyed on `rubric_version`** — per-scope
  appraisal rows are a deliberate hedge for the plan-carried rubric seam
  (§ Evidence Base internals: Steerable / plan-carried appraisal rubric), so
  reuse must key on `rubric_version`, not assume one rubric per project; and
  **pool-wide per-question screening cost growth** — screening re-runs
  pool-wide per question (verified scope mechanics, 2026-07-12), so cost grows
  with the number of questions per project, a sizing input for the
  workspace-cluster contract.

## Execution / collaboration / ops

- **Per-lane test-DB partition (018 B2/C)** — concurrent `make verify` runs against the
  one shared test DB flake (migration round-trip + steering tests, psycopg INERROR);
  seen from worker lanes (B2/B4) and from a review-lane agent (step 7). Convention today:
  one suite runner at a time, stated in reviewer/worker briefs. If parallel suite runs
  become routine, give lanes separate DATABASE_URLs (disposable per-lane DBs) instead of
  policing serialization.

- **Harness failure-event write on an aborted transaction — DISCHARGED for the
  product path (task 017)** (013 review stack, 2026-07-08) — every `run_harness`
  node's exception handler appends the `component.failed` event on the same
  connection; a DB-error exception (constraint violation, driver error) leaves
  the transaction aborted, the event write itself fails, and no audit record
  survives. 013's synthesise node avoids the known case with a pre-write guard.
  Task 017's EB capability-runner closes the gap for the product path
  (`runner.py::_record_failure_backstop`: rollback first, `component.failed` +
  `run.failed` idempotently on a fresh transaction — same discharge as the
  task-012 entry above). Residual: `run_harness` driven directly outside the
  runner (the zero-egress `skeleton.py` smoke) retains the old behaviour; an
  in-harness fix remains a harness slice if that path ever matters.
- **Harness node generalisation** — `_run_scope_component`,
  `_run_characterise` and `_run_synthesise` share ~30 verbatim lines of
  started/lookup/not-found/completed bookkeeping, diverging only in the
  custom-failure branch (a documented deliberate copy). A fourth node of this
  shape is the trigger to parameterise `_run_scope_component` with a
  failure-payload hook instead of copying again.
- **Branch-level parallelism** — intra-run parallel branches with a check-in blocking only the
  dependent sub-graph; a dedicated durable workflow engine; durable timers. (Within-step
  data-parallel fan-out is **retained**, not deferred.)
- **Formal sign-off / clearance workflow**, **artefact-scoped permissions / full RBAC**,
  cross-project nudges.
- **Per-item sensitivity gates & egress control**, **private / self-host deployments** — return
  when a sensitivity label drives concrete behaviour (block / approve / generalise / route /
  private deploy).
- **Formal SLO/SLA, incident process, canaries, live drift monitors, product analytics**, and a
  committed **judge calibration scheme** (owned by the eval workstream; v3.0 only persists judge
  I/O for eval-readiness).
- **Time/cost estimate model** (the plan drives an estimate; the model is deferred — a coarse band
  suffices in v3.0). Sharpened (user, 2026-07-10): the eventual model is per-component roll-up,
  conditioned on corpus size and the plan's component set (search effort × analysis depth) —
  which needs to know which components scale with corpus size and which are near-invariant.
  **Data accrual starts in 018** (durable per-component wall-clock + in/out counts on every
  run); the model itself is eval-slice-or-later work over that accrued telemetry.
- **Forecast/prewarm extraction** — modelled only if built (no inert forecast object otherwise).
- **`structlog.contextvars.bind_contextvars` for ambient run/project correlation —
  DISCHARGED (task 019).** Bound once per component execution at `run_harness`
  (`bound_contextvars` context manager), instead of threading `project_id`/`run_id`
  kwargs through every call site. `exc_info` renderers (`dict_tracebacks` for JSON,
  `format_exc_info` for console) were added to the processor chain so
  `exc_info=True` now carries type/traceback.

## Codebase health (task 023 seams)

- **4× ThreadPoolExecutor fan-out consolidation** — extract/screen(×2)/classify each
  hand-roll the submit→wait→collect→retry shape; one `fan_out_with_retry` would save ~60
  lines but the per-site diffs are subtle (error taxonomy, budget hooks). Excluded from
  023's behaviour-preserving scope by contract; take it when one of the four next changes
  for a product reason.
- **Search-as-shared-tool layer** (owner ruling, 2026-07-14) — the spec classes search as
  a universal core tool, but no incoming capability searches; they read the EB corpus.
  Extract a `tools/`-style search layer only when a web-search capability or a new data
  source lands. Until then search lives in `evidence_base/sourcing/`.
- **Five-facet group fan-out** (023 optimisation lane #1, high impact on deep runs) — the
  5 facet pipelines in `group` are verified order-independent, but claim-theme facets read
  via a shared non-thread-safe Connection. Safe shape: hoist per-facet conn reads before a
  pure-worker ThreadPoolExecutor region (mirror extract's fan-out). Candidate to ride the
  eval slice if deep-run wall-time hurts throughput; stacks with the 4-wide assignment
  fan-out 023 shipped (WP10a).
- **Embeddings batch-slice parallelism** (023 optimisation lane #4, low) — slices are
  independent but share the conn; not smallest-diff to do safely. Note, don't rush.
- **Test consolidations 3–5** (023 lane 4) — IOF record-factory twin beside
  `make_icf_wire_record` (~80–100 lines), shared fake-Langfuse (~50), `capturing_fetch`
  factory in test_search_live (~60). Separable; take with the next test-heavy slice.
- **`synthesis_prompts_v6` deletion** — KEEP ruling holds only through the eval slice
  (frozen cost baseline); delete in the first post-eval cleanup.
- **`run_harness(provider=…)` kwarg** — zero component readers post-echo; removal ripples
  into every caller. Retire alongside the inference-seam decisions at Bedrock, when the
  routing seam is touched anyway.
- **`core/tracing.py` EB-domain score renderers** — tracing imports
  `evidence_base.corpus.theme_grouping` + finding PROFILE_IDs for its `*_score_summary`
  functions; a core→capability edge the regroup made visible. Relocate renderers into
  their phase modules (or invert via injection) in a slice that touches tracing.
- **Per-lane test-DB partition — RECURRENCE (023)** — the 018 entry above fired twice in
  023's build: parallel lane done-checks and the orchestrate smoke both left committed
  rows that break migration-roundtrip downgrades across sessions. 023's mitigations:
  serial gate re-runs + dropdb/createdb resets + the smoke recipe
  (`docs/knowledge/orchestrate-stub-smoke.md`). If parallel lanes stay routine, promote
  this to per-lane disposable DATABASE_URLs.
- **`quote_verify` generic-matcher split (owner ruling, 2026-07-15: leave as-is, seam
  recorded)** — `extract/quote_verify.py` is one engine with two kinds of content: the
  generic `qv_v1` matcher substrate (`BasisText`/`QuoteMatcher`/`build_basis`) and the
  extract-specific IOF/ICF field rules + grain gates that dominate the module. Synthesis
  reaches back for exactly the matcher trio (`synthesise.py`) so both checkpoints share
  one normalisation regime and offset convention — a clean downstream-imports-upstream
  edge, verified acyclic. Split the matcher trio into `core/` (the `hashing.py` pattern)
  only if a third consumer of the matcher appears; purity alone doesn't pay for the
  extra module.
- **Bedrock security-pass riders (023 review stack, security lane)** — two diff-scoped
  observations routed to the deferred whole-repo security pass: (1) the untrusted-input
  parsers `lxml` and `trafilatura` have floors but no ceilings — consider the `<N+1`
  treatment the product-egress SDK already gets, since a lock regen crossing a major on
  an HTML parser is a silent behaviour change on hostile input; (2) `FixtureFetcher`'s
  manifest-basename traversal guard is an `assert` (vanishes under `python -O`) —
  dev/test-only surface today, should become a `ValueError`.
- **Monorepo hoist: `backend/` (owner layout intent, 2026-07-14; amended 2026-07-20:
  `frontend/`, no dash — DISCHARGED, 025-web-app-foundation A.2, 2026-07-21).** The
  frontend lands at `frontend/`, the CDK will land at `infra/` (the reason 023's
  shared-layer package is `core/`, not `infra/` — ADR 0019). The whole Python project
  (`backend/pyproject.toml`, `backend/src/`, `backend/tests/`, `backend/alembic/`,
  `backend/Makefile`) has hoisted into `backend/` as a sibling of `frontend/` and
  `infra/`. The `policy_atlas` import name is untouched — src-layout made the hoist
  import-neutral; the cost was tooling paths only (CI working-directory, Docker
  contexts, CDK references, doc links).
- **Per-query source provenance (demo carry-back, 2026-07-15)** — the search fan-out is
  already fully audited at the query grain (`search.executed` events persist query text,
  backend, filters, origin and result count), but `source.acquired` /
  `project_source_snapshot` never record *which query surfaced the source*. Two
  consequences: per-query relevance ("this query surfaced 12 sources, 5 screened
  relevant") is underivable, and any user-facing search-audit surface can only attribute
  relevance per backend. Fix is in acquire: stamp acquired sources with the surfacing
  query/queries (a set — multi-query dedupe means one source can arrive via several).
  Pays off for search-loop tuning and for the demo/web-app search cards.

## Steering surface (task 024 seams)

Recorded per the annex's "Still OUT, even in the big slice" list
(`docs/tasks/024-steering-surface/steerability-refinement.md`) plus seams the
build itself surfaced. 024 shipped the P1–P4 steer-point lattice (search
exception · evidence-base coverage · deepening selection · the synthesis
shape), the four delegation-posture modes + decider dial, the orchestrator
watch (triage/decide/route, two-tier information model), the router (free-text
→ fan-out compile), guidance channels B1/B3/B5, structured keys
D1/D3/D5/D6/D7/D8/D9, and the two re-run modes (additive/replacement) as
first-class vocabulary. What follows is what it deliberately left out.

- **B4 global synthesis guidance — HELD (2026-07-16).** Global writing-intent
  steering ("write for a technical audience", "keep it plain-language") was
  scoped as a guidance channel symmetric with B1/B3/B5, then held at owner
  review: it risks two overlapping voice levers fighting each other ahead of
  the audience-framing pair design (see `target-users.md` memory). Global
  writing intents route through the shipped per-section `focus` fan-out +
  evidence-emphasis boosts meanwhile. Demand meter: refusal events on
  global-voice free-text asks (the router's honest-remainder mechanism) —
  a spike is the trigger to design the pair together.
- **Directive-level tag-boost vocabulary (D4) — dropped to a named seam
  (2026-07-16).** Narrows the retrieval-boost-v2 seam recorded above (§ Live
  search / depth-graded loop) rather than replacing it: the open tag layer is
  disparate at live scale (the tag-consolidation trigger, § Characterise,
  records exactly this fragmentation), so an exact-match boost over a
  fragmented vocabulary would boost a sliver and silently distort retrieval.
  The closed-vocabulary cases users actually want are already boostable
  columns (`primary_evidence_type`, appraisal tiers). The boost grammar keeps
  *accepting* tags (built, clamped, `unmatched_boosts` stays honest) but
  nothing advertises or authors them; the router steers tag-ish intents to
  type/tier boosts instead. Seam: tag boosts return after tag consolidation +
  hybrid matching over the open layer.
- **Vetting steer of any kind + judge steering — FULLY OUT (owner, 2026-07-16).**
  Integrity surfaces: users must not instruct their own verifier. No binary,
  no retry action, no dial on the vetter or the grounding judge this slice —
  vetter/judge behaviour stays entirely fixed. `vetting_failed` spikes remain
  a floor *trigger only*: the user is told and steers other levers in
  response, never the vetter itself.
- **Classify steering — OUT (2026-07-16).** Classify is factual typing (closed
  9-value list + provider priors, § LLM screen + classify); the substantive
  intent behind a classify-shaped ask lands downstream in the appraisal
  rubric (D1, shipped this slice) rather than as a classify-time steer.
- **Dual-view coverage / the source-evidence policy object — carried forward
  unchanged (2026-07-16).** Still the 017-decision-9 deferral (§ Characterise,
  "Dual-view coverage" above): a data-model design of its own, not steering
  machinery. The "policy unmeetable above-bar" trigger stays parked with it;
  024's trigger floor does not include it.
- **Mid-component steering** (between deep-search rounds, between synthesis
  sections) **— OUT (2026-07-16).** Requires the durable-resume engine
  (§ Orchestrator task-017 seams, "Resume-engine design requirement"); the
  boundary-only pause model holds. 024's segment re-entry generalises the
  *boundary* re-run (bounded forward re-walk, one cycle per boundary), never
  an in-flight pause mid-component.
- **Free-text replanning — OUT (2026-07-16).** The 024 router compiles free
  text into deltas across not-yet-run components, but never recomposes the
  chain (adds/removes components mid-run beyond the existing nudge
  mechanics). Planner re-entry is its own surface; the nudge + mode change
  remain the only composition levers. The watch inherits the same limit by
  construction — it adjusts within the composed chain, never recomposes it.
- **Query-set pre-approval — OUT (2026-07-16).** Approving the generated
  query set before it executes needs an in-component pause (query generation
  happens inside acquire's own run). The iterative equivalent shipped
  instead: B1 `search.guidance` in, executed queries visible at P1/P2
  (`search.executed` events), targeted additive re-search after via P2's
  segment re-entry.
- **The EB-expert capability agent — still post-eval (2026-07-16); three
  sockets shipped.** Cross-refs the entry above (§ Orchestrator task-017
  seams). 024 builds the walk-forward sockets so the eventual arrival is a
  backend swap, not surgery: (1) author-blind compile — already the design
  for every channel/key; (2) `authored_by`/`decided_by` attribution on every
  steering event — the history projection is unchanged when the author
  changes; (3) the authoring seam as a protocol — "boundary state + intent →
  suggested responses / decision" — the orchestrator watch implements it
  today; post-eval the EB-expert plugs in behind it at the runner's existing
  `leg_directive` slot. Authority order is fixed regardless of author: user >
  declared rules > orchestrator.
- **Tier-1 (routine-boundary) triage tooling — deferred (2026-07-16).**
  Bounded read-only tool pulls (`lookup`, `query_findings`, cap ~4) ship at
  decision points (P1–P4 + watch escalations — tier 2); tooling for tier-1
  push-only triage stays out — cost explodes for little value at routine-
  boundary volume. Insufficient-context escalations (bias-to-escalate after
  the cap) are the demand meter; a spike there is the trigger to reconsider.
- **Transcript persistence / turn tables — re-homed to 025 (owner,
  2026-07-16).** 024 ships the anchors only: `session_id` on `capability_run`
  (nullable), verbatim `user_text` on every steering event. Provider-side
  conversation state (OpenAI Responses, Bedrock sessions) stays forbidden —
  the record lives in our store (018 standing constraint; audit/FOI/
  portability). 025's co-pilot Q&A needs persisted per-user sessions
  ("multiple persisted sessions; browse previous ones") — the transcript
  companion store (per-user/per-project turn table, session/`capability_run`
  linkage, window-plus-recall context assembly) lands there.
- **Build-discovered seams (024 build, 2026-07-16)** — surfaced mid-build,
  not pre-registered in the annex:
  - **Live DB-backed read executors for watch deliberation** — the runner
    passes `read_tools=None` at both fallback-deliberation call sites
    (`runner.py:3243`, `runner.py:3626`); the tier-2 `lookup`/`query_findings`
    tool loop is wired but has no live executor behind it yet. Escalation
    volume (insufficient-context bias-to-escalate) is the demand meter for
    building one.
  - **Segment-reentry re-presentation boundary runs unwatched** — the
    one-cycle re-presentation after an additive segment re-entry
    (`_run_plan_segment_reentry`, `runner.py:2982`) calls
    `_handle_after_component_boundary` without an `orchestrator` argument
    (defaults `None`); that specific re-presentation is structural-floor-only,
    no watch judgement. Named, not yet closed.
  - **D3 repeat-refresh fingerprint collision** — the refresh-tagged
    fingerprint (`extraction.refresh`) is deterministic, so a second identical
    refresh on the same class collides with the first and is a no-op rather
    than a fresh re-extract. Supersession-style plumbing (mirroring the
    `screen_generation` pattern) is the fix if a second refresh is ever wanted.
  - **Pending-select fine keys — overlay-carried since the review stack
    (2026-07-16).** The build shipped these rejected fail-closed at P2; the
    review stack found the compile grammar accepted them while the plan
    mapper raised post-confirmation (MAJOR, fixed in-stack): `select` is now
    in `_MIXED_COMMIT_LAYER_KEYS` (plan-mappable `budget`; commit-layer
    `strata_scope`/`exclude_ids`/`weight_emphasis`/`must_include_ids`/
    `boosts`/`priority_strata` overlay to the run).
  - **P2 `stage2_toggle` omitted** — turning stage-2 full-text screening
    on/off mid-run is a chain-composition change the plan grammar can't
    express (composition is fixed at plan-compile time); recorded, not built.
  - **Per-dropped-stratum preview titles need the theme-membership join** —
    P3's selection preview can name counts for a dropped stratum but not
    human-readable theme names without joining through group's
    theme-membership table; `p3_bundle` surfaces names+counts+notable digests
    where the join is cheap, digests-only where it isn't.
  - ~~Mixed-grammar overlay for select~~ — **discharged by the review stack
    (2026-07-16)**: select joined the mixed-grammar split (see the
    pending-select entry above).
  - **Deliberation `needs_tool` structured field is primary** — the watch's
    fallback tool-call loop reads the structured `needs_tool`/`needs_arguments`
    wire fields (`orchestrator_backend.py:578`, `orchestrator_prompt.py:229`)
    first; the legacy JSON-in-`needs` free-text fallback is retained for
    backward parse tolerance, not the primary path.

- **Review-stack seams (024 step 7, 2026-07-16)** — surfaced by the review
  lanes, adjudicated as deferrals (each has a reason; fixes applied in-stack
  are NOT listed here — see verification.md § Review findings):
  - **Live router compile robustness** — in the pinned live runs ~3 of 6
    free-text steers mis-compiled (malformed `acquire` delta on an
    expressible P2 additive re-search; a P4 sections edit mis-labelled
    `replacement`); every failure was caught fail-closed (refusal, no
    invalid apply) but compile quality is below the surface's ambition.
    The delta render at the confirm gate (review fix) is the mitigation;
    router prompt iteration belongs to the eval slice, where compile
    fidelity can be measured, not vibed.
  - **Classify/appraise collapse triggers are not generation-scoped** —
    after a criteria re-screen demotes docs at a new generation, their old
    classification/appraisal rows still count in the trigger denominators
    (`steering_triggers.py:233,296` read the result tables directly). ADR
    0022 names re-classify/re-appraise generation-awareness as future work;
    the honest fix is a join through `effective_screen_rows` when those
    components gain generation semantics.
  - **Re-screen quorum-failure falls back to the prior generation's verdict
    unflagged** — `effective_screen_rows` excludes `failed`, so a doc whose
    gen-N re-screen failed silently keeps its gen-N−1 verdict: a criteria
    mix inside one effective set with no marker. Needs a flag class (or a
    bundle note) when effective rows span generations.
  - **Router-reachable `screen_full` re-screen is untested** — the fixed P2
    catalog never emits `{"stage": 2, "rescreen": true}` but a router
    replacement fragment can; the same-generation stage-2 collision then
    halts the whole batch loudly (`ScreenSupersessionError`, by design —
    the reason now persists on the `component.failed` event, review fix).
    Pin a test + decide the partial-batch semantics if this path is ever
    advertised.
  - **Structural consolidation sweep (post-merge slice candidate)** — the
    review confirmed 12 duplication/altitude sites that stay correct today
    but must be edited in lockstep: the attempt/retry loop ×3
    (`runner.py:792/2532/2796`), apply-path state reconstruction ×3
    (`runner.py:2324/2399/2643`), the before/after boundary-handler twins
    (`runner.py:1027/1216`), the segment-reentry runner twins
    (`runner.py:2919/3036`), quorum trigger stage blocks
    (`steering_triggers.py:399`), segment-reentry compile duplication
    (`steering.py:1186`), the replacement-validation ladder vs
    `REPLACEMENT_RERUN_CONTEXT_KEYS` (+ the diverging noun table,
    `steering.py:1561-1599/1266`), `_reference_kwargs` vs
    `REPLACEMENT_RERUNS` (`runner.py:4094`), the `floor_triggers` dispatch
    ladder (`steering_triggers.py:573`), `selection_run_id` bespoke
    threading, `_doc_metadata` title fallback ×3, and per-boundary double
    `engine.connect()`. Deferred as one refactor slice rather than churning
    a 19k-line surface mid-review; the fresh grammar/behaviour tests make
    the later refactor safe.
  - **Event-payload display strings persist NUL-scrubbed only** — the full
    control/format-char defence lives at the CLI output seam
    (`_strip_control`, now incl. Cf); the 025 web renderer must scrub on
    render or the persistence layer should adopt `sanitize_prompt_field`
    for model-authored display strings (security-lane recommendation).
  - **Watch `choose_option` id never resolved against the canonical menu**
    — a delta-less `choose_option` silently proceeds; grammar fencing makes
    it safe, but resolving the id (or renaming the event action) would make
    provenance more truthful (security-lane recommendation).
  - **CLI re-prints the stale check-in line on every re-presentation** —
    cosmetic duplicate "component: succeeded" lines in the pause loop
    (visible in the live transcripts); tidy with the next CLI-surface
    slice.

## Web app (task 025 seams)

- **Cross-instance steering & live tail** (025 contract, digest §1.3) — the deployment
  posture is one API instance / one worker process: pause-unblocking, the live SSE tail
  and the ephemeral tick channel are process-local; durable replay covers reconstruction,
  not cross-instance live delivery. Scale-out needs Postgres LISTEN/NOTIFY (or pub-sub)
  for tail fan-out and answer delivery — the infra/CDK slice's seam. The continuation
  dispatch path is deliberately queue-shaped so broker-backed workers (Celery/RQ) slot in
  behind it later without a reshape.
- **Designed component-progress protocol** (RETRO §4.10, 025 contract 🟡) — 025 ships
  stage-grain durable events plus a minimal ephemeral tick channel
  (`policy_atlas.core.liveness`, best-effort publish points in the search/fetch
  transports). A *designed* per-component progress protocol (typed progress shapes,
  coverage of every component, durable where warranted) is still open.
- **Cursor pagination migration path** (025 API pins) — offset + `total_items` is the
  deliberate v1 shape at per-project scale; if cross-project or unbounded-growth listings
  appear, add an opaque `cursor` param alongside (additive, never a breaking reshape).
- **Hard purge** (025 contract 🟡) — delete = idempotent archive (rows retained per the
  audit/FOI/portability constraint). A real purge (rows, snapshots, event history) is its
  own gated seam.
- **Per-run provider-rate-limit fairness** (owner, 2026-07-21) — provider limits are
  shared across concurrent runs; the executing-walk bound is the v1 fairness mitigation.
  Recorded non-goal until real contention shows up.
- **Plan-field↔turn provenance** (025 adversarial finding 7) — ephemeral planner prose is
  not execution-bearing for continuation, but which conversation turn produced which plan
  field remains an acknowledged loss until the transcript store (026) / workspace-cluster.
- **NULL-owner pre-025 projects** (migration b5f1a3d7e9c2) — rows predating ownership keep
  `owner_user_id NULL` and are intentionally inaccessible via the strictly owner-scoped
  API (the dev DB's two live-run projects are the known case). Recovery is a documented
  manual UPDATE at the DB; an admin/ownership-claim surface is deliberately unbuilt.
- **`CitationOut.source_id`** (025 live check, 2026-07-21) — **CLOSED at 027 owner
  feedback (2026-07-29)**: `source_id` (+ `grounding_rationale`) added to `CitationOut`;
  citation→dossier opens are id-keyed (title stays as the legacy path for references
  and theme members). The sibling display bug — full-text-grounded citations showing
  locator URLs — was the envelope/text-snapshot authority split, fixed at the read
  model (envelope is the sole bibliographic authority; references keyed by document).
- **Post-re-auth return-to renders the landing route** (026 live check, 2026-07-28) —
  the OIDC sign-in callback restores the stashed path via `history.replaceState`, which
  react-router never observes: after any auth round-trip the URL may show the deep link
  while the landing route renders. Cosmetic (a reload or click recovers); fix is a
  router-level navigate in `onSigninCallback` — next frontend-touching slice.
  (A second facet — a persistent OIDC callback error mounting the shell tokenless,
  flagged by the 026 review's Codex lane — bit the owner live the same day and was
  **fixed in-slice**: on error the provider renders a "Sign in again" retry that
  strips consumed `code`/`state` params before stashing the return path; the shell
  never mounts. Only the router-navigate restoration above remains open.)
- **Rename/archive controls in the UI** (025 live check) — the PATCH/archive mutations
  exist, are authz-tested and envelope-conformant; no view exposes them yet. Ingest also
  presents under the acquire stage label ("Searching sources" while reading documents) —
  both are workspace-surface polish for the next frontend-touching slice.

## Infra deployment (task 026 seams)

- **No deploy lock** (026 review, Codex adversarial, 2026-07-28) — `scripts/deploy.sh`
  assumes one operator: two concurrent runs can interleave stop→migrate→scale (parallel
  Alembic runs, one deploy booting the API mid-migration of the other). Acceptable while
  deploys are one team member on staging (DEPLOYMENT.md § 1 states the rule); a real
  lock (S3 conditional-put lease or DynamoDB lock, plus an Alembic advisory lock) is the
  seam when a second operator or CI-driven deploys appear.

## Frontend uplift (task 027 seams)

- **025 "draft conversation is lost on restart" pin — DISCHARGED** (027 strand 12,
  2026-07-29): the planning conversation persists in `planning_transcript` (durable
  idempotency, rehydration, restart-surviving thread — live-checked). No backfill:
  pre-027 projects have zero turn rows.
- **Co-pilot Q&A UI seam** — multi-thread chat, Chats library, per-thread artifact
  context (PR #35 adjudication): the transcript schema is deliberately single-table/
  planning-only so the co-pilot slice brings its own thread/context model; the rail is
  single-thread until then. Q&A needs a lead-authored prompt surface (own slice).
- **Workspace-cluster IA seam** — artifact gallery / capability picker / multi-artifact
  IA / per-artifact "Cited in" (PR #35): needs run/artifact-scoped read models. 027's
  journey/evidence components are IA-agnostic and re-mount under it unchanged.
- **Steering boundary re-pause under FREQUENT mode** (027 live check, 2026-07-29) —
  **DISCHARGED same day** (owner-directed, commit 4c4a65d): continuation records the
  parked pause's boundary+component and a continue/adjust/mode_change resume of a
  decided before-boundary no longer re-presents it (live-path parity; parity tests in
  test_continuation_parity.py). The original loop: answer → continuation → re-evaluate
  → pause again, one orchestrator call per cycle (event seq 364–388, project
  5e08e143…).
- **Multi-instance turn lock** — the planning 409 primitive is a process-local lock
  registry by design (one-instance posture); LISTEN/NOTIFY stays the 025 scale-out seam.
- **Live per-backend search counts** (D‑1 rev 2) — `search.executed` events commit with
  the acquire component, so mid-stage per-backend counts genuinely cannot stream yet;
  the journey shows tick-based activity until stage completion. Revisit if tick payloads
  ever widen (behaviour change, own gate).
- **Print/share/export CTA** — the evidence-base print stylesheet ships; the share/export
  product seam stays deferred and undischarged.
- **Project-wide decision-log scoping** (read-model-additions.md rev 2 [D-2], recorded
  here per its own commitment): the decisions read model derives from every run in the
  project; the journey card says "attributed across this project". Run-scoped decision
  views wait on the workspace-cluster IA's run-scoped read models (above).
- **`DecisionOut.detail` server-side narrowing** (read-model-additions.md rev 2 [D-4],
  API hygiene): `detail` passes the raw event payload through; the client renders only
  allowlisted keys. Narrow the server projection when a second consumer appears.
- **Orphaned `component.started` on hard process death** (027 review, 2026-07-29): the
  runner commits `component.started` in a standalone transaction before opening the
  component transaction; a SIGKILL in that gap leaves the pair unclosed on the `runs`
  row (walk-level recovery via the continuation startup sweep still marks the
  capability run interrupted, so the user-facing state is honest). A runs-row
  reconciliation sweep is the seam if that trail ever needs to be self-consistent.
- **Filter pagination materialises the collection** (027 C.2, by design): evidence and
  findings pages derive the full project collection per request for collection-true
  `total_items` (funnel precedent), so a page walk is O(N) per page. Fine at
  single-project scale; revisit with SQL-level filters if project corpora grow 10×.
