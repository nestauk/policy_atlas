"""Durable presentation-progress events for long-running components."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import structlog
from sqlalchemy.engine import Engine

from policy_atlas.core import events

log = structlog.get_logger()

#: The case-studies slot's title and focus in the skeleton (task 058, round 7).
CASE_STUDIES_SLOT_TITLE = "Case studies"
CASE_STUDIES_SLOT_FOCUS = "Relevant examples from the cited evidence."


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
        self._case_studies: dict[str, Any] | None = None
        self._skeleton_emitted = False
        self._disabled = False

    def emit_skeleton(
        self,
        sections: Sequence[dict[str, str]],
        *,
        key_findings: bool = True,
        case_studies: bool = False,
    ) -> None:
        """Emit the presentation-ordered skeleton and establish display indexes.

        Args:
            sections: Sections in synthesis order, including any code-rendered
                foot section. The skeleton IS this list — nothing is added to
                it beyond the key-findings slot below.
            key_findings: Whether the run ends in a key-findings pass, which is
                generated last and presented first. True for the Evidence
                search report; False for an output kind that runs no such pass
                (the baseline, task 044 X8), whose skeleton is exactly
                ``sections``.
            case_studies: Whether the run ends in a case-studies pass, which
                is generated after the key findings (task 058, round 7: its
                cards stream into this slot). Its slot comes last, after the
                body sections, so their indexes do not move.

        Every skeleton entry carries a ``role`` (``key_findings``, ``body``
        or ``case_studies``) so the page orders the live sections by the
        same rule as the saved report.

        Raises:
            RuntimeError: If a skeleton was already emitted for this emitter.
        """
        if self._skeleton_emitted:
            raise RuntimeError("synthesis progress skeleton already emitted")
        self._skeleton_emitted = True
        self._key_findings = (
            {
                "index": 0,
                "title": "Key findings",
                "focus": "The report's headline claims.",
                "role": "key_findings",
            }
            if key_findings
            else None
        )
        leading = [self._key_findings] if self._key_findings is not None else []
        self._sections_by_synthesis_index = [
            {
                "index": index,
                "title": section["title"],
                "focus": section["focus"],
                "role": "body",
            }
            for index, section in enumerate(sections, start=len(leading))
        ]
        self._case_studies = (
            {
                "index": len(leading) + len(sections),
                "title": CASE_STUDIES_SLOT_TITLE,
                "focus": CASE_STUDIES_SLOT_FOCUS,
                "role": "case_studies",
            }
            if case_studies
            else None
        )
        trailing = [self._case_studies] if self._case_studies is not None else []
        self._append(
            "artefact.skeleton",
            {"sections": [*leading, *self._sections_by_synthesis_index, *trailing]},
        )

    def section_started(self, synthesis_index: int) -> None:
        """Record that a normal section has begun generation.

        Args:
            synthesis_index: Zero-based position in the generation loop.
        """
        payload = self._compose(lambda: {"index": self._section(synthesis_index)["index"]})
        if payload is not None:
            self._append("artefact.section_started", payload)

    def section_completed(
        self,
        synthesis_index: int,
        *,
        prose: str,
        citations: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        """Record a normal section after its artefact write.

        Args:
            synthesis_index: Zero-based position in the generation loop.
            prose: Final whole-section prose shown by the live view.
            citations: The section's checked citations over ``prose``
                (``start``, ``end``, ``n``, ``source_id``, ``title``,
                ``tier``; task 058, round 7).
        """
        payload = self._compose(
            lambda: {
                "index": self._section(synthesis_index)["index"],
                "title": self._section(synthesis_index)["title"],
                "prose": prose,
                "citations": [dict(citation) for citation in citations],
            }
        )
        if payload is not None:
            self._append("artefact.section_completed", payload)

    def key_findings_started(self) -> None:
        """Record the final-generated, first-presented key-findings pass."""
        payload = self._compose(lambda: {"index": self._key_findings_section()["index"]})
        if payload is not None:
            self._append("artefact.section_started", payload)

    def key_findings_completed(
        self, *, prose: str, citations: Sequence[Mapping[str, Any]] = ()
    ) -> None:
        """Close the key-findings slot, including the intentional empty case.

        Args:
            prose: Generated prose, or an empty string when no key-findings
                block was warranted.
            citations: The block's checked citations over ``prose``.
        """
        payload = self._compose(
            lambda: {
                "index": self._key_findings_section()["index"],
                "title": self._key_findings_section()["title"],
                "prose": prose,
                "citations": [dict(citation) for citation in citations],
            }
        )
        if payload is not None:
            self._append("artefact.section_completed", payload)

    def case_studies_started(self) -> None:
        """Record that the case-studies pass has begun (task 058, round 7)."""
        payload = self._compose(lambda: {"index": self._case_studies_section()["index"]})
        if payload is not None:
            self._append("artefact.section_started", payload)

    def case_studies_completed(
        self, *, prose: str, citations: Sequence[Mapping[str, Any]] = ()
    ) -> None:
        """Close the case-studies slot, including the empty case (no cards survived).

        Args:
            prose: The block's prose (each card as its bold title line and
                text, cards separated by a blank line), or an empty string
                when no case studies were kept.
            citations: The block's checked citations over ``prose``.
        """
        payload = self._compose(
            lambda: {
                "index": self._case_studies_section()["index"],
                "title": self._case_studies_section()["title"],
                "prose": prose,
                "citations": [dict(citation) for citation in citations],
            }
        )
        if payload is not None:
            self._append("artefact.section_completed", payload)

    def key_findings_display_index(self) -> int | None:
        """The key-findings slot's index on the page, or ``None`` without one."""
        return None if self._key_findings is None else int(self._key_findings["index"])

    def case_studies_display_index(self) -> int | None:
        """The case-studies slot's index on the page, or ``None`` without one."""
        return None if self._case_studies is None else int(self._case_studies["index"])

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

    def display_index(self, synthesis_index: int) -> int:
        """The index the page shows for a section the writer is on (task 058).

        The writer counts sections in the order it writes them, from 0. The
        page numbers them with the key findings first at 0 when the report
        has them, so a body section's display index is one higher (the
        case-studies slot, when there is one, comes after the body).
        Streamed text and revising spans must carry this index, or they land
        on the wrong section.

        Args:
            synthesis_index: Zero-based position in the generation loop.

        Returns:
            The section's index in the skeleton the page received.
        """
        return int(self._section(synthesis_index)["index"])

    def _section(self, synthesis_index: int) -> dict[str, Any]:
        try:
            return self._sections_by_synthesis_index[synthesis_index]
        except IndexError as exc:
            raise RuntimeError("synthesis progress section is not in the skeleton") from exc

    def _case_studies_section(self) -> dict[str, Any]:
        if self._case_studies is None:
            raise RuntimeError("synthesis progress skeleton carries no case-studies slot")
        return self._case_studies

    def _key_findings_section(self) -> dict[str, Any]:
        if self._key_findings is None:
            raise RuntimeError("synthesis progress skeleton carries no key-findings slot")
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
