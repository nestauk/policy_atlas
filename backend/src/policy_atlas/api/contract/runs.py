"""Capability run resource contract: creation body and the read shape.

A run is the durable walk identity created by `POST .../runs` and observed
through `GET .../runs` / `GET .../runs/{run_id}` and the SSE `run.status`
frame (`sse.py`). Status values are the contract; nothing else about run
execution is modelled here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

#: Run lifecycle status. Contract (spec § Runs).
RunStatus = Literal[
    "running",
    "paused",
    "succeeded",
    "degraded",
    "failed",
    "aborted",
    "interrupted",
]


class RunCreate(BaseModel):
    """Inbound body for `POST /api/v1/tasks/{id}/runs`.

    The run is created from the task's current approved-ready plan; the
    request body carries no fields. `extra="forbid"` rejects any body at
    all beyond `{}`.
    """

    model_config = ConfigDict(extra="forbid")


class RunOut(BaseModel):
    """A capability run resource.

    Args:
        capability_run_id: The run's identity.
        task_id: Owning task.
        plan_id: Identity of the plan the run executes.
        plan_version: Plan version current at run creation.
        status: Current run status.
        started_at: When the run started executing.
        ended_at: When the run reached a terminal status, or `None` while
            still running or paused.
        artefact_id: The artefact this walk wrote, or `None` when it wrote
            none (it has not reached synthesise, or ended before it). A
            scoping walk that carries one produced a baseline, whatever its
            terminal status (task 044 review, C5/C6).
        parent_capability_run_id: The walk that dispatched this one (a longlist
            walk's option search), or `None` for a parentless walk (task 045).
        purpose: The walk's intent-record purpose (`baseline`, `longlist`,
            `targeted`, ...), or `None` for an Evidence search walk.
    """

    capability_run_id: uuid.UUID
    task_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version: int
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
    artefact_id: uuid.UUID | None = None
    parent_capability_run_id: uuid.UUID | None = None
    purpose: str | None = None
