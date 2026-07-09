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
from demo.server.driver import AnalysisDriver, install_log_bridge
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from policy_atlas.db import get_engine
from policy_atlas.logging import configure_logging
from policy_atlas.schema import project_source_snapshot, synthesis_result

_SIDECAR = Path(__file__).parent / "projects.json"
_LOCK = threading.Lock()


class ProjectState:
    def __init__(self, project_id: str, name: str, question: str = "") -> None:
        self.project_id = project_id
        self.name = name
        self.question = question
        self.history: list[dict[str, str]] = []
        self.plan: dict[str, Any] | None = None
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
            state.created_at = entry.get("created_at", state.created_at)
            PROJECTS[entry["project_id"]] = state


def _save_sidecar() -> None:
    with _LOCK:
        _SIDECAR.write_text(json.dumps([
            {"project_id": s.project_id, "name": s.name, "question": s.question,
             "plan": s.plan, "created_at": s.created_at}
            for s in PROJECTS.values()
        ], indent=1))


def _status(state: ProjectState, conn: Any) -> str:
    if state.driver is not None and state.driver.running:
        return "running"
    if state.driver is not None and state.driver.failed:
        return "failed"
    has_artefact = conn.execute(
        select(func.count()).select_from(synthesis_result)
        .where(synthesis_result.c.project_id == uuid.UUID(state.project_id))
    ).scalar_one() > 0
    if has_artefact:
        return "complete"
    return "planning" if state.history else "new"


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


class ChatIn(BaseModel):
    message: str


class CheckinIn(BaseModel):
    reply: str


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
                "question": state.question or (state.plan or {}).get("question", ""),
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
    state.history.append({"role": "user", "content": body.message})
    reply, plan = orchestrator.plan_turn(state.history, state.plan)
    plan["steps"] = orchestrator.plan_steps(plan)
    state.history.append({"role": "assistant", "content": reply})
    state.plan = plan
    state.question = plan.get("question", "")
    # derive the project name from the plan's title, never the raw message;
    # user-typed names always win
    title = plan.get("title", "")
    if state.auto_named and isinstance(title, str) and title.strip():
        state.name = title.strip()
    # conversation lands on the bus too, so a reconnecting tab replays the
    # full transcript (the open tab dedups against its local copy)
    state.bus.emit("user.message", {"text": body.message})
    state.bus.emit("narration", {"text": reply})
    state.bus.emit("plan.updated", {"plan": plan})
    _save_sidecar()
    return {"reply": reply, "plan": plan}


@app.post("/api/projects/{project_id}/start")
def start(project_id: str) -> dict[str, Any]:
    state = _state(project_id)
    if state.plan is None or not state.plan.get("question"):
        raise HTTPException(400, "no plan yet")
    if state.driver is not None and state.driver.running:
        raise HTTPException(409, "analysis already running")
    if any(s.driver is not None and s.driver.running for s in PROJECTS.values()):
        raise HTTPException(409, "another analysis is running")  # ponytail: one at a time
    state.driver = AnalysisDriver(
        uuid.UUID(project_id), state.plan, state.bus, create_project_row=True,
    )
    state.driver.start()
    _save_sidecar()
    return {"ok": True}


@app.post("/api/projects/{project_id}/checkin/{checkin_id}")
def answer_checkin(project_id: str, checkin_id: str, body: CheckinIn) -> dict[str, Any]:
    state = _state(project_id)
    if state.driver is None:
        raise HTTPException(409, "no analysis running")
    state.driver.answer_checkin(checkin_id, body.reply)
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
