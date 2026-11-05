---
type: Convention
title: A Task Agent line the code posts without a model call is a completed transcript row with an empty user message
description: Code-authored chat lines (the draft landed, the check is done) are stored as completed task_agent_transcript rows with user_message empty; the plan-stale fence in create_run skips theory tasks that already have a graph, and the frontend hides the empty user bubble — both had to learn about the shape.
tags: [task-agent, chat, runtime, theory-of-change, task-054]
timestamp: 2026-11-05
---

# Rule

- `post_agent_message` writes one completed transcript row: `user_message=""`, the agent's
  text as the reply, no model call, no plan slot.
- Two readers must tolerate the shape: the plan-stale fence in `create_run` (a new transcript
  row would otherwise mean "the plan changed; re-approve") and the transcript view (no empty
  user bubble).
- Any new reader of the transcript checks for the empty user message before treating a row as
  a user turn.

# Why

Task 054's J3, J5 and J7 lines had no precedent. The first build blocked restarts (the fence saw
a newer row) and showed an empty bubble, so both readers were taught the shape.

# Citations

- `backend/src/policy_atlas/api/toc_start.py` (`post_agent_message`, `DRAFT_LANDED_MESSAGE`)
- `backend/src/policy_atlas/api/routers/runs.py` (the fence skips theory tasks with a graph)
- `frontend/src/views/workspace/TaskAgentPane.tsx`
