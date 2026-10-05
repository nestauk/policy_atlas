"""Conversation, chat-turn, and NDJSON stream contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CHAT_MESSAGE_MAX = 10_000

ConversationKind = Literal["planning", "chat"]
ConversationStatus = Literal["active", "closed", "archived"]


class ConversationCreate(BaseModel):
    """Inbound body for creating a follow-up chat conversation.

    Args:
        entry_artefact_id: Optional task-local artefact used as entry context.
    """

    model_config = ConfigDict(extra="forbid")

    entry_artefact_id: uuid.UUID | None = None


class ConversationUpdate(BaseModel):
    """Partial update for an existing chat conversation.

    Omitted fields remain unchanged. An explicitly null ``entry_artefact_id``
    clears its entry-context chip.

    Args:
        title: Replacement user-visible chat title.
        entry_artefact_id: Replacement task-local entry context, or null to clear it.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1)
    entry_artefact_id: uuid.UUID | None = None


class ConversationOut(BaseModel):
    """Durable public projection of one conversation.

    Args:
        id: Conversation identity.
        task_id: Owning task identity.
        kind: Whether this is a planning conversation or a follow-up chat.
        title: User-visible conversation title.
        status: Current conversation lifecycle status.
        entry_artefact_id: Optional task-local entry-context artefact.
        created_at: When the conversation was created.
        closed_at: When it closed, if applicable.
        archived_at: When it was archived, if applicable.
    """

    id: uuid.UUID
    task_id: uuid.UUID
    kind: ConversationKind
    title: str
    status: ConversationStatus
    entry_artefact_id: uuid.UUID | None
    created_at: datetime
    closed_at: datetime | None
    archived_at: datetime | None


class LatestTurnPreviewOut(BaseModel):
    """The most recent durable turn rendered in a conversations-library row.

    Args:
        user_message: Bounded user-message preview.
        reply_snippet: Bounded reply preview, absent for an unfinished turn.
        at: Turn completion time, absent for an unfinished turn.
    """

    user_message: str
    reply_snippet: str | None
    at: datetime | None


class ConversationListItemOut(ConversationOut):
    """A conversation plus its latest cross-kind turn preview.

    Args:
        latest_turn_preview: Most recent chat or planning turn, when one exists.
    """

    latest_turn_preview: LatestTurnPreviewOut | None


class ChatTurnCreate(BaseModel):
    """One idempotent question submitted to an active chat conversation."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=CHAT_MESSAGE_MAX)
    client_turn_id: uuid.UUID


class ChatTurnOut(BaseModel):
    """Durable public projection of one chat turn."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    turn_index: int
    client_turn_id: uuid.UUID
    user_message: str
    answer: str | None
    status: Literal["pending", "completed", "failed", "cancelled"]
    created_at: datetime
    completed_at: datetime | None
    claims: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    enrichment: dict[str, Any] | None = None
    warning_not_evidence_checked: bool = False
    handoff: Literal["evidence_not_held"] | None = None
    stopped_before_evidence_check: bool = False


class ProgressEvent(BaseModel):
    """A user-facing read-tool activity emitted before that tool runs."""

    type: Literal["progress"] = "progress"
    label: str


class DeltaEvent(BaseModel):
    """A provider-neutral prose fragment."""

    type: Literal["delta"] = "delta"
    text: str


class CompletedEvent(BaseModel):
    """The one successful terminal stream event."""

    type: Literal["completed"] = "completed"
    turn: ChatTurnOut


class FailedEventError(BaseModel):
    """Publicly safe post-header failure information."""

    code: str
    message: str


class FailedEvent(BaseModel):
    """The one failed terminal stream event."""

    type: Literal["failed"] = "failed"
    error: FailedEventError
    turn_id: uuid.UUID


class CancelledEvent(BaseModel):
    """The one cancelled terminal stream event, retaining partial prose."""

    type: Literal["cancelled"] = "cancelled"
    turn: ChatTurnOut


ChatStreamEvent = Annotated[
    ProgressEvent | DeltaEvent | CompletedEvent | FailedEvent | CancelledEvent,
    Field(discriminator="type"),
]


class CancelTurnOut(BaseModel):
    """The honest durable status observed after a cancel attempt."""

    status: Literal["pending", "completed", "failed", "cancelled"]
