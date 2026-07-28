"""Durable presentation-progress events for long-running components."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.engine import Engine

from policy_atlas.core import events


class ProgressEmitter:
    """Append synthesis presentation events in independent transactions.

    The emitter deliberately has no access to the component connection.  Its
    records are live UI progress, not artefact-of-record writes, and therefore
    must remain visible if the component transaction later rolls back.

    Args:
        engine: Database engine used for one short transaction per event.
        project_id: Owning project.
        run_id: Synthesise component run.
    """

    def __init__(self, engine: Engine, *, project_id: uuid.UUID, run_id: uuid.UUID) -> None:
        self._engine = engine
        self._project_id = project_id
        self._run_id = run_id
        self._sections_by_synthesis_index: list[dict[str, Any]] = []
        self._key_findings: dict[str, Any] | None = None

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
        self._append("artefact.section_started", {"index": self._section(synthesis_index)["index"]})

    def section_completed(self, synthesis_index: int, *, prose: str) -> None:
        """Record a normal section after its artefact write.

        Args:
            synthesis_index: Zero-based position in the generation loop.
            prose: Final whole-section prose shown by the live view.
        """
        section = self._section(synthesis_index)
        self._append(
            "artefact.section_completed",
            {"index": section["index"], "title": section["title"], "prose": prose},
        )

    def key_findings_started(self) -> None:
        """Record the final-generated, first-presented key-findings pass."""
        self._append("artefact.section_started", {"index": self._key_findings_section()["index"]})

    def key_findings_completed(self, *, prose: str) -> None:
        """Close the key-findings slot, including the intentional empty case.

        Args:
            prose: Generated prose, or an empty string when no key-findings
                block was warranted.
        """
        section = self._key_findings_section()
        self._append(
            "artefact.section_completed",
            {"index": section["index"], "title": section["title"], "prose": prose},
        )

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
        with self._engine.begin() as conn:
            events.append(
                conn,
                project_id=self._project_id,
                run_id=self._run_id,
                event_type=event_type,
                payload=payload,
            )
