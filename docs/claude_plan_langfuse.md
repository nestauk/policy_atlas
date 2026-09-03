# Langfuse improvement plan: users, sessions, prompts, and evals

## Context

We self-host Langfuse server v3.225.5. The backend uses Langfuse Python SDK 4.13. These two versions are compatible: SDK v4 works with any server from v3.63.0 up. No upgrade is necessary for this plan.

The tracing layer in [tracing.py](backend/src/policy_atlas/core/tracing.py) is well built. A review found three gaps:

1. **No user tracking.** No trace carries a `user_id`. This is easy to fix: every API router already knows the authenticated user, and the SDK function `propagate_attributes` accepts a `user_id`.
2. **Most traces have no session.** Only chat turns, planning turns, and CLI runs get a `session_id`. Runs started through the API ([runs.py:69](backend/src/policy_atlas/api/routers/runs.py#L69)) and resumed runs ([continuation.py:486](backend/src/policy_atlas/api/continuation.py#L486)) pass no session id. As a result, all evidence-base pipeline traces from those paths have no session, and the `capability_run.session_id` database column stays NULL. Chat enrichment and the grounding judge also produce traces that belong to no session.
3. **Trace loss on deploy.** Production never calls `tracing.flush()`, and no single client is tied to the app's lifespan. ECS gives the app 10 seconds to stop. Spans that are still queued at that moment are lost.

Decisions already made with the user:

- **Prompts:** the code stays the source of truth. A script pushes each prompt version to Langfuse so the team can view and diff prompts in the UI. The app never fetches prompts from Langfuse at runtime. This keeps the `prompt_hash_guard.py` governance intact.
- **User id:** use the raw Cognito sub. It is already an opaque UUID and joins to the app database.

One SDK fact makes the users-and-sessions fix small. We verified it in the installed SDK source: `propagate_attributes` only sets the keys you give it. A nested call that sets only `session_id` keeps an outer call's `user_id`. So one user scope at each entry point covers every trace made inside it. None of the 13 `traced_call` sites need to change.

---

## Slice 1 — Users and sessions (this branch)

### 1a. Add one new function to tracing.py

Generalize the private `_session_scope(session_id)` context manager at [tracing.py:159](backend/src/policy_atlas/core/tracing.py#L159) into a public one: `trace_scope(session_id=None, user_id=None)`. The new function calls `propagate_attributes` with the ids you give it, converted to strings. When both ids are None, it does nothing. Keep `_session_scope` as a one-line alias so its two internal callers ([tracing.py:150](backend/src/policy_atlas/core/tracing.py#L150), [tracing.py:365](backend/src/policy_atlas/core/tracing.py#L365)) do not change. Do not change the signatures of `traced_call` or `component_span`.

### 1b. Open the scope at the five entry points

One rule applies everywhere: open the scope **inside** the worker thread, not before it starts. Context variables do not cross a thread start. The fan-out thread pool is already safe because `submit_with_context` copies the context for it.

1. **Chat turns** — in [conversations.py](backend/src/policy_atlas/api/routers/conversations.py), inside `worker()` (around line 753), wrap the `run_chat_turn(...)` call in `tracing.trace_scope(user_id=user.user_id)`. The existing session scope at [chat_turns.py:927](backend/src/policy_atlas/api/chat_turns.py#L927) then inherits the user id.
2. **Chat enrichment** — in the same file, in the second worker thread (around lines 815–825), wrap the `enrich_chat_turn(...)` call in `trace_scope(session_id=conversation_id, user_id=user.user_id)`. This puts the grounding-judge traces into the conversation's session. `grounding_judge.py` itself does not change.
3. **Planning turns** — at [planning.py:419](backend/src/policy_atlas/api/routers/planning.py#L419), wrap the `planner.plan_turn(...)` call in `trace_scope(user_id=user.user_id)`. The session id already flows on this path.
4. **API-dispatched runs** — in [runs.py](backend/src/policy_atlas/api/routers/runs.py), `create_run` (line 117) already has the user. Create a new `session_id = uuid.uuid4()` there, the same way the CLI does at [orchestrate.py:1055](backend/src/policy_atlas/runtime/orchestrate.py#L1055). Pass the session id and user id into `_dispatch_run` (line 60). In `_dispatch_run`, pass `session_id=session_id` to `run_plan(...)` and wrap the call in `trace_scope(user_id=...)`. The `run_plan` parameter and the `capability_run.session_id` persistence already exist; this path just never used them.
5. **Resumed runs** — no code change needed. During implementation we found that `run_plan` already reads `session_id` from `resume_from.session_id` ([runner.py:684](backend/src/policy_atlas/runtime/runner.py#L684)). Resumed runs only traced without a session because the original dispatch (point 4) never stored one. Point 4 fixes both. Leave the user id out here: the continuation state does not record who started the run, and widening its schema is not worth it.

**Not built:** no `user_id` threading through the internals of `run_plan`, no user tagging for CLI runs, and no changes to the 13 `traced_call` sites or the 36 score calls.

### 1c. One client for the app's lifespan, flushed at shutdown

In [app.py](backend/src/policy_atlas/api/app.py), in `_lifespan` (line 271):

- **At startup:** call `client = tracing.get_langfuse()` once. This validates the configuration when the app boots. Leave the per-request `get_langfuse()` calls alone: the SDK keeps one client per public key, so every call returns the same client.
- **At shutdown:** in the `finally` block, after `executor.shutdown(wait=True)` (line 313), call `client.shutdown()` when the client exists. This drains the span queue inside the 10-second ECS stop window. Known limit, accepted: a chat worker thread that is mid-turn at shutdown can still lose its final spans.

### Verification (slice 1)

- Add a unit test in [backend/tests/core/test_tracing.py](backend/tests/core/test_tracing.py). It must show two things: `trace_scope(user_id=...)` sets the user id in the OTel context, and a nested scope that sets only a session id keeps the outer user id.
- Test manually against a local Langfuse: run one chat turn, one planning turn, and one API run dispatch. Then check the UI. The Sessions tab must show the conversation sessions plus a new run session. The Users tab must show the Cognito sub. The enrichment and judge traces must sit inside the conversation session. Confirm that `capability_run.session_id` is not NULL for the API run.
- Run `make verify`. No prompt files change in this slice, so the prompt hash guard must stay green.

---

## Slice 2 — Prompts in Langfuse (separate PR; prompt work is lead-only)

Principle: the code is the source of truth. Langfuse is a read-only layer for viewing and diffing prompts.

1. **Close the guard gap first.** Nine `*_PROMPT_VERSION` constants live in files whose names do not contain "prompt" (`synthesis_backend.py`, `grounding_judge.py`, `finding_vetter.py`, `theme_grouping.py`, `ranking.py`, `group_clustering.py`). The [prompt_hash_guard.py](scripts/prompt_hash_guard.py) script cannot see them. Add an explicit list of extra files to the guard — a smaller change than renaming six modules — and refresh `scripts/prompt_hashes.json`.
2. **Write `scripts/push_prompts_to_langfuse.py`.** The script holds a flat registry with one entry per prompt family (about 14): the Langfuse name, the prompt content, the version constant, and the model. For each entry it calls `langfuse.create_prompt(name=..., type="chat"|"text", prompt=..., labels=["production"], commit_message=f"{PROMPT_VERSION} @ {git sha}")`. Before it creates a version, it fetches the latest version from Langfuse and skips the entry when the content already matches. This makes the script safe to run repeatedly. Add a `make push-prompts` target. Run it manually after any merge that changes a prompt.
3. **Leave the trace-to-prompt link as it is.** Every call site already writes `prompt_version` into the span metadata, so traces and prompt versions can be joined. Do **not** add the SDK's prompt linking (the `prompt=` argument on generations). That feature requires a runtime `get_prompt` fetch, which contradicts the code-is-truth decision.

**Not built:** runtime prompt fetching, migration to `{{var}}` templates, editing prompts in the UI (document the Langfuse copies as read-only), and extraction of the prompt text inside Pydantic `Field(description=...)` definitions (that text stays guarded in code).

### Verification (slice 2)

Run the push script twice against a local Langfuse. The first run must create all prompts with the correct labels and commit messages. The second run must change nothing. Run `make verify` with the updated hash list; it must pass.

---

## Slice 3 — Evals via Langfuse (separate PR; blocked on branch 34)

**Why SDK experiments, and not the evaluators in the Langfuse UI.** We verified this against the v3-to-v4 upgrade guide on 2026-09-02. Trace-level LLM-as-a-judge evaluators do run on self-hosted v3, but they are legacy: they stop running when the server later moves to v4, and their replacement (observation-level evaluators) does not exist on v3. Code evaluators run through the SDK's `run_experiment` work against a v3 server today and carry over to v4 unchanged. So: do not build on the v3 evaluator UI.

**Precondition:** merge branch `34-evaluate-against-ground-truth`, or extract its harness. That branch already has the pieces this slice needs: the ground-truth reviews (`scripts/eval_ground_truth/input/gt_reviews.csv`, loaded by `ground_truth.py`), a run-and-score harness (`run_and_score.py`), metrics (`test_metrics.py`), and a relevance judge (`relevance_judge.py`).

1. **Dataset upload script.** Write a one-off script, `scripts/eval_ground_truth/push_dataset.py`. It calls `create_dataset("ground-truth-reviews")` and then `create_dataset_item` once per review. The item input is the review question and intent. The expected output is the set of studies the ground-truth review included. Give each item a deterministic id so a repeat run changes nothing.
2. **Experiment wrapper.** Adapt `run_and_score.py` to the SDK experiment shape. The per-question run becomes a `task(*, item, **kwargs)` function. The existing recall and precision metrics become item-level evaluators that return `Evaluation` objects. The corpus-level aggregates become `run_evaluators`. Then call `dataset.run_experiment(name=f"{PROMPT_VERSION}@{git_sha}", task=..., evaluators=[...])`. Each experiment appears as a dataset run in the Langfuse UI, so you can compare prompt versions side by side.
3. **One judge, calibrated first.** Implement Rubric S from [judge-rubrics.md](docs/evals/judge-rubrics.md) as a code evaluator. The judge prompt is versioned code under prompting doctrine rule 12. Calibrate the judge against human ratings, as the rubric document describes, before its score gates anything. Rubrics A and Q follow the same shape later.

**Not built:** UI-managed trace evaluators (legacy on v3), CI gating with `langfuse/experiment-action` (add it once experiments are stable), rubrics A and Q, and observation-level evaluators (v4 only).

### Verification (slice 3)

Push the dataset twice; the second run must change nothing. Run one experiment against a local Langfuse. Confirm three things in the UI: the dataset run appears with item scores and run-level aggregates, and each item's trace carries the full pipeline spans. Then bump the search-prompt version and run the experiment again. Confirm that the two runs compare side by side in the UI.

---

## Deferred (recorded, not planned here)

- **User feedback as Langfuse scores.** When `feat/in-app-feedback` merges, its handler needs one call: `create_score(trace_id=answer_payload["trace_id"], ...)`. The handler already persists the trace id ([chat_turns.py:977](backend/src/policy_atlas/api/chat_turns.py#L977)).
- **Delete `test_langfuse.py`** at the repository root once slice 1 verifies. The script uses `requests`, which is not a declared dependency, and calls the legacy ingestion endpoint.
