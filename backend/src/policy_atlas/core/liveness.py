"""Live activity for running tasks, kept in this process's memory only (task 058).

While a task's run is working, the stage loops, the model-call wrapper and the
report writer publish short-lived messages here: an activity line ("tick") per
stage, and the report section's text as it streams. The hub hands each message
to every browser connection (a "subscriber") watching that task, and remembers
just enough to greet a newly connected browser with where things stand: the
last tick per stage and the section text written so far (task 058, N4).
While a section is written the hub also passes on the sources the writer has
just read and, as each of the writer's citations closes, the stretch of text it
marks; it remembers both beside the section text, so a newly connected browser
sees them too (task 058, "evidence shown live", owner 2026-11-05). The
case-study cards are passed on the same way, each as it closes (task 058,
round 7). After the sections, each most-relevant-source note is passed on as
it is written; the hub keeps the run's notes for a newly connected browser
until the run ends (task 058, round 8). While the search runs, each query is
passed on as it goes out and again when it comes back, and after the
characterise stage finds its themes, their names are passed on before the
sources are assigned to them; the hub keeps both for a newly connected
browser until the run ends (task 058, round 9).

Nothing here is saved to the database. The durable record stays in
``event_log``; these messages may be lost (a full queue drops its oldest
message, a restart forgets everything) and that is by design.

Three things keep the stream calm and alive:

* Coalescing: at most one tick per task and stage every
  :data:`COALESCE_SECONDS`; quicker ticks are held and the latest one is sent
  when the window closes (task 058, N1).
* Heartbeats: while a model call is open, the stage's last tick is repeated
  every :data:`HEARTBEAT_SECONDS`, so a long call still shows signs of life.
* Delta merging: streamed section text that arrives within
  :data:`DELTA_COALESCE_SECONDS` is sent as one message.

This module uses the standard library only, so any part of the code base can
publish without depending on the web layer.
"""

from __future__ import annotations

import asyncio
import dataclasses
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Literal

#: At most one tick per task per stage in this many seconds.
COALESCE_SECONDS = 0.5
#: Consecutive appended section text for one task merges within this many seconds.
DELTA_COALESCE_SECONDS = 0.1
#: While a model call is open, the current tick is repeated this often (seconds).
HEARTBEAT_SECONDS = 10.0
#: Remembered ticks and the section draft are forgotten this long after their last update.
MEMORY_TTL_SECONDS = 600.0
#: The remembered section draft keeps at most this many characters (the stream is not cut).
DRAFT_MAX_CHARS = 20_000

type TickSource = Literal["loop", "hook"]
#: One source as the page names it: ``(source_id, title)``.
type SourceRef = tuple[str, str]
type DeltaMode = Literal["append", "replace"]
type Schedule = Callable[[float, Callable[[], None]], None]


@dataclass(frozen=True, slots=True)
class Tick:
    """One activity line for one stage of a running task.

    Attributes:
        stage: Public stage key the line belongs to, or ``None``.
        activity: The plain-words line the client shows.
        occurred_at: When the line was published (or, for a heartbeat, repeated).
        done: Items finished so far, or ``None`` when there is no honest count.
        total: Items in all, or ``None`` when unknown.
        unit: What is being counted ("documents", "batches", ...), or ``None``.
        section: The report section being written, or ``None`` outside writing.
        heartbeat: ``True`` when this is a repeat sent while a model call is open.
        dropped: How many messages for this task had been dropped from full
            subscriber queues when this tick was sent.
    """

    stage: str | None
    activity: str
    occurred_at: datetime
    done: int | None = None
    total: int | None = None
    unit: str | None = None
    section: str | None = None
    heartbeat: bool = False
    dropped: int = 0


@dataclass(frozen=True, slots=True)
class SectionDelta:
    """A piece of a report section's text while it streams.

    Attributes:
        index: The section's position in the report.
        text: The new text.
        mode: ``"append"`` adds ``text`` to the section's draft; ``"replace"``
            makes ``text`` the whole draft.
        occurred_at: When the message was sent.
    """

    index: int
    text: str
    mode: DeltaMode
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SectionRevising:
    """Character ranges of a section draft that the writer is rewriting.

    Attributes:
        index: The section's position in the report.
        spans: ``(start, end)`` character ranges in the draft.
        occurred_at: When the message was sent.
    """

    index: int
    spans: tuple[tuple[int, int], ...]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SectionSources:
    """The sources the writer has read so far for the section being written.

    Each message carries the whole set (it replaces the one before), in the
    order the sources were first read, each source once.

    Attributes:
        index: The section's position in the report.
        sources: ``(source_id, title)`` pairs.
        occurred_at: When the message was sent.
    """

    index: int
    sources: tuple[SourceRef, ...]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SectionClaim:
    """One of the writer's citations, bound to its stretch of the section draft.

    Display-only: the claim is still to be checked; the completed section
    brings the checked citations.

    Attributes:
        index: The section's position in the report.
        start: First character of the cited text in the draft.
        end: One past its last character (the same counting as
            :class:`SectionRevising`).
        sources: ``(source_id, title)`` pairs for the sources it cites.
        occurred_at: When the message was sent.
    """

    index: int
    start: int
    end: int
    sources: tuple[SourceRef, ...]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SectionCard:
    """One case-study card as it closes in the streamed reply (task 058, round 7).

    Display-only: the card is still to be checked; the completed section
    brings the checked cards.

    Attributes:
        index: The section's position in the report.
        title: The card's title.
        prose: The card's text.
        occurred_at: When the message was sent.
    """

    index: int
    title: str
    prose: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SourceNote:
    """One most-relevant-source note, as soon as it is written (task 058, round 8).

    Display-only: the saved report brings the notes it keeps.

    Attributes:
        source_id: The source's id in this task.
        title: The source's title as the saved report's references name it.
        note: The note's text.
        occurred_at: When the message was sent.
    """

    source_id: str
    title: str
    note: str
    occurred_at: datetime


#: What a search query is: a written topic query, a meaning-based
#: (semantic) query, a pass following citations, or a pass looking up works
#: by id (task 058, round 9).
type SearchQueryKind = Literal["topic", "semantic", "citations", "lookup"]


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """One search query as it goes out, and again when it comes back (task 058, round 9).

    Display-only: the saved search record lists the queries after the stage.

    Attributes:
        backend: The database searched (``"openalex"`` or ``"overton"``).
        query: The query text for a topic or semantic query; a short
            description for a citations or lookup pass (never the ids).
        kind: ``"topic"``, ``"semantic"``, ``"citations"`` or ``"lookup"``.
        results: ``None`` while the query is out; the number of records it
            returned once it is back.
        occurred_at: When the message was sent.
    """

    backend: str
    query: str
    kind: SearchQueryKind
    results: int | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ThemesFound:
    """The characterise stage's themes, found before sources are assigned to them (round 9).

    Display-only: the saved characterisation brings the themes with their
    document counts.

    Attributes:
        themes: ``(label, description)`` pairs in the order found; the
            description may be ``None``.
        occurred_at: When the message was sent.
    """

    themes: tuple[tuple[str, str | None], ...]
    occurred_at: datetime


type HubMessage = (
    Tick
    | SectionDelta
    | SectionRevising
    | SectionSources
    | SectionClaim
    | SectionCard
    | SourceNote
    | SearchQuery
    | ThemesFound
)


@dataclass(frozen=True, slots=True)
class _Subscriber:
    """One queue and the event loop that owns it."""

    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[HubMessage]


@dataclass(slots=True)
class _StageMemory:
    """What the hub keeps for one task and stage."""

    last: Tick | None = None
    last_source: TickSource = "loop"
    last_emit: float | None = None
    updated_at: float = 0.0
    pending: Tick | None = None
    pending_source: TickSource = "loop"
    pending_due: float = 0.0
    flush_scheduled: bool = False
    open_calls: int = 0


@dataclass(slots=True)
class _Draft:
    """The section being written: its text, sources read, citations bound and cards."""

    index: int
    text: str
    updated_at: float
    sources: tuple[SourceRef, ...] = ()
    claims: list[SectionClaim] = field(default_factory=list)
    cards: list[SectionCard] = field(default_factory=list)


@dataclass(slots=True)
class _PendingDelta:
    """Appended section text waiting to be sent as one message."""

    index: int
    text: str
    due: float
    flush_scheduled: bool = False


@dataclass(slots=True)
class _TaskMemory:
    """Everything the hub keeps for one task."""

    run_id: uuid.UUID | None = None
    stages: dict[str | None, _StageMemory] = field(default_factory=dict)
    draft: _Draft | None = None
    pending_delta: _PendingDelta | None = None
    #: The run's source notes so far, in the order written (round 8).
    source_notes: list[SourceNote] = field(default_factory=list)
    source_notes_at: float = 0.0
    #: The run's search queries so far, keyed by (backend, query, kind), in
    #: the order first sent; each holds its latest message (round 9).
    search_queries: dict[tuple[str, str, str], SearchQuery] = field(default_factory=dict)
    search_queries_at: float = 0.0
    #: The characterise stage's themes, once found (round 9).
    themes: ThemesFound | None = None
    themes_at: float = 0.0

    def keeps_run_lists(self) -> bool:
        """Whether the run's source notes, search queries or themes are remembered."""
        return bool(self.source_notes or self.search_queries or self.themes is not None)


def _now_utc() -> datetime:
    return datetime.now(UTC)


class TickHub:
    """Fans live messages out to each task's subscribers and remembers the latest state.

    Publishers call from worker threads; subscribers are asyncio queues on their
    own event loops. One lock guards all state, and messages reach a queue
    through its loop's ``call_soon_threadsafe``. A full queue drops its oldest
    message and the task's dropped counter goes up.
    """

    def __init__(
        self,
        *,
        queue_size: int = 32,
        clock: Callable[[], float] = time.monotonic,
        schedule: Schedule | None = None,
    ) -> None:
        """Create an empty hub.

        Args:
            queue_size: How many messages each subscriber queue holds.
            clock: A steady clock in seconds, used for coalescing, heartbeats
                and forgetting old state. Tests pass a fake one.
            schedule: ``schedule(delay_s, fn)`` arranges one later call of
                ``fn``. With ``None`` nothing is arranged and the caller runs
                :meth:`flush` and :meth:`sweep` itself (tests do this).
        """
        self._queue_size = queue_size
        self._clock = clock
        self._schedule = schedule
        self._lock = threading.Lock()
        self._subscribers: dict[uuid.UUID, list[_Subscriber]] = {}
        self._tasks: dict[uuid.UUID, _TaskMemory] = {}
        self._dropped: dict[uuid.UUID, int] = {}
        self._sweep_scheduled = False

    # Subscribers ---------------------------------------------------------

    async def subscribe(self, task_id: uuid.UUID) -> asyncio.Queue[HubMessage]:
        """Register and return a bounded queue for one task's messages.

        Args:
            task_id: The task to follow.

        Returns:
            The queue new messages arrive on.
        """
        queue: asyncio.Queue[HubMessage] = asyncio.Queue(maxsize=self._queue_size)
        subscriber = _Subscriber(asyncio.get_running_loop(), queue)
        with self._lock:
            self._subscribers.setdefault(task_id, []).append(subscriber)
        return queue

    async def subscribe_with_snapshot(
        self, task_id: uuid.UUID
    ) -> tuple[asyncio.Queue[HubMessage], list[HubMessage]]:
        """Register a queue and return the task's remembered state in one step.

        Both happen under the hub's lock, so a message published at the same
        moment lands either in the returned state or in the queue, never both
        and never neither (task 058, P6).

        Args:
            task_id: The task to follow.

        Returns:
            The queue, and the remembered state: the run's search queries
            so far (each in its latest state, in the order first sent) and
            its themes once found; then the last tick of each stage (in the
            order the stages first appeared), then, if a section is being
            written, one ``replace`` delta carrying its text so far (when
            there is any), the sources read so far (when there are any),
            each citation bound so far and each case-study card closed so
            far; then the run's source notes so far, in order.
        """
        queue: asyncio.Queue[HubMessage] = asyncio.Queue(maxsize=self._queue_size)
        subscriber = _Subscriber(asyncio.get_running_loop(), queue)
        with self._lock:
            now = self._clock()
            memory = self._tasks.get(task_id)
            if memory is not None and memory.pending_delta is not None:
                # The draft already holds the held text; send it to the
                # existing subscribers now so the newcomer does not get it twice.
                self._emit_pending_delta(task_id, memory)
            self._subscribers.setdefault(task_id, []).append(subscriber)
            snapshot: list[HubMessage] = []
            if memory is not None:
                if (
                    memory.search_queries
                    and now - memory.search_queries_at < MEMORY_TTL_SECONDS
                ):
                    snapshot.extend(memory.search_queries.values())
                if memory.themes is not None and now - memory.themes_at < MEMORY_TTL_SECONDS:
                    snapshot.append(memory.themes)
                for stage_memory in memory.stages.values():
                    last = stage_memory.last
                    if last is None or now - stage_memory.updated_at >= MEMORY_TTL_SECONDS:
                        continue
                    snapshot.append(dataclasses.replace(last, heartbeat=False))
                draft = memory.draft
                if draft is not None and now - draft.updated_at < MEMORY_TTL_SECONDS:
                    if draft.text:
                        snapshot.append(
                            SectionDelta(
                                index=draft.index,
                                text=draft.text,
                                mode="replace",
                                occurred_at=_now_utc(),
                            )
                        )
                    if draft.sources:
                        snapshot.append(
                            SectionSources(
                                index=draft.index,
                                sources=draft.sources,
                                occurred_at=_now_utc(),
                            )
                        )
                    snapshot.extend(draft.claims)
                    snapshot.extend(draft.cards)
                if (
                    memory.source_notes
                    and now - memory.source_notes_at < MEMORY_TTL_SECONDS
                ):
                    snapshot.extend(memory.source_notes)
        return queue, snapshot

    async def unsubscribe(self, task_id: uuid.UUID, queue: asyncio.Queue[HubMessage]) -> None:
        """Remove a queue returned by :meth:`subscribe` or :meth:`subscribe_with_snapshot`.

        Args:
            task_id: The task the queue follows.
            queue: The queue to remove.
        """
        with self._lock:
            subscribers = self._subscribers.get(task_id)
            if subscribers is None:
                return
            subscribers[:] = [s for s in subscribers if s.queue is not queue]
            if not subscribers:
                del self._subscribers[task_id]

    def dropped(self, task_id: uuid.UUID) -> int:
        """Return how many of the task's messages full queues have dropped.

        Args:
            task_id: The task.

        Returns:
            The count since the task's current run began.
        """
        with self._lock:
            return self._dropped.get(task_id, 0)

    # Ticks ---------------------------------------------------------------

    def publish_tick(
        self,
        task_id: uuid.UUID,
        *,
        stage: str | None,
        activity: str,
        done: int | None = None,
        total: int | None = None,
        unit: str | None = None,
        section: str | None = None,
        source: TickSource = "loop",
    ) -> None:
        """Publish one activity line, coalesced per task and stage.

        The first tick in a :data:`COALESCE_SECONDS` window is sent at once;
        later ones in the window are held, each replacing the one before, and
        the latest is sent when the window closes. A tick from the model-call
        wrapper (``source="hook"``) never replaces a stage loop's own tick
        (``source="loop"``); a loop tick always replaces a hook tick.

        Args:
            task_id: The task.
            stage: Public stage key, or ``None``.
            activity: The plain-words line.
            done: Items finished so far, or ``None``.
            total: Items in all, or ``None``.
            unit: What is counted, or ``None``.
            section: The section being written, or ``None``.
            source: ``"loop"`` for a stage loop's line, ``"hook"`` for the
                model-call wrapper's verb.
        """
        tick = Tick(
            stage=stage,
            activity=activity,
            occurred_at=_now_utc(),
            done=done,
            total=total,
            unit=unit,
            section=section,
        )
        with self._lock:
            now = self._clock()
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            entry = memory.stages.setdefault(stage, _StageMemory())
            if source == "hook":
                current_source = (
                    entry.pending_source
                    if entry.pending is not None
                    else (entry.last_source if entry.last is not None else None)
                )
                if current_source == "loop":
                    return
            if entry.last_emit is None or now - entry.last_emit >= COALESCE_SECONDS:
                entry.pending = None
                self._emit_tick(task_id, entry, tick, source, now)
                return
            entry.pending = tick
            entry.pending_source = source
            entry.pending_due = entry.last_emit + COALESCE_SECONDS
            entry.updated_at = now
            if not entry.flush_scheduled and self._schedule is not None:
                entry.flush_scheduled = True
                self._schedule(
                    max(entry.pending_due - now, 0.0),
                    partial(self._timer_flush_stage, task_id, stage),
                )

    def call_opened(self, task_id: uuid.UUID, stage: str) -> None:
        """Mark a model call as open for the task and stage (heartbeats start).

        Args:
            task_id: The task.
            stage: Public stage key.
        """
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.stages.setdefault(stage, _StageMemory()).open_calls += 1
            self._schedule_sweep()

    def call_closed(self, task_id: uuid.UUID, stage: str) -> None:
        """Mark a model call as closed for the task and stage.

        Args:
            task_id: The task.
            stage: Public stage key.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            entry = memory.stages.get(stage) if memory is not None else None
            if entry is not None and entry.open_calls > 0:
                entry.open_calls -= 1

    # Section text --------------------------------------------------------

    def publish_delta(
        self,
        task_id: uuid.UUID,
        *,
        index: int,
        text: str,
        mode: DeltaMode = "append",
    ) -> None:
        """Publish a piece of a section's streamed text and remember the draft.

        A ``replace`` is sent at once (after any held append). Appends within
        :data:`DELTA_COALESCE_SECONDS` of the first held one are merged into a
        single message. The remembered draft is capped at
        :data:`DRAFT_MAX_CHARS`; the messages themselves are not cut.

        Args:
            task_id: The task.
            index: The section's position in the report.
            text: The text.
            mode: ``"append"`` or ``"replace"``.
        """
        with self._lock:
            now = self._clock()
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            if mode == "replace":
                self._emit_pending_delta(task_id, memory)
                kept = memory.draft
                # The sources read stay; citations bound to the old text and
                # cards from the old reply go.
                memory.draft = _Draft(
                    index,
                    text[:DRAFT_MAX_CHARS],
                    now,
                    sources=kept.sources if kept is not None and kept.index == index else (),
                )
                self._fan_out(
                    task_id,
                    SectionDelta(index=index, text=text, mode="replace", occurred_at=_now_utc()),
                )
                return
            draft = memory.draft
            if draft is None or draft.index != index:
                draft = memory.draft = _Draft(index, "", now)
            draft.text = (draft.text + text)[:DRAFT_MAX_CHARS]
            draft.updated_at = now
            pending = memory.pending_delta
            if pending is not None and pending.index != index:
                self._emit_pending_delta(task_id, memory)
                pending = None
            if pending is not None:
                pending.text += text
                if now >= pending.due:
                    self._emit_pending_delta(task_id, memory)
                return
            pending = memory.pending_delta = _PendingDelta(
                index, text, now + DELTA_COALESCE_SECONDS
            )
            if self._schedule is not None:
                pending.flush_scheduled = True
                self._schedule(DELTA_COALESCE_SECONDS, partial(self._timer_flush_delta, task_id))

    def publish_revising(
        self, task_id: uuid.UUID, *, index: int, spans: Sequence[tuple[int, int]]
    ) -> None:
        """Send the ranges of a section draft being rewritten (not remembered).

        Any held append is sent first, so the ranges refer to text the
        client already has.

        Args:
            task_id: The task.
            index: The section's position in the report.
            spans: ``(start, end)`` character ranges in the draft.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            if memory is not None:
                self._emit_pending_delta(task_id, memory)
            self._fan_out(
                task_id,
                SectionRevising(
                    index=index,
                    spans=tuple((start, end) for start, end in spans),
                    occurred_at=_now_utc(),
                ),
            )

    def publish_sources(
        self, task_id: uuid.UUID, *, index: int, sources: Sequence[SourceRef]
    ) -> None:
        """Add the sources one read returned to the section's set and send the whole set.

        A source already in the set keeps its place; new ones join at the
        end. Nothing is sent when the read added nothing new.

        Args:
            task_id: The task.
            index: The section's position in the report.
            sources: ``(source_id, title)`` pairs from one read, in order.
        """
        with self._lock:
            now = self._clock()
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            draft = memory.draft
            if draft is None or draft.index != index:
                self._emit_pending_delta(task_id, memory)
                draft = memory.draft = _Draft(index, "", now)
            seen = {source_id for source_id, _title in draft.sources}
            added: list[SourceRef] = []
            for source_id, title in sources:
                if source_id in seen:
                    continue
                seen.add(source_id)
                added.append((source_id, title))
            draft.updated_at = now
            if not added:
                return
            draft.sources = (*draft.sources, *added)
            self._fan_out(
                task_id,
                SectionSources(index=index, sources=draft.sources, occurred_at=_now_utc()),
            )

    def publish_claim(
        self,
        task_id: uuid.UUID,
        *,
        index: int,
        start: int,
        end: int,
        sources: Sequence[SourceRef],
    ) -> None:
        """Send one citation bound to the draft, and remember it for a reconnect.

        Any held append is sent first, so the range refers to text the
        client already has.

        Args:
            task_id: The task.
            index: The section's position in the report.
            start: First character of the cited text in the draft.
            end: One past its last character.
            sources: ``(source_id, title)`` pairs it cites.
        """
        claim = SectionClaim(
            index=index,
            start=start,
            end=end,
            sources=tuple(sources),
            occurred_at=_now_utc(),
        )
        with self._lock:
            now = self._clock()
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            self._emit_pending_delta(task_id, memory)
            draft = memory.draft
            if draft is None or draft.index != index:
                draft = memory.draft = _Draft(index, "", now)
            draft.claims.append(claim)
            draft.updated_at = now
            self._fan_out(task_id, claim)

    def publish_card(
        self, task_id: uuid.UUID, *, index: int, title: str, prose: str
    ) -> None:
        """Send one case-study card, and remember it beside the draft for a reconnect.

        Args:
            task_id: The task.
            index: The section's position in the report.
            title: The card's title.
            prose: The card's text.
        """
        card = SectionCard(index=index, title=title, prose=prose, occurred_at=_now_utc())
        with self._lock:
            now = self._clock()
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            draft = memory.draft
            if draft is None or draft.index != index:
                self._emit_pending_delta(task_id, memory)
                draft = memory.draft = _Draft(index, "", now)
            draft.cards.append(card)
            draft.updated_at = now
            self._fan_out(task_id, card)

    def publish_source_note(
        self, task_id: uuid.UUID, *, source_id: str, title: str, note: str
    ) -> None:
        """Send one source note, and remember it for a reconnect until the run ends.

        Args:
            task_id: The task.
            source_id: The source's id in this task.
            title: The source's title.
            note: The note's text.
        """
        message = SourceNote(
            source_id=source_id, title=title, note=note, occurred_at=_now_utc()
        )
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.source_notes.append(message)
            memory.source_notes_at = self._clock()
            self._fan_out(task_id, message)

    def publish_search_query(
        self,
        task_id: uuid.UUID,
        *,
        backend: str,
        query: str,
        kind: SearchQueryKind,
        results: int | None,
    ) -> None:
        """Send one search query's state, and remember it for a reconnect until the run ends.

        A query is keyed by ``(backend, query, kind)``: the message sent when
        it comes back replaces the one sent when it went out.

        Args:
            task_id: The task.
            backend: The database searched.
            query: The query text, or a short description of an id pass.
            kind: What the query is.
            results: ``None`` while out; the records returned once back.
        """
        message = SearchQuery(
            backend=backend, query=query, kind=kind, results=results, occurred_at=_now_utc()
        )
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.search_queries[(backend, query, kind)] = message
            memory.search_queries_at = self._clock()
            self._fan_out(task_id, message)

    def publish_themes(
        self, task_id: uuid.UUID, *, themes: Sequence[tuple[str, str | None]]
    ) -> None:
        """Send the themes found, and remember them for a reconnect until the run ends.

        Args:
            task_id: The task.
            themes: ``(label, description)`` pairs in the order found.
        """
        message = ThemesFound(themes=tuple(themes), occurred_at=_now_utc())
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.themes = message
            memory.themes_at = self._clock()
            self._fan_out(task_id, message)

    def clear_draft(self, task_id: uuid.UUID) -> None:
        """Forget the section draft, its sources, citations and cards, and any held append.

        Called when a section has finished.

        Args:
            task_id: The task.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            if memory is not None:
                # A held append still goes out: the client's draft then holds
                # every word the writer streamed before the completed section
                # replaces it (task 058, N7).
                if memory.pending_delta is not None:
                    self._emit_pending_delta(task_id, memory)
                memory.draft = None
                memory.pending_delta = None
                self._forget_if_empty(task_id, memory)

    # Runs and stages -----------------------------------------------------

    def begin_run(
        self,
        task_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        parent_run_id: uuid.UUID | None = None,
    ) -> None:
        """Start a fresh memory for a task's new top-level run.

        A top-level run forgets everything the task's earlier run left
        (ticks, held ticks, open calls, draft, held text, source notes,
        search queries, themes, dropped count). A
        child run (one with a parent) changes nothing, so a parent's and its
        children's activity never wipe each other out.

        Args:
            task_id: The task.
            run_id: The run starting.
            parent_run_id: The parent run, for a child run.
        """
        if parent_run_id is not None:
            return
        with self._lock:
            self._tasks[task_id] = _TaskMemory(run_id=run_id)
            self._dropped.pop(task_id, None)

    def end_run(self, task_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """Forget the task's memory when its current top-level run ends.

        A run that is not the task's current one (a child) changes nothing.

        Args:
            task_id: The task.
            run_id: The run ending.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            if memory is None or memory.run_id != run_id:
                return
            del self._tasks[task_id]
            self._dropped.pop(task_id, None)

    def end_stage(self, task_id: uuid.UUID, stage: str) -> None:
        """Forget one stage's tick, held tick and open calls.

        Ending ``synthesise`` also forgets the section draft (with its sources,
        citations and cards) and held text.

        Args:
            task_id: The task.
            stage: Public stage key.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            if memory is None:
                return
            memory.stages.pop(stage, None)
            if stage == "synthesise":
                memory.draft = None
                memory.pending_delta = None
            self._forget_if_empty(task_id, memory)

    # Timed work ----------------------------------------------------------

    def flush(self) -> None:
        """Send every held tick and held text whose time has come."""
        with self._lock:
            now = self._clock()
            for task_id, memory in list(self._tasks.items()):
                for stage, entry in list(memory.stages.items()):
                    if entry.pending is None:
                        continue
                    if now >= entry.pending_due:
                        self._emit_held_tick(task_id, entry, now)
                    elif not entry.flush_scheduled and self._schedule is not None:
                        entry.flush_scheduled = True
                        self._schedule(
                            entry.pending_due - now,
                            partial(self._timer_flush_stage, task_id, stage),
                        )
                pending = memory.pending_delta
                if pending is None:
                    continue
                if now >= pending.due:
                    self._emit_pending_delta(task_id, memory)
                elif not pending.flush_scheduled and self._schedule is not None:
                    pending.flush_scheduled = True
                    self._schedule(pending.due - now, partial(self._timer_flush_delta, task_id))

    def sweep(self) -> None:
        """Send heartbeats for open model calls, then forget stale memory.

        A stage with an open model call whose last tick went out at least
        :data:`HEARTBEAT_SECONDS` ago gets that tick again with
        ``heartbeat=True``. Ticks, drafts, source notes, search queries and
        themes not updated for
        :data:`MEMORY_TTL_SECONDS` are forgotten. While any call is open,
        another sweep is arranged.
        """
        with self._lock:
            now = self._clock()
            for task_id, memory in list(self._tasks.items()):
                for stage, entry in list(memory.stages.items()):
                    if (
                        entry.open_calls > 0
                        and entry.last is not None
                        and entry.last_emit is not None
                        and now - entry.last_emit >= HEARTBEAT_SECONDS
                    ):
                        self._fan_out(
                            task_id,
                            dataclasses.replace(
                                entry.last,
                                heartbeat=True,
                                occurred_at=_now_utc(),
                                dropped=self._dropped.get(task_id, 0),
                            ),
                        )
                        entry.last_emit = now
                    if entry.last is not None and now - entry.updated_at >= MEMORY_TTL_SECONDS:
                        entry.last = None
                    if entry.last is None and entry.pending is None and entry.open_calls == 0:
                        del memory.stages[stage]
                draft = memory.draft
                if draft is not None and now - draft.updated_at >= MEMORY_TTL_SECONDS:
                    memory.draft = None
                if (
                    memory.source_notes
                    and now - memory.source_notes_at >= MEMORY_TTL_SECONDS
                ):
                    memory.source_notes = []
                if (
                    memory.search_queries
                    and now - memory.search_queries_at >= MEMORY_TTL_SECONDS
                ):
                    memory.search_queries = {}
                if memory.themes is not None and now - memory.themes_at >= MEMORY_TTL_SECONDS:
                    memory.themes = None
                if (
                    not memory.stages
                    and memory.draft is None
                    and memory.pending_delta is None
                    and not memory.keeps_run_lists()
                ):
                    # Nothing left to remember: drop the task (and its run id) for good.
                    del self._tasks[task_id]
            self._schedule_sweep()

    # Internals (the caller holds the lock) -------------------------------

    def _emit_tick(
        self,
        task_id: uuid.UUID,
        entry: _StageMemory,
        tick: Tick,
        source: TickSource,
        now: float,
    ) -> None:
        tick = dataclasses.replace(tick, dropped=self._dropped.get(task_id, 0))
        entry.last = tick
        entry.last_source = source
        entry.last_emit = now
        entry.updated_at = now
        self._fan_out(task_id, tick)

    def _emit_held_tick(self, task_id: uuid.UUID, entry: _StageMemory, now: float) -> None:
        held = entry.pending
        if held is None:
            return
        entry.pending = None
        self._emit_tick(task_id, entry, held, entry.pending_source, now)

    def _emit_pending_delta(self, task_id: uuid.UUID, memory: _TaskMemory) -> None:
        pending = memory.pending_delta
        if pending is None:
            return
        memory.pending_delta = None
        self._fan_out(
            task_id,
            SectionDelta(
                index=pending.index, text=pending.text, mode="append", occurred_at=_now_utc()
            ),
        )

    def _fan_out(self, task_id: uuid.UUID, message: HubMessage) -> None:
        for subscriber in self._subscribers.get(task_id, ()):
            try:
                subscriber.loop.call_soon_threadsafe(
                    self._offer, task_id, subscriber.queue, message
                )
            except RuntimeError:
                # A closed loop is a disconnected client.
                continue

    def _offer(
        self, task_id: uuid.UUID, queue: asyncio.Queue[HubMessage], message: HubMessage
    ) -> None:
        """Place one message without waiting, dropping the oldest when full (loop thread)."""
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
            queue.put_nowait(message)
            with self._lock:
                self._dropped[task_id] = self._dropped.get(task_id, 0) + 1

    def _schedule_sweep(self) -> None:
        if self._schedule is None or self._sweep_scheduled:
            return
        if not any(
            entry.open_calls > 0
            for memory in self._tasks.values()
            for entry in memory.stages.values()
        ):
            return
        self._sweep_scheduled = True
        self._schedule(HEARTBEAT_SECONDS, self._timer_sweep)

    def _forget_if_empty(self, task_id: uuid.UUID, memory: _TaskMemory) -> None:
        # Keep the memory while its run is current, so the run's end still matches.
        if (
            not memory.stages
            and memory.draft is None
            and memory.pending_delta is None
            and not memory.keeps_run_lists()
            and memory.run_id is None
        ):
            self._tasks.pop(task_id, None)

    # Timer callbacks (run on a timer thread) -----------------------------

    def _timer_flush_stage(self, task_id: uuid.UUID, stage: str | None) -> None:
        with self._lock:
            memory = self._tasks.get(task_id)
            entry = memory.stages.get(stage) if memory is not None else None
            if entry is not None:
                entry.flush_scheduled = False
        self.flush()

    def _timer_flush_delta(self, task_id: uuid.UUID) -> None:
        with self._lock:
            memory = self._tasks.get(task_id)
            if memory is not None and memory.pending_delta is not None:
                memory.pending_delta.flush_scheduled = False
        self.flush()

    def _timer_sweep(self) -> None:
        with self._lock:
            self._sweep_scheduled = False
        self.sweep()


def _timer_schedule(delay_s: float, fn: Callable[[], None]) -> None:
    """Call ``fn`` once after ``delay_s`` seconds on a background (daemon) timer thread."""
    timer = threading.Timer(max(delay_s, 0.0), fn)
    timer.daemon = True
    timer.start()


_task_id: ContextVar[uuid.UUID | None] = ContextVar("liveness_task_id", default=None)
_stage: ContextVar[str | None] = ContextVar("liveness_stage", default=None)
tick_hub = TickHub(schedule=_timer_schedule)


@contextmanager
def task_liveness(task_id: uuid.UUID, *, stage: str | None = None) -> Iterator[None]:
    """Bind the task (and the public stage key, when known) for the publishers below.

    Args:
        task_id: The task whose work runs inside the block.
        stage: The public stage key, when the block is one stage's work.

    Yields:
        Nothing; the binding lasts until the block exits.
    """
    task_token = _task_id.set(task_id)
    stage_token = _stage.set(stage)
    try:
        yield
    finally:
        _stage.reset(stage_token)
        _task_id.reset(task_token)


def current_task_id() -> uuid.UUID | None:
    """Return the task bound by :func:`task_liveness`, or ``None``."""
    return _task_id.get()


def current_stage() -> str | None:
    """Return the stage key bound by :func:`task_liveness`, or ``None``."""
    return _stage.get()


def publish_progress(
    *,
    activity: str,
    done: int | None = None,
    total: int | None = None,
    unit: str | None = None,
    section: str | None = None,
) -> None:
    """Publish a stage loop's own line for the bound task and stage.

    Does nothing when no task is bound.

    Args:
        activity: The plain-words line.
        done: Items finished so far, or ``None``.
        total: Items in all, or ``None``.
        unit: What is counted ("documents", "batches", ...), or ``None``.
        section: The section being written, or ``None``.
    """
    task_id = _task_id.get()
    if task_id is None:
        return
    tick_hub.publish_tick(
        task_id,
        stage=_stage.get(),
        activity=activity,
        done=done,
        total=total,
        unit=unit,
        section=section,
        source="loop",
    )


def publish_verb(activity: str) -> None:
    """Publish the model-call wrapper's verb for the bound task and stage.

    The verb never replaces a stage loop's own line. Does nothing when no task
    or no stage is bound.

    Args:
        activity: The verb line for the model step.
    """
    task_id = _task_id.get()
    stage = _stage.get()
    if task_id is None or stage is None:
        return
    tick_hub.publish_tick(task_id, stage=stage, activity=activity, source="hook")


def model_call_opened() -> None:
    """Mark a model call as open for the bound task and stage (no-op when unbound)."""
    task_id = _task_id.get()
    stage = _stage.get()
    if task_id is not None and stage is not None:
        tick_hub.call_opened(task_id, stage)


def model_call_closed() -> None:
    """Mark a model call as closed for the bound task and stage (no-op when unbound)."""
    task_id = _task_id.get()
    stage = _stage.get()
    if task_id is not None and stage is not None:
        tick_hub.call_closed(task_id, stage)


def publish_section_delta(index: int, text: str, *, mode: DeltaMode = "append") -> None:
    """Publish a piece of streamed section text for the bound task (no-op when unbound).

    Args:
        index: The section's position in the report.
        text: The text.
        mode: ``"append"`` or ``"replace"``.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_delta(task_id, index=index, text=text, mode=mode)


def publish_section_revising(index: int, spans: Sequence[tuple[int, int]]) -> None:
    """Publish the draft ranges being rewritten for the bound task (no-op when unbound).

    Args:
        index: The section's position in the report.
        spans: ``(start, end)`` character ranges in the draft.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_revising(task_id, index=index, spans=spans)


def publish_section_sources(index: int, sources: Sequence[SourceRef]) -> None:
    """Publish the sources one read returned for the bound task (no-op when unbound).

    Args:
        index: The section's position in the report.
        sources: ``(source_id, title)`` pairs, in the order the read returned them.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_sources(task_id, index=index, sources=sources)


def publish_section_claim(
    index: int, start: int, end: int, sources: Sequence[SourceRef]
) -> None:
    """Publish one citation bound to the draft for the bound task (no-op when unbound).

    Args:
        index: The section's position in the report.
        start: First character of the cited text in the draft.
        end: One past its last character.
        sources: ``(source_id, title)`` pairs it cites.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_claim(task_id, index=index, start=start, end=end, sources=sources)


def publish_section_card(index: int, title: str, prose: str) -> None:
    """Publish one case-study card for the bound task (no-op when unbound).

    Args:
        index: The section's position in the report.
        title: The card's title.
        prose: The card's text.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_card(task_id, index=index, title=title, prose=prose)


def publish_source_note(source_id: str, title: str, note: str) -> None:
    """Publish one most-relevant-source note for the bound task (no-op when unbound).

    Args:
        source_id: The source's id in this task.
        title: The source's title.
        note: The note's text.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_source_note(task_id, source_id=source_id, title=title, note=note)


def publish_search_query(
    backend: str, query: str, kind: SearchQueryKind, results: int | None
) -> None:
    """Publish one search query's state for the bound task (no-op when unbound).

    Args:
        backend: The database searched.
        query: The query text, or a short description of an id pass.
        kind: What the query is.
        results: ``None`` while out; the records returned once back.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_search_query(
            task_id, backend=backend, query=query, kind=kind, results=results
        )


def publish_themes(themes: Sequence[tuple[str, str | None]]) -> None:
    """Publish the themes found for the bound task (no-op when unbound).

    Args:
        themes: ``(label, description)`` pairs in the order found.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_themes(task_id, themes=themes)


def clear_section_draft() -> None:
    """Forget the bound task's section draft (a section has finished; no-op when unbound)."""
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.clear_draft(task_id)
