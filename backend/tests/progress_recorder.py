"""A recorder for the live-progress lines the stage loops publish (task 058, N2).

``install`` replaces ``policy_atlas.core.liveness.publish_progress`` with a
recorder for the length of one test and returns the recorded calls. It also
gives ``current_stage`` a fixed answer when a test needs one. ``raising=False``
lets this work whether or not the real functions exist yet.
"""

from __future__ import annotations

from typing import Any

import pytest

from policy_atlas.core import liveness


def install(monkeypatch: pytest.MonkeyPatch, *, stage: str | None = None) -> list[dict[str, Any]]:
    """Record every ``publish_progress`` call; return the (growing) list.

    Args:
        monkeypatch: The test's monkeypatch fixture.
        stage: When given, ``current_stage()`` returns it.

    Returns:
        The list each call's keyword arguments are appended to, in order.
    """
    calls: list[dict[str, Any]] = []

    def record(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(liveness, "publish_progress", record, raising=False)
    if stage is not None:
        monkeypatch.setattr(liveness, "current_stage", lambda: stage, raising=False)
    return calls
