"""In-process event bus: one per project. Backlog + fan-out to SSE subscribers.

ponytail: in-memory only — a server restart loses the stream (read models rebuild
from the DB; the pre-run project doesn't need its stream).
"""

import json
import queue
import threading
import time
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self.backlog: list[dict[str, Any]] = []
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "data": payload, "ts": time.time()}
        with self._lock:
            self.backlog.append(event)
            for q in list(self._subscribers):
                q.put(event)

    def subscribe(self) -> tuple[list[dict[str, Any]], queue.Queue]:
        q: queue.Queue = queue.Queue()
        with self._lock:
            backlog = list(self.backlog)
            self._subscribers.append(q)
        return backlog, q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


def sse_format(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
