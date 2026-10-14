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
| `make verify` (gate 2, re-run) | pass | backend 2648 passed in 7:00; mypy 313; prompt-guard 17 pins unchanged; frontend 617 |
| `make verify-fast` + `make prompt-guard` (Phase C gate) | pass | backend 2654 passed in 6:07 (6 new Claude tests); 17 pins unchanged |
| `make verify` + `make audit` (gate 3, step-6 exit) | pass | backend 2654 passed in 6:13; mypy 313; prompt-guard 17; frontend 617; no known vulnerabilities |

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
- Docs: contract build-time note; ADR renamed 0038 to 0039; plan links.

## Review findings

<!-- added by the review conversation (step 7) -->

## Rubric status

Walked at step 6 against [rubric.md](rubric.md). "Holds" means the evidence is in this
file or in the named test; "open" means it waits on the live checks.

| # | Item | Status |
|---|---|---|
| 1 | Satisfies the contract incl. D1 to D8, O1 (Terra), O2 (Claude for query generation only) | holds; four build-time deviations flagged above |
| 2 | `make verify` passes; live checks ran in budget | verify holds (gate 3 at Phase E); live checks 1 and 2 ran in budget; live check 3 ran to its 15-minute cap and failed at full-text ingest on a driver defect (recorded; owner asked about one re-run) |
| 3 | No unapproved gated change | holds: egress and the `boto3` move are the two approved gates; nothing under `infra/` |
| 4 | No generated files or secrets edited by hand; no key in the diff | holds; `.env` untouched, `.env.example` has empty values |
| 5 | No tests deleted, skipped or weakened without justification | holds; the one repointed guard is justified in § Test changes |
| 6 | Verification evidence recorded | this file |
| 7 | Known gaps and deferred seams in `docs/deferred.md` | holds; the "Bedrock routes" entry is superseded, gaps listed |
| 8 | Tier 3 review stack ran | **open**, review conversation |
| 9 | Unset means unchanged | holds: `test_default_route_reproduces_every_pre_045_model` plus the diff showing no other request field changed |
| 10 | No literal model name left; loader fails loud; retired variables ignored with a warning | holds: default-route test; `grep -rnE '= "(gpt-\|text-embedding-)' backend/src` empty; `grep -rn 'environ.get("POLICY_ATLAS_[A-Z_]*MODEL' backend/src` empty; loader tests |
| 11 | Claude fails loud, no silent fallback | holds: `test_claude_generate_queries_rejects_invalid_responses` |
| 12 | Only query generation moved | holds: `test_claude_reformulate_and_suggest_delegate_to_inner_backend` |
| 13 | Usage and tracing hold for Claude | holds: tests, and live check 2 returned token counts per call for all three Claude tiers |
| 14 | Prompt text unchanged; pins honest | holds: one new pin; six re-pins, each diff import + constant only (§ Diff summary) |
| 15 | Tests stay offline; scrub list extended | holds: `conftest.py`; the suite ran socket-denied throughout |
| 16 | Dependency change exactly as approved; `make audit` green after lock change and at exit | holds after Phase A; exit run at Phase E |
| 17 | A cold reader can set it up from `.env.example` | holds: file rewritten; the owner reached live check 2 from it, after one round trip on "the same key in both variables", which the file now states first |
| 18 | Nothing under `infra/` changed | holds: `git diff --stat 5f84bef..HEAD -- infra` is empty |
| 19 | Embeddings follow the route; old profile rows not read | holds: factory tests and `test_pending_chunks_with_old_profile_are_pending_for_cohere` |
| 20 | Cohere batching and input types | holds: `test_cohere_embedding_backend_batches_100_texts_in_order`, `..._sends_complete_request` for both kinds, the two `kind="query"` call sites |
| 21 | Claude tier is a one-line swap | holds: the mechanical test, and live check 2 ran Haiku, Sonnet 5 and Opus 5 by changing only the model line |
| 22 | Nothing built from § Future work | holds: no key minting, no `infra/`, no shared Converse layer, old vectors kept, live-mode detection unchanged |
| 23 | Route file committed, shipped and readable | holds: `test_route_file_ships_inside_the_package`; 23 steps; comments beside each non-obvious value |
| 24 | The web API follows the route | holds: `test_chat_embedding_backend_selects_cohere_in_live_mode` |
| 25 | Claude reply shape enforced, six failure shapes | holds: parametrised test |
| 26 | Overlay works and is bounded; Sonnet and Opus live calls ran through an overlay | holds: tests, and live check 2's Sonnet and Opus arms were selected from an uncommitted overlay file |

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

- Live check 3 did not get past full-text ingest, because of the driver's missing
  `__main__` guard (§ Checks beyond the build). Full-text chunk embedding through Cohere
  and the characterise step reading Cohere vectors are therefore shown by tests and by
  the identical backend code path on abstracts, not by a completed run. The owner
  decides whether one re-run with the fixed driver is worth the spend.
- Claude prompt quality is not measured (contract D8).

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
