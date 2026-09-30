"""The dossier's records on an options-scoping task (task 046, amendment 3, R67).

``GET /tasks/{task_id}/sources/{source_id}/records?option_id=``: a document's
intervention profile records that are members of an option, one entry per
(option, record), each in the record's own words; the document's DOI twins
count as the document; filtered to one option when ``option_id`` is given;
empty when the document has no record under the option (the dossier then
shows its findings, B8). Scoped as the sibling dossier route: an unreadable
task is the indistinguishable 404, and an option or document of another task
yields nothing. The sibling ``sources/{source_id}`` route is unchanged.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import source_snapshot, task_source_snapshot
from tests.api.resource_support import api_client, create_task
from tests.api.test_longlist_routes import (  # noqa: F401 - the autouse cleanup
    _build,
    _clients,
    _org_build,
    _remove_committed_tasks,
)


def _document(engine: Engine, task_id: uuid.UUID, title: str) -> uuid.UUID:
    """This task's document row with the given title."""
    with engine.connect() as conn:
        found = conn.execute(
            select(task_source_snapshot.c.task_source_snapshot_id)
            .select_from(
                task_source_snapshot.join(
                    source_snapshot,
                    source_snapshot.c.source_snapshot_id
                    == task_source_snapshot.c.source_snapshot_id,
                )
            )
            .where(task_source_snapshot.c.task_id == task_id)
            .where(source_snapshot.c.metadata["title"].astext == title)
        ).scalar_one()
        return uuid.UUID(str(found))


def _records(
    client: Any,
    task_id: uuid.UUID,
    source_id: uuid.UUID,
    headers: dict[str, str] | None,
    option_id: uuid.UUID | None = None,
) -> Any:
    query = f"?option_id={option_id}" if option_id is not None else ""
    return client.get(
        f"/api/v1/tasks/{task_id}/sources/{source_id}/records{query}", headers=headers
    )


def _words(body: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (
            r["option_name"],
            r["intervention"],
            r["setting"],
            r["unit"],
            r["outcome"],
            r["study_geography"],
            r["role"],
        )
        for r in body["records"]
    ]


def test_a_document_s_records_one_per_option_in_their_own_words(
    engine: Engine, tmp_path: Path
) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        uk = _document(engine, built.task_id, "UK guarantee evaluation")
        preprint = _document(engine, built.task_id, "UK guarantee preprint")

        response = _records(client, built.task_id, uk, owner.headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["task_source_snapshot_id"] == str(uk)
        # Every record of the document and of its DOI twin, options by name.
        assert _words(body) == [
            ("Guarantee package", "guarantee package", None, None, None, None, "evaluated"),
            (
                "Youth guarantee",
                "youth guarantee",
                "Jobcentres",
                "16 to 24 year olds",
                "employment",
                "England",
                "evaluated",
            ),
            (
                "Youth guarantee",
                "youth guarantee flagged",
                None,
                None,
                None,
                "United Kingdom",
                "evaluated",
            ),
        ]
        assert {r["option_id"] for r in body["records"]} == {
            str(built.options["Guarantee package"]),
            str(built.options["Youth guarantee"]),
        }
        # The twin opens on the same records.
        twin = _records(client, built.task_id, preprint, owner.headers).json()
        assert _words(twin) == _words(body)
        # A colleague reads what the owner reads (the read grade).
        assert _records(client, built.task_id, uk, colleague.headers).json() == body


def test_the_records_filter_to_one_option(engine: Engine, tmp_path: Path) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        uk = _document(engine, built.task_id, "UK guarantee evaluation")
        body = _records(
            client, built.task_id, uk, owner.headers, built.options["Youth guarantee"]
        ).json()
        assert [(r["option_name"], r["intervention"]) for r in body["records"]] == [
            ("Youth guarantee", "youth guarantee"),
            ("Youth guarantee", "youth guarantee flagged"),
        ]


def test_a_document_with_no_record_under_the_option_reads_empty(
    engine: Engine, tmp_path: Path
) -> None:
    """B8: the frontend then shows the document's findings."""
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        uk = _document(engine, built.task_id, "UK guarantee evaluation")
        response = _records(client, built.task_id, uk, owner.headers, built.options["Mentoring"])
        assert response.status_code == 200
        assert response.json() == {"task_source_snapshot_id": str(uk), "records": []}


def test_an_unreadable_task_is_the_indistinguishable_404(engine: Engine, tmp_path: Path) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, stranger)):
        built = _org_build(engine, owner, colleague, linked=False)
        uk = _document(engine, built.task_id, "UK guarantee evaluation")
        hidden = _records(client, built.task_id, uk, stranger.headers)
        absent = _records(client, uuid.uuid4(), uk, stranger.headers)
        assert hidden.status_code == absent.status_code == 404
        assert hidden.content == absent.content
        assert _records(client, built.task_id, uk, None).status_code == 404
        # Public like the dossier: a shared task reads to anyone.
        shared = client.patch(
            f"/api/v1/tasks/{built.task_id}", headers=owner.headers, json={"is_public": True}
        )
        assert shared.status_code == 200, shared.text
        for headers in (None, stranger.headers):
            response = _records(client, built.task_id, uk, headers)
            assert response.status_code == 200
            assert len(response.json()["records"]) == 3


def test_another_owner_s_option_or_document_gives_nothing(
    engine: Engine, tmp_path: Path
) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, stranger)):
        mine = _org_build(engine, owner, colleague, linked=False)
        theirs = _build(engine, owner=stranger.user_id, linked=False)
        my_uk = _document(engine, mine.task_id, "UK guarantee evaluation")
        their_uk = _document(engine, theirs.task_id, "UK guarantee evaluation")
        # Their option id on my readable task: nothing, not their records.
        foreign_option = _records(
            client, mine.task_id, my_uk, owner.headers, theirs.options["Youth guarantee"]
        )
        assert foreign_option.status_code == 200
        assert foreign_option.json()["records"] == []
        # Their document id on my readable task: nothing, although the DOI matches.
        foreign_document = _records(client, mine.task_id, their_uk, owner.headers)
        assert foreign_document.status_code == 200
        assert foreign_document.json()["records"] == []
        # Their task: the 404.
        assert _records(client, theirs.task_id, their_uk, owner.headers).status_code == 404


def test_the_sibling_dossier_route_and_an_evidence_search_task_are_unchanged(
    engine: Engine, tmp_path: Path
) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        uk = _document(engine, built.task_id, "UK guarantee evaluation")
        dossier = client.get(f"/api/v1/tasks/{built.task_id}/sources/{uk}", headers=owner.headers)
        assert dossier.status_code == 200
        assert dossier.json()["source_id"] == str(uk)
        assert "records" not in dossier.json()
    with api_client(tmp_path) as (client, headers, _other):
        task_id = create_task(client, headers)
        source_id = uuid.uuid4()
        assert (
            client.get(f"/api/v1/tasks/{task_id}/sources/{source_id}", headers=headers).status_code
            == 404
        )
        empty = client.get(
            f"/api/v1/tasks/{task_id}/sources/{source_id}/records", headers=headers
        )
        assert empty.status_code == 200
        assert empty.json() == {"task_source_snapshot_id": str(source_id), "records": []}
