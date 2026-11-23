---
type: Integration quirk
title: Bedrock from London — which models answer, through which API, with which key variable
description: From eu-west-2 the GPT-5.6 family (Terra, Luna, Sol) answers through Bedrock's OpenAI-compatible endpoint under global.* profiles only (gpt-5.4-mini is absent, gpt-5.5 is US-only); Claude and Cohere answer through eu.* profiles via boto3 Converse / InvokeModel; each route names its key variable (Bedrock routes read AWS_BEARER_TOKEN_BEDROCK for both clients), and a missing Bedrock variable surfaces as an AccessDeniedException naming the IAM user; Terra refuses function tools without reasoning_effort "none" but parses structured output without it.
tags: [bedrock, openai, claude, cohere, boto3, credentials, live-probe]
generated:
  by: process:okf-migrate
  at: 2026-11-05
sources:
  - resource: "../tasks/053-bedrock-local-route/contract.md"
    title: "[053 contract \u00a7 Facts we rely on](../tasks/053-bedrock-local-route/contract.md) (model cards and probes, 2026-09-24/25)"
  - resource: "../tasks/053-bedrock-local-route/verification.md"
    title: "[053 verification \u00a7 Live checks and \u00a7 Review findings](../tasks/053-bedrock-local-route/verification.md) (live checks 1 to 3 and the Terra knob probe, 2026-10-14)"
  - resource: "../tasks/063-responses-api/contract.md"
    title: "[063 contract \u00a7 What the feasibility checks showed and \u00a7 Stalls](../tasks/063-responses-api/contract.md) (probes, audit-log and trace joins, 2026-11-20)"
  - resource: "../tasks/063-responses-api/verification.md"
    title: "[063 verification](../tasks/063-responses-api/verification.md) (live checks on the Responses endpoint, 2026-11-20)"
  - resource: "backend/src/policy_atlas/model_routes.toml"
    title: "`backend/src/policy_atlas/model_routes.toml`; `core/embeddings.py` `CohereEmbeddingBackend`; `evidence_search/sourcing/search_generation.py` `ClaudeSearchGenerationBackend`; `backend/.env.example`"
---

# Rules

- **Which models, which API, from London (`eu-west-2`).** GPT-5.6 Terra, Luna and Sol
  answer through `https://bedrock-runtime.eu-west-2.amazonaws.com/openai/v1` with the
  existing OpenAI client, under the `global.openai.*` profile names only (the request
  may run outside the UK/EU). `gpt-5.4-mini` is not on Bedrock; `gpt-5.5` is US-only.
  Claude (`eu.anthropic.*`) does not accept the OpenAI-compatible format: use `boto3`
  Converse. Cohere Embed v4 (`eu.cohere.embed-v4:0`) is InvokeModel, 96 texts per call,
  1536 numbers by default, and distinguishes `search_document` from `search_query`.
- **Each route names its key variable.** On a Bedrock route both the OpenAI client and
  `boto3` read `AWS_BEARER_TOKEN_BEDROCK` (`api_key_env` in the route file); the
  OpenAI key in `OPENAI_API_KEY` is left alone, so both may be set at once. If the
  Bedrock variable is unset, `boto3` falls back to the machine's ordinary AWS
  credentials and Bedrock answers `AccessDeniedException` **naming the IAM user and
  the profile**. That reads like a permission gap; check the variable before treating
  it as one. A 401 from `api.openai.com` quoting a `bedrock-…` key means the route
  selector is unset, not a bad key.
- **What streams on the OpenAI-compatible endpoint (task 058, probes 1, 2 and the cache
  probe).** A streamed strict `json_schema` response delivers a string field's text as it
  is generated (prose ahead of claims); a streamed forced tool call delivers its arguments
  in one burst at the end, so it cannot show progress. On a live run the writer called its
  emit tool itself on turn 2, before any forced turn, so "stream the forced turn" showed
  nothing. The shape that streams AND keeps the cached prompt prefix is a no-argument ready
  tool on the open turns, then a write turn with the same tools kept, `tool_choice`
  "none" and no `response_format`, parsed as the tool's arguments; adding
  `response_format` or dropping the tools broke the cache prefix.
- **Every OpenAI-SDK call goes to the Responses endpoint (`/openai/v1/responses`) with
  `store=false`.** `core/openai_client.py` is the only module that sends a request; call
  sites build chat-style requests and the module translates. On Responses, Bedrock keeps a
  call's input and output for 30 days unless the call says `store=false`; Chat Completions
  had no such default. The account setting for zero retention (mode `none`) made Bedrock
  refuse every GPT-6 call when it was tried, and one account serves production, staging
  and laptops; AWS grants it for these models on request.
- **Tools and reasoning work together on Responses, and reasoning is carried.** On Terra
  and Sol a tool turn may reason. The provider's output items of a turn (the reasoning as
  an encrypted block) are passed back on the next turn with a result for every tool call;
  a request that has tools and an effort above `none` asks for the block with
  `include=["reasoning.encrypted_content"]`. Histories that mix carried turns with turns
  rebuilt from the product's own record are accepted, with and without `tools`. Sol
  refuses effort `none`; Luna and Terra accept `none` to `high`. The rule below about
  Terra's knob describes Chat Completions, which no code calls now.
- **A change of reasoning effort breaks the prompt cache.** The same prompt start sent at
  `low` and then at `none` read 0 cached tokens. Steps that share a cached prompt start
  must run at the same effort. Tools come first in the cached start, so a request with no
  `tools` shares nothing with one that has them (the chat reply and final parse read
  nothing from the chat tool turns' cache).
- **A tool with no `strict` field is read as `strict: true` on Responses.** The module
  states `strict` on every tool, `false` where the tool has none.
- **How a Responses stream ends.** `response.completed` carries the usage. A cut-off answer
  ends with `response.incomplete`, which also carries usage; a failure with
  `response.failed` or an `error` event. Lifecycle events arrive in about 0.4 s, before any
  text, so "first content" must mean the first text piece. The request id is in the
  `x-request-id` header (equal to `x-amzn-requestid`) and finds the call in the AWS audit
  log (CloudTrail `requestID`).
- **An error while a stream is being read is a raw `httpx` error.** The SDK wraps a
  failure at request open (`APIConnectionError`, `APITimeoutError`) but not one raised while
  the body is read (`ReadError`, `ReadTimeout`, `RemoteProtocolError`), so a retry rule
  written against the SDK's errors does not see a dropped stream.
- **What the AWS audit log (CloudTrail) holds for a Responses call.** A non-streamed call
  has `inputTokens` (uncached input only) and `outputTokens` (reasoning included); there
  are no cached, cache-write or reasoning fields. A streamed call has a request event and a
  stream-end event, joined by `parentRequestId`, and **no token counts at all**. Langfuse
  keeps reasoning tokens apart from output, so a join compares the log's output with
  output plus reasoning.
- **Carried items are accepted in more forms than first seen.** Requests that keep `status`
  on function-call items, or drop a reasoning item's `id`, were accepted on Terra and Sol.
  A reasoning item with no encrypted content cannot be sent back with `store=false`.
- **Effort `low` buys little reasoning on these steps.** 58 reasoning tokens over 74
  section turns on Terra; Sol produced a reasoning item on the first tool turn only. The
  exception is a loop that forces tool turns: chat at `low` spent about 5,000 reasoning
  tokens on each late turn.
- **Parallel first calls each write the same prompt start to the cache.** A burst of
  calls that start together cannot read one another's write, so the cached share of a
  small step differs between two runs for no other reason; compare the calls in order.
- **Stalled calls are a laptop-side effect, not the provider's.** From a laptop 4 to 6% of
  calls return nothing until the client timeout and succeed on a retry, on both endpoints
  alike. Bedrock had finished each stalled call in 2 to 8 seconds; stalls came in bursts
  that hit every open connection at once. Over 14 days production had 0 timeouts in 7,919
  calls and staging 2 in 10,367 (one answer that genuinely needed longer than its limit).
  So laptop runs overstate latency: size a timeout from staging traces, not from a laptop.
- **Terra's knob is about function tools, not structured output.** On Bedrock as on
  OpenAI direct, `chat.completions.create(tools=...)` on Terra returns 400 unless
  `reasoning_effort="none"`; `chat.completions.parse(response_format=...)` works
  without it (with more completion tokens spent on reasoning). Probed 2026-10-14. So
  moving a parse-only step (task_agent, agent) onto Terra needs no knob; a tool-bearing
  step (synthesis, chat) does, and the route file carries it keyed by model id.
- **Claude JSON through tool use, not Bedrock structured output.** Structured output
  is supported on Haiku only and was refused for this account ("Model use case
  details have not been submitted"); a forced tool call with the wire model's JSON
  schema returned valid output on Haiku 4.5, Sonnet 5 and Opus 5, which is what makes
  the Claude tier a one-line route edit.
- **Usage shapes differ.** OpenAI models on Bedrock return usage with OpenAI field
  names (plus `cached_tokens`, `cache_write_tokens`, `reasoning_tokens`); Converse
  returns `inputTokens`/`outputTokens`/`totalTokens` (input excludes cached reads);
  Cohere returns the input token count in the `x-amzn-bedrock-input-token-count`
  response header, not the body.
- **Model ids carry a prefix.** The Bedrock routes name the same OpenAI models as
  `global.openai.gpt-6-luna` (Terra, Sol alike). A price table keyed by the OpenAI id must strip
  `global.openai.` before the lookup (`theory_of_change/cost.py`, `scripts/cost_per_run.py`), or
  every Bedrock call reports as unpriced (054 review, Codex, 2026-11-05).
