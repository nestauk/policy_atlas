# Implementation plan: 063-responses-api

> **Status:** draft 1, 2026-11-20. Serves [contract.md](contract.md) revision 5 (approved
> 2026-11-20). Plan-stage adversarial review: _pending_ · Plan approved (before
> implementation): _pending_. Ids (M, E, S, D, O) and terms are the contract's. As-built
> facts with file and line are in `research/plan-facts.md` (gitignored); this plan cites
> the section as "facts § n".

## Context

The contract moves every OpenAI-SDK model call to the Responses endpoint in stages:
**1a** every request site calls one module, still on Chat Completions, with requests
identical to a baseline capture; **1b** that module alone changes endpoint; **1c** two
fixes and the clean-up; **Part 2** carried reasoning and ten raised efforts; **Part 3**
request ids and the stall findings.

What the code looks like today (facts § 1, 2):

- `core/openai_client.py` holds `parse_structured` and `traced_parse`. 62 route steps reach
  the provider through them.
- 19 other request sites call `client.chat.completions.create/parse` themselves: 13 in
  `evidence_search/synthesis/synthesis_backend.py`, 1 in `grounding_judge.py`, 3 in
  `runtime/chat_backend_openai.py`, 1 in `runtime/task_agent.py`, 1 in
  `theory_of_change/backend.py`. With the one inside `parse_structured` that is 20.
- Each site reads its step's model, effort and timeout from the route file and passes them
  in (`_step_kwargs`, `_chat_kwargs`, `openai_kwargs`). Each site opens its own Langfuse
  observation and owns its retry rule (`traced_attempts`, `traced_parse`,
  `call_with_retry`, a local loop, or none).
- Seven sites read a stream with their own chunk loop.

## Decisions taken in this plan

1. **The seam: three calls in `core/openai_client.py`.** Call sites keep building
   chat-style messages and tools, as today. The module sends, translates (from stage 1b),
   sets `store=false`, reads usage, raises the named errors and notes the request id.

   ```python
   def parse_structured(client, *, messages, response_format, usage_event, label, model,
                        reasoning_effort, prompt_cache, timeout_s, **parse_kwargs
                        ) -> UsageResult[T]            # name and signature unchanged

   def send_turn(client, *, messages, model, reasoning_effort, prompt_cache, timeout_s,
                 label, usage_event, tools=None, tool_choice=None,
                 parallel_tool_calls=None, json_schema=None, max_output_tokens=None,
                 carried=None) -> ModelTurn

   def stream_turn(client, *, <the same arguments as send_turn>) -> TextStream

   @dataclass(frozen=True)
   class ToolCall:   name: str; arguments: str; call_id: str
   @dataclass(frozen=True)
   class ModelTurn:  text: str; tool_calls: tuple[ToolCall, ...]; usage: TokenUsage
                     carry: tuple[Any, ...]   # the provider's output items, opaque

   class TextStream:   # iterate for text pieces; then .usage; .close() cancels
   class AnswerCutOff(RuntimeError): ...   # the output limit was reached
   class ModelRefusal(RuntimeError): ...   # the model refused
   def last_request_id() -> str | None     # the id of the newest response on this thread
   ```

   - `parse_structured` keeps its name and signature. Four hash-pinned files call it, and
     `make eval-check` names `screening_backend.parse_structured` (facts § 1). The sites
     that call `.parse` directly today call it instead.
   - `send_turn` serves a tool turn and a plain answer. `carried` is `None` in Part 1.
   - `TextStream` raises `AnswerCutOff`, `ModelRefusal` or the provider's error when it is
     exhausted (M8); `.close()` keeps the Theory of change cancel working.
   - `require_parsed`, `require_single_tool_call` and `_first_named_tool_call` read the
     Chat Completions answer shape. Their checks move behind the three calls and act on
     `ModelTurn`.

2. **What stays at the call sites.** Reading the route file, tracing and retries stay where
   they are. This narrows one sentence of the contract (§ One way in says the module reads
   the step, traces and applies nothing of the site's; revision 4 wording said more). The
   reason is the same as for `parse_structured`: 25 callers of `traced_attempts` and the
   pinned files would otherwise change for no gain. See § Contract corrections.

3. **Request ids without touching the 25 callers (S1).** The three calls put the response's
   request id in a context variable. `traced_attempts` reads `last_request_id()` after the
   call returns or raises, and writes it to the attempt's metadata. The SDK already exposes
   the id on a response, on an `APIStatusError` and on a stream's response headers
   (facts § 3). An attempt with no response records its start time, which the observation
   already has.

4. **The baseline capture (M1) records HTTP request bodies.** A real `OpenAI` client with
   an `httpx.MockTransport` records the JSON body of each request and returns a canned
   answer. This sees what the SDK really sends, including the JSON schema built from a
   Pydantic class, which the present harness never sees (facts § 8). It runs in its own
   process with `POLICY_ATLAS_MODEL_ROUTE=bedrock` set before any import, because 47 model
   ids and efforts are read from the route at import time. One test starts that process
   and compares its output with the committed file.

5. **Coverage of the capture.** One request for each of the 74 steps, plus the variants the
   present harness misses (facts § 8): the forced section turn; a turn with tool history;
   the repair turn; the key-findings, case-studies and intro streams and their fallbacks;
   the three task agent streamed turns; the Theory of change draft and report streams; the
   three chat sites with tool history. Inputs are the repository's sanitised fixtures only.

6. **The two checks.**
   - M4 (after 1a): each recorded body equals the baseline, as parsed JSON.
   - M7 (after 1b): a comparison function reads a baseline Chat Completions body and the
     new Responses body for the same step and asserts: the ordered list of text parts is
     equal; tools are equal by name, description and parameters, and each states `strict`
     with today's value (`false` where today's tool has none); the schema body is equal;
     effort, timeout, output limit and cache options are equal; a cache marker sits on the
     same text part; `store` is `false`; `previous_response_id` and `background` are absent.
     The Responses bodies are committed as a second capture so a later change shows in a diff.

7. **Tests in stage 1a do not change.** The module still calls `client.chat.completions`,
   so every fake of the SDK client keeps working. Untouched tests passing is the second
   proof, beside M4, that 1a changed nothing. Fakes move in stage 1b.

8. **Fakes in stage 1b.** The fakes of the SDK client (facts § 9, group a) return the
   Responses answer shape. `backend/tests/helpers.py` gets the shared builders first; the
   per-file fakes then use them. Tests that assert on request arguments keep asserting on
   chat-style arguments where the site still builds them, and on the HTTP body where they
   test the module.

9. **Theory of change.** `draft_stream_request`, `report_stream_request` and its other
   builders keep returning chat-style requests, built with the private SDK helper
   `type_to_response_format_param` as today. Only the send lines change. The contract's
   "private helpers are replaced where a public call exists" does not reach this one,
   because replacing it would change a builder's shape. See § Contract corrections.

10. **Carried reasoning (E1), section writer.** The live `section_turn` returns the turn's
    provider items in a new optional key of `SectionTurn`. `run_section_loop` keeps them in
    the closure of its `turn_fn` and passes them to the next `section_turn` and to
    `section_emit_stream` only when there are some. A test double never returns items, so
    it never receives the argument, and none of the 25 doubles changes (facts § 4). The
    backend builds the next request as: the prompt start, then for each earlier turn its
    carried items followed by one `function_call_output` for each tool call in them. A call
    the loop did not use (`write_section` or `emit_section` beside reads, an ignored extra)
    gets the fixed result `NOT_USED_TOOL_RESULT`. The repair turn sends no history today
    and stays so.

11. **Carried reasoning, chat.** The same shape on `ChatBackend`: the tool turn returns its
    items; the loop in `api/answer_core.py` holds them for the one answer and passes them
    to the next tool turn, the reply stream and the final parse.

12. **`NOT_USED_TOOL_RESULT` is prompt text.** The lead writes it. It lives in
    `section_prompt.py`, which is hash-pinned, so it is guarded like other model-facing
    text.

13. **Fallback for E1.** If a carried request is refused in the live check, that loop uses
    today's rebuilt history for the whole loop (the probe showed it is accepted with
    reasoning on), and `verification.md` records it. One flag in each backend, off by
    default, removed if never needed by the end of the build.

14. **E3, from the code.** The only different steps that share a prompt start are
    `synthesise_section_turn` and `synthesise_section_emit` (facts § 5). The three `chat`
    sites are one step. So `option_profile_line` stays at `none`.

15. **E4 and E5, exact values** (facts § 6).

    | Step | Output limit today → after | File (all hash-pinned) | Timeout on `bedrock` today → after |
    |---|---|---|---|
    | `synthesise_section_turn`, `synthesise_section_emit` | none sent → none | n/a | 25 s → 60 s |
    | `synthesise_write_key_findings` | none sent → none | n/a | 120 s, no change |
    | `chat` | 4,096 → 6,144 | `runtime/chat_prompt.py` | 120 s, no change |
    | `task_agent_scoping_turn` | 16,384 → 18,432 | `runtime/task_agent_scoping_prompt.py` | 60 s, no change |
    | `longlist_constrain`, `longlist_distinct`, `longlist_authority` | 16,384 → 18,432 each | `options_scoping/constrain/constrain_prompt.py` | 60 s, no change |
    | `option_profile_potential_impact`, `option_profile_ambition` | 16,384 → 18,432 | `options_scoping/option_profile/option_profile_prompt.py` | 60 s, no change |

    The option profile limit is one constant shared with `option_profile_line` (`none`) and
    `option_profile_setting` (`high`); their ceiling rises too and nothing else about them
    changes. Largest burst against the Bedrock quota: 12 option profile calls at once
    reserve 24,576 more output tokens than today; 4 constrain batches reserve 8,192 more.
    Both are far below Terra's quota of some millions of tokens a minute.

## Owner items

| Id | Item | Lean |
|---|---|---|
| **P1** | **Chat at `low` means five reasoning turns before each reply.** A live chat answer always runs five tool turns, then the reply (facts § 4). At `low` each turn may think for a second or more, so the reply could start several seconds later than today. The contract's stop rule catches a large rise (three times slower and over 10 s), and the run after Part 2 measures it. | Build as ruled and measure. If the rule is met, the fallback is `chat` back to `none` by one route-file line. |
| **P2** | The three corrections in § Contract corrections. | Accept; they narrow wording and change no scope. |
| **P3** | Three scripts already fail or misbehave today (`snowball_recall.py` raises when an effort is set; `run_screen.py` ignores its effort override; two feasibility scripts fail on the helpers). | Not fixed here. All go to `docs/deferred.md`. They still move to the shared module where they send a request. |

## Contract corrections

Found while grounding the plan in the code. None changes scope. They are applied to the
contract as revision 5.1 when this plan is approved.

1. **§ One way in, "what the module does".** The module sends, translates, sets
   `store=false`, reads usage, raises the named errors and notes the request id. The call
   site still reads the route step's model, effort and timeout, opens its trace
   observation and owns its retry rule (decision 2).
2. **M10.** Today a cut-off answer is an SDK error only at the `.parse` sites. At the
   `create`, tool-turn and stream sites it shows as malformed JSON, and the chat reply
   stream ends and is treated as complete (facts § 2). M10's change is the same: all three
   calls raise `AnswerCutOff`.
3. **Private SDK helpers.** The Theory of change request builder keeps
   `type_to_response_format_param` (decision 9). `to_strict_json_schema` in
   `runtime/task_agent.py` is replaced only if a public call gives the same schema.
4. **E5.** "Present value" means the `bedrock` override where one exists.
5. **M13.** Three scripts, not two, are already broken (P3).

## Phases

Each phase ends with a commit on `task/063-responses-api`. **Gate** names the check before
the commit: `fast` is `make verify-fast`; `full` is `make verify`. Executors are fixed here
and not re-decided in the build.

### Phase 0: build open and the baseline capture (M1)

| Task | Executor |
|---|---|
| 0.1 `make verify` on the branch as it stands. | lead |
| 0.2 The capture driver: a script under `backend/tests/core/` that builds every backend with a recording transport, drives each step and variant of decision 5 once, and writes one JSON file of bodies keyed by step and variant. Reuse the drivers in `test_call_site_kwargs.py`; add the missing ones. | deep-reasoner |
| 0.3 The test that runs the driver in its own process on the `bedrock` route and compares with the committed capture. Commit the capture. | deep-reasoner |
| 0.4 Read the capture: 74 steps present, variants present, no text from outside the fixtures. | lead |

Done when: the test passes twice in a row with a byte-identical file; a step count check
in the test fails if a route step has no entry. **Gate: full** (build-open baseline).

### Phase 1: stage 1a, one way in on Chat Completions (M2, M3, M4)

| Task | Executor |
|---|---|
| 1.1 Add `send_turn`, `stream_turn`, `ModelTurn`, `ToolCall`, `TextStream` to `core/openai_client.py`, over `client.chat.completions`. `parse_structured` unchanged. Unit tests for the three calls against the recording transport. | deep-reasoner |
| 1.2 `synthesis_backend.py`: its 13 sites call the module; its chunk loops use `TextStream`. | deep-reasoner |
| 1.3 `grounding_judge.py` (re-pin, code-only diff recorded), `chat_backend_openai.py` (3 sites), `task_agent.py` (stream), `theory_of_change/backend.py` (send lines only). Runs after 1.2 in the same tree; the file sets do not overlap. | deep-reasoner |
| 1.4 The one-way-in test: no file in `backend/src` or `scripts/` other than `core/openai_client.py` reaches `.chat.completions` or `.responses`. | fast-worker |

Done when: the capture test passes unchanged (M4); no test file under `backend/tests`
changed except the new ones; the retry rule of each site is as listed in facts § 2.
**Gate: fast** after 1.1, 1.2; **full** after 1.4.

### Phase 2: stage 1b, the change of endpoint (M5 to M9, M12)

| Task | Executor |
|---|---|
| 2.1 The translation inside the module: chat-style messages, tools, tool choice, schema, limit, effort and cache options to a Responses request with `store=false`; the Responses answer to `ModelTurn`, the parsed object and `TokenUsage`. Field mapping from `research/openai-responses-notes.md` § 2 and the shapes proved in `research/probe2/`. | deep-reasoner |
| 2.2 `TextStream` on Responses events, with the endings of M8. `core/usage.py` reads the Responses usage fields (M9). | deep-reasoner |
| 2.3 The comparison function of decision 6 and the M7 test; commit the Responses capture. The lead writes the list of asserted invariants (it is decision 6); the worker codes it. | deep-reasoner |
| 2.4 Shared fake builders in `backend/tests/helpers.py` for the Responses answer shape; then the per-file fakes of facts § 9 group (a). | deep-reasoner for `helpers.py`; fast-worker for the per-file moves, one file set each, from the builders |

Done when: M7 passes for every step and variant; `rg "chat\.completions" backend/src`
finds nothing; no call site file changed in this phase except tests. **Gate: fast** after
2.2; **full** after 2.4.

### Phase 3: stage 1c, fixes, request ids, clean-up (M10, M11, M13 to M15, S1)

| Task | Executor |
|---|---|
| 3.1 `AnswerCutOff` and `ModelRefusal` raised by all three calls; one test for each call and each error. Sites that caught `LengthFinishReasonError` or stored its name catch `AnswerCutOff`. | deep-reasoner |
| 3.2 The chat reply stream records usage and gets a trace observation (M11). | deep-reasoner |
| 3.3 `last_request_id()` and its use in `traced_attempts` (S1). | deep-reasoner |
| 3.4 Scripts under `scripts/` send through the module (M13); the one-way-in test covers them. | fast-worker |
| 3.5 Spec change 1 in the three places of the Theory of change components spec, with the `log.md` line (M15). | lead |
| 3.6 Live check after Part 1 (contract § Acceptance checks): the before run on the commit before Phase 1, the after run here; the token match against the audit log by request id. The join script is adapted from `research/prod-join/` and stays in `research/`. | lead runs; builder adapts the script |

Done when: the Part 1 acceptance checks hold and are in `verification.md`.
**Gate: full**, then the live check.

### Phase 4: Part 2, carried reasoning and efforts (E1 to E6)

| Task | Executor |
|---|---|
| 4.1 `NOT_USED_TOOL_RESULT` text (decision 12). | lead |
| 4.2 Section writer: the optional key on `SectionTurn`, the closure in `run_section_loop`, the request built from carried items (decision 10); re-pin `section_prompt.py`. Tests: items passed back unchanged; one result for each call; no carried item in the stored transcript or in a trace input. | deep-reasoner |
| 4.3 Chat: the same on `ChatBackend` and `api/answer_core.py` (decision 11), with the same three tests. | deep-reasoner |
| 4.4 Route file: the ten efforts of the contract's § Efforts; the two `bedrock` timeouts; the four limit constants (decision 15) with their re-pins. Tests that pin these values updated. | lead (one-line edits) |
| 4.5 Live check after Part 2: the Evidence search run, the options scoping run, one chat answer, one scoping planning turn, the Sol tool-loop smoke (E6). Figures and stop rules of the contract's § Efforts. | lead |

Done when: the Part 2 acceptance checks hold; no stop rule is met, or the owner's ruling on
a met rule is recorded. **Gate: fast** after 4.2 and 4.3; **full** after 4.4.

### Phase 5: Part 3 and documents (S2, D2, deferred entries)

| Task | Executor |
|---|---|
| 5.1 `docs/knowledge/bedrock-route-facts.md`: the stall findings, the effort-and-cache fact, `strict`, stream endings, the retention setting. `make okf-validate`. | lead |
| 5.2 `docs/deferred.md`: correct the stale stall entries; add the entries the contract names and P3. | lead |
| 5.3 `verification.md` complete. | lead |

**Step-6 exit gate: full.**

### After the merge (not gating it)

A smoke on staging before production; after one week the two raised timeouts are re-sized
by the rule of ADR 0043, and staging traces are joined to the audit log by request id.

## Executor summary

| Executor | Tasks | Why |
|---|---|---|
| lead | 0.1, 0.4, 3.5, 3.6 (run), 4.1, 4.4, 4.5, 5.x, the seam and the invariants (decisions 1, 6) | Seam design, prompt text, adjudication, live checks, one-line edits. |
| deep-reasoner | 0.2, 0.3, 1.1 to 1.3, 2.1 to 2.3, 2.4 (`helpers.py`), 3.1 to 3.3, 4.2, 4.3 | Judgement-bearing implementation against a machine-checkable done (M4, M7, named tests). |
| fast-worker | 1.4, 2.4 (per-file fakes), 3.4 | Mechanical work from an exact pattern. |
| builder | 3.6 (join script) | A throwaway measuring script in `research/`. |
| codex | none | The family change happens at the review stack. |

One working tree. Tasks in a phase run one after another unless their file sets are
stated not to overlap.

## Gate map

| Boundary | Check | Why |
|---|---|---|
| Phase 0 | full | Build-open baseline. |
| 1.1, 1.2 | fast | New code and one file; the capture test is in `verify-fast`'s test run. |
| Phase 1 exit | full | Every request site has moved. |
| 2.2 | fast | Module internals. |
| Phase 2 exit | full | The endpoint changed and about 100 tests' fakes moved. |
| Phase 3 exit | full | Before the live check. |
| 4.2, 4.3 | fast | Tool loops and their tests. |
| Phase 4 exit | full | Efforts, limits and pinned files changed. |
| Step-6 exit | full | Mandatory. |

No phase touches the database schema or ingest code, so no extra full gate is owed for that.

## Reuse before new code

| New thing | Reuses, or why new |
|---|---|
| `send_turn`, `stream_turn` | New: no shared call exists for a tool turn or a stream. They sit beside `parse_structured` and use `openai_kwargs` and `with_system_breakpoint` as it does. |
| `ModelTurn`, `ToolCall` | Replace three readers of the Chat Completions shape (`require_single_tool_call`, `_first_named_tool_call`, the reader in `chat_backend_openai.py`). |
| `TextStream` | Replaces seven chunk loops. The three JSON decoders are reused unchanged. |
| Capture driver | Extends the drivers of `test_call_site_kwargs.py`; that file and its data file are deleted when the capture covers them (M12). |
| Request id in traces | Reuses `traced_attempts`' metadata; no new table or field elsewhere. |
| Carried items | A new optional key on the existing `SectionTurn` and `ChatTurn`; no new protocol. |

## Out of this slice

Embeddings and their rate limit; the progress card's screening row; why laptop connections
stall; prompt changes for the raised steps; the effort comparison for the options scoping
steps; a request to AWS for zero data retention; fixing the three broken scripts.
