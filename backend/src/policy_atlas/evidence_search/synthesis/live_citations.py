"""Citations for the live report as each section is checked (task 058, round 7).

In plain terms: while the report is written, the page shows each finished
section before the whole report is saved. This module gives that finished
section its citation markers: for each source a checked claim cites, the
claim's stretch of text, the source's reference number, its title and the
checker's verdict, so the page can show ``[3]`` where the saved report will.

The reference numbers follow the rule the saved report's read model uses
(``api/read_models/repository.py``, ``artefact_out``): one number per
document, the document being the task's source (else the cited snapshot when
no task source holds it), numbered from 1 in order of first citation. Both
sides walk the citations in one fixed order: sections in the order the run
saves them (body sections as written, then the key findings, then the case
studies); within a section, claims by their span (start, then end); within a
claim, citations by chunk id, then quote. One :class:`ReferenceNumbering`
lives for one synthesis run and numbers the sections in the order they are
saved, so a number once given never changes during the run.
"""

from __future__ import annotations

import html
import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

from sqlalchemy import or_, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import chunk, source_snapshot, task_source_snapshot

#: The title the read model gives a source whose record is missing.
UNKNOWN_SOURCE = "Unknown source"


class _CitationRow(Protocol):
    @property
    def chunk_id(self) -> str: ...

    @property
    def quote(self) -> str: ...


class _Claim(Protocol):
    @property
    def span(self) -> tuple[int, int] | None: ...

    @property
    def verdict(self) -> str | None: ...

    @property
    def citation_rows(self) -> Sequence[_CitationRow]: ...


def _title(metadata: Mapping[str, Any], locator: str | None) -> str:
    """Name a source as the read model's ``_title`` does (title, else locator)."""
    title = metadata.get("title")
    if isinstance(title, str) and title:
        return html.unescape(title)
    return locator or UNKNOWN_SOURCE


class ReferenceNumbering:
    """Number a run's cited sources as the saved report will, section by section.

    Args:
        conn: Open database connection (the synthesis run's own).
        task_id: The task whose sources are cited.
    """

    def __init__(self, conn: Connection, *, task_id: uuid.UUID) -> None:
        self._conn = conn
        self._task_id = task_id
        self._numbers: dict[uuid.UUID, int] = {}

    def citations(self, claims: Sequence[_Claim]) -> list[dict[str, Any]]:
        """Give one section's checked claims their citation entries, numbering new sources.

        Call once per section, in the order the sections are saved (body
        sections as written, then the key findings, then the case studies).

        Args:
            claims: The section's claims as persisted (each with its bound
                ``span`` into the section prose, its ``citation_rows`` and
                its ``verdict``).

        Returns:
            One entry per citation row, claims by span and each claim's
            citations by chunk id then quote (the read model's order):
            ``start``, ``end`` (the
            claim's span), ``n``, ``source_id`` (the task source id as a
            string, or ``None``), ``title`` and ``tier`` (the verdict, or
            ``None``). A citation whose chunk is unknown is left out, as the
            read model leaves it out.
        """
        chunk_ids: set[uuid.UUID] = set()
        for claim in claims:
            for row in claim.citation_rows:
                chunk_ids.add(uuid.UUID(str(row.chunk_id)))
        if not chunk_ids:
            return []
        snapshot_by_chunk = {
            row.chunk_id: row.source_snapshot_id
            for row in self._conn.execute(
                select(chunk.c.chunk_id, chunk.c.source_snapshot_id).where(
                    chunk.c.chunk_id.in_(chunk_ids)
                )
            )
        }
        snapshots = set(snapshot_by_chunk.values())
        snapshot_to_tss: dict[uuid.UUID, uuid.UUID] = {}
        tss_to_envelope: dict[uuid.UUID, uuid.UUID] = {}
        if snapshots:
            for row in self._conn.execute(
                select(
                    task_source_snapshot.c.task_source_snapshot_id,
                    task_source_snapshot.c.source_snapshot_id,
                    task_source_snapshot.c.full_text_snapshot_id,
                ).where(
                    task_source_snapshot.c.task_id == self._task_id,
                    or_(
                        task_source_snapshot.c.source_snapshot_id.in_(snapshots),
                        task_source_snapshot.c.full_text_snapshot_id.in_(snapshots),
                    ),
                )
            ):
                snapshot_to_tss[row.source_snapshot_id] = row.task_source_snapshot_id
                tss_to_envelope[row.task_source_snapshot_id] = row.source_snapshot_id
                if row.full_text_snapshot_id is not None:
                    snapshot_to_tss[row.full_text_snapshot_id] = row.task_source_snapshot_id

        def envelope_of(snapshot_id: uuid.UUID) -> uuid.UUID:
            # Bibliographic authority is the document's envelope snapshot,
            # as in the read model.
            tss_id = snapshot_to_tss.get(snapshot_id)
            return tss_to_envelope.get(tss_id, snapshot_id) if tss_id is not None else snapshot_id

        envelopes = {envelope_of(snapshot_id) for snapshot_id in snapshots}
        titles = {
            row.source_snapshot_id: _title(
                row.metadata if isinstance(row.metadata, Mapping) else {},
                row.source_locator,
            )
            for row in self._conn.execute(
                select(
                    source_snapshot.c.source_snapshot_id,
                    source_snapshot.c.metadata,
                    source_snapshot.c.source_locator,
                ).where(source_snapshot.c.source_snapshot_id.in_(envelopes))
            )
        }
        entries: list[dict[str, Any]] = []
        spanned = sorted(
            (claim for claim in claims if claim.span is not None),
            key=lambda claim: cast("tuple[int, int]", claim.span),
        )
        for claim in spanned:
            start, end = cast("tuple[int, int]", claim.span)
            rows = sorted(
                claim.citation_rows,
                key=lambda row: (uuid.UUID(str(row.chunk_id)), row.quote),
            )
            for row in rows:
                snapshot_id = snapshot_by_chunk.get(uuid.UUID(str(row.chunk_id)))
                if snapshot_id is None:
                    continue
                tss_id = snapshot_to_tss.get(snapshot_id)
                # Reference identity is the document, not the snapshot.
                doc_key = tss_id if tss_id is not None else snapshot_id
                if doc_key not in self._numbers:
                    self._numbers[doc_key] = len(self._numbers) + 1
                entries.append(
                    {
                        "start": start,
                        "end": end,
                        "n": self._numbers[doc_key],
                        "source_id": str(tss_id) if tss_id is not None else None,
                        "title": titles.get(envelope_of(snapshot_id), UNKNOWN_SOURCE),
                        "tier": claim.verdict if isinstance(claim.verdict, str) else None,
                    }
                )
        return entries
