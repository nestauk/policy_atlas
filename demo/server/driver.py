"""Demo analysis driver: wraps the REAL 017 runner, streaming progress to the bus.

Execution is `runner.run_plan` — composition, depth gating, per-component
commits, retry-once on LLM-bearing components and failure chaining are all the
real backend's. This module owns only the demo surfaces the backend defers
(component progress protocol, narration): the structlog→SSE bridge, a
step-start observability shim over the named `leg_directive` seam, and
`DemoSSEIO`, the `OrchestratorIO` implementation that turns steering pauses
into SSE check-ins and HTTP answers into real `SteeringResponse`s.

ponytail: module-level bus/stage globals — one live analysis at a time. Per-project
buses if the demo ever runs two analyses concurrently.
"""

import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from demo.server import orchestrator
from demo.server.bus import EventBus

from policy_atlas import runner, tracing
from policy_atlas.db import get_engine
from policy_atlas.orchestrate import _live_planner_and_backends
from policy_atlas.orchestration_plan import OrchestrationPlan
from policy_atlas.schema import evidence_scope, orchestration_plan, project
from policy_atlas.steering import Abort, Adjust, Continue, SteeringResponse

log = structlog.get_logger()

# --- structlog → bus bridge (installed once at app startup) ---

_BUS: EventBus | None = None
_STAGE: str | None = None

# The activity feed is user-facing: ALLOWLIST only. Telemetry (token usage,
# budgets, tracing, internals) never reaches the browser — a curated set of
# log events translates to plain English; everything else is dropped.
_NOTE_EVENTS: dict[str, str] = {
    "screen.call_budget": "Screening the found sources for relevance",
    "screen.profile": "Screening pass starting",
    "search.rapid_thin_escalation": "First pass looks thin — searching deeper",
    "ingest.parse_started": "Reading fetched documents",
    "extract.window": "Reading closely and pulling out findings",
    "extract.doc_started": "Extracting findings from the next document",
    "group.discovery": "Looking for groups across the findings",
    "synthesise.section_started": "Drafting the next section",
}


def _translate(event_dict: dict[str, Any]) -> dict[str, Any] | None:
    name = str(event_dict.get("event", ""))
    if not name:
        return None
    fields = {
        k: v
        for k, v in event_dict.items()
        if k not in ("event", "timestamp", "level", "logger")
        and isinstance(v, (int, float, str, bool))
        and len(str(v)) <= 200
    }
    out: dict[str, Any] = {"stage": _STAGE, "kind": "tick"}
    if "query" in fields:
        out.update(kind="search_query", backend=fields.get("backend", ""),
                   query=str(fields["query"])[:160])
        return out
    if "deep_round" in name or name == "search.deep_round_summary":
        round_fields = {k: fields[k] for k in fields if "round" in k or "relevant" in k}
        out.update(kind="round", **round_fields)
        return out
    if name.startswith("search.") and "count" in fields:
        out.update(kind="results", backend=fields.get("backend", ""), count=fields["count"])
        return out
    if name in _NOTE_EVENTS:
        out.update(note=_NOTE_EVENTS[name])
        return out
    # per-call/per-doc liveness: these fire in real time from worker threads,
    # so a generic plain-English tick per event keeps long stages visibly alive
    # (the frontend collapses consecutive duplicates into a counter)
    live_ticks = {
        "screening.screen.usage": "Screening sources against your question",
        "classification.classify.usage": "Labelling evidence types",
        "extraction.extract.usage": "Reading closely and pulling out findings",
        "fulltext.ingested": "Read a document in full",
        "fulltext.failed": "A document couldn't be fetched — recorded",
        "grouping.discover.usage": "Looking for themes across the sources",
    }
    if name in live_ticks:
        out.update(note=live_ticks[name])
        return out
    return None  # everything else is telemetry — not for the user


def _bridge_processor(logger: Any, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    if _BUS is not None and _STAGE is not None:
        try:
            translated = _translate(dict(event_dict))
            if translated is not None:
                _BUS.emit("stage.progress", translated)
        except Exception:  # noqa: BLE001 — the bridge must never break a component
            pass
    return event_dict


def install_log_bridge() -> None:
    """Prepend the bus bridge to the already-configured structlog processor chain."""
    config = structlog.get_config()
    processors = list(config["processors"])
    if _bridge_processor not in processors:
        structlog.configure(processors=[_bridge_processor] + processors)


# --- step-start shim over the runner's named directive seam ---
# The runner has no per-step start hook (the component progress protocol is a
# deferred seam, docs/deferred.md). `leg_directive` is the documented per-step
# seam and fires exactly once per composed step before its attempts — the shim
# observes the boundary for the timeline and returns the directive unchanged.

_ORIG_LEG_DIRECTIVE = runner.leg_directive


def _observing_leg_directive(
    plan: OrchestrationPlan, step: Any, upstream_state: dict[str, Any]
) -> dict[str, Any]:
    _set_stage(step.component)
    if _BUS is not None:
        label, blurb = orchestrator.STAGES[step.component]
        _BUS.emit("stage.started", {"stage": step.component, "stage_label": label,
                                    "stage_blurb": blurb})
    return _ORIG_LEG_DIRECTIVE(plan, step, upstream_state)


runner.leg_directive = _observing_leg_directive

_SUMMARY_DROP = ("docs", "selected", "excluded", "groups", "themes", "distributions", "rounds")


def _summarise(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Counts-only trim of a check-in payload for SSE / narration.

    User-facing: numbers read as progress; strings (ids, versions, vocab
    values) read as internals — numbers only, capped, one level deep.
    """
    if not payload:
        return {}
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SUMMARY_DROP:
            out[key + "_count"] = len(value) if isinstance(value, (list, dict)) else value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = value
        elif isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and len(out) < 8:
                    out[k] = v
    return {k: v for k, v in list(out.items())[:8]}


class DemoSSEIO:
    """`OrchestratorIO` over the SSE bus: real steering, browser transport.

    `check_in` turns runner boundary payloads into `stage.completed`/`stage.failed`
    events; `pause` emits a `checkin` event carrying the REAL steering options
    and blocks until `POST /checkin/{id}` maps the answer to a real
    `SteeringResponse` (Continue / Adjust / Abort).
    """

    _NARRATED = ("characterise", "synthesise")

    def __init__(self, driver: "AnalysisDriver") -> None:
        self._driver = driver

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        driver = self._driver
        label, _blurb = orchestrator.STAGES[component]
        status = payload.get("status")
        if status == "succeeded":
            summary = _summarise(payload.get("headline_counts") or {})
            if isinstance(payload.get("wall_clock_s"), (int, float)):
                summary["seconds"] = round(payload["wall_clock_s"], 1)
            driver.bus.emit("stage.completed", {"stage": component, "stage_label": label,
                                                "summary": summary})
            if component in self._NARRATED:
                driver.narrate(label, summary)
            return
        reason = str(payload.get("reason", "unknown"))
        driver.bus.emit("stage.failed", {"stage": component, "stage_label": label,
                                         "reason": reason,
                                         "skipped": bool(payload.get("skipped"))})
        # honest, visible, non-fatal: the runner chains off successful
        # predecessors; a failed or skipped stage is reported, never hidden
        verb = "was skipped" if payload.get("skipped") else "hit a limit and stopped"
        driver.bus.emit("narration", {
            "text": f"{label} {verb}: {reason}. Recorded — carrying on with "
            "what the analysis has.",
        })

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        return self._driver.pause(point, render)


class AnalysisDriver:
    """Runs one approved orchestration plan for one project, in a background thread."""

    CHECKIN_TIMEOUT_S = 1800  # unattended-safe: a forgotten pause never hangs the run

    def __init__(
        self,
        project_id: uuid.UUID,
        plan: OrchestrationPlan,
        bus: EventBus,
        create_project_row: bool = False,
    ) -> None:
        self.project_id = project_id
        self.plan = plan
        self.bus = bus
        self.create_project_row = create_project_row
        self.thread: threading.Thread | None = None
        self.failed: str | None = None
        self.done = False
        self.paused = False
        self._checkin_replies: dict[str, dict[str, Any]] = {}
        self._checkin_event = threading.Event()

    # -- public --

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def answer_checkin(self, checkin_id: str, reply: str,
                       params: dict[str, Any] | None = None) -> None:
        self._checkin_replies[checkin_id] = {"reply": reply, "params": params or {}}
        self._checkin_event.set()

    # -- internals --

    def _run(self) -> None:
        global _BUS
        _BUS = self.bus
        try:
            self.bus.emit("analysis.started", {})
            engine = get_engine()
            scope_id, plan_row_id = self._write_rows(engine)
            langfuse_client = tracing.get_langfuse()
            _planner, backends = _live_planner_and_backends(langfuse_client)
            outcome = runner.run_plan(
                engine,
                project_id=self.project_id,
                evidence_scope_id=scope_id,
                plan=self.plan,
                plan_id=plan_row_id,
                plan_version=1,
                plan_row_id=plan_row_id,
                backends=backends,
                io=DemoSSEIO(self),
            )
            if outcome.status == "failed":
                self.failed = outcome.collation_render
                self.bus.emit("analysis.failed", {"stage": _STAGE,
                                                  "message": "The run failed.",
                                                  "collation": outcome.collation_render})
            elif outcome.status == "aborted":
                self.bus.emit("analysis.aborted", {"collation": outcome.collation_render})
            else:
                # succeeded or degraded — flags rendered honestly either way
                self.bus.emit("analysis.completed", {
                    "status": outcome.status, "collation": outcome.collation_render,
                })
        except Exception as exc:  # noqa: BLE001 — surface honestly, never hang the stream
            log.exception("demo.analysis_failed")
            self.failed = f"{type(exc).__name__}: {exc}"
            self.bus.emit("analysis.failed", {"stage": _STAGE, "message": self.failed})
        finally:
            self.done = True
            _set_stage(None)
            _BUS = None

    def _write_rows(self, engine: Any) -> tuple[uuid.UUID, uuid.UUID]:
        """Project (for fresh runs) + scope + approved plan row, one transaction.

        Mirrors `orchestrate._write_plan_row`, which mints its own project id —
        the demo's projects exist before their run does.
        """
        scope_id = uuid.uuid4()
        plan_row_id = uuid.uuid4()
        now = datetime.now(UTC)
        with engine.begin() as conn:
            if self.create_project_row:
                conn.execute(project.insert().values(
                    project_id=self.project_id, created_at=now,
                ))
            conn.execute(evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                project_id=self.project_id,
                intent=self.plan.question,
                context={},
                created_at=now,
            ))
            conn.execute(orchestration_plan.insert().values(
                plan_id=plan_row_id,
                project_id=self.project_id,
                evidence_scope_id=scope_id,
                version=1,
                status="approved",
                payload=self.plan.model_dump(mode="json"),
                created_at=now,
                created_by="user",
                approved_at=now,
            ))
        return scope_id, plan_row_id

    def narrate(self, label: str, summary: dict[str, Any]) -> None:
        try:
            text = orchestrator.narrate(label, self.plan.question, summary)
            self.bus.emit("narration", {"text": text})
        except Exception:  # noqa: BLE001 — narration is garnish, never fatal
            log.exception("demo.narration_failed")

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        """One steering pause: real options out, real SteeringResponse back."""
        checkin_id = str(uuid.uuid4())
        kind = str(point.get("kind", "check_in"))
        try:
            text = orchestrator.checkin_prose(self.plan.question, render, kind)
        except Exception:  # noqa: BLE001 — prose is garnish; the render is the content
            text = render
        options = [{"id": "continue", "label": "Continue",
                    "description": "Carry on as planned.", "requires_user_input": False}]
        for option in point.get("options") or []:
            if option["id"] == "as_proposed":
                continue  # semantically identical to the leading Continue
            options.append({k: option[k] for k in
                            ("id", "label", "description", "requires_user_input")})
        options.append({"id": "abort", "label": "Stop the analysis",
                        "description": "End the run cleanly; everything done so far is kept.",
                        "requires_user_input": False})
        self._checkin_event.clear()
        self.paused = True
        self.bus.emit("checkin", {"checkin_id": checkin_id, "kind": kind,
                                  "text": text, "render": render, "options": options,
                                  "triggers": point.get("triggers") or []})
        try:
            self._checkin_event.wait(timeout=self.CHECKIN_TIMEOUT_S)
        finally:
            self.paused = False
        answer = self._checkin_replies.pop(checkin_id, None)
        if answer is None:
            self.bus.emit("narration", {"text": "No answer in time — carrying on as planned."})
            return Continue()
        return self._map_reply(point, answer["reply"], answer["params"])

    def _map_reply(
        self, point: dict[str, Any], reply: str, params: dict[str, Any]
    ) -> SteeringResponse:
        if reply == "abort":
            self.bus.emit("narration", {"text": "Stopping the analysis — everything "
                                        "done so far is kept."})
            return Abort()
        by_id = {o["id"]: o for o in point.get("options") or []}
        option = by_id.get(reply)
        if reply == "continue" or option is None or option["id"] == "as_proposed":
            self.bus.emit("narration", {"text": "Noted — carrying on."})
            return Continue()
        delta: dict[str, Any] = option.get("delta") or {}
        if option["id"] == "adjust_budget":
            budget = params.get("budget")
            if not isinstance(budget, int) or budget < 1:
                self.bus.emit("narration", {"text": "That budget didn't parse — "
                                            "carrying on unchanged."})
                return Continue()
            delta = {"selection": {"budget": budget}}
        elif option["id"] == "deepen_clusters":
            delta = {"selection": {
                "priority_strata": [s for s in params.get("strata", []) if s],
                "must_include_ids": [d for d in params.get("docs", []) if d],
            }}
        self.bus.emit("narration", {"text": f"Noted — {option['label'].lower()}. "
                                    "Re-running the shortlist."})
        return Adjust(directive_deltas={"select": delta})


def _set_stage(stage: str | None) -> None:
    global _STAGE
    _STAGE = stage
