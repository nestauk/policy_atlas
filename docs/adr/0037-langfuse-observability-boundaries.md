# ADR 0037 — Langfuse observability boundaries: users, sessions, prompts, evals

- **Status:** Accepted — 2026-09-11 (owner, in review of PR #62)
- **Date:** 2026-09-11
- **Task:** none. Issue #60 (too small for a task folder).
- **Amends:** [ADR 0036](0036-one-vocabulary-across-code-schema-api-and-screen.md)
  rider V9 (which session id a chat turn carries).

## Context

We self-host Langfuse server v3.225.5 and use Python SDK 4.13. The SDK's
`propagate_attributes` only sets the keys it is given, so a nested scope that
sets only `session_id` keeps an outer scope's `user_id`. One user scope at each
API entry point therefore covers every trace opened inside it.

Task 038 (rider V9) grouped every trace of a Task under the task id as the
Langfuse session, because the owner saw the planning chat and the run split
across two sessions. PR #62 adds user tracking and puts the chat grounding
judge in a session. Reviewing it raised the question of which id a chat turn
should carry.

## Decisions

1. **User id is the raw Cognito `sub`.** It is already an opaque UUID and
   joins to the app database. It is set with `tracing.trace_scope(user_id=...)`
   inside the worker thread at each entry point: chat turns, chat enrichment,
   planning turns, run dispatch, and check-in resumes. Context variables do not
   cross a thread start, so the scope opens inside the thread, never before it.

2. **Session id depends on the surface.**
   - Planning turns and runs carry the **task id** (ADR 0036 V9 stands).
     The planning chat is the task's origin and the run follows from it.
   - Chat turns and their enrichment carry the **conversation id**. A
     conversation can open long after the task ran, so grouping it with the
     run mixes two different sittings. The task id stays reachable through the
     trace metadata key `conversation_id` and the conversation row.
   - A check-in resume traces under the responder's user id, not the run
     starter's. The continuation state does not record who started the run,
     and widening it is not worth the schema change.

3. **Code stays the source of truth for prompts.** The app never fetches a
   prompt from Langfuse at runtime, so the prompt hash guard
   (`scripts/prompt_hash_guard.py`) keeps working. Langfuse copies, if we push
   any, are a read-only view for diffing. Do not use the SDK's prompt linking
   (`prompt=` on generations), since it needs a runtime `get_prompt` fetch.

4. **Evals run as SDK experiments, not v3 UI evaluators.** Trace-level LLM
   judge evaluators in the self-hosted v3 UI are legacy and stop running on
   v4. Code evaluators through `run_experiment` work on v3 today and carry over
   unchanged.

5. **One client for the app's lifespan.** `get_langfuse()` is called once at
   startup and `shutdown()` once in the lifespan `finally`, after the executor
   drains, so queued spans flush inside the ECS 10 s stop window. A detached
   chat thread mid-turn at shutdown can still lose its tail spans. Accepted.

## Consequences

- The Sessions tab shows one session per task for planning and runs, and one
  per conversation for chat.
- The Users tab shows Cognito subs. Operators see them as opaque ids.
- Future prompt and eval work follows decisions 3 and 4. The scoped work is in
  issues linked from #60.

## Rollback

Revert the one `session_id=` line in `chat_turns.py` to `task_id` to return to
the ADR 0036 V9 grouping. No schema or data change is involved.
