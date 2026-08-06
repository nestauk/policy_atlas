# Planner rehydration mapping (contract strand 12 — plan artefact)

> **rev 2 (2026-07-28, plan-adversarial adjudications):** rows store **both
> representations** (finding 3) — `planner_state` (raw `PlanDraftWire` dump,
> what the planner consumes as `previous_draft`) and `response` (the exact
> projected `PlanningTurnOut`, what idempotent retries return verbatim);
> the projection is never fed back to the planner. **`turn_index`**
> (monotonic per project, assigned at phase-1 insert) is the ordering
> coordinate — `created_at` is display metadata (finding 6). Retry rules:
> latest-row-only retry in place; fresh `pending` row blocks new turns
> (409 `planning_turn_in_progress`); `pending` > 10 min fails on read;
> non-latest retry → 409 `stale_turn`. The **turn lock survives as a
> process-local lock registry** keyed by project (finding 4) — only state
> moves to rows. **`GET /plan` is a named second reader** (finding 5): it
> serves unapproved drafts from the latest completed row and carries a
> draft-after-restart test.

The contract requires an enumerated mapping of every `_PlanningSession` field
(`backend/src/policy_atlas/api/routers/planning.py`, as-built at 027 branch
open) to its durable source in `planning_transcript`. A field with no durable
source is a stop-condition finding. The parity test asserts a rehydrated
session composes the identical planner call (turns list + previous_draft) as
an unbroken one.

| `_PlanningSession` field | As-built role | Durable source | Rule |
|---|---|---|---|
| `turns: list[dict]` | Prose history fed to `planner.plan_turn` (`role: user/planner` alternating) | `planning_transcript` rows, **`turn_index` ascending** | Each **completed** row contributes `{user, user_message}` + `{planner, reply}`. `pending`/`failed` rows contribute nothing (as-built: a failed turn pops the dangling user message — review finding m4; the durable analogue is exclusion). |
| `previous_draft: dict \| None` | Structured draft passed separately to the planner | Latest **completed** row's **`planner_state`** (raw wire dump) | `None` when no completed rows. Never the projected response — the projection drops `steer_point_defaults` and reshapes constraints (finding 3). |
| `draft: PlanDraft \| None` | Last computed draft for read endpoints (`GET /plan`, SSE `plan.updated`) | Latest completed row's `response.plan` | The stored projection, served as-is — no recomputation drift across code changes. |
| `results: OrderedDict[client_turn_id → PlanningTurnOut]` | Idempotency cache (process-local today — the restart-broken promise) | The rows: `client_turn_id` (unique per project) → the stored **`response`**, returned verbatim | Retry rules per the rev-2 note. The LRU bound becomes irrelevant durably — rows are the cache. |
| `session_id: uuid` | Tracing/observability identity for planner calls | **None — deliberately.** Fresh per rehydration | Not quality-bearing: 018 forbids provider-side sessions; context is composed per call from `turns` + `previous_draft`. A restart starting a new trace session is correct, not a loss. |
| `lock: threading.Lock` | Per-project turn concurrency (409 `planning_turn_in_progress`) | **None — process primitive, not state** — survives as a module-level lock **registry** keyed by project id (finding 4: deleting `_sessions` must not delete the 409 primitive). | Two different `client_turn_id`s can never run the planner concurrently for one project: the registry lock + the fresh-`pending`-row check are belt and braces. Staleness window: 10 minutes, pinned (plan pin 2). |

**Approved-plan interaction:** when a turn reaches `ready`, the approved plan
already persists durably (`persist_approved_plan`) — the transcript's phase-2
write joins **that same transaction**, so "the turn that approved the plan"
and the plan itself commit atomically.

**Session-cache retirement:** with all fields durably sourced, the in-memory
`_sessions` OrderedDict survives only as an optional hot cache — the build may
delete it entirely (preferred; one source of truth) or keep it as a
read-through cache with the rows authoritative. Decided in the build task;
deleting is the default unless the turn-latency cost shows up.
