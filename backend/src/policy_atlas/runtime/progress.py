"""Durable presentation-progress events for long-running components."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from sqlalchemy.engine import Engine

from policy_atlas.core import events

log = structlog.get_logger()


class ProgressEmitter:
    """Append synthesis presentation events in independent transactions.

    The emitter deliberately has no access to the component connection.  Its
    records are live UI progress, not artefact-of-record writes, and therefore
    must remain visible if the component transaction later rolls back.

    Args:
        engine: Database engine used for one short transaction per event.
        task_id: Owning task.
        run_id: Synthesise component run.
    """

    def __init__(self, engine: Engine, *, task_id: uuid.UUID, run_id: uuid.UUID) -> None:
        self._engine = engine
        self._task_id = task_id
        self._run_id = run_id
        self._sections_by_synthesis_index: list[dict[str, Any]] = []
        self._key_findings: dict[str, Any] | None = None
        self._disabled = False

    def emit_skeleton(self, sections: Sequence[dict[str, str]]) -> None:
        """Emit the presentation-ordered skeleton and establish display indexes.

        Args:
            sections: Non-key-findings sections in synthesis order, including
                the code-injected conclusion foot.

        Raises:
            RuntimeError: If a skeleton was already emitted for this emitter.
        """
        if self._key_findings is not None:
            raise RuntimeError("synthesis progress skeleton already emitted")
        self._key_findings = {
            "index": 0,
            "title": "Key findings",
            "focus": "The report's headline claims.",
        }
        self._sections_by_synthesis_index = [
            {"index": index, "title": section["title"], "focus": section["focus"]}
            for index, section in enumerate(sections, start=1)
        ]
        self._append(
            "artefact.skeleton",
            {"sections": [self._key_findings, *self._sections_by_synthesis_index]},
        )

    def section_started(self, synthesis_index: int) -> None:
        """Record that a normal section has begun generation.

        Args:
            synthesis_index: Zero-based position in the generation loop.
        """
        payload = self._compose(lambda: {"index": self._section(synthesis_index)["index"]})
        if payload is not None:
            self._append("artefact.section_started", payload)

    def section_completed(self, synthesis_index: int, *, prose: str) -> None:
        """Record a normal section after its artefact write.

        Args:
            synthesis_index: Zero-based position in the generation loop.
            prose: Final whole-section prose shown by the live view.
        """
        payload = self._compose(
            lambda: {
                "index": self._section(synthesis_index)["index"],
                "title": self._section(synthesis_index)["title"],
                "prose": prose,
            }
        )
        if payload is not None:
            self._append("artefact.section_completed", payload)

    def key_findings_started(self) -> None:
        """Record the final-generated, first-presented key-findings pass."""
        payload = self._compose(lambda: {"index": self._key_findings_section()["index"]})
        if payload is not None:
            self._append("artefact.section_started", payload)

    def key_findings_completed(self, *, prose: str) -> None:
        """Close the key-findings slot, including the intentional empty case.

        Args:
            prose: Generated prose, or an empty string when no key-findings
                block was warranted.
        """
        payload = self._compose(
            lambda: {
                "index": self._key_findings_section()["index"],
                "title": self._key_findings_section()["title"],
                "prose": prose,
            }
        )
        if payload is not None:
            self._append("artefact.section_completed", payload)

    def _compose(self, build: Any) -> dict[str, Any] | None:
        """Build an event payload, degrading (never raising) on skeleton drift."""
        if self._disabled:
            return None
        try:
            return dict(build())
        except RuntimeError:
            self._disabled = True
            log.warning(
                "synthesis_progress_skeleton_inconsistent",
                run_id=str(self._run_id),
                exc_info=True,
            )
            return None

    def _section(self, synthesis_index: int) -> dict[str, Any]:
        try:
            return self._sections_by_synthesis_index[synthesis_index]
        except IndexError as exc:
            raise RuntimeError("synthesis progress section is not in the skeleton") from exc

    def _key_findings_section(self) -> dict[str, Any]:
        if self._key_findings is None:
            raise RuntimeError("synthesis progress skeleton has not been emitted")
        return self._key_findings

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        # Presentation records must never fail the walk (ADR 0027 decision 5):
        # a DB error on a progress append degrades the live view, not the run.
        # First failure disables further emission — the live stream is already
        # incoherent past a gap, and retry noise helps nobody.
        if self._disabled:
            return
        try:
            with self._engine.begin() as conn:
                events.append(
                    conn,
                    task_id=self._task_id,
                    run_id=self._run_id,
                    event_type=event_type,
                    payload=payload,
                )
        except Exception:
            self._disabled = True
            log.warning(
                "synthesis_progress_emission_failed",
                run_id=str(self._run_id),
                event_type=event_type,
                exc_info=True,
            )
