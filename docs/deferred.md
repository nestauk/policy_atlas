# Deferred work

This file lists work that Policy Atlas put off on purpose. It is ordered by part of the system:
read the section for the part you are about to change. Each entry says what is not built (or what
the limit is), why, and the condition that would make someone build it. Remove an entry when its
work is built.

The first release has live runtime egress: the product calls model providers, search services and
document hosts ([environment.md](agentic-ops/environment.md) § Network policy). "Zero runtime
egress" in a task document is a build-stage rule (a slice that adds egress needs approval), not a
statement of product scope.

## Contents

- [Product and future capabilities](#product-and-future-capabilities): Capabilities not built yet, the workspace cluster, sharing and export, the report's shape.
- [Evidence search: search and acquisition](#evidence-search-search-and-acquisition): Search backends, queries, filters, the pool and the coverage record (`evidence_search/sourcing/`).
- [Evidence search: full-text ingest and embedding](#evidence-search-full-text-ingest-and-embedding): Fetch, parse, chunk and embed; the queued ingest function (`evidence_search/sourcing/`, `core/embeddings.py`).
- [Evidence search: screening, classification and appraisal](#evidence-search-screening-classification-and-appraisal): Screen, classify, appraise and the source/evidence policy (`evidence_search/assess/`).
- [Evidence search: selection](#evidence-search-selection): The select component and ranking (`evidence_search/corpus/select.py`, `ranking.py`).
- [Evidence search: extraction](#evidence-search-extraction): Finding schemas, extraction and the vetter (`evidence_search/extract/`).
- [Evidence search: grouping and themes](#evidence-search-grouping-and-themes): Characterise, group and the clustering engine (`evidence_search/group/`, `evidence_search/corpus/`, `core/clustering_engine.py`).
- [Evidence search: synthesis and retrieval](#evidence-search-synthesis-and-retrieval): The writer, the grounding judge, repair, summaries and chunk retrieval (`evidence_search/synthesis/`).
- [Options scoping](#options-scoping): Baseline, longlist, option profile, constrain, themes and shortlist (`options_scoping/`).
- [Theory of change](#theory-of-change): The theory of change task kind (`theory_of_change/`).
- [Task Agent, plans and steering](#task-agent-plans-and-steering): Planning turns, the plan, steer points, the router and the agent watch (`runtime/task_agent*.py`, `runtime/steering*.py`).
- [Chat](#chat): Chat conversations and turns (`runtime/chat_*.py`, `api/chat_*.py`).
- [Runner, harness and walks](#runner-harness-and-walks): The capability runner, the harness, events and walks (`runtime/runner.py`, `runtime/harness.py`, `core/events.py`).
- [Model routes and model calls](#model-routes-and-model-calls): The route file, providers, keys, caching and call wrappers (`model_routes.toml`, `core/model_routes.py`, `core/tracing.py`).
- [Data model](#data-model): Tables, keys, migrations and stored history (`core/schema.py`, `backend/alembic/`).
- [API (application programming interface)](#api-application-programming-interface): Routes, read models, live streams and locks (`api/`).
- [Frontend](#frontend): Views and shared components (`frontend/src/`).
- [Accounts, organisations and administration](#accounts-organisations-and-administration): Cognito, organisations, the admin read and the ops CLI (`api/auth.py`, `ops/`).
- [Infrastructure and deployment](#infrastructure-and-deployment): AWS stacks, deploys, alarms, analytics and operations (`infra/`, `infra/DEPLOYMENT.md`).
- [Observability (Langfuse)](#observability-langfuse): Traces, scores, costs and trace access (`core/tracing.py`, `core/usage.py`, `scripts/` cost tools).
- [Evaluations](#evaluations): Eval datasets, scripts and measures (`scripts/evals/`).
- [Test suite](#test-suite): Backend and frontend tests (`backend/tests/`, `frontend/src/**/*.test.*`).
- [Agent harness and repository tooling](#agent-harness-and-repository-tooling): Prompt pins, scripts and type checks (`scripts/`, `.claude/`).

## Product and future capabilities

- Capabilities not built: Impact, Transferability, Value for Money, Risk, Scrutinise (red team) and
  map stakeholders. Each needs its own capability contract. See
  [evidence-search/capability.md](specs/capabilities/evidence-search/capability.md) (the ⏸ consumers
  of the findings layer). Condition: the owner picks the next capability.
- An orientation (domain primer) capability for people new to a policy area: see
  [options-scoping/capability.md](specs/capabilities/options-scoping/capability.md) (ruling 24).
  Condition: the owner picks the next capability.
- Question shapes with no home yet: stakeholder views and public opinion, and statistics or fact
  finding. Evidence search must still give a useful answer to these, but its prompts and evals are
  not tuned for them. Condition: a stakeholder or baseline-analysis capability is chosen.
- The report's shape stays intent-led. Recommendations, stakeholder views, impact framing and cost
  comparisons belong to future capabilities (options assessment, stakeholders, impact, value for
  money), not to the Evidence search report. `section_role` is the extension point. Condition: one
  of those capability contracts is drafted.
- Companion documents for Transferability: 76% of process evaluations are published apart from their
  trial results, a median of 15.5 months later. The capability's search should look for them.
  Condition: the Transferability contract is drafted.
- The workspace cluster is not built: an artefact gallery, a capability picker, several artefacts
  per task, "Cited in" per artefact, run-scoped decision views, and plan, run and artefact moved
  under the task. Open design inputs: reuse of classify labels across questions in one task,
  appraisal reuse keyed on `rubric_version`, and screening cost that grows with each question (the
  screen re-runs over the whole pool). Condition: the workspace-cluster contract is drafted.
- Sharing and export beyond the public task link (ADR 0035): project-level public sharing, a public
  gallery, export formats other than the print style sheet, deep links pinned to a version, and
  summary export. Condition: none recorded.
- Cross-artefact tracing, body-level coherence checks, chart view-types and the editing user
  interface: see [data-model.md](specs/system/data-model.md) (the ⏸ items). Condition: as the spec
  says.
- Summaries as a retrieval-routing signal and support-direction relations (supports, caveats,
  contradicts): see [provenance-grounding.md](specs/system/provenance-grounding.md). Condition: as
  the spec says.
- No artefact-level confidence badge and no aggregate confidence score across sources. The report
  uses descriptive metadata and finding-strength words instead. Condition: none recorded.
- Curated collections (`Library`), departmental-repository ingest (`Connected`), document versioning
  beyond the `supersedes` link, cross-task finding reuse and per-item sensitivity labels: see
  [data-model.md](specs/system/data-model.md). Condition: as the spec says.
- Formal sign-off (clearance) workflow and full role-based access control: see
  [product.md](specs/product.md) § In / out of scope. Condition: as the spec says.

## Evidence search: search and acquisition

- Document identity (issue #75): one document from two backends, or in two versions, is two
  snapshots and counts twice in coverage, selection and counts (one Cochrane review was five
  snapshots; 6 to 27 duplicate titles per run have no digital object identifier, DOI). The first
  rule is DOI-only. Open: dedupe at acquire or at ingest, and before or after the chunk index.
  Options scoping groups by DOI where it counts. Condition: its own Evidence search slice after the
  options scoping build (owner ruling).
- A third search backend: a Semantic Scholar snippet search or Consensus. The snippet arm leans to
  open-access papers, gives about 550 unique papers per 1,000 snippets and needs a DOI lookup. Price
  Consensus per request sized to the cap. Condition: a decision on the recall baselines (see the
  measured facts).
- Search stays inside `evidence_search/sourcing/` and is not a shared tool layer. Condition: a
  web-search capability or a new data source lands (the theory of change web search is the first
  candidate).
- Filter vocabularies not built: OpenAlex topic, keyword, venue and funder name-to-id lookup; an
  Overton `source_region` code table; a COFOG (Classification of the Functions of Government) table;
  Overton open topics and document types; the country groups "Very high human development", APAC
  (Asia-Pacific) and "all but UK"; OpenAlex `is_global_south`. Condition: a user asks for a filter
  the vocabulary lacks.
- No citation floor: recall comes first. If a floor is wanted, make it a steerable directive, never
  a silent filter in the transport. Condition: a user asks for a citation floor.
- Author-country geography is not offered: `_geography` reads the publisher's country only. The
  stored authorships keep author countries, so a separate, labelled dimension needs no migration.
  Condition: users ask where the authors are based.
- A calibrated recall estimate on the coverage record ("about N% of relevant documents found") and
  compression of abstracts before the screen. Condition: a recall estimate method holds on the
  search ground truth; compression only if screen tokens set the wall time.
- Similarity damping of the policy ranking, `(specificity + 0.5) × (similarity + 0.2)`, agreed in
  principle. It costs about 5 embedding calls, and a document with no excerpt scores on its title
  alone (fix untested). Condition: a measured policy-recall gain with that fix.
- The reformulation pass for the Broadest scope gave +3.9 points of recall at the ceiling. The
  prompt builders and wires stay in the tree, tested and unreachable; the orchestration is at the
  tag `search-round-loop-last` ([ADR 0038](adr/0038-single-pass-search-and-adaptive-screen.md)).
  Build it as one more pass after the screen. Condition: Broadest recall must go up.
- `source_country` is not a plan option. The directive `source_country_post_filter` exists; exposing
  it is a plan-vocabulary change. Condition: users ask for a source-country filter.
- Option searches send three query forms. The review and trial forms nearly always return nothing,
  and Overton gets the whole design paragraph as its query. A fallback ladder would cut calls.
  Condition: a review of search cost.
- The option-search loop and allocation by corpus size need a stop condition in the search loop.
  Condition: none recorded.
- An open-web search backend (untrusted trust class) behind the same `search` verb, with mandatory
  injection screening, ingested as frozen chunks: see
  [execution-orchestration.md](specs/system/execution-orchestration.md). Condition: as the spec
  says.
- Saturation-based stopping (a `saturated` stop value): see
  [evidence-search/provenance.md](specs/capabilities/evidence-search/provenance.md). Condition: as
  the spec says.
- Injection screening of third-party text (titles, abstracts, full text, Overton's model-written
  descriptions). The posture: third-party text is data, and `llm_description` text is stored
  visibly. Not built: a distinct flag on claims that rest on `llm_description` text, and a decision
  on enforcement now that the screen, classify and synthesis models read this text. Condition: due
  now; the model readers it waited for have shipped.
- `acquire_sources`: a backend counts as failed only when every call fails. One failed call beside
  good ones leaves `completed` and `adequate`, visible only on its `search.executed` row. Fix: a
  partial status in the coverage vocabulary. Condition: the coverage vocabulary changes next.
- Landmarks fetched by id are checked against `source_country_post_filter` only, so a dated or
  publisher-typed plan can admit a landmark outside its range. Fix: apply the plan's Overton filters
  locally. Condition: none recorded.
- `search_live.py`: Overton has `has_snowball=False`. The edges if it opens: `plain_dois_cited`,
  `generate_id_set.php`, `open_cited_institution_authors`. Condition: none recorded.
- `source_tag` rows accrete on re-runs and are never merged; `_provider_tags` dispatches by backend
  name and gives no tags for an unknown name (`_MAPPERS` is a separate structure). Condition: a
  third backend, or tag fragmentation blocks a feature such as tag boosts.
- Acquire dedup preloads the task's records in memory, so two acquire runs in one task at the same
  time can insert one document twice. A database guard is a schema change. Condition: concurrent
  acquire runs in one task become routine.
- Provider rate limits are shared by concurrent runs. The pacing lock and the 429 (too many
  requests) pause are per backend instance, so per run; the executing-walk bound is the only
  fairness control. Condition: real contention, or the scaling task.
- `ScopeConstraints` has no language filter. Scoping stores a language restriction and shows "not
  yet applied at retrieval". Condition: none recorded.
- Non-English documents: title selection prefers English; nothing else handles other languages.
  Condition: none recorded.
- `fetch_live.py` and `search_live.py` duplicate the retryable-status set and the backoff shape.
  Condition: a third live HTTP (hypertext transfer protocol) client.
- Overton snapshots acquired before author names were kept show the publishing body as a corporate
  author. Backfill means re-acquisition. Condition: readers ask for named authors on old policy
  documents.
- Overton's `published_on` becomes the document year, but for grey literature it is often Overton's
  indexing date. Fix in the Overton adapter: prefer the document's own date, and show no year rather
  than a wrong one. Condition: the next cleanup chore.
- Overton placeholder titles ("[THIS TITLE IS BROKEN AND HAS BEEN REMOVED]" on 114 snapshots, also
  "Untitled" and file names) reach screening and option cards. Drop or flag them in the mapper.
  Condition: the next cleanup chore.
- Acquired sources do not record which query found them, so relevance per query cannot be derived.
  Fix in acquire (a set of queries per source; a schema change). Condition: search tuning work
  starts.
- Search recall baselines: one Semantic Scholar snippet search reached 18.1% recall at the
  1,000-result ceiling, above the pipeline's deep depth (15.3%). One plain Consensus search beat the
  rapid depth; one plain OpenAlex search fell below it.
- Provider-written abstracts: 32 to 52% of "abstracts" are machine summaries. OpenAlex returned
  nothing for 27 to 47 of 50 to 60 generated option-search queries.

## Evidence search: full-text ingest and embedding

- Layout-model parsing (docling) for heading-light PDFs (portable document format files) that
  collapse into 2 or 3 huge chunks: see [ADR
  0004](adr/0004-parse-profile-per-snapshot-pymupdf4llm.md). Docling on a CPU (central processing
  unit) takes about 5 to 20 minutes per 100 documents, so GPU (graphics processing unit) sizing is
  part of it; the pymupdf-layout tier is licence-blocked (PolyForm Noncommercial). Condition:
  parse-quality evals.
- Depth and time-budget gradation: the agent would compile a user's time or quality preference into
  per-component budgets (search, screen, parser tier, fetch volume, select budget, synthesis caps).
  `parse_profile` per snapshot is the hook for the parser choice. Today depth is a fixed table.
  Condition: users ask to trade time for quality.
- Embedding-unit research: contextual retrieval, late chunking, exact token budgets, semantic
  re-chunking of oversized sections. `embedding_unit_policy_v1` is versioned, so each lands as a new
  policy. Condition: retrieval evals in synthesis refinement.
- `lxml` and `trafilatura` read untrusted HTML (hypertext markup language) and have version floors
  but no ceilings. A major upgrade on a lock regeneration changes behaviour on hostile input
  silently. Condition: a dependency decision (dependency changes need approval).
- A richer content peek for poor-metadata grey literature: see
  [evidence-search/components.md](specs/capabilities/evidence-search/components.md) (tiered content
  peek). Condition: windowed full-text screening proves too weak.
- No second parser for PDFs that fail or have no text layer (OCR, optical character recognition;
  Textract; Bedrock Data Automation). The signals exist: `parse_failed` counts by reason and
  thin-text guard hits. Condition: a measured share of failures that a second parser could recover.
- Parse profile v2 is the markup rule only. The header, page-number and footnote rules recovered 5
  of 941 quotes together and nothing alone. Condition: a quote-failure measurement blames page
  furniture.
- `ingest_full_text.py`: when landing-page HTML parses above the thin threshold and a
  `citation_pdf_url` exists, the cascade keeps the HTML, so a verbose landing page ingests as
  boilerplate. Condition: content-quality evals show boilerplate ingest.
- Overton records with several PDFs: ingest reads the primary `pdf_url` only
  (`grouped_pdf_ids_in_result` is kept). Condition: none recorded.
- `fetch_live.py`: `getaddrinfo` runs outside the 30-second request timeout. Condition: telemetry
  shows DNS (domain name system) resolver stalls tying up fetch workers.
- `fetch_live.py`: the SSRF (server-side request forgery) guard allows any port on a public address.
  A port 80/443 allowlist would block port probing. Condition: live-corpus telemetry on ports, or a
  security review.
- The ingest functions (up to 20 at once) do not share the per-host limit (2 at once, 1 second
  apart). `Retry-After` and queue redelivery cover it today. Condition: 429 (too many requests)
  errors rise on staging; then use a per-host FIFO (first in, first out) message group.
- `set_forkserver_preload` acts only before the forkserver starts. Ingest is the only forkserver
  user in `backend/src`. Condition: a second, earlier forkserver user.
- Embedding batch slices share one database connection, so they run in sequence. Condition:
  embedding wall time sets the ingest stage time.
- `ingest_upload` runs its embed pass outside any trace span, so its batches show as separate root
  traces, and uploads have no audit event. Only the dev CLI (command-line interface) reaches it
  today. Condition: a product upload surface uses `ingest_upload`.
- `FixtureFetcher`'s path-traversal guard is an `assert`, which `python -O` removes. Make it a
  `ValueError`. Condition: the next cleanup chore.

## Evidence search: screening, classification and appraisal

- A "Narrative review" evidence type at score 2 (now such reviews land in "Expert opinion and
  commentary", score 1). It is shared by Evidence search, Options scoping and theory of change, so
  it needs its own decision: a new `EVIDENCE_TYPES` member, a `DEFAULT_RUBRIC` row, the classify
  prompt, a migration and a re-classify note. Condition: an owner decision.
- The source/evidence policy object: corpus view against evidence view coverage, a policy that
  compiles into directive boosts for select and synthesis, below-policy citations flagged, and the
  "policy unmeetable" trigger. See
  [evidence-search/components.md](specs/capabilities/evidence-search/components.md) (dual-view
  coverage). Condition: its own data-model design.
- The full-text second appraisal pass, the relative-to-feasible tier and modifier-tag dimensions:
  see [provenance-grounding.md](specs/system/provenance-grounding.md) and
  [evidence-search/components.md](specs/capabilities/evidence-search/components.md). The same pass
  would add v2's small-sample penalty (it needs sample size) and read the retracted flag. Condition:
  as the spec says.
- Splitting the grey-literature evidence types, and resolving `Unknown` on full text: see
  [evidence-search/components.md](specs/capabilities/evidence-search/components.md). Condition: as
  the spec says.
- A steer point can override the appraisal rubric (D1), but the agent does not compile an evidence
  hierarchy into the plan before the run, and nothing checks that a stored `rubric_version` names a
  real rubric. Condition: users need a different hierarchy at plan time.
- Uploaded documents might skip the screen (acquired documents always screen). That is why there is
  no foreign key from classification results to screening results. The spec says classify runs on
  the screened-in set, so this needs a spec change first. Condition: an upload flow into Evidence
  search is designed.
- Classify runs one call per document; screen uses 3-call consensus. Condition: a measure of
  classify's single-call errors shows a need.
- A screening ensemble across model families. Bedrock routes now exist ([ADR
  0041](adr/0041-bedrock-inference-route-and-model-route-file.md)), so the prerequisite is met.
  Condition: a screen-quality eval to compare with 3 calls to one model.
- Classify confidence is stored only in event payloads; no gate acts on it. Condition: a first
  consumer of the confidence.
- The add walk's screen loads the task's whole pool and judges it against the option's design; there
  is no screen memo across scopes. Condition: the screening cost of add walks matters.
- `uq_sar_scope_source` allows one appraisal per scope and source. A re-appraisal under a new rubric
  needs `rubric_version` in the key and a fix to `already_appraised` counting. Condition:
  re-appraisal is wanted.
- `effective_screen_rows` excludes failed rows, so a document whose new re-screen failed keeps the
  old generation's verdict with no marker. Condition: effective rows span generations in a real run.
- The screen's stage-row insert (NOT EXISTS plus a partial unique index) assumes one screen run per
  scope at a time. Condition: concurrent screen runs of one scope.
- `screen.py` `_load_stage2_docs` streams one query per snapshot to bound memory. A single
  window-function query would cut round trips. Condition: stage-2 telemetry shows database round
  trips dominate.
- No automatic sweep re-runs failed screen or extract rows; a new run retries them. Condition:
  failure rates make manual re-runs a burden.

## Evidence search: selection

- The selection budget is a fixed ceiling per depth (`ANALYSIS_DEPTH_TABLE`, 25 at deep). It could
  depend on the corpus (screened and full-text counts, strata, question breadth). Condition: eval
  evidence for the conditioning function.
- Select's ranking as a shared purpose-fit tool other components could call. Condition: a second
  component needs purpose-fit ranking.
- No embedding relevance in select: the screen and the strata already use the semantic signal.
  Condition: rerank evals show the deterministic composite needs a semantic leg.
- Selection diversity by publication country and by study geography or population. The spec marks
  them rough. Condition: post-extraction dimensions exist.
- Only two select strategies exist and the registry checks exactly those. Condition: another
  capability (for example Transferability) needs its own strategy.

## Evidence search: extraction

- New finding schemas: the generic container and runtime custom extraction stay declined ([ADR
  0017](adr/0017-icf-second-finding-schema.md)). Named candidates: `reported_statistic`,
  `case_example`, `intervention_specification` and perhaps `reported_problem`. The first reader is a
  baseline-analysis capability. Additive schemas never invalidate eval baselines. Condition: that
  capability's contract commits the profile, with eval evidence per category.
- Hybrid indexing of finding dimensions (`intervention`, `outcome`, ICF (implementation context
  finding) fields): see [data-model.md](specs/system/data-model.md) (behind the promotion gate for
  all dimensions). Condition: observed query behaviour.
- The extraction service and dataset snapshots: profile resolution against existing records,
  per-source task objects, capability commits that declare profiles, and pinned datasets. Today
  extraction is a per-document record with a memo key. Condition: a capability needs a pinned
  point-in-time dataset.
- A second extraction pass for recall on long documents (`pass_count` already records 1). A claim
  that spans two window-filling chunks is never seen whole. Condition: extraction ground truth.
- Retrieval-augmented extraction (targeted in-document retrieval to repair or join windows).
  Condition: extraction evals show a field gap on multi-window documents.
- Extraction remedies held for evals: draft-then-constrain, one call per intervention, and a bounded
  fuzzy quote fallback that can flag but never verify. Condition: extraction evals show the matching
  error.
- A retrieval-based findings layer for rapid and standard runs, which skip the extract chain. It
  needs its own coverage-base rung and honest absence semantics. Condition: evals show synthesis
  from envelopes is too weak at those depths.
- `extract_profiles` must include `iof`; ICF-only extraction cannot be expressed. Condition: a plan
  needs ICF alone.
- The IOF (intervention-outcome finding) and ICF profiles run in sequence, about twice the extract
  wall time, because they share one connection for memo reads and writes. Condition: extract wall
  time matters.
- The ICF build copied the IOF plumbing (backends, vetter, dedup, per-kind literals). Condition: a
  third finding schema; then budget a consolidation (a profile registry).
- `claim_basis` coverage cannot tell "indeterminate after reading" from "not attempted": every null
  lands as `not_extracted`. Condition: extraction ground truth.
- Two selected documents that share one content-keyed basis snapshot both extract fresh and collide
  on `uq_ser_memo`. The document store ([ADR
  0043](adr/0043-queued-ingest-document-store-sql-retrieval-step-timeouts.md)) may now make this
  possible. Two concurrent extract runs collide the same way. Condition: due now; check, then add an
  in-run memo update.
- The memo keys on task, basis snapshot and fingerprint, not on evidence type. Condition: plans that
  extract before they classify.
- The call budget scales with document length; there is no absolute per-run window ceiling.
  Condition: arbitrary corpora reach extract.
- Windows are independent; only exact claim-key dedup collapses duplicates across the 1-chunk
  overlap. Condition: near-duplicate findings are seen.
- The `thin_extraction` flag has no definition and is not computed. Condition: a consumer needs it.
- `study_geography` keeps the source's raw place strings with no normalisation to country codes.
  Condition: a consumer must group findings by country.
- `extract/quote_verify.py` holds the generic matcher that synthesis also imports. Condition: a
  third consumer; then move the matcher to `core/`.
- Extraction and vetter output is scrubbed of NUL characters only. Extend the scrub to C0 and C1
  control characters (except newline and tab); `prompt_fields.scrub_nul` and `extract._scrub_nul`
  must change together. Condition: the next cleanup chore.
- No length cap on free-text finding fields between model output and storage. One bound in
  `validate_record` covers the class (needs an `iof_rules` version bump). Condition: the next
  cleanup chore.

## Evidence search: grouping and themes

- Grouping input beyond `FACET_VALUE_CAP` (400): sampling or embedding-based clustering for
  discovery, and characterise's all-titles read. See
  [evidence-search/components.md](specs/capabilities/evidence-search/components.md). Condition: real
  corpora exceed the cap.
- Promoting facet themes past run-local, and graph-structured synthesis, both gated on
  entity-resolution quality: see [data-model.md](specs/system/data-model.md). Condition: as the spec
  says.
- Grouping ideas held for evals: topic merge and split, quote-verified assignment, provider topics
  as hints, characterise themes as facet hints, and per-document open tags. Condition:
  grouping-quality evals.
- ICF facet grouping covers barriers, enablers and mechanisms only. The other four `context_type`
  values are a config addition on the same engine. Condition: a reader wants that lens.
- The five facet pipelines in `group` run in sequence; claim-theme facets share one connection that
  is not thread-safe. Condition: deep-run wall time hurts.
- Discovery can emit themes that assignment gives no members; they persist with `size: 0`.
  Condition: grouping-quality evals decide on pruning.
- Grouping-quality evals: quality bars, adversarial corpora, negative-rule adherence,
  `FACET_VALUE_CAP` calibration and a two-scopes-one-task coverage fixture. Condition: none
  recorded.
- Grouping on live corpora: a 206-document corpus hit an `APITimeoutError` batch failure and an
  85-document corpus failed discovery twice (`InvalidDiscoveryOutput`) before a 60-document pass
  worked. Retry caps and batch sizes are calibration targets.

## Evidence search: synthesis and retrieval

- The weighted verdict ("the evidence supports X at strength Y"): see
  [evidence-search/components.md](specs/capabilities/evidence-search/components.md) (consensus
  seam). When built: unsupported, mis-cited and tier-4 reasoning claims never count for; weakly
  grounded claims count at a discount; gap claims never count. Condition: the aggregate roll-up is
  designed.
- A slimmer emit payload: claims anchored by position in the prose and chunk citations by record id
  plus a short anchor. About 70% of the write turn's output is claim structure; this would halve the
  write turn. It changes the grounding contract ([ADR
  0015](adr/0015-prose-first-synthesis-with-span-anchored-claims.md) § 4). Condition: synthesis
  refinement.
- After one repair pass, a claim the judge still marks unsupported stays in the prose, flagged.
  Options: a second bounded repair round, hedge-or-delete by default, a visible marker in the prose,
  or re-gather repair (tool turns inside repair). Each changes the grounding contract. Condition:
  synthesis refinement, with a judged set of sections.
- The writer does not reason before it writes: `reasoning_effort="none"` is a provider limit on
  tool-bearing chat-completions calls. The Responses endpoint may lift it; reasoning tokens cost
  latency. Condition: the Responses API move.
- Route the gather (tool-selection) turns to a cheaper model: they were about 43% of writer input
  tokens, an estimated 20 to 30% run-cost saving. A weaker gatherer can fetch worse evidence.
  Condition: synthesis refinement, with evals as the regression net.
- Unappraised documents are readable but not citable. Open: do they take top-k slots and prime prose
  nothing can cite? Measure first; a default down-weight is the fallback. An appraised-only boundary
  was rejected (a wrong `Unknown` would silently remove a document). Condition: synthesis
  refinement.
- Envelope A/B tests: `effect_basis` in the judge envelope, and writer metadata (author
  institutions, FWCI, field-weighted citation impact). Run each A/B on its own baseline, one after
  another. Condition: synthesis refinement.
- `search_chunks` scope filters exist; the writer prompt has no guidance on when to scope. Prompt
  work is lead-only. Condition: synthesis refinement.
- `SELECTION_PRIOR_BOOST` is a flat 2.0 multiplier on the fused score. Citations record their
  origin, so the effect can be measured. Condition: synthesis refinement.
- The section ledger is sent in the task message from the first turn, so it overlaps the read
  context; removing it needs a prompt-shape change. Condition: synthesis refinement.
- Report composition conventions (block order, summary and key-findings rules, citation numbers by
  first appearance) and block versioning (supersede and lock-on-advance; blocks ship at
  `version=1`). Condition: blocks regenerate or reports need versions.
- Structure discovery for sections (recon-informed proposal, mismatch signals, a revision
  checkpoint). Condition: one-shot sectioning proves a problem on live corpora.
- A coherence pass when blocks regenerate. Condition: blocks regenerate.
- Cross-corpus pattern claims are refused because nothing can verify them. Condition: a
  deterministic validator or a judge lane for them.
- Retrieval over unscreened content and corpus-scale retrieval: see
  [evidence-search/components.md](specs/capabilities/evidence-search/components.md). Condition: as
  the spec says.
- The section proposal stays inside synthesise, so headings appear when writing starts: see [ADR
  0044](adr/0044-live-activity-streamed-sections-one-copy-source.md). Condition: none recorded.
- `synthesis_tools.py` `search_chunks` returns the top 8 chunks with no per-document spread, and
  `SYNTH_CHUNK_CHAR_BUDGET` (24,000) is spent on the first read turn. Reports cite about 12 of about
  55 relevant documents (see the measured facts). Condition: synthesis refinement.
- The SQL (structured query language) retriever's word leg scores word overlap, not BM25 (rarity
  weighting, frequency saturation, length normalisation). Condition: synthesis refinement; measure
  on the 88 recorded queries and the citation funnel first.
- `ChunkRerankerBackend` passes chunks through (`reranker: "none"`). Its stated trigger, the Bedrock
  route, has shipped; a cross-encoder reranker on Bedrock is possible. Condition: synthesis
  refinement measures retrieval.
- Judge and repair take 19% to 37% of write time. Levers: a smaller judge envelope (the cited chunks
  only), judging section N while N+1 reads (about 25 seconds per baseline), and a quote bound of
  about 120 characters (about 20 seconds). Condition: synthesis refinement.
- `judge_grounding` runs at `low` effort on the Bedrock route: half the wall time, but more lenient
  than `medium` (see the measured facts). Condition: synthesis refinement re-judges a labelled set
  of disputed claims.
- `unspanned_assertions == 0` can mean "not scanned": a block whose final prose no judge call
  scanned mints unscanned. Readers must check `unspanned_lane_skipped`. Condition: synthesis
  refinement decides on a judge call for that lane.
- `SectionOut.summary` projects a one-block section only; a multi-block section shows no summary.
  The artefact summary has a staleness marker but no machinery. Condition: sections hold several
  blocks, or blocks regenerate.
- `_first_named_tool_call` keeps the first `emit_section` or `emit_repairs` call and counts the rest
  in `extra_tool_calls_ignored` (0 of 434 calls). Condition: the count goes above zero; then merge
  or retry.
- The synthesis `lookup` tool's vocabulary has no screening rows. Condition: a consumer wants them.
- Retrieval is exact cosine over the scope's units, about 300 ms a search under load. Condition:
  per-search latency matters as scopes grow; then add an HNSW (hierarchical navigable small world)
  index on `chunk_embedding.embedding`.
- Synthesis, judge and retrieval quality evals: judge calibration, prose quality, retrieval quality,
  and the constants `SECTION_CAP`, `SECTION_TURN_CAP`, `SYNTH_CHUNK_TOP_K`,
  `SYNTH_CHUNK_CHAR_BUDGET`, `EMISSION_CLAIMS_MAX`, `CLAIM_TEXT_MAX`, the boost weights, the
  `lookup` vocabulary and the one-pass repair cap. Add cases: unjudged pattern, theme and gap claim
  text, and a chunk that tells the judge how to rule. Condition: synthesis refinement.
- Summary retries can repeat word for word: `_write_and_judge_summary` carries only the latest
  failed attempt, and a regenerate resends the same seed. Carry every failed attempt in both
  summariser prompts (a re-pin). Also: `writer_calls` misses the attempt that raised. Condition:
  synthesis refinement.
- `block.summary_status` says `failed` but the judge's reason lives only in logs and traces. Add a
  `summary_reason` column (a schema change). Condition: synthesis refinement.
- The baseline writer asks for tools the scoping chain never fills (4 to 7
  `characterisation_summary` errors per baseline). Condition: synthesis refinement.
- Synthesis timing on one 9-section baseline: 180 seconds wall, 170 in model calls (write turns 110,
  judge 30, read 22, proposal and repairs 7). Only about 30% of emitted output is prose. Rapid
  baselines cited 2 to 15 sources.
- Citation funnel on one report run: 100 candidates, 59 screened relevant, 53 appraised, 17 ever
  returned to the writer, 12 cited. Other runs cite 7 to 12 documents whatever the corpus (36 to 81
  relevant). The writer stopped after 2 of its 6 turns on every section; select is not the cause.
  Query recipe: `synthesis_result.blocks → block → annotation → citation → chunk →
  task_source_snapshot`.
- Per-claim judge filtering (experiment E9): deterministic quote, number and negation checks catch 8
  of 26 unsupported claims with 82 false flags; skipping whole judge calls saves 8% of tokens;
  per-claim filtering removes about 41% of chunk text at 2% false passes; two judges disagree on 13%
  of claims.
- Low-effort judge (experiment E3): half the wall per call (11.5 to 5.4 seconds) at 0.8 times the
  cost; 91.7% agreement with the medium judge (8% of claims flip run to run); 26 claims marked
  unsupported against 33 and 28 for two medium runs; 3 real attribution catches missed in 157
  claims.
- `unspanned_assertions` counts from before and after the span-map precision fixes are not
  comparable; re-baseline the metric.

## Options scoping

- Deep depth for scoping, the applicability capability and critical review: see
  [options-scoping/capability.md](specs/capabilities/options-scoping/capability.md) (⏸ Deferred).
  Condition: as the spec says.
- "Assess all kept options" beside "Assess these N": see
  [options-scoping/capability.md](specs/capabilities/options-scoping/capability.md) (ruling 19).
  Condition: live runs show what a standard run costs.
- A report written from the longlist alone: the report comes from the assessment, so before it the
  Result is the longlist
  ([options-scoping/capability.md](specs/capabilities/options-scoping/capability.md), ruling 50).
  Condition: live use shows people hand over unassessed longlists.
- "Search further" at the baseline gate: an additive re-acquire that rewrites the sections that
  gained sources (build it once for the longlist too). Today a request in words is refused as not
  yet available. Condition: none recorded.
- Baseline latency levers not taken: start the longlist's retrieval while the user reads the
  baseline (wastes some egress when the plan changes), a faster model tier for the baseline
  sections, and rebuilding only the sections a plan change touched. Parallel section writing needs
  an owner revision of the durability rule ([plan-as-object.md](specs/system/plan-as-object.md)).
  Condition: none recorded.
- No longlist chain fetches full text; chat answers from abstracts and says so. About half the
  fetches failed in the pre-contract runs (52 of 74 on the obesity list), so the next step must plan
  for missing full text. Condition: the options scoping assessment.
- Direction of effect and outcome counts belong to the assessment. A reason may say an option "bears
  on" an outcome, never that it moves it. A record carries one plan outcome. Condition: the options
  scoping assessment.
- What makes a setting comparable (income level, health system, federal structure) is not defined;
  `tried_only` and the maturity rung compare by country only. Condition: the options scoping
  assessment.
- A written option summary at first open (about 10 to 20 seconds once per card). Condition: the
  options scoping assessment.
- Linked searches are inlined whole (plan, report body, coverage) on every Task Agent turn. Options
  for many links: a digest plus a read tool, or retrieval over the linked tasks' chunks and blocks.
  `runtime/inherit.py::linked_context` is the one seam. Condition: meta-analysis is contracted, or a
  real task links more than a handful of searches; read quality first.
- The loop budgets (target size, ceiling, residual passes, records-per-document cap) are constants
  the user cannot see or set. Condition: none recorded.
- The not-stated flag sits on 76 to 96% of memberships. Condition: an owner decision on its future.
- A "burden" line on "What it would take". Condition: a test across a range of policy domains.
- A legal-change line grounded in the baseline or a document (today it would rest on the model's
  knowledge). Condition: none recorded.
- On lists that mix rules and programmes, about two thirds of options carry a cost mark. A cap would
  be a quota. Condition: the owner reads the built screen.
- An instance-of relation (a two-level longlist: a class of option and its implementations).
  Condition: evidence from live use.
- The option search takes the design only, with no `guidance` argument; the queries did not miss
  what the designs meant. Condition: option queries miss the design's meaning.
- Shortlist verbs (Add, Remove, Suggest more) are buttons only. A chat verb needs the same opener
  and refusals as the routes. Condition: none recorded.
- The appetite is never inferred from the plan's words. A later slice could propose one as a guess
  for the user to confirm. Condition: none recorded.
- The rung words ("Evaluated" and so on) carry no "in the documents we found" qualifier. Condition:
  a reader takes the rung as a fact about the world.
- The constrain reason on the "Who decides" row is served but not shown. Condition: the owner wants
  it back.
- The template sentence says "studies" ("3 moderate observational studies"), the one place the
  card's copy uses the word. Condition: an owner ruling.
- Folding calls: on the mini model the tail fails, and folds vary more between runs than between
  rounds. Two guards stand (a slash-joined kind is cut; a catch-all over half the words retries
  once). A third-of-the-words catch-all or a twenty-word kind passes. Levers: the judgment model on
  long lists, a share threshold tied to the target unit, a word-count guard. Condition: none
  recorded.
- `extract_interventions` on the mini model: 13 to 32% of programme names are the study's or
  provider's name, and a body's own name reaches `study_geography` (61 of 223 records). The next
  lever is the model tier, not the wording. Condition: none recorded.
- Place sentences: 4 of 56 fall back to the template. A `max_length` on the wire fails the whole
  call; a second call per long sentence costs one more call. Condition: none recorded.
- The records-per-document cap of 8 removes 15 to 116 records per run where a review names many
  interventions. Condition: a review-aware rule is designed.
- A setting that names a place moves or drops as a whole ("primary schools in England" is not kept
  as "primary schools"). Condition: none recorded.
- A child search that the join timeout cut off can still acquire; its documents have no screen row
  until the next build. Condition: none recorded.
- The profile memo key holds the prompt version, not the prompt text, so a text change without a
  version bump reuses old records. Condition: none recorded.
- The option-search pool is shared by every task in the process. Condition: the scaling task.
- From the end of `longlist` to the end of `theme`, and to the end of `option_profile`, the list
  shows options without groups or profile lines (20 to 77 seconds). Themes go stale after a user's
  own exclusion; `theme` can run alone. Condition: none recorded.
- An added option has no lever type, ambition, lines or setting until the next Rebuild. Condition:
  none recorded.
- "Studied in" per document: the setting words are stored but have no read-model field. Condition:
  none recorded.
- A merged pair: the lines were written with the duplicate on the list; the kept option keeps its
  own lines. Condition: none recorded.
- Rebuild matches options by `(origin, name)`, so an own option that later gains a design under
  another name mints a second row (only after a failed design proposal). Condition: such a duplicate
  is seen.
- Inherited rows carry no provider `source_tag`, so classify has no provider priors for them.
  Condition: none recorded.
- The intervention profile memo is keyed by task, so an inherited document is profiled again.
  Condition: an Evidence search task runs the profile.
- Inherit re-checks that the owner can still read a linked source, but an uploaded document of a
  readable source is still inherited, so a public scoping task shows it. Condition: public sharing
  of scoping tasks widens.
- After a design edit whose typing batch fails, the card keeps the old design's lever: lever columns
  key by option id only, not by `(option_id, design_version)`. Condition: `typing_invalid` appears
  live (0 so far).
- The read models take the newest `longlist_result` whatever the walk's status. Condition: a walk
  fails after `longlist`; then select the last completed walk.
- The shortlist has its own stage key, not `select` with an override. Condition: the owner wants the
  override (four call sites in `routers/sse.py` and `checkin_read`).
- Potential impact length: the prompt targets about 300 characters, over 400 warns, over 600 fails.
  Condition: the model keeps writing over 400; then lower the prompt target first.
- `option_cards()` calls `repository.option_out` once per option, several hundred queries before one
  model call (9 to 27 seconds per proposal). Condition: proposal wall time becomes visible to users;
  then a batch reader.
- Each appetite change opens a full shortlist walk (about USD 0.15). Condition: the price envelope
  is decided; then a per-task cap.
- No per-option reading counts before clustering: the option-search children do not publish document
  counts. Condition: none recorded.
- At the ceiling a suggested seed cannot fold into a new broader option, because room is computed
  before folds. Apply accepted folds first. Condition: the next cleanup chore.
- A duplicate chain (A to B, B to C) drops B and says A has no duplicate. Follow the chain (with a
  visited set) or give A `cannot_check`. Condition: the next cleanup chore.
- Scoping wires: free-text fields (`MarkedLineWire.answer`, `AmbitionWire.reason`, `SettingWire.*`,
  `LeverTypingWire.lever_reason`, `ConstraintJudgementWire.reason`, `AuthorityWire.*`,
  `FoldingResponse.kinds[]`) have no `max_length` and no control-character strip before storage; the
  trace check is lexical. One pass sets ceilings. Condition: the next cleanup chore.
- `_constraint_lists` and `_checks` build one list by undoing each other; a user requirement whose
  id matches a screen id is dropped silently. Build the list once. Condition: the next cleanup
  chore.
- `theme.py` imports private names from `longlist.py` (`_engine_stats`, `_forbidden_label`, `_key`).
  Make them public or move them. Condition: the next cleanup chore.
- Template sentences are not length-checked (238 and 334 characters seen). Add a ceiling on the
  template's clauses. Condition: the next cleanup chore.
- `suggest` writes its token use to a log line only, not to its summary. Condition: the next cleanup
  chore.
- The shortlist call does not see a breach on a kept place, so the note cannot mention it. One
  breach line in the card text (prompt-bearing). Condition: the options scoping assessment.
- The reasoned-guess path (a plan with a preference) has no live test. Condition: the options
  scoping assessment.
- Of 210 generated option-search queries on three tasks, none names a country, but 27 (13%) use UK
  institution words from the designs ("local authority", "NHS", "DWP"). Look again if option
  searches read too UK-heavy.
- The authority label is doubtful where a council has a part but not the whole (NHS commissioning,
  school food enforcement).

## Theory of change

- Increments not built: web search (the Responses call, Mantle on Bedrock, the web cap on grades), a
  stress-test conversation kind, "Design from an option", PowerPoint and Google Slides export. See
  [ADR 0042](adr/0042-theory-of-change-task-kind.md) § Amendment 2026-11-05. Condition: each is its
  own slice; web search follows the Responses API move.
- Full-text depth on a link and links to Evidence search tasks: see
  [theory-of-change/capability.md](specs/capabilities/theory-of-change/capability.md) (⏸ items).
  Other contract seams: findings reuse, the cross-task duplicate gap, the Miro API, removing the
  build flag, an upload retention rule, and how an older theory signals it may be out of date.
  Condition: none recorded.
- `pa_changed` and `prior_version` are stored and never shown. Not built: Undo per automatic change,
  Undo all, Keep mine, Restore for a set-aside pathway, and the plan-change choice (Redraft or Keep
  the canvas). One change list in the detail panel would read the stored flags. Condition: none
  recorded.
- Annex and build disagree: Restore for set-aside pathways, "Your original" from the Result page,
  Stop on the chat's progress line, and the History list position. An unchecked connection draws as
  a faint solid line. Condition: an owner ruling.
- `toc_proposal`, `task_upload` and `toc_figure` have no `UNIQUE(id, task_id)`. Condition: a foreign
  key needs the pair.
- When a draft lands and `admit_and_mint` refuses the follow-on check (`run_active`, `no_plan`),
  only a log line records it and `check_status` reads "checking". Persist the refusal as an event
  and tell the chat. Condition: the next cleanup chore.
- The draw.io export has not been opened in diagrams.net or Miro. Condition: the next cleanup chore.

## Task Agent, plans and steering

- The Evidence-search expert agent: it would author each component's directive (select, group and
  others) just in time from upstream outputs. Its slot is `runner.py::leg_directive`; the sockets
  exist (author-blind compile, `authored_by` and `decided_by`, the authoring protocol). Authority
  order stays user, then declared rules, then agent. Condition: evals can measure directive quality.
- The Task Agent as the control surface for an Evidence search, and any chat able to plan, edit
  artefacts and answer with citations. Routed turns hang on the turn, not the conversation kind, so
  `task_agent` would become a "pinned first" flag. See also [vocabulary.md](specs/vocabulary.md) §
  Future direction. Condition: an Evidence search slice adopts routed turns.
- Mid-component pauses and steering need a resume engine: checkpointed state plus an idempotency key
  written before any interruption, so a resumed action runs once. Pauses are at component boundaries
  only ([ADR 0025](adr/0025-parked-pauses-boundary-continuation.md)). Condition: a pause inside a
  component is needed.
- Free-text replanning (adding or removing components mid-run) is out; the router and the watch work
  inside the composed chain: see [ADR 0014](adr/0014-thin-v1-orchestrator.md). Condition: planner
  re-entry is designed.
- Global writing guidance ("write for a technical audience") is held, so two voice levers do not
  fight before the audience-framing design. Condition: the router's refusals of global-voice
  requests rise.
- Tag boosts: the boost grammar accepts tags but nothing offers or authors them, because the open
  tag layer is fragmented. Condition: tag consolidation plus hybrid matching over open tags.
- The agent watch's tool reads: `read_tools=None` at both fallback-deliberation call sites in
  `runner.py`, so the `lookup` and `query_findings` loop has no live executor; routine-boundary
  triage has no tools. Condition: insufficient-context escalations rise.
- Not built: a narration voice and rules that suppress a mode mid-run. Condition: none recorded.
- Key findings and conclusions are display-only on the report-plan card. Steering those blocks is a
  new design, not an extension of `edit_sections`. Condition: none recorded.
- The router mis-compiled about 3 of 6 free-text steers in the pinned live runs; each failure was
  caught fail-closed. Condition: an eval that measures compile fidelity.
- The Evidence search Task Agent prompt defaults to unattended ("check-ins are requested, not
  offered"); the execution contract names moderate. Decide which is right. Condition: the next edit
  of that prompt (prompt work is lead-only).
- A time and cost estimate model: see [plan-as-object.md](specs/system/plan-as-object.md) and [ADR
  0044](adr/0044-live-activity-streamed-sections-one-copy-source.md). The planner's bands are a
  static table (`task_plan.TIME_BANDS`); the lever is a rolling window of recent walks' times per
  depth, shown as a range. Condition: the recent timing changes settle.
- `steering_triggers.py`: the classify and appraise collapse triggers read the result tables
  directly, so old rows of documents a re-screen demoted still count. Condition: classify and
  appraise gain generation semantics ([ADR 0022](adr/0022-screen-generation-supersession.md)); then
  join through `effective_screen_rows`.
- `_run_plan_segment_reentry` calls `_handle_after_component_boundary` with no agent, so that
  re-presentation gets no watch judgement. Condition: none recorded.
- A repeat D3 refresh has the same deterministic fingerprint as the first, so it is a no-op.
  Condition: a second refresh is wanted; then follow the `screen_generation` pattern.
- Turning stage-2 full-text screening on or off mid-run is a composition change the plan grammar
  cannot express. Condition: none recorded.
- P3's selection preview can name counts for a dropped stratum but not theme names, which need a
  join through the theme-membership table. Condition: none recorded.
- Theme renames work at P2 only: strata are keyed by name downstream. Condition: a rename after
  selection or grouping is wanted; then key strata by id.
- `p1_bundle.sample_titles` takes the five newest snapshots for the whole task, while counts are per
  scope. Condition: tasks with several questions.
- A steer-point reselect's plan version row carries attribution but no pointer to the directive that
  caused it (the substance is in `selection_result.selection_provenance`). Condition: none recorded.
- `publisher_source: "apo"` is a test mod (Australian Policy Online). Removal touches
  `task_plan.py`, the plan drafts and wires, the Overton allowlists and filters in `search_live.py`
  and `search_loop.py`, `planning.py`, `agent.py`, `scopeChips` and the `planner_v11` rule (a
  re-pin). Stored plans with the field then fail validation unless tolerated. Condition: the APO
  test ends.
- The watch's fallback tool loop still accepts the legacy JSON-in-`needs` shape beside the
  structured `needs_tool` fields (`agent_backend.py`). Delete the legacy path. Condition: the next
  cleanup chore.
- The watch's `choose_option` id is never checked against the menu; a delta-less choice proceeds
  silently. Resolve the id. Condition: the next cleanup chore.
- Event-payload display strings are stored NUL-scrubbed only. Use `sanitize_prompt_field` on
  model-written display strings. Condition: the next cleanup chore.
- A refactor of about 12 duplicated sites in `runner.py`, `steering.py` and `steering_triggers.py`
  (retry loops, state rebuilds, boundary-handler twins, trigger ladders) that must change in
  lockstep. Condition: none recorded.
- The dev CLI (command-line interface) re-prints the stale check-in line on every re-presentation.
  Condition: none recorded.
- Prompt caching on Task Agent turns: from the third turn on, 8,960 of about 10,700 prompt tokens
  were served from the provider's cache (the system prompt and linked block).

## Chat

- Closed planning conversations never list, so "Earlier plan" is unreachable in production and an
  old `?chat=<planning id>` link reads as an ordinary chat. Decide whether closed planning rows list
  (a backend filter change). Condition: an owner call.
- Chat context is the conversation's own turns under a ceiling; there is no recall layer, and a
  re-plan's reasons do not carry to the successor conversation. Condition: none recorded.
- A chat answer never becomes artefact content, because blocks need the full appraisal bar.
  Condition: none recorded.
- The "evidence not held" hand-off links to the planning conversation; it does not become a
  structured search request. Condition: none recorded.
- Not built: search within or across conversations, task-level standing chat instructions, and
  "Continue generating" on a stopped turn. Condition: none recorded.
- Regenerate, edit and branching need the turn-pair row split into one row per message. Condition:
  none recorded.
- All chat read tools are bounded to the terminal completed run, so on a re-run task earlier runs'
  text is not searchable from chat. Condition: the workspace cluster widens the read models.
- `chat_turns.py` refuses chat turns while a walk is paused (409 `run_active`). Condition: reading a
  paused run becomes a real workflow.
- A client that reconnects mid-stream re-reads the chat or planner turn once it lands; only the
  section stream resumes. Condition: none recorded.
- The chat prose stream has no retry: a connection error before the first token fails the turn. Wrap
  the opening request in `traced_attempts`, as the planner stream does. Condition: the next cleanup
  chore.
- Chat turn citations still carry a per-citation verdict; the report moved it to the claim. Make the
  same move with the chat renderer. Condition: the next cleanup chore.

## Runner, harness and walks

- Branch-level parallelism inside a run and a durable workflow engine: see
  [execution-orchestration.md](specs/system/execution-orchestration.md). Condition: as the spec
  says.
- Cancelling a run: closing the HTTP client does not stop a Bedrock call, so cancel needs a
  cooperative flag checked between turns and chunks. See [ADR
  0044](adr/0044-live-activity-streamed-sections-one-copy-source.md). Condition: its own slice.
- Consumers take one upstream run per kind (grouping already fans out per facet inside one run). No
  durable object says "this capability run is characterise once, group twice, synthesise once".
  Condition: a plan needs two runs of one component feeding one consumer.
- `run_harness`'s generic component handler appends the failure event on the component's own
  transaction, so a database error reads as an aborted transaction. The runner path rolls back
  first. Condition: none recorded.
- Every child walk appends to the task's one event-log sequence; four walks at once contend (retry
  cap raised from 5 to 32). Condition: contention errors appear; then a per-walk sequence.
- A model-calling step that fails can cost four calls: the component re-asks once, then the runner
  retries once. Condition: none recorded; the lever is a per-step "no runner retry" flag.
- `component.started` commits before the component transaction, so a hard kill in that gap leaves
  the pair open on the `runs` row (the walk is still marked interrupted). Condition: that trail must
  be self-consistent.
- `_run_scope_component`, `_run_characterise` and `_run_synthesise` share about 30 lines of
  bookkeeping. Condition: a fourth node of this shape; then add a failure-payload hook.
- Extract, both screens and classify each hand-roll the submit, wait, collect and retry fan-out.
  Condition: one of the four changes for a product reason; then share one helper.
- `run_harness(provider=…)` has no component readers. Its removal waited for the Bedrock route,
  which has shipped. Condition: the next cleanup chore.

## Model routes and model calls

- Older projects keep vectors under the old embedding profile. Re-embed them under the Cohere
  profile, or do not offer chat retrieval on them: a cost decision. Condition: a user needs chat
  retrieval on an older project.
- Model quality on the routes is partly unmeasured: Terra for the two agents, Cohere vectors for
  grouping and retrieval, and the inactive Claude route for query generation. Compare with an
  overlay route file per experiment (`POLICY_ATLAS_MODEL_ROUTE_FILE`). Condition: synthesis
  refinement for the writer and judge; none recorded for the rest.
- Bedrock hangs: invocation logging would show the provider side, but it stores request bodies.
  Condition: the DPIA (data protection impact assessment) allows stored bodies.
- `core/model_routes.py`: overlay routes may name only the two committed key variables
  (`API_KEY_ENVS`). Condition: an experiment needs a third provider.
- There is one Claude backend; the shared Converse plumbing stays with it. Condition: a third call
  site moves to Claude; then move the plumbing into `core/`.
- `synthesis/cache_modes.py` is a second per-step table beside the route file, imported by five
  packages; a test keeps it in step with `[steps]`. Condition: the route file's step schema changes
  next; then a `prompt_cache` key per step.
- A second cache breakpoint after run-stable user-message blocks is not measured; the
  `bedrock-claude` route's breakpoint is unmeasured; the Claude-direct search path reads only
  `cacheReadInputTokens`. Condition: a route selects a Claude path.
- The `boto3` region for Cohere and Claude comes from `AWS_REGION` alone (default `eu-west-2`), so a
  shell with another region sends the EU (European Union) profiles to the wrong region. Read the
  region from the route file. Condition: the next cleanup chore.
- `scoping_backend._call` turns the trace name into the route step (`longlist:discover` to
  `longlist_discover`), so a trace rename fails at call time. Pass an explicit `step=`. Condition:
  the next cleanup chore.
- Three `Retry-After` parsers (`tracing._retry_wait_s`, `embeddings._retry_after_s`,
  `fetch_live.retry_after_seconds`); only the last reads the HTTP-date form. Use one parser in
  `core`. Condition: the next cleanup chore.
- Record the response's request-id header on every traced attempt, and graph the free `AWS/Bedrock`
  `Invocations` metric against Langfuse's attempts, to diagnose the hangs. Condition: the next
  cleanup chore.
- Dependency direction: `core/tracing.py` imports Evidence search modules for its `*_score_summary`
  renderers (about 400 lines); the options scoping and API read models import each other. Move the
  renderers into their phase modules. Condition: the next cleanup chore.
- Bedrock hangs: the bare OpenAI SDK (software development kit) hangs on 10 to 17% of serial
  judge-sized calls, some returning after 2 to 4 minutes. The client, the pool and our wrapper are
  cleared; the cause is the provider's and unknown.

## Data model

- A `supersedes` link from a corrected re-upload to its predecessor: see
  [data-model.md](specs/system/data-model.md). Condition: the re-upload user experience is scoped.
- A quote that spans chunks writes one citation row per chunk. Condition: none recorded; the seam is
  a `citation_chunk` join table.
- `summary_status="pending"` is allowed but never written, so "in flight" and "never summarised"
  look the same. Condition: a consumer needs the difference.
- Every approved scoping plan version writes an `evidence_scope` row with `purpose = baseline`, also
  versions that never run. Condition: a retention rule is written; it must know these rows.
- `task_link` is unique per task pair. Condition: the options scoping full run links two tasks
  twice.
- `synthesis_result.synthesis_provenance`, `counts.groups_unsectioned_by_facet` and `event_log`
  payloads keep the old facet key `population` as history. Condition: a reader of stored history
  needs the new key.
- Migrations: the next revision that changes `finding_reference_union` must freeze a copy of the
  view's SQL (structured query language) in `f1b6d3a8c2e5`, as `c7e2a9f4b1d8` does. Condition: that
  revision.

## API (application programming interface)

- Hard purge (rows, snapshots, event history): delete is an idempotent archive. See [ADR
  0024](adr/0024-web-app-architecture.md). Condition: its own gated slice.
- A task's name comes from its question at creation and never from the planner's `plan.title`.
  Writing it back is new behaviour (which write wins, and when). Condition: none recorded.
- The chat pending cap is per acting user, so an organisation of N members can drive 2N chat turns
  at once on one task. Condition: the scaling task.
- Per-component progress is not durable: ticks are ephemeral by design. Condition: none recorded.
- One API instance and one worker process per environment. The live tail, ticks, the liveness hub's
  memory, the planning turn lock and the dispatch reservations (`_dispatching_tasks`,
  `_dispatch_lock`) are all process-local; a second replica turns the live line off silently, and a
  request's `finally` can clear a newer reservation. See [web-api.md](specs/system/web-api.md).
  Condition: the scaling task (LISTEN/NOTIFY or pub-sub, reservations as database rows).
- Tasks and projects page by offset over an order that moves while runs write, so a row can be
  skipped. See [web-api.md](specs/system/web-api.md) (the opaque `cursor` path). Condition: the
  scaling task, or cross-task listings.
- The live channel re-authorises and reads the durable tail on every wake-up: about ten database
  round trips a second per watching client. Condition: the scaling task; measure the feel first.
- `routers/task_agent.py` and `routers/conversations.py` bridge the event queue with
  `run_in_executor`, so each open stream holds one of six default threads on a 2-vCPU (virtual CPU)
  task. Condition: the scaling task; then the hub's bridge.
- `liveness._timer_schedule` starts a timer thread per coalesce window (about ten a second per
  streaming task). Condition: the scaling task; then one scheduler thread.
- The hub's lists (`search_queries`, `source_notes`, `claims`, `cards`) grow with the run, not to a
  cap. Condition: a run publishes thousands of items.
- `_source_reason_maps` reads the whole task event log per request. Condition: event logs grow; then
  payload-filtered SQL.
- Evidence and findings pages build the full task collection per request for a true `total_items`.
  Condition: task corpora grow tenfold.
- `DecisionOut.detail` passes the raw event payload; the client renders only allowlisted keys.
  Condition: a second consumer appears.
- `CheckInOut.bundle` is an open `dict`, so the generated client has no shape and
  `CheckInBundle.tsx` parses by hand. Condition: the bundle grammar settles; then a discriminated
  union per point.
- `TaskCreate.from_task_ids` allows ten links; each linked report can add up to 60,000 characters to
  every Task Agent turn. Condition: a real task needs more links; measure the prompt size.
- A `cursor=0` reconnect replays and maps the whole durable log, and there is no cap on open streams
  per user. Cap streams per user and task, and cap the replay. Condition: the scaling task.
- The planner turn takes its lock before authorisation, so a user who cannot read a task gets 409 or
  404 depending on the owner's activity. Resolve `accessible_task(write=True)` first. Condition: the
  next cleanup chore.
- Plan-patch routes in `routers/task_agent.py` return `detail=str(exc)` on a 422 (unprocessable
  entity), which echoes the caller's values and model names. Use the plain `validation_error` shape.
  Condition: the next cleanup chore.
- `archive_task_route` takes the dispatch lock and the task row in the reverse order to the openers:
  a latent deadlock. Condition: the next cleanup chore.
- The projects list computes last activity three times (a correlated subquery, then `_task_counts`
  twice). Use one grouped CTE (common table expression). Condition: the next cleanup chore.
- `ReferenceOut` has no `source_id`, so the References list opens dossiers by title and can miss.
  Add the field at the read model and run `make openapi-sync`. Condition: the next cleanup chore.

## Frontend

- Mobile: the chat panel is hidden below the md breakpoint with no stand-in; a `?chat=` link on a
  phone shows nothing. Condition: none recorded.
- The report's reference list shows names only; institutions appear in the citation sheet and the
  dossier. Condition: readers ask for them.
- Shortlist view: the route can turn a pick into "Added by you", but the view offers only Remove on
  a pick. A "Keep" control would expose it. Condition: an owner design call.
- No leave-and-return telemetry (PostHog is the later answer) and no notification channel (email
  through SES, Simple Email Service): see [ADR
  0044](adr/0044-live-activity-streamed-sections-one-copy-source.md). Condition: a later task.
- The "Most relevant sources" cards have an authors slot, but citations carry no authorships on the
  wire. Condition: the cards need bylines; then join the reference list's authorships.
- Plan document: mid-year scope dates show as bare years, so the day can be neither seen nor reset.
  Condition: this bites; then compare against the stored ISO date.
- `planOverlay.ts` lists the overlay keys in three places; a new plan field must go in all three.
  Condition: a fourth list appears; then consolidate.
- Re-run defect (seen once, not re-checked): when a re-run surfaces a new plan for review, the plan
  editor stays locked as during a run. Unlock it at the review step. Condition: the next cleanup
  chore.
- Re-run defect (seen once, not re-checked): after a re-run fails, the Result tab no longer reaches
  the earlier run's good artefact, which is intact in the database. Serve the last succeeded
  artefact when the latest run failed. Condition: the next cleanup chore.
- Result outline: the publisher-country list cuts to the top 8 (`ArtefactOutline.tsx`), so the bars
  can sum below the total and "Not reported" takes a slot. Add a "+N more" row. Condition: the next
  cleanup chore.
- `PublicTaskShell` and `AppShell`'s public branch each build the two-tab chrome by hand. Extract
  one task nav bar. Condition: the next cleanup chore.
- Mobile pass: list pages, the splash and the Sources sub-tab strip have none ("All sources" clips
  at 390 px); the task bar is tight at exactly 768 px. Condition: the next cleanup chore.
- The popover listbox is hand-rolled in three places (`FilterSelect`, `ProjectPicker`, the plan
  document pickers); only `FilterSelect` has the keyboard model and none has type-ahead. Make one
  `ui/` listbox. Condition: the next cleanup chore.
- Check the bottom bar's `env(safe-area-inset-bottom)` padding on real iOS Safari (tested in
  Chromium emulation only). Condition: the next cleanup chore.
- Eyebrow labels drift in weight and size; `artefactPresentation.ts` still hard-codes
  `tracking-[0.06em]` though `tracking-label` exists. One label component or class. Condition: the
  next cleanup chore.
- A theme heading's summary overflows at 390 px when every option sits under "No theme". Add
  `min-w-0` or wrap. Condition: the next cleanup chore.
- History view: every child walk's stage events sit beside the user's own actions. Add a filter.
  Condition: the next cleanup chore.
- Shortlist view: the "could not propose" notice stays until the next walk, even after the user
  changes places by hand. Keep the walk id in the view's state. Condition: the next cleanup chore.
- Result: a case study's result sentence turns bold only when the committed report lands. Carry
  `result_claim_id` on `artefact.section_card`. Condition: the next cleanup chore.
- Design leftovers: the Findings table keeps its own quote fallback; the Sources table draws its own
  tick and cross icons (`CitedMark`, `VerdictMark`); `auth/DevTokenLoginPanel.tsx` keeps two raw
  colours (auth changes need approval). Condition: the next cleanup chore.
- `finishAlerts.ts` misses a run that starts and ends between two polls (`before === null`). Alert
  on the latest run's identity. Condition: the next cleanup chore.
- `hasToc` means both "a theory of change task" and "a populated, checked theory" (`taskResult.ts`).
  Use two names. Condition: the next cleanup chore.
- After a sign-in round trip the URL can show the deep link while the landing route renders
  (`history.replaceState` is invisible to the router). Navigate in `onSigninCallback` (auth changes
  need approval). Condition: the next cleanup chore.
- The bottom bar's last tab sits flush against the 390 px edge on first paint (declined as
  cosmetic). Condition: none recorded.

## Accounts, organisations and administration

- The Cognito pool has no MFA (multi-factor authentication), so an admin account reads every
  organisation's rows behind a password alone. An accepted risk ([ADR
  0033](adr/0033-organisation-tenancy-and-global-admin-read.md)); MFA for `is_admin` holders alone
  is possible. Condition: before the first real organisation is enrolled in production.
- The admin audit trail has no durable sink: the in-app admin trace has one-month log retention, and
  ops CLI privilege changes print only to the operator's terminal (`rows assign` prints nothing).
  Options: a log subscription filter to long retention, and an `ops_audit` table. Condition: none
  recorded (raised with the DPIA, data protection impact assessment).
- There is no user deletion and no ownership transfer; they ship together. De-enrolment is the only
  lever: the person can still sign in, and erasure needs the Cognito side handled apart. Condition:
  a real user is offboarded or asks for erasure.
- The privacy notice disagrees with the product: § 7 promises permanent deletion, § 3 calls the
  email the only identifier (the `sub` is one too), and § 6 does not mention the admin read.
  Condition: the notice's owner reviews it.
- Invitations go out from Cognito's default sender (spam-prone, 50 a day). The fix is an SES (Simple
  Email Service) domain identity, the pool's `EmailConfiguration` and SES production access. `user
  create --invite manual` is the workaround. Condition: none recorded.
- There is no admin screen: `app_user.is_admin` is a global read grade. Condition: a dashboard or
  ops view is wanted; per-organisation admin turns this into a roles slice.
- Tasks from before ownership have `owner_user_id NULL`: the owner-scoped API cannot reach them, the
  admin listing shows them with no owner or organisation, and recovery is a manual database UPDATE.
  Condition: none recorded.
- Membership moves race task creation (`creator_org_id` is a non-locking read); the runbook rule is
  to re-confirm row visibility after a move. Condition: enrolment becomes frequent; then a database
  trigger.
- `admin grant` refuses a subject with no organisation, so every admin is enrolled somewhere.
  Condition: an organisation-less admin is wanted; then an org-less enrol mode.
- An idle admin event stream writes one trace line per 0.4-second poll. Condition: log cost bites;
  then widen the poll, never drop the grain.
- Nothing detects an email changed in Cognito; `user resync --email` is manual. Condition: none
  recorded.

## Infrastructure and deployment

- Bedrock uses a long-term API key owned by an IAM (identity and access management) user; AWS says
  such keys are for exploration. Replace it with short-term keys or SigV4 signing. Condition: its
  own approval-gated task.
- The VPC (virtual private cloud) runs three NAT (network address translation) instances, one per
  availability zone, not the single instance the network stack's comment describes. Condition: an
  owner call on cost against zone resilience.
- No formal SLO or SLA (service-level objective or agreement), incident process, canary deploys,
  live drift monitors or product analytics. Condition: none recorded.
- Metabase on staging has no Policy Atlas data source: direct table access would bypass the API's
  owner scoping. A follow-up needs curated views or row-level controls and a least-privilege read
  role. Condition: an approved analytics need.
- Metabase uses its own accounts (no single sign-on or embedding), and `deploy_analytics` is
  fail-closed outside staging. Condition: an authentication and product decision; production needs a
  capacity, backup and ownership review.
- Actions runs are serialised per environment, but a local recovery or bootstrap can still
  interleave with them (parallel Alembic runs). The runbook asks for human coordination. Condition:
  unattended local operations or a second deploy system; then a lease and an Alembic advisory lock.
- `infra/infra/components/ingest_worker.py` sets `MAX_CONCURRENCY = 20`: embedding binds the stage
  while the Bedrock embedding quota is about 650,000 tokens a minute, and each copy holds a
  connection on the `db.t3.medium` writer. Condition: AWS raises the quota; measure queue waits and
  free connections, then raise the cap.
- `scripts/prune_unlinked_snapshots.py` runs by hand (dry run by default). Condition: the document
  store's growth is measured on staging; then a scheduled run.
- The public waitlist route has field caps, one row per email and a honeypot only. Condition: real
  spam appears; then a WAF (web application firewall) rate rule, no app code.
- The dead-letter, NAT traffic and writer CPU-credit alarms have no notification action (no SNS,
  Simple Notification Service, topic). Add one topic with an email subscription (an infra change
  needs approval). Condition: the next cleanup chore.
- The staging inspection secret's password no longer matches the database. Rotate it and update the
  secret. Condition: the next staging session.
- Owner checks after deploy: parse wall time on staging (2 CPUs), chunk quality of the XML route on
  live documents, the 60-second timeout on the long extraction and vetter steps, and saved Metabase
  questions and Langfuse filters that the renames broke. Condition: the next staging session.

## Observability (Langfuse)

- Langfuse follow-ons: prompt-registry deployment (labels, environments), retention, sampling,
  masking and access policies, and promoting traces to eval datasets. Condition: none recorded.
- Traces hold full input and output, including fabricated quotes the domain model later excludes.
  Condition: trace access widens beyond the operator; then a redaction policy.
- The dev agent CLI (command-line interface) groups its traces by conversation id, because it mints
  the conversation before the task exists. Condition: CLI traces must group with a task.
- A streamed turn cut by the between-chunks timeout records no usage; Langfuse shows an error
  generation with no tokens. Condition: none recorded.
- The theory of change consolidate call routes as `toc_merge` but its tokens land in the
  `toc_discover` component, so the walk's cost under-reports. One component per model call.
  Condition: the next cleanup chore.
- `cost_per_run.py` pages every trace to resolve a session prefix (about 40 seconds a session).
  Filter by `sessionId`. Condition: the next cleanup chore.

## Evaluations

- The search ground truth has 34 references with no DOI (digital object identifier) and no Overton
  id, so every recall number is scholarly recall only. Label `overton_id` (the gap-map rows hold
  about 9,500 grey-literature studies), then add the `overton` arm. Condition: the owner's
  ground-truth expansion.
- Shortlist recall as the eval measure: was the option the assessment later finds best on the
  shortlist? Condition: the options scoping assessment.
- The replay tool: running `suggest --fresh` before `longlist --fresh` on a clone makes the clone's
  options count as seeds. Reset the clone per round for the option stages. Condition: the next
  cleanup chore.
- Rerank-quality evals (deterministic against model reranking; listwise ordering). Select runs only
  at standard and deep depth. Condition: none recorded.
- Extraction-quality evals (finding-level ground truth) and a probe of planner narrowing across
  phrasings. No stored run had extraction. Condition: none recorded.
- Measure the survivorship skew: abstract-only documents cannot be ejected after stage 1. Condition:
  none recorded.
- Thumbs feedback as Langfuse scores (the gold-set seam). Condition: none recorded.
- Gate sort and baseline template checks: mixed utterances against the gate sort, and whether the
  reasoning label should show in the prose. Condition: none recorded.
- Read the feature rule on the whole tuning set with a from-scratch replay (a clone with its option
  rows dropped). Condition: none recorded.
- Upload `results/cache/` (about 25 MB) to S3; today `--refresh` is the only recovery and Consensus
  bills every call. Condition: the results are cited.
- A ranking-stability test (about USD 0.50 per review per repeat). Condition: a recall difference of
  a point or two must be told from noise.
- Seminal-decile recall as a Langfuse score. Condition: the ground truth carries citation counts per
  reference.
- Theory of change evals E1, E2 and E6 did not run (the ground-truth and plausibility evals did).
  Condition: none recorded.
- Screening eval seed: the V2 baseline (13,740 documents; recall 0.836, precision 0.634, work saved
  over sampling at 95% recall 0.187; recall 0.400 on hard corpora). Every deep run stores stage-1
  and stage-2 label pairs. First calibration question: should a no-information document sit at the
  corpus base rate instead of 0.5?
- Search eval sources to reuse: PaperFindingBench, SYNERGY, CODEC policy topics, a Campbell, 3ie and
  EPPI golden dataset, OpenAlex `sample` with `seed`, AstaBench cost-normalised scoring and MetaSyn
  stage-attributed metrics. The screen judge's quality is the search's biggest unmeasured dependency
  ([ADR 0012](adr/0012-depth-graded-agentic-search.md)).

## Test suite

- The pool convergence test measures the fake's timing (`_QuotaFakeBackend` holds 0.2 seconds).
  Condition: the pool changes next; then a virtual clock.
- `delete_task_data` (`tests/helpers.py`) deletes snapshots another task still references, so
  `test_longlist_routes` builds its add fixture without the link. Condition: a test needs a shared
  snapshot.
- `test_option_search.py`: a thread-join test stalls at 0% CPU under load and has cost 40-minute CI
  (continuous integration) runs. Put a timeout on that join, and capture a stack dump (`pytest -o
  faulthandler_timeout=110`) if it recurs. Condition: the next cleanup chore.
- Older migration round-trip tests (`test_screen_step_rename_migration`, `test_search_migration`,
  `test_synthesis_refinement_migration`, `test_schema`'s downgrade) still churn columns on a
  long-lived database. Move them to the scratch-database pattern. Condition: the next cleanup chore.
- Worker test databases (`policy_atlas_test_gw<N>_<pid>`) survive a hard kill. Sweep names whose
  process is dead at suite start. Condition: the next cleanup chore.
- `test_option_searches_run_at_the_configured_width` measures concurrency with sleeps and fails
  under heavy load. Use a barrier. Condition: the next cleanup chore.
- Test helpers: an IOF record factory beside `make_icf_wire_record`, one shared fake Langfuse, and a
  `capturing_fetch` factory. Condition: the next cleanup chore.
- Add a race test: Start against an older approved plan while a newer planning turn is pending
  (Start is disabled while a turn streams). Condition: the next cleanup chore.
- A router replacement can ask for a same-generation `screen_full` re-screen, which halts the batch
  (`ScreenSupersessionError`). Pin a test and decide the partial-batch rule. Condition: the next
  cleanup chore.
- The frontend mirrors the screening caps (`SCREENING_CRITERION_MAX` and others) with no
  cross-language test. Add one. Condition: the next cleanup chore.
- Theory of change write and upload routes lack the same-organisation colleague case. One
  parametrised matrix over the router's write routes. Condition: the next cleanup chore.
- The mock API (`frontend/src/mock/api.ts`) has no public mode and covers project mutations only in
  part. Condition: the next cleanup chore.
- Race tests with barriers for the theory of change compare-and-apply (row-revision unit tests cover
  it). Condition: none recorded.
- `test_admin_leg.py::test_administrator_reads_a_null_organisation_row_and_an_ownerless_one` failed
  once on a polluted baseline. Condition: it recurs.
- An OS-level (operating system) CI egress guard such as `unshare -n`; the socket-deny guard and the
  import guard stand. Condition: none recorded.

## Agent harness and repository tooling

- Repository-root `scripts/*.py` are outside mypy (`backend/pyproject.toml` checks `src` and
  `tests`). Add `scripts/` or move long-lived scripts under `policy_atlas/ops`. Condition: the next
  cleanup chore.
- Stale text in pinned prompt files: `agent_prompt.py`'s docstring cites `planner_prompt.py` and
  `planner_v5`; `baseline_prompt.py` names `synthesis_backend.py` as the shared core's home;
  `task_agent_toc_prompt.py` says "Suggestions, above the canvas". Condition: the next deliberate
  re-pin (lead-only).
