# Implementation plan: 045-bedrock-local-route

> Status: revision 2, 2026-09-25. Contract-stage findings adjudicated
> ([adversarial-review-contract.md](adversarial-review-contract.md)); plan-stage findings
> adjudicated and folded in ([adversarial-review-plan.md](adversarial-review-plan.md)).
> **Approved by the owner 2026-09-25** (Karlis Kanders). Contract:
> [contract.md](contract.md) (approved 2026-09-25). Rubric: [rubric.md](rubric.md). ADR:
> [0038](../../adr/0038-bedrock-inference-route-and-model-route-file.md), Accepted
> 2026-09-25. Terms and need numbers (N1 to N8) are defined in the contract and are not
> restated here.

## Context

The contract fixes three things this plan builds: a committed route file that names every
model the app uses (N1, N2); Cohere embeddings on Bedrock behind the existing embedding
seam (N3); and a Claude backend for the search query generation step behind its existing
seam (N4, N5). Everything else is tests, dependency housekeeping and documents (N6, N7,
N8).

Facts the plan relies on beyond the contract, checked in the code on 2026-09-25:

- 25 literal model constants in 15 modules, plus one unconditional knob in a 16th. Every
  constant is `gpt-5.4-mini`, `gpt-5.6-terra` or `gpt-5.5`, so the three tiers cover them
  with none left over. Nine read an environment override, retired in this slice
  (§ Retired overrides). Two compare the name to `gpt-5.6-terra`, both in
  `synthesis_backend.py`. The chat backend pins `reasoning_effort="none"` without a
  comparison.
- Five of the modules are hash-pinned prompt modules. Editing the constant line changes
  the file hash. The contract accepts a re-pin with a recorded diff.
- Comments and docstrings in several modules mention model names. A grep for the bare
  string would never pass, so the "no literal left" check is a test on the constants
  plus a grep narrowed to assignment lines.
- The operator command line's tests already fake `boto3` with `botocore.stub.Stubber`,
  which checks request parameters against the real service definition. The same tool
  fakes Converse and InvokeModel here. No new test dependency. A `Stubber` client needs a
  region and dummy credentials; the pattern is in `tests/ops/support.py`.
- `tests/ops/test_make_wrappers.py` already runs subprocesses from a test. Import-time
  route selection is tested the same way, one small subprocess per route.
- `embed_pending_chunks` in `core/embeddings.py` takes the batch size as an argument with
  the module constant as its default.
- The Langfuse embedding wrapper `TracedEmbeddingBackend` in `core/tracing.py` is what
  live runs call. It must accept and forward the new argument.
- The live backend builder for the command line is `live_planner_and_backends` in
  `runtime/agent.py`. The web API builds its own embedding backend in
  `api/deps.py:get_chat_embedding_backend`. Both must read the route.
- `make audit` (the dependency vulnerability scan) is not part of `make verify`. It runs
  separately after the lock file changes.

## Decisions taken in this plan

| # | Topic | Decision |
|---|---|---|
| P1 | Loader shape | `core/model_routes.py` has a pure function `load_route(path, name, environ, overlay_path=None) -> Route` and a module-level `route()` that calls it once with the packaged file, `POLICY_ATLAS_MODEL_ROUTE`, `POLICY_ATLAS_MODEL_ROUTE_FILE` and `os.environ`, then caches. The overlay's `[routes.*]` tables replace or add committed routes by name; `[steps]` comes only from the committed file. `Route` is a frozen dataclass with `model_for(step)`, `openai_base_url`, `knobs`, `embeddings` and `search_queries`. Tests call `load_route` directly with fixture files; they never reload the cached module (F10). |
| P2 | Where the file lives | `backend/src/policy_atlas/model_routes.toml`, read as `Path(__file__).resolve().parent.parent / "model_routes.toml"` from `core/model_routes.py`. Same pattern as the prompt `.txt` files; the wheel and image carry it with no build change (contract F1, plan F1). |
| P3 | Fail-loud rule | Unknown route, unknown step (asked by code or named in a route's exceptions), missing tier, missing section, or a parse error raises `RuntimeError` naming the file and the key. No defaults are invented in code. |
| P4 | Resolution order for `model_for(step)` | 1. The route's step exception for this step, if any: a tier name resolves through the route's tiers, anything else is a model id. 2. The step's default tier from `[steps]`, resolved through the route's tiers. The environment plays no part (§ Retired overrides). |
| P5 | Prompt-module re-pins | Constants in the five hash-pinned prompt modules are replaced in place. Re-pin once with `python3 scripts/prompt_hash_guard.py --update` at the end of Phase A and record `git diff` of each file in `verification.md`. |
| P6 | Keys | Cohere and Claude read `AWS_BEARER_TOKEN_BEDROCK` through `boto3`'s own environment handling. The code never reads the variable. |
| P7 | Sequencing | Phases run one after the other: 0, A, B, C, D, E. No parallel jobs. Every gate runs alone, because test lanes share one Postgres (AGENTS.md landmine; plan F8). |
| P8 | Gates | Three full `make verify` runs: Phase 0 (build-open), end of Phase B (embedding write path is ingest-adjacent), Phase E (step-6 exit). Phases A and C gate on `make verify-fast` plus `make prompt-guard`. `make audit` runs at the end of Phase A and at Phase E (F9). |

## Retired overrides

Nine environment variables override a step's model today, and two of them make another
step follow along (case studies follow synthesis, agent triage follows screen). The owner
retired all nine on 2026-09-25: the route file and the overlay are the only mechanisms.
The loader reads none of them. At import it checks whether any is set and, if so, logs
one `structlog` warning `model_routes.retired_env_ignored` listing the names and saying
to use the route file. This is the pattern `_warn_stale_agent_env` in
`runtime/agent_backend.py` already uses; that helper's own list gains these names or is
replaced by the loader's warning, whichever is smaller.

| Retired variable | Step it used to set |
|---|---|
| `POLICY_ATLAS_PLANNER_MODEL` | `planner` |
| `POLICY_ATLAS_AGENT_MODEL` | `agent` |
| `POLICY_ATLAS_AGENT_TRIAGE_MODEL` | `agent_triage` |
| `POLICY_ATLAS_CHAT_MODEL` | `chat` |
| `POLICY_ATLAS_SYNTHESIS_MODEL` | `synthesis` |
| `POLICY_ATLAS_CASE_STUDIES_MODEL` | `case_studies` |
| `POLICY_ATLAS_MRS_NOTE_MODEL` | `mrs_note` |
| `POLICY_ATLAS_FULL_REPORT_INTRO_MODEL` | `full_report_intro` |
| `POLICY_ATLAS_RELEVANCE_MODEL` | `relevance` |

Tests: with one of them set, the resolved model is unchanged and the warning names it;
with none set, no warning. `.env.example` loses their entries. The deployed stack sets
none of them, so no environment changes.

## Gates

| # | When | Class |
|---|---|---|
| 1 | Phase 0 | build-open baseline |
| 2 | End of Phase B | ingest-adjacent (embedding write path, profile change) |
| 3 | End of Phase E | step-6 exit |

Plus `make audit` at the end of Phase A and at Phase E.

## Phases

Each phase ends in a commit on the branch. Executor marks follow AGENTS.md § Agent-side
model routing; every `lead` mark carries its reason.

### Phase 0 — Baseline — lead (inline; one command, nothing to brief)

Run `make verify` on the branch as it stands. Record the test count and wall time. Do not
open the build on a red base.

**Gate:** full `make verify`.

### Phase A — Route file and loader (N1, N2, N6, N7)

1. `backend/src/policy_atlas/model_routes.toml` with the `[steps]` table (23 steps, see
   § Call sites) and the three routes from contract D3, comments beside each non-obvious
   value. — **lead** (this is the design surface a cold reader judges the slice by).
2. `core/model_routes.py`: `load_route`, `Route`, `model_for`, the resolution order (P4),
   the fail-loud rule (P3), the overlay merge, the retired-variable warning, the cached
   `route()`. About 70 lines. — **lead** (seam design is judgment; the code is the same
   size as the brief).
3. Loader tests, against fixture TOML files under `tests/core/data/`: default route
   returns every pre-045 literal for all 23 steps, the profile and the address;
   `bedrock-local` returns the Bedrock names; a step exception naming a tier and one
   naming a model both win over the default tier; a retired variable set in the
   environment changes nothing and is named in the warning, and no warning fires when
   none is set; unknown route, unknown step, missing tier, missing
   section and malformed file each raise naming the key; a stray `OPENAI_BASE_URL` in
   the environment does not change the address; an overlay fixture that replaces
   `bedrock-local-claude` with a Sonnet model takes effect, one that adds a route
   `eval-x` is selectable, one with a `[steps]` table is rejected, and a missing or
   malformed overlay path raises. — **lead** (the fixture design is the judgment; F11).
4. Import-time selection tests: one subprocess per route that imports
   `policy_atlas.core.model_routes` with `POLICY_ATLAS_MODEL_ROUTE` set and prints the
   resolved `search_queries` model and embedding profile; the test asserts the printed
   values. — **lead** (same fixture reasoning; F10).
5. Replace the 25 constants with `route().model_for("<step>")` in 15 modules, exactly per
   the § Call sites table, keeping every constant's name and deleting the nine
   `os.environ.get(...)` reads they replace. — **fast-worker** (mechanical transcription
   of an exact table; step 3's default-route test pins every value).
6. The two string comparisons in `synthesis_backend.py` and the unconditional pin in
   `chat_backend_openai.py` read `route().knobs["standard_reasoning_effort"]` instead;
   tests assert the knob drives `reasoning_effort` in all three places. — **lead**
   (behaviour change, not transcription; F11).
7. `resolve_openai_client` gains a required `base_url` argument; every caller passes
   `route().openai_base_url`. — **fast-worker** (one signature, 19 call sites, pinned
   by the existing fake-client tests plus the stray-variable test in step 3).
8. `pyproject.toml`: move `boto3>=1.43,<2` from `ops` to main dependencies; add
   `boto3-stubs[bedrock-runtime]>=1.43,<2` beside `boto3-stubs[cognito-idp]` in `ops`
   (stubs are type-check only); `uv lock`. — **lead inline** (approved dependency gate; a
   three-line edit that must be exactly as approved).
9. `tests/conftest.py`: scrub `POLICY_ATLAS_MODEL_ROUTE`, `POLICY_ATLAS_MODEL_ROUTE_FILE`,
   `OPENAI_BASE_URL`, `AWS_BEARER_TOKEN_BEDROCK`. — **fast-worker**.
10. Re-pin the five prompt modules (P5). — **lead inline** (one command; the diff is the
    evidence).

**Done when:** `make verify-fast`, `make prompt-guard` and `make audit` are green; a grep
of `backend/src` for lines matching `= "gpt-` or `= "text-embedding-` finds none (comments
and docstrings do not match this shape).

**Gate:** `make verify-fast` + `make prompt-guard` + `make audit`.

### Phase B — Cohere embeddings (N3) — codex

Brief. All names below are pinned; the job invents nothing.

1. `CohereEmbeddingBackend` in `core/embeddings.py`, `mode = "live"`. Client:
   `boto3.client("bedrock-runtime", region_name=<AWS_REGION or "eu-west-2">)`. Per batch
   of at most 96 texts:

   ```python
   response = client.invoke_model(
       modelId=route().embeddings.model,          # "eu.cohere.embed-v4:0"
       contentType="application/json",
       accept="application/json",
       body=json.dumps({
           "texts": texts,
           "input_type": "search_document" | "search_query",   # from the new argument
           "embedding_types": ["float"],
           "output_dimension": 1536,
           "truncate": "NONE",
       }),
   )
   body = json.loads(response["body"].read())
   vectors = body["embeddings"]["float"]           # list of lists, input order
   tokens = int(response["ResponseMetadata"]["HTTPHeaders"]["x-amzn-bedrock-input-token-count"])
   ```

   Raise `RuntimeError` when `len(vectors) != len(texts)`, when any vector's length is
   not 1536, or when the body is not JSON or lacks the keys. Park `tokens` where the
   OpenAI class parks its prompt tokens. Retry only when a `botocore.exceptions.ClientError`
   has `response["Error"]["Code"] == "ThrottlingException"`, reusing the existing backoff
   loop and attempt limit; any other `ClientError` propagates.
2. `EmbeddingBackend.embed_texts(texts, *, kind: Literal["document", "query"] = "document")`.
   Stub and OpenAI class accept and ignore `kind`. `TracedEmbeddingBackend` accepts it,
   forwards it, and adds `"input_kind": kind` to the trace metadata.
3. `EMBEDDING_PROFILE = route().embeddings.profile`, `EMBEDDING_MODEL =
   route().embeddings.model`, `API_BATCH_SIZE = 96`.
4. `live_embedding_backend() -> EmbeddingBackend` in `core/embeddings.py`: returns
   `CohereEmbeddingBackend()` when `route().embeddings.backend == "cohere"`, else
   `OpenAIEmbeddingBackend()`. Called from `live_planner_and_backends` in
   `runtime/agent.py` and from `get_chat_embedding_backend` in `api/deps.py`, replacing
   the two hard-coded `OpenAIEmbeddingBackend()` calls.
5. The two `embed_texts` calls in `synthesis_tools.py` (near lines 1505 and 1514) pass
   `kind="query"`.
6. Tests in `tests/core/test_embeddings.py` with `Stubber` on a client built with
   `region_name="eu-west-2"`, `aws_access_key_id="test"`, `aws_secret_access_key="test"`:
   the complete request body for a document batch and a query batch; 100 texts go out
   as 96 then 4; vectors return in input order; count mismatch, wrong length, malformed
   body, and a `ValidationException` for an over-limit input each raise; a
   `ThrottlingException` retries then succeeds, and repeated throttling gives up after
   the attempt limit; the header token count is parked; the factory returns each class
   per route from both callers (`agent.py` and `api/deps.py`); the traced wrapper
   forwards `kind` and records it; a reader test inserts an OpenAI-profile row and shows
   the Cohere-profile query does not return it.

**Done when:** the tests above pass and full `make verify` is green.

**Gate:** full `make verify` (gate 2).

### Phase C — Claude search-generation backend (N4, N5) — codex, prompt by lead

1. `search_queries_system_claude_v1.txt`: fresh, short, written for the Claude family per
   the prompting spec's rule 12 and mini-tier guidance. — **lead** (prompt-bearing; never
   delegated).
2. `ClaudeSearchGenerationBackend` in `search_generation.py`, `mode = "live"`. Brief, all
   names pinned:

   ```python
   TOOL_NAME = "emit_search_queries"
   tool = {"toolSpec": {
       "name": TOOL_NAME,
       "description": "Return the generated search queries for the research question.",
       "inputSchema": {"json": SearchQueriesWire.model_json_schema()},
   }}
   messages = build_queries_messages(payload)      # existing builder: [system, user]
   response = client.converse(
       modelId=route().search_queries.model,
       system=[{"text": CLAUDE_SYSTEM_PROMPT}],     # the new file, not messages[0]
       messages=[{"role": "user", "content": [{"text": messages[1]["content"]}]}],
       inferenceConfig={"maxTokens": SEARCH_GEN_MAX_OUTPUT_TOKENS},
       toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": TOOL_NAME}}},
   )
   blocks = response["output"]["message"]["content"]
   tool_blocks = [b["toolUse"] for b in blocks if "toolUse" in b]
   # exactly one, with name == TOOL_NAME and a dict input, else RuntimeError
   wire = SearchQueriesWire.model_validate(tool_blocks[0]["input"])
   usage = response["usage"]                        # inputTokens, outputTokens, totalTokens, cacheReadInputTokens
   token_usage = TokenUsage(prompt=usage["inputTokens"], completion=usage["outputTokens"],
                            total=usage["totalTokens"], cached=usage.get("cacheReadInputTokens"))
   ```

   The guidance splice already applied by `build_queries_messages` to the user turn is
   kept; only the system text is replaced by the Claude file. Raise `RuntimeError` on:
   no `toolUse` block, more than one, a different `name`, a non-dict `input`, a wire
   validation error, or `usage` missing or with non-integer values. Trace with
   `tracing.traced_call` exactly as the OpenAI class does, `as_type="generation"`, model
   set to the Claude model id, `prompt_version` derived from the file name
   (`search_queries_claude_v1`). `reformulate` and `suggest` call an inner
   `OpenAISearchGenerationBackend` built with the same Langfuse client. — **codex**.
3. `live_planner_and_backends` in `runtime/agent.py`: `ClaudeSearchGenerationBackend`
   when `route().search_queries.backend == "claude"`, else the OpenAI class. — **codex**.
4. Tests in `tests/evidence_search/sourcing/test_search_generation.py` with `Stubber`:
   the complete Converse request (model id, system text, user text, `maxTokens`, tool
   spec, forced tool choice); a good reply parses and returns the wire and usage; a route
   fixture with a different model changes only `modelId`; each of the six failure shapes
   raises; `reformulate` and `suggest` reach the inner backend; builder selection per
   route. — **codex**.
5. Add the new prompt file's pin. — **lead inline** (one command).

**Done when:** the tests above pass; `make verify-fast` and `make prompt-guard` green.

**Gate:** `make verify-fast` + `make prompt-guard`.

### Phase D — Live checks and documents (N8) — lead (live evidence and adjudication are the lead's by doctrine)

Each live check names its route, command, evidence and stop condition. Budget 25 minutes
in total. The key is a short-term Bedrock key in `OPENAI_API_KEY` and
`AWS_BEARER_TOKEN_BEDROCK` in `backend/.env`.

1. **API shapes on Terra.** Route `bedrock-local`. A throwaway script in the scratch
   directory (not committed) that uses `resolve_openai_client` and makes three calls to
   the `standard` tier: `chat.completions.parse` with a small pydantic model, a
   `chat.completions.create` with one function tool and `tool_choice="required"`, and a
   streamed `create`. Evidence: each returns without error; the usage block is printed.
   Stop: any 4xx that names a parameter, recorded verbatim. About 2 minutes.
2. **Query generation side by side.** Three research questions from the repo's public
   fixtures. Run `generate_queries` under `bedrock-local` (OpenAI on Bedrock), then under
   `bedrock-local-claude` for Haiku, and under two overlay routes for Sonnet 5 and Opus 5
   (an overlay file in the scratch directory, not committed), through a throwaway script
   that builds the backend from the route. This is also the first real use of the
   overlay mechanism. Evidence: the
   queries and paraphrases, model id, token counts, pasted into `verification.md`. Stop:
   one tier failing is recorded, not fixed. About 5 minutes.
3. **One end-to-end run.** Route `bedrock-local`. Start the API with
   `make -C backend dev` and run one small project through the web app on a question
   from the fixtures, or use the command-line entry `policy_atlas.runtime.agent:main`
   with the same question; record which. Evidence: the run completes; Langfuse shows
   Cohere embed spans with the new profile and `input_kind`, OpenAI-on-Bedrock
   generation spans with `global.` model ids, and no span with a bare `gpt-` id; the
   database has `chunk_embedding` rows under `cohere_embed_v4_1536_v1` for chunks that
   also have OpenAI-profile rows. Stop at 15 minutes and record where it got to.
4. `.env.example`: the key in two variables, `POLICY_ATLAS_MODEL_ROUTE` with the three
   route names explained, `POLICY_ATLAS_MODEL_ROUTE_FILE` explained as the evaluation
   overlay, a pointer to the route file, in plain sentences. Remove the entries for the
   nine retired variables.
5. `docs/deferred.md`: supersede the "Bedrock routes" entry (contract F7); add the known
   gaps from contract § Verification evidence expected; record the nine retired
   variables so anyone who finds them in an old `.env` knows why they do nothing.
6. ADR 0038: set Status to Accepted with the owner's sign-off date from the plan gate.
7. `verification.md`: everything contract § Verification evidence expected lists,
   including the five prompt-module diffs (P5) and both adversarial-review records.

**Gate:** documents complete; `make prompt-guard` green.

### Phase E — Step-6 exit — lead (inline; two commands and the rubric walk)

Full `make verify` and `make audit`. Confirm every rubric box or write the justification.
Commit.

**Gate:** full `make verify` + `make audit` (gate 3).

## Call sites for Phase A step 5

| Module | Constant(s) today | Step name(s) | Default tier |
|---|---|---|---|
| `core/embeddings.py` | `EMBEDDING_MODEL` | (embeddings section, Phase B) | n/a |
| `runtime/planner.py` | `PLANNER_MODEL` (override) | `planner` | `frontier` |
| `runtime/agent_backend.py` | `AGENT_MODEL` (override), `AGENT_TRIAGE_MODEL` (override, follows `screen`) | `agent`, `agent_triage` | `frontier`, `mini` |
| `runtime/chat_prompt.py` | `CHAT_MODEL` (override) | `chat` | `standard` |
| `runtime/chat_backend_openai.py` | `reasoning_effort="none"` pinned (3 call sites) | knob `standard_reasoning_effort` | n/a |
| `evidence_search/group/group_clustering.py` | `GROUP_CLUSTERING_MODEL` | `group_clustering` | `mini` |
| `evidence_search/corpus/theme_grouping.py` | `DISCOVERY_MODEL`, `ASSIGNMENT_MODEL` | `theme_discovery`, `theme_assignment` | `mini` |
| `evidence_search/corpus/ranking.py` | `RERANK_MODEL` | `rerank` | `mini` |
| `evidence_search/synthesis/synthesis_backend.py` | `SYNTHESIS_MODEL` (override), `CASE_STUDIES_MODEL` (override, follows `synthesis`), `MRS_NOTE_MODEL` (override), `FULL_REPORT_INTRO_MODEL` (override); two `== "gpt-5.6-terra"` comparisons | `synthesis`, `case_studies`, `mrs_note`, `full_report_intro`; knob | `standard`, `standard`, `mini`, `mini` |
| `evidence_search/synthesis/grounding_judge.py` | `JUDGE_MODEL` | `grounding_judge` | `mini` |
| `evidence_search/assess/classify_prompt.py` (pinned) | `CLASSIFY_MODEL` | `classify` | `mini` |
| `evidence_search/assess/screen_prompt.py` (pinned) | `SCREEN_MODEL` | `screen` | `mini` |
| `evidence_search/extract/icf_prompt.py` (pinned) | `ICF_EXTRACTION_MODEL` | `icf_extract` | `mini` |
| `evidence_search/extract/iof_prompt.py` (pinned) | `EXTRACTION_MODEL` | `extract` | `mini` |
| `evidence_search/extract/finding_vetter.py` | `FINDING_VETTER_MODEL`, `ICF_FINDING_VETTER_MODEL` | `finding_vetter`, `icf_finding_vetter` | `mini` |
| `evidence_search/extract/relevance_annotator.py` | `RELEVANCE_ANNOTATOR_MODEL` (override) | `relevance` | `mini` |
| `evidence_search/sourcing/search_prompts.py` (pinned) | `SEARCH_QUERIES_MODEL`, `SEARCH_REFORMULATE_MODEL`, `SEARCH_SUGGEST_MODEL` | `search_queries`, `search_reformulate`, `search_suggest` | `mini` |

25 constants, 23 step names, 16 modules touched. "(override)" marks the nine
environment reads that are deleted. The `[steps]` table in the route file lists exactly
these 23 names. Constants keep their names so no importer changes; only
their right-hand side becomes `route().model_for("<step>")`. Existing tests that assert a
constant equals `"gpt-5.4-mini"` keep passing under the default route.

## Executor summary

- **lead** — Phase 0; Phase A steps 1, 2, 3, 4, 6, 8, 10; Phase C steps 1 and 5; Phases
  D and E. Reasons are given at each mark: design surfaces, override and fixture
  judgment, the approved dependency edit, the prompt text, live evidence, adjudication,
  and one-command inline edits.
- **codex** — Phase B and Phase C steps 2 to 4: judgment-bearing implementation against
  pinned wire contracts and named tests, so "done" is self-checkable.
- **fast-worker** — Phase A steps 5, 7, 9: mechanical transcription of exact tables with
  pinned tests.

## Out of this slice

Everything in contract § Future work. In particular: key minting in the container, any
`infra/` change, re-embedding deployed data, a shared Converse layer, deleting old
vectors, Langfuse pricing, prompt re-tuning for Luna.
