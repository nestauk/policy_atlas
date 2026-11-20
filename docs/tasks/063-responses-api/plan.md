# Implementation plan: 063-responses-api

> **Status:** draft 2, 2026-11-20. Serves [contract.md](contract.md) revision 5 (approved
> 2026-11-20). The plan-stage adversarial review of draft 1 the same day (20 findings; a
> fresh reader on the lead's model stood in for Codex, which was out of quota) is folded in
> (§ Plan-stage review). **Plan approved (before implementation): 2026-11-20 · owner**, with
> P1 to P4 ruled as leaned. ADR: [0050](../../adr/0050-responses-api-one-send-module-carried-reasoning.md).
> Ids (M, E, S, D, O) and terms are the contract's. This plan stands without the
> gitignored `research/` folder: the tables a build needs are in it.

## Context

The contract moves every OpenAI-SDK model call to the Responses endpoint in stages:
**1a** every request site calls one module, still on Chat Completions, with requests
identical to a baseline capture; **1b** that module alone changes endpoint; **1c** fixes
and clean-up; **Part 2** carried reasoning and ten raised efforts; **Part 3** request ids
and the stall findings.

The code today:

- `core/openai_client.py` holds `parse_structured` and `traced_parse`. 62 route steps reach
  the provider through them.
- 19 other request sites call `client.chat.completions.create/parse` themselves (§ The 20
  request sites). With the one inside `parse_structured` that is 20.
- Each site reads its step's model, effort and timeout from the route file
  (`_step_kwargs`, `_chat_kwargs`, `openai_kwargs`), applies the cache marker where its
  cache mode asks for one (`_cache_messages`, `with_system_breakpoint`), opens its own
  Langfuse observation and owns its retry rule.
- Seven sites read a stream with their own chunk loop.

## Decisions taken in this plan

### 1. The seam: the module takes the request the site builds today

The app's internal request language stays the chat-style keyword arguments that every site
builds now. The module is the only code that turns them into a provider request.

```python
# core/openai_client.py
def parse_structured(client, *, messages, response_format, usage_event, label, model,
                     reasoning_effort, prompt_cache, timeout_s, **parse_kwargs
                     ) -> UsageResult[T]              # name and signature unchanged

def send_turn(client, *, label: str, **request) -> ModelTurn
def stream_turn(client, *, label: str, **request) -> TextStream
```

- `**request` is exactly what the site passes to `client.chat.completions.create` today:
  `model`, `messages`, `reasoning_effort`, `timeout`, `extra_body`, and where the site
  uses them `tools`, `tool_choice`, `parallel_tool_calls`, `response_format`,
  `max_completion_tokens`, `stream_options`. A site changes one line:
  `completions.create(**kw)` becomes `send_turn(client, label=..., **kw)`, and
  `completions.create(stream=True, **kw)` becomes `stream_turn(client, label=..., **kw)`.
  An unknown key raises `TypeError`.
- **Who applies the cache marker:** the site, as today. The new calls never call
  `with_system_breakpoint`. `parse_structured` keeps applying it for its own callers, as
  today. The Theory of change send line is
  `stream_turn(client, label=..., **{k: v for k, v in request.items() if k != "stream"})`
  on the dict its builder already returns.
- Results:

  ```python
  @dataclass(frozen=True)
  class ToolCall:   name: str; arguments: str; call_id: str
  @dataclass(frozen=True)
  class ModelTurn:  text: str; tool_calls: tuple[ToolCall, ...]; usage: TokenUsage
                    carried: CarriedTurn | None      # None in Part 1
  class TextStream:   # iterate for text pieces; after the loop: .usage, .carried
                      # .close() cancels; a cut-off or refusal raises when the loop ends
  class AnswerCutOff(RuntimeError): ...   # the output limit was reached; carries label, usage
  class ModelRefusal(RuntimeError): ...   # the model refused; carries label
  ```
- `require_parsed`, `require_single_tool_call` and `_first_named_tool_call` read the Chat
  Completions answer shape today. Their checks stay at the sites and act on `ModelTurn`.
- In stage 1a the readers tolerate what today's test fakes lack (a tool call with no `id`
  gets `call_{i}`; a message with no `content` gives `""`), so fakes need not change.
- The chat-style vocabulary inside the app is a choice, not an oversight: it keeps every
  prompt file's message builder untouched. A `docs/deferred.md` entry records it.

### 2. What stays at the call sites

Reading the route file, the cache marker, tracing, the retry rule and the fallback. The
module sends, translates (from 1b), sets `store=false`, reads usage, raises the two named
errors and notes the request id.

### 3. The 20 request sites and their retry rules (unchanged by this task)

"TA" is `tracing.traced_attempts`: three attempts, retrying only failures that
`tracing._retryable` accepts.

| # | Site | Step | Call after 1a | Retry rule and fallback today |
|---|---|---|---|---|
| 1 | `core/openai_client.py` `parse_structured` | 62 steps | itself | none inside; callers use `traced_parse` or their own TA |
| 2 | `synthesis_backend.py` `_parse_proposal_once` | `synthesise_propose_sections` | `parse_structured` | TA; the caller re-asks on rejection |
| 3 | `_write_summary_once` | block and artefact summary | `parse_structured` | TA |
| 4 | `judge_summary._call` | `synthesise_judge_summary` | `parse_structured` | TA |
| 5 | `_create_section_turn_once` | `synthesise_section_turn` (open and forced) | `send_turn` | TA; a malformed emission is not retried and goes to the tool loop |
| 6 | `section_emit_stream._stream` | `synthesise_section_emit` | `stream_turn` | one attempt; on any failure reset the page text, count it, run the forced turn (#5) |
| 7 | `_repair_once` | `synthesise_section_turn` (repair) | `send_turn` | TA |
| 8 | `_write_key_findings_once` | key findings, fallback path | `send_turn` | TA; a malformed emission becomes the empty emission |
| 9 | `write_key_findings_stream._stream` | key findings, normal path | `stream_turn` | one attempt; fallback #8 |
| 10 | `_write_case_studies_once` | case studies, fallback | `parse_structured` | TA |
| 11 | `write_case_studies_stream._stream` | case studies, normal path | `stream_turn` | one attempt; fallback #10 |
| 12 | `write_source_note._call` | `synthesise_write_source_note` | `parse_structured` | TA |
| 13 | `write_full_report_intro._call` | intro, fallback | `parse_structured` | TA |
| 14 | `write_full_report_intro_stream._stream` | intro, normal path | `stream_turn` | one attempt; fallback #13 |
| 15 | `grounding_judge.py` `_judge_once` | `judge_grounding` | `parse_structured` | TA |
| 16 | `chat_backend_openai.py` `_tool_turn_once` | `chat` tool turn | `send_turn` | TA; no tool call raises, not retried |
| 17 | `_stream_then_parse` | `chat` reply stream | `stream_turn` | none; a failure leaves `chat_turn` |
| 18 | `_parse_once` | `chat` final parse | `parse_structured` | TA; on a prose mismatch keep the streamed prose, drop claims |
| 19 | `runtime/task_agent.py` `_stream_attempt._call` | the three task agent steps, streamed | `stream_turn` | local loop, two attempts, retry only before the first decoded reply text |
| 20 | `theory_of_change/backend.py` `_stream_parse.pieces` | `toc_draft`, `toc_report` | `stream_turn` | one attempt; any failure is `StreamFailed`; the callers fall back once to `traced_parse` |

### 4. Cut-off and refusal at each site (M10)

Today a cut-off answer is an SDK error only at `.parse` sites; elsewhere it shows as
malformed JSON, and the chat reply stream ends and is kept. After M10 every call raises
`AnswerCutOff`. Each site maps it to what it does today:

| Sites | On `AnswerCutOff` |
|---|---|
| `.parse` sites (through `parse_structured`) | Raised to the caller, not retried, as the SDK error is today. Code that stored the SDK error's class name stores `AnswerCutOff`. |
| 5, 7, 8 (tool turns) | Treated as the malformed emission they are today. |
| 6, 9, 11, 14, 19, 20 (streams with a fallback) | Their existing failure path: reset, count, fall back. |
| 17 (chat reply) | **The text shown so far is kept, as today.** The site catches the error, marks the trace observation as a warning, and goes on to the parse. No change for the user. |

`ModelRefusal` follows the same table, except at site 17, where a refusal with no text
raises as an empty answer does today.

### 5. The baseline capture (M1) records HTTP requests

- A **plain script**, `backend/tests/core/capture_requests.py`, not a pytest run: the test
  suite's `conftest.py` removes the route variable. The script is started by one test with
  `POLICY_ATLAS_MODEL_ROUTE=bedrock` and a throwaway key in the child's environment,
  before any import, because 47 model ids and efforts are read from the route at import.
- It replaces the `OpenAI` name in `core.openai_client` with a factory that builds a real
  SDK client on an `httpx.MockTransport`. The transport records, for each request: the
  path, the JSON body and the request timeout (from the request's extensions), and returns
  a canned answer.
- Drivers for the sites are written in the script (the ones in
  `test_call_site_kwargs.py` depend on pytest fixtures and are a model, not an import).
  A site that needs an earlier answer to build a later request gets canned answers that
  pass its Pydantic class. No database: every driver builds its backend directly with
  fixture inputs from the repository.
- **Coverage:** one request for each of the 74 route steps, plus these variants: the forced
  section turn; a section turn with two turns of tool history; the repair turn; the section
  emit stream; the key-findings, case-studies and intro streams and their fallbacks; the
  three task agent streamed turns; the Theory of change draft and report streams and
  `toc_import` with an image; the three chat sites with tool history. The script fails if
  a route step has no entry.
- **Deterministic:** entries sorted by step and variant; any generated id or time in a
  prompt is fixed by the driver.
- The capture file is committed. `test_call_site_kwargs.py` and its data file are deleted
  in Phase 2, after their two checks that the capture does not give are re-homed in the
  capture test: `CACHE_MODES` covers every route step, and each site sends its cache mode.

### 6. The two checks

- **M4 (after 1a):** every recorded request equals the baseline: path, body as parsed
  JSON, timeout.
- **M7 (after 1b):** a comparison function reads the baseline (Chat Completions) and the
  new (Responses) request of the same step and variant and asserts all of:

  | Aspect | Assertion |
  |---|---|
  | Messages | The same sequence of (role, parts). A `system` message stays an input message with role `system`. Text parts equal; image parts equal (same data or URL). |
  | Tool history | Each assistant tool call becomes one `function_call` item with the same name, arguments and call id; each `tool` message becomes one `function_call_output` with the same call id and text; order kept. |
  | Tools | Same names, descriptions and parameters, in the same order. Each tool states `strict`, with today's value (`false` where today's tool has none). |
  | Tool choice | `"required"`, `"none"`, a tool forced by name, and allowed-tools in mode `required` each map to the Responses form the second probe proved; `parallel_tool_calls` equal. |
  | Schema | `text.format` has the same name, the same `strict` and the same schema body as `response_format`. |
  | Scalars | Model equal; `reasoning.effort` equals `reasoning_effort`; `max_output_tokens` equals `max_completion_tokens` or both absent; timeout equal; `extra_body` cache options equal; a cache marker sits on the same part. |
  | Data handling | `store` is `false`. |
  | Nothing else | Top-level keys are within: `model`, `input`, `tools`, `tool_choice`, `parallel_tool_calls`, `text`, `reasoning`, `max_output_tokens`, `store`, `stream`, `prompt_cache_options`. So no `previous_response_id`, `background`, `truncation`, `include`, verbosity or reasoning summary. |

  The Responses requests are committed as a second capture, so a later change shows in a
  diff.

### 7. Field mapping for the translation (task 2.1)

| Chat Completions | Responses |
|---|---|
| `messages` (system, user, assistant text) | `input` message items, same roles; text parts `input_text` (assistant: `output_text`); image parts `input_image` |
| assistant `tool_calls[i]` | `function_call` item (`name`, `arguments`, `call_id`) |
| `tool` message | `function_call_output` item (`call_id`, `output`) |
| `tools[i].function.{name, description, parameters}` | flat `{type: "function", name, description, parameters, strict}` |
| `tool_choice` string / named function / `allowed_tools` | same string / `{type: "function", name}` / `{type: "allowed_tools", mode, tools}` |
| `response_format` json_schema `{name, schema, strict}` | `text.format` `{type: "json_schema", name, schema, strict}` |
| `max_completion_tokens` | `max_output_tokens` |
| `reasoning_effort` | `reasoning.effort` |
| `extra_body.prompt_cache_options`, a part's `prompt_cache_breakpoint` | the same, unchanged |
| `stream_options` | dropped (usage always arrives on the last event) |
| answer: `choices[0].message.content` / `.tool_calls` / `.parsed` | `output_text` / `function_call` items / parsed from `output_text` |
| `usage.prompt_tokens`, `completion_tokens`, `prompt_tokens_details.cached_tokens`, `cache_write_tokens`, `completion_tokens_details.reasoning_tokens` | `usage.input_tokens`, `output_tokens`, `input_tokens_details.cached_tokens`, `cache_write_tokens`, `output_tokens_details.reasoning_tokens` |
| `finish_reason == "length"` | `status == "incomplete"`, `incomplete_details.reason == "max_output_tokens"` |
| stream chunks `choices[0].delta.content` | `response.output_text.delta` events; the last event is `response.completed`, `response.incomplete`, `response.failed` or `error` |

### 8. Request ids (S1)

- `core/tracing.py` gets `request_id_scope()`, a context manager that puts a fresh mutable
  holder in a context variable. The module writes the id of each response into the current
  holder. A holder is an object, so a thread that runs under a copied context (the Theory
  of change stream pump) writes into the same one.
- `traced_attempts` opens a scope **for each attempt**, so an attempt with no response
  shows no id, never the previous attempt's. It writes the id to the attempt's metadata.
- The sites that open an observation outside `traced_attempts` use the scope themselves:
  the six one-attempt streams (#6, 9, 11, 14, 19, 20) and the chat reply (#17).
- The id is read from the SDK response, from an `APIStatusError`, or from a stream's
  response headers.

### 9. Fakes and tests

- **Stage 1a:** tests should not need to change, because the module still calls
  `client.chat.completions` and tolerates the fakes (decision 1). Any test that does
  change is listed in `verification.md` with the reason. Untouched tests passing is the
  second proof, beside M4, that 1a changed nothing.
- **Stage 1b:** `backend/tests/helpers.py` gets shared builders for the Responses answer
  shape. Tests that fake the SDK client split in two kinds:
  - *answer fakes* (they return a canned answer and assert on what the site does with it):
    moved to the builders; mechanical.
  - *request-asserting tests* (they assert on what the site sent):
    `test_section_request_shape.py`, `test_chat_backend_openai.py`,
    `test_synthesis_backend.py`, `test_step_timeout_sites.py`, `core/test_openai_client.py`,
    `test_draft_stream.py`, `test_report_stream.py`. Each is re-seamed to fake
    `send_turn` / `stream_turn` / `parse_structured` and keeps asserting on the chat-style
    request, which is still what the site builds. For each file the worker lists the
    assertions before and after; none may be dropped (rubric row 5).
- **Task 3.2** opens an observation outside `traced_attempts`; the exempt list in
  `test_step_timeout_sites.py` (`NOT_WRAPPED`) gains the chat reply site.

### 10. Carried reasoning (E1)

- **Shape.** `ModelTurn.carried` is a `CarriedTurn`: the provider's output items for the
  turn, as the module received them, with the `status` field removed from every item that
  is not a message (the form the second probe showed Bedrock accepts). The site never
  reads inside it.
- **Recipe.** A request for a step whose effort is above `none` and which has tools sends
  `include=["reasoning.encrypted_content"]`. This is the only use of `include`; the M7
  allow-list gains it for those steps in Phase 4.
- **Placing it in a request.** The site builds its messages as today, but where it would
  write the rebuilt assistant-and-tool messages of an earlier turn it puts
  `turn.carried.with_results({call_id: text, ...})` in the list. The module expands that
  entry to the carried items followed by one `function_call_output` for each call in them.
  A call with no result given raises. So the order is the list's order (prompt start,
  earlier turns, trailing messages), the pairing is done inside the module, and the "one
  result for each call" rule cannot be broken silently.
- **Section writer.**
  - `section_turn` and `section_emit_stream` on the `SynthesisBackend` protocol gain an
    optional keyword `carried: Sequence[CarriedTurn | None] | None = None`, parallel to
    the transcript's turns. `run_section_loop` keeps the list in its `turn_fn` closure.
    Test doubles that `mypy` requires to match the protocol gain the keyword and ignore
    it (mechanical).
  - Results: a call the loop used gets its result text from the transcript, as today. A
    call it did not use (`write_section` or `emit_section` beside reads; an ignored extra)
    gets `NOT_USED_TOOL_RESULT`.
  - A turn whose only call is `write_section` (the model says it is ready) adds no entry,
    as today: it never enters the history.
  - A turn that raises `MalformedEmissionError` returns no `ModelTurn`. The error carries
    the turn's `carried`; the loop records its error exchange as today and stores the
    carried entry with the error text as the result of that call.
  - The repair turn sends no history today and stays so.
- **Chat.** The same on `ChatBackend.chat_turn`. The loop in `api/answer_core.py` holds the
  entries for one answer and passes them to the next tool turn, the reply stream and the
  final parse. The next answer starts from the stored chat history, rebuilt as today.
- **Never stored or traced.** `CarriedTurn` is not a key of `SectionTurn` or `ChatTurn`
  that reaches storage or a trace. Two lines write a whole `ChatTurn` to a trace today
  (`chat_backend_openai.py` `_update`, `api/answer_core.py` `_record`); both filter it.
  The test asserts that no `CarriedTurn` and no item of one appears in any argument of
  any `span.update` call (input, output, metadata, status message), in a log event, or in
  a stored transcript.
- **No fallback flag is built.** Task 4.0 probes the shapes the first probes did not:
  five carried turns in a row; a `NOT_USED_TOOL_RESULT` output; carried history followed
  by a stream with tools present and `tool_choice="none"`; carried history in a request
  with no `tools` (the chat reply and parse); a history that mixes a rebuilt turn with
  carried turns. If any is refused, the build stops before 4.2 and the lead brings the
  choice to the owner.
- `NOT_USED_TOOL_RESULT` is prompt text. The lead writes it. It lives in
  `section_prompt.py`, which is hash-pinned.

### 11. Efforts, limits, timeouts (E2 to E5)

Steps that share a prompt start (E3), from the message builders:

| Raised step | Shares its prompt start with | Result |
|---|---|---|
| `synthesise_section_turn` | `synthesise_section_emit` | Both at `low`. They change together and roll back together. |
| `chat` | its own three sites | One step, `low`. |
| `synthesise_write_key_findings` | its own fallback path | One step, `medium`. |
| `task_agent_scoping_turn`, `longlist_constrain`, `longlist_distinct`, `longlist_authority`, `option_profile_potential_impact`, `option_profile_ambition` | none (each system prompt differs from its first sentence) | `low`. `option_profile_line` stays at `none`. |

Limits and timeouts:

| Step | Output limit today → after | Constant and file (all hash-pinned) | `bedrock` timeout today → after |
|---|---|---|---|
| `synthesise_section_turn`, `synthesise_section_emit` | none sent → none | n/a | 25 s → 60 s |
| `synthesise_write_key_findings` | none sent → none | n/a | 120 s, no change |
| `chat` | 4,096 → 6,144 | `CHAT_MAX_OUTPUT_TOKENS`, `runtime/chat_prompt.py` | 120 s, no change |
| `task_agent_scoping_turn` | 16,384 → 18,432 | `SCOPING_MAX_OUTPUT_TOKENS`, `runtime/task_agent_scoping_prompt.py` | 60 s, no change |
| `longlist_constrain`, `longlist_distinct`, `longlist_authority` | 16,384 → 18,432 each | `CONSTRAIN_`, `DISTINCT_`, `AUTHORITY_MAX_OUTPUT_TOKENS`, `options_scoping/constrain/constrain_prompt.py` | 60 s, no change |
| `option_profile_potential_impact`, `option_profile_ambition` | 16,384 → 18,432 | `OPTION_PROFILE_MAX_OUTPUT_TOKENS`, `options_scoping/option_profile/option_profile_prompt.py` | 60 s, no change |

- The option profile constant is shared with `option_profile_line` (`none`) and
  `option_profile_setting` (`high`). Their ceiling rises too; nothing else about them changes.
- Output tokens reserved against the Bedrock quota by the largest bursts: option profile,
  12 calls at once, 12 × 18,432 = 221,184 (today 196,608); constrain, 4 batches with
  distinct and authority beside them, 6 × 18,432 = 110,592 (today 98,304). The 057 brief
  records global quotas of 2,000,000 tokens a minute for Sol and 4,000,000 for Luna;
  Terra's figure is read from AWS Service Quotas in task 0.1 and recorded.
- **The captures after Part 2.** Phase 4 regenerates the Responses capture. The M7 test
  gets an explicit table of allowed differences from the baseline: effort for the ten
  steps, the limits and timeouts above, `include` for the reasoning tool steps, and the
  tool-history variants of the section writer and chat (carried entries replace rebuilt
  ones; E1's own tests cover them). Any other difference still fails.

## Owner items

| Id | Item | Ruling (2026-11-20: as leaned) |
|---|---|---|
| **P1** | **Chat at `low` means five reasoning turns before each reply.** A live chat answer always runs five tool turns, then the reply. At `low` each may think for a second or more, so a reply could start several seconds later than today. The contract's stop rule catches a large rise and the run after Part 2 measures it. | Build as ruled and measure. The fallback is `chat` back to `none`. |
| **P2** | **The app's internal request language stays chat-style** (decision 1). The module translates at the edge. | Accepted for this task as a stop-gap. The `docs/deferred.md` entry is written (Model routes and model calls). |
| **P3** | The corrections in § Contract corrections. | Accept. |
| **P4** | Three scripts already fail or misbehave today (`snowball_recall.py` raises when an effort is set; `run_screen.py` ignores its effort override; two feasibility scripts fail on the helpers). | Not fixed here; `docs/deferred.md`. Scripts that send a request still move to the module. |

## Contract corrections

Found while grounding the plan in the code. Applied to the contract as revision 5.1. Item 6 changes a rollback statement; the others narrow wording.

1. **§ One way in.** The module sends, translates, sets `store=false`, reads usage, raises
   the named errors and notes the request id. The call site reads the route step's model,
   effort and timeout, applies the cache marker, opens its trace observation and owns its
   retry rule and fallback (decision 2).
2. **M10.** The named errors carry the site's `label`, not a step name: `parse_structured`
   keeps its signature and has no step. What each site does with a cut-off is decision 4;
   the chat reply keeps the text shown, as today.
3. **Private SDK helpers.** The Theory of change request builder keeps
   `type_to_response_format_param`. `to_strict_json_schema` in `runtime/task_agent.py` is
   replaced only if a public call gives the same schema.
4. **E5.** "Present value" means the `bedrock` override where one exists.
5. **M13.** Three scripts, not two, are already broken (P4).
6. **§ Rollback.** Rolling back one effort is the route-file line, its row in the M7
   allowed-differences table, and a regenerated capture (one command).
   `synthesise_section_turn` and `synthesise_section_emit` roll back together.
7. **E1.** Carried items are passed back in the form the probe proved (the `status` field
   removed from non-message items), not byte for byte.

## Phases

Each phase ends with a commit on `task/063-responses-api`. **Gate** names the check before
the commit: `fast` is `make verify-fast`; `full` is `make verify`. A phase with one gate is
green only at its exit. Executors are fixed here.

### Phase 0: build open, the before run, the baseline capture (M1)

| Task | Executor |
|---|---|
| 0.1 `make verify`. Read Terra's token quota (read-only) and record it. | lead |
| 0.2 **The before run**, now, before the branch moves: one Evidence search run on the fixed question, one options scoping run to the shortlist, one chat answer, one scoping planning turn, on the `bedrock` route. Save stage times, cost, cached-token share and latency for each step in `research/`. | lead |
| 0.3 `capture_requests.py` and its drivers (decision 5). | deep-reasoner |
| 0.4 The test that runs it in a child process and compares with the committed capture, with the two re-homed cache-mode checks. Commit the capture. | deep-reasoner |
| 0.5 Read the capture: every step and variant present; no text from outside the fixtures. | lead |

Done when: the test passes twice with a byte-identical file. **Gate: full.**

### Phase 1: stage 1a, one way in on Chat Completions (M2, M3, M4, M13)

| Task | Executor |
|---|---|
| 1.1 `send_turn`, `stream_turn`, `ModelTurn`, `ToolCall`, `TextStream` in `core/openai_client.py`, over `client.chat.completions`, with tolerant readers (decision 1). Unit tests against the recording transport. | deep-reasoner |
| 1.2 `synthesis_backend.py`: sites 2 to 14 (decision 3); its chunk loops use `TextStream`. | deep-reasoner |
| 1.3 `grounding_judge.py` (re-pin; code-only diff recorded), `chat_backend_openai.py`, `task_agent.py`, `theory_of_change/backend.py` (the send lines only). After 1.2; the file sets do not overlap. | deep-reasoner |
| 1.4 Scripts under `scripts/` that send a request call the module (M13). | fast-worker |
| 1.5 The one-way-in test: by syntax tree, no file in `backend/src` or `scripts/` other than `core/openai_client.py` has an attribute access `.chat.completions` or `.responses`. Docstrings do not count. | fast-worker |

Done when: the capture test passes unchanged (M4); the list of changed test files is
empty or each has its reason recorded. **Gate: fast** after 1.1 and 1.2; **full** at exit.

### Phase 2: stage 1b, the change of endpoint (M5 to M9, M12): one commit

The module, the fakes and the checks change together; nothing in between is green.

| Task | Executor |
|---|---|
| 2.1 The translation inside the module (decision 7): request, answer, usage, with `store=false`. | deep-reasoner |
| 2.2 `TextStream` on Responses events with the endings of M8; "first content" is the first text piece. `core/usage.py` reads the Responses usage fields (M9). | deep-reasoner |
| 2.3 The comparison function and the M7 test (decision 6); the Responses capture committed. The lead's list of assertions is decision 6; the worker codes it. | deep-reasoner |
| 2.4 Shared answer builders in `backend/tests/helpers.py`. | deep-reasoner |
| 2.5 Answer fakes moved to the builders, file by file. | fast-worker |
| 2.6 Request-asserting tests re-seamed (decision 9), each with its before-and-after list of assertions. | deep-reasoner |
| 2.7 Delete `test_call_site_kwargs.py` and its data file (their checks are in the capture test since 0.4). | lead |

Done when: M7 passes for every step and variant; the one-way-in test passes; no file under
`backend/src` changed except `core/openai_client.py` and `core/usage.py`. **Gate: full.**

### Phase 3: stage 1c, fixes, request ids, the live check (M10, M11, M14, M15, S1)

| Task | Executor |
|---|---|
| 3.1 `AnswerCutOff` and `ModelRefusal` from all three calls; each site's handling per decision 4; one test for each call and error, and one for the chat reply keeping its text. | deep-reasoner |
| 3.2 The chat reply stream records usage and opens a trace observation (M11); `NOT_WRAPPED` updated. | deep-reasoner |
| 3.3 `request_id_scope()`, its use in `traced_attempts` and at the seven sites of decision 8; tests: an attempt with no response shows no id; an id set on a copied-context thread is seen. | deep-reasoner |
| 3.4 Spec change 1 in the three places of the Theory of change components spec, with the `log.md` line (M15). | lead |
| 3.5 **The after run** (the same four items as 0.2, plus one Theory of change draft and report) and the comparison with 0.2. The token match against the audit log, call by call, by request id; streamed calls through their stream-end event; calls with no response listed and excluded. Read with the `pa-prod` read-only sign-in the owner already has. | lead runs; builder adapts the join script, which stays in `research/` |

Done when: the contract's Part 1 acceptance checks hold and are in `verification.md`.
**Gate: full**, then 3.5.

### Phase 4: Part 2, carried reasoning and efforts (E1 to E6)

| Task | Executor |
|---|---|
| 4.0 The probe of decision 10 (five shapes), on Terra and Sol, `store=false`. A refusal stops the phase. | builder |
| 4.1 `NOT_USED_TOOL_RESULT` text. | lead |
| 4.2 `CarriedTurn`, `with_results`, the `include` recipe and the expansion inside the module; unit tests (missing result raises; `status` removed; order kept). | deep-reasoner |
| 4.3 Section writer (decision 10); re-pin `section_prompt.py`. Tests: carried entries reach the next turn and the emit; each path of decision 10 (unused call, ready turn, malformed emission); nothing carried in any trace argument, log or stored transcript. | deep-reasoner |
| 4.4 Chat (decision 10), with the same tests and the two trace lines filtered. | deep-reasoner |
| 4.5 Doubles that `mypy` flags gain the ignored keyword. | fast-worker |
| 4.6 Route file: the ten efforts; the two `bedrock` timeouts. The four limit constants with their re-pins. Tests that pin these values. The M7 allowed-differences table and the regenerated capture (decision 11). | lead |
| 4.7 **The run after Part 2:** the four items of 0.2 and the Sol tool-loop smoke (E6). The figures and stop rules of the contract's § Efforts, against 0.2 and 3.5. | lead |

Done when: the Part 2 acceptance checks hold; no stop rule is met, or the owner's ruling
on a met rule is recorded. **Gate: fast** after 4.3 and 4.4; **full** after 4.6; then 4.7.

### Phase 5: Part 3 and documents (S2, D2, deferred entries)

| Task | Executor |
|---|---|
| 5.1 `docs/knowledge/bedrock-route-facts.md`: the stall findings; effort and cache; `strict`; stream endings; the retention setting. `make okf-validate`. | lead |
| 5.2 `docs/deferred.md`: correct the stale stall entries; add the contract's four entries and P4 (the chat-style vocabulary entry is already there). | lead |
| 5.3 `verification.md` complete. | lead |

**Step-6 exit gate: full.**

### After the merge (not gating it)

A smoke on staging before production. After one week the two raised timeouts are re-sized
by the rule of ADR 0043, and staging traces are joined to the audit log by request id.

## Executor summary

| Executor | Tasks | Why |
|---|---|---|
| lead | 0.1, 0.2, 0.5, 2.7, 3.4, 3.5, 4.1, 4.6, 4.7, 5.x; the seam, the invariants and the tables in this plan | Seam design, prompt text, adjudication, live checks, one-line edits. |
| deep-reasoner | 0.3, 0.4, 1.1 to 1.3, 2.1 to 2.4, 2.6, 3.1 to 3.3, 4.2 to 4.4 | Judgement-bearing implementation against a machine-checkable done (M4, M7, named tests, assertion lists). |
| fast-worker | 1.4, 1.5, 2.5, 4.5 | Mechanical work from an exact pattern. |
| builder | 3.5 (join script), 4.0 | Throwaway measuring code in `research/`. |
| codex | none | The family change happens at the review stack. |

One working tree. Tasks run one after another unless their file sets are stated not to
overlap.

## Gate map

| Boundary | Check | Why |
|---|---|---|
| Phase 0 exit | full | Build-open baseline. |
| 1.1, 1.2 | fast | New code and one file; the capture test runs in `verify-fast`. |
| Phase 1 exit | full | Every request site has moved. |
| Phase 2 exit | full | One commit: the endpoint, the fakes and the checks change together. |
| Phase 3 exit | full | Before the live check. |
| 4.3, 4.4 | fast | Tool loops and their tests. |
| After 4.6 | full | Efforts, limits and pinned files changed. |
| Step-6 exit | full | Mandatory. |

No phase touches the database schema or ingest code.

## Reuse before new code

| New thing | Reuses, or why new |
|---|---|
| `send_turn`, `stream_turn` | New: no shared call exists for a tool turn or a stream. They take the request the sites already build. |
| `ModelTurn`, `ToolCall` | One answer shape for the three site-level readers that read the Chat Completions shape today. |
| `TextStream` | Replaces seven chunk loops. The three JSON decoders are reused unchanged. |
| `capture_requests.py` | New drivers, modelled on `test_call_site_kwargs.py`, which it replaces. |
| `request_id_scope()` | Writes into the metadata `traced_attempts` already records. |
| `CarriedTurn` | New: nothing holds provider items today. An optional keyword on two existing protocol methods; no new protocol. |

## Plan-stage review

A fresh reader on the lead's model attacked draft 1 (raw record in `research/`). All 20
findings were accepted.

| Finding | Outcome |
|---|---|
| 1. Phase 2 could not be green at its middle gate. | Phase 2 is one commit with one gate. |
| 2. The one-way-in test covered scripts before they moved; a text search matched docstrings. | Scripts move in Phase 1; the test reads the syntax tree. |
| 3, 4. The seam could not reproduce every request; who applies the cache marker was unclear. | Decision 1: the module takes the site's own request; the site applies the marker. |
| 5. `carried` had no position or shape. | Decision 10: an entry in the message list, expanded and paired by the module. |
| 6. A malformed emission and a ready turn broke "one result for each call". | Decision 10 names both paths, each with a test. |
| 7. Carried items could reach a trace through the chat output. | Two lines filtered; the test covers every trace argument. |
| 8. A context variable could record a wrong id or miss streams. | Decision 8: a fresh holder for each attempt; the seven other sites listed. |
| 9. The M7 list let the request change and still pass. | Decision 6 widened; a key allow-list; the timeout captured. |
| 10. Part 2 invalidated the captures; rollback was not one line. | Decision 11 and contract correction 6. |
| 11. "No test changes in 1a" was not achievable as described. | Tolerant readers; any change listed with its reason; `NOT_WRAPPED` named. |
| 12. The plan leaned on gitignored files. | The retry table, the field mapping, the E3 table and the carried recipe are in this plan. |
| 13. A cut-off chat reply would newly fail. | Decision 4: the text shown is kept, as today. |
| 14. Moving request-asserting tests is not mechanical; a deletion had no task. | Tasks 2.6 and 2.7; the checks re-homed in 0.4. |
| 15. The capture's process and reuse were vague. | Decision 5. |
| 16. The named error had no step to name. | It carries the label (contract correction 2). |
| 17. The quota statement was incomplete. | Decision 11 gives totals; Terra's quota is read in 0.1. |
| 18. The protocol keyword may fail the type check on doubles. | The doubles gain the keyword (task 4.5); the "none changes" claim is dropped. |
| 19. The fallback flag was under-defined. | No flag; a probe before the code (task 4.0). |
| 20. The before run was not specified. | Task 0.2, at build open. |

## Out of this slice

Embeddings and their rate limit; the progress card's screening row; why laptop connections
stall; prompt changes for the raised steps; the effort comparison for the options scoping
steps; a request to AWS for zero data retention; fixing the three broken scripts; moving
the app's internal request language off the chat-style shape.
