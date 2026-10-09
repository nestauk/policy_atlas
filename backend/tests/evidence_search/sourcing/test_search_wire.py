"""Strategy-level wire-param assertions for live search backends."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import search_coverage_record
from policy_atlas.evidence_search.sourcing import search_live
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext
from policy_atlas.evidence_search.sourcing.search_live import (
    OpenAlexLiveBackend,
    OvertonLiveBackend,
)
from policy_atlas.evidence_search.sourcing.search_loop import (
    SearchDirectiveError,
    overton_wire_params,
    run_search,
    to_wire_params,
)
from policy_atlas.evidence_search.sourcing.search_prompts import SearchQueriesWire
from tests.helpers import ScriptedGenerationBackend, seed_scope, seed_task_and_run
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend


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


class ScriptedFetch(CapturingFetch):
    """Capturing fetch seam with a deterministic response sequence."""

    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        super().__init__()
        self._responses = iter(responses)

    def __call__(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        self.calls.append(CapturedRequest(url=url, params=dict(params)))
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_openalex_semantic_wire_shape_and_empty_text() -> None:
    fetch = CapturingFetch()
    backend = OpenAlexLiveBackend("openalex-test-key", fetch=fetch)

    backend.search_semantic(
        "  housing   retrofit ", wire_params={"filter": "type:article,language:en"}
    )

    assert fetch.calls[0].params == {
        "api_key": "openalex-test-key",
        "search.semantic": "housing retrofit",
        "filter": "type:article,language:en",
        "select": ",".join(search_live.OA_SELECT),
        "per-page": "50",
        "page": "1",
    }
    backend.search_semantic("\t \n")
    assert len(fetch.calls) == 1


def test_openalex_semantic_omits_absent_filter() -> None:
    fetch = CapturingFetch()
    OpenAlexLiveBackend("openalex-test-key", fetch=fetch).search_semantic("housing")
    assert "filter" not in fetch.calls[0].params


def test_openalex_lookup_ids_batches_and_normalizes_urls() -> None:
    fetch = CapturingFetch()
    ids = [f"https://openalex.org/W{i}" for i in range(1, 121)]
    OpenAlexLiveBackend("openalex-test-key", fetch=fetch).lookup_ids(
        ids, wire_params={"filter": "type:article"}
    )

    assert len(fetch.calls) == 3
    assert [call.params["per-page"] for call in fetch.calls] == ["50", "50", "20"]
    assert fetch.calls[0].params["filter"] == (
        f"ids.openalex:{'|'.join(f'W{i}' for i in range(1, 51))},type:article"
    )
    assert fetch.calls[-1].params["filter"].startswith("ids.openalex:W101|W102")


def test_openalex_fetch_citing_wire_shape_and_bounds() -> None:
    fetch = CapturingFetch()
    backend = OpenAlexLiveBackend("openalex-test-key", fetch=fetch)
    backend.fetch_citing(["W1", "https://openalex.org/W2"], page=3)

    assert len(fetch.calls) == 1
    assert fetch.calls[0].params["filter"] == "cites:W1|W2"
    assert fetch.calls[0].params["per-page"] == "200"
    assert fetch.calls[0].params["page"] == "3"
    with pytest.raises(ValueError, match="at most 100"):
        backend.fetch_citing([f"W{i}" for i in range(101)])
    with pytest.raises(ValueError, match="at least 1"):
        backend.fetch_citing(["W1"], page=0)


def test_overton_fetch_by_id_wire_shape_and_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICY_ATLAS_SEARCH_CACHE_TTL_S", "0")
    fetch = ScriptedFetch(
        [
            {"results": []},
            {"results": [{"policy_document_id": "other"}]},
            {"results": [{"policy_document_id": "target"}]},
        ]
    )
    backend = OvertonLiveBackend("overton-test-key", fetch=fetch)
    assert backend.fetch_by_id("target") is None
    assert backend.fetch_by_id("target") is None
    assert backend.fetch_by_id("target") == {"policy_document_id": "target"}
    assert fetch.calls[0].params == {
        "policy_document_id": "target",
        "format": "json",
        "pp": "1",
        "api_key": "overton-test-key",
    }
    with pytest.raises(ValueError, match="without whitespace"):
        backend.fetch_by_id("not valid")


def test_overton_relevance_sort_is_protected_and_counts_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLICY_ATLAS_SEARCH_CACHE_TTL_S", "0")
    fetch = ScriptedFetch(
        [
            {
                "results": [_overton_record("one", "UK")],
                "next_page_url": "https://app.overton.io/documents.php?page=2",
            },
            {"results": [_overton_record("two", "UK")]},
        ]
    )
    backend = OvertonLiveBackend("overton-test-key", fetch=fetch)
    assert len(backend.search("housing", max_results=2)) == 2
    assert backend.last_pages == 2
    assert fetch.calls[0].params["sort"] == "relevance"
    post_filter_fetch = CapturingFetch()
    OvertonLiveBackend("overton-test-key", fetch=post_filter_fetch).search_with_post_filter(
        "housing", source_country_post_filter=["UK"]
    )
    assert post_filter_fetch.calls[0].params["sort"] == "relevance"
    with pytest.raises(ValueError, match="sort"):
        backend.search("housing", wire_params={"sort": "date"})


def test_semantic_retry_and_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICY_ATLAS_SEARCH_CACHE_TTL_S", "0")
    sleeps: list[float] = []
    monkeypatch.setattr(search_live, "_sleep", sleeps.append)
    retry_fetch = ScriptedFetch(
        [
            search_live.SearchTransportError(429, "not-the-provider.example"),
            {"results": []},
        ]
    )
    OpenAlexLiveBackend("openalex-test-key", fetch=retry_fetch).search_semantic("housing")
    assert len(retry_fetch.calls) == 2
    assert len(retry_fetch.calls) <= search_live.RETRY_MAX_ATTEMPTS

    sleeps.clear()  # the retry half's back-off sleep must not satisfy the interval check
    values = iter([0.0, 0.0, 1.0])
    monkeypatch.setattr(search_live, "_monotonic", lambda: next(values))
    interval_fetch = CapturingFetch()
    backend = OpenAlexLiveBackend("openalex-test-key", fetch=interval_fetch)
    backend.search_semantic("first")
    backend.search_semantic("second")
    assert any(wait >= 1.0 for wait in sleeps)


def test_pacing_admits_concurrent_requests_one_interval_apart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paced admission (task 051, plan S13): threads calling one backend at once
    are admitted (the last-request stamp taken) no closer than the interval,
    and every request is counted."""
    monkeypatch.setenv("POLICY_ATLAS_SEARCH_CACHE_TTL_S", "0")
    stamps: list[float] = []

    class Stamping(OpenAlexLiveBackend):
        _min_interval_s = 0.05

        def _wait_rate_limit(self, *, min_interval_s: float | None = None) -> None:
            super()._wait_rate_limit(min_interval_s=min_interval_s)
            # Still inside the pacing lock: the stamp is this admission's.
            assert self._last_request_at is not None
            stamps.append(self._last_request_at)

    in_flight = {"now": 0, "max": 0}
    gate = threading.Lock()

    def overlapping_fetch(url: str, params: dict[str, str]) -> dict[str, Any]:
        # The request runs outside the pacing lock, so requests overlap.
        with gate:
            in_flight["now"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["now"])
        try:
            time.sleep(0.2)
            return {"results": []}
        finally:
            with gate:
                in_flight["now"] -= 1

    backend = Stamping("openalex-test-key", fetch=overlapping_fetch)
    threads = [threading.Thread(target=backend.search, args=(f"q{i}",)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads), "a request thread did not finish"

    assert len(stamps) == 6
    assert backend.http_calls == 6
    assert in_flight["max"] > 1, "requests did not overlap: the lock is held through the request"
    gaps = [b - a for a, b in zip(stamps, stamps[1:], strict=False)]
    assert all(gap >= 0.05 - 1e-3 for gap in gaps), gaps


def test_a_429_pauses_every_threads_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rate-limit reply pushes the backend's next admission out by the pause,
    for every caller, not only the thread that was refused (task 051, S13)."""
    monkeypatch.setenv("POLICY_ATLAS_SEARCH_CACHE_TTL_S", "0")
    clock = {"now": 100.0}
    monkeypatch.setattr(search_live, "_monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        search_live, "_sleep", lambda seconds: clock.__setitem__("now", clock["now"] + seconds)
    )
    # No retry back-off: the only thing that can delay the retry is the pause
    # itself (review finding, 2026-10-09: with the back-off in place the old
    # assertion held with the pause deleted).
    monkeypatch.setattr(search_live, "RETRY_BACKOFF_S", 0.0)
    fetch = ScriptedFetch(
        [search_live.SearchTransportError(429, "api.openalex.org"), {"results": []}]
    )
    backend = OpenAlexLiveBackend("openalex-test-key", fetch=fetch)

    backend.search("first")  # 429 at t=100, retried at once

    assert len(fetch.calls) == 2
    # The refused request stamped t=100; the pause moved the next admission to
    # t=100 + RATE_LIMIT_PAUSE_S, which is where the retry (a new admission)
    # landed. Without the pause it would have landed at t=100 + the interval.
    assert backend._last_request_at == pytest.approx(100.0 + search_live.RATE_LIMIT_PAUSE_S)


def test_rate_limit_pauses_coalesce(monkeypatch: pytest.MonkeyPatch) -> None:
    """Several 429 replies in the same instant pause the backend once, not once
    each: the next admission is one pause away, whichever thread asks."""
    monkeypatch.setattr(search_live, "_monotonic", lambda: 100.0)
    backend = OpenAlexLiveBackend("openalex-test-key", fetch=ScriptedFetch([]))
    for _ in range(8):
        backend._pause_admission(search_live.RATE_LIMIT_PAUSE_S)
    assert backend._last_request_at is not None
    next_admission = backend._last_request_at + backend._min_interval_s
    assert next_admission == pytest.approx(100.0 + search_live.RATE_LIMIT_PAUSE_S)


def test_new_transport_calls_redact_keys_and_urls() -> None:
    def fail(_url: str, _params: dict[str, str]) -> dict[str, Any]:
        raise search_live.SearchTransportError(400, "secret.example")

    openalex = OpenAlexLiveBackend("openalex-secret", fetch=fail)
    with pytest.raises(search_live.SearchTransportError) as error:
        openalex.search_semantic("https://contains-a-url.example")
    assert str(error.value) == "search transport error host=api.openalex.org status_code=400"
    assert "openalex-secret" not in str(
        search_live._loggable_params({"api_key": "openalex-secret"})
    )
    openalex_fetch = CapturingFetch()
    openalex = OpenAlexLiveBackend("openalex-secret", fetch=openalex_fetch)
    overton_fetch = CapturingFetch()
    overton = OvertonLiveBackend("overton-secret", fetch=overton_fetch)
    openalex.search_semantic("x")
    openalex.lookup_ids(["W1"])
    openalex.fetch_citing(["W1"])
    overton.fetch_by_id("id")
    assert all(
        "secret" not in repr(search_live._search_cache_key(call.url, call.params))
        for call in [*openalex_fetch.calls, *overton_fetch.calls]
    )


def test_fixture_new_verbs_are_deterministic() -> None:
    openalex = OpenAlexFixtureBackend()
    assert openalex.search_semantic("x") != openalex.search("x")
    first = openalex.search("x")[0]
    work_id = first["id"].rsplit("/", 1)[-1]
    assert openalex.lookup_ids([work_id]) == [first]
    overton = OvertonFixtureBackend()
    record = overton.search("x")[0]
    assert overton.fetch_by_id(record["policy_document_id"]) == record
    assert overton.fetch_by_id("unknown") is None


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
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id, context=_context(uuid.uuid4()).context)
    openalex_fetch = CapturingFetch()
    overton_fetch = CapturingFetch()
    openalex = OpenAlexLiveBackend("openalex-test-key", fetch=openalex_fetch)
    overton = OvertonLiveBackend("overton-test-key", fetch=overton_fetch)

    run_search(
        conn,
        task_id=task_id,
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
    keyword_calls = [c for c in openalex_fetch.calls if "search.semantic" not in c.params]
    semantic_calls = [c for c in openalex_fetch.calls if "search.semantic" in c.params]
    assert keyword_calls
    assert semantic_calls
    for call in semantic_calls:
        # The semantic endpoint takes only some filters (probe 2026-10-09): the
        # accepted ones and a year fence go on the wire; the rest is local.
        semantic_filter = call.params["filter"]
        assert "type:article" in semantic_filter
        assert "language:en" in semantic_filter
        assert "is_retracted:false" in semantic_filter
        assert "publication_year:>2019" in semantic_filter
        assert "from_publication_date" not in semantic_filter
        assert "sustainable_development_goals" not in semantic_filter
    for call in keyword_calls:
        assert "filter" in call.params
        assert "select" in call.params
        assert "title_and_abstract.search:" in call.params["filter"]
        assert "from_publication_date:2020-01-01" in call.params["filter"]
        assert (
            "sustainable_development_goals.id:https://metadata.un.org/sdg/3"
            in (call.params["filter"])
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
            for event in events.read(conn, task_id)
            if event["event_type"] == "search.executed"
        )
        if payload["verb"] == "search"  # keyword and Overton searches carry the plan's filters
    }
    assert event_filters == expected_filters
    row = conn.execute(
        select(search_coverage_record).where(search_coverage_record.c.acquired_by_run_id == run_id)
    ).one()
    # The coverage record also names the filters the semantic leg applied
    # locally, and lists what each locally filtered call excluded (zero here).
    exclusions = row.scope_filters["post_filter_exclusions"]
    assert {entry["verb"] for entry in exclusions} == {"search_semantic"}
    assert all(entry["post_filter_excluded"] == 0 for entry in exclusions)
    assert {k: v for k, v in row.scope_filters.items() if k != "post_filter_exclusions"} == {
        **expected_filters,
        "semantic_local_filters": ["published_after", "sdgs"],
    }


def test_overton_post_filter_without_capable_backend_fails_closed(
    conn: Connection,
) -> None:
    """A backend that cannot enforce a required source_country_post_filter must
    refuse loudly — silently searching unfiltered would admit out-of-group
    records with no provenance trace (the recorded silent-zero hazard shape)."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    backend = OvertonFixtureBackend()  # has no search_with_post_filter

    with pytest.raises(SearchDirectiveError, match="search_with_post_filter"):
        run_search(
            conn,
            task_id=task_id,
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
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
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
        task_id=task_id,
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
        for event in events.read(conn, task_id)
        if event["event_type"] == "search.executed"
    ]
    assert payloads[0]["filters"] == {}
    assert payloads[0]["post_filter_excluded"] == 1
    row = conn.execute(
        select(search_coverage_record).where(search_coverage_record.c.acquired_by_run_id == run_id)
    ).one()
    assert row.scope_filters["post_filter_exclusions"][0]["post_filter_excluded"] == 1
