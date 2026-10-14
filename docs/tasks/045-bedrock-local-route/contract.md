# Task contract: 045-bedrock-local-route

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** drafted, revision 3 (2026-09-25: embeddings move to Cohere; Claude tier
> kept at Haiku with the swap path made explicit; model choices move from environment
> variables to a committed route file). **Contract approved (before planning): 2026-09-25
> · Karlis Kanders (owner).** Gates approved the same day: runtime egress to Bedrock
> (OpenAI models via global profiles, Claude and Cohere via EU profiles) and the
> dependency change (`boto3` to main dependencies plus `boto3-stubs[bedrock-runtime]`).
> Open questions settled: O1 `frontier` maps to Terra; O2 Claude covers query generation
> only. **Plan approved (before implementation): 2026-09-25 · Karlis Kanders (owner)**,
> with two later owner decisions folded in the same day: an overlay route file for
> evaluations, and retirement of the nine per-step model environment variables. ADR:
> [0038](../../adr/0038-bedrock-inference-route-and-model-route-file.md), Accepted
> 2026-09-25. Adversarial reviews: contract-stage 10 findings, plan-stage 13 plus one
> lead finding, all adopted ([adversarial-review-contract.md](adversarial-review-contract.md),
> [adversarial-review-plan.md](adversarial-review-plan.md)). Branch:
> `aws-bedrock-integration` (owner-created; the usual name would be
> `task/045-bedrock-local-route`).

## Goal

Make the app run on a developer's laptop with all of its AI calls going to Amazon Bedrock
instead of directly to OpenAI. This includes embeddings, which move to Cohere Embed v4 on
Bedrock. In addition, let one step, the search query generation step, use an Anthropic
Claude model instead of an OpenAI model when a developer asks for it, and make the Claude
model a one-line swap.

This is the first of three slices in the Bedrock programme. It covers local development
only. The staging slice (task role permissions, CDK changes, short-lived keys,
re-embedding the deployed database) and the model quality slice (running the evaluation
set on the new models and re-tuning prompts) come later and are out of scope here.

## Why this is safe to do now

The app uses three OpenAI models today: gpt-5.6-terra for synthesis and chat, gpt-5.5
for the planner and agent, and gpt-5.4-mini for the fourteen high-volume steps. The team
verified on 2026-09-24 that Bedrock serves Terra through an endpoint that speaks the same
API the app already speaks: Terra answered a test call from the London region with the
existing OpenAI client and no code change. The other two are not reachable from London:
gpt-5.4-mini is not on Bedrock at all, and gpt-5.5 is US-only. So the slice keeps Terra
as it is and tries two stand-ins from the same OpenAI family: GPT-5.6 Luna, Bedrock's
cheap tier, in place of gpt-5.4-mini, and Terra in place of gpt-5.5. Luna also answered
the London test call. Whether Luna is good enough is not known yet; that is the
evaluation slice's question (D8). The remaining facts below come from the AWS model
cards and the live probes of 2026-09-25.

## Deliverable

A pull request where:

1. A developer sets a Bedrock key and `POLICY_ATLAS_MODEL_ROUTE=bedrock-local` in
   `.env`, runs the app or the dev command line, and every AI call goes to Bedrock: text
   generation to OpenAI models on Bedrock, embeddings to Cohere on Bedrock. Which models,
   and at which address, is written in a committed route file, not in anyone's `.env`.
2. Selecting the route `bedrock-local-claude` instead makes the search query generation
   step call Claude Haiku 4.5 on Bedrock through the EU routing profile. Swapping Haiku
   for Sonnet 5 or Opus 5 is a one-line edit to that route. Leaving the route variable
   unset gives exactly today's behaviour.
3. The test suite still runs fully offline and still passes.
4. `.env.example`, the deferred log and an ADR explain the change in plain language.

## Terms

| Term | Meaning |
|---|---|
| **Bedrock** | Amazon's hosted service for running AI models from several vendors, including OpenAI, Anthropic and Cohere. The app pays AWS, not the vendor. |
| **Endpoint** | The web address a program sends its requests to. Bedrock has two. This slice uses `bedrock-runtime` in the `eu-west-2` (London) region. |
| **OpenAI-compatible endpoint** | A Bedrock address that accepts requests in the same format as OpenAI's own API. It lets the existing OpenAI client library talk to Bedrock by changing only the address and the key. |
| **Inference profile** | A Bedrock model name with a routing prefix. `global.` means Bedrock may run the request in any of its regions worldwide. `eu.` means it stays inside the EU. The OpenAI models are only reachable from London with the `global.` prefix. Claude and Cohere have `eu.` profiles. |
| **Converse** | Bedrock's own request format for text generation, used by the Python library `boto3`. It works for Claude and most other vendors' models. Claude models do not accept the OpenAI-compatible format, so the Claude backend must use Converse. |
| **InvokeModel** | Bedrock's lower-level request format, also through `boto3`. Cohere Embed v4 is called this way. |
| **Tool use** | A way to make a model return structured data. The code declares a "tool" with a JSON schema, and asks the model to call it. The model's answer is the tool's input, already parsed into a dictionary. Every Claude tier supports this on Bedrock. |
| **Structured output** | A different way to get JSON that matches a schema. OpenAI calls it `response_format`. Bedrock's Converse calls it `outputConfig.textFormat`. On Bedrock only some Claude tiers support it (see § Facts). |
| **Bedrock API key** | A password-like string that stands in for AWS credentials. A short-term key lives up to 12 hours and is what a developer uses locally. Long-term keys and the container's own key minting are the staging slice's concern. |
| **Backend** (code word) | In this codebase, a class that implements one step of the pipeline against a provider. Each step has a `Protocol` (an interface), a live class and a `Stub` class used by tests. |
| **Search query generation** | The step that turns a research question into search queries: up to five keyword or boolean queries for the OpenAlex academic index and up to two natural-language paraphrases for the Overton policy index. The seam is `SearchGenerationBackend` in `evidence_search/sourcing/search_generation.py`; the method is `generate_queries`. The same seam has `reformulate` and `suggest`, which this slice does not move to Claude. |
| **Embedding** | A list of numbers that represents the meaning of a piece of text, so texts can be compared by distance. The app stores one per text unit in the `chunk_embedding` table as a JSON array. Today they have 1536 numbers. |
| **Embedding profile** | A text label stored with every vector that says which model produced it. Today: `openai_text_embedding_3_small_v1`. Every reader filters on the current profile, so vectors from a different model are never mixed with the current ones. |
| **Input type** (Cohere) | Cohere models embed a document and a search query differently. The caller says which it is sending: `search_document` for corpus text, `search_query` for a query. |
| **Wire model** | The pydantic class that describes the exact JSON shape the model must return. For query generation it is `SearchQueriesWire`. |
| **Route file** | New in this slice. A committed file, `backend/src/policy_atlas/model_routes.toml`, that lists every model the app uses, grouped into named routes such as `openai-direct` and `bedrock-local`. It lives inside the package so the built Docker image carries it, the same way the prompt `.txt` files do. One environment variable, `POLICY_ATLAS_MODEL_ROUTE`, picks the route. Model names are not secrets, so they belong in the repository where a reviewer can see them change. |
| **Tier** | A role a model plays in the app, not a specific model. This slice has three text tiers, `mini`, `standard` and `frontier`, matching the three OpenAI models in use today. Each route says which model each tier is. |
| **Step** | One named place in the pipeline that calls a text model, such as `screen`, `classify`, `synthesis` or `search_queries`. The route file lists every step once with its default tier. A route may override a single step with a different tier or a specific model. The code asks for a model by step name. |
| **TOML** | A plain-text configuration format with sections and comments, read by Python's standard library (`tomllib`). Chosen over JSON because it allows comments beside each model choice. |
| **Overlay file** | An optional second route file, not committed, named by `POLICY_ATLAS_MODEL_ROUTE_FILE`. Its routes are merged over the committed file's routes, adding new ones or replacing existing ones by name. It lets an evaluation script try any model without touching the committed file. |
| **Prompt hash guard** | `make prompt-guard`. Every prompt text file is pinned by a hash in `scripts/prompt_hashes.json`. Changing or adding prompt text is deliberate work and needs a re-pin. |
| **Live mode** | The app builds real provider backends instead of stubs. Today it decides this from whether `OPENAI_API_KEY` is set (`api/deps.py`). |
| **Decided / Leaning / Open** | Status words for decisions in this document. Decided means settled. Leaning means the recommended choice unless the reviewer objects. Open means the owner must choose at the approval gate. |

## Facts we rely on

Checked against the AWS model cards on 2026-09-24 and 2026-09-25, and confirmed by live
probe calls from London on 2026-09-25 where marked *probed*.

| Fact | Consequence for this slice |
|---|---|
| Bedrock serves GPT-5.6 Terra, Luna and Sol through the OpenAI-compatible endpoint. From London only the `global.` profiles work. Verified live for Terra and Luna. | The existing OpenAI client works unchanged. Model names must change. |
| `gpt-5.4-mini` does not exist on Bedrock. Fourteen backends use it. | The Bedrock routes set the `mini` tier to Luna. Prompt quality on Luna is not measured in this slice. |
| `gpt-5.5` exists on Bedrock but only in US regions and not through the London endpoint. | The Bedrock routes set the `frontier` tier to Terra (owner's choice, O1). |
| Bedrock has no OpenAI embedding model. Cohere Embed v4 is on Bedrock with an EU profile, `eu.cohere.embed-v4:0`, callable from London and staying inside the EU. Its default output is 1536 numbers, the same length as today. It accepts at most 96 texts per call. It distinguishes documents from queries by an input type. | Embeddings move to Cohere. Vector length and the database column stay the same. The batch size drops from 128 to 96. The embedding interface gains a way to say "this is a query". *Probed:* two texts returned two vectors of 1536 numbers for both input types; the input token count arrived in the `x-amzn-bedrock-input-token-count` response header. |
| Claude models on Bedrock do not accept the OpenAI-compatible format. They accept Converse. | The Claude backend uses `boto3`, not the OpenAI client. |
| Claude Haiku 4.5's model card lists Bedrock structured output as supported. The Sonnet 5 and Opus 5 cards list it as not supported on `bedrock-runtime`. All three support Converse tool use. All three have EU profiles: `eu.anthropic.claude-haiku-4-5-20251001-v1:0`, `eu.anthropic.claude-sonnet-5`, `eu.anthropic.claude-opus-5`. | To make the Claude tier a one-variable swap, the Claude backend gets its JSON through tool use, which works on every tier, not through structured output, which works on Haiku only. *Probed:* a forced tool call with the `SearchQueriesWire` schema returned valid output on all three tiers (Haiku 2.0 s, Sonnet 3.4 s, Opus 6.5 s; 5 queries and 2 paraphrases each). The structured-output path on Haiku was refused with "Model use case details have not been submitted for this account", an account-level Anthropic form. Tool use did not need it. Recorded for the staging slice. |
| Bedrock's structured output and strict tool use reject some JSON schema features: numeric bounds, string length bounds, recursion. `SearchQueriesWire` uses none of these. | No wire model change is needed. |
| `boto3` is already installed for the operator command line, but in the `ops` dependency group which the production image excludes. | Product code that imports `boto3` needs it in the main dependency list. This is a dependency change and needs approval. |
| A Bedrock API key works for both clients: the OpenAI client reads it from `OPENAI_API_KEY`, `boto3` reads it from `AWS_BEARER_TOKEN_BEDROCK`. Short-term keys expire within 12 hours. | Locally, one key value goes in two variables, and a developer re-mints it each working day. |
| The usage record Bedrock returns for OpenAI models has the same field names as OpenAI's. Converse returns different names. Cohere returns token counts in a response header, not the body. | OpenAI usage code is unchanged. The Claude and Cohere backends each need a small translation into the app's usage types. |
| Every reader of stored vectors filters on the embedding profile, and the ingest step embeds any chunk that has no vector for the current profile. | Switching the profile makes old vectors invisible and triggers re-embedding on the next ingest. No migration script is needed locally. The deployed database is the staging slice's concern. |
| The prompting spec says a model-family swap needs a fresh minimal prompt, not a port of the OpenAI prompt (`docs/specs/system/prompting.md` rule 12). | The Claude backend gets its own short system prompt file. It is prompt-bearing work and stays with the lead. |
| Five hash-pinned prompt modules also hold model-name constants: `classify_prompt.py`, `screen_prompt.py`, `icf_prompt.py`, `iof_prompt.py` and `search_prompts.py`. The guard hashes the whole file. | Moving those constants to route tiers changes five existing pins. They are re-pinned, and verification records a diff of each file showing that only the constant lines changed and no prompt text moved. |

## Read first

- [system/prompting.md](../../specs/system/prompting.md) § Provider-specific (never bake
  in) and rule 12 (fresh prompt at a model-family swap).
- [system/execution-orchestration.md](../../specs/system/execution-orchestration.md) §
  egress rules. The inference route is product egress and is gated.
- [engineering-considerations.md](../../agentic-ops/engineering-considerations.md) §
  Inference route: "OpenAI API under approved data controls first; target Amazon Bedrock".
  This slice is that target.
- [ADR 0005](../../adr/0005-first-product-egress-embedding-grouping-seams.md): how the
  first live provider calls, including embeddings, were gated and traced. The new backends
  follow the same posture.
- [deferred.md](../../deferred.md) § Characterise / embeddings / telemetry, entry
  "Bedrock routes", and the standing constraint from task 018 that nothing new couples to
  OpenAI-specific API surface.
- Code: `core/openai_client.py`, `core/embeddings.py`, `core/tracing.py`,
  `evidence_search/sourcing/search_generation.py`,
  `evidence_search/sourcing/search_prompts.py`,
  `evidence_search/synthesis/synthesis_tools.py` (the two query-embedding calls),
  `runtime/agent.py` (where live backends are built), `api/deps.py` (live mode),
  `tests/conftest.py` (environment scrub).

## Numbered needs

Every later section, the rubric and the plan use these numbers.

| # | Need | Where it lives today |
|---|---|---|
| N1 | Point every OpenAI text call at Bedrock with no per-call-site change. | `resolve_openai_client` in `core/openai_client.py`. The OpenAI library already reads `OPENAI_BASE_URL` from the environment, so this may need no code. |
| N2 | Take model names out of the code and into one committed, reviewable file, so a route can name models that exist on Bedrock. Retire the per-step environment variables so the file is the only mechanism. | 25 literal constants in 15 modules. Nine read an environment override, two of which make another step follow along. Two modules compare the model name as a string to decide a provider knob. |
| N3 | Move embeddings to Cohere Embed v4 on Bedrock, with the OpenAI class kept for rollback. | `OpenAIEmbeddingBackend`, `EMBEDDING_PROFILE`, `API_BATCH_SIZE` in `core/embeddings.py`; the traced wrapper in `core/tracing.py`; two query-embedding calls in `synthesis_tools.py`. |
| N4 | Let the search query generation step use Claude on Bedrock, chosen by configuration, with the Claude tier a one-variable swap. | `SearchGenerationBackend` seam; live class chosen in `runtime/agent.py`. |
| N5 | Give the Claude call its own fresh, short system prompt, hash-pinned. | New text file beside `search_queries_system_v3.txt`. |
| N6 | Keep the test suite offline and unaffected by a developer's `.env`. | `tests/conftest.py` scrubs a fixed list of variables. |
| N7 | Make `boto3` available to product code. | `backend/pyproject.toml`, `ops` group. |
| N8 | Explain the setup to a developer in plain language. | `backend/.env.example`, `docs/deferred.md`, a new ADR. |

## Decisions

**D1. Endpoint and profiles. Decided.** The OpenAI client points at
`https://bedrock-runtime.eu-west-2.amazonaws.com/openai/v1`. OpenAI models are named with
the `global.` prefix. Claude and Cohere are named with the `eu.` prefix. Data sent to an
OpenAI model through the global profile may be processed outside the UK and EU. This is
the same position as today's direct OpenAI calls, and needs written sign-off before
staging, not before this slice. Data sent to Claude and Cohere stays in the EU.

**D2. Local authentication. Decided.** A developer pastes one short-term Bedrock API key
into two variables: `OPENAI_API_KEY` for the OpenAI client and `AWS_BEARER_TOKEN_BEDROCK`
for `boto3`. No key minting code is added in this slice. Live mode detection in `deps.py`
is unchanged, because `OPENAI_API_KEY` is still set.

**D3. A committed route file, selected by one variable. Decided (owner, 2026-09-25).**

A new file `backend/src/policy_atlas/model_routes.toml` is the single source of truth for
which model each part of the app uses. It sits inside the package, found relative to the
module that reads it, so the wheel and the Docker image carry it without a build change
(adversarial finding F1). A new module `core/model_routes.py` reads it once at import
with the standard library and exposes the chosen route. One environment variable,
`POLICY_ATLAS_MODEL_ROUTE`, names the route. When it is unset the route is
`openai-direct`, which reproduces today's behaviour exactly.

The file has three layers, so a reader can answer "which model does step X use on route
Y" from the file alone, without repeating twenty lines per route:

1. **Steps**, once at the top: every place in the code that calls a text model, with its
   default tier. This is the complete list of steps; the loader refuses a name not on it.
2. **Routes**, one per named setting: the model for each tier, the provider knobs, the
   embedding section and the search-queries backend.
3. **Step exceptions**, optional per route: a step that should not follow its default
   tier on this route. The value is a tier name or a specific model id.

```toml
[steps]                           # every text-model call site, once; default tier for each
screen = "mini"
classify = "mini"
extract = "mini"
icf_extract = "mini"
finding_vetter = "mini"
icf_finding_vetter = "mini"
relevance = "mini"
rerank = "mini"
theme_discovery = "mini"
theme_assignment = "mini"
group_clustering = "mini"
grounding_judge = "mini"
mrs_note = "mini"
full_report_intro = "mini"
agent_triage = "mini"             # follows screen when only the screen override is set
search_queries = "mini"
search_reformulate = "mini"
search_suggest = "mini"
synthesis = "standard"
case_studies = "standard"
chat = "standard"
planner = "frontier"
agent = "frontier"

[routes.openai-direct]            # today's behaviour; the default when nothing is set
openai_base_url = "https://api.openai.com/v1"   # stated, so no stray env var can move it (F6)
[routes.openai-direct.text]
mini = "gpt-5.4-mini"
standard = "gpt-5.6-terra"
frontier = "gpt-5.5"
[routes.openai-direct.knobs]
standard_reasoning_effort = "none"   # Terra refuses tool calls otherwise (task 029)
[routes.openai-direct.embeddings]
backend = "openai"
model = "text-embedding-3-small"
profile = "openai_text_embedding_3_small_v1"
[routes.openai-direct.search_queries]
backend = "openai"

[routes.bedrock-local]            # every call to Bedrock from London; OpenAI models for text
openai_base_url = "https://bedrock-runtime.eu-west-2.amazonaws.com/openai/v1"
[routes.bedrock-local.text]
mini = "global.openai.gpt-5.6-luna"
standard = "global.openai.gpt-5.6-terra"
frontier = "global.openai.gpt-5.6-terra"   # owner's choice (O1); Sol is the step-up if needed
[routes.bedrock-local.knobs]
standard_reasoning_effort = "none"
[routes.bedrock-local.embeddings]
backend = "cohere"
model = "eu.cohere.embed-v4:0"
profile = "cohere_embed_v4_1536_v1"
[routes.bedrock-local.search_queries]
backend = "openai"
# [routes.bedrock-local.steps]    # example exception, not shipped:
# planner = "global.openai.gpt-5.6-sol"     # a specific model for one step
# grounding_judge = "standard"              # or a different tier

[routes.bedrock-local-claude]     # as bedrock-local, but query generation on Claude
# ... same as bedrock-local except:
[routes.bedrock-local-claude.search_queries]
backend = "claude"
model = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"   # swap: eu.anthropic.claude-sonnet-5 / claude-opus-5
```

The step names in the example are the plan's to settle against the code; the three
layers, the three routes and the fail-loud rule are the contract. In code, a module asks
for its model by step name, for example `route().model_for("screen")`. The loader
resolves step exception, then default tier, then the route's model for that tier. The
`search_queries` section is a backend switch, not only a model, so it stays its own
section; when its backend is `openai` the step uses the normal resolution.

What changes in code:

- Every module that today holds a literal model name asks the route for its step's model
  instead. `SEARCH_QUERIES_MODEL = "gpt-5.4-mini"` becomes a lookup by the step name
  `search_queries`. 25 one-line changes plus one knob change, in 16 modules. The plan's
  § Call sites table is the inventory: module, constant, step name, default tier (F10).
- **The nine existing per-step environment overrides are retired (owner, 2026-09-25).**
  Today `POLICY_ATLAS_SYNTHESIS_MODEL` and eight similar variables can change one step's
  model, and two of them make another step follow along. After this slice the route file
  and the overlay file are the only ways to choose a model. The loader ignores the nine
  variables and logs one warning at start-up naming any that are set and pointing at the
  route file, using the same warn-and-ignore pattern the agent backend already applies to
  stale variables. The plan's § Retired overrides table lists all nine. Nothing deployed
  sets any of them today, so no environment changes.
- The two places in `synthesis_backend.py` that compare the model name to the string
  `gpt-5.6-terra` to decide `reasoning_effort`, and the chat backend that pins the same
  value unconditionally, read the knob from the route instead. This is the prompting
  spec's rule that provider knobs live in configuration.
- The OpenAI client always receives its base address from the route, on every route,
  including OpenAI's own address for `openai-direct`. The library's habit of reading
  `OPENAI_BASE_URL` from the environment is therefore never exercised, and a stray value
  cannot move a selected route (F6). Keys stay in the environment.
- **Overlay file (owner, 2026-09-25). Decided.** If `POLICY_ATLAS_MODEL_ROUTE_FILE` names
  a file, the loader reads it after the committed file and merges its `[routes.*]`
  tables over the committed ones, whole route by whole route: an overlay route with the
  same name replaces the committed route; a new name adds a route. The `[steps]` table
  is never overridden. `POLICY_ATLAS_MODEL_ROUTE` then selects from the merged set. A
  missing or malformed overlay file fails at start-up like any other loader error. This
  is how the evaluation slice compares models without editing the committed file, and it
  is what replaces the retired per-step variables for quick local experiments. Tests are
  never affected: `conftest.py` scrubs the variable.
- An unknown route name, a route missing a tier, a step name in the code or in a route's
  exceptions that is not in the `[steps]` table, or a malformed file fails at start-up
  with a message naming the file and the key. Nothing falls back silently.

Why a file and not variables: model names change together and are reviewed together; a
pull request shows the change; a cold reader sees every model in one place; the
evaluation slice compares models by adding a route, not by editing code. Why one
selector variable: it is the same pattern the deployment already uses for environments,
and it keeps secrets and model choices apart. Why tiers plus step exceptions rather than
only one of them (owner's question, 2026-09-25): tiers keep a route to three lines and
make "swap the cheap model everywhere" one edit; step exceptions let the evaluation slice
pin one step to one model without touching the rest; the `[steps]` table makes the
mapping readable without opening the code.

**D4. Embeddings move to Cohere. Decided (owner, 2026-09-25).**

- A new class `CohereEmbeddingBackend` in `core/embeddings.py` calls
  `eu.cohere.embed-v4:0` through `boto3` InvokeModel, asking for float vectors of 1536
  numbers. `EMBEDDING_DIMENSIONS` and `validate_vector` stay as they are.
- Which embedding backend runs, and its model and profile, come from the route file's
  `embeddings` section (D3). The `openai-direct` route keeps today's values, so an unset
  environment behaves as today. The two Bedrock routes use Cohere.
- `EMBEDDING_PROFILE` and `EMBEDDING_MODEL` are read from the route at import. The Cohere
  profile is `cohere_embed_v4_1536_v1`. Old OpenAI vectors keep their profile and are
  ignored by readers. The next ingest re-embeds the chunks that lack a vector for the new
  profile.
- The `EmbeddingBackend` protocol gains an optional argument that says whether the texts
  are documents or queries. Its default means documents, so the stub, the OpenAI class
  and every existing caller are unchanged. The two query-embedding calls in
  `synthesis_tools.py` pass "query". The Cohere class maps this to Cohere's input type.
  The Langfuse wrapper `TracedEmbeddingBackend` in `core/tracing.py` accepts the argument,
  forwards it, and records it in the trace metadata; live runs always go through this
  wrapper, so without this the query path would fail before reaching Cohere (F3).
- The web API builds its own embedding backend for chat retrieval in `api/deps.py`,
  separately from the command line. Both use one factory function in
  `core/embeddings.py` that reads the route, so the API cannot be left on OpenAI while
  the command line is on Cohere (F2).
- The batch size constant drops from 128 to 96, Cohere's per-call limit. The request
  sends `truncate = "NONE"`, so over-length text is refused by Cohere with an error the
  app surfaces, never silently cut. The app already caps units at 2000 characters, so
  this should never fire (F5).
- Throttling from Bedrock reuses the existing backoff loop, catching the `boto3` error
  class instead of the OpenAI one.
- Token usage comes from the response header Bedrock adds. It is parked for the tracing
  wrapper the same way the OpenAI class parks it.

**D5. Claude backend shape. Decided.** A new class in
`search_generation.py`, named `ClaudeSearchGenerationBackend`, implements the
`SearchGenerationBackend` protocol.

- `generate_queries` calls Claude through `boto3` Converse. It gets JSON back through
  tool use: one tool whose input schema is `SearchQueriesWire.model_json_schema()`, and
  the request tells the model it must call that tool. The tool input comes back already
  parsed and is validated with `SearchQueriesWire.model_validate`. This mechanism works
  on Haiku, Sonnet and Opus, which is what makes the tier a one-variable swap. The
  alternative, Bedrock structured output, is listed as unsupported for Sonnet 5 and Opus
  5 and would tie the backend to Haiku. Probed on all three tiers on 2026-09-25; the
  mechanism is now Decided.
- The Converse reply is a message whose `content` is a list of blocks. The backend
  requires exactly one block of kind `toolUse`, whose `name` is the tool it asked for,
  and whose `input` is a JSON object. Any other shape raises `RuntimeError`: no tool-use
  block, more than one, a different tool name, a non-object input, an input that fails
  `SearchQueriesWire.model_validate`, or a `usage` field that is missing or not integers.
  It never falls back silently (F4).
- `reformulate` and `suggest` are passed through to an inner
  `OpenAISearchGenerationBackend`. Only the one step the owner named moves to Claude.
- Token usage from Converse is translated into the app's `TokenUsage`. The call is traced
  in Langfuse like the OpenAI call, with the Claude model name and the new prompt version.
- The model name comes from the route file's `search_queries` section (D3). The
  committed `bedrock-local-claude` route names Haiku 4.5. Region comes from `AWS_REGION`,
  default `eu-west-2`, the same rule the operator command line uses.
- No provider-specific tuning knobs are baked in (prompting spec § Provider-specific).
  Thinking stays at each model's default.

**D6. How the Claude backend is chosen. Decided.** By the route file's `search_queries`
section (D3): `backend = "openai"` or `backend = "claude"`. The live backend builder in
`runtime/agent.py` reads the chosen route. Switching a developer's machine to Claude
means setting `POLICY_ATLAS_MODEL_ROUTE=bedrock-local-claude`. Trying another Claude
tier means editing the model in that route, locally for an experiment or in a pull
request to make it the team's choice.

**D7. The Claude prompt. Decided.** A new file `search_queries_system_claude_v1.txt`,
written fresh and short, following the prompting spec's rules for a model-family swap.
The wire model's field descriptions carry the length and count rules, as they do for
OpenAI. The file is hash-pinned as a new entry. The three existing OpenAI prompt files
are not edited. The trace's `prompt_version` is derived from the file name.

**D8. Quality is not measured here. Decided.** This slice proves the routes work. It does
not claim Luna matches gpt-5.4-mini, that Claude's queries are as good as OpenAI's, or
that Cohere's vectors group documents as well as OpenAI's did. Verification records a
side-by-side of three research questions for the reader to look at. The evaluation set on
branch `34-evaluate-against-ground-truth` is the regression net that licenses model
choices later.

**Settled by the owner at the gate (2026-09-25):**

- O1. The `frontier` tier on the Bedrock routes maps to Terra, the cheaper choice. Sol
  stays available as a one-line route edit if the evaluation slice finds Terra short.
- O2. The Claude backend covers `generate_queries` only. `reformulate` and `suggest` stay
  on the OpenAI model. Moving them is a decision for the evaluation slice.

## Why Haiku first, and how to swap

The owner asked why Haiku 4.5 rather than Sonnet or Opus. Two reasons, neither about
Haiku being better.

1. Query generation is a high-volume, low-difficulty call. Today it runs on the cheapest
   OpenAI tier, gpt-5.4-mini. Haiku is the matching Claude tier, so the comparison in
   verification is like for like.
2. Haiku's model card is the only one of the three that lists Bedrock structured output
   as supported. D5 avoids that dependency by using tool use instead, so this reason no
   longer constrains the choice, but it explains the first draft.

Swapping later is one line in the route file: change the `search_queries` model in the
`bedrock-local-claude` route to `eu.anthropic.claude-sonnet-5` or
`eu.anthropic.claude-opus-5`. Nothing else changes, and the change is reviewed like any
other.
The verification for this slice includes one query-generation call on each of the three
tiers to prove the swap works, and the deferred log records that choosing a tier is a
quality question for the evaluation slice. The prompt file is written for the Claude
family, not for Haiku specifically, and a tier swap does not require a new prompt under
the prompting spec's rule 12, which is about model families.

## Future work: what the next slices will do

This section is for the planner and the implementer. Nothing in it is built in this
slice. Its purpose is to stop this slice from making choices that the next slices would
have to undo, and to name the seams they will pick up.

**Slice 2: staging and production (the deploy slice).**

- The container mints its own short-term Bedrock key from the ECS task role, using the
  `aws-bedrock-token-generator` package. The OpenAI client already accepts a function as
  its API key and calls it before each request, so `resolve_openai_client` should be
  written so that swapping a string for a function is a one-line change. `boto3` picks
  up the task role on its own.
- Live mode detection in `api/deps.py` stops depending on `OPENAI_API_KEY`, because the
  deployed container will not have one. The deployed stack already sets
  `PA_BACKEND_MODE=live`. This slice must not add any new dependency on that key.
- CDK changes in `infra/infra/policy_atlas_stack.py`: task role statements for each
  model's inference profile (three statements per model for the global profiles), the
  bearer-token action, the Bedrock base URL and model variables in the container
  environment, and `POLICY_ATLAS_MODEL_ROUTE` set per environment from `pa_config.json`.
  The staging slice adds `bedrock-staging` and `bedrock-prod` routes to the route file if
  they need to differ from `bedrock-local`; if not, it reuses one route. Optionally a VPC
  interface endpoint for `bedrock-runtime`.
- DevOps actions outside code: accept Marketplace terms for each model in each account;
  allow the region value `unspecified` for Bedrock in the organisation's service control
  policies, or the global profiles are denied; check and raise token-per-minute quotas;
  submit the Anthropic use case form if any Claude path needs it; written sign-off on
  data residency for the global profiles.
- Decide whether to re-embed the deployed database under the new embedding profile, based
  on cost. Every reader filters on the profile, so projects created before the switch
  would have no vectors the new code can read. Two features depend on them: the chat's
  retrieval over a project's sources, and the coverage count in the characterise step.
  Re-embedding is not strictly necessary. The owner's current view (2026-09-25) is that
  we could simply not support chat on older projects rather than pay to re-embed them;
  new projects embed under the new profile as they are created. The staging slice costs
  the re-embed (number of chunks times Cohere's per-token price) and makes the call. If
  chat on older projects is dropped, the app should say so plainly on those projects
  rather than show an empty answer. This slice should leave the profile constant derived
  from configuration, not hard-coded, so a re-embed, if chosen, is a normal ingest under
  the new setting.
- Remove `OPENAI_API_KEY` from the app secret once nothing reads it.
- Add Bedrock model names to the Langfuse pricing table in each project.

**Slice 3: model quality (the evaluation slice).**

- Run the evaluation set on branch `34-evaluate-against-ground-truth` against Luna in
  place of gpt-5.4-mini, and against each Claude tier for query generation, and decide
  which model each step uses. Comparing models means writing an overlay route file per
  experiment and selecting its route; the committed file changes only when a choice is
  made. It must not need code changes.
- Re-tune and re-pin any prompt that regresses on Luna. This slice leaves every OpenAI
  prompt hash unchanged so that the comparison starts from a clean baseline.
- Compare grouping and retrieval quality with Cohere vectors against the OpenAI baseline.
  The old vectors stay in the database under their old profile for exactly this reason.
  This slice must not delete them.
- Decide whether reformulation and suggestion also move to Claude (O2, deferred here).

**Later, if wanted.**

- Moving further steps to Claude. Each is one more class behind its existing seam,
  following the Claude backend in this slice as the pattern. If a third seam moves, pull
  the shared Converse plumbing (client, tool-use request, usage translation) into
  `core/`. Do not build that shared layer in this slice; one user is not enough.
- A Cohere Rerank backend behind the retrieval seam, already noted in the deferred log.
- Claude prompt caching, which needs explicit cache markers in the request. The prompting
  spec says prompts must stay append-only and deterministic so this remains possible.

## Scope / Out of scope

**In:**

- `backend/model_routes.toml`, new, with the three routes (N2).
- `core/model_routes.py`, new: reads the file, applies the selector variable and the
  existing per-step overrides, fails loud on a bad file or route (N2).
- `core/openai_client.py`: base address from the route (N1).
- Every module that holds a literal model name: ask the route for its step (N2). There
  are 25 such constants in 15 modules plus one unconditional knob in a 16th, and they
  reduce to the three tiers exactly. The two
  string comparisons on `gpt-5.6-terra` in `synthesis_backend.py` (the synthesis writer
  and the case-studies pass) read the route's knob instead, and the chat backend, which
  pins the same knob unconditionally, reads it from the route too. The plan lists all of
  them.
- `core/embeddings.py`: Cohere class, profile and model read from the route, protocol
  argument, batch size, and one factory function that returns the live embedding class
  for the route (N3).
- `core/tracing.py`: the traced embedding wrapper accepts and forwards the new argument
  and records it in the trace (N3, F3).
- `api/deps.py`: `get_chat_embedding_backend` uses the factory (N3, F2). Live mode
  detection in the same file is not changed.
- `evidence_search/synthesis/synthesis_tools.py`: the two query-embedding calls say
  "query" (N3).
- `evidence_search/sourcing/search_generation.py`: the Claude class (N4).
- `evidence_search/sourcing/search_queries_system_claude_v1.txt` and its entry in
  `scripts/prompt_hashes.json` (N5).
- `docs/deferred.md`: the "Bedrock routes" entry is superseded, not appended to. Its
  sequencing rule ("after the evaluation slice, because it is a model-family swap") is
  replaced with: the OpenAI models keep their family on Bedrock so no re-tuning is forced
  by this slice; Claude gets the fresh prompt the spec requires; the quality decisions
  that remain are listed and assigned to the evaluation slice (N8, F7).
- `runtime/agent.py`: choose the search generation backend and the embedding backend
  from the route (N3, N4).
- `tests/conftest.py`: scrub `POLICY_ATLAS_MODEL_ROUTE`, `POLICY_ATLAS_MODEL_ROUTE_FILE`
  and the new key variables (N6).
  Tests for the route loader, the Cohere backend, the Claude backend, the protocol
  argument, and backend selection, all against fake clients (N2, N3, N4).
- `backend/pyproject.toml`: move `boto3` to main dependencies; add the `bedrock-runtime`
  type stubs beside the existing stubs (N7).
- `backend/.env.example`, `docs/deferred.md`,
  `docs/adr/0038-bedrock-inference-route-and-model-route-file.md` (N8).

**Out:**

- Anything under `infra/`. No CDK, IAM, secrets or deploy workflow changes.
- Key minting inside the container (`aws-bedrock-token-generator`).
- Changing live mode detection in `api/deps.py`.
- Editing any existing prompt text. The three OpenAI `.txt` prompt files keep their
  hashes. Five prompt modules are re-pinned only because a model constant moved out of
  them; their prompt text is unchanged and the diff proves it.
- Re-embedding the staging or production database. Locally, re-embedding happens on the
  next ingest; for deployed data the staging slice decides on cost grounds whether to
  re-embed or to drop chat on older projects (§ Future work).
- Changing `EMBEDDING_DIMENSIONS`, the `chunk_embedding` table or the unit policy.
- Moving any other step to Claude.
- Measuring or claiming model quality. Re-tuning prompts for Luna.
- Langfuse pricing tables. That is a setting in the Langfuse project, not code.
- The frontend.

## Constraints & approval gates

Two gates are hit and need the owner's written approval at the contract gate:

- **Runtime egress.** The running product will send project data to Amazon Bedrock
  instead of OpenAI: to OpenAI models through the global profile, to Anthropic's model
  and Cohere's model through EU profiles. Bedrock is the documented target in the specs,
  but each new route still needs the approval recorded here.
- **Dependencies.** `boto3` moves from the `ops` group to the main dependency list, and
  `boto3-stubs[bedrock-runtime]` is added beside the existing stubs. No other package is
  added. `openai` stays, because the OpenAI models on Bedrock still use it.

Not hit: schema (the profile column already exists for this purpose), auth, CI,
production config, public interfaces, scaffold, generated files.

## Public / private boundary

Committable: all code, prompt files, tests, docs, the `.env.example` with empty values.
Private: the Bedrock API key, any `.env`, Langfuse traces, and the three research
questions used in the live check if they are not already public in the repo's fixtures.

## Model route

| Step | Today | After this slice, locally |
|---|---|---|
| Search query generation | `gpt-5.4-mini` on OpenAI | `global.openai.gpt-5.6-luna` on Bedrock, or `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (swappable to Sonnet 5 or Opus 5) when switched |
| Every other `gpt-5.4-mini` step | OpenAI | `global.openai.gpt-5.6-luna` on Bedrock |
| Synthesis, chat (`gpt-5.6-terra`) | OpenAI | `global.openai.gpt-5.6-terra` on Bedrock |
| Planner, agent (`gpt-5.5`) | OpenAI | `global.openai.gpt-5.6-terra` on Bedrock |
| Embeddings | `text-embedding-3-small` on OpenAI, 1536 numbers | `eu.cohere.embed-v4:0` on Bedrock, 1536 numbers, EU only |

Prompt-bearing change: one new prompt file for Claude (D7). Lead-authored.

## Disciplines binding this slice

- Keep decision status words as written: Decided, Leaning, Open.
- Add no flag, class or setting that does not change behaviour in this slice.
- Fail loud, never silently fall back, when a provider returns something unparseable or
  refuses an input.
- Leave deferred work as named entries in `docs/deferred.md`, not as silence.
- Nothing new couples to a provider-specific API feature that Bedrock's OpenAI-compatible
  endpoint, Converse or InvokeModel does not offer.

## Stop conditions

Halt and report when: a gate above is not approved; the OpenAI-compatible
endpoint rejects a request shape the app depends on (structured output, tools, streaming)
and no in-scope fix exists; the change would need a new database table or a new seam;
the live check budget below is spent.

## Acceptance checks

- `make verify` green: tests, type check, lint, build, knowledge validation.
- `make audit` green after the dependency move and again at exit. It is not part of
  `make verify`.
- `make prompt-guard` green. One new pin, the Claude prompt file. Five existing pins
  change because their modules lose a model-name constant; for each, verification shows
  the diff and that no prompt text changed. The three `.txt` prompt files and the
  synthesis prompt modules keep their hashes.
- **Pre-plan probe: done 2026-09-25.** Tool-use query generation succeeded on Haiku 4.5,
  Sonnet 5 and Opus 5 through the EU profiles. Cohere Embed v4 returned 1536-number
  vectors for both input types. Results are in § Facts we rely on. The probe script is a
  throwaway and is not committed.
- Deterministic tests, all offline:
  - Route loader: with `POLICY_ATLAS_MODEL_ROUTE` unset, every step, the embedding
    profile and the base address equal today's literal values, so every request is
    byte-identical to before this slice. With `bedrock-local`, the Bedrock names are
    returned. A step exception naming a tier, and one naming a specific model, both win
    over the default tier. An unknown route, a missing tier, an unknown step name (in
    code or in a route's exceptions) or a malformed file raises at import with the file
    and key named. Setting any of the nine retired variables changes nothing and logs
    one warning naming it. An overlay file
    that replaces a route by name and one that adds a new route both take effect; an
    overlay that names a missing file or fails to parse raises; the overlay cannot
    change `[steps]`.
  - Under `openai-direct` the OpenAI embedding class is built and the profile is
    `openai_text_embedding_3_small_v1`. Under `bedrock-local` the Cohere class is built
    and the profile is `cohere_embed_v4_1536_v1`.
  - The `reasoning_effort` knob for the standard tier comes from the route, and the two
    former string comparisons are gone.
  - `CohereEmbeddingBackend` against a fake `boto3` client: the complete request body is
    asserted (model id, texts, input type, float embedding type, 1536 dimensions,
    `truncate = "NONE"`); 100 texts go out as batches of 96 and 4; `search_document` by
    default and `search_query` when asked; vectors return in input order; a count
    mismatch, a missing vector, an over-limit input error and a malformed response body
    each raise; throttling retries and gives up after the existing attempt limit; the
    token count is read from the response header (F5).
  - The two query-embedding calls in `synthesis_tools.py` pass "query", and the traced
    wrapper forwards it and records it (F3).
  - `api/deps.py` returns the OpenAI embedding class under `openai-direct` and the Cohere
    class under `bedrock-local` (F2).
  - A stray `OPENAI_BASE_URL` in the environment does not change the address a selected
    route sends to (F6).
  - `ClaudeSearchGenerationBackend.generate_queries` against a fake `boto3` client: sends
    the tool schema and the system prompt, requires the tool, parses a good tool input,
    records usage, and sends whatever model id the route holds. It raises on: no tool-use
    block, two tool-use blocks, a block with a different tool name, a non-object input,
    an input that fails the wire model, and a usage field that is missing or not integers
    (F4).
  - `reformulate` and `suggest` on the Claude backend reach the inner OpenAI backend.
  - The backend builder returns the OpenAI classes under `openai-direct`, Cohere under
    `bedrock-local`, and Cohere plus Claude under `bedrock-local-claude`.
  - `conftest.py` scrubs every new variable.
- **Live check, pinned here.** Budget 25 minutes of wall time in total.
  1. The API-shape smoke test: one structured-output call, one tool call, one streamed
     call against Terra on Bedrock, from a throwaway script. About 2 minutes.
  2. `generate_queries` on three research questions, once with the OpenAI backend on
     Bedrock and once each with Claude Haiku, Sonnet and Opus. Outputs pasted into
     `verification.md`. About 5 minutes.
  3. One small end-to-end run through the dev command line on a stub corpus with live
     inference, to prove the route file and Cohere embeddings hold across a whole run,
     including re-embedding chunks that only have OpenAI vectors. Stop at 15 minutes if
     it has not finished and record where it got to.

## Verification evidence expected

In `verification.md`: the `make verify` and `make prompt-guard` output; the probe and
live check results with model names, vector lengths and token counts; the side-by-side
query outputs; a diff summary listing every module that moved from a literal model name
to a route tier; confirmation
that no key or `.env` is in the diff; the list of known gaps (Luna quality unmeasured,
Claude tier choice unmeasured, Cohere grouping quality unmeasured, deployed vectors not
yet re-embedded under the Cohere profile, Langfuse pricing to be set by hand); and the
adjudicated findings from [adversarial-review-contract.md](adversarial-review-contract.md).

## Risk tier & review focus

**Tier 3.** The slice changes where the running product sends project data (egress) and
changes dependencies. It does not change schema, auth or production config, so it is not
Tier 4.

Review stack: contract verifier, code review, security review (the key handling and the
three new outbound routes), adversarial review of this contract before planning and of
the plan before build, human deep review of the PR.

Focus for reviewers: that unsetting the new variables leaves every request byte-identical
to today; that the Claude and Cohere backends fail loud; that old vectors cannot be read
under the new profile; that no prompt text moved without a re-pin; that no `infra/` file
changed; that the test suite makes no network calls.
