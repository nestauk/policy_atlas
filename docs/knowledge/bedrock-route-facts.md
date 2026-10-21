---
type: Integration quirk
title: Bedrock from London — which models answer, through which API, with which key variable
description: From eu-west-2 the GPT-5.6 family (Terra, Luna, Sol) answers through Bedrock's OpenAI-compatible endpoint under global.* profiles only (gpt-5.4-mini is absent, gpt-5.5 is US-only); Claude and Cohere answer through eu.* profiles via boto3 Converse / InvokeModel; each route names its key variable (Bedrock routes read AWS_BEARER_TOKEN_BEDROCK for both clients), and a missing Bedrock variable surfaces as an AccessDeniedException naming the IAM user; Terra refuses function tools without reasoning_effort "none" but parses structured output without it.
tags: [bedrock, openai, claude, cohere, boto3, credentials, live-probe]
timestamp: 2026-10-14
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
- **Terra's knob is about function tools, not structured output.** On Bedrock as on
  OpenAI direct, `chat.completions.create(tools=...)` on Terra returns 400 unless
  `reasoning_effort="none"`; `chat.completions.parse(response_format=...)` works
  without it (with more completion tokens spent on reasoning). Probed 2026-10-14. So
  moving a parse-only step (planner, agent) onto Terra needs no knob; a tool-bearing
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

# Citations

- [053 contract § Facts we rely on](../tasks/053-bedrock-local-route/contract.md) (model
  cards and probes, 2026-09-24/25)
- [053 verification § Live checks and § Review findings](../tasks/053-bedrock-local-route/verification.md)
  (live checks 1 to 3 and the Terra knob probe, 2026-10-14)
- `backend/src/policy_atlas/model_routes.toml`; `core/embeddings.py`
  `CohereEmbeddingBackend`; `evidence_search/sourcing/search_generation.py`
  `ClaudeSearchGenerationBackend`; `backend/.env.example`
