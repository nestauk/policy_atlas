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

from pydantic import BaseModel, ConfigDict, Field

from .common import StageKey

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

#: A theory-of-change walk's kind (task 054's 058 alignment, S3): the draft, an
#: uploaded theory's read, a check, or "Update the report".
TocWalkKind = Literal["draft", "read", "check", "report_update"]


class StageCount(BaseModel):
    """One count a done row shows, with its noun: `312 found` (task 058, N17)."""

    value: int
    noun: str


class RunStageOut(BaseModel):
    """One step of a walk, as its stage frames told it (task 058, round 11).

    The walk's own steps only: an option search's steps belong to that child
    walk, not to the longlist walk that dispatched it. The same words the
    `stage.started` and `stage.completed` frames carry, so a walk that has
    ended renders its rows as the live one did.

    Args:
        stage: The public stage key.
        label: The row's label.
        status: `started` (no end recorded), `completed`, `failed` or
            `skipped`.
        started_at: When the step started, or `None` when only its end is
            recorded.
        ended_at: When it ended, or `None` while started.
        summary: The done row's scalar counts (`stage.completed.summary`),
            or `{"reason": ...}` for a failed or skipped step.
        counts: The counts the done row shows, each with its noun.
        seconds: The step's wall time, when recorded.
    """

    stage: StageKey
    label: str
    status: Literal["started", "completed", "failed", "skipped"]
    started_at: datetime | None = None
    ended_at: datetime | None = None
    summary: dict[str, int | float | str] = Field(default_factory=dict)
    counts: list[StageCount] = Field(default_factory=list)
    seconds: float | None = None


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
        paused_seconds: Seconds the run spent in finished pauses at
            check-ins, on the list and the one-run reads. The run's working
            time is its span from start to end less this.
        artefact_id: The artefact this walk wrote, or `None` when it wrote
            none (it has not reached synthesise, or ended before it). A
            scoping walk that carries one produced a baseline, whatever its
            terminal status (task 044 review, C5/C6).
        parent_capability_run_id: The walk that dispatched this one (a longlist
            walk's option search), or `None` for a parentless walk (task 045).
        purpose: The walk's intent-record purpose (`baseline`, `longlist`,
            `targeted`, ...), or `None` for an Evidence search walk.
        stages: The walk's own steps in the order started (task 058, round
            11), on the list and the one-run reads; empty elsewhere.
        toc_walk: A theory-of-change walk's kind, or `None` for any other
            walk (task 054, S3).
        follows_capability_run_id: For a check the server started by itself
            after a draft, that draft walk's id; `None` otherwise (task 054,
            S3).
    """

    capability_run_id: uuid.UUID
    task_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version: int
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
    # A factory, as for a list field: the generated front-end type then has
    # the field as optional, so a client object without it is still valid.
    paused_seconds: float = Field(default_factory=float)
    artefact_id: uuid.UUID | None = None
    parent_capability_run_id: uuid.UUID | None = None
    purpose: str | None = None
    stages: list[RunStageOut] = Field(default_factory=list)
    toc_walk: TocWalkKind | None = None
    follows_capability_run_id: uuid.UUID | None = None
