"""Demo FastAPI app: planning chat, analysis lifecycle, SSE stream, read models.

Run: uv run uvicorn demo.server.app:app --port 8100
"""

import json
import queue
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from demo.server import orchestrator, readmodels
from demo.server.bus import EventBus, sse_format
from demo.server.driver import AnalysisDriver, _summarise, install_log_bridge
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select

from policy_atlas import events
from policy_atlas.db import get_engine
from policy_atlas.logging import configure_logging
from policy_atlas.orchestration_plan import OrchestrationPlan
from policy_atlas.schema import project_source_snapshot, synthesis_result

_SIDECAR = Path(__file__).parent / "projects.json"
_LOCK = threading.Lock()


class ProjectState:
    def __init__(self, project_id: str, name: str, question: str = "") -> None:
        self.project_id = project_id
        self.name = name
        self.question = question
        # planner-format turns: [{"role": "user"|"planner", "text": ...}]
        self.turns: list[dict[str, str]] = []
        self.draft: dict[str, Any] | None = None  # last PlanDraftWire dump
        self.plan: dict[str, Any] | None = None  # wire payload for the frontend
        self.approved: dict[str, Any] | None = None  # validated OrchestrationPlan dump
        self.bus = EventBus()
        self.driver: AnalysisDriver | None = None
        self.created_at = datetime.now(UTC).isoformat()
        # names set from the plan's derived title may be replaced by better ones;
        # names typed by the user never are
        self.auto_named = name == "Untitled project"


PROJECTS: dict[str, ProjectState] = {}


def _load_sidecar() -> None:
    if _SIDECAR.exists():
        for entry in json.loads(_SIDECAR.read_text()):
            state = ProjectState(entry["project_id"], entry["name"], entry.get("question", ""))
            state.plan = entry.get("plan")
            state.approved = entry.get("approved")
            state.turns = entry.get("turns", [])
            state.created_at = entry.get("created_at", state.created_at)
            PROJECTS[entry["project_id"]] = state


def _save_sidecar() -> None:
    with _LOCK:
        _SIDECAR.write_text(json.dumps([
            {"project_id": s.project_id, "name": s.name, "question": s.question,
             "plan": s.plan, "approved": s.approved, "turns": s.turns,
             "created_at": s.created_at}
            for s in PROJECTS.values()
        ], indent=1))


def _hydrate_backlog(state: ProjectState, conn: Any) -> None:
    """Rebuild the SSE backlog after a restart, from the durable record.

    The bus is in-memory (RETRO §3): a restart loses the stream, but the chat
    turns persist in the sidecar and every component outcome is in the
    canonical event_log — so the frontend's replay-and-rebuild path works
    unchanged on a reconstructed backlog. Live-progress ticks and narration
    prose are gone for good (not persisted); the timeline, summaries and
    terminal state are exact.
    """
    pid = uuid.UUID(state.project_id)
    for turn in state.turns:
        if turn.get("role") == "user":
            state.bus.emit("user.message", {"text": turn.get("text", "")})
        else:
            state.bus.emit("narration", {"text": turn.get("text", "")})
    if state.plan:
        state.bus.emit("plan.updated", {"plan": state.plan})

    # component.completed/.failed carry the harness REGISTRY name; both screen
    # steps dispatch to registry "screen" (019 renamed only the plan vocabulary),
    # so replay maps it to the stage-1 step for display.
    def _stage(payload: dict) -> str | None:
        component = payload.get("component")
        return "screen_abstract" if component == "screen" else component

    stage_events = [
        e for e in events.read(conn, pid)
        if e["event_type"] in ("component.completed", "component.failed")
        and _stage(e["payload"]) in orchestrator.STAGES
    ]
    has_artefact = conn.execute(
        select(func.count()).select_from(synthesis_result)
        .where(synthesis_result.c.project_id == pid)
    ).scalar_one() > 0
    if not stage_events:
        return
    state.bus.emit("analysis.started", {})
    for entry in stage_events:
        stage = _stage(entry["payload"])
        label, blurb = orchestrator.STAGES[stage]
        if entry["event_type"] == "component.completed":
            summary = _summarise({k: v for k, v in entry["payload"].items()
                                  if k != "component"})
            state.bus.emit("stage.completed", {"stage": stage, "stage_label": label,
                                               "summary": summary})
        else:
            state.bus.emit("stage.failed", {
                "stage": stage, "stage_label": label,
                "reason": str(entry["payload"].get("error", "unknown")), "skipped": False,
            })
    if has_artefact:
        state.bus.emit("analysis.completed", {"status": "succeeded", "collation": ""})
    else:
        state.bus.emit("analysis.failed", {
            "stage": None,
            "message": "This run didn't finish (interrupted or failed before the "
            "write-up). Everything completed is shown; start the analysis again "
            "to continue.",
        })


def _status(state: ProjectState, conn: Any) -> str:
    if state.driver is not None and state.driver.running:
        return "paused" if state.driver.paused else "running"
    if state.driver is not None and state.driver.failed:
        return "failed"
    has_artefact = conn.execute(
        select(func.count()).select_from(synthesis_result)
        .where(synthesis_result.c.project_id == uuid.UUID(state.project_id))
    ).scalar_one() > 0
    if has_artefact:
        return "complete"
    return "planning" if state.turns else "new"


app = FastAPI(title="Policy Atlas demo")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    configure_logging()
    install_log_bridge()
    _load_sidecar()
    # rebuild each project's SSE backlog from the durable record; a project
    # whose history can't hydrate still serves (read models are DB-backed)
    import structlog
    log = structlog.get_logger()
    try:
        with get_engine().connect() as conn:
            for state in PROJECTS.values():
                try:
                    _hydrate_backlog(state, conn)
                except Exception:  # noqa: BLE001
                    log.exception("demo.hydrate_failed", project_id=state.project_id)
    except Exception:  # noqa: BLE001 — no DB at boot: read models will fail anyway
        log.exception("demo.hydrate_skipped")


class ChatIn(BaseModel):
    message: str


class CheckinIn(BaseModel):
    reply: str
    params: dict[str, Any] | None = None


class ProjectIn(BaseModel):
    name: str


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    engine = get_engine()
    out = []
    with engine.connect() as conn:
        for state in PROJECTS.values():
            pid = uuid.UUID(state.project_id)
            source_count = conn.execute(
                select(func.count()).select_from(project_source_snapshot)
                .where(project_source_snapshot.c.project_id == pid)
            ).scalar_one()
            out.append({
                "project_id": state.project_id, "name": state.name,
                "question": state.question or (state.plan or {}).get("question") or "",
                "status": _status(state, conn), "created_at": state.created_at,
                "source_count": source_count, "updated_at": state.created_at,
            })
    return sorted(out, key=lambda p: p["created_at"], reverse=True)


@app.post("/api/projects")
def create_project(body: ProjectIn) -> dict[str, str]:
    project_id = str(uuid.uuid4())
    PROJECTS[project_id] = ProjectState(project_id, body.name)
    _save_sidecar()
    return {"project_id": project_id}


def _state(project_id: str) -> ProjectState:
    state = PROJECTS.get(project_id)
    if state is None:
        raise HTTPException(404, "unknown project")
    return state


@app.post("/api/projects/{project_id}/chat")
def chat(project_id: str, body: ChatIn) -> dict[str, Any]:
    state = _state(project_id)
    state.turns.append({"role": "user", "text": body.message})
    state.bus.emit("user.message", {"text": body.message})
    state.bus.emit(
        "stage.progress",
        {"stage": None, "kind": "tick", "note": "Planning the analysis"},
    )
    turn = orchestrator.plan_turn(state.turns, state.draft)
    state.draft = turn.plan_draft.model_dump()

    # fail-closed: a ready draft must validate into an OrchestrationPlan; a
    # validation failure is surfaced honestly, never run (orchestrate.py's loop)
    validated: OrchestrationPlan | None = None
    reply = turn.reply
    if turn.ready:
        try:
            validated = orchestrator.build_plan(turn)
        except ValidationError as exc:
            reply = f"{turn.reply}\n\n{orchestrator.validation_reply(exc)}"
    if turn.question:
        reply = f"{reply}\n\n{turn.question}"
    state.turns.append({"role": "planner", "text": reply})

    plan = orchestrator.plan_payload(state.draft, validated)
    state.plan = plan
    state.approved = validated.model_dump(mode="json") if validated else None
    state.question = plan.get("question") or ""
    # derive the project name from the plan's title, never the raw message;
    # user-typed names always win
    title = plan.get("title")
    if state.auto_named and isinstance(title, str) and title.strip():
        state.name = title.strip()
    # Conversation lands on the bus too, so a reconnecting tab replays the full
    # transcript (the open tab dedups against its local copy). The user turn was
    # emitted before the planner call so the browser has a live progress tick
    # during multi-turn planning.
    state.bus.emit("narration", {"text": reply,
                                 "suggestions": turn.suggested_answers or []})
    state.bus.emit("plan.updated", {"plan": plan})
    _save_sidecar()
    return {"reply": reply, "plan": plan, "suggestions": turn.suggested_answers or []}


@app.post("/api/projects/{project_id}/start")
def start(project_id: str) -> dict[str, Any]:
    state = _state(project_id)
    if state.approved is None:
        raise HTTPException(400, "no approved plan yet")
    if state.driver is not None and state.driver.running:
        raise HTTPException(409, "analysis already running")
    if any(s.driver is not None and s.driver.running for s in PROJECTS.values()):
        raise HTTPException(409, "another analysis is running")  # ponytail: one at a time
    plan = OrchestrationPlan.model_validate(state.approved)
    state.driver = AnalysisDriver(
        uuid.UUID(project_id), plan, state.bus, create_project_row=True,
    )
    state.driver.start()
    _save_sidecar()
    return {"ok": True}


@app.post("/api/projects/{project_id}/checkin/{checkin_id}")
def answer_checkin(project_id: str, checkin_id: str, body: CheckinIn) -> dict[str, Any]:
    state = _state(project_id)
    if state.driver is None:
        raise HTTPException(409, "no analysis running")
    state.driver.answer_checkin(checkin_id, body.reply, body.params)
    return {"ok": True}


@app.get("/api/projects/{project_id}/events")
def events_stream(project_id: str) -> StreamingResponse:
    state = _state(project_id)

    def generate():
        backlog, q = state.bus.subscribe()
        try:
            for event in backlog:
                yield sse_format(event)
            while True:
                try:
                    yield sse_format(q.get(timeout=15))
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            state.bus.unsubscribe(q)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/api/projects/{project_id}/plan")
def get_plan(project_id: str) -> dict[str, Any]:
    state = _state(project_id)
    return state.plan or dict(orchestrator.EMPTY_PLAN)


def _read(project_id: str, fn: Any) -> Any:
    _state(project_id)
    with get_engine().connect() as conn:
        return fn(conn, uuid.UUID(project_id))


@app.get("/api/projects/{project_id}/funnel")
def funnel(project_id: str) -> dict[str, Any]:
    return _read(project_id, readmodels.funnel)


@app.get("/api/projects/{project_id}/landscape")
def landscape(project_id: str) -> dict[str, Any] | None:
    return _read(project_id, readmodels.landscape)


@app.get("/api/projects/{project_id}/groups")
def groups(project_id: str) -> dict[str, Any] | None:
    return _read(project_id, readmodels.groups)


@app.get("/api/projects/{project_id}/evidence")
def evidence(project_id: str) -> list[dict[str, Any]]:
    return _read(project_id, readmodels.evidence_table)


@app.get("/api/projects/{project_id}/artefact")
def artefact(project_id: str) -> dict[str, Any] | None:
    return _read(project_id, readmodels.artefact)


@app.get("/api/projects/{project_id}/findings")
def findings(project_id: str) -> list[dict[str, Any]]:
    return _read(project_id, readmodels.findings)


@app.get("/api/projects/{project_id}/decisions")
def decisions(project_id: str) -> list[dict[str, Any]]:
    """DB audit trail merged with this session's check-ins and narrations."""
    state = _state(project_id)
    entries = _read(project_id, readmodels.decision_log)
    queries: list[str] = []
    for event in state.bus.backlog:
        if event["type"] == "checkin":
            entries.append({
                "at": datetime.fromtimestamp(event["ts"], UTC).isoformat(),
                "kind": "checkin",
                "text": f"Paused to check in: {event['data']['text']}",
                "detail": {},
            })
        elif (
            event["type"] == "stage.progress"
            and event["data"].get("kind") == "search_query"
            and event["data"].get("query")
        ):
            backend = str(event["data"].get("backend", "")).title() or "Search"
            queries.append(f"{backend}: {event['data']['query']}")
    if queries:
        entries.append({
            "at": datetime.fromtimestamp(state.bus.backlog[0]["ts"], UTC).isoformat(),
            "kind": "searches",
            "text": f"Search terms used ({len(queries)} queries)",
            # the exact wire queries, user-inspectable
            "detail": {f"Query {i + 1}": q for i, q in enumerate(queries[:40])},
        })
    return sorted(entries, key=lambda e: e["at"])


@app.get("/api/projects/{project_id}/coverage")
def coverage(project_id: str) -> dict[str, Any] | None:
    return _read(project_id, readmodels.coverage)


@app.get("/api/projects/{project_id}/chunks/{chunk_id}/context")
def chunk_context(project_id: str, chunk_id: str) -> dict[str, Any] | None:
    _state(project_id)
    with get_engine().connect() as conn:
        return readmodels.chunk_context(conn, uuid.UUID(project_id), uuid.UUID(chunk_id))


@app.get("/api/projects/{project_id}/sources/{source_id}")
def source_detail(project_id: str, source_id: str) -> dict[str, Any] | None:
    _state(project_id)
    with get_engine().connect() as conn:
        return readmodels.source_detail(conn, uuid.UUID(project_id), uuid.UUID(source_id))
