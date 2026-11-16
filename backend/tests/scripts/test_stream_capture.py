"""Coverage for the event-stream capture client (`scripts/stream_capture.py`, task 058, N25).

No network: the parser is fed a hand-written SSE byte stream cut at awkward places,
and the capture loop is given a fake stream opener, a fake clock and a fake sleep.
"""

from __future__ import annotations

import importlib.util
import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "stream_capture.py"
WALK = "c0580000-0058-4000-8000-000000000001"
CHILD = "c0580000-0058-4000-8000-0000000000c0"
OLD = "c0580000-0058-4000-8000-0000000000a0"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stream_capture", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sc = _load()

# A replayed durable frame (with id), a tick (no id), a keep-alive comment, a
# frame whose body spans two data lines, one frame with CRLF line ends, and a
# frame with an event name but no data (dropped, as a browser drops it).
_STREAM = (
    b'id: 1\nevent: run.status\ndata: {"type":"run.status","sequence":1,'
    b'"capability_run_id":"' + WALK.encode() + b'","status":"running"}\n\n'
    b'event: tick\ndata: {"type":"tick","stage":"acquire","activity":"Searching",'
    b'"dropped":0}\n\n'
    b": keep-alive\n\n"
    b'id: 2\nevent: stage.started\ndata: {"type":"stage.started",\ndata: "stage":"acquire"}\n\n'
    b'id: 3\r\nevent: stage.completed\r\ndata: {"stage":"acquire","label":"Caf\xc3\xa9"}\r\n\r\n'
    b"event: tick\n\n"
    b"id: 4\nevent: odd\ndata: not json\n\n"
)


def _feed_in_pieces(data: bytes, size: int) -> list[dict[str, Any]]:
    parser = sc.SseParser()
    out: list[dict[str, Any]] = []
    for i in range(0, len(data), size):
        out.extend(parser.feed(data[i : i + size]))
    return out


def test_parser_reads_frames_comments_and_multiline_data() -> None:
    records = _feed_in_pieces(_STREAM, len(_STREAM))
    assert [(r["kind"], r["event"], r["id"]) for r in records] == [
        ("frame", "run.status", 1),
        ("frame", "tick", None),
        ("comment", None, None),
        ("frame", "stage.started", 2),
        ("frame", "stage.completed", 3),
        ("frame", "odd", 4),
    ]
    assert records[1]["data"]["activity"] == "Searching"
    assert records[2] == {
        "kind": "comment",
        "event": None,
        "id": None,
        "data": None,
        "text": "keep-alive",
    }
    # Two data lines are joined with a newline, which JSON reads as whitespace.
    assert records[3]["data"] == {"type": "stage.started", "stage": "acquire"}
    assert records[4]["data"] == {"stage": "acquire", "label": "Café"}
    assert records[5]["data"] is None and records[5]["raw"] == "not json"


@pytest.mark.parametrize("size", [1, 2, 7, 64])
def test_parser_gives_the_same_records_however_the_bytes_are_cut(size: int) -> None:
    assert _feed_in_pieces(_STREAM, size) == _feed_in_pieces(_STREAM, len(_STREAM))


def test_events_url() -> None:
    assert sc.events_url("http://127.0.0.1:8000/", "abc", 17) == (
        "http://127.0.0.1:8000/api/v1/tasks/abc/events?cursor=17"
    )


class _Clock:
    """Starts at 10:00:00 UTC and moves one second per reading."""

    def __init__(self) -> None:
        self.t = datetime(2026, 11, 5, 10, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self.t
        self.t += timedelta(seconds=1)
        return current


def _frame(frame_id: int | None, event: str, data: dict[str, Any]) -> bytes:
    head = f"id: {frame_id}\n" if frame_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n".encode()


def _status(frame_id: int, walk: str, status: str, occurred: str) -> bytes:
    body = {"type": "run.status", "sequence": frame_id, "capability_run_id": walk,
            "status": status, "occurred_at": occurred}
    return _frame(frame_id, "run.status", body)


LIVE = "2026-11-05T10:30:00Z"
HISTORY = "2026-11-04T09:00:00Z"


def _lines(out: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_reconnect_resumes_at_the_last_id() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def open_stream(cursor: int) -> Iterator[bytes]:
        calls.append(cursor)
        if len(calls) == 1:
            yield _status(5, WALK, "running", LIVE)
            yield _frame(None, "tick", {"type": "tick", "activity": "Searching"})
            yield _frame(7, "stage.started", {"stage": "acquire"})
            yield b"event: tick\ndata: {\"half"  # cut off mid-frame
            raise ConnectionResetError("peer went away")
        yield _status(8, WALK, "succeeded", LIVE)

    out = io.StringIO()
    result = sc.run_capture(
        open_stream, out, until_terminal=True, timeout_s=3600, now=_Clock(), sleep=sleeps.append
    )
    assert calls == [0, 7]  # the tick carries no id, so the cursor is the stage frame's
    assert sleeps == [1.0]
    assert result == {
        "stopped": "terminal",
        "cursor": 8,
        "lines": 5,
        "reconnects": 1,
        "error": None,
    }
    lines = _lines(out)
    assert [(line["kind"], line["event"]) for line in lines] == [
        ("frame", "run.status"),
        ("frame", "tick"),
        ("frame", "stage.started"),
        ("reconnect", None),
        ("frame", "run.status"),
    ]
    assert lines[3]["data"] == {"cursor": 7, "reason": "ConnectionResetError: peer went away"}
    # received_at is UTC with milliseconds and a Z.
    assert lines[0]["received_at"] == "2026-11-05T10:00:02.000Z"


def test_terminal_stop_skips_history_and_child_runs() -> None:
    def open_stream(cursor: int) -> Iterator[bytes]:
        # An earlier run, replayed from history: its end is not this run's end.
        yield _status(1, OLD, "running", HISTORY) + _status(2, OLD, "failed", HISTORY)
        yield _status(3, WALK, "running", LIVE)
        # A child run (an option search) ends while the run itself goes on.
        yield _status(4, CHILD, "running", LIVE) + _status(5, CHILD, "succeeded", LIVE)
        yield _status(6, WALK, "degraded", LIVE)
        yield _frame(7, "task.updated", {"name": "never read"})

    out = io.StringIO()
    result = sc.run_capture(
        open_stream, out, until_terminal=True, timeout_s=3600, now=_Clock(), sleep=lambda s: None
    )
    assert result["stopped"] == "terminal" and result["cursor"] == 6
    assert [line["id"] for line in _lines(out)] == [1, 2, 3, 4, 5, 6]


def test_without_until_terminal_it_keeps_going_until_the_deadline() -> None:
    def open_stream(cursor: int) -> Iterator[bytes]:
        yield _status(1, WALK, "running", LIVE)
        yield _status(2, WALK, "succeeded", LIVE)
        yield b": keep-alive\n\n"

    out = io.StringIO()
    result = sc.run_capture(
        open_stream, out, until_terminal=False, timeout_s=10, now=_Clock(), sleep=lambda s: None
    )
    assert result["stopped"] == "timeout"
    kinds = [line["kind"] for line in _lines(out)]
    assert kinds[:3] == ["frame", "frame", "comment"]
    assert "reconnect" in kinds  # the server ended the response; it connected again


def test_a_refused_token_gives_up() -> None:
    def open_stream(cursor: int) -> Iterator[bytes]:
        raise sc.FatalStreamError("HTTP 401 from the events endpoint")
        yield b""  # pragma: no cover

    out = io.StringIO()
    result = sc.run_capture(
        open_stream, out, until_terminal=True, timeout_s=60, now=_Clock(), sleep=lambda s: None
    )
    assert result["stopped"] == "fatal" and result["lines"] == 0
    assert result["error"] == "HTTP 401 from the events endpoint"


def test_backoff_doubles_and_is_capped() -> None:
    sleeps: list[float] = []

    def open_stream(cursor: int) -> Iterator[bytes]:
        raise OSError("connection refused")
        yield b""  # pragma: no cover

    sc.run_capture(
        open_stream,
        io.StringIO(),
        until_terminal=True,
        timeout_s=30,
        now=_Clock(),
        sleep=sleeps.append,
    )
    assert sleeps[:6] == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


def test_token_env_must_be_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("STREAM_CAPTURE_TEST_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        sc.main(
            [
                "--task-id",
                "abc",
                "--token-env",
                "STREAM_CAPTURE_TEST_TOKEN",
                "--out",
                str(tmp_path / "x.jsonl"),
            ]
        )
    assert exc.value.code == 2
    assert not (tmp_path / "x.jsonl").exists()
