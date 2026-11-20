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
3. Record enough on each call to diagnose a stall. The checks for this task showed that the
   deployed apps do not stall; the stalls are seen from laptops only (§ Stalls: what the
   checks showed).

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
| Where is a stalled call stuck? | Not at the model. AWS's audit log shows Bedrock had finished every stalled laptop call 2 to 8 s after it started. The laptop then waited 53 to 148 s for an answer that already existed. |
| Do stalls hit calls at random? | No. They come in bursts of a few seconds that hit every open connection from the laptop at once (5 of 6 calls in flight, then 6 of 7). |
| Do the deployed apps stall? | No. In 14 days production had 0 timeouts in 7,919 calls and staging had 2 in 10,367. No answer arrived late: the longest gap between Bedrock finishing and the app receiving was 1.0 s in production and 2.3 s in staging. Production made 797 calls in the same minutes as the laptop's stalls and none was delayed. |
| Are all slow calls stalls? | No. Staging's 2 timeouts were one `extract_interventions` call whose answer (about 7,100 output tokens) genuinely needed longer than its 35 s limit. From laptops, 36 Sol calls and 15 Terra calls genuinely ran over 60 s at Bedrock in 14 days. |

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
| **E2** | The `none` steps that use tools go to `low` (owner ruling 2026-11-20; table in § Efforts): `synthesise_section_turn` and the chat tool turn, which becomes its own route step. Each gets a higher output-token limit (reasoning tokens count against the limit: in the probe one call spent all 64 of its tokens on reasoning). Latency and cost are measured before and after. Every other step keeps its effort. |
| **E3** | A live tool loop on Sol passes (the section writer's tool turn with the route overlay naming `frontier`). No default route changes. This unblocks the 054 follow-up and task 059. |

### Part 3: diagnosis

| Id | Change |
|---|---|
| **S1** | Every traced attempt records the response's request id. With it, any slow call can be matched to AWS's audit log in one step; the production check for this task had to match by time and token counts. Takes in the `docs/deferred.md` "Now" entry on request ids. |
| **S2** | The findings in § Stalls go into `docs/knowledge/` (`bedrock-route-facts`) and the stale stall entries in `docs/deferred.md` are corrected, so later work does not size timeouts or design remedies from laptop stall rates. |

Not built, on the evidence (owner item O8): a streaming watchdog, hedged requests, connection
tuning, or an AWS support case. The deployed apps show no fault to remedy.

### Data handling

| Id | Change |
|---|---|
| **D1** | On Responses, Bedrock stores the input and output of a call for 30 days unless the call says `store=false`. With a `global.` profile the stored copy sits in the Region that served the call. Chat Completions has no such default. So M6 is a data-protection control, not a style choice. |
| **D2** | AWS says `store=false` alone "does not guarantee zero data retention" and offers an account setting (retention mode `none`) for each Region. Whether to set it on the production account is an owner and DevOps decision (owner item O7). Not a code change. |
| **D3** | The owner updates the DPIA (Data Protection Impact Assessment) notes with: the Responses endpoint; the Regions that served our calls in the last 14 days (Luna in us-west-2, Terra and Sol in us-east-1, all 112,264 calls); and that traffic flagged by the provider's abuse checks can be kept for up to 30 days. |

## Efforts (E2): the 21 steps that send `none` today

Owner ruling, 2026-11-20: **every `none` step that uses tools goes to `low`.** "Uses tools"
means the model chooses which tool to call. Two call sites carry tools without choosing
(noted below); they stay at `none`.

| Step | Tools | Effort after | Why |
|---|---|---|---|
| `synthesise_section_turn` | yes: the writer's gather turns (6 tools) and the repair turn | **`low`** | Owner ruling. The writer picks evidence without reasoning today (`docs/deferred.md`, synthesis). |
| `chat`, tool turn only | yes: 3 read tools | **`low`** | Owner ruling. The `chat` step covers three call sites today (tool turn, streamed prose, final parse). The tool turn becomes its own route step, `chat_tool_turn`, so the streamed prose keeps `none` and its first words are not delayed. This also follows the rule of one route step for each call site. |
| `chat`, streamed prose and final parse | no | `none` | No tool. |
| `synthesise_section_emit` | carried, never called | `none` | It sends the tool list with `tool_choice="none"` only so the cached prompt start matches the gather turns. Streamed prose. |
| `synthesise_write_key_findings` | one forced tool, fallback path only | `none` | The tool is an output format, not a choice. The main path is streamed with no tool. |
| `synthesise_write_case_studies`, `synthesise_propose_sections`, `synthesise_write_block_summary`, `synthesise_write_artefact_summary`, `synthesise_judge_summary` | no | `none` | No tool. Revisit in synthesis refinement. |
| `task_agent_scoping_turn` | no | `none` | A structured reply, no tool. |
| `longlist_constrain`, `longlist_distinct`, `longlist_authority`, `option_profile_line`, `option_profile_potential_impact`, `option_profile_ambition` | no | `none` | No tool. Set to `none` by the owner on 2026-11-02 (task 056); task 059 reworks this area. |
| `task_agent_toc`, `toc_discover`, `toc_judge`, `toc_summarise`, `toc_sense_check` | no | `none` | No tool. Theory of change is a colleague's capability (owner item O9). |

For the two raised call sites the build records median latency, cost for each call and the
cached-token share, before and after, and raises the output-token limit so reasoning tokens
do not cut answers short. A cost or latency rise that the owner would not expect from
`low` (more than a few seconds for each turn) is flagged before the change stays.

## Stalls: what the checks showed

The 4 to 6% stall rate was measured on runs from laptops (task 057's probes and build
rounds, and this task's probe). The checks for this task compared three sources: a 900-call
laptop probe, AWS's audit log (CloudTrail), and the deployed apps' own traces (Langfuse).

- **The endpoint is not the cause.** Chat Completions and Responses stalled at the same rate.
- **The model and Bedrock are not the cause.** Bedrock finished every stalled laptop call in
  2 to 8 s. No queue, no throttle, no slow generation.
- **The deployed apps are not affected.** 0 timeouts in 7,919 production calls and 2 in
  10,367 staging calls over 14 days, and those 2 were one genuinely long answer.
  Production ran in the same minutes as the laptop's stalls, on the same model and Region,
  with no delay.
- **So the delay sits on the laptop's side of the path**: the laptop, its network, or the
  route from it to AWS. Which of these is not shown. The pattern (every open connection
  hit at once, new connections fine, delays near 51 s and 102 s) fits connections that go
  dead and recover, but that mechanism is an inference, not a finding.

Limits of this evidence: production runs the version of 2026-11-03, which does not trace
retries (they were checked through the audit log instead, and none was found); staging's
156 streamed calls could not be matched for delay, though all completed; production was
active on 7 of the 14 days.

What follows from it:

- No stall remedy is built in this task.
- Laptop runs overstate latency and stall rates. A measure that decides a timeout or a
  design should come from staging, or be checked against the audit log.
- The step timeouts and the three attempts for each step (ADR 0043) stay. They cost the
  deployed apps nothing and protect laptop runs.
- One timeout is worth a look outside this task: `extract_interventions` (35 s) cut a
  7,100-token answer on staging twice. Whether the answer should be that long is an
  extraction question, so it goes to `docs/deferred.md`.

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
  only), `model_routes.toml` (E2), their tests and fakes, the SDK-calling scripts,
  `docs/knowledge/bedrock-route-facts.md` and `docs/deferred.md` (S2).
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
with the lead; this slice changes no prompt text. Route-file edits: efforts under E2 only,
each with its measure.

## Owner items

| Id | Decision | Lean |
|---|---|---|
| **O1** | One task in three parts, or three tasks? | One task. If the E2 measures run long, E2 splits off; Parts 1 and 3 do not wait for it. |
| **O2** | Keep a switch back to Chat Completions? | No. Replace and delete; roll back by reverting. |
| **O3** | The legacy `openai-direct` route. | Keep it passing unit tests; no live measure. |
| **O4** | Which of the 21 `none` steps to raise. | **Ruled 2026-11-20:** all tool-using `none` steps to `low`. That is two call sites (§ Efforts). Open: confirm the chat tool turn becomes its own route step. |
| **O5** | Fix the two defects found on the way (M7, M8)? | Yes; the lines are rewritten in any case. |
| **O6** | Reuse stored extraction records made through Chat Completions? | Yes. |
| **O7** | Set the account retention mode `none` (D2), and update the DPIA notes (D3). | Yes to both; needs DevOps. |
| **O8** | Build no stall remedy and send no AWS support case, given § Stalls. | Agree. The fault is not shown on AWS's side or in the deployed apps. |
| **O9** | Theory of change: tell the colleague about the endpoint move and the efforts they may now set. | Owner tells the colleague before the build. |
| **O10** | Find why laptop connections stall (for example, rerun 100 probe calls on another network, or with any VPN off). Outside this task; it affects only local runs. | Worth 15 minutes of the owner's time, since local measures feed design decisions. |

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
- **E2:** for the two raised call sites: median latency, cost for each call and cached-token
  share, before and after.
- **E3:** the Sol tool-loop smoke passes.
- **S1:** a traced attempt in Langfuse shows the request id, and that id finds the call in
  AWS's audit log.
- **S2:** the knowledge entry and the corrected `docs/deferred.md` entries are in the diff.
- **After deploy to staging:** one week of staging traces joined to the audit log by
  request id shows no timeout that is not a genuinely long answer.

## Verification evidence expected

In [verification.md](verification.md): the command results above; the before-and-after
tables; each prompt-hash diff; the list of fakes moved; the staging join after deploy;
public-safety confirmation; known gaps.

## Evidence (gitignored `research/`)

| File or folder | Holds |
|---|---|
| `call-site-inventory.md` | Every call site, seam, test double and stored shape. |
| `probe/` | The capability check (`capability.md`) and the 900-call stall comparison (`analysis.md`). |
| `effort-none/` | The check that `none` means no reasoning. |
| `cloudwatch/` | 14 days of Bedrock metrics and audit-log events, and the join that showed the delivery delay (`delivery_lag.txt`). |
| `prod-join/` | The check on the deployed apps: 14 days of their traces joined to the audit log (`results.txt`). |
| `openai-responses-notes.md`, `bedrock-responses-notes.md`, `aws-throughput-guidance-notes.md` | Sourced research, read 2026-11-20. |

## Risk tier & review focus

**Tier 3**: runtime egress (a new provider endpoint with a storage default that must be
turned off). Contract-stage and plan-stage adversarial reviews, a security lane, human deep
review.

Focus: a call site missed by the move; a request without `store=false`; a cache marker that
no longer matches and raises cost silently; usage read from the wrong field; a streamed
answer cut short and treated as complete; a fake that passes while the real shape differs;
scope creep into prompts or into Theory of change.
