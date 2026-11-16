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
browser until the run ends (task 058, round 9). The longlist walk's two
clusterings pass on their names the same way: the options found while
sources are assigned to them, then the themes found while options are
(round 11), each kept under its stage. While the theory of change's first draft
is written, the boxes and connections the model has closed so far are passed on
as one sketch, sent whole each time; the hub keeps the latest for a newly
connected browser until the draft's stage ends (task 054, S12).

Nothing here is saved to the database. The durable record stays in
``event_log``; these messages may be lost (a full queue is emptied and
refilled with where things stand, a restart forgets everything) and that is by
design.

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
import unicodedata
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
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
#: Longest model query shown in an activity line (task 058, N3).
ACTIVITY_QUERY_MAX = 120
#: Longest query a ``search.query`` message carries. The Search queries table
#: shows whole queries, so this is wider than the activity line's bound; it
#: bounds the frame.
SEARCH_QUERY_MAX = 300

type TickSource = Literal["loop", "hook"]
#: One source as the page names it: ``(source_id, title)``.
type SourceRef = tuple[str, str]
type DeltaMode = Literal["append", "replace"]
#: The stages that publish the names their clustering found (rounds 9 and 11).
type ThemesStage = Literal["characterise", "longlist", "theme"]
#: A stage's memory is kept per walk too (round 11): a longlist walk's own
#: search and its option searches' searches are all ``acquire``.
type _StageKey = tuple[str | None, uuid.UUID | None]
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
        run_id: The walk the line belongs to (a longlist walk's option search
            is its own walk), or ``None`` when unknown (round 11).
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
    run_id: uuid.UUID | None = None


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
    """Names a clustering found, before units are assigned to them (rounds 9 and 11).

    The characterise stage's themes (sources into themes), the longlist
    stage's options (sources into options) and the theme stage's themes
    (options into themes). Display-only: the saved result brings them with
    their counts.

    Attributes:
        themes: ``(label, description)`` pairs in the order found; the
            description may be ``None``.
        occurred_at: When the message was sent.
        stage: The stage that found them: ``characterise``, ``longlist`` or
            ``theme``.
    """

    themes: tuple[tuple[str, str | None], ...]
    occurred_at: datetime
    stage: ThemesStage = "characterise"


#: One sketched box: ``(key, layer, text)``, the model's draft key (task 054, S12).
type SketchBox = tuple[str, str, str]
#: One sketched connection: ``(key, source, target)``, its ends as draft box keys.
type SketchLink = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class TocSketch:
    """The theory of change's first draft as it is written (task 054, S12).

    Display-only and sent whole: each message replaces the one before. An
    empty sketch means "start again" (the draft is written again). The
    stored graph, read when the draft's stage completes, replaces it.

    Attributes:
        boxes: The boxes closed so far, in the order written.
        links: The connections closed so far, in the order written.
        occurred_at: When the message was sent.
        stage: The stage drawing it (``toc_draft``), so its end forgets it.
    """

    boxes: tuple[SketchBox, ...]
    links: tuple[SketchLink, ...]
    occurred_at: datetime
    stage: str | None = None


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
    | TocSketch
)


@dataclass(slots=True)
class _Subscriber:
    """One queue, the event loop that owns it, and how far a resync covered."""

    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[HubMessage]
    #: Messages numbered up to this one are already in the resync this queue
    #: was refilled with, so they are not placed again.
    resynced_through: int = 0


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
    stages: dict[_StageKey, _StageMemory] = field(default_factory=dict)
    draft: _Draft | None = None
    pending_delta: _PendingDelta | None = None
    #: The run's source notes so far, in the order written (round 8).
    source_notes: list[SourceNote] = field(default_factory=list)
    source_notes_at: float = 0.0
    #: The run's search queries so far, keyed by (backend, query, kind), in
    #: the order first sent; each holds its latest message (round 9).
    search_queries: dict[tuple[str, str, str], SearchQuery] = field(default_factory=dict)
    search_queries_at: float = 0.0
    #: The names each clustering stage found, once found, by stage (rounds 9
    #: and 11), in the order first found.
    themes: dict[str, ThemesFound] = field(default_factory=dict)
    themes_at: float = 0.0
    #: The theory of change's draft so far, while it is written (task 054, S12).
    sketch: TocSketch | None = None
    sketch_at: float = 0.0
    #: Stages the run has ended: a late tick for one is ignored, so it cannot
    #: bring the stage back until it starts again.
    ended_stages: set[_StageKey] = field(default_factory=set)

    def keeps_run_lists(self) -> bool:
        """Whether the run's source notes, search queries, themes or sketch are remembered."""
        return bool(self.source_notes or self.search_queries or self.themes or self.sketch)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _clean(text: str) -> str:
    """Replace what UTF-8 cannot carry (a lone surrogate) so the text can be sent."""
    return text.encode("utf-8", "replace").decode("utf-8")


def normalise_query(query: object, limit: int = ACTIVITY_QUERY_MAX) -> str:
    """Make the model's search query safe to show (task 058, N3).

    The text is put in Unicode NFC form, every run of whitespace becomes one
    space, control and format characters (Unicode categories starting with
    ``C``, such as zero-width spaces and lone surrogates) are removed, and the
    result is cut to ``limit`` characters with nothing appended.

    Args:
        query: The query the model sent, of any type.
        limit: The most characters kept.

    Returns:
        The cleaned query, or ``""`` when it is missing or not a string.
    """
    if not isinstance(query, str):
        return ""
    kept = (
        " " if char.isspace() else char
        for char in unicodedata.normalize("NFC", query)
        if char.isspace() or not unicodedata.category(char).startswith("C")
    )
    return " ".join("".join(kept).split())[:limit]


class TickHub:
    """Fans live messages out to each task's subscribers and remembers the latest state.

    Publishers call from worker threads; subscribers are asyncio queues on their
    own event loops. One lock guards all state, and messages reach a queue
    through its loop's ``call_soon_threadsafe``. A full queue is emptied and
    refilled with the task's remembered state, the section draft first, and
    the task's dropped counter goes up by one.
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
        #: Every message fanned out gets the next number (see ``_offer``).
        self._sent = 0

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
            so far (each in its latest state, in the order first sent),
            its themes once found and the theory of change draft's sketch
            so far; then the last tick of each stage (in the
            order the stages first appeared), then, if a section is being
            written, one ``replace`` delta carrying its text so far (even
            when empty, so a client drops what it held before), the sources
            read so far (when there are any),
            each citation bound so far and each case-study card closed so
            far; then the run's source notes so far, in order.
        """
        queue: asyncio.Queue[HubMessage] = asyncio.Queue(maxsize=self._queue_size)
        subscriber = _Subscriber(asyncio.get_running_loop(), queue)
        with self._lock:
            snapshot = self._remembered(task_id)
            self._subscribers.setdefault(task_id, []).append(subscriber)
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
        run_id: uuid.UUID | None = None,
    ) -> None:
        """Publish one activity line, coalesced per task, walk and stage.

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
            run_id: The walk the line belongs to, or ``None``.
        """
        key: _StageKey = (stage, run_id)
        with self._lock:
            now = self._clock()
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            if key in memory.ended_stages:
                # A late callback after the stage ended (task 058 review).
                return
            entry = memory.stages.setdefault(key, _StageMemory())
            if done is not None and total is not None:
                # Workers publish after releasing their own lock, so a smaller
                # count can arrive last: the count never goes backwards.
                for prior in (entry.pending, entry.last):
                    if prior is not None and prior.total == total and prior.done is not None:
                        done = max(done, prior.done)
            tick = Tick(
                stage=stage,
                activity=_clean(activity),
                occurred_at=_now_utc(),
                done=done,
                total=total,
                unit=unit,
                section=_clean(section) if section is not None else None,
                run_id=run_id,
            )
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
                    partial(self._timer_flush_stage, task_id, key),
                )

    def call_opened(
        self, task_id: uuid.UUID, stage: str, run_id: uuid.UUID | None = None
    ) -> None:
        """Mark a model call as open for the task, walk and stage (heartbeats start).

        Args:
            task_id: The task.
            stage: Public stage key.
            run_id: The walk, or ``None``.
        """
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.stages.setdefault((stage, run_id), _StageMemory()).open_calls += 1
            self._schedule_sweep()

    def call_closed(
        self, task_id: uuid.UUID, stage: str, run_id: uuid.UUID | None = None
    ) -> None:
        """Mark a model call as closed for the task, walk and stage.

        Args:
            task_id: The task.
            stage: Public stage key.
            run_id: The walk, or ``None``.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            entry = memory.stages.get((stage, run_id)) if memory is not None else None
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
        text = _clean(text)
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
                added.append((source_id, _clean(title)))
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
        card = SectionCard(
            index=index, title=_clean(title), prose=_clean(prose), occurred_at=_now_utc()
        )
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
            source_id=source_id, title=_clean(title), note=_clean(note), occurred_at=_now_utc()
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
        it comes back replaces the one sent when it went out. The query is
        normalised (:func:`normalise_query`) and cut at
        :data:`SEARCH_QUERY_MAX` first, and keyed on that text.

        Args:
            task_id: The task.
            backend: The database searched.
            query: The query text, or a short description of an id pass.
            kind: What the query is.
            results: ``None`` while out; the records returned once back.
        """
        query = normalise_query(query, limit=SEARCH_QUERY_MAX)
        message = SearchQuery(
            backend=backend, query=query, kind=kind, results=results, occurred_at=_now_utc()
        )
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.search_queries[(backend, query, kind)] = message
            memory.search_queries_at = self._clock()
            self._fan_out(task_id, message)

    def publish_themes(
        self,
        task_id: uuid.UUID,
        *,
        themes: Sequence[tuple[str, str | None]],
        stage: ThemesStage = "characterise",
    ) -> None:
        """Send the names a clustering found, and remember them until the run ends.

        A second message for the same stage replaces the first (the longlist's
        residual pass sends the whole list again).

        Args:
            task_id: The task.
            themes: ``(label, description)`` pairs in the order found.
            stage: The stage that found them.
        """
        cleaned = tuple(
            (_clean(label), _clean(description) if description is not None else None)
            for label, description in themes
        )
        message = ThemesFound(themes=cleaned, occurred_at=_now_utc(), stage=stage)
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.themes[stage] = message
            memory.themes_at = self._clock()
            self._fan_out(task_id, message)

    def publish_sketch(
        self,
        task_id: uuid.UUID,
        *,
        boxes: Sequence[SketchBox],
        links: Sequence[SketchLink],
        stage: str | None = None,
    ) -> None:
        """Send the draft's sketch so far, and remember it until its stage ends.

        Each sketch replaces the one before; an empty one clears the page's.

        Args:
            task_id: The task.
            boxes: ``(key, layer, text)`` of each box so far, in order.
            links: ``(key, source, target)`` of each connection so far, in order.
            stage: The stage drawing it.
        """
        message = TocSketch(
            boxes=tuple((key, layer, _clean(text)) for key, layer, text in boxes),
            links=tuple((key, source, target) for key, source, target in links),
            occurred_at=_now_utc(),
            stage=stage,
        )
        with self._lock:
            memory = self._tasks.setdefault(task_id, _TaskMemory())
            memory.sketch = message
            memory.sketch_at = self._clock()
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

    def end_stage(
        self, task_id: uuid.UUID, stage: str, run_id: uuid.UUID | None = None
    ) -> None:
        """Forget one stage's tick, held tick and open calls.

        Ending ``synthesise`` also forgets the section draft (with its sources,
        citations and cards) and held text. Until the stage starts again
        (:meth:`open_stage`) or the run ends, a late tick for it is ignored.

        Args:
            task_id: The task.
            stage: Public stage key.
            run_id: The walk, or ``None``.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            if memory is None:
                return
            memory.stages.pop((stage, run_id), None)
            memory.ended_stages.add((stage, run_id))
            if stage == "synthesise":
                memory.draft = None
                memory.pending_delta = None
            if memory.sketch is not None and memory.sketch.stage == stage:
                # The stored graph is read once the draft's stage ends.
                memory.sketch = None
            self._forget_if_empty(task_id, memory)

    def open_stage(
        self, task_id: uuid.UUID, stage: str, run_id: uuid.UUID | None = None
    ) -> None:
        """Let a stage that ended publish again, because it is starting again.

        Args:
            task_id: The task.
            stage: Public stage key.
            run_id: The walk, or ``None``.
        """
        with self._lock:
            memory = self._tasks.get(task_id)
            if memory is not None:
                memory.ended_stages.discard((stage, run_id))

    # Timed work ----------------------------------------------------------

    def flush(self) -> None:
        """Send every held tick and held text whose time has come."""
        with self._lock:
            now = self._clock()
            for task_id, memory in list(self._tasks.items()):
                for key, entry in list(memory.stages.items()):
                    if entry.pending is None:
                        continue
                    if now >= entry.pending_due:
                        self._emit_held_tick(task_id, entry, now)
                    elif not entry.flush_scheduled and self._schedule is not None:
                        entry.flush_scheduled = True
                        self._schedule(
                            entry.pending_due - now,
                            partial(self._timer_flush_stage, task_id, key),
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
        :data:`MEMORY_TTL_SECONDS` are forgotten; a stage with an open model
        call stays fresh. A task left with nothing fresh is forgotten, its run
        too (a run that died without ending). While the hub remembers any
        task, another sweep is arranged.
        """
        with self._lock:
            now = self._clock()
            for task_id, memory in list(self._tasks.items()):
                for key, entry in list(memory.stages.items()):
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
                    if (
                        entry.last is not None
                        and entry.open_calls == 0
                        and now - entry.updated_at >= MEMORY_TTL_SECONDS
                    ):
                        entry.last = None
                    if entry.last is None and entry.pending is None and entry.open_calls == 0:
                        del memory.stages[key]
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
                if memory.themes and now - memory.themes_at >= MEMORY_TTL_SECONDS:
                    memory.themes = {}
                if memory.sketch is not None and now - memory.sketch_at >= MEMORY_TTL_SECONDS:
                    memory.sketch = None
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

    def _remembered(self, task_id: uuid.UUID) -> list[HubMessage]:
        """Build the task's remembered state, as :meth:`subscribe_with_snapshot` returns it."""
        now = self._clock()
        memory = self._tasks.get(task_id)
        snapshot: list[HubMessage] = []
        if memory is None:
            return snapshot
        if memory.pending_delta is not None:
            # The draft already holds the held text; send it to the existing
            # subscribers now so a newcomer does not get it twice.
            self._emit_pending_delta(task_id, memory)
        if memory.search_queries and now - memory.search_queries_at < MEMORY_TTL_SECONDS:
            snapshot.extend(memory.search_queries.values())
        if memory.themes and now - memory.themes_at < MEMORY_TTL_SECONDS:
            snapshot.extend(memory.themes.values())
        if memory.sketch is not None and now - memory.sketch_at < MEMORY_TTL_SECONDS:
            snapshot.append(memory.sketch)
        for stage_memory in memory.stages.values():
            last = stage_memory.last
            if last is None or now - stage_memory.updated_at >= MEMORY_TTL_SECONDS:
                continue
            snapshot.append(dataclasses.replace(last, heartbeat=False))
        draft = memory.draft
        if draft is not None and now - draft.updated_at < MEMORY_TTL_SECONDS:
            # Sent even when empty: a client that held text from before (the
            # fallback's reset) drops it, and its cards and citations with it.
            snapshot.append(
                SectionDelta(
                    index=draft.index, text=draft.text, mode="replace", occurred_at=_now_utc()
                )
            )
            if draft.sources:
                snapshot.append(
                    SectionSources(
                        index=draft.index, sources=draft.sources, occurred_at=_now_utc()
                    )
                )
            snapshot.extend(draft.claims)
            snapshot.extend(draft.cards)
        if memory.source_notes and now - memory.source_notes_at < MEMORY_TTL_SECONDS:
            snapshot.extend(memory.source_notes)
        return snapshot

    def _fan_out(self, task_id: uuid.UUID, message: HubMessage) -> None:
        self._sent += 1
        self._schedule_sweep()
        for subscriber in self._subscribers.get(task_id, ()):
            try:
                subscriber.loop.call_soon_threadsafe(
                    self._offer, task_id, subscriber, message, self._sent
                )
            except RuntimeError:
                # A closed loop is a disconnected client.
                continue

    def _offer(
        self, task_id: uuid.UUID, subscriber: _Subscriber, message: HubMessage, number: int
    ) -> None:
        """Place one message without waiting; resync a full queue (loop thread).

        Dropping messages would leave a hole in the client's draft, so a full
        queue is emptied and refilled with the task's remembered state, the
        section draft first. Messages fanned out before the resync was built
        are in it already and are not placed again.
        """
        if number <= subscriber.resynced_through:
            return
        queue = subscriber.queue
        try:
            queue.put_nowait(message)
            return
        except asyncio.QueueFull:
            pass
        with self._lock:
            resync = self._remembered(task_id)
            subscriber.resynced_through = self._sent
            self._dropped[task_id] = self._dropped.get(task_id, 0) + 1
        while not queue.empty():
            queue.get_nowait()
        drafts = (SectionDelta, SectionSources, SectionClaim, SectionCard)
        ordered: list[HubMessage] = [m for m in resync if isinstance(m, drafts)]
        ordered += [m for m in resync if not isinstance(m, drafts)]
        for item in ordered[: queue.maxsize]:
            queue.put_nowait(item)

    def _schedule_sweep(self) -> None:
        if self._schedule is None or self._sweep_scheduled or not self._tasks:
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

    def _timer_flush_stage(self, task_id: uuid.UUID, key: _StageKey) -> None:
        with self._lock:
            memory = self._tasks.get(task_id)
            entry = memory.stages.get(key) if memory is not None else None
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
_run_id: ContextVar[uuid.UUID | None] = ContextVar("liveness_run_id", default=None)
tick_hub = TickHub(schedule=_timer_schedule)


@contextmanager
def task_liveness(
    task_id: uuid.UUID, *, stage: str | None = None, run_id: uuid.UUID | None = None
) -> Iterator[None]:
    """Bind the task (and the stage key and walk, when known) for the publishers below.

    Args:
        task_id: The task whose work runs inside the block.
        stage: The public stage key, when the block is one stage's work.
        run_id: The walk the work belongs to, when known: its ticks carry it,
            so a longlist walk's page can tell its option searches' lines
            from its own (round 11).

    Yields:
        Nothing; the binding lasts until the block exits.
    """
    if stage is not None:
        tick_hub.open_stage(task_id, stage, run_id)
    task_token = _task_id.set(task_id)
    stage_token = _stage.set(stage)
    run_token = _run_id.set(run_id)
    try:
        yield
    finally:
        _run_id.reset(run_token)
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
        run_id=_run_id.get(),
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
    tick_hub.publish_tick(
        task_id, stage=stage, activity=activity, source="hook", run_id=_run_id.get()
    )


def model_call_opened() -> None:
    """Mark a model call as open for the bound task and stage (no-op when unbound)."""
    task_id = _task_id.get()
    stage = _stage.get()
    if task_id is not None and stage is not None:
        tick_hub.call_opened(task_id, stage, _run_id.get())


def model_call_closed() -> None:
    """Mark a model call as closed for the bound task and stage (no-op when unbound)."""
    task_id = _task_id.get()
    stage = _stage.get()
    if task_id is not None and stage is not None:
        tick_hub.call_closed(task_id, stage, _run_id.get())


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


def publish_themes(
    themes: Sequence[tuple[str, str | None]], *, stage: ThemesStage = "characterise"
) -> None:
    """Publish the names a clustering found for the bound task (no-op when unbound).

    Args:
        themes: ``(label, description)`` pairs in the order found.
        stage: The stage that found them (rounds 9 and 11).
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_themes(task_id, themes=themes, stage=stage)


def publish_toc_sketch(boxes: Sequence[SketchBox], links: Sequence[SketchLink]) -> None:
    """Publish the theory of change draft's sketch so far for the bound task (task 054, S12).

    Does nothing when no task is bound.

    Args:
        boxes: ``(key, layer, text)`` of each box closed so far, in order.
        links: ``(key, source, target)`` of each connection closed so far, in order.
    """
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.publish_sketch(task_id, boxes=boxes, links=links, stage=_stage.get())


def clear_section_draft() -> None:
    """Forget the bound task's section draft (a section has finished; no-op when unbound)."""
    task_id = _task_id.get()
    if task_id is not None:
        tick_hub.clear_draft(task_id)
