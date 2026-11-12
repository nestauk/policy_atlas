"""The theory-of-change report as it is written (task 054's 058 alignment, S4 to S7b).

In plain terms: the report is still one model call with the same prompt
(``toc_report_v7``), model and answer format. What changes is that the answer
is read as it arrives ("streamed"), and each field of it is shown on the page
in its own place while the rest is still being written. The finished answer is
then checked and assembled by :func:`policy_atlas.theory_of_change.report.toc_report_scope`
exactly as before, so the stored report does not change.

What the page receives, through Evidence search's live frames (ADR 0044):

1. A **skeleton**: one entry per part of the report page, in page order. Its
   ``index`` is the part's identity in every later frame (:func:`report_layout`).
2. The **verdict line** at once: it is decided before the report call, so its
   part is completed straight after the skeleton.
3. Each **field** as the model writes it, in the order it writes them (the
   answer format's order, not the page order). Text fields arrive as pieces of
   text (``artefact.section_delta``); list fields arrive one item at a time
   (``artefact.section_card``). A part gets ``artefact.section_completed`` as
   soon as its last field closes, so a browser that reconnects gets every
   closed part back from the saved event log.
4. The numbered sources, on each part as its text starts
   (``artefact.section_sources``), so a pending ``[n]`` chip can name its
   source. A source's ``source_id`` is its number as the model cites it.

If the stream fails, or sends no words within the route file's
``first_content_s``, the page is reset (a fresh skeleton and an empty
``replace`` for every part), the ordinary non-streamed call runs once through
today's retries, and its text arrives as one ``replace`` per part.

Nothing here changes the content: there is no claim check and no repair, so
no revising or claim frames.
"""

from __future__ import annotations

import contextvars
import queue
import re
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

import structlog
from pydantic import BaseModel, ValidationError

from policy_atlas.core import liveness
from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import (
    JsonArrayObjectDecoder,
    JsonArrayStringDecoder,
    JsonStringFieldDecoder,
)
from policy_atlas.core.usage import TokenUsage, UsageAccumulator, UsageResult
from policy_atlas.runtime.progress import ProgressEmitter
from policy_atlas.theory_of_change.report_prompt import (
    ConnectionReasonWire,
    FoundRouteWire,
    PathwayLineWire,
    ReportResponse,
    WhatToTestWire,
)

log = structlog.get_logger()

#: The route step the report call uses.
REPORT_STEP = "toc_report"

#: The page's parts in page order: the header above the canvas, then the report
#: below it (``TocResult.tsx`` and ``DetailedInformation.tsx``). ``None`` titles
#: are the header parts, which carry no heading; the verdict's title is its label.
#: ``found_routes`` and ``supporting_activities`` are left out when the report
#: has none, as the page leaves them out.
PAGE_PARTS: tuple[tuple[str, str | None], ...] = (
    ("title", None),
    ("verdict", None),
    ("question", None),
    ("in_brief", None),
    ("summary", "Summary"),
    ("pathways", "Pathways"),
    ("how_it_could_fail", "How it could fail"),
    ("tests", "What to test first"),
    ("found_routes", "How it could be expanded"),
    ("supporting_activities", "Supporting activities"),
    ("assumptions", "Assumptions"),
    ("references", "References"),
)


@dataclass(frozen=True)
class _Field:
    """One field of the model's answer and where it shows on the page."""

    name: str
    #: ``"text"``, ``"objects"`` or ``"strings"``.
    kind: str
    part: str
    #: Written before the field's text when its part already holds text.
    joiner: str = ""


#: The answer's fields in the order the model writes them (``ReportResponse``'s
#: order, task 054 S6), each with its page part. ``question`` shows in the header
#: and again in the Summary's first paragraph: it streams into the header, and
#: joins the Summary whole when it closes (see :meth:`ReportFrames._close_field`).
FIELDS: tuple[_Field, ...] = (
    _Field("title", "text", "title"),
    _Field("summary", "text", "in_brief"),
    _Field("context", "text", "summary"),
    _Field("question", "text", "question"),
    _Field("if_then_because", "text", "summary", "\n\n"),
    _Field("verdict_reason", "text", "summary", "\n\n"),
    _Field("pathways", "objects", "pathways"),
    _Field("how_it_could_fail", "text", "how_it_could_fail"),
    _Field("connection_reasons", "objects", "assumptions"),
    _Field("found_routes", "objects", "found_routes"),
    _Field("supporting_activities", "strings", "supporting_activities"),
    _Field("tests", "objects", "tests"),
)
#: ``question`` joins the Summary after the context, with a space.
QUESTION_JOINER = " "

#: An unclosed ``[n]`` or ``#n`` at the end of streamed text: held back until it closes.
_OPEN_MARKER = re.compile(r"(?:\[\d*|#\d*)$")


class FirstContentTimeout(TimeoutError):
    """The streamed call sent no words within the step's ``first_content_s``."""


class StreamFailed(RuntimeError):
    """A streamed call that failed after it was sent, with the tokens it had used.

    In plain terms: a stream can fail late (its whole answer came but did not
    parse) after the model has already been paid for. The tokens it reported
    ride on this error so the caller adds them to the step's cost before the
    ordinary call runs. The original failure is the error's ``__cause__``.

    Args:
        usage: The tokens the stream reported, or ``None`` when it reported none
            (a stream that dropped or sent nothing in time reports none).
    """

    def __init__(self, usage: TokenUsage | None) -> None:
        super().__init__("the streamed call failed")
        self.usage = usage


def stream_failure(exc: BaseException) -> tuple[str, TokenUsage | None]:
    """A failed stream's error name for the log, and the tokens it used.

    Args:
        exc: What the streamed call raised.

    Returns:
        The original failure's class name and the stream's usage (``None``
        unless ``exc`` is a :class:`StreamFailed` that carries some).
    """
    if isinstance(exc, StreamFailed):
        return type(exc.__cause__ or exc).__name__, exc.usage
    return type(exc).__name__, None


@dataclass(frozen=True)
class Part:
    """One part of the report page in the live frames.

    Args:
        index: The display index every frame for the part carries.
        key: The part's name in :data:`PAGE_PARTS`.
        title: The title the skeleton gives it ("" for a header part).
    """

    index: int
    key: str
    title: str


def report_layout(
    *, verdict_label: str | None, found_routes: bool, supporting_activities: bool
) -> list[Part]:
    """The report's parts in page order, numbered from 0.

    Args:
        verdict_label: The overall verdict's label (the verdict part's title), or
            ``None`` when the verdict call failed.
        found_routes: Whether the report has routes found in the evidence.
        supporting_activities: Whether the theory names supporting activities.

    Returns:
        One :class:`Part` per part the page shows.
    """
    left_out = {
        name
        for name, present in (
            ("found_routes", found_routes),
            ("supporting_activities", supporting_activities),
        )
        if not present
    }
    keys = [(key, title) for key, title in PAGE_PARTS if key not in left_out]
    return [
        Part(
            index=index,
            key=key,
            title=(verdict_label or "") if key == "verdict" else (title or ""),
        )
        for index, (key, title) in enumerate(keys)
    ]


def first_content_limit() -> float | None:
    """The report stream's time-to-first-content limit from the route file."""
    return route().first_content_for(REPORT_STEP)


def consume(
    fragments: Iterator[str],
    *,
    first_content_s: float | None,
    on_fragment: Callable[[str], None],
    cancel: Callable[[], None] | None = None,
) -> str:
    """Read a stream's text pieces, giving up if no words come in time.

    In plain terms: the pieces are read on a helper thread, so this thread can
    stop waiting when the first words are late, even while the helper is stuck
    waiting on the network. Each piece is handed to ``on_fragment`` on this
    thread (where the task's live-progress binding is), in order.

    Args:
        fragments: The stream's text pieces; it may raise.
        first_content_s: Seconds to wait for the first non-empty piece, or
            ``None`` for no limit. After it, the stream's own timeout applies.
        on_fragment: Called with each non-empty piece.
        cancel: Called when the limit passes, to close the stream (best effort).

    Returns:
        The whole text.

    Raises:
        FirstContentTimeout: If no words came within ``first_content_s``.
        Exception: Whatever the stream raised.
    """
    items: queue.Queue[tuple[str, Any]] = queue.Queue()
    stop = threading.Event()

    def pump() -> None:
        try:
            for piece in fragments:
                if stop.is_set():
                    return
                items.put(("text", piece))
            items.put(("end", None))
        except BaseException as exc:  # handed to the reading thread
            items.put(("error", exc))

    context = contextvars.copy_context()
    threading.Thread(target=context.run, args=(pump,), daemon=True).start()
    deadline = None if first_content_s is None else time.monotonic() + first_content_s
    parts: list[str] = []
    while True:
        try:
            if deadline is None:
                kind, item = items.get()
            else:
                kind, item = items.get(timeout=max(deadline - time.monotonic(), 0.0))
        except queue.Empty:
            stop.set()
            if cancel is not None:
                try:
                    cancel()
                except Exception:  # closing is best effort; the fallback runs anyway
                    log.debug("toc_report.stream_cancel_failed", exc_info=True)
            raise FirstContentTimeout(
                f"no words from the report stream within {first_content_s} s"
            ) from None
        if kind == "end":
            return "".join(parts)
        if kind == "error":
            raise item
        if item:
            deadline = None
            parts.append(item)
            on_fragment(item)


def _card_prose(cards: Iterable[tuple[str, str]]) -> str:
    """A list part's text: each item as its bold title line and text, as Evidence search's cards."""
    return "\n\n".join(f"**{title}**\n{prose}" if title else prose for title, prose in cards)


@dataclass
class _FieldState:
    spec: _Field
    decoder: Any
    held: str = ""
    text: str = ""
    closed: bool = False


@dataclass
class ReportFrames:
    """Send the report's live frames as the model's answer streams in.

    Args:
        emitter: The durable frames' writer, or ``None`` (no saved frames, as
            in a test that calls the step directly).
        parts: The page's parts (:func:`report_layout`).
        verdict_headline: The overall verdict's headline, sent with the
            verdict part at once; ``None`` when the verdict call failed.
        sources: ``(number, short name)`` of each numbered source, in number order.
        route_labels: Found route key → its label, the title of its item.
    """

    emitter: ProgressEmitter | None
    parts: list[Part]
    verdict_headline: str | None
    sources: list[tuple[str, str]]
    route_labels: dict[str, str]
    _by_key: dict[str, Part] = field(init=False)
    _fields: list[_FieldState] = field(init=False)
    _texts: dict[int, str] = field(init=False)
    _cards: dict[int, list[tuple[str, str]]] = field(init=False)
    _started: set[int] = field(init=False)
    _completed: set[int] = field(init=False)
    _current: int | None = field(init=False)

    def __post_init__(self) -> None:
        self._by_key = {part.key: part for part in self.parts}
        self._reset_state()

    # The frames ----------------------------------------------------------

    def start(self) -> None:
        """Send the skeleton, then the verdict part (known before the call)."""
        if self.emitter is not None:
            self.emitter.emit_skeleton(
                [{"title": part.title, "focus": ""} for part in self.parts], key_findings=False
            )
        self._complete(self._by_key["verdict"].index, self.verdict_headline or "")

    def feed(self, fragment: str) -> None:
        """Read one piece of the answer's JSON text and publish what it closed.

        Args:
            fragment: The next piece of the streamed JSON text.
        """
        for state in self._fields:
            if state.closed:
                continue
            spec = state.spec
            if spec.kind == "text":
                self._text(state, state.decoder.feed(fragment))
            else:
                for raw in state.decoder.feed(fragment):
                    self._item(state, raw)
            if state.decoder.done:
                self._close_field(state)

    def finish(self) -> None:
        """Close every part still open and the References part; forget the draft."""
        for state in self._fields:
            if not state.closed:
                self._close_field(state)
        self._close_rest()

    def restart(self) -> None:
        """Start the page again for the fallback: a fresh skeleton and an empty part each.

        The verdict part is sent again after the fresh skeleton.
        """
        if self.emitter is not None:
            self.emitter = self.emitter.fresh()
        self._reset_state()
        if self.emitter is not None:
            self.emitter.emit_skeleton(
                [{"title": part.title, "focus": ""} for part in self.parts], key_findings=False
            )
        for part in self.parts:
            liveness.publish_section_delta(part.index, "", mode="replace")
        liveness.clear_section_draft()
        self._complete(self._by_key["verdict"].index, self.verdict_headline or "")

    def publish_whole(self, response: ReportResponse) -> None:
        """Send the fallback's answer: one ``replace`` per part, each part then completed.

        Args:
            response: The non-streamed call's answer.
        """
        for index, text in part_texts(response, self.parts, self.route_labels).items():
            if index in self._completed:
                continue
            self._open(index)
            liveness.publish_section_delta(index, text, mode="replace")
            self._texts[index] = text
            self._complete(index, text)
        self._close_rest()

    def texts(self) -> dict[int, str]:
        """Each completed or open part's text so far, by display index (for tests)."""
        return dict(self._texts)

    # Fields --------------------------------------------------------------

    def _reset_state(self) -> None:
        self._fields = [
            _FieldState(
                spec,
                JsonStringFieldDecoder(spec.name)
                if spec.kind == "text"
                else JsonArrayObjectDecoder(spec.name)
                if spec.kind == "objects"
                else JsonArrayStringDecoder(spec.name),
            )
            for spec in FIELDS
            if spec.part in self._by_key
        ]
        self._texts = {}
        self._cards = {}
        self._started = set()
        self._completed = set()
        self._current = None

    def _text(self, state: _FieldState, decoded: str) -> None:
        if not decoded:
            return
        pending = state.held + decoded
        match = _OPEN_MARKER.search(pending)
        cut = match.start() if match else len(pending)
        state.held = pending[cut:]
        self._write(state, pending[:cut])

    def _write(self, state: _FieldState, text: str) -> None:
        if not text:
            return
        index = self._by_key[state.spec.part].index
        joiner = state.spec.joiner if not state.text and self._texts.get(index) else ""
        state.text += text
        self._append(index, joiner + text)

    def _item(self, state: _FieldState, raw: str) -> None:
        card = _card(state.spec.name, raw, self.route_labels)
        if card is None:
            return
        index = self._by_key[state.spec.part].index
        self._open(index)
        self._cards.setdefault(index, []).append(card)
        self._texts[index] = _card_prose(self._cards[index])
        liveness.publish_section_card(index, card[0], card[1])

    def _close_field(self, state: _FieldState) -> None:
        state.closed = True
        if state.held:
            held, state.held = state.held, ""
            self._write(state, held)
        if state.spec.name == "question" and state.text and "summary" in self._by_key:
            summary = self._by_key["summary"].index
            joiner = QUESTION_JOINER if self._texts.get(summary) else ""
            self._append(summary, joiner + state.text)
        for key in {state.spec.part, *(["summary"] if state.spec.name == "question" else [])}:
            index = self._by_key[key].index
            feeding = [s for s in self._fields if s.spec.part == key]
            if key == "summary":
                feeding += [s for s in self._fields if s.spec.name == "question"]
            if all(s.closed for s in feeding) and index not in self._completed:
                self._complete(index, self._texts.get(index, ""))

    def _close_rest(self) -> None:
        for part in self.parts:
            if part.index not in self._completed:
                self._complete(part.index, self._texts.get(part.index, ""))
        liveness.clear_section_draft()
        self._current = None

    # The hub and the saved frames ----------------------------------------

    def _open(self, index: int) -> None:
        """Make ``index`` the hub's current draft, with the sources and its text so far."""
        if self._current == index:
            return
        self._current = index
        if index not in self._started:
            self._started.add(index)
            if self.emitter is not None:
                self.emitter.section_started(index)
        if self.sources:
            liveness.publish_section_sources(index, self.sources)
        if self._texts.get(index):
            # Back on a part after another one (the Summary after the header's
            # question): the hub's draft holds one part, so it gets this part's
            # text so far. The browser already has it; nothing changes there.
            liveness.publish_section_delta(index, self._texts[index], mode="replace")

    def _append(self, index: int, text: str) -> None:
        self._open(index)
        self._texts[index] = self._texts.get(index, "") + text
        liveness.publish_section_delta(index, text)

    def _complete(self, index: int, prose: str) -> None:
        self._completed.add(index)
        if self.emitter is not None:
            self.emitter.section_completed(index, prose=prose)
        if self._current == index:
            liveness.clear_section_draft()
            self._current = None


_ITEM_WIRES: dict[str, type[BaseModel]] = {
    "pathways": PathwayLineWire,
    "connection_reasons": ConnectionReasonWire,
    "found_routes": FoundRouteWire,
    "tests": WhatToTestWire,
}


def _card(name: str, raw: Any, route_labels: dict[str, str]) -> tuple[str, str] | None:
    """One list item as ``(title, text)``; ``None`` when it does not parse."""
    if name == "supporting_activities":
        return ("", raw) if isinstance(raw, str) and raw else None
    try:
        item = _ITEM_WIRES[name].model_validate_json(raw)
    except ValidationError:
        return None
    return _card_of(item, route_labels)


def _card_of(item: BaseModel, route_labels: dict[str, str]) -> tuple[str, str]:
    if isinstance(item, PathwayLineWire):
        return item.title, item.sentence
    if isinstance(item, ConnectionReasonWire):
        return item.connection, item.why
    if isinstance(item, FoundRouteWire):
        return route_labels.get(item.route, item.route), item.sentence
    assert isinstance(item, WhatToTestWire)
    return item.connection, item.sentence


def part_texts(
    response: ReportResponse, parts: list[Part], route_labels: dict[str, str]
) -> dict[int, str]:
    """Each streamed part's whole text for an answer, as the stream composes it.

    Args:
        response: The model's answer.
        parts: The page's parts.
        route_labels: Found route key → its label.

    Returns:
        Display index → text, for every part fed by the answer (not the
        verdict or References).
    """
    by_key = {part.key: part.index for part in parts}
    texts: dict[str, str] = {}

    def add(key: str, text: str, joiner: str = "") -> None:
        if key in by_key and text:
            texts[key] = texts[key] + joiner + text if texts.get(key) else text

    add("title", response.title)
    add("in_brief", response.summary)
    add("question", response.question)
    add("summary", response.context)
    add("summary", response.question, QUESTION_JOINER)
    add("summary", response.if_then_because, "\n\n")
    add("summary", response.verdict_reason, "\n\n")
    add("how_it_could_fail", response.how_it_could_fail)
    for key, items in (
        ("pathways", response.pathways),
        ("assumptions", response.connection_reasons),
        ("found_routes", response.found_routes),
        ("tests", response.tests),
    ):
        add(key, _card_prose(_card_of(item, route_labels) for item in items))
    add(
        "supporting_activities",
        _card_prose(("", text) for text in response.supporting_activities if text),
    )
    return {by_key[key]: text for key, text in texts.items() if key in by_key}


def write_streamed(
    backend: Any,
    inputs: dict[str, Any],
    frames: ReportFrames,
    usage: UsageAccumulator,
    fallback: Callable[[], ReportResponse | None],
) -> ReportResponse | None:
    """Write the report with one streamed call, falling back once to the ordinary call.

    The streamed call runs once, outside every retry loop: a retry would
    repeat words the reader has already seen. Its usage is added to ``usage``
    as the ordinary call's is, also when it failed late and the fallback ran.

    Args:
        backend: The ToC backend (``report_stream`` and ``report``).
        inputs: The report call's keyword inputs (plan, theory, rows, sources).
        frames: The live frames.
        usage: The step's usage totals.
        fallback: Makes the ordinary call with today's retries (and adds its usage).

    Returns:
        The answer, or ``None`` when the fallback failed too.
    """
    frames.start()
    liveness.model_call_opened()
    started = time.monotonic()
    try:
        wire, used = backend.report_stream(
            **inputs, on_text=frames.feed, first_content_s=first_content_limit()
        )
    except Exception as exc:
        error, stream_usage = stream_failure(exc)
        log.warning(
            "toc_report.stream_fallback",
            error=error,
            elapsed_s=round(time.monotonic() - started, 1),
        )
        # The failed stream's tokens were paid for: they count in the step's cost.
        usage.add(stream_usage)
        result: UsageResult[ReportResponse] | None = None
    else:
        result = (wire, used)
    finally:
        liveness.model_call_closed()
    if result is not None:
        usage.add(result[1])
        frames.finish()
        return result[0]
    frames.restart()
    response = fallback()
    if response is not None:
        frames.publish_whole(response)
    return response
