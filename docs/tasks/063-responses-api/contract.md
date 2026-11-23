# Task contract: 063-responses-api

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** revision 5.3, 2026-11-23. Revision 4 was approved by the owner on 2026-11-20.
> The contract-stage adversarial review the same day (23 findings; a fresh reader on the
> lead's model stood in for Codex, which was out of quota) and a second live probe are
> folded in as revision 5 (§ Contract-stage review). The changes are material, so
> **Revision 5 approved (before planning): 2026-11-20 · owner**, with O14 and O15 ruled
> yes. Revision 5.1 applies the seven corrections of [plan.md](plan.md) § Contract
> corrections, accepted by the owner with the plan; revision 5.2 adds M16 at the owner's request; revision 5.3 keeps `chat` at `none` (plan item P1's fallback, owner ruling 2026-11-23 after the review stack) · **Plan approved (before
> implementation): 2026-11-20 · owner** (draft 2, after its adversarial review) ·
> ADR: [0050](../../adr/0050-responses-api-one-send-module-carried-reasoning.md) · Branch: `task/063-responses-api`.
>
> This is a system-level task: it changes shared code that every capability uses. It runs
> before the task 059 build, because 059's analyst needs a tool loop with reasoning on.
> The evidence behind each claim is in the task's `research/` folder (gitignored); § Evidence
> lists the files.

## Goal

1. Send every model call that uses the OpenAI SDK (software development kit) to the
   Responses endpoint (`/v1/responses`) on the `bedrock` route. Today they go to the Chat
   Completions endpoint (`/v1/chat/completions`). Results stay the same.
2. Let a step use reasoning and tools together, with the reasoning carried from one tool
   turn to the next. Chat Completions cannot do this on the current models.
3. Record enough on each call to diagnose a slow call.

## Why now, and why the whole surface

- OpenAI still supports Chat Completions and has announced no end date. The reason to move
  is tools: on GPT-6.1 Sol and later, "tool calling requires Responses". On Chat
  Completions, Terra accepts tools only with reasoning off, and Sol refuses tools.
- Task 059's analyst and the task 054 follow-up (the shared synthesis on Sol) both need
  tools with reasoning on.
- Only three call sites need the new endpoint for that. The rest move too, so the app has
  one model interface and not two. The order of work (§ Deliverable) makes this cheap: once
  every call goes through one module, the change of endpoint is a change to that module.
  The data-protection control is the same for every call (`store=false`).

## What the feasibility checks showed (2026-11-20)

| Question | Answer |
|---|---|
| Does Responses on Bedrock do what the app needs? | Yes, on Luna, Terra and Sol: streaming with function tools, streaming with a strict JSON schema, usage on the last stream event, a timeout for each request, an output-token limit. |
| Do the app's real request shapes work? | Yes, on Terra and Sol, with the six section tools and the three chat tools: allowed-tools in mode `required`, a tool forced by name, tools present with `tool_choice="none"`, parallel tool calls, tool history with no `tools` argument, a cache marker on a user message, an image input (Sol). |
| Can reasoning be carried between tool turns with `store=false`? | Yes. The provider's own items, with the reasoning as an encrypted block, were accepted back on Terra and Sol at `low` and `medium`. The app's rebuilt history (no reasoning) was accepted too. The prompt cache was read in full in every case. |
| Does prompt caching still work? | Yes, with one new fact: **a change of reasoning effort breaks the cache.** The same prompt start sent at `low` and then at `none` read 0 cached tokens (Terra; `low` then `low` read all 9,093). So steps that share a cached prompt start must run at the same effort. |
| What happens to a tool with no `strict` field? | The endpoint reports it as `strict: true`, with the schema unchanged. With `strict: false` it reports false. The app's section tools are not strict today, so every tool states `strict` explicitly. |
| How does a cut-off stream end? | With a `response.incomplete` event that carries usage, not with `response.completed`. |
| Does reasoning effort `none` mean no reasoning? | Yes: 0 reasoning tokens and about 1 s, against 190 to 630 tokens and 3 to 4 s at `low`. |
| Which efforts does each model accept? | Luna and Terra: `none` to `high`. Sol: `low` to `max`; it refuses `none`. No Sol step sends `none`. |
| May the deployed apps' keys call Responses? | The five Bedrock API keys have the same permission policy, and the laptop key works. Nothing in the policies stops the staging or production key. |
| Does Responses lower the stall rate? | No difference found (6, 7 and 4 stalls in 300 calls for each arm). |
| Do the deployed apps stall? | No (§ Stalls). |

## Deliverable

One pull request. The work is in stages, in this order. Each stage is its own commit or
commits and ends green, so a difference has one cause.

### Part 1: the move (results unchanged)

**Stage 1a: one way in, still on Chat Completions.**

| Id | Change |
|---|---|
| **M1** | Before any call site is edited, the full request of every route step is captured from today's code on the `bedrock` route: arguments, messages, tool definitions and schema bodies. This is the **baseline capture**. It is committed with the tests. |
| **M2** | `core/openai_client.py` becomes the only module that sends a model request (§ One way in). It offers three calls: a structured answer, a streamed answer and a tool turn. The 20 request sites that send their own requests today call it: 13 in the synthesis backend, the grounding judge, 3 in chat, the task agent's streamed turn, the Theory of change streamed draft and report, and the shared helper. Call sites still build chat-style messages and tools, as today. |
| **M3** | One shared reader turns a stream into text pieces and final usage. The seven hand-written chunk loops use it. The three JSON stream decoders stay; they read text pieces. |
| **M4** | Check for stage 1a: every step's request is identical to the baseline capture. The endpoint has not changed yet, so this stage is a pure reorganisation. |

**Stage 1b: the change of endpoint.**

| Id | Change |
|---|---|
| **M5** | Inside the shared module, one translation turns the chat-style request into a Responses request and reads the Responses answer. No call site changes in this stage. The prompt files' message builders are not edited, which keeps prompt-hash re-pins few. |
| **M6** | Every request sends `store=false`. No code uses `previous_response_id` (provider-side conversation memory) or background mode. |
| **M7** | Check for stage 1b, against the baseline capture, for every step: the same text parts in the same order; the same tools (names, descriptions, parameters) with `strict` stated; the same schema body; the same effort, timeout and output limit; the cache marker at the same place; `store=false`. |
| **M8** | The stream reader handles each way a stream can end: `response.completed` gives text and usage; `response.incomplete` raises the cut-off error (M10) and still records usage; `response.failed` or `error` raises a provider error that follows the site's retry rule; a stream that stops with no final event is a connection error. "First content" (the task agent's retry rule, the Theory of change watchdog) means the first text piece, not the first event: lifecycle events arrive in about 0.4 s, before any text. |
| **M9** | `core/usage.py` reads the Responses usage fields (input, output, cached, cache-write, reasoning tokens). Cost reports and Langfuse traces show the same numbers as before for the same call. |

**Stage 1c: three fixes and the clean-up.**

| Id | Change |
|---|---|
| **M10** | An answer cut at the output-token limit and a refusal each raise a named error that carries the site's label, on all three calls (structured, streamed, tool turn). Today a cut-off is an SDK error at the `.parse` sites, malformed JSON at the other sites, and silently kept by the chat reply stream; a refusal reads "was not parsed". Each site keeps what it does today with such an answer; the chat reply keeps the text already shown (plan decision 4). |
| **M11** | The chat reply stream counts its tokens. Today it never asks for usage. |
| **M12** | Tests: the fakes that copy the Chat Completions answer shape move to the Responses shape, or fake the shared module's three calls. The golden request fixture is replaced by the baseline capture and its checks (M4, M7), and covers every step (it misses 17 today and is captured on the legacy route). |
| **M13** | Scripts under `scripts/` that call the SDK use the shared module, so they send `store=false` too. Three scripts that already fail or misbehave today are left as they are and listed in `docs/deferred.md` (plan item P4). |
| **M14** | No Chat Completions call is left in `backend/src` or `scripts/`. There is no switch between the two endpoints. |
| **M15** | The Theory of change components spec is corrected in the three places that describe Responses as a second call path or name the `chat.completions.parse` wrapper (spec change 1, accepted by the owner 2026-11-20), with a line in the specs `log.md`. |
| **M16** | The chat reply stream is tried again when it fails before its first text piece, by the rule the planning stream already uses (two attempts, only for failures the tracing code calls retryable). Once any text has been shown it is never retried. Today a connection error before the first word fails the whole answer. Takes in a `docs/deferred.md` "Now" entry (owner ruling 2026-11-20). |

### Part 2: reasoning with tools

| Id | Change |
|---|---|
| **E1** | **Reasoning is carried between tool turns** (the standard pattern on Responses). The tool-turn call returns the provider's output items for that turn. The tool loop keeps them in memory for the life of that one loop and passes them back on the next turn in the form the probe proved (the `status` field removed from items that are not messages), followed by a result for every tool call. A tool call that the loop does not use gets a short fixed "not used" result. The items are never written to the database or to traces. The product's own record of each tool exchange is unchanged. This applies to the section writer's loop and the chat tool turn. If the build finds a case where carried items fail, that loop falls back to today's rebuilt history, which the probe showed works, and the limit is recorded. |
| **E2** | Ten steps that send `none` today get reasoning (table in § Efforts). |
| **E3** | **Same effort for steps that share a cached prompt start.** The plan lists, for each raised step, the steps that share its prompt start (from `synthesis/cache_modes.py` and the baseline capture). A partner moves to the same effort, or the plan states the cost of the lost cache and the owner rules. |
| **E4** | Output limits: where a raised step sends a limit today, the limit rises by 2,048 tokens at `low` and 4,096 at `medium` (reasoning tokens count against the limit). A step that sends no limit stays without one. A limit shared by several steps rises for all of them; a limit is a ceiling, so a step at `none` is not affected. The plan gives the table: step, file, old limit, new limit, and the tokens that one batch reserves against the Bedrock quota. |
| **E5** | Timeouts: a raised step's timeout on the `bedrock` route becomes the larger of its present value there and 60 s (the section writer's tool turn is 25 s on `bedrock` today, sized at `none`). After one week on staging each is re-sized by the rule of ADR 0043 (twice the healthy 99th percentile). No other timeout changes. |
| **E6** | A live tool loop on Sol passes (the section writer's tool turn with a route overlay naming `frontier`). No default route changes. This unblocks the 054 follow-up and task 059. |

### Part 3: diagnosis

| Id | Change |
|---|---|
| **S1** | Every traced attempt that received a response records its request id. An attempt that was cut before any response has no id; it records its start time, so it can still be found in AWS's audit log by time. Takes in the `docs/deferred.md` "Now" entry on request ids. |
| **S2** | The findings in § Stalls go into `docs/knowledge/` (`bedrock-route-facts`) and the stale stall entries in `docs/deferred.md` are corrected. |

Not built, on the evidence: a streaming watchdog, hedged requests, connection tuning, or
an AWS support case.

### Data handling

| Id | Change |
|---|---|
| **D1** | On Responses, Bedrock stores the input and output of a call for 30 days unless the call says `store=false`. Chat Completions has no such default. So M6 is a data-protection control. It is set in one place (M2) and checked for every step (M7) and for scripts (M13). |
| **D2** | The account setting for zero data retention cannot be used today. It was tried on 2026-11-20 and Bedrock then refused every GPT-6 call; it was reverted within minutes. AWS grants it for these models to an account on request. Owner ruling: no account setting for now. The request to AWS is an entry in `docs/deferred.md`. |
| **D3** | The owner updates the DPIA (Data Protection Impact Assessment) notes: the Responses endpoint; that account-level zero retention needs a grant from AWS; the Regions that served our calls (Luna in us-west-2, Terra and Sol in us-east-1, in 108,035 calls over 14 days); that traffic flagged by abuse checks can be kept for up to 30 days. This is an owner action and does not block the merge. |

## Efforts (E2)

Owner rulings, 2026-11-20: tool-using steps reason; key findings reason at `medium`; the
scoping planning conversation reasons a little; the options scoping judgement steps are
raised; no replays and no owner reads during the build.

| Step | What it does | Effort after | Why |
|---|---|---|---|
| `synthesise_section_turn` | The section writer's gather turns (6 tools) and its repair turn. | **`low`** | Owner ruling. |
| `synthesise_section_emit` | The streamed section prose. It shares the gather turns' cached prompt start. | **`low`** | E3: at a different effort it would lose that cache on every section. Its first words arrive a little later (O14). |
| `chat` (tool turn, streamed reply, final parse) | One step, three call sites that share a prompt start. | **`none`** (unchanged) | Planned at `low` (owner ruling for the tool turn; E3 for the other two; O14). At `low` a live answer failed and the next took 118 s to its first words, so plan item P1's fallback was applied and the step stays at `none` (owner ruling 2026-11-23). Raising it is on `docs/deferred.md`. The step is not split, so there is no new route step. |
| `synthesise_write_key_findings` | One call over the run's whole ledger of checked claims. | **`medium`** | Owner ruling. |
| `task_agent_scoping_turn` | The planning conversation for options scoping. | **`low`** | Owner ruling. |
| `longlist_constrain`, `longlist_distinct`, `longlist_authority` | Judgements over the options. | **`low`** | Owner ruling. |
| `option_profile_potential_impact`, `option_profile_ambition` | A judgement for each option. | **`low`** | Owner ruling. |
| `option_profile_line` | One descriptive line for each option. | `none`, unless E3 moves it | Writing. If it shares a prompt start with the two steps above, the plan says so and it moves to `low`. |
| `synthesise_write_case_studies`, `synthesise_propose_sections`, `synthesise_write_block_summary`, `synthesise_write_artefact_summary`, `synthesise_judge_summary` | Writing and summary steps. | `none` | Not ruled. |
| `task_agent_toc`, `toc_discover`, `toc_judge`, `toc_summarise`, `toc_sense_check` | Theory of change. | `none` | A colleague's capability. |

**Exception to the prompting spec (owner ruling O13).**
[prompting.md](../../specs/system/prompting.md) says prompts are written for the effort
mode they run at, and that effort on judgement steps is checked with a live comparison
before it is fixed. This task changes efforts with no prompt change and no comparison. The
prompts of the raised steps contain almost no step-by-step wording that reasoning would
repeat. The owner accepts the exception for this task. A `docs/deferred.md` entry asks for
the comparison on the five options scoping steps when task 059 reworks that area.

**How the raised steps are checked.** One live run after Part 2 (§ Acceptance checks). For
each raised step it records the number of calls, the median and longest latency, the cost
for each call and the cached-token share. The build's lead stops and asks the owner only
if: an answer is cut at the output limit or fails its schema; a step's median latency is
more than three times its earlier value and more than 10 s; or a writer step's cached-token
share falls below nine tenths of its earlier value.

## One way in (M2)

Today the route file is the one place that says which model, effort and timeout each step
uses. But the code that sends the request is in two shapes: 62 steps go through one shared
helper, and 20 request sites build and send their own requests.

After this task, `core/openai_client.py` is the only module that sends a model request.

- **What the module does for every call:** takes the chat-style request the site builds;
  translates it (M5); sets `store=false`; reads usage; raises the named errors; notes the
  request id.
- **What stays with each call site:** the messages and tools it builds; reading the route
  step's model, effort and timeout; the cache marker; its trace observation; what it does
  with each piece of streamed text; its retry rule; its fallback. The plan lists the retry rule
  of every site as it is today (most sites try three times; the task agent's stream tries
  twice before its first text; a streamed call whose text the user has seen is not retried).
  These do not change.
- **The test:** no file in `backend/src` or `scripts/` other than `core/openai_client.py`
  reaches `.responses` or `.chat.completions` on an SDK client. `core/embeddings.py` uses
  the SDK's embeddings call and is not part of this.
- **What it is not:** a layer that hides the provider. The Claude and Cohere paths stay.

**Theory of change.** Its request builders (`draft_stream_request`,
`report_stream_request` and the others) keep returning chat-style requests, so they and
their tests do not change shape. Only the lines that send the request change: they call
the shared module. Its first-content watchdog, its cancel and its tracing stay.

## Stalls: what the checks showed

The 4 to 6% stall rate was measured on runs from laptops. The checks compared a 900-call
laptop probe, AWS's audit log (CloudTrail) and the deployed apps' own traces (Langfuse).

- **The endpoint is not the cause.** Both endpoints stalled at the same rate.
- **The model and Bedrock are not the cause.** Bedrock finished every stalled laptop call
  in 2 to 8 s; the laptop then waited 53 to 148 s. Stalls came in bursts that hit every
  open connection from the laptop at once.
- **The deployed apps do not show it.** Over 14 days production had 0 timeouts in 7,919
  calls (7,499 Luna, 420 Terra, no Sol) and staging had 2 in 10,367 (8,661 Luna, 1,679
  Terra, 27 Sol). Those 2 were one `extract_interventions` answer that genuinely needed
  longer than its 35 s limit. The longest gap between Bedrock finishing and the app
  receiving was 1.0 s in production and 2.3 s in staging.
- **Limits of that evidence.** No deployed call was in flight during either laptop burst;
  production ran in the same 19 minutes and was not delayed. The evidence is thin for Sol
  and modest for Terra. Production runs the version of 2026-11-03, which does not trace
  retries (the audit log showed none). Staging's 156 streamed calls could not be matched
  for delay, though all completed.
- **So the delay sits on the laptop's side of the path.** Where exactly is not shown.

What follows: no stall remedy; laptop runs overstate latency, so a measure that sizes a
timeout comes from staging (E5); the step timeouts and three attempts of ADR 0043 stay.

## Terms

| Term | Meaning |
|---|---|
| **Chat Completions** | The older OpenAI request format (`/v1/chat/completions`): a list of messages in, one message out. |
| **Responses** | The newer OpenAI request format (`/v1/responses`): input items in, output items out (messages, tool calls, reasoning). |
| **Route step** | One named model call site in `backend/src/policy_atlas/model_routes.toml`, with its model tier, reasoning effort and timeout. There are 74. |
| **Request site** | A place in the code that sends a model request. There are 20 today; several steps can share one. |
| **Reasoning effort** | How much the model thinks before it answers: `none`, `low`, `medium`, `high` (Sol also `xhigh`, `max`). Thinking produces reasoning tokens, billed as output. |
| **Carried reasoning** | The provider's output items from one tool turn, passed back unchanged on the next. With `store=false` the reasoning is an encrypted block the app holds but cannot read. |
| **Baseline capture** | The full request of every route step, taken from today's code on the `bedrock` route before any edit (M1). |
| **Cached prompt start** | The beginning of a request that matches an earlier request and is billed at the cheaper cached rate. |
| **Stall** | A model call that returns nothing until the client timeout and then succeeds on a retry (as in task 057). |
| **`store`** | A Responses request field. `true` (the default) tells the provider to keep the input and output; `false` tells it not to. |
| **Luna / Terra / Sol** | The three model tiers: `fast` (gpt-6-luna), `standard` (gpt-6.1-terra), `frontier` (gpt-6.1-sol). |

## Read first

- [ADR 0041](../../adr/0041-bedrock-inference-route-and-model-route-file.md) (the route file),
  [ADR 0042](../../adr/0042-gpt6-switch-per-call-site-routing-and-caching.md) (one step for each call
  site, cache modes), [ADR 0043](../../adr/0043-queued-ingest-document-store-sql-retrieval-step-timeouts.md)
  (a timeout for each step), [ADR 0044](../../adr/0044-live-activity-streamed-sections-one-copy-source.md)
  (streamed sections and their shared cached prompt start).
- [prompting.md](../../specs/system/prompting.md) and
  [execution-orchestration.md](../../specs/system/execution-orchestration.md).
- [057 Bedrock integration brief](../057-queued-ingest/bedrock-integration-brief.md).
- `docs/knowledge/`: `bedrock-route-facts`, `gpt-56-terra-tool-calls-reasoning-effort`,
  `reasoning-effort-omitted-is-medium-gpt6-shapes`, `reasoning-model-output-cap`,
  `interface-change-sweeps-fakes-and-premise-pins`.
- `research/call-site-inventory.md` and `research/adversarial-review-contract.md`.

**Deferred work taken in** (`docs/deferred.md`): the writer's `reasoning_effort="none"` limit
(E2); request ids on traced attempts (S1); the chat reply stream's missing retry (M16). **Left on purpose:** web search for Theory of
change; invocation logging; short-term Bedrock keys; the three `Retry-After` parsers.
**Added:** the request to AWS for zero retention (D2); the effort comparison for the
options scoping steps (O13); the `extract_interventions` timeout; the three broken
scripts (M13); the chat-style internal request language (O16, added on 2026-11-20).

## Scope / Out of scope

- **In:** `core/openai_client.py`, `core/usage.py`, `core/tracing.py` (attempt fields),
  the request sites named in M2 and their modules, the tool loops for E1
  (`evidence_search/synthesis/synthesis_tools.py`, `section_prompt.py`,
  `runtime/chat_backend.py`, `runtime/chat_backend_openai.py`) and their fake backends,
  `model_routes.toml` (E2, E5), the files that hold the output limits of the raised steps
  (E4; the plan lists them), their tests, the SDK-calling scripts,
  `docs/knowledge/bedrock-route-facts.md`, `docs/deferred.md`, the Theory of change
  components spec (M15).
- **Out:**
  - Prompt wording. No prompt text changes, except the fixed "not used" tool result of E1,
    which the lead writes. Hash re-pins are for code edits in pinned files, and the diff of
    each is recorded.
  - Embeddings (Cohere through `boto3`, and the SDK's embeddings call) and the Claude path.
  - Database schema, public interfaces, the OpenAPI file, the frontend. Chat history and
    tool transcripts are stored in the product's own shape and need no conversion.
  - The model on any step, and the default route. New route steps: none.
  - Provider features Bedrock does not serve on this host: background mode, web search.
  - Theory of change efforts, timeouts, prompts and behaviour.
  - Live measurement of the legacy `openai-direct` route.

## Constraints & approval gates

- **Runtime egress (gate, hit; approved with revision 4).** Project data goes to the same
  provider and host, on a new endpoint path with a different storage default. Every call
  sends `store=false`.
- **Production config:** none.
- **Prompt hashes.** The guard hashes a pinned file's code, not only its text. The plan
  lists every pinned file the task edits. Known: `grounding_judge.py` (a request site),
  `section_prompt.py` (E1), and the pinned files that hold output limits (E4).
- **Dependencies:** none new. The pinned `openai>=2.44,<3` has the Responses calls. Of the two
  private SDK helpers imported today, the Theory of change request builder keeps its one
  (its builders do not change shape); the other is replaced only if a public call gives the
  same schema.
- **No schema, auth, CI, public interface or scaffold change.** If the build finds it needs
  one, it stops.
- **Stored extraction records** made through Chat Completions are reused after the move.
  No extraction step changes effort.

## Public / private boundary

- Public (committed): this contract, the rubric, the plan, the ADR, code, tests, the
  baseline capture (built from the repository's sanitised fixtures), `verification.md`.
- Private (gitignored `research/`): probe results, the audit-log extract, request ids, AWS
  key names, the probe inputs, the raw review record. No AWS account id, key or IP address
  in any committed file.

## Model route

`bedrock` only, the default route. Models and tiers unchanged. Route-file edits: efforts
(E2, E3) and timeouts of the raised steps (E5).

## Owner items

All ruled on 2026-11-20.

| Id | Decision | Ruling |
|---|---|---|
| **O1** | One task or several? | One task, one pull request. If Part 2 runs long it becomes its own pull request; Parts 1 and 3 do not wait. |
| **O2** | Keep a switch back to Chat Completions? | No. |
| **O3** | The legacy `openai-direct` route. | Unit tests only. |
| **O4** | Which `none` steps to raise. | § Efforts; no replays; the build's lead judges. |
| **O5** | Fix the two defects found on the way (M10, M11)? | Yes. |
| **O6** | Reuse stored extraction records? | Yes. |
| **O7** | Data retention. | `store=false` on every call. No account setting for now (D2). |
| **O8** | No stall remedy, no AWS support case. | Settled by the evidence. |
| **O9** | Theory of change: only how its requests are sent changes. | Agreed. The owner tells the colleague before the build. |
| **O10** | Find why laptop connections stall. | Optional, outside this task. |
| **O11** | Every model call through one place? | Yes (M2). |
| **O12** | Spec change 1. | Accepted (M15). |
| **O13** | The exception to the prompting spec. | Accepted. |
| **O14** | A change of effort breaks the prompt cache. So the section prose step and the whole `chat` step go to `low` with their tool turns, and `chat` is not split into two steps. | Yes. |
| **O15** | Carried reasoning (E1), the standard pattern, for the section writer's loop and the chat tool turn. | Yes. |
| **O16** | The app's internal request language stays chat-style; the module translates at the edge (plan P2). | Yes for this task. The owner calls it a stop-gap: a `docs/deferred.md` entry asks for the app's own request types after task 059. |

## Contract-stage review

A fresh reader on the lead's model attacked revision 4 (raw record in `research/`). All 23
findings were accepted in whole or in part.

| Finding | Outcome |
|---|---|
| 1. Carrying reasoning was never tested, and the tool loops cannot hold it. | A second probe tested it: accepted on Terra and Sol. E1 now names the pattern and the loops it changes (O15). |
| 2. The golden fixture does not pin messages and is captured on the legacy route. | Replaced by the baseline capture and two checks (M1, M4, M7). |
| 3. The effort measures could not be produced. | One live run after Part 2, with numeric stop rules (§ Efforts). |
| 4. Timeouts were sized with reasoning off. | E5. |
| 5. The prompting spec disagrees with "no prompt change, no comparison". | Recorded as an accepted exception (O13). |
| 6. "Only the endpoint" clashed with moving Theory of change request building. | Its request builders keep their shape; only the send lines change (§ One way in). |
| 7. Request shapes the app uses were not probed; `strict` could change silently. | Probed; all accepted. Every tool states `strict`. |
| 8. A new chat step needs a verb, a cache mode and a timeout. | No new step (O14). |
| 9. "Raise each limit" had no numbers and pointed at files out of scope. | E4. |
| 10. Stream endings were not specified. | M8. |
| 11. The caching check had no number and skipped Part 2. | A floor of nine tenths, after Part 1 and after Part 2. E3 for effort and cache. |
| 12. Token totals cannot match the audit log as written. | Matched call by call, by request id, for calls that got a response (§ Acceptance checks). |
| 13. A request id does not exist for a call cut before any response. | S1 reworded. |
| 14. The one-way-in test was not defined; retry rules differ by site. | Defined; retry rules pinned as they are (§ One way in). |
| 15. Scripts could send requests without `store=false`. | M13; the test covers `scripts/`. |
| 16. The deployed keys were not checked. | Their policies are the same as the working laptop key. A smoke on staging comes before production. |
| 17. Part 1 mixed several changes. | Stages 1a, 1b, 1c. |
| 18. The stall summary said more than the evidence. | § Stalls reworded with the counts for each model. |
| 19. Rubric and contract did not map. | Rubric rewritten. |
| 20. Rollback was thin. | § Rollback. |
| 21. Spec change 1 named one line of three. | M15. |
| 22. Wrong figures and labels. | Corrected. |
| 23. Why move the whole surface? | § Why now. |

## Rollback

- **An effort (Part 2):** the step's line in the route file, its row in the allowed-differences
  table of the request check, and a regenerated capture (one command).
  `synthesise_section_turn` and `synthesise_section_emit` roll back together.
- **The whole task:** revert the pull request. No stored data changes shape, so a revert is
  safe for data. It stays possible until task 059 or the 054 follow-up builds on the tool
  loop; after that, only efforts roll back.
- Results made at the new efforts are reused after a revert, because effort is not part of
  any stored fingerprint. This is accepted.

## Disciplines binding this slice

- **Same results first.** Part 1 changes how calls are sent and nothing a model sees.
- **One cause for each stage.** Stages 1a, 1b, 1c and Part 2 are separate commits, each green.
- **Compute, do not estimate.** Every figure in `verification.md` is read from a saved
  result file by a script.
- **Flag, don't drop.** A step whose behaviour differs on Responses is recorded.

## Stop conditions

Halt and escalate when:

- a step cannot pass M4 or M7 without a change to what a model sees;
- a request would go out without `store=false`, or a feature needs provider-side state;
- a schema, public-interface or dependency change turns out to be necessary;
- a Theory of change request builder would have to change shape;
- a stop rule of § Efforts is met.

## Acceptance checks

- `make verify` green; `make prompt-guard` green after the recorded re-pins.
- **M4:** after stage 1a, every step's request equals the baseline capture.
- **M7:** after stage 1b, every step passes the content check against the baseline capture,
  `store=false` included.
- **M2, M13, M14:** the one-way-in test passes for `backend/src` and `scripts/`.
- **M16:** a test shows the chat reply is tried again after a retryable failure before its
  first text piece, and is not tried again after one.
- **M8, M10:** one test for each stream ending, and one cut-off test and one refusal test
  for each of the three calls.
- **Live, `bedrock` route, after Part 1** (about 40 minutes of wall time, from a laptop):
  one Evidence search run on the fixed question, before and after; one options scoping run
  to the shortlist; one Theory of change draft and report; one chat turn that uses a tool;
  one task agent turn. The build's lead compares stage wall times, cost and cached-token
  share for each step, and the two reports for a difference in kind (a missing section,
  uncited claims), not wording. Cached-token share for each step with a cache mode is at
  least nine tenths of its earlier value.
- **M9, M11:** for the after run, the app's token counts equal the audit log's, call by
  call, matched by request id (streamed calls through their stream-end event), for every
  call that got a response. Calls with no response are listed and excluded. The audit log
  is read with the production read-only sign-in.
- **Live, after Part 2** (about 20 minutes): the same Evidence search run and options
  scoping run, one chat tool turn, one scoping planning turn. The figures and stop rules of
  § Efforts. Attempts that show the laptop stall pattern are counted and excluded from
  latency.
- **E1:** a test shows that the items of one tool turn are passed back unchanged on the
  next, that every tool call gets a result, and that no carried item reaches the database
  or a trace.
- **E6:** the Sol tool-loop smoke passes.
- **S1:** a traced attempt shows its request id, and that id finds the call in the audit log.

**After merge, not gating it:** a smoke on staging before production (one chat turn, one
short run); after one week on staging, the raised steps' timeouts are re-sized (E5) and the
staging traces are joined to the audit log to confirm no timeout that is not a genuinely
long answer.

## Verification evidence expected

In [verification.md](verification.md): the command results above; the before-and-after
tables; each prompt-hash diff; the list of fakes moved; the E4 limits table; the retry
rule of each site; public-safety confirmation; known gaps.

## Evidence (gitignored `research/`)

| File or folder | Holds |
|---|---|
| `call-site-inventory.md` | Every call site, seam, test double and stored shape. |
| `probe/` | The capability check and the 900-call stall comparison. |
| `probe2/` | The app's real request shapes, carried reasoning, effort and cache, stream endings, the keys' policies. |
| `effort-none/` | The check that `none` means no reasoning. |
| `cloudwatch/`, `prod-join/` | Bedrock metrics and audit-log events; the join with the deployed apps' traces. |
| `retention/` | The account retention setting: the read-back and the check after the revert. |
| `adversarial-review-contract.md` | The raw contract-stage review. |
| `openai-responses-notes.md`, `bedrock-responses-notes.md`, `aws-throughput-guidance-notes.md` | Sourced research, read 2026-11-20. |

## Risk tier & review focus

**Tier 3**: runtime egress (a new provider endpoint with a storage default that must be
turned off). Contract-stage and plan-stage adversarial reviews, a security lane, human deep
review.

Focus: a request site missed by M2; a request without `store=false`; a cache start that no
longer matches and raises cost silently; usage read from the wrong field; a stream that
ends early and is treated as complete; a fake that passes while the real shape differs; a
carried item that leaks into storage; scope creep into prompts or into Theory of change.
