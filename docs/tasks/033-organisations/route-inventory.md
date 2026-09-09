# Route inventory — Phase 0 baseline evidence

Captured from the code tree (not from any doc) on 2026-08-24, for task
033-organisations Phase 0. Source: `backend/src/policy_atlas/api/routers/`
(`_common.py`, `check_ins.py`, `conversations.py`, `planning.py`,
`portfolios.py`, `projects.py`, `read_models.py`, `runs.py`, `sse.py`) plus
`backend/src/policy_atlas/api/chat_turns.py`.

**Total HTTP route decorators: 39** (confirmed by grepping
`^@router\.(get|post|patch|put|delete)\(` and
`^@project_router\.(get|post|patch|put|delete)\(` across the nine files).

`_common.py` and `chat_turns.py` carry **zero** route decorators. `_common.py`
holds only the shared ownership helpers (`owned_project`, `owned_portfolio`,
`run_out`, `project_out`). `chat_turns.py` is a two-phase durable *service*
module (`ChatTurnResult`, `_phase_one_turn`, `run_chat_turn`,
`apply_appraisal_labels`) with no `APIRouter` of its own — the chat-turn HTTP
routes it backs (`create_chat_turn_stream`, `cancel_chat_turn`,
`list_chat_turns`) actually live on `conversations.py`'s `router`
(mounted at `/api/v1/conversations`), which imports `chat_turns` functions
directly.

All routers are mounted with `app.include_router(router)` and **no
additional prefix** (`backend/src/policy_atlas/api/app.py` lines 157–168), so
each route's full path is exactly `router.prefix + <decorator path>`.

## Router prefixes

| File | Router variable | `prefix=` |
|---|---|---|
| check_ins.py | `router` | `/api/v1/projects` |
| conversations.py | `router` | `/api/v1/conversations` |
| conversations.py | `project_router` | `/api/v1/projects` |
| planning.py | `router` | `/api/v1/projects` |
| portfolios.py | `router` | `/api/v1/portfolios` |
| projects.py | `router` | `/api/v1/projects` |
| read_models.py | `router` | `/api/v1/projects` |
| runs.py | `router` | `/api/v1/projects` |
| sse.py | `router` | `/api/v1/projects` |

`conversations.py` is the one file with **two** `APIRouter`s: `router`
(`/api/v1/conversations`, conversation-id-rooted routes and chat-turn
streaming) and `project_router` (`/api/v1/projects`, the project-scoped
list/create conversation routes).

## Full route table

| File | Method | Full path | Function | Ownership resolution |
|---|---|---|---|---|
| check_ins.py | GET | `/api/v1/projects/{project_id}/check-ins` | `list_check_ins` | `owned_project` |
| check_ins.py | POST | `/api/v1/projects/{project_id}/check-ins/{check_in_id}/response` | `respond_to_check_in` | `owned_project` |
| conversations.py (`project_router`) | GET | `/api/v1/projects/{project_id}/conversations` | `list_conversations` | `owned_project` |
| conversations.py (`project_router`) | POST | `/api/v1/projects/{project_id}/conversations` | `create_conversation` | `owned_project` |
| conversations.py (`router`) | GET | `/api/v1/conversations/{conversation_id}` | `get_conversation` | `_owned_conversation` (inline helper, joins `conversation`→`project`, filters `owner_user_id`) |
| conversations.py (`router`) | PATCH | `/api/v1/conversations/{conversation_id}` | `update_conversation` | `_owned_conversation` |
| conversations.py (`router`) | POST | `/api/v1/conversations/{conversation_id}/archive` | `archive_conversation` | `_owned_conversation` |
| conversations.py (`router`) | POST | `/api/v1/conversations/{conversation_id}/unarchive` | `unarchive_conversation` | `_owned_conversation` |
| conversations.py (`router`) | GET | `/api/v1/conversations/{conversation_id}/turns` | `list_chat_turns` | `_owned_conversation` |
| conversations.py (`router`) | POST | `/api/v1/conversations/{conversation_id}/turns` | `create_chat_turn_stream` | inline filter (joins `conversation`→`project`, `owner_user_id == user.user_id`, `status == "active"`) — not via `_owned_conversation`/`owned_project` |
| conversations.py (`router`) | POST | `/api/v1/conversations/{conversation_id}/turns/{turn_id}/cancel` | `cancel_chat_turn` | inline filter (joins `chat_turn`→`conversation`→`project`, `owner_user_id == user.user_id`) |
| planning.py | POST | `/api/v1/projects/{project_id}/planning-turns` | `create_planning_turn` | `owned_project` (via `_phase_one_turn`) |
| planning.py | GET | `/api/v1/projects/{project_id}/planning-turns` | `list_planning_turns` | `owned_project` |
| planning.py | GET | `/api/v1/projects/{project_id}/plan` | `get_plan` | `owned_project` |
| planning.py | PATCH | `/api/v1/projects/{project_id}/plan` | `patch_plan` | `owned_project` |
| portfolios.py | GET | `/api/v1/portfolios` | `list_portfolios` | inline filter (`portfolio.c.owner_user_id == user.user_id`) |
| portfolios.py | POST | `/api/v1/portfolios` | `create_portfolio` | none (new row, `owner_user_id` set to caller) |
| portfolios.py | GET | `/api/v1/portfolios/{portfolio_id}` | `get_portfolio` | `owned_portfolio` |
| portfolios.py | PATCH | `/api/v1/portfolios/{portfolio_id}` | `update_portfolio` | `owned_portfolio` |
| projects.py | GET | `/api/v1/projects` | `list_projects` | inline filter (`project.c.owner_user_id == user.user_id`) |
| projects.py | POST | `/api/v1/projects` | `create_project` | none (new row, `owner_user_id` set to caller) |
| projects.py | GET | `/api/v1/projects/{project_id}` | `get_project` | `owned_project` |
| projects.py | PATCH | `/api/v1/projects/{project_id}` | `update_project` | `owned_project` (+ `owned_portfolio` when `portfolio_id` changes) |
| projects.py | POST | `/api/v1/projects/{project_id}/archive` | `archive_project_route` | `owned_project` |
| read_models.py | GET | `/api/v1/projects/{project_id}/funnel` | `funnel` | `owned_project` (via `_owned` wrapper) |
| read_models.py | GET | `/api/v1/projects/{project_id}/landscape` | `landscape` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/groups` | `groups` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/evidence` | `evidence` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/findings` | `findings` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/sources/{source_id}` | `source_dossier` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/decisions` | `decisions` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/artefact` | `artefact` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/coverage` | `coverage` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/citations/{citation_key}/context` | `chunk_context` | `owned_project` (via `_owned`) |
| read_models.py | GET | `/api/v1/projects/{project_id}/chunks/{chunk_id}/context` | `chat_chunk_context` | `owned_project` (via `_owned`) |
| runs.py | POST | `/api/v1/projects/{project_id}/runs` | `create_run` | `owned_project` |
| runs.py | GET | `/api/v1/projects/{project_id}/runs` | `list_runs` | `owned_project` |
| runs.py | GET | `/api/v1/projects/{project_id}/runs/{run_id}` | `get_run` | `owned_project` |
| sse.py | GET | `/api/v1/projects/{project_id}/events` | `stream_events` | `owned_project` (via `_snapshot`) |

`chat_turns.py` contributes no rows to this table — see note above.

## Alembic head

Confirmed by walking the `down_revision` chain across all 29 files in
`backend/alembic/versions/`: exactly one revision id is never referenced as
another migration's `down_revision` — **`b3c7d914e0a2`**
(`b3c7d914e0a2_portfolio_layer.py`), whose own `down_revision` is
`d8e4a1c7f2b9`. This matches the expected head.

## `metadata.tables == 33` assertions

`grep -rn "metadata.tables" backend/tests/` finds exactly six test files
asserting `len(metadata.tables) == 33`:

| File | Line |
|---|---|
| `backend/tests/evidence_base/assess/test_appraise.py` | 90 |
| `backend/tests/evidence_base/assess/test_classify.py` | 52 |
| `backend/tests/evidence_base/assess/test_screen.py` | 69 |
| `backend/tests/evidence_base/sourcing/test_acquire.py` | 178 |
| `backend/tests/evidence_base/sourcing/test_ingest_full_text.py` | 1357 |
| `backend/tests/core/test_embeddings.py` | 74 |

`backend/tests/core/test_schema.py` carries the portfolio column-set
equality assertion in `test_migration_roundtrip_portfolio_layer` (function
at line 241): after `command.upgrade(cfg, "head")`, lines 262–268 assert

```python
assert {c["name"] for c in inspector.get_columns("portfolio")} == {
    "portfolio_id",
    "owner_user_id",
    "name",
    "description",
    "created_at",
}
```
