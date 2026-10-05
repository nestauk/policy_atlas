"""Best-effort, process-local liveness notes for active tasks.

This module intentionally depends only on the standard library: execution
surfaces may publish activity notes without depending on FastAPI or transport
code. Durable state remains in ``event_log``; these notes are lossy by design.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Tick:
    """One ephemeral progress note delivered to a task's live subscribers."""

    stage: str | None
    note: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class _Subscriber:
    """One queue and its owning event loop."""

    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[Tick]


class TickHub:
    """Asyncio-safe, bounded, drop-oldest task tick fan-out."""

    def __init__(self, *, queue_size: int = 32) -> None:
        """Create a hub with the requested per-subscriber queue bound."""
        self._queue_size = queue_size
        self._subscribers: defaultdict[uuid.UUID, set[_Subscriber]] = defaultdict(set)

    async def subscribe(self, task_id: uuid.UUID) -> asyncio.Queue[Tick]:
        """Register and return a bounded queue for one task's ticks."""
        queue: asyncio.Queue[Tick] = asyncio.Queue(maxsize=self._queue_size)
        subscriber = _Subscriber(asyncio.get_running_loop(), queue)
        self._subscribers[task_id].add(subscriber)
        return queue

    async def unsubscribe(self, task_id: uuid.UUID, queue: asyncio.Queue[Tick]) -> None:
        """Remove a queue previously returned by :meth:`subscribe`."""
        subscribers = self._subscribers.get(task_id)
        if subscribers is None:
            return
        for subscriber in tuple(subscribers):
            if subscriber.queue is queue:
                subscribers.remove(subscriber)
        if not subscribers:
            self._subscribers.pop(task_id, None)

    def publish(self, task_id: uuid.UUID, *, stage: str | None, note: str) -> None:
        """Best-effort fan-out without blocking the publishing worker thread."""
        tick = Tick(stage=stage, note=note, occurred_at=datetime.now(UTC))
        for subscriber in tuple(self._subscribers.get(task_id, ())):
            try:
                subscriber.loop.call_soon_threadsafe(_offer, subscriber.queue, tick)
            except RuntimeError:
                # A closing loop is indistinguishable from a disconnected client.
                continue


def _offer(queue: asyncio.Queue[Tick], tick: Tick) -> None:
    """Place one tick without waiting, evicting the oldest one when full."""
    try:
        queue.put_nowait(tick)
    except asyncio.QueueFull:
        with suppress(asyncio.QueueEmpty):
            queue.get_nowait()
        queue.put_nowait(tick)


_task_id: ContextVar[uuid.UUID | None] = ContextVar("liveness_task_id", default=None)
tick_hub = TickHub()


@contextmanager
def task_liveness(task_id: uuid.UUID) -> Iterator[None]:
    """Bind a task identity while its component code emits liveness notes."""
    token = _task_id.set(task_id)
    try:
        yield
    finally:
        _task_id.reset(token)


def publish_current_tick(*, stage: str | None, note: str) -> None:
    """Publish for the currently executing task, if one is bound."""
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish(task_id, stage=stage, note=note)
