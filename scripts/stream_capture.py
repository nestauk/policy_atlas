#!/usr/bin/env python3
"""Record a task's live event stream to a file, one line per thing received (task 058, N25).

What this is for
----------------
The web page learns what a run is doing from one long-lived HTTP response, the
*event stream* (Server-Sent Events, SSE: a plain-text format where the server keeps
the connection open and writes small blocks of text as things happen). Task 058
measures how long the page goes without being told anything (a *silent gap*). To
measure that, we need a timestamped record of everything the page would have
received. This script is that record keeper: it connects to the task's stream the
same way the browser does, and writes one JSON object per line to a file for

- every **frame** (a block with an ``event:`` name and a ``data:`` body): the durable
  ones, which carry an ``id:`` line, and the ephemeral ones (``tick``,
  ``artefact.section_delta``, ``artefact.section_revising``,
  ``artefact.section_sources``, ``artefact.section_claim``,
  ``artefact.section_card``, ``artefact.source_note``), which do not;
- every **comment** (a line starting with ``:``; the server sends ``: keep-alive``
  so that proxies do not close an idle connection);
- every **reconnect** (the connection dropped and the script connected again).

Each line looks like::

    {"received_at": "2026-11-05T10:00:05.123Z", "kind": "frame", "event": "tick",
     "id": null, "data": {...the frame's JSON...}}

``received_at`` is this machine's clock (UTC, milliseconds) when the block arrived.
``kind`` is ``frame``, ``comment`` or ``reconnect``. ``id`` is the frame's ``id:``
value (an integer) or ``null``. ``data`` is the parsed JSON body, or ``null``. A
comment line also carries ``text`` (for example ``"keep-alive"``); a frame whose body
is not JSON carries ``raw`` (the text) with ``data`` null; a reconnect line carries
``data: {"cursor": <n>, "reason": "..."}``. The numbers (silent gaps and the rest)
are computed afterwards from this file by ``scripts/stage_walls.py --capture``.

How it behaves
--------------
- It only reads: ``GET {api}/api/v1/tasks/{task_id}/events?cursor=0`` with a bearer
  token. ``cursor=0`` means "replay the task's whole history first, then go live", so
  the first lines may be old frames arriving in one burst.
- If the connection drops (network error, server restart, no bytes for 60 s), it
  writes a ``reconnect`` line and connects again with ``cursor=<last id seen>``, the
  same resume rule the browser uses, so no durable frame is lost or repeated.
  Ephemeral frames have no id and are never replayed; what was sent while
  disconnected is gone, which is the point of recording it.
- ``--until-terminal`` stops after the run's final ``run.status`` frame (status
  ``succeeded``, ``degraded``, ``failed``, ``aborted`` or ``interrupted``). Two
  refinements keep it from stopping early: the run followed is the one the page
  follows (a ``run.status`` for another run while the followed run is still running
  or paused is a child run, such as an Options scoping option search, and its end
  is ignored), and a final status that happened before the capture started (an
  earlier run, replayed from history) is ignored.
- ``--timeout-s`` is an overall deadline; the script stops when it passes.
- Exit code 0 when it stopped as asked (the final status was seen, or the deadline
  passed without ``--until-terminal``); 1 when it gave up (the server refused the
  token or the task, or the deadline came first under ``--until-terminal``).

Usage
-----
Mint a dev token first (the local stack's own sign-in issuer; ``make dev`` creates
``backend/.dev-issuer``). From the repository root::

    TOKEN=$(cd backend && uv run python -m policy_atlas.api.dev_issuer mint \\
        --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev --ttl 7200)
    export TOKEN
    python3 scripts/stream_capture.py --task-id <task uuid> --token-env TOKEN \\
        --out /path/to/run.capture.jsonl --until-terminal --timeout-s 7200

``--sub`` must be the user who owns the task. ``--api`` defaults to the local API
(``http://127.0.0.1:8000``); point it at staging for a staging capture, with a
token that staging accepts. Standard library only: no package to install.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, TextIO

#: ``run.status`` values that end a run.
TERMINAL_STATUSES = frozenset({"succeeded", "degraded", "failed", "aborted", "interrupted"})
#: Seconds without a single byte before the connection is treated as dead. The
#: server writes a keep-alive comment every 15 s and a heartbeat tick every 10 s
#: while a model call runs, so a minute of silence is a broken connection.
READ_TIMEOUT_S = 60.0
#: Longest wait between reconnect attempts (the wait doubles from 1 s up to this).
MAX_BACKOFF_S = 10.0


class FatalStreamError(RuntimeError):
    """The server refused the request in a way a retry will not fix (401, 403, 404)."""


# --- Parsing the event stream -----------------------------------------------------


def _parse_id(value: str) -> int | str | None:
    value = value.strip()
    if not value:
        return None
    return int(value) if value.isdigit() else value


class SseParser:
    """Turn the stream's bytes into frame and comment records, chunk by chunk.

    Bytes arrive in arbitrary pieces (a line, or a frame, can be split across two
    reads), so the parser keeps the unfinished tail between calls to :meth:`feed`.
    Lines end in ``\\n`` (a trailing ``\\r`` is dropped). Inside a frame, ``event:``
    sets its name, ``id:`` its id, and each ``data:`` line adds one line of body
    (several are joined with ``\\n``, as the SSE standard says); a blank line ends
    the frame. A frame with no ``data:`` line is dropped, as a browser drops it.
    """

    def __init__(self) -> None:
        self._buffer = b""
        self._event: str | None = None
        self._id: int | str | None = None
        self._data: list[str] = []

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        """Consume a chunk of bytes and return the records it completed.

        Args:
            chunk: Bytes read from the response body.

        Returns:
            Records without ``received_at``: ``{"kind": "frame", "event", "id",
            "data"}`` (plus ``raw`` when the body is not JSON) or ``{"kind":
            "comment", "event": None, "id": None, "data": None, "text"}``.
        """
        self._buffer += chunk
        out: list[dict[str, Any]] = []
        while b"\n" in self._buffer:
            raw, self._buffer = self._buffer.split(b"\n", 1)
            line = raw.decode("utf-8", errors="replace").removesuffix("\r")
            record = self._line(line)
            if record is not None:
                out.append(record)
        return out

    def _line(self, line: str) -> dict[str, Any] | None:
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            text = line[1:].strip()
            return {"kind": "comment", "event": None, "id": None, "data": None, "text": text}
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "event":
            self._event = value
        elif field == "id":
            self._id = _parse_id(value)
        elif field == "data":
            self._data.append(value)
        return None  # ``retry:`` and unknown fields are ignored, as a browser does.

    def _dispatch(self) -> dict[str, Any] | None:
        event, frame_id, data = self._event, self._id, self._data
        self._event, self._id, self._data = None, None, []
        if not data:
            return None
        body = "\n".join(data)
        record: dict[str, Any] = {"kind": "frame", "event": event, "id": frame_id}
        try:
            record["data"] = json.loads(body)
        except json.JSONDecodeError:
            record["data"] = None
            record["raw"] = body
        return record


# --- Following the run ------------------------------------------------------------


def new_walk_state() -> dict[str, Any]:
    """An empty record of which run the page follows (see :func:`track_walk`)."""
    return {"walk": None, "status": None, "children": set()}


def track_walk(state: dict[str, Any], data: dict[str, Any]) -> bool:
    """Fold one ``run.status`` body into ``state``; say whether it is the followed run's.

    The same rule as the web client's store (``frontend/src/store/reducer.ts``): a
    ``run.status`` for a different run while the followed run is running or paused,
    or for a run already seen as a child, is a child run's (an option search in
    Options scoping). Any other ``run.status`` makes its run the followed one.

    Args:
        state: From :func:`new_walk_state`; updated in place.
        data: The ``run.status`` frame's body.

    Returns:
        True when the frame belongs to the followed run (after this frame).
    """
    run_id = data.get("capability_run_id")
    walk = state["walk"]
    if run_id in state["children"] or (
        walk is not None and run_id != walk and state["status"] in ("running", "paused")
    ):
        state["children"].add(run_id)
        return False
    state["walk"], state["status"] = run_id, data.get("status")
    return True


def is_final_status(
    record: dict[str, Any], state: dict[str, Any], capture_started: datetime
) -> bool:
    """Whether ``record`` is the followed run's final status, live (not from history).

    Folds ``run.status`` frames into ``state`` as a side effect, so call it once per
    record in arrival order.

    Args:
        record: A parsed record from :class:`SseParser`.
        state: From :func:`new_walk_state`.
        capture_started: When the capture began; a final status that happened
            before it was replayed from an earlier run.

    Returns:
        True when ``--until-terminal`` should stop after this record.
    """
    data = record.get("data")
    if record.get("kind") != "frame" or record.get("event") != "run.status":
        return False
    if not isinstance(data, dict) or not track_walk(state, data):
        return False
    if data.get("status") not in TERMINAL_STATUSES:
        return False
    occurred = data.get("occurred_at")
    if isinstance(occurred, str):
        try:
            when = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
        except ValueError:
            return True
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return when >= capture_started
    return True


# --- The capture loop -------------------------------------------------------------


def utc_stamp(moment: datetime) -> str:
    """ISO 8601 UTC with milliseconds and a ``Z``, e.g. ``2026-11-05T10:00:05.123Z``."""
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def events_url(api: str, task_id: str, cursor: int) -> str:
    """The stream's address for ``task_id``, resuming after ``cursor``."""
    query = urllib.parse.urlencode({"cursor": cursor})
    return f"{api.rstrip('/')}/api/v1/tasks/{urllib.parse.quote(task_id)}/events?{query}"


def run_capture(
    open_stream: Callable[[int], Iterable[bytes]],
    out: TextIO,
    *,
    until_terminal: bool,
    timeout_s: float,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Read the stream, write one JSON line per record, reconnect on drops.

    Args:
        open_stream: Opens the stream at a cursor and yields its body in chunks;
            it may raise (``OSError``, ``urllib.error.URLError``,
            ``http.client.HTTPException``) when the connection fails or drops,
            or :class:`FatalStreamError` to give up.
        out: Where the JSON lines go (flushed after every line, so a killed
            capture keeps everything written so far).
        until_terminal: Stop after the followed run's final ``run.status``.
        timeout_s: Overall deadline in seconds.
        now: Clock (tests pass a fake one).
        sleep: Waits between reconnects (tests pass a fake one).

    Returns:
        ``{"stopped": "terminal" | "timeout" | "fatal", "cursor", "lines",
        "reconnects", "error"}``.
    """
    started = now()
    state = new_walk_state()
    cursor = 0
    lines = reconnects = failures = 0
    error: str | None = None

    def write(record: dict[str, Any], at: datetime) -> None:
        nonlocal lines
        out.write(json.dumps({"received_at": utc_stamp(at), **record}) + "\n")
        out.flush()
        lines += 1

    while True:
        if (now() - started).total_seconds() >= timeout_s:
            stopped = "timeout"
            break
        parser = SseParser()
        reason = "the server ended the response"
        try:
            for chunk in open_stream(cursor):
                if chunk:
                    failures = 0
                at = now()
                for record in parser.feed(chunk):
                    write(record, at)
                    if isinstance(record.get("id"), int):
                        cursor = record["id"]
                    if is_final_status(record, state, started) and until_terminal:
                        return _result("terminal", cursor, lines, reconnects, None)
                if (at - started).total_seconds() >= timeout_s:
                    break
        except FatalStreamError as exc:
            error = str(exc)
            stopped = "fatal"
            break
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            reason = f"{type(exc).__name__}: {exc}"
        if (now() - started).total_seconds() >= timeout_s:
            stopped = "timeout"
            break
        reconnects += 1
        failures += 1
        write({"kind": "reconnect", "event": None, "id": None,
               "data": {"cursor": cursor, "reason": reason}}, now())
        sleep(min(2.0 ** (failures - 1), MAX_BACKOFF_S))
    return _result(stopped, cursor, lines, reconnects, error)


def _result(
    stopped: str, cursor: int, lines: int, reconnects: int, error: str | None
) -> dict[str, Any]:
    return {
        "stopped": stopped,
        "cursor": cursor,
        "lines": lines,
        "reconnects": reconnects,
        "error": error,
    }


def http_stream(
    api: str, task_id: str, token: str, *, deadline: float
) -> Callable[[int], Iterator[bytes]]:
    """The real :func:`run_capture` opener: an HTTP GET read as it arrives.

    Args:
        api: Base address of the API.
        task_id: The task whose stream is read.
        token: Bearer token.
        deadline: ``time.monotonic()`` value after which reads stop waiting.

    Returns:
        A function from cursor to an iterator of body chunks.
    """

    def open_stream(cursor: int) -> Iterator[bytes]:
        request = urllib.request.Request(
            events_url(api, task_id, cursor),
            headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
        )
        read_timeout = max(1.0, min(READ_TIMEOUT_S, deadline - time.monotonic()))
        try:
            response = urllib.request.urlopen(request, timeout=read_timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403, 404, 422):
                raise FatalStreamError(f"HTTP {exc.code} from the events endpoint") from exc
            raise
        with response:
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    return
                yield chunk

    return open_stream


# --- Command line -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Record a task's event stream, one JSON line per frame, comment or "
        "reconnect (read-only). See the module docstring."
    )
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="API base address")
    parser.add_argument("--task-id", required=True, help="task uuid")
    parser.add_argument(
        "--token-env",
        required=True,
        metavar="NAME",
        help="name of the environment variable that holds the bearer token",
    )
    parser.add_argument("--out", required=True, help="the .jsonl file to write")
    parser.add_argument(
        "--until-terminal", action="store_true", help="stop after the run's final run.status"
    )
    parser.add_argument("--timeout-s", type=float, default=7200.0, help="overall deadline")
    args = parser.parse_args(argv)
    bearer = os.environ.get(args.token_env, "")
    if not bearer:
        parser.error(f"${args.token_env} is empty or unset")
    deadline = time.monotonic() + args.timeout_s
    with open(args.out, "w", encoding="utf-8") as out:
        result = run_capture(
            http_stream(args.api, args.task_id, bearer, deadline=deadline),
            out,
            until_terminal=args.until_terminal,
            timeout_s=args.timeout_s,
        )
    print(
        f"stream_capture: stopped ({result['stopped']}); {result['lines']} lines, "
        f"{result['reconnects']} reconnects, last cursor {result['cursor']}"
        + (f"; {result['error']}" if result["error"] else ""),
        file=sys.stderr,
    )
    gave_up = result["stopped"] == "fatal" or (
        args.until_terminal and result["stopped"] != "terminal"
    )
    return 1 if gave_up else 0


if __name__ == "__main__":
    raise SystemExit(main())
