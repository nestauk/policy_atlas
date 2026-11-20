# Verification: 063-responses-api

Evidence for the build of [contract.md](contract.md) (revision 5.2) by [plan.md](plan.md)
(draft 2). Ids (M, E, S, D, O) and terms are the contract's. Figures from live runs are
read from saved result files in the task's gitignored `research/live/` folder.

> **Status:** build complete through step 6, except one acceptance check that waits on an
> AWS sign-in (§ Token counts against the audit log). The review stack has not run.

**Read this first (owner):**

1. **Chat is back at no reasoning** (nine steps raised, not ten). At `low` a live answer
   failed and the next took 118 s to its first words; the fallback ruled in plan item P1
   was applied (§ The run after Part 2).
2. **The token match against the audit log is not done.** The `pa-prod` sign-in expired
   mid-build. Two commands finish it after a sign-in.
3. **O14's premise does not hold:** the chat reply and final parse share no cache with
   the tool turns (§ The run after Part 1).
4. **A fourth stale line in the Theory of change spec** is proposed, not applied (§ Phase 3).

## Commands run

| When | Command | Result | Notes |
|---|---|---:|---|
| Build open (commit `6734deca`) | `make verify` | pass | Backend 4,988 passed, 1 skipped (9 min 13 s); mypy 577 files; ruff; build; okf-validate; eval-check; infra tests; audit-paths; rules-check; prompt-guard 58 files unchanged; font-guard; drift-check OK; frontend 147 files / 2,025 tests. See the note below on how it was run. |
| Phase 0 (`e40b888c`) | `make verify` on the snapshot | pass | Backend 4,991 passed, 1 skipped. |
| Stage 1a (`b43107f5`) | `make verify` on the snapshot | pass on the second run | Backend 4,997 passed, 1 skipped. The first run was red on one over-long docstring line the lead had written (ruff E501); fixed in the snapshot and the whole gate run again. |
| Stage 1b (`c3411905`) | `make verify` on the snapshot | pass | Backend 4,940 passed (62 old request-shape tests and the one skipped test deleted with their file; new tests added). |
| Stage 1c (`4e94ddcf`) | `make verify` on the snapshot | pass | Backend 4,952 passed. |
| Part 2 (`d5db3e9f`) | `make verify` on the snapshot | pass | Backend 4,976 passed. |
| Chat fallback and documents (`8461fd36`) | `make verify` on the snapshot | pass | Backend 4,976 passed; okf-validate 189 concepts; prompt-guard 58 files. |

Every gate: mypy and ruff clean, build, eval-check, infra tests, audit-paths, rules-check,
prompt-guard, font-guard, drift-check OK, frontend 147 files / 2,025 tests. Each ran in
`../policy_atlas-gate` on a commit made from the index (`git write-tree`), and the commit
was made only when the index still equalled the gated tree.

**How the build-open baseline was run.** The backend tests ran in the working tree. A
subagent had already begun the capture script there (the lead started it too early), so
the type check that followed stopped on that half-written, untracked file. The type check,
lint and build were therefore run on a clean checkout of the same commit
(`../policy_atlas-live`), and the remaining steps in the working tree. Every step passed.

## Phase 0

- **Terra's token quota (task 0.1).** AWS Service Quotas, read on 2026-11-20 (read-only):
  "Global cross-region model inference tokens per minute" is 4,000,000 for GPT-6.1 Terra,
  4,000,000 for GPT-6 Luna and 2,000,000 for GPT-6.1 Sol. The largest burst of E4
  (12 option-profile calls reserving 18,432 output tokens each, 221,184) is well inside it.

- **The before run (task 0.2),** served from a checkout of the build-open commit on the
  `bedrock` route, 2026-11-20 from 17:49 UTC, from a laptop. A first attempt at 16:50 was
  cut off when the machine restarted; its runs were marked interrupted and are not used.
  - Evidence search, the "NEET" fixed question at standard depth: 1,291 s in all, 890 s in
    synthesis; $1.10 for the session.
  - Options scoping, the fixed question, unattended to the shortlist: baseline 282 s, then
    the longlist walk 1,162 s; $1.04 for the session.
  - One chat answer on the finished Evidence search task: first text after 15.4 s, done in
    22.8 s; six `chat` calls, cached share 0.581. The reply stream is not traced on this
    commit, so its tokens are not in that figure.
  - The scoping planning turns are the two `task_agent_scoping_turn` calls of the scoping
    session (median 3.4 s).
  - 2,095 model calls in the two task sessions; 66 attempts ended in a client timeout and
    were retried (the laptop stall pattern of the contract's § Stalls).
  - The per-step table (calls, latency, cost for each call, cached share) is
    `research/live/before-step-stats.md`, written by `research/live/step_stats.py` from
    the Langfuse traces; its total equals `scripts/cost_per_run.py`'s for the same sessions.
  - Load on the laptop was not quiet: subagent test runs and one full gate ran beside it,
    so its latencies are an upper estimate.
- **The baseline capture (M1).** `backend/tests/core/capture_requests.py` drives all 74
  route steps on the `bedrock` route against a recording transport: 88 requests with the
  variants (section turn: open, with history, forced, repair; the streams and their
  fallbacks; the three task agent streams; the Theory of change streams and the image
  import; `toc_merge` in its two uses; the three chat sites with a system prompt, a task
  frame, an earlier turn and two turns of tool history). Two runs give byte-identical
  files; removing a step's driver makes the script fail. The chat frame text is a literal
  laid out like `assemble_chat_frame`'s, not a recording of it (that function reads the
  database).
- **Recorded as sent:** the path is the full path on Bedrock
  (`/openai/v1/chat/completions`); the timeout is httpx's four-part timeout.

## Phase 1 (stage 1a)

- **M4:** the capture test passes with the committed baseline file unchanged after all 20
  request sites moved. No existing test was edited in this stage.
- **The call each site uses** is plan decision 3's table, as planned. The retry rule of
  every site is untouched.
- **`grounding_judge.py` re-pin** (hash `7d0635…` → `1e8e52…`): code only. The send lines
  became one `parse_structured` call and four imports went; no prompt text is in the diff.
- **Scripts (M13):** four scripts under `scripts/evals/theory_of_change/judge_context/`
  sent their own requests; they call `parse_structured` now. The already-broken scripts of
  plan item P4 hold no direct SDK request and were left as they are.
- **The one-way-in test** (`backend/tests/core/test_one_way_in.py`) reads the syntax tree
  of every Python file under `backend/src` and `scripts/` and passes.

## Phase 2 (stage 1b)

- **M5, M6:** `_responses_request` in `core/openai_client.py` is the one translation, by
  plan decision 7. Every request sends `store=False`. A message whose content is a plain
  string stays a plain string; content already in parts becomes `input_text` /
  `output_text` / `input_image` parts with the cache marker on the same part. An input the
  translation does not know (a role, a part type, a tool type, a tool choice) raises
  `TypeError`; nothing is dropped silently.
- **M7:** `content_differences` in `test_request_capture.py` codes every row of plan
  decision 6 and passes for all 88 entries. The Responses requests are committed as
  `request_capture_responses.json`; the baseline file is unchanged. The builder altered
  copies of the capture to show the check fails on each kind of change: `store=true`, a
  tool flipped to strict, a removed cache marker, an added `include`, a changed timeout,
  a dropped input item, schema strictness, a changed tool choice.
- **M8:** `TextStream` ends as the contract says: `response.completed` gives text and
  usage; `response.incomplete` records usage; `response.failed` or `error` raises
  `openai.APIError` (not retryable, as a mid-stream error is today); a stream with no
  final event raises `openai.APIConnectionError` (retryable); a stream closed by its
  watchdog ends quietly. One test for each ending.
- **M9:** `core/usage.py` reads the Responses usage fields; output keys and numbers are
  unchanged. The Chat Completions reading is replaced, not kept beside.
- **M12, the fakes moved** (18 test files). `backend/tests/helpers.py` has the answer
  builders (`response_usage`, `text_response`, `structured_response`, `tool_call_response`,
  `text_stream_events`), `FakeResponsesClient`, `FakeStream` and `spy_calls`; the old
  `fake_parse_client` family is deleted. Tests that assert on a site's request spy the
  module's call and keep asserting on the chat-style request the site builds. No assertion
  was dropped. These changed form, for the review to confirm (rubric row 5):
  - `usage is None` became an exact `TokenUsage` match in nine tests (the new answers
    always carry usage): stronger.
  - `result is wire` became `result == wire` (`parse_structured` builds the object from
    the answer's JSON text).
  - In `core/test_openai_client.py`, "messages sent unchanged" is now "the input equals
    the messages translated item by item", on the Responses request.
  - `stream_options` is asserted on the request the site hands to `stream_turn` (the
    module drops it before sending); `stream is True` on the request the client receives.
  - `test_call_site_kwargs.py` and its data file are deleted (62 tests and the fixture
    refresh hook, which was the suite's one skipped test). Its two checks that the capture
    did not give were re-homed in `test_request_capture.py` in Phase 0.
- **A third private SDK import.** `parse_structured` builds its schema with
  `openai.lib._parsing._completions.type_to_response_format_param`, the function
  `chat.completions.parse` used inside the SDK, so the schema body, name and strictness
  are the same by construction. The Theory of change builder already imports it. The
  pinned `openai>=2.44,<3` guards it; a public call was not used because
  `responses.parse` parses during the request and hides the response status that the
  cut-off check needs.
- **Two forms the design probes had not sent, probed live on 2026-11-20 through the new
  module** (`research/live/probe_forms.py`, two calls): an earlier assistant turn as plain
  text (Terra) and an image part with detail `auto` (Sol, strict schema). Both accepted;
  usage read back.

## Phase 3 (stage 1c and request ids)

- **M10:** `AnswerCutOff` and `ModelRefusal` (both `RuntimeError`s carrying the site's
  label and the usage) are raised by all three calls from one check. A refusal is checked
  before a cut-off. An answer stopped for any reason other than the token limit (the SDK
  knows one, `content_filter`) is a `ModelRefusal`. Neither is retried. Each site does what
  plan decision 4 says:
  - `.parse` sites: raised to the caller.
  - Section turn and repair: turned into the malformed-emission error; the key findings
    fallback returns its empty emission.
  - The six streams with a fallback: their existing `except Exception` path (checked site
    by site).
  - Chat reply: a cut-off keeps the text shown, marks the observation `WARNING` and goes
    on to the parse; a refusal with no text raises. **A refusal after some text keeps the
    text, like a cut-off:** the plan's table does not cover this case; flagged for review.
  - No code matched the old SDK error names; two comments in hash-pinned prompt files
    still name `LengthFinishReasonError` and were left.
  - Tests: cut-off and refusal for each of the three calls; the chat reply keeping its
    text; a cut-off section turn. Not tested: the key findings fallback's empty emission
    and the repair turn on a cut-off (same helper as the section turn).
- **M11:** the chat reply's tokens are added to the final parse's and reach the answer's
  totals and trace; the reply has its own `chat:reply` generation for each attempt.
- **M16:** two attempts; a retry only when no text piece has arrived and
  `tracing._retryable` accepts the failure; the wait is `tracing._retry_wait_s`. The loop
  mirrors the task agent's (site 19) and is not shared, because that site's tests pin its
  own module's names. Tests: a retry before text, none after.
- **S1:** `request_id_scope()` in `core/tracing.py`; `core/openai_client.py` has one
  function that calls `client.responses.create` and notes the provider's request id from
  the response, a stream's headers or a status error. `traced_attempts` opens a scope for
  each attempt; the seven one-attempt observations open their own. An attempt with a
  response records `request_id`; one with none records `started_at` (UTC). The header is
  `x-request-id`: in the design probe it equalled `x-amzn-requestid` in 899 of 899 calls,
  and 893 of 893 ids were found in the audit log.
- **Existing tests changed in this phase** (4): the incomplete-stream test now expects
  the raise (renamed; its text and usage assertions kept); three trace tests read one more
  span update or metadata key (the request id or start time).
- **M15:** spec change 1 applied in the three places of the Theory of change components
  spec (the call-path bullet, the modules table row, the build-order row), with its line
  in `docs/specs/log.md`.
  - **For the owner (not applied):** a fourth line of the same spec, the import row of
    the steps table, still says PDF pages "go through the existing
    `chat.completions.parse` path". It names the old call too, but spec change 1 as
    accepted lists three places. Proposed wording: "go through the existing
    structured-answer call as image parts".

### The run after Part 1 (task 3.5)

Served from a checkout of the stage-1c commit (`4e94ddcf`), `bedrock` route, 2026-11-20
from 19:48 UTC, from a laptop: the same Evidence search and options scoping questions, one
chat answer, one Theory of change draft and check. Tables: `research/live/after1-step-stats.md`
and `research/live/compare-before-after1.md` (written by `step_stats.py --compare`).

- **Every call site worked on the Responses endpoint.** Both runs succeeded; the server
  log holds no traceback, no cut-off, no refusal and no rejected request.
- **Wall time.** Evidence search 516 s (before: 1,291 s). The before run wrote synthesis
  twice (358 s + 532 s) and this one once, and the two ran under different laptop load, so
  this is not a speed-up of the endpoint. Options scoping: baseline 465 s, longlist walk
  880 s.
- **Cost.** $1.76 for the two task sessions (before: $2.14, with more calls: 2,095
  attempts against 1,899).
- **Latency.** No step meets the flag (median more than three times the before value and
  over 10 s). On steps with more than three calls the largest ratio is 1.27 (`chat`, a
  median of 3.3 s against 2.6 s).
- **Cached-token share (acceptance: at least nine tenths of the before value).** Held on
  every step with more than a handful of calls: section emit 0.995 → 0.994, section turn
  0.674 → 0.656, extraction 0.924 → 0.917, classify 0.654 → 0.622, abstract screening
  0.719 → 0.712. Four steps fall below nine tenths; each was read call by call from the
  saved observations and none is an effect of the endpoint:
  - `option_profile_place_sentences` (0.602 → 0.458): the same 1,635-token prompt start
    in both runs. In the before run the first parallel burst wrote it once; in this run
    four calls of the burst wrote it at the same moment. Every later call read all 1,635.
  - `longlist_type` (3 calls → 2) and `agent_suggest` (2 → 1): the before run's figures
    were lifted by a retried call reading what the first attempt had written. One call
    cannot read its own cache.
  - `chat` (0.581 → 0.510): the after figure includes the reply stream, which the before
    commit did not trace. Tool turn by tool turn the cached tokens are alike (before 0,
    6,808, 14,994, 26,440, 26,514; after 0, 5,613, 26,457, 26,548, 26,623).
- **Chat answer:** first text after 18.5 s (before 15.4 s), done in 25.0 s (22.8 s).
- **A finding for the owner (O14).** In both runs the chat reply stream and the final
  parse read **0** cached tokens and each wrote the whole prompt again (about 27,000
  tokens each, at the cache-write price). They send no `tools`, and tools come first in
  the cached prompt start, so they do not share the tool turns' cache; the parse does not
  read the reply's either (it adds a schema). O14 put the reply and the parse at `low`
  with the tool turn so as not to lose a shared cache. There is none to lose. The build
  keeps the ruling (one `chat` step, `low`); the owner may want the reply and parse back
  at `none` (a new route step), or tools sent with `tool_choice="none"` on those two
  requests so the cache is shared, as the section emit does. Deferred candidate.

## Phase 4 (Part 2)

- **Task 4.0, the probe before the code** (`research/probe3/`, 2026-11-20, Terra and Sol,
  effort `low`, `store=false`): none of the five shapes of plan decision 10 was refused;
  38 of 38 requests accepted, none timed out. Five carried turns in a row read the cache
  on turns 2 to 5; the "not used" result was accepted (Terra went on, Sol made the call
  again with the same arguments); carried history followed by a stream with tools and
  `tool_choice="none"` streamed text and ended with `response.completed`; carried history
  with no `tools` worked streamed and with a strict schema, with and without `include`;
  a history mixing a rebuilt turn with carried turns was accepted in both orders. So no
  fallback is needed and the build goes on as planned.
  - Two findings differ from the design probe: requests that kept `status` on function-call
    items were accepted, and so were requests with the reasoning item's `id` dropped. The
    build still removes `status` from non-message items, the form the plan fixed.
  - At `low`, Sol produced a reasoning item only on the first turn, and later turns on both
    models often show 0 reasoning tokens.
- **E1 as built.** `CarriedTurn` in `core/openai_client.py` holds a turn's output items
  (`status` removed from items that are not messages); `with_results({call_id: text})`
  gives the entry a site puts in its message list, and the module expands it to the items
  followed by one result for each call. A missing result, or a result for an unknown call,
  raises. A request with tools and an effort above `none` sends
  `include=["reasoning.encrypted_content"]`; nothing else uses `include`.
  - Section writer: `run_section_loop` holds the entries for one loop and passes them to
    each turn, the forced turn and the emit stream. A call the loop ran gets the same
    result text the rebuilt tool message carries; a call it did not run gets
    `NOT_USED_TOOL_RESULT`; the ready turn adds nothing; a malformed emission keeps its
    entry with the error text. The repair turn sends no history, as before.
  - Chat: the loop in `api/answer_core.py` holds the entries for one answer and passes
    them to each tool turn, the reply and the final parse. The next answer starts from the
    stored history, rebuilt as before.
  - Tests: 9 on the module, 7 on the section writer, 7 on chat, including that nothing
    carried appears in any span update, log event, stored transcript or stored chat row.
    The builder put a leak back twice (messages in the section trace; the whole turn in the
    chat trace) and the tests failed each time.
- **E2 to E5 as built** (the route file and four constants; checked by the request test's
  table of deliberate differences, `_CHANGED` in `test_request_capture.py`):

  | Step | Effort | Output limit | `bedrock` timeout |
  |---|---|---|---|
  | `synthesise_section_turn`, `synthesise_section_emit` | `none` → `low` | none sent | 25 s → 60 s |
  | `synthesise_write_key_findings` | `none` → `medium` | none sent | 120 s |
  | `chat` (tool turn, reply, parse) | `none` → `low` | 4,096 → 6,144 | 120 s |
  | `task_agent_scoping_turn` | `none` → `low` | 16,384 → 18,432 | 60 s |
  | `longlist_constrain`, `longlist_distinct`, `longlist_authority` | `none` → `low` | 16,384 → 18,432 | 60 s |
  | `option_profile_potential_impact`, `option_profile_ambition` | `none` → `low` | 16,384 → 18,432 | 60 s |
  | `option_profile_line` (`none`), `option_profile_setting` (`high`) | unchanged | 16,384 → 18,432 (shared constant) | unchanged |

  The regenerated capture differs from the Part 1 capture in exactly these entries and
  keys (19 entries: effort, limit, timeout, and `include` on the entries that send tools).
  The efforts sit in the route file's shared `[steps]` table, so the legacy
  `openai-direct` route gets them too.
- **Prompt-hash re-pins in Part 2** (5 files): `section_prompt.py` (code, plus the one
  constant `NOT_USED_TOOL_RESULT`, written by the lead: "Not used: this call was not run
  in this turn. If it is still needed, make it again."), and one number each in
  `chat_prompt.py`, `task_agent_scoping_prompt.py`, `constrain_prompt.py` and
  `option_profile_prompt.py`.
- **Tests that pinned the old values** were updated to the new ones: the step table in
  `test_model_routes.py` (10 rows), three assertions in `test_chat_backend_openai.py`,
  two in `test_synthesis_backend.py`, one in `test_chat_turns.py`. Three of them carried a
  comment that the `none` pin guarded against Terra refusing tools; that guard belonged to
  Chat Completions and the comments went with it.

### The run after Part 2 (task 4.7)

Served from a checkout of the Part 2 commit (`d5db3e9f`), `bedrock` route, 2026-11-20 from
20:28 UTC, from a laptop: the same two questions, then chat. Tables:
`research/live/after2-step-stats.md`, `compare-after1-after2.md`, `compare-before-after2.md`.

| Raised step | Calls | Median latency: before, after Part 1, after Part 2 | Longest after Part 2 | Cost for each call after Part 2 (before) | Cached share: before, Part 1, Part 2 | Reasoning tokens, all calls |
|---|---|---|---|---|---|---|
| `synthesise_section_turn` | 74 | 1.45 s, 1.53 s, 1.73 s | 7.88 s | $0.0067 ($0.0078) | 0.674, 0.656, 0.719 | 58 |
| `synthesise_section_emit` | 27 | 9.16 s, 10.18 s, 9.46 s | 13.46 s | $0.0068 ($0.0085) | 0.995, 0.994, 0.994 | 551 |
| `synthesise_write_key_findings` | 3 | 6.81 s, 9.38 s, 13.33 s | 13.59 s | $0.0354 ($0.0431) | no cache read (one call for each report) | 482 |
| `task_agent_scoping_turn` | 2 | 3.39 s, 3.70 s, 3.92 s | 4.72 s | $0.0140 ($0.0136) | none | 129 |
| `longlist_constrain` | 4 | 4.96 s, 5.35 s, 5.65 s | 6.63 s | $0.0084 ($0.0096) | 0, 0, 0.113 | 21 |
| `longlist_distinct` | 1 | 0.94 s, 0.65 s, 1.66 s | 1.66 s | $0.0036 ($0.0034) | none | 35 |
| `longlist_authority` | 0 | not called in any of the three runs | | | | |
| `option_profile_potential_impact` | 2 | 13.73 s, 17.49 s, 14.32 s | 14.32 s | $0.0173 ($0.0207) | 0, 0, 0.127 | 42 |
| `option_profile_ambition` | 2 | 6.51 s, 4.63 s, 6.56 s | 6.56 s | $0.0116 ($0.0139) | none | 0 |
| `chat` | see below | | | | | |

- **Stop rules (§ Efforts).** No answer was cut at its output limit and none failed its
  schema (the server log holds no `AnswerCutOff`, `ModelRefusal` or malformed emission).
  No raised step's median is three times its earlier value and over 10 s. The writer
  steps' cached share is at or above the before value. So no rule is met for the nine
  steps above. The models reason very little at these efforts (58 reasoning tokens over
  74 section turns).
- **The runs.** Evidence search 1,678 s: its first synthesis pass (720 s) failed when the
  grounding judge, a step this task does not change, timed out three times in the seconds
  another call also timed out; the runner ran synthesis again (646 s) and the run
  succeeded. Options scoping: baseline 432 s, longlist walk 1,029 s, to its shortlist.
  $1.99 for the two sessions.
- **Reports, a difference in kind?** No. Evidence search report: 9 sections and 109 claims
  before, 7 and 93 after Part 1, 9 and 86 after Part 2; scoping baseline: 10
  sections in all three. Every citation verified in all three (0 unverified).
- **The laptop stall pattern, counted and excluded from latency:** 71 failed attempts
  (68 client timeouts, 3 connection errors) in the two sessions, against 66 before and 22
  after Part 1; each was retried. Two streams fell back to their non-streamed call after a read error
  (one section emit, one key findings stream at its 120 s limit; the fallback answered in
  13 s).
- **Chat: the fallback of plan item P1 was applied.** At `low` on the Part 2 commit:
  - the first answer **failed**: the second tool turn got a connection error, then timed
    out at 120 s twice;
  - the second answer completed, with its first text after 117.6 s (15.4 s before, 18.5 s
    after Part 1). Its five forced tool turns took 1.7, 7.2, 4.0, 46.2 and 37.9 s, with
    8, 449, 197, 5,094 and 4,947 reasoning tokens. The fifth read nothing from the cache.
  - By the letter the stop rule is not met (the median of the successful `chat` calls is
    about 8 s, under the 10 s floor), but one answer in two failed and the other made the
    user wait two minutes. P1 ruled: build as ruled, measure, "the fallback is `chat` back
    to `none`". The lead applied it: `chat` is at `none` again and its output limit is
    4,096 again (`chat_prompt.py` re-pinned back to its earlier hash). Carried turns stay
    in the chat loop; at `none` they hold no reasoning. **For the owner:** nine steps are
    raised, not ten. The likely cause is the loop's design, not the effort alone: every
    chat answer forces five tool turns (`tool_choice="required"`), and a model that
    reasons spends its thinking on what else it could look up.
  - Re-checked on the commit with the fallback (`8461fd36`): one chat answer, first text
    after 13.5 s, done in 19.1 s, with carried turns in the loop and 0 reasoning tokens.
- **E6, the Sol tool-loop smoke** (`research/sol-smoke/`): the product's own
  `run_section_loop` with the live backend, on a route overlay that points
  `synthesise_section_turn` and `synthesise_section_emit` at Sol; no committed file
  changed. Two runs at the committed `low`: tools called, the earlier turn carried back,
  a streamed section of about 2,250 characters with 11 and 13 claims, no fallback. Sol
  did not reason at `low`, so a further run with the overlay at `medium` was made: Sol
  returned an encrypted reasoning item on a tool turn, the next turn and the streamed
  write turn carried it back, and both were accepted (22,178 of 23,355 input tokens read
  from the cache with the reasoning item in the history). 15 calls in all.

### Token counts against the audit log (M9, M11, S1): **not done, blocked on a sign-in**

The AWS production read-only sign-in (`pa-prod`) expired during the build and signing in
is interactive. The join script is ready (`research/live/token_join.py`) and the app's
side is saved: 2,369 model calls in the four sessions of the run after Part 1, 2,316 with
a request id and 53 without (all 53 are attempts that got no response: 47 timeouts and 6
connection errors, each with its start time, as S1 specifies). The chat reply stream has
a request id and its token counts (2 input, 27,008 cache-write, 189 output). To finish,
after `aws sso login --profile pa-prod`, from `backend/`:

```bash
uv run python ../docs/tasks/063-responses-api/research/live/token_join.py ct
uv run python ../docs/tasks/063-responses-api/research/live/token_join.py join
```

What S1 has without it: a unit test shows each attempt's own id (or start time) on its
trace, and the design probe found 893 of 893 ids of this header in the audit log.

## Diff summary

Flagged deviations:

- **Gates folded.** The plan's fast gates after 1.1 and 1.2 were not run separately: 1.1 to
  1.5 were gated once, by the full gate, and committed as one stage-1a commit. Gates ran on
  a snapshot of the index in a second worktree (`../policy_atlas-gate`), so building could
  continue in the working tree.
- **`ModelTurn.usage` and `TextStream.usage` are `TokenUsage | None`** (plan decision 1
  types them `TokenUsage`). `None` when the provider sent no usage, which is what the sites
  passed on before, so traces record the same thing.
- **Small behaviour differences in stage 1a, none in a request:** (1) at the three
  synthesis tool-turn sites the usage log line is skipped when an answer has no choices at
  all (the error is raised first); (2) the warning for ignored extra tool calls shows `""`
  for an unnamed call, where it showed `"None"`; (3) empty stream pieces are no longer
  passed to the decoders (they did nothing); (4) the chat final parse now writes a
  `chat.final_answer.usage` log line, because `parse_structured` always logs usage; (5) the
  chat tool turn's no-choices error reads "OpenAI chat tool turn response had no choices."
  (was "returned no choices.").
- **The four eval scripts send a 120 s timeout.** They sent none before (the SDK default
  is 600 s); `parse_structured` requires one.

- `scripts/fixed_questions.py` (outside the contract's scope list; two lines): the script
  that starts the fixed questions read the Task Agent reply as one JSON object. That route
  has streamed one JSON object per line since the live-activity work, so the script failed
  before it could start a run. It now reads the last line. Needed for both live checks.

- **Carried entries are kept for each tool call, not for each turn** (plan decision 10
  says a list parallel to the transcript's turns). The transcript stores one exchange for
  each tool call, so a list by turn could not say which exchanges a turn made or which
  call each answers. `CarriedCall(turn, call_id)` in `synthesis_tools.py` points each
  exchange at its turn; exchanges of one turn go back as one entry.
- **Carried entries travel inside the turn dictionaries** (`SectionTurn`, `ChatTurn`, key
  `carried`) and are taken out before anything is traced or stored (`traceable_turn`,
  named-key copies). Decision 10 asked that they not be a key that reaches storage or a
  trace; they do not reach either, and tests hold that, but the key exists. For the
  review to weigh.
- **`section_emit_stream` is not on the `SynthesisBackend` protocol** (the loop finds it
  by name), so its `carried` keyword is on the live backend only.
- **`ModelRefusal` carries usage as well as the label** (a refusal is billed).
- **`docs/knowledge/` and `docs/deferred.md` were written in the build**, for the items
  the contract makes deliverables (S2, D2, O13, the timeout, the scripts). Lessons the
  build itself learned are only listed below, for step 8.

## Simplification (build step 5c)

`/simplify` over `git diff dev...HEAD` (code and tests; the capture data files and `docs/`
left out): four read-only reviewers on Opus (reuse, simplification, efficiency, altitude),
then the fixes below applied by a `deep-reasoner` and gated.

**Applied** (none changes a request; both capture files unchanged):

- One carried type fewer: `CarriedEntry` is gone; `CarriedTurn.with_results` returns a
  `CarriedTurn` holding the items and their results, and the module refuses to send a
  carried turn that has a tool call with no result (one new test).
- Two branches in `_carried` that existed only for test doubles are removed (the fakes
  build real SDK objects now).
- The chat reply loop marks "text has arrived" once, not for every piece.
- Two tests use the shared `FakeResponsesClient` in place of a hand-built client.
- The `ToolCall` and `ModelTurn` docstrings say `Attributes:`; eight comments in
  `model_routes.toml`, on lines this task changed, lost their task numbers, dates and
  decision ids (no value changed).
- Tried and reverted: passing `carried=carried` straight to the emit stream's fallback
  call. Four test doubles define `section_turn` without that keyword, so the conditional
  stays.

**Found and not applied**, with the reason:

- *`stream_options` is a dead key* (the module drops it; six sites still pass it and four
  tests assert it on the site's request). Removing it means changing the Theory of change
  request builder, which the contract forbids in this task.
- *"had no choices" wording* in two error messages (a Responses answer has no choices).
  The plan kept today's messages; a test pins the text.
- *One base class for `AnswerCutOff` and `ModelRefusal`, and dropping their unused
  `label`:* the plan fixed their shape.
- *Key findings could reuse `_emission_turn`:* it would change the usage returned on that
  path.
- *`include` only for sites that carry reasoning* (key findings and the repair turn ask
  for it and carry nothing): changes captured requests; the cost is a few kilobytes.
- *Cache the answer schema built on every `parse_structured` call* (about a second of
  CPU for each run, as the SDK did before): a shared mutable dictionary is not worth it.
- *Build the trace copy of the messages only when tracing is on* (1 to 10 ms for each
  section turn): negligible beside a model call.
- *`FIXED_ID` in the capture script ends in the task number:* it is inside the frozen
  baseline capture, which cannot be regenerated from the old code.
- Structural findings: on the deferred list below.

## End-to-end command

```bash
# 1. serve the commit under measurement from a second checkout, on the bedrock route
git worktree add --detach ../policy_atlas-live <commit>
(cd ../policy_atlas-live/backend && uv sync)
(cd backend && POLICY_ATLAS_THEORY_OF_CHANGE=1 TASK_QUOTA_PER_YEAR=100000 \
  uv run --project ../../policy_atlas-live/backend --env-file .env \
  uvicorn policy_atlas.api.app:create_app --factory --port 8000) &

# 2. the Evidence search and options scoping questions as fresh tasks (unattended)
uv run --project backend python scripts/fixed_questions.py --only neet --only scoping

# 3. one chat answer on the finished Evidence search task; one Theory of change task
R=docs/tasks/063-responses-api/research/live
uv run --project backend python $R/chat_turn.py <task-id> $R/<label>-chat.ndjson
uv run --project backend python $R/toc_run.py

# 4. per-step figures from the traces, and the comparison of two runs
(cd backend && uv run --env-file .env python ../$R/step_stats.py --label <label> \
  --session <task-id> --session <task-id> --out-dir ../$R --cache ../$R/<label>-observations.json)
(cd backend && uv run --env-file .env python ../$R/step_stats.py \
  --compare ../$R/<a>-step-stats.json ../$R/<b>-step-stats.json --out ../$R/compare-<a>-<b>.md)
(cd backend && uv run --env-file .env python ../scripts/stage_walls.py --run-id <run-id> --format md --out ../$R/<label>-stage-walls.md)
```

Runs: before (`6734deca`), after Part 1 (`4e94ddcf`), after Part 2 (`d5db3e9f`), and one
chat answer on `8461fd36`. Do not start a second server on the same database while a run
is live: a server's start-up marks running runs as interrupted.

## Known unverified items

- **Token counts against the audit log** (M9, M11, S1's "the id finds the call"): blocked
  on the sign-in, see above. Rubric rows 15 and 25 are open until it runs.
- **The legacy `openai-direct` route** was not called live (owner ruling O3: unit tests
  only). It now sends the Responses endpoint and the raised efforts too.
- **Staging and production keys** were not exercised; a staging smoke comes before
  production (contract, after merge).
- **Sol with several reasoning items carried on one request**, and Sol on a section that
  needs more than three turns: not seen in the smoke.
- **The key findings fallback's empty emission and the repair turn on a cut-off** have no
  test of their own (the section turn does; they share its helper).
- **`CarriedHistory` when entries and exchanges do not line up** (it falls back to rebuilt
  history) is not tested directly.
- **A refusal on a live call** was never seen; the refusal paths are tested with fakes
  built from the SDK's types.
- The before run and the run after Part 2 ran on a busy laptop; their latencies are upper
  estimates. Timeouts are to be sized from staging (E5).

## Public safety

- Committed: code, tests, the two request captures, this file, the knowledge note and the
  deferred list. The captures hold prompt text from the repository and literal fixture
  inputs written for the capture; no recorded provider answer, no project data, no id
  from a live run. The only image is the 8-byte PNG signature already in the test suite.
- This file names commit ids and task-run figures, no AWS account id, key name, IP
  address or request id. Request ids, trace extracts, probe results and server logs stay
  in the gitignored `research/` folder.
- No secret was read into a file; the environment file was only ever passed to
  `uv run --env-file`.

## Review handoff (step-7/8 inputs)

- **Executor provenance** (who wrote which files; the lead reviewed each report and the
  gates, and read the core translation in `core/openai_client.py` line by line):
  - `deep-reasoner` (Opus): `tests/core/capture_requests.py`, `test_request_capture.py`
    and both captures (0.3, 0.4); `send_turn` / `stream_turn` and `test_openai_turns.py`
    (1.1); `synthesis_backend.py` (1.2); `grounding_judge.py`, `chat_backend_openai.py`,
    `task_agent.py`, `theory_of_change/backend.py` (1.3); the Responses translation,
    stream reader, `core/usage.py`, the M7 comparison, the answer builders (2.1 to 2.4);
    the re-seamed request-asserting tests and `FakeResponsesClient`, `FakeStream`,
    `spy_calls` (2.6, and the 11 tests the fast-worker left); the named errors, the chat
    reply usage, trace and retry, `request_id_scope` (3.1 to 3.3); carried reasoning in
    the module, the section writer and chat, with the doubles (4.2 to 4.5).
  - `fast-worker` (Sonnet): the four eval scripts and `test_one_way_in.py` (1.4, 1.5);
    the answer fakes of four test files (2.5).
  - `builder` (Opus), all in gitignored `research/`: `step_stats.py`, the carried-reasoning
    probe, `token_join.py`, the Sol smoke.
  - Lead: the two small module decisions after 1.1 (usage may be absent; the no-answer
    error); `scripts/fixed_questions.py`; the deletion of the old request-shape test
    (2.7); the spec change and its log line (3.4); `NOT_USED_TOOL_RESULT` (4.1); the route
    file, the four limits, the re-pins, `_CHANGED` and the pinned-value tests (4.6); the
    chat fallback; the knowledge note, the deferred list and this file (5.x); all live
    runs and their reading.
  - Codex: none (the plan marks none).
- **Adjudication items for the review:** the two carried-entry shape deviations above;
  the chat reply keeping its text on a refusal after some text; the chat fallback; the
  third private SDK import; the changed-form assertions of Phase 2 (rubric row 5); the
  efforts landing on `openai-direct` too.
- **Diff scoping:** exclude `backend/tests/core/data/request_capture_*.json` (1.2 MB of
  captured requests each) from review diffs; review `capture_requests.py` and
  `test_request_capture.py` instead.
- **Live-trace pointers:** the Langfuse session ids of every run are in
  `research/live/*-start*.txt` and the `*-step-stats.json` files.
- **Knowledge candidates:**
  - On Responses, raw `httpx` errors raised while a stream is being read (`ReadError`,
    `ReadTimeout`) reach the site unwrapped. `tracing._retryable` does not accept them, so
    the "retry before the first text" rules of the task agent and the chat reply do not
    retry them. Seen twice live (both sites fell back as designed).
  - Chat forces five tool turns for every answer; a model that reasons spends tens of
    seconds on the late turns. Raising chat's effort needs the loop changed first.
  - The chat reply and final parse share no cached prompt start with the tool turns
    (no `tools`), and each writes about 27,000 tokens to the cache for every answer.
  - Models reason very little at `low` on the raised steps (58 reasoning tokens over 74
    section turns; Sol none at all on tool turns); expect little change in the writing.
  - A burst of parallel first calls writes the same prompt start to the cache several
    times; cached-share comparisons between two runs need the calls read in order.
  - A second server started on the same database marks live runs as interrupted (its
    start-up sweep); a restart of the machine did the same to the first before run.
  - Parallel Theory of change child runs can collide on the event sequence number and
    fail a child (seen once live; already on the deferred list).
  - `uv run --env-file` does not override a variable already set in the shell.
  - Requests on Bedrock that keep `status` on carried function-call items, or drop the
    reasoning item's `id`, were accepted (the design probe had found `status` refused).
  - `docs/knowledge/pydantic-docstrings-in-tool-schemas-are-prompt-text.md` names the
    deleted `test_call_site_kwargs.py`; the capture test (`test_request_capture.py`) now
    holds the schemas it refers to.
  - Two comments in hash-pinned prompt files name the SDK's `LengthFinishReasonError`,
    which no longer exists on this path (`classify_prompt.py`, `iof_prompt.py`).
  - A full gate must not share a working tree with a subagent that is writing files: the
    type check and lint read untracked files. Gate a snapshot, or start the subagent after.
  - `scripts/fixed_questions.py` had silently gone stale against the streamed Task Agent
    route; nothing tests the script against the live route shape.
- **Deferred candidates:**
  - Share the chat tool turns' cache with the reply and the parse (send the tools with
    `tool_choice="none"`, as the section emit does), or split the step; saves two cache
    writes of about 27,000 tokens for every answer.
  - Chat with reasoning: stop forcing five tool turns (let the model say it is ready, as
    the section writer does) before raising its effort again.
  - Make mid-stream `httpx` read errors retryable in `tracing._retryable` (or wrap them in
    the stream reader), so the "retry before the first text" rules cover them.
  - One shared "retry before the first text" helper for the task agent stream and the chat
    reply (the two loops are copies; the task agent's tests pin its own names).
  - Return carried entries beside the turn, not inside the turn dictionary, so no filter
    is needed before tracing.
  - The Theory of change spec's import row still names the `chat.completions.parse` path
    (owner item, § Phase 3).
  - `scripts/fixed_questions.py` has no test against the streamed Task Agent route.
  - Step 5c, structural (not applied):
    - Keep the carried list inside `run_tool_loop`, beside the transcript, where each
      exchange is appended; `CarriedHistory`, its count matching and the wiring in two
      callers then go, and carried entries can be returned beside the turn.
    - One `tracing.generation(...)` helper (or `traced_attempts` with one attempt) for
      the seven sites that open a generation by hand; request ids are then recorded in
      one place and an eighth site cannot forget them.
    - Log usage inside `send_turn` and `stream_turn` (a `usage_event` argument), as
      `parse_structured` does; today a cut-off or refused stream logs none.
    - A neutral home for the tool loop that chat and the section writer share
      (`run_tool_loop`, `ToolExchange`, `CarriedCall`, the tool-history messages, the
      "not used" text), which now sits under the section writer's hash-pinned prompt file.
    - One shape for a step's settings on all three calls (model, effort, cache mode,
      timeout from the step), and one helper for "add the cache marker in breakpoint
      mode", which is written four times.
    - Remove `stream_options` from the request vocabulary, with the Theory of change
      builder (its owner's change).
    - Test helpers: a shared fake Langfuse client (ten test files keep their own), one
      network-level fake client (three copies), and the carried-turn fixtures of the two
      new carried test files.

## Deferred work

Seams left open are in [docs/deferred.md](../../deferred.md): the entries this task added
(zero data retention, the effort comparison, the `extract_interventions` timeout, the
three broken scripts) and the corrected stall entries.
