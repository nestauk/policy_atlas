"""In-app feedback, element B: resolve "a paper I expected is missing".

A user gives a DOI, a URL or a title. The server works out which paper that is
(:func:`resolve_paper`), finds the paper among the task's documents
(:func:`find_document`), and then names the pipeline stage at which the paper
was lost (:func:`failure_stage`). The user never chooses a stage.

The stage sets come from the read-model helpers that the Sources tab already
uses, so "cited", "selected" and "screened out" mean the same here as on screen.

Data sources: OpenAlex Works API (publisher: OurResearch; worldwide coverage)
for the paper lookup. No geographic data is used.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, NamedTuple, Protocol

import structlog
from langfuse import Langfuse
from sqlalchemy import or_, select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.read_models.repository import (
    _cited_snapshot_ids,
    _effective_screens,
    _latest_selection,
    _selected_ids,
)
from policy_atlas.core import tracing
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    feedback_event,
    missing_paper_resolution,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.evidence_search.sourcing.acquire import normalize_doi

log = structlog.get_logger()

#: A title match from OpenAlex is accepted only at or above this similarity
#: (0 to 1, :func:`title_similarity`). Chosen to accept a difference in case,
#: punctuation or a subtitle separator, and to reject a different paper on the
#: same topic. The similarity of each accepted match is stored as
#: ``missing_paper_resolution.resolver_confidence``.
TITLE_SIMILARITY_THRESHOLD = 0.9
#: The confidence of a match on an identifier (a DOI or an OpenAlex id), or on
#: an exact title among the task's own documents.
EXACT_MATCH_CONFIDENCE = 1.0

#: A DOI anywhere in the input: bare, ``doi:``, or inside a web address.
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
#: An OpenAlex work address or id, for example ``https://openalex.org/W2741809807``.
_OPENALEX_WORK = re.compile(r"(?:openalex\.org/(?:works/)?|^)(W\d+)$", re.IGNORECASE)
_NOT_WORD = re.compile(r"[^a-z0-9]+")


class PaperLookup(Protocol):
    """The two OpenAlex lookups that the resolver needs.

    ``OpenAlexLiveBackend`` has both. Tests pass a fake.
    """

    def lookup_dois(self, dois: list[str]) -> list[dict[str, Any]]:
        """Return the OpenAlex Work records for the DOIs."""
        ...

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Return a small page of OpenAlex Work records for a title search."""
        ...


class ResolvedPaper(NamedTuple):
    """The paper that a user's input names.

    Attributes:
        openalex_id: The OpenAlex work address, when known.
        doi: The DOI in bare lower-case form, when known.
        title: The paper's title, when known.
        confidence: How sure the match is, from 0 to 1.
    """

    openalex_id: str | None
    doi: str | None
    title: str | None
    confidence: float

    @property
    def external_id(self) -> str | None:
        """The identifier to store when the paper is not in the task."""
        return self.openalex_id or self.doi


class RunMembership(NamedTuple):
    """Which of a task's documents reached each pipeline stage.

    Each set holds ``task_source_snapshot_id`` values. A document can be in
    more than one set; :func:`failure_stage` reads them from the last stage
    to the first.
    """

    cited: frozenset[uuid.UUID]
    selected: frozenset[uuid.UUID]
    screened_in: frozenset[uuid.UUID]
    screened_out_s2: frozenset[uuid.UUID]
    screened_out_s1: frozenset[uuid.UUID]
    acquired: frozenset[uuid.UUID]


def normalise_title(title: str) -> str:
    """Return a title in lower case with each run of punctuation or space as one space."""
    return _NOT_WORD.sub(" ", title.lower()).strip()


def title_similarity(first: str, second: str) -> float:
    """Return how alike two titles are, from 0 (different) to 1 (the same).

    The titles are normalised first, so case and punctuation do not count.

    Args:
        first: One title.
        second: The other title.

    Returns:
        The ``difflib`` similarity ratio of the two normalised titles.
    """
    return SequenceMatcher(None, normalise_title(first), normalise_title(second)).ratio()


def _paper_from_record(record: dict[str, Any], confidence: float) -> ResolvedPaper:
    """Build a resolved paper from a raw OpenAlex Work record."""
    return ResolvedPaper(
        openalex_id=record.get("id") or None,
        doi=normalize_doi(record.get("doi")),
        title=record.get("display_name") or None,
        confidence=confidence,
    )


def resolve_paper(raw_input: str, lookup: PaperLookup | None) -> ResolvedPaper | None:
    """Work out which paper a DOI, a URL or a title names.

    - A DOI (bare, or inside a URL) is an identity. OpenAlex adds its id and
      the title when it knows the DOI.
    - An OpenAlex work address is an identity.
    - Any other URL cannot be matched: the server does not fetch web pages.
    - Other text is a title. The best OpenAlex title hit is accepted only at
      or above :data:`TITLE_SIMILARITY_THRESHOLD`.

    Args:
        raw_input: What the user typed.
        lookup: The OpenAlex lookups, or ``None`` when no OpenAlex key is
            configured. Then only an identifier resolves.

    Returns:
        The paper, or ``None`` when the input cannot be matched.
    """
    text = raw_input.strip()
    found_doi = _DOI.search(text)
    if found_doi is not None:
        doi = normalize_doi(found_doi.group(0).rstrip(".,;)"))
        records = lookup.lookup_dois([doi]) if lookup is not None and doi is not None else []
        if records:
            return _paper_from_record(records[0], EXACT_MATCH_CONFIDENCE)
        return ResolvedPaper(None, doi, None, EXACT_MATCH_CONFIDENCE)
    found_work = _OPENALEX_WORK.search(text)
    if found_work is not None:
        openalex_id = f"https://openalex.org/{found_work.group(1).upper()}"
        return ResolvedPaper(openalex_id, None, None, EXACT_MATCH_CONFIDENCE)
    if text.lower().startswith(("http://", "https://")) or lookup is None or not text:
        return None
    scored = [
        (title_similarity(text, record.get("display_name") or ""), record)
        for record in lookup.lookup_title(text)
    ]
    if not scored:
        return None
    similarity, best = max(scored, key=lambda pair: pair[0])
    if similarity < TITLE_SIMILARITY_THRESHOLD:
        return None
    return _paper_from_record(best, similarity)


def find_document(
    conn: Connection, *, task_id: uuid.UUID, paper: ResolvedPaper | None, raw_input: str
) -> uuid.UUID | None:
    """Find a paper among the documents of a task.

    A document matches on its DOI, on its provider record id (the OpenAlex
    id), or on its title after normalisation. The title of the user's own
    input is also tried, so a paper that OpenAlex does not hold (an Overton
    policy document) is still found by its exact title.

    Args:
        conn: Open database connection.
        task_id: The task.
        paper: The resolved paper, or ``None`` when the input did not resolve.
        raw_input: What the user typed.

    Returns:
        The ``task_source_snapshot_id`` of the first matching document, or
        ``None`` when the task does not hold the paper.
    """
    metadata = source_snapshot.c.metadata
    identifiers = []
    if paper is not None and paper.doi is not None:
        identifiers.append(metadata["doi"].astext == paper.doi)
    if paper is not None and paper.openalex_id is not None:
        identifiers.append(metadata["backend_record_id"].astext == paper.openalex_id)
    titles = {normalise_title(raw_input)}
    if paper is not None and paper.title is not None:
        titles.add(normalise_title(paper.title))
    documents = (
        select(task_source_snapshot.c.task_source_snapshot_id, metadata["title"].astext)
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
    )
    if identifiers:
        by_identifier = conn.execute(documents.where(or_(*identifiers)).limit(1)).first()
        if by_identifier is not None:
            found: uuid.UUID = by_identifier[0]
            return found
    # ponytail: a scan of the task's titles in Python (a task holds at most a
    # few thousand documents). Add a normalised-title column if this is slow.
    for document_id, title in conn.execute(documents):
        if title and normalise_title(title) in titles:
            matched: uuid.UUID = document_id
            return matched
    return None


def run_membership(
    conn: Connection, *, task_id: uuid.UUID, artefact_id: uuid.UUID | None
) -> RunMembership:
    """Read which documents of a task reached each pipeline stage.

    Screening is stored for an evidence scope and a document, not for a run,
    and a document is linked to a task once. The sets are therefore the
    task's current state: the effective screening row of each document, the
    newest selection, and the citations of the named report.

    Args:
        conn: Open database connection.
        task_id: The task.
        artefact_id: The report whose citations count as "cited", or ``None``
            when the run wrote no report (then nothing is cited).

    Returns:
        The stage sets.
    """
    documents = conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            task_source_snapshot.c.source_snapshot_id,
            task_source_snapshot.c.full_text_snapshot_id,
        ).where(task_source_snapshot.c.task_id == task_id)
    ).all()
    cited_snapshots = _cited_snapshot_ids(conn, artefact_id) if artefact_id is not None else set()
    screens = _effective_screens(conn, task_id)
    selection = _latest_selection(conn, task_id)

    def screened(status_is_relevant: bool, stage: int | None = None) -> frozenset[uuid.UUID]:
        """Return the documents whose effective screening row matches."""
        return frozenset(
            document_id
            for document_id, row in screens.items()
            if (row.status == "relevant") == status_is_relevant
            and (stage is None or row.screen_stage == stage)
        )

    return RunMembership(
        cited=frozenset(
            row.task_source_snapshot_id
            for row in documents
            if {row.source_snapshot_id, row.full_text_snapshot_id} & cited_snapshots
        ),
        selected=frozenset(_selected_ids(selection["selected"]) if selection is not None else ()),
        screened_in=screened(True),
        screened_out_s2=screened(False, 2),
        screened_out_s1=screened(False, 1),
        acquired=frozenset(row.task_source_snapshot_id for row in documents),
    )


def failure_stage(
    paper: ResolvedPaper | None, document_id: uuid.UUID | None, membership: RunMembership
) -> str:
    """Name the pipeline stage at which a reported paper was lost.

    The order is from the end of the pipeline to its start, so a paper is
    named by the last stage that it reached.

    Args:
        paper: The resolved paper, or ``None`` when the input did not resolve.
        document_id: The paper's document in the task, or ``None`` when the
            task does not hold it.
        membership: The stage sets of the run.

    Returns:
        A value of ``MISSING_PAPER_FAILURE_STAGES``:

        - ``unresolved``: the input names no paper that could be matched.
        - ``cited``: the report cites the paper (the user is wrong; still recorded).
        - ``not_cited``: selected, but the report does not cite it.
        - ``not_selected``: screened in, but not selected.
        - ``screened_out_s2`` / ``screened_out_s1``: removed at full-text or
          at title-and-abstract screening.
        - ``acquired_only``: acquired and never screened. This must not occur.
        - ``not_retrieved``: the search did not find the paper.
    """
    if document_id is None:
        return "unresolved" if paper is None else "not_retrieved"
    for stage, members in (
        ("cited", membership.cited),
        ("not_cited", membership.selected),
        ("not_selected", membership.screened_in),
        ("screened_out_s2", membership.screened_out_s2),
        ("screened_out_s1", membership.screened_out_s1),
        ("acquired_only", membership.acquired),
    ):
        if document_id in members:
            return stage
    return "not_retrieved"


def resolve_and_store(
    engine: Engine,
    langfuse: Langfuse | None,
    lookup: PaperLookup | None,
    *,
    feedback_event_id: uuid.UUID,
) -> None:
    """Resolve one stored missing-paper record and write the answer.

    Runs on a worker thread, so that a slow OpenAlex lookup does not hold the
    request. It never raises: a failure is logged and the record stays
    pending, with its row safe in Postgres.

    The steps: read the record; resolve the paper (a network call, outside any
    transaction); find the document and the stage; store the resolution row;
    then mirror the record as the Langfuse score ``missing_paper`` with the
    stage as its value and in its metadata.

    Args:
        engine: The process engine.
        langfuse: Langfuse client, or ``None`` when tracing is off.
        lookup: The OpenAlex lookups, or ``None`` when no key is configured.
        feedback_event_id: The ``missing_paper`` record.
    """
    try:
        with engine.connect() as conn:
            event = conn.execute(
                select(
                    feedback_event.c.payload,
                    feedback_event.c.surface,
                    feedback_event.c.trace_id,
                    feedback_event.c.capability_run_id,
                    capability_run.c.task_id,
                )
                .join(
                    capability_run,
                    capability_run.c.capability_run_id == feedback_event.c.capability_run_id,
                )
                .where(feedback_event.c.feedback_event_id == feedback_event_id)
            ).one()
            artefact_id = conn.execute(
                select(artefact.c.artefact_id)
                .where(artefact.c.capability_run_id == event.capability_run_id)
                .order_by(artefact.c.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        raw_input = event.payload["raw_input"]
        try:
            paper = resolve_paper(raw_input, lookup)
        except Exception as exc:  # noqa: BLE001 - OpenAlex is down: a person reviews the record
            log.warning("feedback.missing_paper.lookup_failed", error=type(exc).__name__)
            paper = None
        with engine.begin() as conn:
            document_id = find_document(
                conn, task_id=event.task_id, paper=paper, raw_input=raw_input
            )
            stage = failure_stage(
                paper,
                document_id,
                run_membership(conn, task_id=event.task_id, artefact_id=artefact_id),
            )
            if document_id is not None:
                resolved_id: str | None = str(document_id)
                confidence: float | None = (
                    paper.confidence if paper is not None else EXACT_MATCH_CONFIDENCE
                )
            else:
                resolved_id = paper.external_id if paper is not None else None
                confidence = paper.confidence if paper is not None else None
            conn.execute(
                missing_paper_resolution.update()
                .where(missing_paper_resolution.c.feedback_event_id == feedback_event_id)
                .values(
                    resolved_id=resolved_id,
                    failure_stage=stage,
                    resolver_confidence=confidence,
                    resolved_at=datetime.now(UTC),
                )
            )
        if stage == "acquired_only":
            # The brief: "should be impossible; log it".
            log.warning("feedback.missing_paper.acquired_only", resolved_id=resolved_id)
        tracing.score_feedback(
            langfuse,
            feedback_event_id=feedback_event_id,
            trace_id=event.trace_id,
            name="missing_paper",
            value=stage,
            comment=event.payload.get("why"),
            metadata={
                "surface": event.surface,
                "failure_stage": stage,
                "resolved_id": resolved_id,
            },
        )
    except Exception as exc:  # noqa: BLE001 - a worker thread must not die silently
        log.warning(
            "feedback.missing_paper.resolution_failed",
            feedback_event_id=str(feedback_event_id),
            error=type(exc).__name__,
        )
