# Verification: 063-responses-api

Evidence for the build of [contract.md](contract.md) (revision 5.2) by [plan.md](plan.md)
(draft 2). Ids (M, E, S, D, O) and terms are the contract's. Figures from live runs are
read from saved result files in the task's gitignored `research/live/` folder.

> **Status:** build in progress. Sections are filled as each phase ends.

## Commands run

| When | Command | Result | Notes |
|---|---|---:|---|
| Build open (commit `6734deca`) | `make verify` | pass | Backend 4,988 passed, 1 skipped (9 min 13 s); mypy 577 files; ruff; build; okf-validate; eval-check; infra tests; audit-paths; rules-check; prompt-guard 58 files unchanged; font-guard; drift-check OK; frontend 147 files / 2,025 tests. See the note below on how it was run. |

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
- **Two forms the design probes had not sent, probed live on 2026-11-20 through the new
  module** (`research/live/probe_forms.py`, two calls): an earlier assistant turn as plain
  text (Terra) and an image part with detail `auto` (Sol, strict schema). Both accepted;
  usage read back.

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

## Review handoff (step-7/8 inputs)

- **Executor provenance:** filled per phase below.
- **Knowledge candidates:**
  - A full gate must not share a working tree with a subagent that is writing files: the
    type check and lint read untracked files. Gate a snapshot, or start the subagent after.
  - `scripts/fixed_questions.py` had silently gone stale against the streamed Task Agent
    route; nothing tests the script against the live route shape.
- **Deferred candidates:** none yet.
