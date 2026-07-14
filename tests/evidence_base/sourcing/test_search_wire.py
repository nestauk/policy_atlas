"""Strategy-level wire-param assertions for live search backends."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import search_coverage_record
from policy_atlas.evidence_base.sourcing import search_live
from policy_atlas.evidence_base.sourcing.acquire import AcquireContext
from policy_atlas.evidence_base.sourcing.search_live import OpenAlexLiveBackend, OvertonLiveBackend
from policy_atlas.evidence_base.sourcing.search_loop import (
    SearchDirectiveError,
    overton_wire_params,
    run_search,
    to_wire_params,
)
from policy_atlas.evidence_base.sourcing.search_prompts import SearchQueriesWire
from tests.helpers import ScriptedGenerationBackend, seed_project_and_run, seed_scope
from tests.provider_fixtures import OvertonFixtureBackend


@dataclass(frozen=True)
class CapturedRequest:
    """One injected transport call."""

    url: str
    params: dict[str, str]


class CapturingFetch:
    """Fetch seam that records requests and returns empty provider pages."""

    def __init__(self) -> None:
        self.calls: list[CapturedRequest] = []

    def __call__(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        self.calls.append(CapturedRequest(url=url, params=dict(params)))
        if "overton" in url:
            return {"results": [], "next_page_url": False}
        return {"results": []}


def _context(scope_id: uuid.UUID) -> AcquireContext:
    return AcquireContext(
        scope_id=scope_id,
        intent="Find evidence on housing retrofit policy.",
        context={
            "search": {
                "depth": "rapid",
                "filters": {
                    "shared": {"published_after": "2020-01-01", "sdgs": [3]},
                    "openalex": {
                        "types": ["article"],
                        "languages": ["en"],
                        "exclude_retracted": True,
                    },
                    "overton": {"publisher_type": "government", "language": "eng"},
                },
            }
        },
    )


def _overton_record(rid: str, country: str) -> dict[str, Any]:
    return {
        "policy_document_id": rid,
        "title": f"Policy document {rid}",
        "snippet": "Policy evidence summary.",
        "document_url": f"https://example.org/{rid}",
        "source": {"country": country, "type": "government", "title": "Test source"},
        "published_on": "2024-01-01",
        "languages": ["eng"],
    }


def test_live_backends_receive_backend_native_wire_params_via_run_search(
    conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search_live, "_sleep", lambda _seconds: None)
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id, context=_context(uuid.uuid4()).context)
    openalex_fetch = CapturingFetch()
    overton_fetch = CapturingFetch()
    openalex = OpenAlexLiveBackend("openalex-test-key", fetch=openalex_fetch)
    overton = OvertonLiveBackend("overton-test-key", fetch=overton_fetch)

    run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[openalex, overton],
        generation_backend=ScriptedGenerationBackend(
            queries=[
                SearchQueriesWire(
                    queries=["housing retrofit", "fuel poverty"],
                    overton_paraphrases=["Policy evidence about housing retrofit."],
                )
            ]
        ),
    )

    assert openalex_fetch.calls
    assert overton_fetch.calls
    for call in openalex_fetch.calls:
        assert "filter" in call.params
        assert "select" in call.params
        assert "title_and_abstract.search:" in call.params["filter"]
        assert "from_publication_date:2020-01-01" in call.params["filter"]
        assert "sustainable_development_goals.id:https://metadata.un.org/sdg/3" in (
            call.params["filter"]
        )
        assert "type:article" in call.params["filter"]
        assert "language:en" in call.params["filter"]
        assert "is_retracted:false" in call.params["filter"]
        assert "squery" not in call.params
        assert "min_similarity" not in call.params
    for call in overton_fetch.calls:
        assert call.params["squery"]
        assert call.params["min_similarity"] == "0.3"
        assert call.params["published_after"] == "2020-01-01"
        assert call.params["sdgcategories"] == "SDG 3: Good Health and Well-being"
        assert call.params["source_type"] == "government"
        assert call.params["language"] == "eng"
        assert "filter" not in call.params
        assert "select" not in call.params

    expected_filters = {
        "openalex": to_wire_params(
            "openalex",
            {
                "published_after": "2020-01-01",
                "sdgs": [3],
                "types": ["article"],
                "languages": ["en"],
                "exclude_retracted": True,
            },
        ),
        "overton": overton_wire_params(
            {
                "published_after": "2020-01-01",
                "sdgs": [3],
                "publisher_type": "government",
                "language": "eng",
            }
        ),
    }
    event_filters = {
        payload["backend"]: payload["filters"]
        for payload in (
            event["payload"]
            for event in events.read(conn, project_id)
            if event["event_type"] == "search.executed"
        )
    }
    assert event_filters == expected_filters
    row = conn.execute(
        select(search_coverage_record)
        .where(search_coverage_record.c.acquired_by_run_id == run_id)
    ).one()
    assert row.scope_filters == expected_filters


def test_overton_post_filter_without_capable_backend_fails_closed(
    conn: Connection,
) -> None:
    """A backend that cannot enforce a required source_country_post_filter must
    refuse loudly — silently searching unfiltered would admit out-of-group
    records with no provenance trace (the recorded silent-zero hazard shape)."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    backend = OvertonFixtureBackend()  # has no search_with_post_filter

    with pytest.raises(SearchDirectiveError, match="search_with_post_filter"):
        run_search(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=AcquireContext(
                scope_id=scope_id,
                intent="Find evidence on housing retrofit policy.",
                context={
                    "search": {
                        "depth": "rapid",
                        "filters": {
                            "overton": {"source_country_post_filter": ["UK"]},
                        },
                    }
                },
            ),
            backends=[backend],
            generation_backend=ScriptedGenerationBackend(
                queries=[SearchQueriesWire(queries=[], overton_paraphrases=[])]
            ),
        )


def test_overton_post_filter_exclusion_count_reaches_event_and_coverage(
    conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search_live, "_sleep", lambda _seconds: None)
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    calls = 0

    def fetch(url: str, params: dict[str, str]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "results": [_overton_record("uk-1", "UK"), _overton_record("igo-1", "IGO")],
                "next_page_url": "https://app.overton.io/documents.php?page=2",
            }
        return {"results": [_overton_record("uk-2", "UK")]}

    overton = OvertonLiveBackend("overton-test-key", fetch=fetch)
    run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=AcquireContext(
            scope_id=scope_id,
            intent="Find evidence on housing retrofit policy.",
            context={
                "search": {
                    "depth": "rapid",
                    "filters": {
                        "overton": {"source_country_post_filter": ["UK"]},
                    },
                }
            },
        ),
        backends=[overton],
        generation_backend=ScriptedGenerationBackend(
            queries=[SearchQueriesWire(queries=[], overton_paraphrases=[])]
        ),
    )

    payloads = [
        event["payload"]
        for event in events.read(conn, project_id)
        if event["event_type"] == "search.executed"
    ]
    assert payloads[0]["filters"] == {}
    assert payloads[0]["post_filter_excluded"] == 1
    row = conn.execute(
        select(search_coverage_record)
        .where(search_coverage_record.c.acquired_by_run_id == run_id)
    ).one()
    assert row.scope_filters["post_filter_exclusions"][0]["post_filter_excluded"] == 1
