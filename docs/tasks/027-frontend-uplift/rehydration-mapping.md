# Planner rehydration mapping (contract strand 12 — plan artefact)

The contract requires an enumerated mapping of every `_PlanningSession` field
(`backend/src/policy_atlas/api/routers/planning.py`, as-built at 027 branch
open) to its durable source in `planning_transcript`. A field with no durable
source is a stop-condition finding. The parity test asserts a rehydrated
session composes the identical planner call (turns list + previous_draft) as
an unbroken one.

| `_PlanningSession` field | As-built role | Durable source | Rule |
|---|---|---|---|
| `turns: list[dict]` | Prose history fed to `planner.plan_turn` (`role: user/planner` alternating) | `planning_transcript` rows, `created_at` ascending | Each **completed** row contributes `{user, user_message}` + `{planner, reply}`. `pending`/`failed` rows contribute nothing (as-built: a failed turn pops the dangling user message — review finding m4; the durable analogue is exclusion). |
| `previous_draft: dict \| None` | Structured draft passed separately to the planner | Latest **completed** row's `plan_draft` snapshot | `None` when no completed rows (fresh project). |
| `draft: PlanDraft \| None` | Last computed draft for read endpoints | Same as `previous_draft` (derived, not separately stored) | Recomputed via the existing `_draft_from_wire`/`_draft_from_plan` path. |
| `results: OrderedDict[client_turn_id → PlanningTurnOut]` | Idempotency cache (process-local today — the restart-broken promise) | The rows themselves: `client_turn_id` (unique per project) → reply/plan_draft/suggestions | A completed row reconstitutes its `PlanningTurnOut` verbatim; a `pending`/`failed` row means the retry re-runs the turn in place. The LRU bound (`PLAN_SESSION_CACHE_MAX`) becomes irrelevant durably — rows are the cache. |
| `session_id: uuid` | Tracing/observability identity for planner calls | **None — deliberately.** Fresh per rehydration | Not quality-bearing: 018 forbids provider-side sessions; context is composed per call from `turns` + `previous_draft`. A restart starting a new trace session is correct, not a loss. |
| `lock: threading.Lock` | Per-project turn concurrency (409 `planning_turn_in_progress`) | **None — process primitive, not state.** | Concurrency semantics unchanged (one API instance, 025 posture). A `pending` row older than a bounded staleness window is treated as failed (crash leftover), not as an in-progress turn — exact window pinned in the build. |

**Approved-plan interaction:** when a turn reaches `ready`, the approved plan
already persists durably (`persist_approved_plan`) — the transcript's phase-2
write joins **that same transaction**, so "the turn that approved the plan"
and the plan itself commit atomically.

**Session-cache retirement:** with all fields durably sourced, the in-memory
`_sessions` OrderedDict survives only as an optional hot cache — the build may
delete it entirely (preferred; one source of truth) or keep it as a
read-through cache with the rows authoritative. Decided in the build task;
deleting is the default unless the turn-latency cost shows up.
