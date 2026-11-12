"""The theory of change's first draft, drawn on the page as it is written (task 054, S12).

In plain terms: the draft is still one model call with the same prompt
(``toc_draft_v5``), model, answer format, checks and retry. What changes is
that the answer is read as it arrives ("streamed"). The model writes the
boxes first, then the connections, then the pathways and the rest. Each box
and each connection is sent to the page as soon as its part of the answer is
complete, so the canvas can draw it while the rest is still being written.

What the page receives: one live frame, ``toc.sketch``, carrying every box and
connection written so far (sent whole each time, so a frame that goes missing
costs nothing). The keys in it are the model's own keys ("b1", "l1"), not
stored ids. When the draft step ends, the page reads the stored graph, which
replaces the sketch. An empty sketch means "start again": it is sent when the
stream fails and the ordinary call runs instead, and before a draft that
failed its checks is written again.

Nothing is saved: the sketch lives only in this process's live hub
(:mod:`policy_atlas.core.liveness`), which hands a reconnecting browser the
sketch so far and forgets it when the draft's stage ends.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import structlog
from pydantic import ValidationError

from policy_atlas.core import liveness
from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import JsonArrayObjectDecoder
from policy_atlas.core.usage import TokenUsage, UsageResult, add_token_usage
from policy_atlas.theory_of_change.backend import DRAFT_STEP, TocBackend
from policy_atlas.theory_of_change.draft_prompt import (
    DraftBoxWire,
    DraftLinkWire,
    DraftResponse,
)
from policy_atlas.theory_of_change.report_stream import stream_failure

log = structlog.get_logger()


def first_content_limit() -> float | None:
    """The draft stream's time-to-first-content limit from the route file."""
    return route().first_content_for(DRAFT_STEP)


@dataclass
class SketchFrames:
    """Send the draft's boxes and connections to the page as each one closes.

    The page gets the whole sketch each time (``toc.sketch``). A box or
    connection that does not parse on its own is left out; the stored graph
    brings everything when the step ends.
    """

    _boxes: list[tuple[str, str, str]] = field(default_factory=list)
    _links: list[tuple[str, str, str]] = field(default_factory=list)
    _box_decoder: JsonArrayObjectDecoder = field(init=False)
    _link_decoder: JsonArrayObjectDecoder = field(init=False)

    def __post_init__(self) -> None:
        self._decoders()

    def feed(self, fragment: str) -> None:
        """Read one piece of the answer's JSON text and publish what it closed.

        Args:
            fragment: The next piece of the streamed JSON text.
        """
        changed = False
        if not self._box_decoder.done:
            for raw in self._box_decoder.feed(fragment):
                changed |= self._box(raw)
        if not self._link_decoder.done:
            for raw in self._link_decoder.feed(fragment):
                changed |= self._link(raw)
        if changed:
            self._publish()

    def reset(self) -> None:
        """Start the sketch again: the page drops what it drew (an empty sketch is sent)."""
        self._boxes, self._links = [], []
        self._decoders()
        self._publish()

    def sketch(self) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
        """The boxes and connections so far (for tests)."""
        return list(self._boxes), list(self._links)

    def _decoders(self) -> None:
        self._box_decoder = JsonArrayObjectDecoder("boxes")
        self._link_decoder = JsonArrayObjectDecoder("links")

    def _box(self, raw: str) -> bool:
        try:
            box = DraftBoxWire.model_validate_json(raw)
        except ValidationError:
            return False
        self._boxes.append((box.key, box.layer, box.text))
        return True

    def _link(self, raw: str) -> bool:
        try:
            link = DraftLinkWire.model_validate_json(raw)
        except ValidationError:
            return False
        self._links.append((link.key, link.source, link.target))
        return True

    def _publish(self) -> None:
        liveness.publish_toc_sketch(self._boxes, self._links)


def draft_streamed(
    backend: TocBackend,
    *,
    plan: dict[str, object],
    existing_theory: str | None,
    problems: list[str] | None,
    frames: SketchFrames,
) -> UsageResult[DraftResponse]:
    """Write one draft attempt with a streamed call, falling back once to the ordinary call.

    The streamed call runs once, outside the ordinary call's retries: a retry
    would draw boxes the reader has already seen. If it fails, or sends no
    words within the route file's ``first_content_s``, the sketch is reset
    and :meth:`TocBackend.draft` runs as today (its own retries included).

    Args:
        backend: The ToC backend.
        plan: The plan fields as data.
        existing_theory: The user's own theory, or ``None``.
        problems: The previous attempt's problems, for the retry; else ``None``.
        frames: The live sketch.

    Returns:
        The draft and its usage, as :meth:`TocBackend.draft` returns them. After
        a fallback the usage also counts the failed stream's tokens.

    Raises:
        Exception: Whatever the ordinary call raises after the stream failed.
    """
    liveness.model_call_opened()
    started = time.monotonic()
    stream_usage: TokenUsage | None = None
    try:
        return backend.draft_stream(
            plan=plan,
            existing_theory=existing_theory,
            problems=problems,
            on_text=frames.feed,
            first_content_s=first_content_limit(),
        )
    except Exception as exc:
        error, stream_usage = stream_failure(exc)
        log.warning(
            "toc_draft.stream_fallback",
            error=error,
            elapsed_s=round(time.monotonic() - started, 1),
        )
    finally:
        liveness.model_call_closed()
    frames.reset()
    draft, used = backend.draft(plan=plan, existing_theory=existing_theory, problems=problems)
    # The failed stream's tokens were paid for: they count with the ordinary call's.
    return draft, add_token_usage(stream_usage, used)
