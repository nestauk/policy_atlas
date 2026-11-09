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

Each entry also carries the ids the saved report gives the citation and its
claim, and the checked quote, read back from the rows the run has just saved
for the section (round 8), so the page can show a citation's context and its
provenance sheet before the whole report is committed.
"""

from __future__ import annotations

import html
import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

from sqlalchemy import or_, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    chunk,
    citation,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import source_short_name

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
    def rationale(self) -> str | None: ...

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

    def citations(
        self, claims: Sequence[_Claim], *, block_id: str | uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        """Give one section's checked claims their citation entries, numbering new sources.

        Call once per section, in the order the sections are saved (body
        sections as written, then the key findings, then the case studies).

        Args:
            claims: The section's claims as persisted (each with its bound
                ``span`` into the section prose, its ``citation_rows`` and
                its ``verdict``).
            block_id: The block the section's claims were just saved in. When
                given, each entry carries the saved ``citation_id`` and
                ``claim_id`` (the claim's addressable-unit id, the id the
                committed report's claim carries); otherwise both are ``None``.

        Returns:
            One entry per citation row, claims by span and each claim's
            citations by chunk id then quote (the read model's order):
            ``start``, ``end`` (the
            claim's span), ``n``, ``source_id`` (the task source id as a
            string, or ``None``), ``title``, ``citation_id`` and ``claim_id`` (strings, or
            ``None`` without a saved row to match), ``chunk_id`` (the cited
            chunk, a string; the chunks are committed long before the report,
            so the page reads the passage by chunk and quote while the report
            is still being written: owner, 2026-11-09) and ``quote``. A
            citation whose chunk is unknown is left out, as the read model
            leaves it out.
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
        saved = self._saved_ids(block_id) if block_id is not None else {}
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
                ids = saved.get((start, end, uuid.UUID(str(row.chunk_id)), row.quote))
                citation_id, claim_id = ids.pop(0) if ids else (None, None)
                entries.append(
                    {
                        "start": start,
                        "end": end,
                        "n": self._numbers[doc_key],
                        "source_id": str(tss_id) if tss_id is not None else None,
                        "title": titles.get(envelope_of(snapshot_id), UNKNOWN_SOURCE),
                        "citation_id": citation_id,
                        "claim_id": claim_id,
                        "chunk_id": str(row.chunk_id),
                        "quote": row.quote,
                    }
                )
        return entries

    def claim_verdicts(
        self, claims: Sequence[_Claim], *, block_id: str | uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        """One section's checked claims with the checker's verdict (task 058, round 13).

        The verdict is the claim's, not a citation's: one entry per spanned
        claim that cites, in span order.

        Args:
            claims: The section's claims as persisted.
            block_id: The block they were saved in; when given, each entry
                carries the saved claim's id.

        Returns:
            ``claim_id`` (string, or ``None``), ``start``, ``end``, ``tier``
            (the verdict, or ``None`` when not checked) and ``rationale``.
        """
        claim_ids: dict[tuple[int, int], str] = {}
        if block_id is not None:
            for (start, end, _chunk, _quote), ids in self._saved_ids(block_id).items():
                if ids:
                    claim_ids.setdefault((start, end), ids[0][1])
        entries: list[dict[str, Any]] = []
        for claim in sorted(
            (claim for claim in claims if claim.span is not None and claim.citation_rows),
            key=lambda claim: cast("tuple[int, int]", claim.span),
        ):
            start, end = cast("tuple[int, int]", claim.span)
            entries.append(
                {
                    "claim_id": claim_ids.get((start, end)),
                    "start": start,
                    "end": end,
                    "tier": claim.verdict if isinstance(claim.verdict, str) else None,
                    "rationale": claim.rationale if isinstance(claim.rationale, str) else None,
                }
            )
        return entries

    def _saved_ids(
        self, block_id: str | uuid.UUID
    ) -> dict[tuple[int, int, uuid.UUID, str], list[tuple[str, str]]]:
        """Read the ids saved for a block's citations, keyed by claim span, chunk and quote.

        A claim's span is unique in its block (claims never overlap), so the
        key finds the claim's row; two citations of one claim with the same
        chunk and quote take their ids in id order, the read model's order.
        """
        rows = self._conn.execute(
            select(
                addressable_unit.c.unit_id,
                addressable_unit.c.locator,
                citation.c.citation_id,
                citation.c.chunk_id,
                citation.c.quote,
            )
            .select_from(
                citation.join(
                    annotation, citation.c.annotation_id == annotation.c.annotation_id
                ).join(
                    addressable_unit,
                    (annotation.c.block_id == addressable_unit.c.block_id)
                    & (annotation.c.unit_id == addressable_unit.c.unit_id),
                )
            )
            .where(annotation.c.block_id == uuid.UUID(str(block_id)))
            .order_by(citation.c.citation_id)
        )
        saved: dict[tuple[int, int, uuid.UUID, str], list[tuple[str, str]]] = {}
        for row in rows:
            locator = row.locator if isinstance(row.locator, Mapping) else {}
            start, end = locator.get("start"), locator.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            saved.setdefault((start, end, row.chunk_id, row.quote), []).append(
                (str(row.citation_id), str(row.unit_id))
            )
        return saved


def source_names(
    conn: Connection, *, task_id: uuid.UUID, source_ids: Sequence[str]
) -> dict[str, tuple[str, str]]:
    """Name a task's sources for the live page: short name and reference title (round 8).

    Args:
        conn: Open database connection.
        task_id: The task whose sources are named.
        source_ids: Task source ids (strings); ids that are not this task's
            sources, or not ids at all, are left out.

    Returns:
        ``{source_id: (short_name, title)}``: the short name as the page's
        "Drawing on" line gives it ("Smith 2023") and the title as the saved
        report's references give it.
    """
    wanted: list[uuid.UUID] = []
    for source_id in source_ids:
        try:
            wanted.append(uuid.UUID(str(source_id)))
        except ValueError:
            continue
    if not wanted:
        return {}
    rows = conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
        .where(
            task_source_snapshot.c.task_id == task_id,
            task_source_snapshot.c.task_source_snapshot_id.in_(wanted),
        )
    )
    names: dict[str, tuple[str, str]] = {}
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
        names[str(row.task_source_snapshot_id)] = (
            source_short_name(metadata, row.source_locator),
            _title(metadata, row.source_locator),
        )
    return names
