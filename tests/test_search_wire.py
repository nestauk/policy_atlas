"""Strategy-level wire-param assertions for live search backends."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.acquire import AcquireContext
from policy_atlas.schema import search_coverage_record
from policy_atlas.search_live import OpenAlexLiveBackend, OvertonLiveBackend
from policy_atlas.search_loop import overton_wire_params, run_search, to_wire_params
from policy_atlas.search_prompts import QueriesPayload, SearchQueriesWire
from tests.helpers import seed_project_and_run, seed_scope


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


class ScriptedGenerationBackend:
    """Minimal rapid-query backend for wire tests."""

    mode = "scripted"

    def __init__(self) -> None:
        self.payloads: list[QueriesPayload] = []

    def generate_queries(self, payload: QueriesPayload) -> SearchQueriesWire:
        self.payloads.append(payload)
        return SearchQueriesWire(
            queries=["housing retrofit", "fuel poverty"],
            overton_paraphrases=["Policy evidence about housing retrofit."],
        )

    def reformulate(self, payload: Any) -> SearchQueriesWire:
        raise AssertionError("wire test runs rapid search only")

    def suggest(self, payload: Any) -> Any:
        raise AssertionError("wire test runs rapid search only")


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


def test_live_backends_receive_backend_native_wire_params_via_run_search(
    conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("policy_atlas.search_live._sleep", lambda _seconds: None)
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
        generation_backend=ScriptedGenerationBackend(),
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
