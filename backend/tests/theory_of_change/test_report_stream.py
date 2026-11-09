"""The ToC report streams to the page as it is written (task 054's 058 alignment, A11, A12, A22).

A scripted stream (the stub backend's ``report_stream`` queue, or a fake
OpenAI client) drives the frames: the skeleton, each part in the order the
model writes it, the held markers, the fallback, the reconnect snapshot, and
the equality of the streamed and non-streamed paths.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from openai.lib._parsing._completions import type_to_response_format_param
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core import liveness
from policy_atlas.core.liveness import SectionCard, SectionDelta, SectionSources, TickHub
from policy_atlas.core.schema import event_log
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.theory_of_change import report_stream
from policy_atlas.theory_of_change.backend import OpenAITocBackend, StubTocBackend
from policy_atlas.theory_of_change.report import streams_to_page, toc_report_scope
from policy_atlas.theory_of_change.report_prompt import (
    ConnectionReasonWire,
    FoundRouteWire,
    PathwayLineWire,
    ReportResponse,
    WhatToTestWire,
)
from policy_atlas.theory_of_change.report_stream import (
    ReportFrames,
    part_texts,
    report_layout,
    write_streamed,
)
from tests.theory_of_change.test_check_steps import _run, _summary
from tests.theory_of_change.test_walks import _walks, seed_toc

TASK = uuid.UUID(int=54)

RESPONSE = ReportResponse(
    title="Food advert limits and childhood obesity",
    summary="The weakest step is #2; a trial of [12] would settle it.",
    context="London limited adverts in 2019 [1].",
    question="This report asks whether the limits cut obesity.",
    if_then_because="If adverts fall, then children buy less, because cues drop [2].",
    verdict_reason="Purchases fell [12] but #2 is thin.",
    pathways=[PathwayLineWire(pathway="p1", title="Fewer adverts", sentence="It works [1].")],
    how_it_could_fail="Firms shift spend (#4) [2].",
    connection_reasons=[ConnectionReasonWire(connection="#2", why="Mixed [12].")],
    found_routes=[FoundRouteWire(route="r1", sentence="Schools act too [3].")],
    supporting_activities=["Set-up costs matter [1].", "Training"],
    tests=[WhatToTestWire(connection="#2", sentence="Measure purchases.")],
)
SOURCES = [("1", "Boyland 2016"), ("2", "Public Health Scotland 2022"), ("12", "Yau 2022")]
ROUTES = {"r1": "Schools"}
PARTS = report_layout(verdict_label="Mixed evidence", found_routes=True, supporting_activities=True)
INDEX = {part.key: part.index for part in PARTS}
INPUTS: dict[str, Any] = {"plan": {}, "theory": {}, "rows": [], "sources": []}


class FakeEmitter:
    """Records the saved frames; ``fresh`` shares the record (a fallback's new emitter)."""

    def __init__(self, log: list[tuple[Any, ...]] | None = None) -> None:
        self.log: list[tuple[Any, ...]] = [] if log is None else log
        self.skeleton: list[dict[str, str]] = []

    def fresh(self) -> FakeEmitter:
        return FakeEmitter(self.log)

    def emit_skeleton(self, sections: list[dict[str, str]], *, key_findings: bool) -> None:
        assert key_findings is False
        self.skeleton = list(sections)
        self.log.append(("skeleton", [s["title"] for s in sections]))

    def section_started(self, index: int) -> None:
        self.log.append(("started", index))

    def section_completed(self, index: int, *, prose: str) -> None:
        self.log.append(("completed", index, prose))

    def completed(self) -> list[int]:
        return [entry[1] for entry in self.log if entry[0] == "completed"]


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> Iterator[TickHub]:
    """A fresh live hub bound to TASK under the report's stage, its messages recorded."""
    fresh = TickHub(schedule=None)
    sent: list[Any] = []
    real = fresh._fan_out

    def record(task_id: uuid.UUID, message: Any) -> None:
        sent.append(message)
        real(task_id, message)

    monkeypatch.setattr(fresh, "_fan_out", record)
    monkeypatch.setattr(liveness, "tick_hub", fresh)
    fresh.sent = sent  # type: ignore[attr-defined]
    with liveness.task_liveness(TASK, stage="toc_report"):
        yield fresh


def _sent(hub: TickHub) -> list[Any]:
    return list(hub.sent)  # type: ignore[attr-defined]


def _frames(emitter: FakeEmitter | None = None) -> ReportFrames:
    return ReportFrames(
        emitter=emitter if emitter is not None else FakeEmitter(),  # type: ignore[arg-type]
        parts=PARTS,
        verdict_headline="It may work, but one step is thin.",
        sources=SOURCES,
        route_labels=ROUTES,
    )


def _pieces(text: str, size: int = 7) -> list[str]:
    return [text[at : at + size] for at in range(0, len(text), size)]


def _snapshot(hub: TickHub) -> list[Any]:
    async def take() -> list[Any]:
        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        return snapshot

    return asyncio.run(take())


def _fallback(backend: StubTocBackend) -> Any:
    return lambda: backend.report(**INPUTS)[0]


# --- A11: the streamed call and its frames ------------------------------------------


def test_a_streamed_report_fills_each_part_in_the_order_written(hub: TickHub) -> None:
    emitter = FakeEmitter()
    frames = _frames(emitter)
    backend = StubTocBackend({"report": [RESPONSE]})
    result = write_streamed(backend, INPUTS, frames, UsageAccumulator(), _fallback(backend))
    assert result == RESPONSE
    assert backend.calls["report_stream"] == 1 and backend.calls["report"] == 1
    # The skeleton names the parts in page order; the header parts carry no heading.
    assert emitter.log[0] == (
        "skeleton",
        [
            "",
            "Mixed evidence",
            "",
            "",
            "Summary",
            "Pathways",
            "How it could fail",
            "What to test first",
            "How it could be expanded",
            "Supporting activities",
            "Assumptions",
            "References",
        ],
    )
    # The verdict is known before the call; then each part closes in the order written.
    assert emitter.completed() == [
        INDEX["verdict"],
        INDEX["title"],
        INDEX["in_brief"],
        INDEX["question"],
        INDEX["summary"],
        INDEX["pathways"],
        INDEX["how_it_could_fail"],
        INDEX["assumptions"],
        INDEX["found_routes"],
        INDEX["supporting_activities"],
        INDEX["tests"],
        INDEX["references"],
    ]
    # Text parts stream as deltas, list parts as one card per item, each in its place.
    written = [m.index for m in _sent(hub) if isinstance(m, SectionDelta | SectionCard)]
    assert list(dict.fromkeys(written)) == [
        INDEX["title"],
        INDEX["in_brief"],
        INDEX["summary"],
        INDEX["question"],
        INDEX["pathways"],
        INDEX["how_it_could_fail"],
        INDEX["assumptions"],
        INDEX["found_routes"],
        INDEX["supporting_activities"],
        INDEX["tests"],
    ]
    cards = [(m.index, m.title, m.prose) for m in _sent(hub) if isinstance(m, SectionCard)]
    assert (INDEX["found_routes"], "Schools", "Schools act too [3].") in cards
    assert (INDEX["supporting_activities"], "", "Training") in cards
    # Each completed part holds what the whole answer gives it; the verdict its headline.
    completed = {entry[1]: entry[2] for entry in emitter.log if entry[0] == "completed"}
    expected = part_texts(RESPONSE, PARTS, ROUTES)
    assert {i: completed[i] for i in expected} == expected
    assert completed[INDEX["verdict"]] == "It may work, but one step is thin."
    assert completed[INDEX["summary"]] == (
        "London limited adverts in 2019 [1]. This report asks whether the limits cut obesity."
        "\n\nIf adverts fall, then children buy less, because cues drop [2]."
        "\n\nPurchases fell [12] but #2 is thin."
    )
    assert completed[INDEX["references"]] == ""
    # The numbered sources travel on the sources frame, so a pending [n] can name its source.
    shown = [m for m in _sent(hub) if isinstance(m, SectionSources)]
    assert shown and shown[0].sources == tuple(SOURCES)
    # No claim check in this pass: nothing but deltas, cards and sources for the parts.
    assert {type(m).__name__ for m in _sent(hub)} <= {
        "SectionDelta",
        "SectionCard",
        "SectionSources",
    }


def test_a_marker_split_across_pieces_is_held_until_it_closes(hub: TickHub) -> None:
    frames = _frames()
    frames.start()
    text = RESPONSE.model_dump_json()
    # Cut inside "[12]" and inside "#2" of the summary field.
    at_cite = text.index("[12]") + 2
    at_code = text.index("#2") + 1
    for piece in (text[:at_code], text[at_code:at_cite], text[at_cite:]):
        frames.feed(piece)
    frames.finish()
    deltas = [m for m in _sent(hub) if isinstance(m, SectionDelta) and m.mode == "append"]
    in_brief = [m.text for m in deltas if m.index == INDEX["in_brief"]]
    assert "".join(in_brief) == RESPONSE.summary
    # No piece ever ends inside a marker.
    assert not any(piece.endswith(("[", "[1", "#")) for piece in in_brief)


def test_a_failure_mid_stream_resets_the_page_and_falls_back_once(hub: TickHub) -> None:
    emitter = FakeEmitter()
    text = RESPONSE.model_dump_json()
    backend = StubTocBackend(
        {"report_stream": [[*_pieces(text[:200]), RuntimeError("stream dropped")]]}
    )
    result = write_streamed(
        backend, INPUTS, _frames(emitter), UsageAccumulator(), _fallback(backend)
    )
    # The fallback is the ordinary call: here the stub's own report.
    assert result is not None and backend.calls["report"] == 1
    skeletons = [i for i, entry in enumerate(emitter.log) if entry[0] == "skeleton"]
    assert len(skeletons) == 2
    sent = _sent(hub)
    # Every part is emptied, then the fallback's text arrives as one replace per part.
    replaces = [m for m in sent if isinstance(m, SectionDelta) and m.mode == "replace"]
    empties = [m.index for m in replaces if m.text == ""]
    assert set(empties) >= {part.index for part in PARTS}
    whole = part_texts(result, PARTS, ROUTES)
    last = {m.index: m.text for m in replaces}
    assert {i: last[i] for i in whole} == whole
    # After the fresh skeleton, every part completes once.
    after = emitter.log[skeletons[1] :]
    assert sorted(entry[1] for entry in after if entry[0] == "completed") == [
        part.index for part in PARTS
    ]


def test_no_first_content_in_time_falls_back(hub: TickHub, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report_stream, "first_content_limit", lambda: 0.05)

    def stalled() -> Iterator[str]:
        time.sleep(1.0)
        yield RESPONSE.model_dump_json()

    emitter = FakeEmitter()
    backend = StubTocBackend({"report_stream": [stalled], "report": [RESPONSE]})
    started = time.monotonic()
    result = write_streamed(
        backend, INPUTS, _frames(emitter), UsageAccumulator(), _fallback(backend)
    )
    assert time.monotonic() - started < 0.8
    assert result == RESPONSE and backend.calls["report"] == 1
    assert sum(1 for entry in emitter.log if entry[0] == "skeleton") == 2


def test_the_route_file_sets_the_first_content_limit() -> None:
    limit = report_stream.first_content_limit()
    assert limit is not None and 0 < limit < 300


def test_a_reconnect_after_two_closed_fields_gets_them_back(hub: TickHub) -> None:
    emitter = FakeEmitter()
    frames = _frames(emitter)
    frames.start()
    text = RESPONSE.model_dump_json()
    # Stop inside the context: the title and the summary line have closed.
    frames.feed(text[: text.index("in 2019")])
    # The saved frames a reconnect replays: the verdict, then the two closed fields.
    assert emitter.completed() == [INDEX["verdict"], INDEX["title"], INDEX["in_brief"]]
    replayed = {entry[1]: entry[2] for entry in emitter.log if entry[0] == "completed"}
    assert replayed[INDEX["title"]] == RESPONSE.title
    assert replayed[INDEX["in_brief"]] == RESPONSE.summary
    # The live part comes from the hub: its text so far, with the sources.
    snapshot = _snapshot(hub)
    drafts = [m for m in snapshot if isinstance(m, SectionDelta)]
    assert [(m.index, m.mode, m.text) for m in drafts] == [
        (INDEX["summary"], "replace", "London limited adverts ")
    ]
    assert any(isinstance(m, SectionSources) and m.index == INDEX["summary"] for m in snapshot)


def test_the_summary_keeps_its_text_when_the_question_streams_between(hub: TickHub) -> None:
    frames = _frames()
    frames.start()
    text = RESPONSE.model_dump_json()
    frames.feed(text[: text.index("If adverts")])
    # The question has closed into the header and joined the Summary: the hub's draft
    # is the Summary again, with all of its text so far.
    snapshot = _snapshot(hub)
    drafts = [m for m in snapshot if isinstance(m, SectionDelta)]
    assert [(m.index, m.text) for m in drafts] == [
        (INDEX["summary"], f"{RESPONSE.context} {RESPONSE.question}")
    ]


def test_the_stream_usage_is_recorded(hub: TickHub) -> None:
    class Backend:
        def report_stream(self, **kwargs: Any) -> Any:
            kwargs["on_text"](RESPONSE.model_dump_json())
            return RESPONSE, report_stream_usage()

    usage = UsageAccumulator()
    write_streamed(Backend(), INPUTS, _frames(), usage, lambda: None)
    assert usage.payload()["completion"] == 7


def report_stream_usage() -> Any:
    from policy_atlas.core.usage import token_usage_from_provider

    return token_usage_from_provider(
        SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
    )


# --- A12: the streamed request and payload equal today's ------------------------------


class _FakeCompletions:
    def __init__(self, text: str) -> None:
        self.text = text
        self.parse_kwargs: dict[str, Any] = {}
        self.create_kwargs: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> Any:
        self.parse_kwargs = kwargs
        parsed = ReportResponse.model_validate_json(self.text)
        message = SimpleNamespace(parsed=parsed)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    def create(self, **kwargs: Any) -> Any:
        self.create_kwargs = kwargs
        chunks = [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=piece))], usage=None
            )
            for piece in _pieces(self.text, 11)
        ]
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=40, total_tokens=140)
        return iter([*chunks, SimpleNamespace(choices=[], usage=usage)])


def test_the_streamed_request_is_todays_request_streamed() -> None:
    backend = OpenAITocBackend(api_key="test-key")
    completions = _FakeCompletions(RESPONSE.model_dump_json())
    backend._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))  # type: ignore[assignment]
    parsed, _ = backend.report(**INPUTS)
    pieces: list[str] = []
    streamed, usage = backend.report_stream(**INPUTS, on_text=pieces.append, first_content_s=None)
    assert streamed == parsed == RESPONSE
    assert "".join(pieces) == RESPONSE.model_dump_json()
    assert usage is not None and usage.completion == 40
    sent = dict(completions.create_kwargs)
    assert sent.pop("stream") is True
    assert sent.pop("stream_options") == {"include_usage": True}
    today = dict(completions.parse_kwargs)
    # ``parse`` turns the wire into this strict JSON schema before it sends it.
    today["response_format"] = type_to_response_format_param(today["response_format"])
    assert sent == today


def _report_context(engine: Engine, task_id: uuid.UUID) -> tuple[uuid.UUID, ScopeContext]:
    """The run id and intent record of the task's stored report step."""
    with engine.connect() as conn:
        run_id = conn.execute(
            select(event_log.c.run_id)
            .where(event_log.c.task_id == task_id)
            .where(event_log.c.event_type == "component.completed")
            .where(event_log.c.payload["component"].astext == "toc_report")
            .order_by(event_log.c.sequence.desc())
            .limit(1)
        ).scalar_one()
    scope = [walk for walk in _walks(engine, task_id) if walk.context.get("toc_walk") == "check"][
        -1
    ]
    return run_id, ScopeContext(
        scope_id=scope.evidence_scope_id, intent=scope.intent, context=dict(scope.context)
    )


def test_a_streamed_report_is_stored_as_the_same_answer_unstreamed(
    engine: Engine, cleanup: list[uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The first report streams (the stub sends its answer in pieces) and saves its frames.
    backend = StubTocBackend()
    task_id = _run(engine, cleanup, backend)
    assert backend.calls["report_stream"] == 1
    stored = _summary(engine, task_id, "toc_report")
    with engine.connect() as conn:
        kinds = [
            row.event_type
            for row in conn.execute(
                select(event_log.c.event_type)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type.like("artefact.%"))
                .order_by(event_log.c.sequence)
            )
        ]
    assert kinds[0] == "artefact.skeleton" and kinds.count("artefact.skeleton") == 1
    assert "artefact.section_completed" in kinds

    # The same answer, made by the ordinary call on the same task: a report now
    # exists, so the step does not stream (A22) and publishes no section frames.
    published: list[Any] = []
    for name in ("publish_section_delta", "publish_section_card", "publish_section_sources"):
        monkeypatch.setattr(liveness, name, lambda *args, **kwargs: published.append(args))
    run_id, context = _report_context(engine, task_id)
    with engine.connect() as conn:
        assert not streams_to_page(conn, task_id=task_id, context=context)
        again = toc_report_scope(
            conn,
            task_id=task_id,
            run_id=run_id,
            context=context,
            backend=backend,
            progress=None,
        )
        conn.rollback()
    assert backend.calls["report_stream"] == 1 and published == []
    # The runner adds its own two keys to the stored payload; the date line may differ.
    for key in ("component", "wall_clock_s"):
        stored.pop(key)
    stored["report"].pop("method")
    again["report"].pop("method")
    assert again == stored


def test_only_a_first_report_streams(engine: Engine, cleanup: list[uuid.UUID]) -> None:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    scope = plan_row["evidence_scope_id"]
    check = ScopeContext(scope_id=scope, intent="q", context={"toc_walk": "check"})
    update = ScopeContext(
        scope_id=scope, intent="q", context={"toc_walk": "check", "mode": "report"}
    )
    with engine.connect() as conn:
        # No report yet: a check's report streams; "Update the report" never does.
        assert streams_to_page(conn, task_id=task_id, context=check)
        assert not streams_to_page(conn, task_id=task_id, context=update)
