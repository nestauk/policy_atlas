"""Tests for the single search pass (task 051, ADR 0038).

One pass at every scope: keyword and semantic seeds, backward and forward
citation chasing, Overton relevance results and landmarks, two ranked pools cut
at the scope's caps. The scripted backends below answer every verb the pass
uses and record each call, so a test can assert the exact call plan.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    evidence_scope,
    search_coverage_record,
    source_screening_result,
    task_source_snapshot,
)
from policy_atlas.evidence_search.sourcing import pool, search_live
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext, BackendCaps
from policy_atlas.evidence_search.sourcing.country_filters import ISO_3166_ALPHA2
from policy_atlas.evidence_search.sourcing.search_live import (
    OpenAlexLiveBackend,
    OvertonLiveBackend,
    SearchTransportError,
)
from policy_atlas.evidence_search.sourcing.search_loop import (
    DEPTH_CONSTANTS,
    RCT_CLAUSE,
    SR_CLAUSE,
    SearchDepth,
    _semantic_filter_parts,
    _semantic_record_passes,
    run_search,
)
from policy_atlas.evidence_search.sourcing.search_prompts import SearchQueriesWire
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    ScriptedGenerationBackend,
    now,
    oa_record,
    seed_run,
    seed_scope,
    seed_source,
    seed_task_and_run,
)
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend

ScriptResult = list[dict[str, Any]] | BaseException
Verb = Literal["search", "search_semantic", "lookup_ids", "fetch_citing", "fetch_by_id"]


@dataclass(frozen=True)
class BackendCall:
    """One scripted backend call captured for assertions."""

    verb: Verb
    query: str
    wire_params: dict[str, str]
    max_results: int | None
    page: int = 1


class ScriptedBackend:
    """Search-backend double answering every verb of the single pass.

    ``scripts`` holds a queue of results per verb, consumed in call order;
    ``keyed`` answers a verb by its query text (ids joined with ``|``, the
    document id for ``fetch_by_id``). An exception entry is raised. Anything
    unscripted returns no records.
    """

    mode = "scripted"

    def __init__(
        self,
        *,
        name: Literal["openalex", "overton"] = "openalex",
        caps: BackendCaps | None = None,
        scripts: Mapping[Verb, Sequence[ScriptResult]] | None = None,
        keyed: Mapping[Verb, Mapping[str, ScriptResult]] | None = None,
    ) -> None:
        self.name: str = name
        self.trust_class = (
            "academic_aggregator" if name == "openalex" else "grey_literature_aggregator"
        )
        self.caps = caps or (
            BackendCaps(
                has_snowball=True,
                has_title_lookup=True,
                has_doi_lookup=True,
                has_semantic=True,
                has_id_lookup=True,
                has_forward=True,
            )
            if name == "openalex"
            else BackendCaps(has_snowball=False, has_title_lookup=False, has_fetch_by_id=True)
        )
        self._scripts = {verb: list(values) for verb, values in (scripts or {}).items()}
        self._keyed = {verb: dict(values) for verb, values in (keyed or {}).items()}
        self.calls: list[BackendCall] = []

    def _consume(self, verb: Verb, key: str) -> list[dict[str, Any]]:
        keyed = self._keyed.get(verb, {})
        if key in keyed:
            result = keyed[key]
        else:
            queue = self._scripts.setdefault(verb, [])
            result = queue.pop(0) if queue else []
        if isinstance(result, BaseException):
            raise result
        return [dict(record) for record in result]

    @staticmethod
    def _limit(records: list[dict[str, Any]], max_results: int | None) -> list[dict[str, Any]]:
        return records if max_results is None else records[:max_results]

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(BackendCall("search", query, dict(wire_params or {}), max_results))
        return self._limit(self._consume("search", query), max_results)

    def search_semantic(
        self,
        text: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            BackendCall("search_semantic", text, dict(wire_params or {}), max_results)
        )
        return self._limit(self._consume("search_semantic", text), max_results)

    def lookup_ids(
        self, ids: list[str], *, wire_params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        key = "|".join(ids)
        self.calls.append(BackendCall("lookup_ids", key, dict(wire_params or {}), None))
        return self._consume("lookup_ids", key)

    def fetch_citing(
        self,
        ids: list[str],
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        key = "|".join(ids)
        self.calls.append(
            BackendCall("fetch_citing", key, dict(wire_params or {}), max_results, page)
        )
        return self._limit(self._consume("fetch_citing", f"{key}#{page}"), max_results)

    def fetch_by_id(self, record_id: str) -> dict[str, Any] | None:
        self.calls.append(BackendCall("fetch_by_id", record_id, {}, 1))
        records = self._consume("fetch_by_id", record_id)
        return records[0] if records else None

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("the single pass uses fetch_citing")

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("the single pass uses lookup_ids")

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        raise NotImplementedError("the single pass does not look up titles")

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("the single pass does not look up DOIs")


def _context(
    scope_id: uuid.UUID,
    *,
    intent: str = "Test intent",
    depth: str | None = None,
    filters: dict[str, Any] | None = None,
) -> AcquireContext:
    search: dict[str, Any] = {}
    if depth is not None:
        search["depth"] = depth
    if filters is not None:
        search["filters"] = filters
    return AcquireContext(
        scope_id=scope_id, intent=intent, context={"search": search} if search else {}
    )


def _wire(queries: list[str], paraphrases: list[str] | None = None) -> SearchQueriesWire:
    return SearchQueriesWire(queries=queries, overton_paraphrases=paraphrases or [])


QUERIES = [f"query {index}" for index in range(5)]
PARAPHRASES = ["paraphrase one", "paraphrase two"]


def _generation() -> ScriptedGenerationBackend:
    return ScriptedGenerationBackend(queries=[_wire(QUERIES, PARAPHRASES)])


def ov_record(
    suffix: str,
    *,
    title: str | None = None,
    cites: list[str] | None = None,
    citation_count: int = 0,
    country: str = "UK",
    scholarly: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "policy_document_id": f"ov-{suffix}",
        "pdf_document_id": f"ov-{suffix}-pdf",
        "title": title or f"Overton record {suffix}",
        "translated_title": "",
        "snippet": "policy evidence snippet",
        "llm_document_description": "",
        "published_on": "2024-01-01",
        "keyed_other_identifiers": {},
        "citation_count": citation_count,
        "cites": {
            "policy": [{"overton_id": cited} for cited in (cites or [])],
            "scholarly": [{"doi": doi} for doi in (scholarly or [])],
        },
        "source": {"title": "Policy Unit", "type": "government", "country": country},
        "document_url": f"https://example.org/overton/{suffix}",
        "overton_url": f"https://example.org/overton-url/{suffix}",
        "languages": ["eng"],
        "topics": [],
    }


def _payloads(conn: Connection, task_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        event["payload"]
        for event in events.read(conn, task_id)
        if event["event_type"] == "search.executed"
    ]


def _coverage(conn: Connection, task_id: uuid.UUID) -> list[Any]:
    return list(
        conn.execute(
            select(search_coverage_record)
            .where(search_coverage_record.c.task_id == task_id)
            .order_by(search_coverage_record.c.created_at)
        )
    )


def _assert_invariant(counts: dict[str, Any]) -> None:
    for scope in (counts, *counts["by_backend"].values()):
        assert (
            scope["acquired"]
            + scope["already_acquired"]
            + scope["skipped_unusable"]
            + scope["dropped_over_cap"]
            == scope["results_returned"]
        )


def _openalex_with_graph() -> ScriptedBackend:
    """Fifteen keyword pages, eight semantic pages, three resolvable references,
    and a forward chase that pages twice in full and once short."""
    refs = [f"https://openalex.org/Wref{index}" for index in range(3)]
    keyword = [
        [oa_record(f"kw-{call}-{index}", referenced_works=refs) for index in range(2)]
        for call in range(15)
    ]
    semantic = [[oa_record(f"sem-{call}")] for call in range(8)]
    forward_pages: list[ScriptResult] = [
        [oa_record(f"cite-1-{index}") for index in range(200)],
        [oa_record(f"cite-2-{index}") for index in range(200)],
        [oa_record(f"cite-3-{index}") for index in range(5)],
    ]
    return ScriptedBackend(
        scripts={"search": keyword, "search_semantic": semantic, "fetch_citing": forward_pages},
        keyed={
            "lookup_ids": {"Wref0|Wref1|Wref2": [oa_record(f"ref{index}") for index in range(3)]}
        },
    )


def _overton_with_landmarks() -> ScriptedBackend:
    """Three searches whose results cite twenty documents, fifteen not returned."""
    cited = [f"ov-cited-{index}" for index in range(20)]
    searches = [[ov_record(f"r{call}", cites=cited)] for call in range(3)]
    return ScriptedBackend(
        name="overton",
        scripts={"search": searches},
        keyed={
            "fetch_by_id": {
                cid: [ov_record(cid.removeprefix("ov-"), citation_count=5)] for cid in cited
            }
        },
    )


@pytest.mark.parametrize("depth", ["rapid", "standard", "deep"])
def test_every_depth_runs_the_same_pass_and_cuts_at_its_caps(conn: Connection, depth: str) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    openalex = _openalex_with_graph()
    overton = _overton_with_landmarks()

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id, depth=depth),
        backends=[openalex, overton],
        generation_backend=_generation(),
    )

    # The plan: 15 keyword, 8 semantic, 1 resolve batch, 3 forward pages;
    # 3 Overton searches, 15 landmark fetches. Same at every depth.
    assert [call.verb for call in openalex.calls] == (
        ["search"] * 15 + ["search_semantic"] * 8 + ["lookup_ids"] + ["fetch_citing"] * 3
    )
    assert [call.page for call in openalex.calls if call.verb == "fetch_citing"] == [1, 2, 3]
    assert [call.verb for call in overton.calls] == ["search"] * 3 + ["fetch_by_id"] * 15
    assert counts["search"]["queries_executed"] == {"openalex": 27, "overton": 18}
    assert [call.query for call in openalex.calls[:15]] == [
        variant
        for query in QUERIES
        for variant in (query, f"({query}) AND {SR_CLAUSE}", f"({query}) AND {RCT_CLAUSE}")
    ]
    assert [call.query for call in openalex.calls[15:23]] == ["Test intent", *PARAPHRASES, *QUERIES]
    assert all(call.max_results == pool.KEYWORD_PER_CALL for call in openalex.calls[:15])
    assert all(call.max_results == pool.SEMANTIC_PER_CALL for call in openalex.calls[15:23])
    assert all(call.max_results == 134 for call in overton.calls[:3])

    origins = [payload["query_origin"] for payload in _payloads(conn, task_id)]
    assert origins[:15] == [o for _ in QUERIES for o in ("generated", "variant_sr", "variant_rct")]
    assert origins[15:23] == ["semantic"] * 8
    assert origins[23:27] == ["snowball_backward"] + ["snowball_forward"] * 3
    assert origins[27:] == ["verbatim", "paraphrase", "paraphrase"] + ["landmark"] * 15

    # The two caps cut the two pools independently; every returned record is counted.
    constants = DEPTH_CONSTANTS[cast(SearchDepth, depth)]
    by_backend = counts["by_backend"]
    assert by_backend["openalex"]["results_returned"] == 30 + 8 + 3 + 405
    assert by_backend["openalex"]["acquired"] == min(constants["papers_cap"], 38 + 3 + 200)
    assert by_backend["openalex"]["dropped_over_cap"] == 446 - by_backend["openalex"]["acquired"]
    assert by_backend["overton"]["acquired"] == 3 + 15
    assert by_backend["overton"]["dropped_over_cap"] == 0
    _assert_invariant(counts)
    assert counts["search"]["seeds"] == 38
    assert counts["search"]["backward_targets"] == 3
    assert counts["search"]["forward_candidates"] == 200
    assert counts["search"]["landmarks"] == 15
    assert counts["stop_condition"] == "completed"
    rows = _coverage(conn, task_id)
    assert len(rows) == 1 and rows[0].stop_condition == "completed"


def test_two_variant_country_filter_runs_semantic_once_and_filters_locally(
    conn: Connection,
) -> None:
    """More than 100 affiliation countries split the keyword calls in two; the
    semantic, resolve and forward calls carry no country clause and apply the
    country rule locally instead (contract D13)."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    countries = sorted(ISO_3166_ALPHA2)[:101]
    refs = ["https://openalex.org/Wref0"]
    keyword = [[oa_record(f"kw-{call}", referenced_works=refs)] for call in range(30)]
    british = oa_record("sem-gb")
    british["authorships"] = [{"countries": ["GB"]}]
    semantic = [[dict(british), oa_record("sem-none")] for _ in range(8)]
    resolved_gb = oa_record("ref0")
    resolved_gb["authorships"] = [{"countries": ["gb"]}]
    openalex = ScriptedBackend(
        scripts={"search": keyword, "search_semantic": semantic},
        keyed={"lookup_ids": {"Wref0": [resolved_gb, oa_record("ref-elsewhere")]}},
    )

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(
            scope_id, filters={"openalex": {"author_affiliation_countries": countries}}
        ),
        backends=[openalex],
        generation_backend=_generation(),
    )

    keyword_calls = [call for call in openalex.calls if call.verb == "search"]
    semantic_calls = [call for call in openalex.calls if call.verb == "search_semantic"]
    resolve_calls = [call for call in openalex.calls if call.verb == "lookup_ids"]
    assert len(keyword_calls) == 30
    assert all("authorships.countries:" in call.wire_params["filter"] for call in keyword_calls)
    assert len(semantic_calls) == 8
    assert all(call.wire_params == {} for call in semantic_calls)
    assert len(resolve_calls) == 1 and resolve_calls[0].wire_params == {}
    payloads = _payloads(conn, task_id)
    assert [p["post_filter_excluded"] for p in payloads if p["verb"] == "search_semantic"] == [
        1
    ] * 8
    assert [p["post_filter_excluded"] for p in payloads if p["verb"] == "fetch_references"] == [1]
    assert counts["search"]["semantic_local_filters"] == ["author_affiliation_countries"]
    assert _coverage(conn, task_id)[0].scope_filters["semantic_local_filters"] == [
        "author_affiliation_countries"
    ]
    _assert_invariant(counts)


def test_call_budget_stops_a_backend(conn: Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    monkeypatch.setitem(DEPTH_CONSTANTS["rapid"], "call_budget", {"openalex": 5, "overton": 30})
    openalex = ScriptedBackend(scripts={"search": [[oa_record(f"kw-{i}")] for i in range(15)]})

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[openalex],
        generation_backend=_generation(),
    )

    assert len(openalex.calls) == 5
    assert counts["search"]["queries_executed"] == {"openalex": 5}
    assert counts["stop_condition"] == "completed"


def test_logical_calls_count_pages_and_retries_once(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A full page, a retried request and a short page are one logical call
    each; an Overton search that pages three times is one call with ``pages`` 3."""
    monkeypatch.setattr(search_live, "_sleep", lambda _seconds: None)
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    openalex_requests: list[dict[str, str]] = []
    state = {"failed_once": False}

    def openalex_fetch(url: str, params: dict[str, str]) -> Any:
        openalex_requests.append(params)
        keyword = len(
            [p for p in openalex_requests if "title_and_abstract.search:" in p.get("filter", "")]
        )
        # Request 1: a full page. Request 2 fails once and request 3 is its
        # retry (one logical call). Request 4 is the third call, a short page.
        if "search.semantic" in params or keyword > 4:
            return {"results": []}
        if keyword == 1:
            return {"results": [oa_record(f"{1000 + i}") for i in range(200)]}
        if keyword == 2 and not state["failed_once"]:
            state["failed_once"] = True
            raise SearchTransportError(status_code=503, host="api.openalex.org")
        return {"results": [oa_record(f"{2000 + keyword * 10 + i}") for i in range(5)]}

    def overton_fetch(url: str, params: dict[str, str]) -> Any:
        page = int(params.get("page", "1")) if params else int(url.rsplit("page=", 1)[-1])
        return {
            "results": [ov_record(f"p{page}-{i}") for i in range(50)],
            "next_page_url": f"https://app.overton.io/documents.php?page={page + 1}",
        }

    openalex = OpenAlexLiveBackend("key", fetch=openalex_fetch)
    overton = OvertonLiveBackend("key", fetch=overton_fetch)
    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[openalex, overton],
        generation_backend=ScriptedGenerationBackend(queries=[_wire(["q1", "q2", "q3"], ["p"])]),
    )

    payloads = _payloads(conn, task_id)
    keyword_events = [p for p in payloads if p["backend"] == "openalex" and p["verb"] == "search"]
    assert [p["result_count"] for p in keyword_events][:3] == [200, 5, 5]
    assert all(p["status"] == "ok" for p in keyword_events)
    # Nine keyword calls (3 queries x 3 forms) plus the semantic and chasing calls,
    # each one logical call; the transport made one more HTTP request (the retry).
    assert counts["search"]["queries_executed"]["openalex"] == len(
        [p for p in payloads if p["backend"] == "openalex"]
    )
    assert openalex.http_calls == counts["search"]["queries_executed"]["openalex"] + 1
    overton_events = [p for p in payloads if p["backend"] == "overton" and p["verb"] == "search"]
    assert [p["pages"] for p in overton_events] == [3, 3]
    assert [p["result_count"] for p in overton_events] == [134, 134]
    _assert_invariant(counts)


def test_semantic_dates_are_fenced_on_the_wire_and_checked_locally(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    in_range = oa_record("sem-2020", year=2020)
    too_late = oa_record("sem-2021", year=2021)
    too_late["publication_date"] = "2021-01-15"
    openalex = ScriptedBackend(
        scripts={"search_semantic": [[in_range, too_late]] + [[] for _ in range(7)]}
    )

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id, filters={"shared": {"published_before": "2020-06-30"}}),
        backends=[openalex],
        generation_backend=_generation(),
    )

    semantic_calls = [call for call in openalex.calls if call.verb == "search_semantic"]
    assert len(semantic_calls) == 8
    assert semantic_calls[0].wire_params == {"filter": "publication_year:<2021"}
    first_semantic = next(p for p in _payloads(conn, task_id) if p["verb"] == "search_semantic")
    assert first_semantic["result_count"] == 1
    assert first_semantic["post_filter_excluded"] == 1
    assert counts["search"]["semantic_local_filters"] == ["published_before"]
    assert counts["search"]["seeds"] == 1


def test_semantic_local_filter_rules() -> None:
    """Every filter the semantic endpoint rejects has a local rule over the fetched fields."""
    record = {
        "publication_date": "2019-05-01",
        "sustainable_development_goals": [{"id": "https://metadata.un.org/sdg/3"}],
        "is_paratext": False,
        "open_access": {"oa_status": "gold"},
        "authorships": [{"countries": ["GB"]}],
    }
    assert _semantic_record_passes({"published_after": "2019-01-01"}, record)
    assert not _semantic_record_passes({"published_after": "2019-06-01"}, record)
    assert not _semantic_record_passes({"published_before": "2019-04-30"}, record)
    assert _semantic_record_passes({"sdgs": [3, 4]}, record)
    assert not _semantic_record_passes({"sdgs": [4]}, record)
    assert _semantic_record_passes({"exclude_paratext": True}, record)
    assert not _semantic_record_passes({"exclude_paratext": True}, {**record, "is_paratext": True})
    assert _semantic_record_passes({"oa_status": ["gold", "green"]}, record)
    assert not _semantic_record_passes({"oa_status": ["green"]}, record)
    assert _semantic_record_passes({"author_affiliation_countries": ["GB"]}, record)
    assert not _semantic_record_passes({"author_affiliation_countries": ["US"]}, record)
    assert not _semantic_record_passes({"published_before": "2020-01-01"}, {})

    wire, local = _semantic_filter_parts(
        {
            "published_after": "2015-03-01",
            "published_before": "2024-12-31",
            "types": ["article"],
            "sdgs": [3],
            "exclude_paratext": False,
        }
    )
    assert wire == {"filter": "type:article,publication_year:>2014,publication_year:<2025"}
    assert local == ["published_after", "published_before", "sdgs"]


def test_overlong_generated_query_is_dropped_at_validation(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    openalex = ScriptedBackend()

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[openalex],
        generation_backend=ScriptedGenerationBackend(queries=[_wire([*QUERIES[:4], "x" * 1_400])]),
    )

    assert len([call for call in openalex.calls if call.verb == "search"]) == 12 + 1  # + fallback
    assert counts["search"]["queries_dropped"] == 1


def test_overton_cited_papers_never_enter_the_paper_pool(conn: Connection) -> None:
    """An Overton result's cited papers (``cites.scholarly``) cause no OpenAlex
    resolve and no paper-pool candidate (contract D9)."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    openalex = ScriptedBackend()
    overton = ScriptedBackend(
        name="overton",
        scripts={"search": [[ov_record("r0", scholarly=["10.1/cited-paper"])]]},
    )

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[openalex, overton],
        generation_backend=_generation(),
    )

    assert {call.verb for call in openalex.calls} <= {"search", "search_semantic"}
    assert counts["by_backend"]["openalex"]["acquired"] == 0
    assert counts["by_backend"]["overton"]["acquired"] == 1


@pytest.mark.parametrize("name", ["openalex", "overton"])
def test_one_backend_scope_leaves_the_other_pool_empty(conn: Connection, name: str) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    backend = _openalex_with_graph() if name == "openalex" else _overton_with_landmarks()

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[backend],
        generation_backend=_generation(),
    )

    assert set(counts["search"]["queries_executed"]) == {name}
    assert set(counts["search"]["pool_sizes"]) == {name}
    assert counts["by_backend"][name]["acquired"] > 0
    assert len(_coverage(conn, task_id)) == 1
    _assert_invariant(counts)


def test_fixture_mode_runs_the_single_pass_with_zero_egress(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id, depth="deep"),
        backends=[OpenAlexFixtureBackend(), OvertonFixtureBackend()],
        generation_backend=_generation(),
    )

    executed = counts["search"]["queries_executed"]
    assert executed["openalex"] >= 15 + 8
    assert executed["overton"] >= 3
    assert counts["by_backend"]["openalex"]["acquired"] <= DEPTH_CONSTANTS["deep"]["papers_cap"]
    assert counts["by_backend"]["overton"]["acquired"] <= DEPTH_CONSTANTS["deep"]["policy_cap"]
    assert counts["stop_condition"] == "completed"
    _assert_invariant(counts)


# --- Retained from the round-loop tests (task 015), updated to the single pass ---


def test_fanout_events_failed_variant_isolated(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    intent = "Evaluate home energy retrofit grants."
    openalex_pages: list[ScriptResult] = [
        RuntimeError("scripted OpenAlex variant failure")
        if index == 7
        else [oa_record(f"kw-{index}")]
        for index in range(15)
    ]
    openalex = ScriptedBackend(scripts={"search": openalex_pages})
    overton = ScriptedBackend(
        name="overton", scripts={"search": [[ov_record(f"r{index}")] for index in range(3)]}
    )

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id, intent=intent),
        backends=[openalex, overton],
        generation_backend=_generation(),
    )

    assert [call.query for call in overton.calls] == [intent, *PARAPHRASES]
    payloads = _payloads(conn, task_id)
    errored = [payload for payload in payloads if payload["status"] == "error"]
    assert len(errored) == 1
    assert "scripted OpenAlex variant failure" in errored[0]["error"]
    assert counts["by_backend"]["openalex"]["status"] == "ok"
    assert counts["by_backend"]["overton"]["status"] == "ok"
    # 15 keyword + 8 semantic + 1 forward page (no references to resolve).
    assert counts["search"]["queries_executed"] == {"openalex": 24, "overton": 3}
    _assert_invariant(counts)


def test_generation_failure_raises_and_harness_records_component_failed(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    with pytest.raises(RuntimeError, match="generation failed"):
        run_search(
            conn,
            task_id=task_id,
            run_id=run_id,
            context=_context(scope_id),
            backends=[ScriptedBackend()],
            generation_backend=ScriptedGenerationBackend(
                queries=[RuntimeError("generation failed")]
            ),
        )

    harness_run_id = seed_run(conn, task_id)
    run_harness(
        conn,
        config=compile(Plan(component="acquire", evidence_scope_id=scope_id)),
        task_id=task_id,
        run_id=harness_run_id,
        provider=StubEchoProvider(),
        search_backends=[ScriptedBackend()],
        search_generation_backend=ScriptedGenerationBackend(
            queries=[RuntimeError("generation failed")]
        ),
    )

    log = events.read(conn, task_id)
    failed = [
        event["payload"]
        for event in log
        if event["event_type"] == "component.failed" and event["payload"]["component"] == "acquire"
    ]
    assert len(failed) == 1
    assert failed[0]["error"] == "generation failed"
    assert any(event["event_type"] == "run.failed" for event in log)


def test_zero_result_generated_queries_count_and_openalex_fallback(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    intent = "Find evaluations of retrofit advice services."
    openalex = ScriptedBackend(
        scripts={
            "search": [*([] for _ in range(15)), [oa_record("fallback", title="Fallback hit")]]
        }
    )

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id, intent=intent),
        backends=[openalex],
        generation_backend=_generation(),
    )

    keyword_events = [p for p in _payloads(conn, task_id) if p["verb"] == "search"]
    assert counts["search"]["queries_zero_result"]["openalex"] == 5
    assert counts["search"]["fallback_to_verbatim"]["openalex"] is True
    assert [p["query_origin"] for p in keyword_events].count("fallback_verbatim") == 1
    assert keyword_events[-1]["query"] == intent
    assert keyword_events[-1]["result_count"] == 1


def test_keyword_calls_request_a_full_page_each(conn: Connection) -> None:
    """Each keyword call asks for its own full page (200), never a share of a run cap."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    pages: list[ScriptResult] = [
        [oa_record(f"cap-{page}-{index}") for index in range(pool.KEYWORD_PER_CALL + 20)]
        for page in range(15)
    ]
    openalex = ScriptedBackend(scripts={"search": pages})

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[openalex],
        generation_backend=_generation(),
    )

    keyword_calls = [call for call in openalex.calls if call.verb == "search"]
    assert len(keyword_calls) == 15
    assert all(call.max_results == pool.KEYWORD_PER_CALL for call in keyword_calls)
    assert counts["by_backend"]["openalex"]["results_returned"] == pool.KEYWORD_PER_CALL * 15
    assert counts["search"]["seeds"] == pool.SEEDS
    assert counts["stop_condition"] == "completed"


def test_fanout_runs_every_planned_call_with_no_time_budget(conn: Connection) -> None:
    """No wall clock exists at any depth (task 029): no planned call is skipped."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    openalex = ScriptedBackend(scripts={"search": [[oa_record(f"late-{i}")] for i in range(15)]})

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id, depth="standard"),
        backends=[openalex],
        generation_backend=_generation(),
    )

    assert len([call for call in openalex.calls if call.verb == "search"]) == 15
    assert counts["stop_condition"] == "completed"


def test_search_guidance_flows_to_query_generation_and_provenance(conn: Connection) -> None:
    """search.guidance reaches query generation and is echoed onto the coverage
    record's scope_filters, never rewriting the evidence_scope row."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    guidance = ["prioritise UK policy evaluations", "avoid clinical literature"]
    generation = _generation()

    run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=AcquireContext(
            scope_id=scope_id, intent="Test intent", context={"search": {"guidance": guidance}}
        ),
        backends=[ScriptedBackend(), ScriptedBackend(name="overton")],
        generation_backend=generation,
    )

    assert generation.query_payloads[0].guidance == guidance
    assert _coverage(conn, task_id)[0].scope_filters["guidance"] == guidance


def test_search_guidance_absent_leaves_scope_filters_without_guidance_key(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    generation = _generation()

    run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[ScriptedBackend(), ScriptedBackend(name="overton")],
        generation_backend=generation,
    )

    assert generation.query_payloads[0].guidance is None
    assert "guidance" not in _coverage(conn, task_id)[0].scope_filters


def test_search_guidance_leaves_evidence_scope_row_unchanged(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    directive = {"search": {"guidance": ["prioritise UK policy evaluations"]}}
    scope_id = seed_scope(conn, task_id, context=directive)

    config = compile(Plan(component="acquire", evidence_scope_id=scope_id))
    events.append(conn, task_id=task_id, run_id=run_id, event_type="run.started", payload={})
    events.append(conn, task_id=task_id, run_id=run_id, event_type="plan.compiled", payload={})
    run_harness(conn, config=config, task_id=task_id, run_id=run_id, provider=StubEchoProvider())

    row = conn.execute(
        select(evidence_scope).where(evidence_scope.c.evidence_scope_id == scope_id)
    ).one()
    assert dict(row.context) == directive


def test_acquire_search_does_not_write_screening_rows(conn: Connection) -> None:
    """Acquire holds no relevance judgment: a run adds snapshots, never screening rows."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id, context={"search": {"depth": "deep"}})
    _, tss_id = seed_source(conn, task_id, meta={"title": "Seeded", "backend": "openalex"})
    conn.execute(
        source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            task_source_snapshot_id=tss_id,
            task_id=task_id,
            screened_by_run_id=run_id,
            status="relevant",
            screen_basis="title_abstract",
            screen_decision_confidence=0.9,
            screen_stage=1,
            screened_at=now(),
        )
    )

    def screening_rows() -> int:
        return int(
            conn.execute(
                select(sa.func.count())
                .select_from(source_screening_result)
                .where(source_screening_result.c.task_id == task_id)
            ).scalar_one()
        )

    before = screening_rows()
    run_search(
        conn,
        task_id=task_id,
        run_id=seed_run(conn, task_id),
        context=_context(scope_id, depth="deep"),
        backends=[
            ScriptedBackend(scripts={"search": [[oa_record("deep-new", title="Deep acquired")]]})
        ],
        generation_backend=_generation(),
    )

    assert screening_rows() == before
    snapshots = conn.execute(
        select(sa.func.count())
        .select_from(task_source_snapshot)
        .where(task_source_snapshot.c.task_id == task_id)
    ).scalar_one()
    assert snapshots == 2
