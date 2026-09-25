# ADR 0038 — Inference moves to Amazon Bedrock; models are named in a committed route file

- **Status:** Accepted — 2026-09-25 (Karlis Kanders, owner, task 045 plan gate).
- **Date:** 2026-09-25
- **Task:** [045-bedrock-local-route](../tasks/045-bedrock-local-route/contract.md)
- **Builds on:** [ADR 0005](0005-first-product-egress-embedding-grouping-seams.md) (first
  live provider calls, egress posture, tracing) ·
  [prompting.md](../specs/system/prompting.md) rule 12 and § Provider-specific.

## Context

Since task 009 the running product has called OpenAI directly for every AI step: text
generation through the Chat Completions API and embeddings through the embeddings API.
The specs always named Amazon Bedrock as the target route, and the deferred log recorded
the move as waiting on the evaluation slice, because a move was expected to change the
model family and reopen every model choice.

Two facts changed that. First, Bedrock now serves the exact OpenAI models the app uses,
through an endpoint that speaks the OpenAI API, so the text route can move without
changing model family. Verified from London on 2026-09-24 with the existing client and
no code change. Second, Bedrock also serves Anthropic's Claude models and Cohere's
embedding model through EU-only routing profiles, which gives the team a way to compare
vendors and to keep embeddings inside the EU.

At the same time, model names were literal strings in 15 code modules, a few with their
own environment overrides. Changing a model meant a code edit or a new variable. The
owner asked for model choices to be reviewable in the repository, not spread across
environment files.

## Decisions

1. **The inference route is Bedrock's `bedrock-runtime` endpoint in eu-west-2.** OpenAI
   models are called through the OpenAI-compatible path with `global.` inference
   profiles, which is the only way to reach them from London. Claude and Cohere are
   called through `boto3` with `eu.` profiles, which keep data in the EU. The `global.`
   profiles may process data outside the UK and EU. This matches the position of today's
   direct OpenAI calls and needs written sign-off before the staging slice.

2. **Every model the app uses is named in one committed file,**
   `backend/src/policy_atlas/model_routes.toml`, selected by one environment variable,
   `POLICY_ATLAS_MODEL_ROUTE`. The file has three layers: a `[steps]` table naming every
   text-model call site once with its default tier; named routes giving the model for
   each tier, the provider knobs, the embedding section and the search-queries backend;
   and optional per-route step exceptions naming a tier or a specific model. Code asks
   for a model by step name. An unknown route, step or tier fails at start-up. With the
   variable unset, the `openai-direct` route reproduces the pre-045 behaviour exactly.
   Secrets stay in the environment. An optional, uncommitted overlay file named by
   `POLICY_ATLAS_MODEL_ROUTE_FILE` can replace or add routes by name, so an evaluation
   run can try any model without editing the committed file. The nine existing per-step
   environment overrides, such as `POLICY_ATLAS_SYNTHESIS_MODEL`, are retired: the
   loader ignores them and logs one warning naming any that are set. There is one
   mechanism for choosing a model, and it is a file.

3. **Provider knobs live in the route file, not in code.** The pin of
   `reasoning_effort="none"` for the Terra model, previously a string comparison on the
   model name in two places and an unconditional literal in a third, becomes a knob on
   the route's standard tier. This is the prompting spec's rule applied.

4. **Embeddings move to Cohere Embed v4 on Bedrock**, 1536 numbers, through the EU
   profile, under a new embedding profile label `cohere_embed_v4_1536_v1`. The vector
   column and length are unchanged. Old OpenAI vectors keep their label and are ignored
   by every reader, which already filters on the label. Local databases re-embed on the
   next ingest. The deployed database is re-embedded by the staging slice. The embedding
   interface gains a "document or query" argument because Cohere embeds the two
   differently; the Langfuse wrapper forwards and records it.

5. **The first Claude backend is for search query generation and gets its JSON through
   tool use, not Bedrock structured output.** Tool use works on every Claude tier on
   Bedrock; structured output is listed as unsupported for Sonnet 5 and Opus 5. Tool use
   therefore makes the Claude tier a one-line edit in the route file. The reply must
   contain exactly one tool-use block with the expected name; anything else fails loud.
   Only the query generation call moves; reformulation and suggestion stay on the OpenAI
   model.

6. **The Claude backend gets a fresh, short system prompt, not a port of the OpenAI
   prompt** (prompting spec rule 12). The OpenAI prompts are unchanged. Five prompt
   modules are re-pinned only because a model constant moved out of them, with the diff
   recorded.

7. **Quality is not claimed by this move.** Luna stands in for gpt-5.4-mini, Terra for
   gpt-5.5, and Claude Haiku is the first Claude tier, all unmeasured. The evaluation set
   on branch `34-evaluate-against-ground-truth` is the regression net that licenses each
   choice. Comparing models means adding a route, not editing code.

## Consequences

- One dependency change: `boto3` moves from the operator-only group to the main
  dependency list, with Bedrock type stubs. `openai` stays.
- Local development needs a Bedrock short-term key in two variables, one for each
  client library. Keys expire within 12 hours.
- Staging and production need task-role permissions per model, Marketplace terms
  accepted per account, an organisation-level allowance for the `unspecified` region
  value that global profiles evaluate against, quota checks, and a re-embed job. The
  container mints its own short-term key from its task role. None of this is in task
  045; it is the staging slice.
- Moving further steps to Claude is one class per seam, following the query generation
  backend. A shared Converse layer is deferred until a third seam needs it.
- The deferred log's "Bedrock routes" entry is superseded by this ADR.
