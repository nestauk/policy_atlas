---
type: Convention
title: A route that runs a model step wraps the call in trace_scope with the task's session id; the scope reaches only observations opened inside it
description: Langfuse groups a task's traces by `session_id == str(task_id)` (task 038 V9); `tracing.trace_scope(user_id=..., session_id=task_id)` must wrap the whole model call at every route that runs one, because `propagate_attributes` reaches only observations opened while the scope is active; a side generation fired outside the turn's span is its own root trace in the session, not a child.
tags: [langfuse, tracing, sessions, api, "058"]
timestamp: 2026-11-09
---

# Rule

- Every API route that runs a model step wraps the call in
  `tracing.trace_scope(user_id=user.user_id, session_id=task_id)`; `user_id` alone leaves the
  trace session-less and it drops out of the task's Langfuse session view.
- The scope must enclose the observation's creation: SDK 4.13 has no
  `update_current_trace`, so a session set after the generation opened is lost
  (`core/tracing.py` docstring).
- A generation fired after the turn's span closed (the task and chat titles,
  `task_agent:title` and `chat:title`, 058 round 14) is its own root trace in the same session,
  never nested in the turn; say "sibling in the session", not "nested", in the records.
- The check is a live read, not a unit test: list the step's observations on the instance and
  look at `sessionId` (`docs/knowledge/langfuse-cost-by-time-window.md` for the API shape).

# Why

The 058 review's trace lane found seven `shortlist:note` generations with no session: the
note refresh route (`api/routers/longlist.py`) had `trace_scope(user_id=...)` only, while the
build's record claimed the refresh carried the task's session. The same read showed the title
generations as sibling root traces (parent `None`, one observation each) where the record said
"nests inside the turn's trace". Both claims had been marked "not proven by test" and neither
was true; the fix was one argument and a test that records the propagated session.
