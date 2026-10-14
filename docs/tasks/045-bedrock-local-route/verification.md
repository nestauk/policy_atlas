# Verification: 045-bedrock-local-route

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
   route still reproduces every pre-045 value. On the Bedrock routes `mini` and `fast`
   both resolve to Luna.
2. **Agent triage no longer follows screen.** Task 051 made its default a literal. Only
   the case-studies "follows synthesis" rule remained, and it is retired with the
   variables.
3. **Six pinned prompt modules changed hash, not five.** `chat_prompt.py` became a pinned
   module after the design. Every one of the six diffs is an import line plus the
   constant line (§ Diff summary).
4. **ADR renumbered to 0039.** Task 051 took 0038.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (Phase 0 baseline, before any change) | pass | backend 2618 passed in 6:05; mypy 311 files; frontend 617 tests; infra 86 |
| `make verify-fast` (Phase A gate) | pass | backend 2635 passed in 5:51 (17 new loader tests); mypy 313 files; ruff clean |
| `make prompt-guard` (Phase A gate) | pass | 16 pins unchanged after the re-pin of six |
| `make audit` (Phase A gate, after the lock change) | pass | no known vulnerabilities |

| `make verify` (gate 2, end of Phase B, first run) | **fail**, 17 of 2648 | Two root causes, both in tests: (1) `FakeEmbedder` in `test_synthesis_tools.py` kept the old `embed_texts` signature, 16 failures; (2) `test_image_hygiene.py` pinned "the image ships no AWS SDK", a premise the approved dependency move overturned, 1 failure. See § Test changes. |
| `make verify` (gate 2, re-run) | _pending_ | |

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
  re-applied the functional edits by hand, so the diff contains only the changes above.
  Recorded as a knowledge candidate.

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
- Tests, 6 new in `test_search_generation.py` plus one in `test_agent.py`: the complete
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

### Live probe: Cohere through the route, refused by AWS (2026-10-14)

`live_embedding_backend()` under `bedrock-local` built `CohereEmbeddingBackend` and sent
the request correctly; AWS answered `AccessDeniedException`: the developer's IAM user
is not authorised for `bedrock:InvokeModel` on
`arn:aws:bedrock:eu-west-2:<account>:inference-profile/eu.cohere.embed-v4:0`. The
2026-09-25 probe of the same call succeeded because it used a short-term key minted
from a console session with broader rights; the key in use on 2026-10-14 is a long-term
key bound to the IAM user, which has no policy for the Cohere (and, see below, Claude)
EU profiles. A follow-up probe through Converse was refused for every inference
profile tried (Claude Haiku 4.5, Sonnet 5 and Opus 5 on `eu.`, and even
`global.openai.gpt-5.6-luna`), while the same key succeeds on the OpenAI-compatible
Chat Completions path for the OpenAI global profiles. So the user's policy covers the
OpenAI-compatible path but grants no `bedrock:InvokeModel` on inference-profile
resources. This is an account permission gap, outside the slice; live checks 2 and 3
wait on it. The owner was asked for an IAM policy on the developer identity allowing
`bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` on
`arn:aws:bedrock:*:*:inference-profile/*` and `arn:aws:bedrock:*::foundation-model/*`.

## End-to-end command

<!-- filled at step 6 -->

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
- Docs: contract build-time note; ADR renamed 0038 to 0039; plan links.

## Review findings

<!-- added by the review conversation (step 7) -->

## Rubric status

<!-- filled at step 6 -->

## Intent & assumptions

<!-- filled at step 6 -->

## Known unverified items

<!-- filled at step 6 -->

## Public safety

<!-- filled at step 6 -->

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

## Deferred work

<!-- filled at step 6 -->
