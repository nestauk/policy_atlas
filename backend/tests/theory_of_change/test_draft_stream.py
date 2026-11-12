"""The theory of change's first draft is drawn on the page as it is written (task 054, S12).

A scripted stream (the stub backend's ``draft_stream`` queue, or a fake OpenAI
client) drives the live sketch: each box, then each connection, as it closes;
the reset and the ordinary call when the stream fails or is late; the reset
before a draft that failed its checks is written again; the reconnect
snapshot; and the equality of the streamed and non-streamed paths.
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
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.sse import _encode_ephemeral
from policy_atlas.core import liveness
from policy_atlas.core.liveness import TickHub, TocSketch
from policy_atlas.runtime.runner import NullIO, RunnerBackends, run_plan
from policy_atlas.runtime.toc_plan import TocPlan
from policy_atlas.theory_of_change import draft_stream, store
from policy_atlas.theory_of_change.backend import OpenAITocBackend, StubTocBackend, stub_draft
from policy_atlas.theory_of_change.draft_prompt import DraftResponse
from policy_atlas.theory_of_change.draft_stream import SketchFrames, draft_streamed
from tests.theory_of_change.test_walks import seed_toc, toc_plan

TASK = uuid.UUID(int=12)
DRAFT = stub_draft({"intervention": "a junk-food advertising ban"})
INPUTS: dict[str, Any] = {"plan": {}, "existing_theory": None, "problems": None}


def _boxes(draft: DraftResponse) -> list[tuple[str, str, str]]:
    return [(box.key, box.layer, box.text) for box in draft.boxes]


def _links(draft: DraftResponse) -> list[tuple[str, str, str]]:
    return [(link.key, link.source, link.target) for link in draft.links]


def _pieces(text: str, size: int = 9) -> list[str]:
    return [text[at : at + size] for at in range(0, len(text), size)]


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> Iterator[TickHub]:
    """A fresh live hub, its messages recorded; bound to TASK under the draft's stage."""
    fresh = TickHub(schedule=None)
    sent: list[Any] = []
    real = fresh._fan_out

    def record(task_id: uuid.UUID, message: Any) -> None:
        sent.append(message)
        real(task_id, message)

    monkeypatch.setattr(fresh, "_fan_out", record)
    monkeypatch.setattr(liveness, "tick_hub", fresh)
    fresh.sent = sent  # type: ignore[attr-defined]
    with liveness.task_liveness(TASK, stage="toc_draft"):
        yield fresh


def _sketches(hub: TickHub) -> list[TocSketch]:
    return [m for m in hub.sent if isinstance(m, TocSketch)]  # type: ignore[attr-defined]


def _counts(hub: TickHub) -> list[tuple[int, int]]:
    return [(len(m.boxes), len(m.links)) for m in _sketches(hub)]


def _snapshot(hub: TickHub, task_id: uuid.UUID = TASK) -> list[Any]:
    async def take() -> list[Any]:
        queue, snapshot = await hub.subscribe_with_snapshot(task_id)
        await hub.unsubscribe(task_id, queue)
        return snapshot

    return asyncio.run(take())


# --- the stream and its frames ------------------------------------------------------


def test_a_streamed_draft_draws_each_box_then_each_connection_as_it_closes(
    hub: TickHub,
) -> None:
    backend = StubTocBackend({"draft": [DRAFT]})
    frames = SketchFrames()
    result, _ = draft_streamed(backend, **INPUTS, frames=frames)
    assert result == DRAFT
    assert backend.calls["draft_stream"] == 1 and backend.calls["draft"] == 1
    # One frame per closed box, then one per closed connection, each the whole sketch.
    n_boxes, n_links = len(DRAFT.boxes), len(DRAFT.links)
    assert _counts(hub) == [(n, 0) for n in range(1, n_boxes + 1)] + [
        (n_boxes, n) for n in range(1, n_links + 1)
    ]
    last = _sketches(hub)[-1]
    assert list(last.boxes) == _boxes(DRAFT) and list(last.links) == _links(DRAFT)
    # A connection is sent only once both of its boxes were.
    for sketch in _sketches(hub):
        keys = {key for key, _layer, _text in sketch.boxes}
        assert all(source in keys and target in keys for _k, source, target in sketch.links)


def test_a_box_split_across_pieces_is_sent_once_it_closes(hub: TickHub) -> None:
    frames = SketchFrames()
    for piece in _pieces(DRAFT.model_dump_json(), size=3):
        frames.feed(piece)
    assert frames.sketch() == (_boxes(DRAFT), _links(DRAFT))
    assert len(_sketches(hub)) == len(DRAFT.boxes) + len(DRAFT.links)


def test_a_failure_mid_stream_resets_the_sketch_and_makes_the_ordinary_call(
    hub: TickHub,
) -> None:
    text = DRAFT.model_dump_json()
    # Fail after the first two boxes have closed.
    cut = text.index('"key":"b3"')
    backend = StubTocBackend(
        {"draft_stream": [[*_pieces(text[:cut]), RuntimeError("stream dropped")]]}
    )
    result, _ = draft_streamed(backend, **INPUTS, frames=SketchFrames())
    # The ordinary call answers: here the stub's own draft.
    assert backend.calls["draft"] == 1 and result.boxes and result.links
    assert _counts(hub) == [(1, 0), (2, 0), (0, 0)]


def test_no_first_content_in_time_resets_and_makes_the_ordinary_call(
    hub: TickHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(draft_stream, "first_content_limit", lambda: 0.05)

    def stalled() -> Iterator[str]:
        time.sleep(1.0)
        yield DRAFT.model_dump_json()

    backend = StubTocBackend({"draft_stream": [stalled], "draft": [DRAFT]})
    started = time.monotonic()
    result, _ = draft_streamed(backend, **INPUTS, frames=SketchFrames())
    assert time.monotonic() - started < 0.8
    assert result == DRAFT and backend.calls["draft"] == 1
    # Nothing was drawn; the page still gets the reset.
    assert _counts(hub) == [(0, 0)]


def test_the_route_file_sets_the_drafts_first_content_limit() -> None:
    limit = draft_stream.first_content_limit()
    assert limit is not None and 0 < limit < 300


def test_a_reconnect_gets_the_sketch_so_far_until_the_stage_ends(hub: TickHub) -> None:
    frames = SketchFrames()
    text = DRAFT.model_dump_json()
    frames.feed(text[: text.index('"key":"l3"')])
    sketches = [m for m in _snapshot(hub) if isinstance(m, TocSketch)]
    assert [(len(m.boxes), len(m.links)) for m in sketches] == [(len(DRAFT.boxes), 2)]
    # Once the draft's stage ends the stored graph is the page's: the sketch is forgotten.
    hub.end_stage(TASK, "toc_draft")
    assert not [m for m in _snapshot(hub) if isinstance(m, TocSketch)]


def test_the_sketch_frame_carries_draft_keys_layers_and_ends() -> None:
    message = TocSketch(
        boxes=(("b1", "input", "Deliver the ban"), ("b2", "output", "Fewer adverts")),
        links=(("l1", "b1", "b2"),),
        occurred_at=liveness._now_utc(),
        stage="toc_draft",
    )
    line = _encode_ephemeral(message)
    assert line.startswith("event: toc.sketch\n")
    assert '"boxes":[{"key":"b1","layer":"input","text":"Deliver the ban"}' in line
    assert '"links":[{"key":"l1","source":"b1","target":"b2"}]' in line
    assert '"ephemeral":true' in line and '"stage"' not in line


# --- the draft step -------------------------------------------------------------------


def _draft_walk(engine: Engine, backend: StubTocBackend, plan: TocPlan | None = None) -> Any:
    task_id, plan_row = seed_toc(engine, plan)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=plan_row["evidence_scope_id"],
        plan=plan or toc_plan(),
        plan_id=plan_row["plan_id"],
        plan_version=plan_row["version"],
        plan_row_id=plan_row["plan_id"],
        backends=RunnerBackends(search_backends=[], toc=backend),
        io=NullIO(),
        session_id=task_id,
    )
    assert outcome.status == "succeeded", outcome
    return task_id


def _stored(engine: Engine, task_id: uuid.UUID) -> Any:
    """The stored graph by content: box texts by layer, links by their ends' texts, pathways."""
    with engine.connect() as conn:
        graph, _rows = store.load_graph(conn, task_id)
    text = {key: box.text for key, box in graph.boxes.items()}
    links = {key: (text[link.source], text[link.target]) for key, link in graph.links.items()}
    return (
        sorted((box.layer, box.text) for box in graph.boxes.values()),
        sorted(links.values()),
        sorted((p.kind, tuple(links[key] for key in p.links)) for p in graph.pathways),
    )


def test_the_stored_graph_is_the_same_streamed_or_not(
    engine: Engine, cleanup: list[uuid.UUID], hub: TickHub
) -> None:
    streamed = StubTocBackend()
    first = _draft_walk(engine, streamed)
    cleanup.append(first)
    assert streamed.calls["draft_stream"] == 1 and streamed.calls["draft"] == 1
    # The same draft through the ordinary call alone (the stream fails at once).
    ordinary = StubTocBackend({"draft_stream": [RuntimeError("no stream")]})
    second = _draft_walk(engine, ordinary)
    cleanup.append(second)
    assert ordinary.calls["draft"] == 1
    assert _stored(engine, first) == _stored(engine, second)
    # The streamed walk drew its whole draft on the page; the sketch is forgotten at the end.
    whole = stub_draft(toc_plan().model_dump())
    drawn = [m for m in _sketches(hub) if len(m.boxes) == len(whole.boxes)]
    assert drawn and len(drawn[-1].links) == len(whole.links)
    assert not [m for m in _snapshot(hub, first) if isinstance(m, TocSketch)]


def test_a_draft_that_fails_its_checks_is_drawn_again_from_the_start(
    engine: Engine, cleanup: list[uuid.UUID], hub: TickHub
) -> None:
    broken = stub_draft({}).model_copy(update={"pathways": []})
    backend = StubTocBackend({"draft": [broken]})
    cleanup.append(_draft_walk(engine, backend))
    assert backend.calls["draft_stream"] == 2
    counts = _counts(hub)
    reset = counts.index((0, 0))
    n_boxes, n_links = len(broken.boxes), len(broken.links)
    # The failed draft was drawn whole, the page was reset, then the retry drawn again.
    assert counts[reset - 1] == (n_boxes, n_links)
    assert counts[reset + 1] == (1, 0) and counts[-1] == (n_boxes, n_links)
    assert counts.count((0, 0)) == 1


def test_a_users_own_diagram_is_not_drawn_live(
    engine: Engine, cleanup: list[uuid.UUID], hub: TickHub
) -> None:
    # The user's theory is kept as drawn: the draft only fills it in, so it is not sketched.
    backend = StubTocBackend()
    cleanup.append(_draft_walk(engine, backend, toc_plan(drawn_on_canvas=True)))
    assert backend.calls["draft_stream"] == 0 and backend.calls["draft"] == 1
    assert _sketches(hub) == []


# --- the streamed request equals today's ---------------------------------------------


class _FakeCompletions:
    def __init__(self, text: str) -> None:
        self.text = text
        self.parse_kwargs: dict[str, Any] = {}
        self.create_kwargs: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> Any:
        self.parse_kwargs = kwargs
        parsed = DraftResponse.model_validate_json(self.text)
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


def test_the_streamed_draft_request_is_todays_request_streamed() -> None:
    backend = OpenAITocBackend(api_key="test-key")
    completions = _FakeCompletions(DRAFT.model_dump_json())
    backend._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))  # type: ignore[assignment]
    inputs = {"plan": {"question": "q"}, "existing_theory": "t", "problems": ["p"]}
    parsed, _ = backend.draft(**inputs)  # type: ignore[arg-type]
    pieces: list[str] = []
    streamed, usage = backend.draft_stream(
        **inputs,  # type: ignore[arg-type]
        on_text=pieces.append,
        first_content_s=None,
    )
    assert streamed == parsed == DRAFT
    assert "".join(pieces) == DRAFT.model_dump_json()
    assert usage is not None and usage.completion == 40
    sent = dict(completions.create_kwargs)
    assert sent.pop("stream") is True
    assert sent.pop("stream_options") == {"include_usage": True}
    today = dict(completions.parse_kwargs)
    today["response_format"] = type_to_response_format_param(today["response_format"])
    assert sent == today


# --- a failed stream's tokens count in the step's cost ---------------------------------


class _BrokenStreamCompletions(_FakeCompletions):
    """The whole answer streams but does not parse; the ordinary call answers."""

    def parse(self, **kwargs: Any) -> Any:
        message = SimpleNamespace(parsed=DRAFT)
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=5, total_tokens=105)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def test_a_stream_that_fails_at_the_parse_still_counts_its_tokens(hub: TickHub) -> None:
    backend = OpenAITocBackend(api_key="test-key")
    # Cut short: every piece arrives, then the text is not a whole DraftResponse.
    completions = _BrokenStreamCompletions(DRAFT.model_dump_json()[:-20])
    backend._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))  # type: ignore[assignment]
    result, usage = draft_streamed(backend, **INPUTS, frames=SketchFrames())
    assert result == DRAFT
    # The stream's 40 completion tokens (paid for) plus the ordinary call's 5.
    assert usage is not None and usage.completion == 45 and usage.prompt == 200


def test_the_streamed_draft_is_traced_under_the_tasks_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    from policy_atlas.core import tracing

    session_id = uuid.uuid4()
    events: list[str] = []

    @contextmanager
    def fake_propagate_attributes(**attributes: Any) -> Iterator[None]:
        events.append(f"session:{attributes.get('session_id')}")
        yield

    @contextmanager
    def fake_observation(_client: Any, *, name: str, as_type: str) -> Iterator[Any]:
        events.append(f"open:{name}")
        yield SimpleNamespace(update=lambda **_kwargs: None)

    monkeypatch.setattr(tracing, "propagate_attributes", fake_propagate_attributes)
    monkeypatch.setattr(tracing, "_observation", fake_observation)
    backend = OpenAITocBackend(
        api_key="test-key",
        langfuse_client=object(),  # type: ignore[arg-type]
        session_id=session_id,
    )
    completions = _FakeCompletions(DRAFT.model_dump_json())
    backend._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))  # type: ignore[assignment]
    streamed, _ = backend.draft_stream(**INPUTS, on_text=lambda _piece: None, first_content_s=None)
    assert streamed == DRAFT
    # The session is set before the generation opens, so the generation carries it.
    assert events == [f"session:{session_id}", "open:toc:draft"]
