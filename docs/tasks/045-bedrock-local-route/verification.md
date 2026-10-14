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

<!-- Phases C to E are appended below as they land. -->

## Checks beyond the build

<!-- filled at step 6 -->

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
