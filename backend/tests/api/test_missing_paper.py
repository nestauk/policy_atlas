"""The missing-paper resolver (in-app feedback, element B): every branch.

Three parts: which paper the input names (``resolve_paper``, with a fake
OpenAlex lookup), which document of the task that is (``find_document``), and
at which pipeline stage the paper was lost (``failure_stage``), over a fixture
run that holds one document at each stage.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.engine import Connection

from policy_atlas.api.missing_paper import (
    TITLE_SIMILARITY_THRESHOLD,
    ResolvedPaper,
    failure_stage,
    find_document,
    resolve_paper,
    run_membership,
    title_similarity,
)
from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    chunk,
    citation,
    selection_result,
)
from tests.helpers import now, seed_screening_result, seed_source, seed_task_and_run, seed_walk

WORK = {
    "id": "https://openalex.org/W100",
    "doi": "https://doi.org/10.1000/Breakfast.1",
    "display_name": "Universal breakfast clubs and school attendance: a cluster trial",
}


class FakeLookup:
    """Stands in for the OpenAlex backend: answers from a fixed list of works."""

    def __init__(self, works: list[dict[str, Any]]) -> None:
        self.works = works
        self.title_queries: list[str] = []

    def lookup_dois(self, dois: list[str]) -> list[dict[str, Any]]:
        """Return the works whose DOI is one of ``dois`` (bare, lower case)."""
        return [work for work in self.works if work["doi"].lower().endswith(tuple(dois))]

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Return every work, as a title search page."""
        self.title_queries.append(title)
        return self.works


# --- Which paper does the input name? --------------------------------------


@pytest.mark.parametrize(
    "raw_input",
    [
        "10.1000/breakfast.1",
        "doi:10.1000/BREAKFAST.1",
        "https://doi.org/10.1000/breakfast.1",
        "See https://journal.example.org/article/10.1000/breakfast.1.",
    ],
)
def test_a_doi_resolves_through_openalex(raw_input: str) -> None:
    """A DOI, bare or in a URL, is an identity; OpenAlex adds its id and the title."""
    paper = resolve_paper(raw_input, FakeLookup([WORK]))

    assert paper == ResolvedPaper(
        "https://openalex.org/W100", "10.1000/breakfast.1", WORK["display_name"], 1.0
    )


def test_a_doi_that_openalex_does_not_hold_is_still_an_identity() -> None:
    """Also true with no OpenAlex key at all: the DOI alone names the paper."""
    expected = ResolvedPaper(None, "10.9999/unknown", None, 1.0)

    assert resolve_paper("10.9999/unknown", FakeLookup([WORK])) == expected
    assert resolve_paper("10.9999/unknown", None) == expected


def test_an_openalex_address_is_an_identity() -> None:
    """No lookup is needed for an OpenAlex work address or a bare work id."""
    expected = ResolvedPaper("https://openalex.org/W100", None, None, 1.0)

    assert resolve_paper("https://openalex.org/W100", None) == expected
    assert resolve_paper("w100", None) == expected


def test_a_url_with_no_identifier_does_not_resolve() -> None:
    """The server does not fetch web pages, and a URL is not a title to search."""
    lookup = FakeLookup([WORK])

    assert resolve_paper("https://www.example.org/reports/breakfast-clubs", lookup) is None
    assert lookup.title_queries == []


def test_a_title_resolves_only_above_the_threshold() -> None:
    """A near title is accepted with its similarity as the confidence; a far one is not."""
    lookup = FakeLookup([WORK, {**WORK, "id": "https://openalex.org/W200", "display_name": "x"}])

    typed = "universal breakfast clubs and school attendance - a cluster trial"
    near = resolve_paper(typed, lookup)
    far = resolve_paper("Breakfast clubs in schools", lookup)

    assert near is not None
    assert near.openalex_id == "https://openalex.org/W100"
    assert TITLE_SIMILARITY_THRESHOLD <= near.confidence <= 1.0
    assert far is None
    assert title_similarity("Breakfast clubs in schools", WORK["display_name"]) < 0.9


def test_a_title_does_not_resolve_with_no_lookup_or_no_hit() -> None:
    """No OpenAlex key, an empty result page or blank input: unresolved."""
    assert resolve_paper(WORK["display_name"], None) is None
    assert resolve_paper(WORK["display_name"], FakeLookup([])) is None
    assert resolve_paper("   ", FakeLookup([WORK])) is None


# --- The fixture run: one document at each stage ---------------------------


def _document(conn: Connection, task_id: uuid.UUID, name: str) -> dict[str, uuid.UUID]:
    """Insert one document named after its stage; return its snapshot and document ids."""
    snapshot_id, document_id = seed_source(
        conn,
        task_id,
        {
            "title": f"The {name} paper",
            "doi": f"10.1000/{name}",
            "backend": "openalex",
            "backend_record_id": f"https://openalex.org/W-{name}",
        },
    )
    return {"snapshot": snapshot_id, "document": document_id}


def _cite(conn: Connection, task_id: uuid.UUID, snapshot_id: uuid.UUID) -> uuid.UUID:
    """Insert a report that cites one chunk of a snapshot; return the report's id."""
    ids = {name: uuid.uuid4() for name in ("artefact", "block", "unit", "annotation", "chunk")}
    conn.execute(
        artefact.insert().values(
            artefact_id=ids["artefact"], task_id=task_id, title="Report", created_at=now()
        )
    )
    conn.execute(
        block.insert().values(
            block_id=ids["block"],
            artefact_id=ids["artefact"],
            content="A claim.",
            content_hash="hash",
            created_at=now(),
        )
    )
    conn.execute(
        addressable_unit.insert().values(
            unit_id=ids["unit"],
            block_id=ids["block"],
            unit_type="text_span",
            locator={"start": 0, "end": 8},
            content="A claim.",
            created_at=now(),
        )
    )
    conn.execute(
        annotation.insert().values(
            annotation_id=ids["annotation"],
            block_id=ids["block"],
            unit_id=ids["unit"],
            annotation_type="citation",
            payload={},
            created_at=now(),
        )
    )
    conn.execute(
        chunk.insert().values(
            chunk_id=ids["chunk"],
            source_snapshot_id=snapshot_id,
            sequence=0,
            content="Evidence.",
            content_hash="hash",
            locator={},
            segmentation_policy="manual_v1",
            created_at=now(),
        )
    )
    conn.execute(
        citation.insert().values(
            citation_id=uuid.uuid4(),
            annotation_id=ids["annotation"],
            chunk_id=ids["chunk"],
            quote="Evidence.",
            verification_result="pass",
            created_at=now(),
        )
    )
    return ids["artefact"]


@pytest.fixture
def fixture_run(conn: Connection) -> dict[str, Any]:
    """A task whose run holds one document at each stage of the pipeline."""
    task_id, run_id = seed_task_and_run(conn)
    walk = seed_walk(conn, task_id, capability="evidence_search")
    names = ("cited", "selected", "screened_in", "out_s2", "out_s1", "acquired")
    documents = {name: _document(conn, task_id, name) for name in names}

    def screen(name: str, status: str, stage: int) -> None:
        seed_screening_result(
            conn,
            task_id,
            run_id,
            walk.scope_id,
            documents[name]["document"],
            status,
            screen_stage=stage,
        )

    for name in ("cited", "selected", "screened_in", "out_s2"):
        screen(name, "relevant", 1)
    screen("out_s2", "not_relevant", 2)
    screen("out_s1", "not_relevant", 1)
    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=walk.scope_id,
            run_id=run_id,
            strategy="coverage_stratified_v1",
            budget=10,
            selection_provenance={},
            selected=[
                {"tss_id": str(documents[name]["document"])} for name in ("cited", "selected")
            ],
            excluded={},
            flags=[],
            created_at=now(),
        )
    )
    artefact_id = _cite(conn, task_id, documents["cited"]["snapshot"])
    return {
        "task_id": task_id,
        "artefact_id": artefact_id,
        "documents": {name: ids["document"] for name, ids in documents.items()},
    }


@pytest.mark.parametrize(
    ("name", "stage"),
    [
        ("cited", "cited"),
        ("selected", "not_cited"),
        ("screened_in", "not_selected"),
        ("out_s2", "screened_out_s2"),
        ("out_s1", "screened_out_s1"),
        ("acquired", "acquired_only"),
    ],
)
def test_a_paper_in_the_task_is_named_by_the_last_stage_it_reached(
    conn: Connection, fixture_run: dict[str, Any], name: str, stage: str
) -> None:
    """Each document of the fixture run, reported by its DOI, gives its own stage."""
    task_id = fixture_run["task_id"]
    paper = resolve_paper(f"https://doi.org/10.1000/{name}", None)

    document_id = find_document(conn, task_id=task_id, paper=paper, raw_input="")
    membership = run_membership(conn, task_id=task_id, artefact_id=fixture_run["artefact_id"])

    assert document_id == fixture_run["documents"][name]
    assert failure_stage(paper, document_id, membership) == stage


def test_a_resolved_paper_that_the_task_does_not_hold_was_not_retrieved(
    conn: Connection, fixture_run: dict[str, Any]
) -> None:
    """The search did not find it: the paper becomes a recall check."""
    task_id = fixture_run["task_id"]
    paper = resolve_paper("10.1000/breakfast.1", FakeLookup([WORK]))

    document_id = find_document(conn, task_id=task_id, paper=paper, raw_input="")
    membership = run_membership(conn, task_id=task_id, artefact_id=fixture_run["artefact_id"])

    assert document_id is None
    assert failure_stage(paper, document_id, membership) == "not_retrieved"


def test_an_input_that_names_no_paper_is_unresolved(
    conn: Connection, fixture_run: dict[str, Any]
) -> None:
    """No paper and no document: a person reviews it."""
    task_id = fixture_run["task_id"]
    raw_input = "that report about breakfast"
    paper = resolve_paper(raw_input, FakeLookup([WORK]))

    document_id = find_document(conn, task_id=task_id, paper=paper, raw_input=raw_input)
    membership = run_membership(conn, task_id=task_id, artefact_id=fixture_run["artefact_id"])

    assert paper is None
    assert failure_stage(paper, document_id, membership) == "unresolved"


def test_a_document_is_found_by_openalex_id_and_by_its_exact_title(
    conn: Connection, fixture_run: dict[str, Any]
) -> None:
    """A title that OpenAlex does not resolve still matches the task's own document."""
    task_id = fixture_run["task_id"]
    by_id = resolve_paper("https://openalex.org/W-out_s1", None)
    membership = run_membership(conn, task_id=task_id, artefact_id=fixture_run["artefact_id"])

    assert by_id is None  # "W-out_s1" is not an OpenAlex work id
    by_record = ResolvedPaper("https://openalex.org/W-out_s1", None, None, 1.0)
    found = find_document(conn, task_id=task_id, paper=by_record, raw_input="")
    assert found == fixture_run["documents"]["out_s1"]

    by_title = find_document(conn, task_id=task_id, paper=None, raw_input="the SELECTED paper!")
    assert by_title == fixture_run["documents"]["selected"]
    assert failure_stage(None, by_title, membership) == "not_cited"


def test_nothing_is_cited_when_the_run_has_no_report(
    conn: Connection, fixture_run: dict[str, Any]
) -> None:
    """With no report named, the cited document is only selected."""
    membership = run_membership(conn, task_id=fixture_run["task_id"], artefact_id=None)

    assert membership.cited == frozenset()
    assert fixture_run["documents"]["cited"] in membership.selected
