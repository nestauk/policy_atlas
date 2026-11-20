# Task contract: 063-responses-api

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-11-20. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: due at step 4 (the model
> interface changes) · Branch: `task/063-responses-api`.
>
> This is a system-level task: it changes shared code that every capability uses. It runs
> before the task 059 build, because 059's analyst needs a tool loop with reasoning on.
> The evidence behind each claim is in the task's `research/` folder (gitignored); § Evidence
> lists the files.

## Goal

1. Send every model call that uses the OpenAI SDK (software development kit) to the
   Responses endpoint (`/v1/responses`) on the `bedrock` route. Today they go to the Chat
   Completions endpoint (`/v1/chat/completions`). Results stay the same.
2. Let a step use reasoning and tools together. Chat Completions forbids this on the
   current models; Responses allows it.
3. Cut what stalls cost, and record what causes them.

## Why now

- OpenAI still supports Chat Completions and has announced no end date. The reason to move
  is tools: on GPT-6.1 Sol and later, "tool calling requires Responses". On Chat
  Completions, Terra accepts tools only with reasoning off, and Sol refuses tools.
- Task 059's analyst and the task 054 follow-up (the shared synthesis on Sol) both need
  tools with reasoning on.

## What the feasibility checks showed (2026-11-20)

| Question | Answer |
|---|---|
| Does Responses on Bedrock do what the app needs? | Yes, on Luna, Terra and Sol: streaming with function tools, streaming with a strict JSON schema (text arrives piece by piece), usage on the last stream event, a timeout for each request, an output-token limit. |
| Does prompt caching still work? | Yes. With today's cache marker and with none, the second call reported the same cached tokens as on Chat Completions (within a few tokens). |
| Does reasoning effort `none` mean no reasoning? | Yes. 0 reasoning tokens and about 1 s, against 190 to 630 tokens and 3 to 4 s at `low`. The endpoint echoes `none`; it does not substitute a default. |
| Which efforts does each model accept? | Luna and Terra: `none` to `high`, with and without a tool. Sol: `low` to `max`; it refuses `none`. No Sol step sends `none` today. |
| Does Responses lower the stall rate? | No difference found: 6 of 300 calls stalled on Chat Completions, 7 of 300 on Responses, 4 of 300 on Responses streamed. 300 calls for each arm can only show a gap of about 3 percentage points or more. |
| Where is a stalled call stuck? | Not at the model. AWS's audit log shows Bedrock had finished every stalled probe call 2 to 8 s after it started. The client then waited 53 to 148 s for an answer that already existed. Shown for a laptop probe; a check on the deployed apps is running (S3). |
| Do stalls hit calls at random? | No. They come in bursts of a few seconds that hit every open connection at once (5 of 6 calls in flight, then 6 of 7). |
| Are all slow calls stalls? | No. In 14 days, 36 Sol calls and 15 Terra calls genuinely ran over 60 s at Bedrock (5,000 to 9,600 output tokens at normal speed). Seven Sol steps have a timeout of 45 to 90 s, so the app cuts these and retries. |

## Deliverable

One pull request, built in three parts in this order. Each part ends green before the next
starts.

### Part 1: the move (results unchanged)

| Id | Change |
|---|---|
| **M1** | The shared helpers in `core/openai_client.py` (`openai_kwargs`, `parse_structured`, `traced_parse`, `require_parsed`) call Responses. This moves 62 of the 74 route steps in one place. |
| **M2** | The 12 steps that call the provider directly move too: the 10 `synthesise_*` steps, `judge_grounding` and `chat`, plus the task agent's streamed turn and the Theory of change streamed draft and report. |
| **M3** | One shared reader turns a Responses stream into text pieces and final usage. The seven hand-written chunk loops use it. The three JSON stream decoders stay as they are; they read text pieces. |
| **M4** | The tool loop (section writer, repair, chat tool turn) uses the Responses tool layout: flat tool definitions, `function_call` items and `function_call_output` items. The two copies of the tool-call reader and tool-history builder become one. Tool order and the cached prompt start do not change. |
| **M5** | `core/usage.py` reads the Responses usage fields (input, output, cached, cache-write, reasoning tokens). Cost reports and Langfuse traces show the same numbers as before for the same call. |
| **M6** | Every request sends `store=false`. One test fails if any step's request lacks it. No code uses `previous_response_id` (the provider-side conversation memory). See D1. |
| **M7** | An answer cut at the output-token limit (`status: incomplete`) and a refusal each raise a named error with the step name. Today the first is an untried SDK error and the second reads "was not parsed". (Owner item O5.) |
| **M8** | The chat prose stream counts its tokens. Today it never asks for usage, so those tokens are missing from cost reports. (Owner item O5.) |
| **M9** | Tests: the fakes that copy the Chat Completions shape (about 100 tests in 20 files) move to the Responses shape. The golden request fixture is captured again and now covers all 74 steps (it misses 17 today). |
| **M10** | Scripts under `scripts/` that call the SDK move too. Two feasibility scripts that already fail on today's helpers are left alone and listed in `docs/deferred.md`. |
| **M11** | No Chat Completions call is left in `backend/src` or `scripts/`. There is no switch between the two endpoints (owner item O2). Rolling back is reverting the pull request. |

### Part 2: reasoning with tools

| Id | Change |
|---|---|
| **E1** | A step's route-file line can set any effort the model accepts, with tools attached. When effort is above `none` in a tool loop, the encrypted reasoning from one turn is passed back on the next turn, in memory only, never stored. |
| **E2** | The efforts of the 21 steps that send `none` today are reviewed one by one (table in § Efforts). Each change is one route-file line, plus a higher output-token limit for that step (reasoning tokens count against the limit: in the probe one call spent all 64 of its tokens on reasoning). Each change is measured (latency, cost, a quality read by the owner) and ruled by the owner. A step with no ruling keeps `none`. |
| **E3** | A live tool loop on Sol passes (the section writer's tool turn with the route overlay naming `frontier`). No default route changes. This unblocks the 054 follow-up and task 059. |

### Part 3: stalls

| Id | Change |
|---|---|
| **S1** | Every traced attempt records the response's request id and the time the response headers arrived. Takes in the `docs/deferred.md` "Now" entry on request ids. |
| **S2** | The timeouts of the seven Sol steps that cut genuinely long answers are re-sized from 14 days of Bedrock's own latency records. |
| **S3** | The remedy for the delivery delay. Decided by the owner once the check on the deployed apps reports (§ Open until the production check reports). |
| **S4** | A draft AWS support case with request ids, UTC (Coordinated Universal Time) timestamps, Region, model ids and the delivery-delay evidence. The owner sends it. |

### Data handling

| Id | Change |
|---|---|
| **D1** | On Responses, Bedrock stores the input and output of a call for 30 days unless the call says `store=false`. With a `global.` profile the stored copy sits in the Region that served the call. Chat Completions has no such default. So M6 is a data-protection control, not a style choice. |
| **D2** | AWS says `store=false` alone "does not guarantee zero data retention" and offers an account setting (retention mode `none`) for each Region. Whether to set it on the production account is an owner and DevOps decision (owner item O7). Not a code change. |
| **D3** | The owner updates the DPIA (Data Protection Impact Assessment) notes with: the Responses endpoint; the Regions that served our calls in the last 14 days (Luna in us-west-2, Terra and Sol in us-east-1, all 112,264 calls); and that traffic flagged by the provider's abuse checks can be kept for up to 30 days. |

## Efforts (E2): the 21 steps that send `none` today

"Tools" means the request carries function tools. Lean is the lead's proposal, not a ruling.

| Step | Tools | Lean | Why |
|---|---|---|---|
| `synthesise_section_turn` | yes | try `low` | The writer picks evidence without reasoning today (`docs/deferred.md`, synthesis). The main gain the move unlocks. |
| `chat` | yes | try `low` | Tool choice in chat turns. |
| `task_agent_scoping_turn` | yes | try `low` | Plans the next step of a task. |
| `synthesise_section_emit`, `synthesise_write_key_findings`, `synthesise_write_case_studies` | no | keep `none` | Streamed prose; reasoning delays the first words the user sees (task 058). Revisit in synthesis refinement. |
| `synthesise_propose_sections`, `synthesise_write_block_summary`, `synthesise_write_artefact_summary`, `synthesise_judge_summary` | no | keep `none` | No tool, so the move changes nothing for them. Revisit in synthesis refinement. |
| `longlist_constrain`, `longlist_distinct`, `longlist_authority`, `option_profile_line`, `option_profile_potential_impact`, `option_profile_ambition` | no | keep `none` | The owner set these to `none` on 2026-11-02 after reading replays (task 056). Task 059 reworks this area. |
| `task_agent_toc`, `toc_discover`, `toc_judge`, `toc_summarise`, `toc_sense_check` | some | not ours to change | Theory of change is a colleague's capability. Their endpoint moves (shared code); their efforts and timeouts change only if the colleague asks (owner item O9). |

## Open until the production check reports (S3)

A read-only check is joining the deployed apps' own call timings (Langfuse) to AWS's audit
log. It answers: do production stalls show the same pattern (finished at Bedrock, delayed
in delivery)?

| If the check shows | Then the lean for S3 is |
|---|---|
| The same delivery delay in production | Stream the calls of steps that write text at once, and cut a call when no event arrives for a set time (far shorter than the step timeout). The probe showed a stalled stream goes silent while a healthy one sends events without a gap. A feasibility check in the build sizes the silence limit for each step. Steps with long reasoning keep today's timeout and retry. |
| No delivery delay in production (a laptop effect) | No new remedy. S1, S2 and S4 stand; today's timeouts and retries stay. |
| Mixed or unclear | S1 lands first so the next two weeks of production traces answer it; the remedy becomes its own follow-up. |

What is not known, whatever the check shows: where the delay sits (AWS's front end, the
network path, or the client host). The support case (S4) is the route to that answer.

## Terms

| Term | Meaning |
|---|---|
| **Chat Completions** | The older OpenAI request format (`/v1/chat/completions`): a list of messages in, one message out. |
| **Responses** | The newer OpenAI request format (`/v1/responses`): input items in, output items out (messages, tool calls, reasoning). |
| **Route step** | One named model call site in `backend/src/policy_atlas/model_routes.toml`, with its model tier, reasoning effort and timeout. |
| **Reasoning effort** | How much the model thinks before it answers: `none`, `low`, `medium`, `high` (Sol also `xhigh`, `max`). Thinking produces reasoning tokens, which are billed as output and add latency. |
| **Stall** | A model call that returns nothing until the client timeout and then succeeds on a retry (as in task 057). |
| **Delivery delay** | A stall where Bedrock's records show the answer was finished in seconds but the client received it a minute or more later, or never. |
| **Burst** | A few seconds in which most open calls stall together. |
| **`store`** | A Responses request field. `true` (the default) tells the provider to keep the input and output; `false` tells it not to. |
| **Golden request fixture** | `backend/tests/core/data/call_site_kwargs_056.json`: the pinned request arguments of each step, checked by a test. |
| **Luna / Terra / Sol** | The three model tiers: `fast` (gpt-6-luna), `standard` (gpt-6.1-terra), `frontier` (gpt-6.1-sol). |

## Read first

- [ADR 0041](../../adr/0041-bedrock-inference-route-and-model-route-file.md) (the route file),
  [ADR 0042](../../adr/0042-gpt6-switch-per-call-site-routing-and-caching.md) (one step for each call
  site, cache modes), [ADR 0043](../../adr/0043-queued-ingest-document-store-sql-retrieval-step-timeouts.md)
  (a timeout for each step), [ADR 0044](../../adr/0044-live-activity-streamed-sections-one-copy-source.md)
  (streamed sections).
- [prompting.md](../../specs/system/prompting.md) and
  [execution-orchestration.md](../../specs/system/execution-orchestration.md).
- [057 Bedrock integration brief](../057-queued-ingest/bedrock-integration-brief.md): what was
  known about stalls before this task.
- `docs/knowledge/`: `bedrock-route-facts`, `gpt-56-terra-tool-calls-reasoning-effort`,
  `reasoning-effort-omitted-is-medium-gpt6-shapes`, `interface-change-sweeps-fakes-and-premise-pins`.
- `research/call-site-inventory.md`: every call site, shared seam, test double and
  Chat-Completions-only behaviour, with file and line.

**Deferred work taken in** (`docs/deferred.md`): the writer's `reasoning_effort="none"` limit
(synthesis; E2); request ids on traced attempts (S1). **Left on purpose:** web search for
Theory of change (its own slice; this task removes its blocker); invocation logging (the
audit log already gives what it would); short-term Bedrock keys; the three `Retry-After`
parsers.

## Scope / Out of scope

- **In:** `core/openai_client.py`, `core/usage.py`, `core/tracing.py` (attempt fields only),
  `evidence_search/synthesis/` (`synthesis_backend.py`, `section_prompt.py`,
  `grounding_judge.py`, `cache_modes.py` if a field name moves), `runtime/chat_backend_openai.py`,
  `runtime/task_agent.py`, `theory_of_change/backend.py` and `import_prompt.py` (endpoint
  only), `model_routes.toml` (E2, S2), their tests and fakes, the SDK-calling scripts.
- **Out:**
  - Prompt wording. No prompt text changes. Hash re-pins are for code edits in pinned
    files only, and the diff of each is recorded.
  - Embeddings (Cohere through `boto3`) and the Claude Converse path.
  - Database schema, public interfaces, the OpenAPI file, the frontend. Chat history and
    tool transcripts are stored in the product's own shape and need no conversion.
  - The model on any step, and the default route.
  - Provider features that Bedrock does not serve on this host: background mode, web search.
  - Theory of change efforts and behaviour (owner item O9).
  - Live measurement of the legacy `openai-direct` route (owner item O3).

## Constraints & approval gates

- **Runtime egress (gate, hit).** Project data goes to the same provider and host, on a new
  endpoint path with a different storage default. Approval of this contract approves the
  endpoint with `store=false` on every call (M6).
- **Production config (gate, hit only if O7 is yes).** The account retention mode is an AWS
  setting, changed by a person with that access, not by this task's code.
- **Prompt hashes.** At least 3 pinned files change code and need a re-pin
  (`section_prompt.py`, `import_prompt.py`, `grounding_judge.py`); 4 more if
  `parse_structured`'s signature changes. The `ChatCompletionMessageParam` annotation on
  plain system and user messages stays, which avoids 41 further re-pins.
- **Dependencies:** none new. The pinned `openai>=2.44,<3` already has the Responses calls
  (probe ran on 2.44.0). Two private SDK helpers imported today
  (`openai.lib._parsing._completions.type_to_response_format_param`,
  `openai.lib._pydantic.to_strict_json_schema`) are replaced by public calls where one exists.
- **No schema, auth, CI, public interface or scaffold change.** If the build finds it needs
  one, it stops.
- **Stored extraction records** made through Chat Completions are reused after the move:
  same prompts, same models, same efforts (owner item O6).
- **Spec note.** [theory-of-change/components.md](../../specs/capabilities/theory-of-change/components.md)
  describes Responses as "a new call path beside the existing wrapper". After this task it
  is the only path. Proposed spec change 1, for the owner and the colleague to accept; not
  edited until then.

## Public / private boundary

- Public (committed): this contract, the rubric, the plan, the ADR, code, tests,
  `verification.md` with figures and no identifiers.
- Private (gitignored `research/`): probe results, the audit-log extract, request ids, AWS
  key names, the probe inputs (document text), the support-case draft. No AWS account id,
  key or IP address in any committed file.

## Model route

`bedrock` only, the default route. Models and tiers unchanged. Prompt-bearing work stays
with the lead; this slice changes no prompt text. Route-file edits: efforts under E2 and
timeouts under S2, each with its measure.

## Owner items

| Id | Decision | Lean |
|---|---|---|
| **O1** | One task in three parts, or three tasks? | One task. If the E2 measures run long, E2 splits off; Parts 1 and 3 do not wait for it. |
| **O2** | Keep a switch back to Chat Completions? | No. Replace and delete; roll back by reverting. |
| **O3** | The legacy `openai-direct` route. | Keep it passing unit tests; no live measure. |
| **O4** | Which of the 21 `none` steps to raise (§ Efforts). | Try `low` on the three tool steps; keep the rest. |
| **O5** | Fix the two defects found on the way (M7, M8)? | Yes; the lines are rewritten in any case. |
| **O6** | Reuse stored extraction records made through Chat Completions? | Yes. |
| **O7** | Set the account retention mode `none` (D2), and update the DPIA notes (D3). | Yes to both; needs DevOps. |
| **O8** | The stall remedy (S3), after the production check. | See § Open until the production check reports. |
| **O9** | Theory of change: tell the colleague about the endpoint move, the short Sol timeouts (S2 touches `toc_merge`, `toc_choose`, `toc_review`, `toc_import`, `toc_verdict`) and the efforts they may now set. | Owner tells the colleague before the build. |
| **O10** | Send the AWS support case (S4). | Owner sends once S1 gives production request ids, or at once with the probe's ids. |

## Disciplines binding this slice

- **Same results first.** Part 1 changes the endpoint and nothing else. No effort, model,
  prompt or limit changes in Part 1, so a before-and-after difference has one cause.
- **Compute, do not estimate.** Every figure in `verification.md` is read from a saved
  result file by a script.
- **Flag, don't drop.** A step whose behaviour differs on Responses is recorded, not tuned
  away silently.
- Leave deferred seams as entries in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when:

- a step cannot give the same result on Responses without a prompt change;
- prompt caching on a real run falls below the baseline share for a step (the cost choices
  of task 056 rest on it);
- any request would go out without `store=false`, or a feature needs provider-side state;
- a schema, public-interface or dependency change turns out to be necessary;
- a Theory of change behaviour would have to change.

## Acceptance checks

- `make verify` green; `make prompt-guard` green after the recorded re-pins.
- **M11:** a search of `backend/src` and `scripts/` finds no `chat.completions` call.
- **M6:** the golden request fixture covers all 74 steps, and one test asserts `store=false`
  and the step's effort and timeout on each.
- **M5, M8:** for one recorded run, the token and cost totals on Responses match the
  provider's audit-log totals for the same calls.
- **Live, `bedrock` route** (scope: every capability has a model call, so one full run of
  each; about 40 minutes of wall time in total, named here so the gate approves it):
  - one Evidence search run on the fixed question, before and after Part 1: stage wall
    times, cost and cached-token share for each step, side by side; the owner reads both
    reports;
  - one options scoping run to the shortlist; one Theory of change draft and report (smoke
    only); one chat turn that uses a tool; one task agent turn.
- **E2:** for each step whose effort changes: median latency, cost for each call and the
  owner's quality ruling, before and after.
- **E3:** the Sol tool-loop smoke passes.
- **S1:** a traced attempt in Langfuse shows the request id; a forced timeout on a streamed
  call still shows one.
- **S2:** for each re-sized step, the new timeout against the 14-day p99 and maximum.
- **Stall rate, before and after:** the same probe (300 calls for each arm) rerun after the
  build, with its interval. Stated limit: it cannot show a change smaller than about 3
  percentage points, and the rate moves with the hour.

## Verification evidence expected

In [verification.md](verification.md): the command results above; the before-and-after
tables; each prompt-hash diff; the list of fakes moved; the stall probe rerun; the
production check's result and the S3 ruling; public-safety confirmation; known gaps.

## Evidence (gitignored `research/`)

| File or folder | Holds |
|---|---|
| `call-site-inventory.md` | Every call site, seam, test double and stored shape. |
| `probe/` | The capability check (`capability.md`) and the 900-call stall comparison (`analysis.md`). |
| `effort-none/` | The check that `none` means no reasoning. |
| `cloudwatch/` | 14 days of Bedrock metrics and audit-log events, and the join that showed the delivery delay (`delivery_lag.txt`). |
| `prod-join/` | The check on the deployed apps (running at the time of drafting). |
| `openai-responses-notes.md`, `bedrock-responses-notes.md`, `aws-throughput-guidance-notes.md` | Sourced research, read 2026-11-20. |

## Risk tier & review focus

**Tier 3**: runtime egress (a new provider endpoint with a storage default that must be
turned off). Contract-stage and plan-stage adversarial reviews, a security lane, human deep
review.

Focus: a call site missed by the move; a request without `store=false`; a cache marker that
no longer matches and raises cost silently; usage read from the wrong field; a streamed
answer cut short and treated as complete; a fake that passes while the real shape differs;
scope creep into prompts or into Theory of change.
