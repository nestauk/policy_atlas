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
    """Inbound body for `POST /api/v1/projects/{id}/runs`.

    The run is created from the project's current approved-ready plan; the
    request body carries no fields. `extra="forbid"` rejects any body at
    all beyond `{}`.
    """

    model_config = ConfigDict(extra="forbid")


class RunOut(BaseModel):
    """A capability run resource.

    Args:
        capability_run_id: The run's identity.
        project_id: Owning project.
        plan_id: Identity of the plan the run executes.
        plan_version: Plan version current at run creation.
        status: Current run status.
        started_at: When the run started executing.
        ended_at: When the run reached a terminal status, or `None` while
            still running or paused.
    """

    capability_run_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version: int
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
