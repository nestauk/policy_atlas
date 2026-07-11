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
- **`implementation_context_finding`** — the second reusable finding schema (mechanisms, barriers,
  implementation conditions); cross-schema linkage is reference-mediated via `group`. Extract-side
  note (task 011): V2's CFIR implementation-profile field definitions (cost/staffing/complexity +
  the inner-setting rule) are recorded design input for this schema; no field of it entered
  `intervention_outcome_finding`.
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
  decision 8; OpenAlex keywords deliberately exited the prompt). Still open:
  `is_retracted` retained-but-unread — a 018-gate proposal to surface it in the writer
  envelope was **struck (user, 2026-07-10): its likely home is earlier in the pipeline,
  probably screening** (a retracted document arguably should not screen in at all) —
  that is an eligibility change with flag-not-drop implications, so it needs its own
  gate when taken up; the appraisal-second-pass visible-flag reading also remains open.
  Non-English handling beyond English-first title selection still open.

## Live search / depth-graded loop (task 015 seams)

Recorded per contract § Verification (rev 3.14 list) + the 015 review stack.

- **Retrieval-boost grammar v2** — rev 3.9's named companion slice: tag-based retrieval
  scoping + the 014 screen-confidence multiplier (grammar pre-decided in the task-014
  section above), one 013-surface slice; sequence before 017 or alongside it.
  **Adjudicated at the 017 contract gate (rev 2d, user call, 2026-07-10): stays
  deferred, eval-gated via its own 013-surface slice; 017 composes with the v1
  grammar as-built.**
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
  tags/record — bounds sized on fixtures now genuinely bind.)
- **Caching (cache-before-throttle)** — declined at plan; live 429s arrive in bursts right
  after a fan-out (observed: OpenAlex rate-limited the immediately-following run in the
  same process), so a response cache pays for itself before a smarter throttle does.
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
  **coverage-record stop-condition grain** (review stack, three lanes convergent): a clean
  rapid completion and a wall-clock breach both persist `breadth_truncated`, and the
  deep-thin overlay hides the raw stop value — the per-round facts live only in
  events/logs; a richer stop/attribution vocabulary is a one-line CHECK migration cousin.
- **Rev-3.10 loop seams** — calibrated recall estimate (Chao capture-recapture /
  Undermind exponential-saturation fit → a user-facing "estimated % of relevant found" on
  the coverage record); sliding-window Thompson-sampling arm allocation (eval-gated, must
  beat round-robin); RCS-style abstract compression before screen (only if screen tokens
  bind the wall-clock); best-of-N query selection.
- **Study-geography extraction field** (rev 3.2, user) — no search API supplies study
  geography; an extraction-schema gate joining the 010 selection-diversity seam,
  characterise's post-extraction coverage dimensions and the Transferability capability.
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
- **Review-stack cleanup candidates** (015 step 7, recorded not ridden): collapse
  `acquire_sources`' legacy no-executed-calls branch into the executed-calls path; unify
  the two wire-validator families in `search_loop.py` when the filter grammar next grows;
  hoist the duplicated `oa_record`/scripted-generation test doubles into `tests/helpers.py`.

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
- **Concurrent-run write guard** — eligibility selection takes no row locks and final writes
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
  eval coverage, not as a rider); (b) future read surfaces (context/dossier views — the
  web-app slice). Cheaper mitigation than (and complementary to) the docling escalation
  above. Trigger: live corpora making collapsed chunks common, or judge token-cost
  observations.
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
  `retrieve`; v1 repair is reword-down over already-gathered evidence only), and
  **`_load_findings` batch loading** (013 review stack: one basis query per distinct
  source snapshot — a confirmed N+1, harmless at v1 corpus scale, batch it when
  corpus-scale work lands here).
- **Contextual retrieval, late chunking, exact-token budgeting, semantic re-chunking** —
  retrieval-eval seams on the embedding-unit layer (contract decision 2, rev-8 research).
  The unit policy is versioned (`embedding_unit_policy_v1`) so any of these lands as a new
  co-existing policy, not a rewrite.
- **Embed-pass live robustness** — fixture-scale is single-batch; pre-registered for real
  corpora: rate-limit backoff under real 429s (the SDK retries transient failures at
  `max_retries=2`, so the HTTP ceiling is (1+retries)× the logical call budget — comment at
  the client seam), batch-failure isolation granularity (one bad unit currently fails every
  chunk sharing its 128-unit API batch — transient over-reporting only, failed chunks
  re-embed next pass; split-on-failure lands here), and concurrent multi-batch behaviour at
  n ≫ batch (review adjudication, 2026-07-06).
- **Very-large-corpus grouping** — discovery currently reads all titles+abstracts in one
  call; the scale seam is discovery-sampling and/or embedding-based clustering over the
  landed chunk vectors (contract decision 4). Assignment already scales (batched,
  concurrent, budget-enforced). **Live-corpus robustness observations (015 live check —
  the first component to wobble when inputs got real):** a 206-doc corpus produced an
  `APITimeoutError` batch failure and an 85-doc corpus a double `InvalidDiscoveryOutput`
  rejection before a ~60-doc pass succeeded; retry caps and batch sizes are eval-slice
  calibration targets. Compounding gap (015 review, the 013 corollary):
  `_discover_themes` discards the validator's rejection detail — only `error_type`
  reaches the logs, so the rejection *reason* is diagnosable solely from Langfuse traces;
  persist/log `str(exc)` when this component is next touched.
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
- **Steering modes / landscape→synthesis steer-point pause** — plan-as-object machinery;
  the payload it relays (the structured landscape summary in `component.completed`) ships
  now (contract decision 8). The deepening-selection steer-point's read surface followed
  in task 010 (see the Select section).
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

- **Deepening-selection steer-point pause** — the mode-governed pause (Frequent/Moderate/
  Minimal routing, escalation UX) is plan-as-object machinery; its **read surface shipped in
  010**: the bidirectional rationale (always logged) and the computed trigger flags —
  `large_stratum_excluded`, `priority_stratum_excluded` (the hardest: a user-nominated
  stratum with zero selections), `must_include_conflict`, `thin_base` (honestly
  stub-constant until the LLM screen tool lands), `thin_full_text` (extraction-shaping).
  The pause slice reads these flags; no new signal computation needed.
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
- **Capability-run entity** — a durable run spanning components (today one run = one
  component execution; the chain order lives only in `skeleton.py`, the agent's stand-in).
  The recorded Langfuse detached-trace warts (009's executor threads; 010's `rank:batch`
  generation spans) are early symptoms of this gap; fix belongs here, not per-component.
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
- **Suite-wide socket deny** (010 security-lane note) — per-test socket-deny helpers now
  exist three times (008/009/010 patterns); `pytest-socket` (deny by default, allowlist
  the DB host) is the structural defense-in-depth upgrade.

## Extract / findings layer (task 011 seams)

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
- **Mixed/unclear findings are first-class — requirement carried forward** — V2 extracted
  `mixed`/`unclear` effect directions and then aggregation silently zeroed them;
  flag-not-drop must survive the whole deep chain: `group` and `synthesise` must carry
  these findings, never discard them at aggregation.
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
  Codex) — `primary_evidence_type` conditions the extraction prompt, yet the memo keys on
  (project, basis snapshot, fingerprint) only and the record does not store the evidence
  type used. Unreachable today: classification is insert-once per (scope, doc) and the
  skeleton orders classify before extract — the only trigger is a hand-rolled plan that
  extracts *before* classifying (docs extract as "Unclassified" and memo-reuse after
  classification lands). If such plans become supported, record the evidence type on
  `source_extraction_record` and make memo hits require a match.
- **Per-run window/call ceiling** (011 review, security) — the enforced call budget is
  `windows × (1 + retry_cap)`, which scales with document length; there is no absolute
  per-run cap, so a pathological oversized corpus drives spend linearly ("within
  budget"). Bounded today by `select`'s budget (the designed cost control) and the
  fixture corpus. If arbitrary corpora land, add an absolute window ceiling as a
  fingerprint component with a per-doc `window_cap_exceeded` failure reason.
- **Prompt envelope fencing** (011 review, security) — segment text enters the prompt as
  id-keyed JSON data records, but the envelope title/abstract are interpolated inline in
  the user template, so a hostile abstract can structurally spoof the template around
  them (impact bounded: wrong findings for its own document, quotes still
  verified-or-flagged). Fence the envelope as a JSON data object at the next
  `extract_iof_v1` version bump — prompt changes are eval-blind until the
  extraction-quality evals exist, so this deliberately does not ride the review phase.
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
- **Cross-schema reference-mediated linkage** — activates with
  `implementation_context_finding` (EB internals entry): the shared source-named
  vocabulary means a facet group's member values can link findings across schemas by
  reference. 012 ships the design property (source-named values, run-referenced
  groupings), no linkage machinery.
- **Re-grouping / steering UX** — a different facet is simply a new run with a different
  directive (shipped semantics); mode-governed steer-points around grouping (pause,
  re-group, facet-switch UX) are plan-as-object machinery at the standing steering seam.
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
- **Id-carrying repair schema** (013 review stack, 2026-07-08) — repair
  replacements bind to failing claims positionally; the prompt instructs same
  order and count mismatches flag `repair_count_mismatch`, but a reordering
  backend would silently misbind claim ids. Candidate: replacements carry the
  failing claim's id in the emission schema (a versioned prompt-surface
  change), validated against the failing set.
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
  spreads per facet family. Design questions for the flow-back: reference
  shape (list vs per-facet named refs), the all-groupings-share-one-extraction
  consistency rule, facet-namespacing of directive `group_ids` (group ids are
  labels — facets can collide), per-facet `groups_unsectioned`, and the
  roll-up column → list/join-table (schema gate). v3.0 stays serial (branch
  parallelism is its own seam) — "concurrent" facets initially means cheap
  back-to-back runs. Adjudicate in the next design conversation alongside the
  eval-slice sequencing.
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

- **The LLM EB-expert capability agent** — the JIT directive-authoring expert
  sub-agent (system-prompted as an evidence-review expert; reads upstream
  outputs to author each component's directive; makes reasoned
  surface-vs-settle calls; carries domain expertise into a more cohesive
  artefact). Its drop-in seam is `runner.py::leg_directive(plan, step,
  upstream_state)` — v1 returns the composer's directive delta unchanged. Own
  slice, recommended post-eval (directive quality is unmeasurable before
  evals). Contract rev 2c, user + lead converged.
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
- **Steering conversational half** — narration voice (the demo's second
  posture) · `clarify`/`escalate` parking on durable signals ·
  `agent_judgement_routed` residual events (require runtime agent
  discretion the deterministic runner lacks) · free-text steering →
  replanning · mid-run mode *suppression* rules. All stay out of 017 by
  contract (Out-of-scope); check-in content stays deterministic renders.
- **Runner-visible token-usage aggregate** — as-built, every LLM backend
  discards `_usage` after Langfuse tracing, so 017's dev summary log
  carries wall-clocks only; per-component tokens are read in Langfuse. A
  runner-visible single-line usage aggregate needs a usage-return refactor —
  arrives with that refactor or the component-progress protocol (contract
  decision 11, rev 2.6). **Scheduled: 018 Phase A telemetry sweep** (usage-return
  refactor + durable per-component wall-clock/counts).
- **Component-name rename `screen`→`screen_abstract` / `screen_stage2`→`screen_full`**
  (user, 2026-07-10) — the DB already stores stage as an integer (`ck_ssr_stage`), so
  this touches only the plan-vocabulary strings (`DiscretionaryComponent`, runner step
  lists, persisted `orchestration_plan` rows and event payloads that carry step names).
  Cosmetic (component names never reach the UI — demo/RETRO §2), so it waits for the
  next slice that touches the screen/plan vocabulary anyway; renaming persisted plan/event
  vocabulary needs a data migration or a read-side alias, decided then.
- **Direct plan editing on the plan pane** (user, 2026-07-10) — editing the proposed
  plan directly (not only conversationally), with edits synced back to the planner
  conversation and a confirm-changes step before the run button arms. Web-app-slice
  feature: it needs the durable plan surface + a plan-patch grammar and the planner's
  acknowledgement turn. The conversational half stays the only editing path until then.

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

## Execution / collaboration / ops

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
- **`structlog.contextvars.bind_contextvars` for ambient run/project correlation** —
  `logging.py` wires `merge_contextvars` into the processor chain but nothing calls
  `bind_contextvars`, so every log call must manually repeat `project_id`/`run_id` and most
  don't (e.g. `harness.py`'s `component.started`/`grounding.failed`). Bind once per run/component
  instead of threading kwargs through every call site. Also: exceptions are logged as `error=str(exc)`
  with no type/traceback, and the processor chain has no `exc_info`/traceback renderer to make
  `exc_info=True` useful even if added.
