# Verification: 053-bedrock-local-route

Evidence for the build of [contract.md](contract.md) against [plan.md](plan.md). Filled
during the build (2026-10-14); the review sections are added by the review conversation.
Public-safe: no keys, no `.env`, no traces beyond token counts and model ids.

## Build-time deviations (flagged, not silent)

`dev` was merged into the branch between design (2026-09-25) and build (2026-10-14),
bringing tasks 046 to 052. Four facts in the contract moved. Each was resolved within the
contract's own vocabulary and is recorded in the contract's build-time note:

1. **A fourth text tier, `fast`.** Task 051 put stage-1 screening and the three
   search-generation steps on gpt-5.6-luna while fourteen steps stayed on gpt-5.4-mini.
   The route file's `[steps]` table maps those four to a new tier `fast`, so the default
   route still reproduces every pre-053 value. On the Bedrock routes `mini` and `fast`
   both resolve to Luna.
2. **Agent triage no longer follows screen.** Task 051 made its default a literal. Only
   the case-studies "follows synthesis" rule remained, and it is retired with the
   variables.
3. **Six pinned prompt modules changed hash, not five.** `chat_prompt.py` became a pinned
   module after the design. Every one of the six diffs is an import line plus the
   constant line (§ Diff summary).
4. **ADR renumbered to 0039.** Task 051 took 0038. (Renumbered again to 0041 at the dev
   merge, deviation 6.)
5. **The `reasoning_effort` knob is keyed by model id, not by the `standard` tier**
   (found by the contract verifier at review, 2026-10-14; the build recorded the reason
   under § Intent & assumptions but did not flag it). Keyed by model id because that is
   what the code compared before, so the default route is byte-identical, and because a
   step exception can name a model directly. ADR 0041 decision 3 and the contract's
   build-time note now say so.

6. **Task and ADR renumbered at the dev merge (2026-10-21).** The options-scoping branch
   (PR #69, merged 2026-10-15) had taken task number 045 and ADR 0039. This slice is now
   `053-bedrock-local-route` with ADR 0041; every citation on this branch was swept on the
   lines this branch added (not dev's), the branch name `aws-bedrock-integration` stays.
7. **Options scoping folded into the route file (2026-10-21).** See § Post-merge
   integration below.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (Phase 0 baseline, before any change) | pass | backend 2618 passed in 6:05; mypy 311 files; frontend 617 tests; infra 86 |
| `make verify-fast` (Phase A gate) | pass | backend 2635 passed in 5:51 (17 new loader tests); mypy 313 files; ruff clean |
| `make prompt-guard` (Phase A gate) | pass | 16 pins unchanged after the re-pin of six |
| `make audit` (Phase A gate, after the lock change) | pass | no known vulnerabilities |

| `make verify` (gate 2, end of Phase B, first run) | **fail**, 17 of 2648 | Two root causes, both in tests: (1) `FakeEmbedder` in `test_synthesis_tools.py` kept the old `embed_texts` signature, 16 failures; (2) `test_image_hygiene.py` pinned "the image ships no AWS SDK", a premise the approved dependency move overturned, 1 failure. See § Test changes. |
| `make verify` (gate 2, re-run) | pass | backend 2648 passed in 7:00; mypy 313; prompt-guard 17 pins unchanged; frontend 617 |
| `make verify-fast` + `make prompt-guard` (Phase C gate) | pass | backend 2654 passed in 6:07 (6 new Claude tests); 17 pins unchanged |
| `make verify` + `make audit` (gate 3, step-6 exit) | pass | backend 2654 passed in 6:13; mypy 313; prompt-guard 17; frontend 617; no known vulnerabilities |
| `make verify` (step 7 entry, fresh review conversation, before any fix) | pass | backend 2654 passed in 6:05; mypy 313; ruff clean; frontend 617; infra 86; okf 153 concepts; prompt-guard green |
| `make verify` + `make audit` (step 7 exit, after the review fixes) | see § Review findings § Gate after fixes | |
| `uv run --env-file .env python probe_key_env.py` (2026-10-21, post-review addition) | pass | `POLICY_ATLAS_MODEL_ROUTE=bedrock-local` with `OPENAI_API_KEY` set to a dummy value: route names `AWS_BEARER_TOKEN_BEDROCK`, the client carries that key, Luna on Bedrock replied `ok` |
| `make verify` (2026-10-21, post-review addition) | interrupted at 64% by the owner for the dev merge; route tests 27 passed, ruff + mypy clean on touched files; the full gate re-runs after the merge | `make okf-validate`: 156 concepts, 0 violations |
| `python3 scripts/prompt_hash_guard.py --update` (2026-10-21, dev merge) | pass | 7 modules re-pinned: the six 045 re-pins merged with dev's prompt edits, plus `extract_interventions_prompt.py` (constant now reads the route) |
| `uv run --env-file backend/.env python probe_sol.py` (2026-10-21, dev merge) | pass | `bedrock-local`: `task_agent_scoping` and `longlist_judgment` resolve to `global.openai.gpt-5.6-sol`; plain reply `Ok.` in 1.2 s (9 in, 6 out); structured parse of a two-field schema in 1.6 s, no knob |
| `make verify` + `make audit` (2026-10-21, after the dev merge) | pass (second run; the first found the four merge losses above) | backend 3638 passed in 9:28; mypy 420 files; infra 93; frontend 882; prompt-guard 36 unchanged; okf 178 concepts; audit: no known vulnerabilities after the certifi bump |
| `drive_scoping.py` + `wait_longlist.py` against `make dev` on `bedrock-local` (2026-10-21, live check 4: options scoping) | pass | task `365d5eb5`, "interventions to reduce obesity", England, rapid: two Task Agent turns on Sol (11 s, 8 s) approved plan v1; baseline walk 90 s to its first steering pause, 3.5 min to the `baseline_confirm` gate (artefact written, 8 blocks); confirm decision 1 s opened the longlist walk; longlist walk 14 min 45 s, `succeeded`: 20 options in 6 themes, 20 included, 0 excluded, 0 without in-scope evidence; about 810 model calls (323 screen, 193 classify, 156 intervention extractions, 11 query generations, the longlist and profile calls), 2.80 M prompt + 0.38 M completion tokens, 26 Cohere batches, 0 errors |

### Phase B (Cohere embeddings), diff summary

- `core/embeddings.py`: `CohereEmbeddingBackend` (InvokeModel on the route's model,
  batches of 96, `truncate = "NONE"`, 1536-length check, count check, token count from
  the `x-amzn-bedrock-input-token-count` header parked for the tracing wrapper, retry
  only on `ThrottlingException`); `EmbeddingBackend.embed_texts` gains
  `kind="document" | "query"`, ignored by the stub and OpenAI classes;
  `API_BATCH_SIZE` 128 to 96; `live_embedding_backend()` chooses the class from the
  route.
- `core/tracing.py`: the Langfuse wrapper accepts `kind`, forwards it, records
  `input_kind` in the span metadata.
- `evidence_search/synthesis/synthesis_tools.py`: the two query-embedding calls pass
  `kind="query"`. Two lines; nothing else in the file changed.
- `runtime/agent.py` and `api/deps.py`: the hard-coded `OpenAIEmbeddingBackend()` calls
  become `live_embedding_backend()`, so the command line and the web API choose the same
  class from the route.
- Tests: 10 new in `tests/core/test_embeddings.py` with `botocore.stub.Stubber`
  (complete request body for both input kinds, batching 100 as 96 then 4, three invalid
  response shapes, a `ValidationException` not retried, throttling retry then success,
  give-up after the attempt limit, header token count parked, factory per route, the web
  API path, and a reader test showing an OpenAI-profile row is pending under the Cohere
  profile); the traced-wrapper test asserts forwarding and `input_kind`; the
  `CountingEmbedder` test helper in `test_acquire_pools.py` gains the argument.
- **Executor note:** Codex implemented the brief faithfully, but also ran the formatter
  over four existing files (hundreds of unrelated line changes, 354 in
  `synthesis_tools.py`). The lead restored those files from the Phase A commit and
  re-applied the functional edits by hand. **Correction at review (2026-10-14):** that
  restore missed `core/embeddings.py` itself, which still carried nine formatter-only
  hunks (`_embedding_rate_limit_delay_s`, `_choose_unit_end`, `derive_units`,
  `_embed_units_with_isolation`, `_pending_chunks`, `embed_pending_chunks`); the review
  reverted them, so the file's diff is now the functional change only (166 changed
  lines against `dev`, was 249). `tests/core/test_embeddings.py` keeps about 40 lines of
  reflow; the contract verifier read every one and none is a weakened assertion, so it
  was left as the cost of a clean source diff. Recorded in
  [delegated-executor-practices](../../knowledge/delegated-executor-practices.md).

### Test changes that are not new tests (rubric item 5)

- `tests/core/test_image_hygiene.py`: the guard said `api/` and `core/` must never
  import `boto3`, because the image did not ship it. The owner-approved dependency move
  (contract § Constraints) puts `boto3` in the image on purpose, so the guard's premise
  is gone. The guard is not deleted or weakened; it is repointed at what the image still
  does not ship, the type stubs (`mypy_boto3_*`, still in the `ops` group). Both tests
  keep their shape: request-path modules must not import the stubs at runtime, and
  `ops/` must (so the check cannot pass vacuously). The module docstring records the
  change and why.
- Three test fakes of the embedding seam gained the new `kind` argument
  (`test_synthesis_tools.py`, `test_acquire_pools.py`, `test_tracing.py`). No
  assertion changed.

### Phase C (Claude search-generation backend), diff summary

- `evidence_search/sourcing/search_queries_system_claude_v1.txt`, new: a fresh, short
  system prompt for the Claude family (prompting spec rule 12), lead-authored. Pinned
  as the one new entry in `scripts/prompt_hashes.json`; the three OpenAI `.txt` prompts
  and `search_prompts.py` text are unchanged.
- `evidence_search/sourcing/search_generation.py`: `ClaudeSearchGenerationBackend`.
  `generate_queries` calls Bedrock Converse with one tool (`emit_search_queries`, input
  schema from `SearchQueriesWire`), forced tool choice, the Claude system prompt, the
  user turn from the existing message builder (so the guidance splice is kept), and the
  existing output-token cap. Exactly one `toolUse` block with the expected name and an
  object input is required; the six failure shapes in contract D5 raise `RuntimeError`.
  Usage maps `inputTokens`, `outputTokens`, `totalTokens`, `cacheReadInputTokens` to
  `TokenUsage`. Traced through `tracing.traced_call` like the OpenAI class, with the
  Claude model id and `prompt_version = search_queries_claude_v1`. `reformulate` and
  `suggest` delegate to an inner OpenAI backend (contract O2). The model comes from the
  route's `search_queries` section; a route without one fails at construction with a
  plain error (the lead replaced Codex's `assert` with a `RuntimeError`, since asserts
  vanish under `python -O`).
- `runtime/agent.py`: the live builder picks the Claude class when the route's
  `search_queries.backend` is `claude`, else the OpenAI class. One expression changed.
- Tests, 7 new in `test_search_generation.py` (the builder-selection test,
  `test_live_planner_selects_search_generation_backend_from_route`, lives there too;
  the build's note naming `test_agent.py` was wrong): the complete
  Converse request through `Stubber`; a good reply parsed with usage; a route fixture
  with Sonnet changes only `modelId`; the six failure shapes (through a small local fake
  client, because `Stubber` refuses to serve a response that violates the service
  model, which is itself the point of those cases); delegation of the other two
  methods; builder selection per route.
- **Executor note:** Codex kept to the three named files and ran no formatter. Two
  brief mismatches it reported and resolved sensibly: the current `botocore` service
  model requires `metrics.latencyMs` in a stubbed Converse response (added to the
  fixture), and `Stubber` cannot emit malformed usage (hence the local fake for those
  cases).

<!-- Phases D and E are appended below as they land. -->

## Checks beyond the build

### Live check 1: API shapes on Terra through the route (2026-10-14)

Route `bedrock-local`, model `global.openai.gpt-5.6-terra`, kwargs from the route
`{"reasoning_effort": "none"}`, base address `bedrock-runtime.eu-west-2`. Throwaway
script in the scratch directory, not committed. Budget 2 minutes; took 3 seconds.

| Shape | Result | Tokens in / out |
|---|---|---|
| `chat.completions.parse` with a pydantic model | parsed `city='London' population_millions=8.9` | 60 / 21 |
| `create` with one function tool, `tool_choice="required"`, parallel calls on | one call `lookup({"id":"abc-123"})` | 52 / 19 |
| `create` with `stream=True` | 18 chunks, prose returned | n/a |

The usage block carried `cached_tokens`, `cache_write_tokens` and `reasoning_tokens`
fields in the OpenAI shape, so the existing usage accounting reads it unchanged.

### Live check 2: query generation side by side (2026-10-14, later the same day)

Run through the real backends built from the route (`live_check_2_queries.py`, scratch
directory, not committed), three generic research questions, four arms. The Sonnet and
Opus arms were selected through an **overlay file** (`POLICY_ATLAS_MODEL_ROUTE_FILE`)
that adds routes `eval-sonnet` and `eval-opus`; the committed file was not edited. Each
arm returned 5 queries and 2 paraphrases for every question, parsed by the wire model.
Budget 5 minutes; total about 40 seconds.

| Arm | Route | Model | Seconds per question | Tokens in / out (question 3) |
|---|---|---|---|---|
| OpenAI on Bedrock | `bedrock-local` | `global.openai.gpt-5.6-luna` | 1.5 to 1.6 | 625 / 117 |
| Claude Haiku | `bedrock-local-claude` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | 1.7 to 2.0 | 1205 / 158 |
| Claude Sonnet 5 | `eval-sonnet` (overlay) | `eu.anthropic.claude-sonnet-5` | 3.2 to 3.4 | 1292 / 247 |
| Claude Opus 5 | `eval-opus` (overlay) | `eu.anthropic.claude-opus-5` | 4.2 to 4.6 | 1224 / 301 |

Representative output, question "Do sugar-sweetened beverage taxes reduce consumption in
the UK?":

- Luna: `UK sugar-sweetened beverage tax consumption` · `sugary drink levy beverage
  purchases consumption England` · `sugar tax soft drink consumption reduction` ·
  `levy on sugar-sweetened beverages consumer behavior United Kingdom` · `fiscal policies
  sugary drinks consumption`
- Haiku: `sugar-sweetened beverage tax UK consumption` · `SSB taxation soft drink sales
  United Kingdom` · `soda tax impact demand beverage consumption` · `sugary drink excise
  tax effects purchasing` · `soft drink duties United Kingdom beverage intake`
- Sonnet 5: `sugar-sweetened beverage tax UK consumption` · `soft drinks industry levy UK
  impact` · `SSB tax price elasticity demand soda` · `sugar tax effect on purchasing
  behaviour UK` · `soft drink tax obesity sugar reduction policy evaluation`
- Opus 5: `sugar-sweetened beverage tax purchases United Kingdom` · `soft drinks industry
  levy evaluation reformulation sugar content` · `sugar tax household purchasing panel
  data interrupted time series` · `beverage tax pass-through price elasticity demand
  sugary drinks` · `fiscal policy sugar consumption obesity children natural experiment`

Observations for the evaluation slice, not claims: Claude's prompt is about twice the
tokens of the OpenAI one (the tool schema travels in the request); Opus writes
noticeably more study-design vocabulary; the Claude paraphrases sometimes open with
"This research examines", which the prompt could forbid. Quality is unmeasured (D8).

### Live check 3: end-to-end run under `bedrock-local` (2026-10-14)

Driver: `live_check_3_e2e.py` in the scratch directory (not committed). It seeded a
task on the local dev database, gave the seeded chunks OpenAI-profile rows, built the
live backends from the route (`live_planner_and_backends`), and ran a rapid,
landscape-depth plan through `run_plan` with `NullIO`, capped at 15 minutes. Question:
"Do heat pump subsidies increase uptake among low-income households?".

What ran live on Bedrock through the route, with headline counts from the runner's own
component logs:

| Component | Result | Evidence of the route |
|---|---|---|
| acquire | succeeded: 150 acquired of 3999 returned, adequacy "adequate" | query generation on Luna via Bedrock; 5 Cohere embed calls, `input_kind=document`; 215 `cohere_embed_v4_1536_v1` rows written beside the 5 seeded OpenAI-profile rows |
| screen_abstract | succeeded: 152 screened, 146 relevant | screening on Luna via Bedrock |
| classify | succeeded: 146 classified, 445 tags | Luna via Bedrock |
| appraise | succeeded: 115 appraised | Luna via Bedrock |
| ingest_full_text | **failed** | see below |

Outcome `status=failed` after 319 s. Root cause: the full-text ingest step starts
worker processes, and on macOS a spawned worker re-imports the launching script; the
throwaway driver had no `if __name__ == "__main__"` guard, so the worker re-ran the
whole driver (a second task id appears in the log, with its own run that stopped at the
15-minute cap at the same step) and the first run failed with "An attempt has been made
to start a new process before the current process has finished its bootstrapping
phase". This is the driver's defect, and the exact lesson task 014 recorded. The product
code did not fail: no error-level event from any backend; no bare `gpt-` model id in any
log line; the embedding rows show Cohere vectors arriving next to the old-profile rows
without touching them.

Not demonstrated by this run: full-text chunk embedding and the characterise step
reading Cohere vectors (both behind the failed step). Both paths are covered by tests
with `Stubber` against the real service definition, and the abstract-embedding path is
the same backend code. The driver is fixed (guard added); a re-run was not made because
the contract's live-check budget was spent, and a further run is spend the owner has
not approved. Two orphan tasks remain on the local dev database
(`b6944df8-ee79-…`, `2477750d-7cf3-…`); harmless, and deletable with the ops tooling.

### Live check 3, re-run with the fixed driver (2026-10-14, review conversation)

The owner asked for the re-run at step 7. Same driver (`live_check_3_e2e.py`, guarded
with `if __name__ == "__main__"`, summary query corrected to the real column name
`capability`), with one addition so that re-embedding is actually demonstrated: after
giving the 5 seeded chunks OpenAI-profile rows, the driver **deletes any current-profile
rows** for them, so the run starts from `{'openai_text_embedding_3_small_v1': 5}` and
nothing else. (The first run had started with 5 Cohere rows already present, which the
seed helper had written, so "re-embed chunks that only have OpenAI vectors" was not
shown by it.) Same question, same rapid landscape plan, 15-minute cap.

**Outcome: `status=succeeded` in 548 s.** Every component ran live on Bedrock through
the route; no error-level log line; no bare `gpt-` model id anywhere in the log.

| Component | Headline counts |
|---|---|
| acquire | 150 acquired of 3626 returned, adequacy "adequate"; query generation on Luna; 155 chunks embedded (150 abstracts + the 5 seeded) |
| screen_abstract | 152 screened, 146 relevant, 0 failed |
| classify | 146 classified, 453 tags, 0 rejected |
| appraise | 119 appraised |
| ingest_full_text | 145 attempted, 39 ingested (95 fetch failures, 11 parse failures: open-web sources), 1151 units embedded in 153 s |
| synthesise | artefact written, 2 sections |

Cohere calls seen in the log: 24 `input_kind=document` batches (22 × 96, then 88 and
14) and **2 `input_kind=query` calls** (1 and 2 texts) from the synthesis retriever, so
both input kinds ran live and the characterise/retrieval path read Cohere vectors.
Embedding rows for the task's chunks after the run: `cohere_embed_v4_1536_v1`: 206,
`openai_text_embedding_3_small_v1`: 5. A direct query on the dev database confirms the
5 seeded chunks now hold **one Cohere row each beside their untouched OpenAI row**.
Not demonstrated: chat retrieval through the web API (not part of `run_plan`); its
query path is the same `kind="query"` call shown here and is covered by tests. Three
orphan tasks now sit on the local dev database (two from the first run, one from this
one); harmless, deletable with the ops tooling.

### Live probe at review: Terra on Bedrock without the knob (2026-10-14)

The contract verifier noted that on the Bedrock routes the planner and agent move from
gpt-5.5 to Terra, and that their calls never read the `reasoning_effort` knob which
synthesis and chat need on Terra (task 029). A five-second probe through
`resolve_openai_client` under `bedrock-local` settled it: `chat.completions.parse`
with a pydantic model succeeds on `global.openai.gpt-5.6-terra` **with or without**
the knob (58/84 tokens without, 58/21 with); `create(tools=..., tool_choice="required")`
returns **400 without it** ("Function tools with reasoning_effort are not supported …
set reasoning_effort to 'none'") and succeeds with it. The planner and agent use
structured parse only (`grep -n "tools=" runtime/planner.py runtime/agent_backend.py`
finds none; the agent's read tools are Python callables chosen through structured
output), so they work on Terra without the knob. Recorded in
[bedrock-route-facts](../../knowledge/bedrock-route-facts.md).

### Live probe: Cohere refused, then explained (2026-10-14, earlier the same day)

The first Cohere probe was refused by AWS with `AccessDeniedException` naming the
developer's IAM user and the Cohere EU inference profile, and a Converse probe was
refused for every Claude profile too. The cause was not a permission on the key:
`AWS_BEARER_TOKEN_BEDROCK` was not set in `.env` at the time, so `boto3` fell back to
the machine's ordinary AWS credentials (the IAM user), which have no Bedrock rights.
Once the Bedrock key was present in that variable, Cohere and all three Claude tiers
answered (live check 2). Lesson for `.env.example`, already written there: the key goes
in both variables, because the OpenAI client and `boto3` read different names.

## End-to-end command

Live check 3, from `backend/`, with the Bedrock key in `OPENAI_API_KEY` (the driver
copies it into `AWS_BEARER_TOKEN_BEDROCK` when that is unset) and the dev database in
`.env`:

```
POLICY_ATLAS_MODEL_ROUTE=bedrock-local uv run --env-file .env python <scratch>/live_check_3_e2e.py
```

The driver seeds a task with `tests.runtime.test_runner._seed_task`, builds the live
backends with `live_planner_and_backends`, and calls `run_plan` with a rapid,
landscape-depth plan and `NullIO`, under a 15-minute `signal.alarm`. Live checks 1 and
2 used the same pattern with `<scratch>/live_check_1_api_shapes.py` and
`<scratch>/live_check_2_queries.py`; the Sonnet and Opus arms of check 2 added
`POLICY_ATLAS_MODEL_ROUTE_FILE=<scratch>/overlay_claude_tiers.toml` and
`POLICY_ATLAS_MODEL_ROUTE=eval-sonnet` / `eval-opus`. The scripts are throwaway and
not committed; their content is described in § Checks beyond the build.

## Diff summary

### Phase A (commit `5bdeffc8`)

- `backend/src/policy_atlas/model_routes.toml`, new: `[steps]` (23 steps, four tiers),
  three routes, comments beside each non-obvious value.
- `backend/src/policy_atlas/core/model_routes.py`, new: `load_route` (pure),
  `Route.model_for`, `Route.reasoning_effort_for`, overlay merge, retired-variable
  warning, cached `route()`. `backend/tests/core/test_model_routes.py`, new, 17 tests
  including two subprocess tests of import-time selection.
- 25 constants in 15 modules now read `route().model_for("<step>")` (fast worker, diff
  reviewed by the lead). The six pinned prompt modules each changed exactly two lines:

  | Module | Lines changed |
  |---|---|
  | `assess/classify_prompt.py` | `+from ... import route`; `CLASSIFY_MODEL = route().model_for("classify")` |
  | `assess/screen_prompt.py` | same shape, `screen` |
  | `extract/icf_prompt.py` | same shape, `icf_extract` |
  | `extract/iof_prompt.py` | same shape, `extract` |
  | `sourcing/search_prompts.py` | import; the three `SEARCH_*_MODEL` constants |
  | `runtime/chat_prompt.py` | `-import os`, `+import route`; `CHAT_MODEL = route().model_for("chat")` |

  No prompt text, comment or docstring in those files changed.
- `synthesis_backend.py`: the two `== "gpt-5.6-terra"` comparisons read
  `route().reasoning_effort_for(...)`; `chat_backend_openai.py`: the three
  `reasoning_effort="none"` pins go through one `_chat_kwargs()` helper that reads the
  same knob. Existing tests already assert the resulting kwargs under the default route.
- `core/openai_client.py`: `resolve_openai_client` always passes
  `base_url=route().openai_base_url`; `OPENAI_BASE_URL` is never read.
- `pyproject.toml`: `boto3>=1.43,<2` to main dependencies; `ops` keeps the stubs as
  `boto3-stubs[cognito-idp,bedrock-runtime]`; `uv.lock` regenerated
  (adds `mypy-boto3-bedrock-runtime`).
- `tests/conftest.py`: scrubs `OPENAI_BASE_URL`, `AWS_BEARER_TOKEN_BEDROCK`,
  `POLICY_ATLAS_MODEL_ROUTE`, `POLICY_ATLAS_MODEL_ROUTE_FILE`.
- Docs: contract build-time note; ADR renamed 0038 to 0041; plan links.

## Review findings

Step 7 ran in a fresh conversation on 2026-10-14 (the build conversation wrote the
code and the Codex lane's raw findings; it adjudicated nothing). Entry gate: `make
verify` green on the unchanged branch. Lanes, Tier 3 baseline, no duplicates:

| Lane | Reviewer | Scope | Result |
|---|---|---|---|
| Contract verifier | `contract-verifier` agent (fresh, read-only) | every rubric item, verification.md and ADR claims against the code, the four flagged deviations, import order | 9 findings (1 major on evidence overclaims, 5 minor, 3 notes); all 4 Codex findings confirmed by probe |
| Claude code review | `/code-review medium` | `git diff dev...HEAD` | no high or medium bugs; 3 low |
| Codex adversarial | `codex-rescue`, read-only ([raw findings](review-codex-adversarial.md)) | Claude-written surfaces anchored, Codex-written read at lower weight | 1 major, 3 minor; targets 2, 6, 7, 10 (import order, security boundary, scope, simplification) **not covered** by that run, taken up by the other lanes below |
| Security | `/security-review` (one reasoning-class finder; nothing reached the false-positive filter) | product diff | none at High or Medium; eight angles checked and recorded (keys never logged or traced; Claude trace input equals the OpenAI path's; tool input reaches nothing before pydantic; overlay path is env-only and `tomllib` is data-only; all route addresses `https://`, SDK certificate checks untouched) |
| Live-trace content | lead | live check 2 outputs, both live-check-3 logs, the Terra probe | the first run's "re-embedding" claim was not shown (seed helper had already written Cohere rows); fixed in the driver and demonstrated in the re-run; Terra knob question closed by probe |
| OKF | `make okf-validate` | bundle | 153 concepts, 0 violations (156 after step 8) |
| `/simplify` | not run | | the cleanup surface of this diff was formatter churn, removed by hand (finding 7 below); the Claude lane found no reuse, simplification or efficiency item; a second same-family pass would add nothing (task-cycle-review § Step 7) |

Codex's uncovered targets: import order was checked by the contract verifier (no
cycles; `route()` at first product import; `conftest.py` scrubs before any product
import); the security boundary by the security lane; scope by the contract verifier's
rubric walk (items 18 and 22 hold); simplification by the Claude lane's cleanup angles.

### Findings and how each was settled

Convergent findings (two families) are marked **C**; unique-to-one-lane findings name
the lane.

1. **C · Major · Unknown `search_queries.backend` silently built the OpenAI class**
   (Codex 1, Claude low 2, verifier 5b; `core/model_routes.py`, `runtime/agent.py`).
   A typo such as `"Claude"` in a route or overlay changed provider silently. **Adopted:**
   the loader now validates `search_queries.backend` against `("openai", "claude")` and
   `embeddings.backend` against `("openai", "cohere")` and raises at import naming the
   file and key; the builder's `else` branch is therefore only reachable for `"openai"`.
   Test: `test_unknown_backend_names_and_wrong_shapes_fail_loud`.
2. **C · Minor · Valid TOML of the wrong shape leaked `TypeError`/`ValueError`** (Codex
   2, verifier 26; probed: an overlay with `routes = [1, 2]`). **Adopted:** every section
   the loader reads goes through a `_table` check that raises `RuntimeError` naming the
   file and key; errors for a route that an overlay defines now name the overlay, not
   the committed file. Tests: the parametrised case `'text' must be a table` and
   `test_malformed_overlay_fails_loud_naming_the_overlay`.
3. **Codex · Minor · No single test imported the 25 constants** (rubric item 10 asks
   for one). **Adopted:** `test_every_module_constant_equals_its_pre_053_literal` imports
   all 15 modules and asserts each of the 25 against its pre-053 literal (the verifier
   grepped `dev` and confirmed the inventory: 25 literals, nine environment reads).
4. **Codex · Minor · The repointed image-hygiene guard scanned `api/` and `core/` only**,
   while the new `boto3` call site sits in `evidence_search/`. **Adopted:** the guard
   now scans every package except `ops/`; the `ops/` witness assertion stays.
5. **Verifier · Major · Rubric rows claimed "holds: tests" for things no test showed.**
   Settled item by item: (9) the stray `OPENAI_BASE_URL` test could not fail, because
   `load_route` never reads that variable; **replaced** by
   `test_stray_openai_base_url_does_not_move_the_client`, which builds a client through
   `resolve_openai_client` with the variable set and asserts the route's address. (13)
   the trace half had no test; **added**
   `test_claude_generate_queries_trace_carries_model_and_prompt_version` (span name,
   Claude model id, `prompt_version = search_queries_claude_v1`, usage). (20) nothing
   checked that `synthesis_tools.py` sends `kind="query"`; **added**: `FakeEmbedder`
   records kinds and the retriever test asserts `["query"]`; the single-query path is
   the same one-line call and ran live (2 query-kind calls in the re-run). (24) the
   OpenAI case for `get_chat_embedding_backend` was missing; **added**. (25) the "usage
   not integers" variant was missing from the six shapes; **added**. (19) the reader
   filter on `embedding_profile` predates this slice and is unchanged; the test shows
   the writer side (an old-profile chunk is pending under the new profile) and the live
   re-run shows the reader side (synthesis retrieval returned chunks under Cohere with
   the old rows present); **declined** to add a reader-side unit test. (21) the swap
   test uses a fake route object rather than a loader-read fixture; **declined**, the
   mechanical intent (only `modelId` differs) is met and the live check covered the real
   file.
6. **Verifier · Minor · The default route is not byte-identical for OpenAI embeddings:**
   `API_BATCH_SIZE` 128 → 96 is global, so `openai-direct` now sends smaller batches.
   Contract D4 approves the drop; rubric item 9 overclaimed. **Adopted as a record
   correction** (rubric row 9 below), no code change: a per-backend batch size is a
   setting that does not change behaviour on the Bedrock routes, which the contract's
   disciplines forbid adding.
7. **Verifier · Minor · The Phase B "diff contains only the functional change" claim was
   false for `core/embeddings.py`.** **Adopted:** nine formatter-only hunks reverted by
   hand (§ Phase B executor note); `synthesis_tools.py` was clean as claimed;
   `search_generation.py` had one stray blank line, left (ruff accepts it).
8. **Verifier · Minor · A fifth deviation was not flagged and ADR 0041 was stale** (knob
   keyed by model id, not tier; "five" re-pinned modules, not six). **Adopted:** build-time
   deviation 5 above, the contract's build-time note, and ADR 0041 decisions 2, 3 and 6
   corrected. The plan's promised "knob drives `reasoning_effort` in all three places"
   test with a non-default knob is **declined**: the three places read one function,
   `route().reasoning_effort_for`, which the loader tests cover, and the default-route
   kwargs are asserted by existing tests.
9. **C · Low · A tier-name typo in a step exception is sent verbatim as a model id**
   (Claude low 1, verifier 5a). By design the value is "a tier name or a model id" and
   the two cannot be told apart. **Declined as a code change; adopted as a wording fix:**
   the module and method docstrings and ADR 0041 now say so instead of claiming every
   unresolvable value raises.
10. **Claude · Low · The `boto3` region comes from `AWS_REGION` alone**, independent of
    the route's London address, so a shell with `AWS_REGION` set for other AWS work
    sends the EU profiles to the wrong region. Contract D5 decided this rule. **Deferred**
    to the deploy slice with the one-line fix named (`docs/deferred.md`, Bedrock routes
    entry).
11. **Verifier · Minor · Documents and one warning still described the retired
    variables.** **Adopted:** `docs/agentic-ops/environment.md` and
    `docs/specs/vocabulary.md` corrected; `_warn_stale_agent_env` now points at the route
    file instead of the retired `POLICY_ATLAS_AGENT_*` names. `infra/DEPLOYMENT.md` § tuning
    knobs cannot change in this slice (no `infra/`); **deferred** to the deploy slice in
    `docs/deferred.md`.
12. **Verifier · Note · Verification text slips.** **Adopted:** the builder test's file
    name corrected; rubric row 10's grep wording corrected (the assignment grep matches
    the four lines of `model_routes.toml`, nothing under `.py`); `make audit` output
    pasted in full under § Gate after fixes.
13. **Verifier · Note · Planner and agent on Terra never ran on Bedrock** (live check 3
    drives `run_plan` with a pre-made plan) and never read the knob. **Settled by probe**
    (§ Live probe at review): parse-only calls need no knob; neither module passes tools.
    Two further notes **deferred** without change: neither `boto3` client sets a timeout
    or retry config (botocore defaults stack on the app's Cohere backoff; the Claude call
    has no app-level throttling retry), and Converse `inputTokens` excludes cached reads
    where OpenAI's `prompt_tokens` includes them, harmless until prompt caching is on.
    Both belong with the evaluation slice's first real volume on these backends.
14. **Lead (trace lane) · The first live check 3 did not show re-embedding.** The build
    read 215 Cohere rows "written beside the 5 seeded OpenAI rows" as proof, but the
    first log's "before run" line already listed 5 Cohere rows for those chunks, written
    by the seed helper. **Adopted:** the driver now strips current-profile rows from the
    seeded chunks first; the re-run and a direct database query show the 5 chunks gaining
    a Cohere row each (§ Live check 3, re-run).

Fake-done check on the fixes above: no test relaxed, skipped or deleted; the image
guard widened, not narrowed; every new raise is tested; the formatter revert touched no
functional line (the suite is the witness, § Gate after fixes).

Unique-to-one-lane findings that justified the lane: the verifier's evidence audit
(5, 6, 7, 8) and the lead's trace read (14) found nothing the diff lanes could see;
the Codex lane's 25-constant and guard-scope items (3, 4) were rubric-literal checks
the Claude lane did not make; the Claude lane alone raised the region question (10).

### Gate after fixes

`make verify` on the tree with every fix above (2026-10-14): backend **2662 passed** in
6:00 (8 new tests; 2654 before), mypy "no issues found in 313 source files", ruff clean,
build OK, infra 86 passed, `prompt-hash-guard: 17 prompt file(s) unchanged`, frontend
617 passed (79 files). `make okf-validate` after the step-8 records: 156 concepts
checked, 0 violations. `make audit` output in full:

```
uv run --with pip-audit pip-audit --skip-editable --progress-spinner=off
No known vulnerabilities found
Name         Skip Reason
------------ -------------------------------
policy-atlas distribution marked as editable
```

## Post-review addition (2026-10-21): each route names its key variable

**Why.** The owner replaced the deploy slice's plan (task-role key minting) with
long-term keys held in the app secret, both keys at once, and the route chosen by
`POLICY_ATLAS_MODEL_ROUTE` from `infra/pa_config.json`. Under the reviewed build a
Bedrock route read `OPENAI_API_KEY`, so with both keys present it would have sent the
OpenAI key to Bedrock, and switching route meant editing the secret.

**What changed.** One new field per route, `api_key_env`, validated against
`API_KEY_ENVS = ("OPENAI_API_KEY", "AWS_BEARER_TOKEN_BEDROCK")`. A new helper
`live_api_key()` in `core/model_routes.py` reads the named variable. The three readers
now go through it: `resolve_openai_client` (error message names the route's variable),
`api/deps._live` (both the `live` fail-loud and the `auto` switch) and the agent
command-line switch in `runtime/agent.py`. Fifteen backend docstrings that said
"`OPENAI_API_KEY` is read" now say "the route's key variable is read". `boto3` is
untouched: it always read `AWS_BEARER_TOKEN_BEDROCK`. `.env.example`, ADR 0041,
`docs/knowledge/bedrock-route-facts.md`, `environment.md` and `deferred.md` updated;
contract build-time note (6).

**Tests.** Both committed routes assert their variable; a misspelt `api_key_env` joins
the fail-loud parametrised case; `test_bedrock_route_reads_its_own_key_variable` sets
only `OPENAI_API_KEY` under `bedrock-local` and expects the client to refuse naming
`AWS_BEARER_TOKEN_BEDROCK`, then sets it and expects the client to carry it.

**Local effect.** A developer on a Bedrock route now needs the Bedrock key in
`AWS_BEARER_TOKEN_BEDROCK` only. If it is left only in `OPENAI_API_KEY`, `auto` mode
runs stubs, the same silent behaviour as any missing key before this slice.

**Gate and live probe.** See § Commands run (rows dated 2026-10-21).

## Post-merge integration (2026-10-21): options scoping under the route file

**Merge.** `origin/dev` at `eedf9ef9` (456 files; the options-scoping capability, PR #69)
merged into this branch. Ten conflicts: four Python files took dev's implementation with the
route constants and the key-variable switch re-applied on top (`agent_backend.py`,
`api/deps.py`, `runtime/agent.py`, `core/openai_client.py`); `runtime/planner.py` is deleted
on dev (the Task Agent replaces it); the environment header, readiness line, a knowledge
timestamp, the knowledge log and the prompt-hash pins were merged by hand.

**What dev brought that the route file had to absorb.**

| Module | Constant | Default | Step | Tier |
|---|---|---|---|---|
| `runtime/task_agent.py` | `TASK_AGENT_MODEL` | gpt-5.5 | `task_agent` (was `planner`) | frontier |
| `runtime/task_agent_scoping.py` | `TASK_AGENT_SCOPING_MODEL` | gpt-5.6-sol | `task_agent_scoping` | judgment (new) |
| `options_scoping/longlist/longlist_backend.py` | `LONGLIST_JUDGMENT_MODEL` | gpt-5.6-sol | `longlist_judgment` | judgment |
| same | `LONGLIST_ASSIGNMENT_MODEL` | gpt-5.6-luna | `longlist_assignment` | fast |
| `extract/extract_interventions_prompt.py` | `INTERVENTIONS_MODEL` | gpt-5.6-luna | `extract_interventions` | fast |

Each constant now reads `route().model_for(step)`; the four `POLICY_ATLAS_*_MODEL`
overrides dev added join `RETIRED_ENV` (warned once, ignored). The fifth tier `judgment`
is Sol on `openai-direct` and `global.openai.gpt-5.6-sol` on both Bedrock routes; no
reasoning-effort knob, and the live probe (§ Commands run) parsed structured output
without one. The default route reproduces dev's values exactly (`PRE_053_MODELS` grows by
four steps; the constant pin is 29 across 19 modules). `extract_interventions_prompt.py`
is hash-pinned, so its re-pin is the one new prompt-module hash beyond the six 045 ones.

**Not changed.** Nothing under `infra/`; dev's options-scoping logic is untouched beyond
the constant lines and one import each; `boto3` region handling as before.

**Live check 4: the options-scoping pipeline end to end on Bedrock (2026-10-21).** The
owner asked for one topic, "interventions to reduce obesity". Driven through the local API
on `bedrock-local` (server started with the selector set; dev DB first upgraded six
migrations to `f1b6d3a8c2e5`). Every step ran on Bedrock models through the route file:
the scoping Task Agent and the longlist judgment calls on Sol, screening, classification,
intervention extraction, query generation and the small longlist calls on Luna, synthesis
on Terra, embeddings on Cohere. Result in § Commands run. Two driver lessons, not product
defects: a walk's first `paused` is a mid-walk steering check-in (after appraise), not the
baseline gate, so a driver must read `/check-ins` for `kind = baseline_confirm` before
confirming; and the confirm decision turn itself opens the longlist walk, so
`POST /plan/confirm-baseline` afterwards is refused with `run_active`. One
`option_profile.call_malformed` warning was retried by design. The twenty options read as
sensible obesity levers (family weight programmes, school meals, HFSS promotion limits, a
sugar levy, planning controls, labelling, bariatric surgery, anti-obesity medicines, active
travel); quality against the 046 measures is the evaluation slice's job, not this check's.

**First gate after the merge: four failures, all merge losses, plus one audit item.**
Taking dev's version of `api/deps.py` and `runtime/agent.py` wholesale had dropped three
045 hunks that no conflict marker covered: the chat embedding seam building
`OpenAIEmbeddingBackend()` instead of `live_embedding_backend()` (caught by
`test_chat_embedding_backend_selects_cohere_in_live_mode`), the live builder's embedding
default and its Claude-or-OpenAI search-generation choice (caught by the selection test,
which itself still used the planner names and now patches dev's three extra backends and
calls `live_task_agent_and_backends`). The fourth was dev's rename sweep refusing the
retired name `POLICY_ATLAS_PLANNER_MODEL` inside `RETIRED_ENV`; that entry is dropped,
the Task Agent name covers it, and `.env.example` still lists the old name for readers.
`make audit` flagged `certifi` 2026.6.17 (PYSEC-2026-4320), inherited from dev; the lock
now pins 2026.10.19. Lesson for the knowledge record: a wholesale "take theirs" on a
conflicted file silently loses every hunk of ours that did not conflict; diff the file
against our pre-merge commit before accepting it.

## Rubric status

Walked at step 6 against [rubric.md](rubric.md). "Holds" means the evidence is in this
file or in the named test; "open" means it waits on the live checks.

| # | Item | Status |
|---|---|---|
| 1 | Satisfies the contract incl. D1 to D8, O1 (Terra), O2 (Claude for query generation only) | holds; four build-time deviations flagged above |
| 2 | `make verify` passes; live checks ran in budget | holds: verify green at step-6 exit, step-7 entry and step-7 exit; live checks 1 and 2 in budget; live check 3 failed on a driver defect first, then the owner-approved re-run succeeded in 548 s inside its 15-minute cap (§ Live check 3, re-run) |
| 3 | No unapproved gated change | holds: egress and the `boto3` move are the two approved gates; nothing under `infra/` |
| 4 | No generated files or secrets edited by hand; no key in the diff | holds; `.env` untouched, `.env.example` has empty values |
| 5 | No tests deleted, skipped or weakened without justification | holds; the one repointed guard is justified in § Test changes |
| 6 | Verification evidence recorded | this file |
| 7 | Known gaps and deferred seams in `docs/deferred.md` | holds; the "Bedrock routes" entry is superseded, gaps listed |
| 8 | Tier 3 review stack ran | holds: contract verifier, `/code-review medium`, `/security-review`, Codex adversarial, lead trace lane; 14 findings settled above; human deep review at the PR |
| 9 | Unset means unchanged | holds for every model id, the profile and the client address (`test_default_route_reproduces_every_pre_053_model`, `test_every_module_constant_equals_its_pre_053_literal`, `test_stray_openai_base_url_does_not_move_the_client`); one approved request-shape change on the default route: OpenAI embedding batches are 96 texts, not 128 (contract D4, finding 6) |
| 10 | No literal model name left; loader fails loud; retired variables ignored with a warning | holds: the 25-constant test; `grep -rnE '= "(gpt-\|text-embedding-)' backend/src` matches only the four lines of `model_routes.toml`; `grep -rn 'environ.get("POLICY_ATLAS_[A-Z_]*MODEL' backend/src` empty; loader tests incl. backend names and wrong shapes (findings 1, 2) |
| 11 | Claude fails loud, no silent fallback | holds: `test_claude_generate_queries_rejects_invalid_responses` |
| 12 | Only query generation moved | holds: `test_claude_reformulate_and_suggest_delegate_to_inner_backend` |
| 13 | Usage and tracing hold for Claude | holds: usage by `..._sends_converse_request_and_parses_reply`, trace by `..._trace_carries_model_and_prompt_version`; live check 2 returned token counts for all three Claude tiers |
| 14 | Prompt text unchanged; pins honest | holds: one new pin; six re-pins, each diff import + constant only (§ Diff summary) |
| 15 | Tests stay offline; scrub list extended | holds: `conftest.py`; the suite ran socket-denied throughout |
| 16 | Dependency change exactly as approved; `make audit` green after lock change and at exit | holds: Phase A and step-6 exit summaries above; full step-7 exit output under § Gate after fixes |
| 17 | A cold reader can set it up from `.env.example` | holds: file rewritten; the owner reached live check 2 from it, after one round trip on "the same key in both variables", which the file now states first |
| 18 | Nothing under `infra/` changed | holds: `git diff --stat 5f84bef..HEAD -- infra` is empty |
| 19 | Embeddings follow the route; old profile rows not read | holds: factory tests (both classes, both callers) and `test_pending_chunks_with_old_profile_are_pending_for_cohere` for the writer side; the live re-run shows the reader side (finding 5) |
| 20 | Cohere batching and input types | holds: `test_cohere_embedding_backend_batches_100_texts_in_order`, `..._sends_complete_request` for both kinds, `FakeEmbedder.kinds == ["query"]` in the retriever test, and 2 live query-kind calls in the re-run |
| 21 | Claude tier is a one-line swap | holds: the mechanical test, and live check 2 ran Haiku, Sonnet 5 and Opus 5 by changing only the model line |
| 22 | Nothing built from § Future work | holds: no key minting, no `infra/`, no shared Converse layer, old vectors kept, live-mode detection unchanged |
| 23 | Route file committed, shipped and readable | holds: `test_route_file_ships_inside_the_package`; 23 steps; comments beside each non-obvious value |
| 24 | The web API follows the route | holds: `test_chat_embedding_backend_selects_cohere_in_live_mode` and `..._selects_openai_in_live_mode` |
| 25 | Claude reply shape enforced, six failure shapes | holds: the case list in `test_claude_generate_queries_rejects_invalid_responses`, now including non-integer usage |
| 26 | Overlay works and is bounded; Sonnet and Opus live calls ran through an overlay | holds: replace/add/no-`[steps]`/missing tests, plus the malformed-overlay test (finding 2); live check 2's Sonnet and Opus arms were selected from an uncommitted overlay file |

## Intent & assumptions

- The three routes reproduce the owner's decisions: Terra for the frontier tier (O1),
  Haiku first for Claude with the tier swappable in the file, Cohere for embeddings.
- The fourth tier `fast` exists only so that the default route reproduces task 051's
  model choice for screening and query generation exactly. On the Bedrock routes it
  resolves to the same Luna as `mini`.
- The `reasoning_effort` knob is keyed by model id, not by tier, because that is what
  the code compared before (the literal `gpt-5.6-terra`), so the default route is
  byte-identical, and because a step exception can name a model directly.
- Retiring the nine variables assumes nobody relies on them in a deployed environment;
  checked: the CDK stack sets none of them.

## Known unverified items

- ~~Live check 3 did not get past full-text ingest~~ — closed at review: the re-run
  completed, with full-text chunk embedding and synthesis retrieval on Cohere vectors
  shown live (§ Live check 3, re-run).
- Chat retrieval through the web API on Cohere vectors ran only in tests (the same
  `kind="query"` call the synthesis retriever made live).
- Claude prompt quality is not measured (contract D8).
- `boto3` client timeouts/retries and the Converse cached-token accounting (finding 13)
  are unexercised at volume.

## Public safety

- No key, `.env` or trace body is in the diff or in this file. The live-check script and
  overlay file live in the session scratch directory and are not committed.
- Token counts and model ids are the only live-call data recorded.
- The research questions used for live check 2 are generic policy questions, not from
  any private project.

## Review handoff (step-7/8 inputs)

- **Executor provenance:** Phase A constant sweep by `fast-worker` (lead reviewed every
  changed line of the six pinned modules); Phase B and Phase C implementation by Codex
  (`codex-rescue`) against pinned briefs; loader, knob changes, prompt text, documents and
  live checks by the lead.
- **Knowledge candidates:**
  - A model-family swap that is really a vendor-hosting swap: Bedrock serves the same
    GPT-5.6 models, so the "fresh prompt at a family swap" rule applied only to Claude.
  - A grep for literal model names cannot be a gate when comments mention them; a test
    on the constants plus a grep narrowed to assignment lines is the mechanical form.
  - Module-level constants read from a cached route at import: tests of other routes
    must use a subprocess, not a reload.
  - Any throwaway driver that calls `run_plan` must sit under `if __name__ == "__main__"`:
    full-text ingest spawns workers that re-import the launching file on macOS, and an
    unguarded driver re-runs itself inside the worker (task 014 recorded the same; it
    bit again because the lesson lives in a verification note, not in `docs/knowledge/`).
  - `boto3` and the OpenAI client read different credential variables; a key present in
    one and absent from the other produces an `AccessDeniedException` that names the
    machine's IAM user and looks like a permission gap. Check both variables before
    reading the error as a policy problem.
  - An approved dependency move can invalidate a structural pin elsewhere in the suite
    (`test_image_hygiene.py` pinned "no AWS SDK in the image"). When a contract approves
    a gate, grep the tests for pins of the old premise before the build, and repoint
    rather than delete them.
  - A targeted test run before a full gate must include every test file that fakes a
    changed interface: `grep -rn "def embed_texts(" tests` would have found the third
    fake before the gate did.
  - Running `ruff format` on an existing file in this repo reformats unrelated lines;
    the lint gate is `ruff check` only. Format new files, not existing ones. A delegate
    brief that allows `ruff format src tests` invites exactly this: Codex reformatted
    four files in Phase B and the lead had to restore and re-apply. Briefs should allow
    `ruff format --check` and `ruff check --fix`, never a bare `ruff format` on the tree.

## Review handoff, delta (2026-10-21, for a fresh step-7 pass)

The stack of 2026-10-14 reviewed the slice up to `84ecc720`. Four commits followed, all
written by the lead in the conversation that also drove the live checks, so that
conversation may not adjudicate them (`task-cycle-review`: fresh conversation). This is
the handoff for a **delta** pass; nothing before `84ecc720` needs re-reading unless a
delta finding points there.

- **Commits:** `f73d8686` (deferred-log plan change, docs only), `8a772ffb` (each route
  names its key variable), `9feb8090` (merge of `origin/dev` at `eedf9ef9`, the task
  renumber 045→053 / ADR 0039→0041, options scoping under the route file, the four
  merge-loss fixes, the certifi bump), `cb597bd6` (live check 4 record, docs only).
- **Diff to read:** our lines on top of dev, scoped to the files the delta touched:

  ```
  git diff origin/dev...HEAD -- backend/src/policy_atlas/model_routes.toml \
    backend/src/policy_atlas/core/model_routes.py backend/src/policy_atlas/core/openai_client.py \
    backend/src/policy_atlas/api/deps.py backend/src/policy_atlas/runtime/agent.py \
    backend/src/policy_atlas/runtime/agent_backend.py backend/src/policy_atlas/runtime/task_agent.py \
    backend/src/policy_atlas/runtime/task_agent_scoping.py \
    backend/src/policy_atlas/options_scoping/longlist/longlist_backend.py \
    backend/src/policy_atlas/evidence_search/extract/extract_interventions_prompt.py \
    backend/tests/core/test_model_routes.py backend/tests/evidence_search/sourcing/test_search_generation.py \
    backend/.env.example backend/uv.lock scripts/prompt_hashes.json
  ```

  Records: `docs/adr/0041-*`, `docs/deferred.md` § Bedrock routes, `docs/knowledge/`
  (`merge-take-theirs-drops-unconflicted-hunks`, the two updated records, `index.md`,
  `log.md`), `docs/agentic-ops/{environment,readiness}.md`, this file's § Post-review
  addition and § Post-merge integration, contract notes (6) to (8). Exclude
  `docs/tasks/04[4-6]-*` and everything dev brought (`git diff 84ecc720...origin/dev`).
- **Provenance:** every delta line is lead-written (Claude); no Codex surface. So the
  Codex adversarial lane anchors the delta and `/code-review medium` is the Claude half.
- **Entry gate:** `make verify` + `make audit` green at `9feb8090` (backend 3638, mypy
  420, infra 93, frontend 882); `cb597bd6` changed this file only.
- **Decisions the stack must confirm or contest** (each made unilaterally by the lead):
  1. `api_key_env` is validated as one of two names (`API_KEY_ENVS`); `live_api_key()`
     feeds `resolve_openai_client`, `api/deps._live` and the agent CLI switch; `boto3`
     still reads its variable on its own. A developer who leaves the Bedrock key only in
     `OPENAI_API_KEY` now gets stubs under `auto` mode, silently, like any missing key.
  2. `POLICY_ATLAS_PLANNER_MODEL` was removed from `RETIRED_ENV` because dev's rename
     sweep (`test_rename_044_sweep.py`) forbids the string in `backend/src`; a stale
     setting of that name is therefore no longer warned about (`.env.example` still lists
     it for readers).
  3. The fifth tier is named `judgment` (Sol); no reasoning-effort knob for Sol; probe
     only (plain + structured parse), no function-tool call on Sol has been made.
  4. `extract_interventions` and `longlist_assignment` sit on `fast` (Luna), matching
     dev's literals; `task_agent` keeps `frontier`.
  5. Merge resolution: `git checkout --theirs` on four Python files, then re-application
     of the 045 hunks from `git diff $(git merge-base 84ecc720 origin/dev) 84ecc720`.
     Check that list against HEAD for any hunk still missing; the gate found three.
  6. The renumber sweep touched only lines this branch added (`git diff -U0 origin/dev`
     hunks); dev's own "045 a third" citation in `environment.md` was restored by hand.
     Confirm no other dev citation of 045/0039 was rewritten.
  7. `certifi` 2026.6.17 → 2026.10.19 by `uv lock --upgrade-package certifi` (inherited
     advisory, one package).
  8. Live check 4's driver lessons are recorded as driver errors, not product defects:
     a walk's first `paused` is a steering check-in, and the confirm decision opens the
     longlist walk itself (`confirm-baseline` afterwards → 409). Contest if either reads
     as a product or documentation defect.
  9. The readiness line now states PR #69 merged 2026-10-15 and this slice landing
     2026-10-21; adjust the date if the merge slips.
- **Knowledge candidates (delta):** the merge lesson is authored
  ([merge-take-theirs-drops-unconflicted-hunks](../../knowledge/merge-take-theirs-drops-unconflicted-hunks.md));
  still open: (a) the two scoping-driver lessons above, a candidate fold into
  [live-check-drive-runbook](../../knowledge/live-check-drive-runbook.md); (b) "a
  renumber sweep after a numbering clash must touch only the branch's own added lines",
  a candidate fold into the two-step-rename concept.
- **Known unverified after the delta:** `bedrock-local-claude` has not been run live
  since the merge (its loader path is covered by the subprocess test only); chat
  retrieval through the web API on Cohere vectors still only in tests; Sol under
  function tools untested; the options-scoping run's quality against the 046 measures
  is unmeasured (evaluation slice).

## Knowledge records (step 8)

Authored from the build's candidates and the stack's findings, each adjudicated:

| Candidate | Decision |
|---|---|
| Vendor-hosting swap vs model-family swap; two credential variables and the AccessDenied look-alike; Terra knob (review probe) | **new** [bedrock-route-facts](../../knowledge/bedrock-route-facts.md) |
| Constants read a cached route at import, subprocess for other routes; grep is not a gate, the constants test is | **new** [model-route-constants-read-at-import](../../knowledge/model-route-constants-read-at-import.md) (also carries findings 1, 2, 9) |
| Approved gate invalidates a structural pin; targeted runs must cover every fake of a changed interface; guard scope (finding 4) | **new** [interface-change-sweeps-fakes-and-premise-pins](../../knowledge/interface-change-sweeps-fakes-and-premise-pins.md) |
| `if __name__ == "__main__"` for drivers that call `run_plan` | **folded** into [live-check-drive-runbook](../../knowledge/live-check-drive-runbook.md) |
| No bare `ruff format` on existing files in delegate briefs | **folded** into [delegated-executor-practices](../../knowledge/delegated-executor-practices.md) |

## Deferred work

Recorded in [docs/deferred.md](../../deferred.md) under the superseded "Bedrock routes"
entry: the deploy slice (task-role permissions, container key minting, route per
environment, Marketplace access, region policy, quotas, secret clean-up, Langfuse
pricing, the Anthropic use-case form, the cost decision on re-embedding older projects),
the evaluation slice (Luna, Terra and Claude tier quality, Cohere grouping quality,
reformulation and suggestion on Claude), the retired variables, and the shared Converse
layer if a third seam moves to Claude. One addition from the build: `OPENAI_API_KEY` is
a misleading name once it holds a Bedrock key; renaming belongs with the deploy slice's
key-minting change, which also reworks live-mode detection.
