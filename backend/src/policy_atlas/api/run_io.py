"""Runner IO implementations used by HTTP-dispatched capability walks."""

from __future__ import annotations

from typing import Any

from policy_atlas.runtime.runner import WalkParked


class ParkIO:
    """Persisted-steering disposition for browser-dispatched walks."""

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Ignore component notices; event-log entries remain the transport source.

        Args:
            component: Completed runner component.
            payload: Deterministic check-in data.
        """
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> None:
        """End the executor walk at an attended boundary after runner persistence.

        Args:
            point: Durable steering point payload.
            render: Deterministic check-in rendering.

        Raises:
            WalkParked: Always, signalling the runner's durable park boundary.
        """
        del point, render
        raise WalkParked()

    def confirm(self, render: str) -> bool:
        """Decline interactive confirmation; HTTP free text uses its confirm route."""
        del render
        return False
