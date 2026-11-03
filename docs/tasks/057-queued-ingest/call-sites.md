# Task 057 — model call sites, their timeouts and their retries (plan Phase 1 step 1)

Read from the code on 2026-11-03, before the Phase 1 sweep (contract D12, N10c; plan P1).
Paths are under `backend/src/policy_atlas/`. This is the input to the sweep (Phase 1
step 3) and to the lead's Bedrock overrides (step 4).

## What the words mean

- **Step**: one named model call site in the route file (`model_routes.toml`,
  `[steps]`). Each step now carries `timeout_s`: how many seconds one request may take
  before the app gives up on it.
- **Timeout today**: the `timeout=` the call site's OpenAI client was built with before
  this task. It is now written into `[steps.<name>] timeout_s` unchanged, so the
  `openai-direct` route behaves as before. The loader test
  (`backend/tests/core/test_model_routes.py::test_every_step_carries_todays_timeout`) and
  the request fixture (`backend/tests/core/data/call_site_kwargs_056.json`, a new
  `timeout` field per site) pin each value.
- **max_retries today**: how many times the OpenAI library itself silently re-sent a
  failed request (timeouts, dropped connections, 429 "too many requests", 5xx server
  errors). These retries were billed but never traced. From Phase 1 every client is
  built with `max_retries=0`.
- **Retry handling today** (on top of the library's): "SDK only" = nothing else;
  "CallBudget loop" = the caller re-runs failed calls under a fixed call ceiling;
  "own loop" = some other caller-side retry, described.
- **Decision** for the sweep:
  - `wrap`: the site's generation is opened by `tracing.traced_attempts` (one traced
    retry; each attempt its own Langfuse generation with `step`, `attempt` and a shared
    `logical_call_id`, set before the request goes out). Any caller loop stays as it is.
  - `budgeted`: keep the caller's loop as the only retry; the site gets the per-request
    timeout and `max_retries=0` only.
  - `exempt-stream`: streamed chat; per-request timeout only, no wrapper.

## One client, several steps

Several clients serve more than one step with one timeout literal. The literal now sits
on **each** step in `[steps]`, so a route can later change one step without the others:

| Client (builder) | Literal | Steps that share it |
|---|---|---|
| `OpenAISearchGenerationBackend` (`evidence_search/sourcing/search_generation.py:159`) | 60 s, 2 retries | the 7 `search_*` steps (V2 inherits the client) |
| `OpenAIScreeningBackend` (`evidence_search/assess/screening_backend.py:109`) | 60 s, 2 | `screen_abstract`, `screen_full` |
| `OpenAIThemeGroupingBackend` (`evidence_search/corpus/theme_grouping.py:329`) | 60 s, 2 | `characterise_discover`, `characterise_assign` |
| `OpenAIGroupClusteringBackendFactory` (`evidence_search/group/group_clustering.py:344`) | 120 s, 2 | `group_discover`, `group_assign` |
| `OpenAISynthesisBackend` (`evidence_search/synthesis/synthesis_backend.py:719`) | 120 s, 2 | 7 steps: `synthesise_propose_sections`, `_write_block_summary`, `_write_artefact_summary`, `_judge_summary`, `_section_turn` (section turns **and** the repair), `_write_key_findings`, `_write_case_studies` |
| `MRSNoteWriter` / `FullReportIntroWriter` (`synthesis_backend.py:1277`, `:1332`, built per call) | 30 s, **1** retry | `synthesise_write_source_note`, `synthesise_write_intro` |
| `OpenAIChatBackend` (`runtime/chat_backend_openai.py:55`) | 120 s, 2 | `chat` (tool turn, prose stream, final parse) |
| `OpenAIAgentBackend` (`runtime/agent_backend.py:400`) | 60 s, 2 | the 7 `agent_*` steps |
| `OpenAITaskAgentBackend` (`runtime/task_agent.py:205`) | 60 s, 2 | `task_agent_turn`, `task_agent_scoping_turn` |
| `OpenAILonglistBackend` (`options_scoping/scoping_backend.py:476`) | 60 s, 2 | the 9 `longlist_*` and 6 `option_profile_*` steps |

Single-step clients: classification 60 s, ranking 60 s, IOF extraction 120 s, ICF
extraction 120 s, interventions 60 s, IOF vetter 120 s, ICF vetter 120 s, relevance
annotator 60 s, grounding judge 120 s (all 2 retries).

## The table: 58 OpenAI call sites

"Obs." is the Langfuse observation name (unchanged by this task: saved views depend on
it). Every row's request now sends `timeout=route().timeout_for(<step>)`; the column
"Timeout today" is that value on both routes until the lead's Bedrock overrides.

### Evidence search: assess, corpus, group

| Module | Function | Obs. | Step | Timeout today | max_retries today | Retry handling today | Decision |
|---|---|---|---|---|---|---|---|
| `evidence_search/assess/classification_backend.py` | `OpenAIClassificationBackend.classify` | `classify:document` | `classify_document` | 60 | 2 | own loop: `classify._run_classification_calls` re-runs each failed doc once, serially after the pool (no budget) | wrap |
| `evidence_search/assess/screening_backend.py` | `OpenAIScreeningBackend.screen_envelope` | `screen:abstract` | `screen_abstract` | 60 | 2 | CallBudget loop: `screen._run_stage1_calls`, `SCREEN_RETRY_CAP`, failed reps re-run serially after each batch | wrap |
| `evidence_search/assess/screening_backend.py` | `OpenAIScreeningBackend.screen_fulltext` | `screen:full` | `screen_full` | 60 | 2 | CallBudget loop: `screen._run_stage2_reps`, serial re-run after the pool | wrap |
| `evidence_search/corpus/ranking.py` | `OpenAIRankingBackend.rank` | `select:rerank` | `select_rerank` | 60 | 2 | CallBudget loop: `select._rerank_infos`, one serial re-run per failed batch, then fallback | wrap |
| `core/tracing.py` (client in `corpus/theme_grouping.py`) | `TracedThemeGroupingBackend.discover` → `OpenAIThemeGroupingBackend.discover` | `characterise:discover` | `characterise_discover` | 60 | 2 | own loop: clustering engine `_discover_labels`, `DISCOVERY_RETRY_CAP = 1`, immediate, on any error or invalid output, under a raise-on-exceed budget | wrap (opened with `_observation`, not `traced_call`) |
| `core/tracing.py` (client in `corpus/theme_grouping.py`) | `TracedThemeGroupingBackend.assign` → `OpenAIThemeGroupingBackend.assign` | `characterise:assign` | `characterise_assign` | 60 | 2 | own loop: clustering engine repair rounds for failed batches, raise-on-exceed budget | wrap (opened with `_observation`) |
| `evidence_search/group/group_clustering.py` | `_OpenAIGroupFacetBackend._call` (`discover`) | `group:discover` | `group_discover` | 120 | 2 | own loop: clustering engine, `GROUP_DISCOVERY_RETRY_CAP = 1`, as characterise | wrap |
| `evidence_search/group/group_clustering.py` | `_OpenAIGroupFacetBackend._call` (`assign`) | `group:assign` | `group_assign` | 120 | 2 | own loop: clustering engine repair rounds | wrap |

### Evidence search: extract

| Module | Function | Obs. | Step | Timeout today | max_retries today | Retry handling today | Decision |
|---|---|---|---|---|---|---|---|
| `evidence_search/extract/extraction_backend.py` | `OpenAIExtractionBackend.extract` | `extract:iof_findings` | `extract_iof_findings` | 120 | 2 | CallBudget loop: `extract._run_windows`, `EXTRACT_RETRY_CAP = 1`, serial re-run after the pool | wrap |
| `evidence_search/extract/extraction_backend.py` | `OpenAIICFExtractionBackend.extract` | `extract:icf_findings` | `extract_icf_findings` | 120 | 2 | CallBudget loop: as IOF | wrap |
| `evidence_search/extract/extraction_backend.py` | `OpenAIInterventionsBackend.extract` | `extract:interventions` | `extract_interventions` | 60 | 2 | CallBudget loop: as IOF (shared pipeline) | wrap |
| `evidence_search/extract/finding_vetter.py` | `_judge_via_openai` (from `OpenAIFindingVetterBackend.judge`) | `extract:vet_iof_findings` | `extract_vet_iof_findings` | 120 | 2 | SDK only (a failure degrades the document's vetting) | wrap |
| `evidence_search/extract/finding_vetter.py` | `_judge_via_openai` (from `OpenAIICFFindingVetterBackend.judge`) | `extract:vet_icf_findings` | `extract_vet_icf_findings` | 120 | 2 | SDK only | wrap |
| `evidence_search/extract/relevance_annotator.py` | `OpenAIRelevanceAnnotatorBackend.annotate` | `extract:annotate_relevance` | `extract_annotate_relevance` | 60 | 2 | SDK only | wrap |

### Evidence search: search (one client)

| Module | Function | Obs. | Step | Timeout today | max_retries today | Retry handling today | Decision |
|---|---|---|---|---|---|---|---|
| `evidence_search/sourcing/search_generation.py` | `OpenAISearchGenerationBackend.generate_queries` → `_call_wire` | `search:generate_queries` | `search_generate_queries` | 60 | 2 | SDK only | wrap (at `_call_wire`, which now takes `step`) |
| same | `OpenAISearchGenerationBackend.reformulate` → `_call_wire` | `search:reformulate` | `search_reformulate` | 60 | 2 | SDK only | wrap |
| same | `OpenAISearchGenerationBackend.suggest` → `_call_wire` | `search:suggest` | `search_suggest` | 60 | 2 | SDK only | wrap |
| same | `V2SearchGenerationBackend.generate_queries` → `_generate_many` → `_call_wire` | `search_queries_v2_openalex:<n>` | `search_queries_v2_openalex` | 60 | 2 | SDK only | wrap |
| same | as above, Overton half | `search_queries_v2_overton:<n>` | `search_queries_v2_overton` | 60 | 2 | SDK only | wrap |
| same | `V2SearchGenerationBackend.reformulate` → `_generate_many` | `search_reformulate_v2_openalex:r<k>:<n>` | `search_reformulate_v2_openalex` | 60 | 2 | SDK only | wrap |
| same | as above, Overton half | `search_reformulate_v2_overton:r<k>:<n>` | `search_reformulate_v2_overton` | 60 | 2 | SDK only | wrap |

### Evidence search: synthesise and judge

All requests build their kwargs through `_step_kwargs(step)` (`synthesis_backend.py:133`),
which now adds `timeout_s=route().timeout_for(step)`; the grounding judge calls
`openai_kwargs(...)` directly.

| Module | Function | Obs. | Step | Timeout today | max_retries today | Retry handling today | Decision |
|---|---|---|---|---|---|---|---|
| `evidence_search/synthesis/synthesis_backend.py` | `OpenAISynthesisBackend.propose_sections` (`completions.parse`) | `synthesise:propose_sections` | `synthesise_propose_sections` | 120 | 2 | own loop: a rejected proposal gets one repair call (`synthesise.py`), a semantic repair, not a transport retry | wrap |
| same | `write_block_summary` (block) | `synthesise:write_block_summary` | `synthesise_write_block_summary` | 120 | 2 | own loop: `synthesise.py` summary regenerate (`SUMMARY_REGENERATE_CAP`); a provider error degrades the summary | wrap |
| same | `write_block_summary` (artefact) | `synthesise:write_artefact_summary` | `synthesise_write_artefact_summary` | 120 | 2 | as above | wrap |
| same | `judge_summary` | `synthesise:judge_summary` | `synthesise_judge_summary` | 120 | 2 | as above | wrap |
| same | `section_turn` (`completions.create`, tools; inside `run_tool_loop`) | `synthesise:section_turn` | `synthesise_section_turn` | 120 | 2 | SDK only per turn; an escaped error fails the section and then the runner's component retry (`runner.py`, `COMPONENT_RETRY_CAP`) | wrap |
| same | `repair_section` (`completions.create`, forced tool) | `synthesise:repair_claims` | `synthesise_section_turn` (shared, D10) | 120 | 2 | SDK only | wrap |
| same | `write_key_findings` (`completions.create`, forced tool) | `synthesise:write_key_findings` | `synthesise_write_key_findings` | 120 | 2 | SDK only | wrap |
| same | `write_case_studies` (`completions.parse`) | `synthesise:write_case_studies` | `synthesise_write_case_studies` | 120 | 2 | SDK only | wrap |
| same | `write_source_note` (own client) | `synthesise:write_source_note` | `synthesise_write_source_note` | 30 | **1** | SDK only | wrap (one traced retry = today's count) |
| same | `write_full_report_intro` (own client) | `synthesise:write_intro` | `synthesise_write_intro` | 30 | **1** | SDK only | wrap |
| `evidence_search/synthesis/grounding_judge.py` | `OpenAIGroundingJudgeBackend.judge_block` | `judge:grounding` | `judge_grounding` | 120 | 2 | SDK only | wrap |

### Conversation and agents

| Module | Function | Obs. | Step | Timeout today | max_retries today | Retry handling today | Decision |
|---|---|---|---|---|---|---|---|
| `runtime/chat_backend_openai.py` (observation in `api/answer_core.py`) | `OpenAIChatBackend._tool_turn` (`completions.create`, tools) | `chat:call` | `chat` | 120 | 2 | SDK only | exempt-stream (see note 1) |
| same | `_stream_then_parse` step 1 (`completions.create`, `stream=True`) | `chat:call` | `chat` | 120 | 2 | SDK only (before the first chunk) | exempt-stream |
| same | `_stream_then_parse` step 2 (`completions.parse`) | `chat:call` | `chat` | 120 | 2 | SDK only | exempt-stream |
| `runtime/agent_backend.py` | `OpenAIAgentBackend.route` → `_parse` → `traced_parse` | `agent:route` | `agent_route` | 60 | 2 | SDK only | wrap (done: `traced_parse` runs under `traced_attempts`) |
| same | `triage` | `agent:triage` | `agent_triage` | 60 | 2 | SDK only | wrap (done) |
| same | `decide` | `agent:decide` | `agent_decide` | 60 | 2 | SDK only | wrap (done) |
| same | `sort_gate_turn` | `agent:gate_sort` | `agent_gate_sort` | 60 | 2 | SDK only | wrap (done) |
| same | `sort_longlist_turn` | `agent:longlist_sort` | `agent_longlist_sort` | 60 | 2 | SDK only | wrap (done) |
| same | `propose_option_design` | `agent:option_design` | `agent_option_design` | 60 | 2 | SDK only | wrap (done) |
| same | `suggest_options` | `agent:suggest` | `agent_suggest` | 60 | 2 | SDK only | wrap (done) |
| `runtime/task_agent.py` | `OpenAITaskAgentBackend.turn` (evidence-search profile) → `traced_parse` | `task_agent:turn` | `task_agent_turn` | 60 | 2 | SDK only | wrap (done) |
| same | `turn` (options-scoping profile) | `task_agent_scoping:turn` | `task_agent_scoping_turn` | 60 | 2 | SDK only | wrap (done) |

### Options scoping (one client, `OpenAILonglistBackend._call` → `traced_parse`; step = observation name with `:` as `_`)

All 15 rows: timeout 60 s, `max_retries` 2, retry handling "own loop:
`options_scoping/model_calls.call_with_retry`, `CALL_ATTEMPTS = 2`, an immediate retry on
any error or malformed answer" (the "stall retry"), decision **wrap (done, through
`traced_parse`)**.

| Function | Obs. | Step |
|---|---|---|
| `discover` | `longlist:discover` | `longlist_discover` |
| `assign` | `longlist:assign` | `longlist_assign` |
| `discover_themes` | `longlist:themes` | `longlist_themes` |
| `assign_themes` | `longlist:assign_themes` | `longlist_assign_themes` |
| `type_options` | `longlist:type` | `longlist_type` |
| `constrain` | `longlist:constrain` | `longlist_constrain` |
| `distinct` | `longlist:distinct` | `longlist_distinct` |
| `authority` | `longlist:authority` | `longlist_authority` |
| `propose_shortlist` | `longlist:shortlist` | `longlist_shortlist` |
| `profile_line` | `option_profile:line` | `option_profile_line` |
| `profile_potential_impact` | `option_profile:potential_impact` | `option_profile_potential_impact` |
| `profile_ambition` | `option_profile:ambition` | `option_profile_ambition` |
| `profile_setting` | `option_profile:setting` | `option_profile_setting` |
| `fold` | `option_profile:fold` | `option_profile_fold` |
| `place_sentences` | `option_profile:place_sentences` | `option_profile_place_sentences` |

## Clients that are not route steps

| Module | Function | Obs. | Timeout today | Retries today | Phase 1 change | Decision |
|---|---|---|---|---|---|---|
| `core/embeddings.py:189` | `OpenAIEmbeddingBackend._create_embeddings_with_backoff` (`embeddings.create`) | `embed:*` (embedding, via `TracedEmbeddingBackend`) | 30 (client) | SDK 2 + own loop: 4 logical attempts on `RateLimitError` with backoff | `max_retries=0`; the 30 s moves onto each request as `OPENAI_EMBEDDING_TIMEOUT_S`; the 429 loop stays | budgeted (own loop) |
| `core/embeddings.py:257` | `CohereEmbeddingBackend._invoke_model_with_backoff` (boto3 `invoke_model`) | `embed:*` | botocore default (60 s read) | botocore legacy default (up to 4 retries) + own loop: 4 attempts on `ThrottlingException` | `Config(read_timeout=60, retries={"mode": "standard", "max_attempts": 1})` (`BEDROCK_CLIENT_CONFIG`) | budgeted (own loop) |
| `evidence_search/sourcing/search_generation.py:335` | `ClaudeSearchGenerationBackend.generate_queries` (boto3 `converse`) | `search:generate_queries` | botocore default | botocore legacy default | the same `BEDROCK_CLIENT_CONFIG` | exempt (boto; no route step; only the unused `bedrock-claude` route selects it) |

## Notes for the sweep and the lead

1. **Chat loses its retries.** The seam builds every client with `max_retries=0`, and the
   `chat` step is exempt from the wrapper, so the chat tool turn and the final parse are
   no longer retried at all on a 429, 5xx or dropped connection (before: up to 2 silent
   SDK retries). The stream itself was only ever retried before its first chunk. If that
   matters, the smallest fix is to wrap `_tool_turn`'s `create` and the final `parse` in
   `traced_attempts` inside `chat_backend_openai.py` (neither has sent text to the user
   yet), keeping `chat:call` as it is; the stream stays exempt.
2. **Why `wrap`, not `budgeted`, for the sites with a caller loop** (screen, select,
   extract, classify, characterise, group, scoping). Before this task the SDK retried a
   timed-out request at once, inside the worker thread. `wrap` keeps that one immediate
   retry (now traced). `budgeted` would move the stall's retry to the caller's loop,
   which for classify, screen, select and extract runs **serially after the whole
   batch**, so each stall would add a full serial call to the stage wall. Attempts per
   logical call fall from at most 3 (SDK) to at most 2; the caller budgets count logical
   calls and are unchanged, so worst-case HTTP attempts are 2 × budget instead of 3 ×.
   `wrap` is also what lets the measurement pair a cut-off attempt with its retry
   (`logical_call_id`). A site can be flipped to `budgeted` row by row if the lead
   prefers.
3. **Where the sweep switches to `traced_attempts`** (everything marked plain `wrap`
   above; the `traced_parse` rows are already done): 23 call expressions —
   `tracing.traced_call(..., as_type="generation")` at classification, screening (×2),
   ranking, extraction (×3), finding vetter (`_judge_via_openai`), relevance annotator,
   group clustering (`_call`), search generation (`_call_wire`), grounding judge,
   synthesis (×9: propose, block/artefact summary, judge summary, section turn, repair,
   key findings, case studies, source note, intro), plus the two raw
   `_observation(..., as_type="generation")` blocks in `core/tracing.py`
   (`TracedThemeGroupingBackend.discover`/`assign`). Each passes `step=` (the helpers
   that funnel several steps already take one: screening `_parse_once`, finding vetter
   `_judge_via_openai`, search generation `_call_wire`/`_generate_many`, group
   clustering `_STAGE_STEP[stage]`). The list is machine-checked by
   `backend/tests/core/test_step_timeout_sites.py::test_only_traced_attempts_opens_generations_outside_the_exempt_sites`,
   marked `xfail(strict=True)` until the sweep lands; the sweep removes the marker.
4. The source note and intro had `max_retries=1` (one retry), the others 2: under the
   wrapper every wrapped site gets one traced retry.
