"""Judgment tests for task 015 depth-graded search loop behavior."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    evidence_scope,
    project_source_snapshot,
    search_coverage_record,
    source_screening_result,
)
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_base.assess.screen import ScreenContext, screen_sources
from policy_atlas.evidence_base.assess.screen_prompt import (
    ScreenEnvelopePayload,
    ScreenFullTextPayload,
    ScreenRepWire,
)
from policy_atlas.evidence_base.sourcing.acquire import AcquireContext, BackendCaps
from policy_atlas.evidence_base.sourcing.search_loop import (
    CONFIDENT_FLOOR,
    DEEP_WALL_CLOCK_S,
    DEPTH_CONSTANTS,
    DIVERSITY_FRACTION,
    NEG_EXEMPLARS,
    POS_EXEMPLARS,
    RAPID_WALL_CLOCK_S,
    RCT_CLAUSE,
    REFORMULATE_CALL_CAP,
    ROUND_CAP,
    SHORT_CIRCUIT_RATE,
    SNOWBALL_SEEDS,
    SR_CLAUSE,
    SUGGEST_CALL_CAP,
    TARGET_CONFIDENT_RELEVANT,
    THIN_CONFIDENT_RELEVANT,
    confident_relevant_count,
    run_deep_rounds,
    run_search,
    should_escalate,
)
from policy_atlas.evidence_base.sourcing.search_prompts import (
    EXEMPLAR_ABSTRACT_MAX,
    EXEMPLAR_TITLE_MAX,
    SearchQueriesWire,
    SearchSuggestWire,
    SuggestedPaper,
    build_reformulate_messages,
)
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    ScriptedGenerationBackend,
    now,
    oa_record,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_source,
)

ScriptResult = list[dict[str, Any]] | BaseException
SearchVerb = Literal["search", "fetch_citations", "fetch_references", "lookup_title", "lookup_dois"]


@dataclass(frozen=True)
class BackendCall:
    """One scripted backend call captured for assertions."""

    verb: SearchVerb
    query: str
    wire_params: dict[str, str]
    max_results: int | None
    values: list[str]


class ScriptedBackend:
    """SearchBackend double with scriptable verb results and full call capture."""

    mode = "scripted"

    def __init__(
        self,
        *,
        name: Literal["openalex", "overton"] = "openalex",
        trust_class: str | None = None,
        caps: BackendCaps | None = None,
        scripts: dict[SearchVerb, list[ScriptResult]] | None = None,
        keyed: dict[SearchVerb, dict[str, ScriptResult]] | None = None,
    ) -> None:
        self.name: str = name
        self.trust_class: str = (
            trust_class
            if trust_class is not None
            else (
                "academic_aggregator"
                if name == "openalex"
                else "grey_literature_aggregator"
            )
        )
        default_caps = (
            BackendCaps(has_snowball=True, has_title_lookup=True, has_doi_lookup=True)
            if name == "openalex"
            else BackendCaps(has_snowball=False, has_title_lookup=False)
        )
        self.caps = caps if caps is not None else default_caps
        self._scripts = {verb: list(values) for verb, values in (scripts or {}).items()}
        self._keyed = {
            verb: dict(values) for verb, values in (keyed or {}).items()
        }
        self.calls: list[BackendCall] = []

    def _consume(self, verb: SearchVerb, key: str) -> list[dict[str, Any]]:
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
    def _limit(
        records: list[dict[str, Any]],
        max_results: int | None,
    ) -> list[dict[str, Any]]:
        return records if max_results is None else records[:max_results]

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            BackendCall("search", query, dict(wire_params or {}), max_results, [query])
        )
        return self._limit(self._consume("search", query), max_results)

    def fetch_citations(
        self,
        record_id: str,
        *,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(BackendCall("fetch_citations", record_id, {}, max_results, [record_id]))
        return self._limit(self._consume("fetch_citations", record_id), max_results)

    def fetch_references(
        self,
        record_ids: list[str],
        *,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        key = "|".join(record_ids)
        self.calls.append(BackendCall("fetch_references", key, {}, max_results, list(record_ids)))
        return self._limit(self._consume("fetch_references", key), max_results)

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        self.calls.append(BackendCall("lookup_title", title, {}, None, [title]))
        return self._consume("lookup_title", title)

    def lookup_dois(
        self,
        dois: list[str],
        *,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        key = "|".join(dois)
        self.calls.append(BackendCall("lookup_dois", key, {}, max_results, list(dois)))
        return self._limit(self._consume("lookup_dois", key), max_results)


class TitleScriptedScreeningBackend:
    """Stage-1 screening double driven by acquired document titles."""

    mode = "scripted"

    def screen_envelope(
        self,
        payload: ScreenEnvelopePayload,
        *,
        rep_index: int = 0,
    ) -> UsageResult[ScreenRepWire]:
        """Return a deterministic rep from the title prefix."""
        del rep_index
        decision: Literal["relevant", "not_relevant"] = (
            "relevant" if payload.title.startswith("Relevant") else "not_relevant"
        )
        return (
            ScreenRepWire(
                decision=decision,
                confidence=0.9,
                reason=f"Title scripted as {decision}.",
            ),
            None,
        )

    def screen_fulltext(
        self, payload: ScreenFullTextPayload
    ) -> UsageResult[ScreenRepWire]:
        """Return a deterministic full-text confirmation."""
        del payload
        return (
            ScreenRepWire(
                decision="relevant",
                confidence=0.9,
                reason="Scripted full-text confirmation.",
            ),
            None,
        )


def _context(scope_id: uuid.UUID, *, intent: str = "Test intent") -> AcquireContext:
    return AcquireContext(scope_id=scope_id, intent=intent, context={})


def _deep_context(scope_id: uuid.UUID, *, intent: str = "Test intent") -> AcquireContext:
    return AcquireContext(
        scope_id=scope_id,
        intent=intent,
        context={"search": {"depth": "deep"}},
    )


def _standard_context(scope_id: uuid.UUID, *, intent: str = "Test intent") -> AcquireContext:
    return AcquireContext(
        scope_id=scope_id,
        intent=intent,
        context={"search": {"depth": "standard"}},
    )


def ov_record(
    suffix: str,
    *,
    title: str | None = None,
    snippet: str = "policy evidence snippet",
    doi: str | None = None,
) -> dict[str, Any]:
    return {
        "policy_document_id": f"ov-{suffix}",
        "pdf_document_id": f"ov-{suffix}-pdf",
        "title": title or f"Overton record {suffix}",
        "translated_title": "",
        "snippet": snippet,
        "llm_document_description": "",
        "published_on": "2024-01-01",
        "keyed_other_identifiers": {"doi": [doi]} if doi else {},
        "source": {"title": "Policy Unit", "type": "government"},
        "document_url": f"https://example.org/overton/{suffix}",
        "overton_url": f"https://example.org/overton-url/{suffix}",
        "languages": ["eng"],
        "topics": [],
    }


def _assert_acquire_invariant(counts: dict[str, Any]) -> None:
    assert (
        counts["acquired"]
        + counts["already_acquired"]
        + counts["skipped_unusable"]
        + counts["dropped_over_cap"]
        == counts["results_returned"]
    )
    for by_backend in counts["by_backend"].values():
        assert (
            by_backend["acquired"]
            + by_backend["already_acquired"]
            + by_backend["skipped_unusable"]
            + by_backend["dropped_over_cap"]
            == by_backend["results_returned"]
        )


def _search_payloads(conn: Connection, project_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        event["payload"]
        for event in events.read(conn, project_id)
        if event["event_type"] == "search.executed"
    ]


def _coverage_rows(conn: Connection, project_id: uuid.UUID) -> list[Any]:
    return list(
        conn.execute(
            select(search_coverage_record)
            .where(search_coverage_record.c.project_id == project_id)
            .order_by(search_coverage_record.c.created_at)
        )
    )


def _screening_count(conn: Connection, project_id: uuid.UUID) -> int:
    return int(
        conn.execute(
            select(sa.func.count())
            .select_from(source_screening_result)
            .where(source_screening_result.c.project_id == project_id)
        ).scalar_one()
    )


def _seed_screened_source(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    title: str,
    status: Literal["relevant", "not_relevant"] = "relevant",
    confidence: float = 0.9,
    backend: str = "openalex",
    backend_record_id: str | None = None,
    abstract: str = "Seeded screened abstract.",
    referenced_works: list[str] | None = None,
) -> uuid.UUID:
    metadata = {
        "title": title,
        "abstract": abstract,
        "abstract_source": "publisher_abstract",
        "backend": backend,
        "backend_record_id": backend_record_id or f"https://openalex.org/W{uuid.uuid4().hex[:8]}",
        "provider_fields": {"referenced_works": referenced_works or []},
    }
    _, pss_id = seed_source(conn, project_id, meta=metadata)
    _seed_screening(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        status=status,
        confidence=confidence,
    )
    return pss_id


def _seed_screening(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
    status: Literal["relevant", "not_relevant"] = "relevant",
    confidence: float = 0.9,
    screen_stage: int = 1,
) -> None:
    conn.execute(
        source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            screened_by_run_id=run_id,
            status=status,
            screen_basis="title_abstract",
            screen_decision_confidence=confidence,
            screen_stage=screen_stage,
            screened_at=now(),
        )
    )


def _seed_coverage_row(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    run_id: uuid.UUID,
    stop_condition: str = "breadth_truncated",
    created_at: datetime | None = None,
    depth: str = "deep",
) -> None:
    conn.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_id=project_id,
            acquired_by_run_id=run_id,
            backends=[
                {
                    "backend": "openalex",
                    "trust_class": "academic_aggregator",
                    "mode": "scripted",
                    "depth": depth,
                }
            ],
            scope_filters={},
            stop_condition=stop_condition,
            adequacy_verdict="adequate",
            verdict_origin="model",
            created_at=created_at or now(),
        )
    )


def _wire_queries(
    queries: list[str],
    paraphrases: list[str] | None = None,
) -> SearchQueriesWire:
    return SearchQueriesWire(queries=queries, overton_paraphrases=paraphrases or [])


def _wire_suggestions(papers: list[dict[str, Any]]) -> SearchSuggestWire:
    return SearchSuggestWire(papers=[SuggestedPaper(**paper) for paper in papers])


def _fixed_clock(values: list[float]) -> Callable[[], float]:
    iterator = iter(values)
    last = values[-1]

    def clock() -> float:
        nonlocal last
        with suppress(StopIteration):
            last = next(iterator)
        return last

    return clock


def _scripted_round_runner(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    docs_screened: list[int],
    new_confident: list[int],
    coverage_start: datetime,
) -> tuple[Callable[[], dict[str, Any]], Callable[[], dict[str, Any]], list[uuid.UUID]]:
    state = {"round": 0}
    coverage_run_ids: list[uuid.UUID] = []

    def acquire_round() -> dict[str, Any]:
        index = state["round"]
        run_id = seed_run(conn, project_id)
        coverage_run_ids.append(run_id)
        _seed_coverage_row(
            conn,
            project_id=project_id,
            scope_id=scope_id,
            run_id=run_id,
            created_at=coverage_start + timedelta(seconds=index),
        )
        return {"acquired_pss_by_verb": {}}

    def screen_round() -> dict[str, Any]:
        index = state["round"]
        for offset in range(new_confident[index]):
            _seed_screened_source(
                conn,
                project_id=project_id,
                run_id=seed_run(conn, project_id),
                scope_id=scope_id,
                title=f"Round {index} relevant {offset}",
                confidence=CONFIDENT_FLOOR,
            )
        state["round"] += 1
        return {"screened": docs_screened[index]}

    return acquire_round, screen_round, coverage_run_ids


def test_rapid_fanout_events_failed_variant_isolated(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    intent = "Evaluate home energy retrofit grants."
    queries = [
        "home energy retrofit grants",
        "residential insulation outcomes",
        "fuel poverty retrofit",
        "heat pump subsidy evaluation",
        "housing decarbonisation policy",
    ]
    paraphrases = [
        "Evidence on policy grants for home energy retrofits.",
        "Policy evaluations of residential decarbonisation incentives.",
    ]
    generation = ScriptedGenerationBackend(queries=[_wire_queries(queries, paraphrases)])
    openalex_records: list[ScriptResult] = []
    for index in range(15):
        if index == 7:
            openalex_records.append(RuntimeError("scripted OpenAlex variant failure"))
        else:
            openalex_records.append([oa_record(f"rapid-{index}")])
    openalex = ScriptedBackend(scripts={"search": openalex_records})
    overton = ScriptedBackend(
        name="overton",
        scripts={"search": [[ov_record(f"rapid-{index}")] for index in range(3)]},
    )

    counts = run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=_context(scope_id, intent=intent),
        backends=[openalex, overton],
        generation_backend=generation,
    )

    expected_openalex_queries = [
        variant
        for query in queries
        for variant in (
            query,
            f"({query}) AND {SR_CLAUSE}",
            f"({query}) AND {RCT_CLAUSE}",
        )
    ]
    assert [call.query for call in openalex.calls] == expected_openalex_queries
    assert [call.query for call in overton.calls] == [intent, *paraphrases]
    assert len(openalex.calls) == 15
    assert len(overton.calls) == 3

    payloads = _search_payloads(conn, project_id)
    assert [payload["query_origin"] for payload in payloads[:15]] == [
        origin
        for _query in queries
        for origin in ("generated", "variant_sr", "variant_rct")
    ]
    assert [payload["query_origin"] for payload in payloads[15:]] == [
        "verbatim",
        "paraphrase",
        "paraphrase",
    ]
    errored = [payload for payload in payloads if payload["status"] == "error"]
    assert len(errored) == 1
    assert "scripted OpenAlex variant failure" in errored[0]["error"]
    assert counts["by_backend"]["openalex"]["status"] == "ok"
    assert counts["by_backend"]["overton"]["status"] == "ok"
    assert counts["search"]["queries_executed"] == {"openalex": 15, "overton": 3}
    _assert_acquire_invariant(counts)


def test_generation_failure_raises_and_harness_records_component_failed(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    backend = ScriptedBackend()

    with pytest.raises(RuntimeError, match="generation failed"):
        run_search(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=_context(scope_id),
            backends=[backend],
            generation_backend=ScriptedGenerationBackend(
                queries=[RuntimeError("generation failed")]
            ),
        )

    harness_run_id = seed_run(conn, project_id)
    run_harness(
        conn,
        config=compile(Plan(component="acquire", evidence_scope_id=scope_id)),
        project_id=project_id,
        run_id=harness_run_id,
        provider=StubEchoProvider(),
        search_backends=[ScriptedBackend()],
        search_generation_backend=ScriptedGenerationBackend(
            queries=[RuntimeError("generation failed")]
        ),
    )

    log = events.read(conn, project_id)
    failed = [
        event["payload"]
        for event in log
        if event["event_type"] == "component.failed"
        and event["payload"]["component"] == "acquire"
    ]
    assert len(failed) == 1
    assert failed[0]["error"] == "generation failed"
    assert any(event["event_type"] == "run.failed" for event in log)


def test_zero_result_generated_queries_count_and_openalex_fallback(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    intent = "Find evaluations of retrofit advice services."
    queries = [f"zero query {index}" for index in range(5)]
    generation = ScriptedGenerationBackend(
        queries=[_wire_queries(queries, ["policy paraphrase"])]
    )
    openalex = ScriptedBackend(
        scripts={
            "search": [
                *([] for _ in range(15)),
                [oa_record("fallback", title="Fallback verbatim hit")],
            ]
        }
    )
    overton = ScriptedBackend(
        name="overton",
        scripts={"search": [[ov_record("verbatim")], [ov_record("para")]]},
    )

    counts = run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=_context(scope_id, intent=intent),
        backends=[openalex, overton],
        generation_backend=generation,
    )

    openalex_search_events = [
        payload for payload in _search_payloads(conn, project_id)
        if payload["backend"] == "openalex"
    ]
    assert counts["search"]["queries_zero_result"]["openalex"] == 5
    assert counts["search"]["fallback_to_verbatim"]["openalex"] is True
    assert [payload["query_origin"] for payload in openalex_search_events].count(
        "fallback_verbatim"
    ) == 1
    assert openalex_search_events[-1]["query"] == intent
    assert openalex_search_events[-1]["result_count"] == 1


def test_rapid_result_cap_is_flat_per_call_and_wall_clock_stop(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    generation = ScriptedGenerationBackend(
        queries=[_wire_queries([f"cap query {index}" for index in range(5)])]
    )
    # Each call requests the depth's flat per-call target — not that target
    # divided across the 15-call fan-out. Dividing a shared cap across a wide
    # fan-out was the bug: quota shrank to ~3-5 per call as soon as the SR/RCT
    # variant fan-out was reinstated. Every call now gets its own full-size
    # request regardless of fan-out width.
    #
    # The scripted pages deliberately over-deliver (target + 20, i.e. more than
    # the entire old shared run cap) so that reintroducing a consumption-coupled
    # `remaining` fails this test on the CALL COUNT: call #1 would bank the
    # whole cap and calls #2-15 would be skipped.
    rapid_quota = DEPTH_CONSTANTS["rapid"]["result_cap_per_backend"]
    scripted_pages: list[ScriptResult] = [
        [oa_record(f"cap-{page}-{index}") for index in range(rapid_quota + 20)]
        for page in range(15)
    ]
    capped_backend = ScriptedBackend(scripts={"search": scripted_pages})

    capped = run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[capped_backend],
        generation_backend=generation,
    )

    assert len(capped_backend.calls) == 15
    assert all(call.max_results == rapid_quota for call in capped_backend.calls)
    assert capped["results_returned"] == rapid_quota * 15
    assert capped["search"]["queries_executed"]["openalex"] == 15
    # Honest stop attribution (task 019 item 5): exhausting the planned fan-out
    # is not a wall-clock breach and not an error — a clean completion. (Nothing
    # "caps" here: there is no run cap, and rapid's OpenAlex http_budget of 20
    # is never reached by a 15-call fan-out.)
    assert capped["search"]["wall_clock_breached"] is False
    assert capped["stop_condition"] == "completed"

    second_run = seed_run(conn, project_id)
    generation_2 = ScriptedGenerationBackend(
        queries=[_wire_queries([f"clock query {index}" for index in range(5)])]
    )
    clock_backend = ScriptedBackend(
        scripts={"search": [[oa_record(f"clock-{index}")] for index in range(15)]}
    )
    clock = _fixed_clock([0.0, 0.0, 1.0, 2.0, RAPID_WALL_CLOCK_S + 1.0])

    stopped = run_search(
        conn,
        project_id=project_id,
        run_id=second_run,
        context=_context(scope_id),
        backends=[clock_backend],
        generation_backend=generation_2,
        clock=clock,
    )

    assert len(clock_backend.calls) == 3
    assert stopped["search"]["queries_executed"]["openalex"] == 3
    assert stopped["search"]["wall_clock_breached"] is True

    # Honest stop attribution (task 019 item 5): the rapid/standard fan-out's
    # own wall-clock breach reaches the coverage record run_search creates,
    # with no update-after pass — acquire_sources sees wall_clock_breached
    # before it ever writes the row.
    assert stopped["stop_condition"] == "wall_clock_exceeded"
    row = conn.execute(
        select(search_coverage_record)
        .where(search_coverage_record.c.acquired_by_run_id == second_run)
    ).one()
    assert row.stop_condition == "wall_clock_exceeded"


def test_standard_fanout_has_no_wall_clock(conn: Connection) -> None:
    """Standard has no time budget, so no query is skipped for being late.

    The clock was the only thing that ever set ``stop_all``, and the fan-out
    runs backend-outer/plan-inner: a breach part-way through the OpenAlex leg
    skipped the whole Overton leg. Volume is bounded at acquisition now
    (``record_cap_per_backend``), so an elapsed time far past the old 75 s
    budget must leave every planned call intact.
    """
    assert DEPTH_CONSTANTS["standard"]["wall_clock_s"] is None
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id, context={"search": {"depth": "standard"}})
    generation = ScriptedGenerationBackend(
        queries=[_wire_queries([f"clock query {index}" for index in range(5)])]
    )
    backend = ScriptedBackend(
        scripts={"search": [[oa_record(f"late-{index}")] for index in range(15)]}
    )

    counts = run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=_standard_context(scope_id),
        backends=[backend],
        generation_backend=generation,
        clock=_fixed_clock([0.0, 10_000.0]),
    )

    assert len(backend.calls) == 15
    assert counts["search"]["wall_clock_breached"] is False
    assert counts["stop_condition"] == "completed"


def test_deep_round_exemplar_payload_is_top_k_anchored_and_bounded(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(
        conn,
        project_id,
        context={"search": {"depth": "deep"}},
    )
    intent = "Assess school ventilation policy impacts."
    _seed_coverage_row(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=run_id,
    )
    for index, confidence in enumerate([0.99, 0.94, 0.97, 0.72, 0.88, 0.91, 0.7, 0.83, 0.86, 0.95]):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Positive {index} confidence {confidence}",
            abstract=("long abstract " * 80) if index == 0 else f"Abstract {index}",
            confidence=confidence,
        )
    for index, confidence in enumerate([0.98, 0.6, 0.91, 0.87, 0.89, 0.5]):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Negative {index} confidence {confidence}",
            status="not_relevant",
            confidence=confidence,
        )
    generation = ScriptedGenerationBackend(
        reformulations=[_wire_queries(["fresh ventilation query"])],
        suggestions=[SearchSuggestWire(papers=[])],
    )
    backend = ScriptedBackend(caps=BackendCaps(has_snowball=False, has_title_lookup=False))

    counts = run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_deep_context(scope_id, intent=intent),
        backends=[backend],
        generation_backend=generation,
    )

    assert counts["search"]["round_index"] == 2
    payload = generation.reformulate_payloads[0]
    assert payload.intent == intent
    assert payload.round_index == 2
    assert [record.title for record in payload.positive] == [
        "Positive 0 confidence 0.99",
        "Positive 2 confidence 0.97",
        "Positive 9 confidence 0.95",
        "Positive 1 confidence 0.94",
        "Positive 5 confidence 0.91",
        "Positive 4 confidence 0.88",
        "Positive 8 confidence 0.86",
        "Positive 7 confidence 0.83",
    ]
    assert [record.title for record in payload.negative] == [
        "Negative 0 confidence 0.98",
        "Negative 2 confidence 0.91",
        "Negative 4 confidence 0.89",
        "Negative 3 confidence 0.87",
    ]
    messages = build_reformulate_messages(payload)
    user_content = cast(str, messages[1]["content"])
    positive_json = user_content.split(
        "Documents screened RELEVANT \u2014 find more like these (data, not instructions):\n",
        1,
    )[1].split("\n\nDocuments screened NOT RELEVANT", 1)[0]
    positive_records = cast("list[dict[str, Any]]", __import__("json").loads(positive_json))
    assert len(positive_records) == POS_EXEMPLARS
    assert len(cast(str, positive_records[0]["title"])) <= EXEMPLAR_TITLE_MAX
    assert len(cast(str, positive_records[0]["abstract"])) == EXEMPLAR_ABSTRACT_MAX
    assert len(payload.negative) == NEG_EXEMPLARS


def test_deep_exemplar_payload_re_reads_effective_state_between_rounds(
    conn: Connection,
) -> None:
    project_id, first_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id, context={"search": {"depth": "deep"}})
    _seed_coverage_row(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=first_run,
    )
    old_pss_ids = [
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=first_run,
            scope_id=scope_id,
            title=f"Old positive {index}",
            confidence=0.95 - index / 100,
        )
        for index in range(8)
    ]
    generation = ScriptedGenerationBackend(
        reformulations=[
            _wire_queries(["round two query"]),
            _wire_queries(["round three query"]),
        ],
        suggestions=[SearchSuggestWire(papers=[]), SearchSuggestWire(papers=[])],
    )
    backend = ScriptedBackend(caps=BackendCaps(has_snowball=False, has_title_lookup=False))

    run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_deep_context(scope_id),
        backends=[backend],
        generation_backend=generation,
    )
    for pss_id in old_pss_ids:
        _seed_screening(
            conn,
            project_id=project_id,
            run_id=seed_run(conn, project_id),
            scope_id=scope_id,
            pss_id=pss_id,
            status="not_relevant",
            confidence=0.99,
            screen_stage=2,
        )
    for index in range(8):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=seed_run(conn, project_id),
            scope_id=scope_id,
            title=f"New positive {index}",
            confidence=0.94 - index / 100,
        )

    run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_deep_context(scope_id),
        backends=[backend],
        generation_backend=generation,
    )

    round_three_payload = generation.reformulate_payloads[1]
    assert round_three_payload.round_index == 3
    assert all(record.title.startswith("New positive") for record in round_three_payload.positive)
    assert not any(
        record.title.startswith("Old positive")
        for record in round_three_payload.positive
    )


def test_deep_round_fixed_allocation_snowball_suggest_and_diversity(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id, context={"search": {"depth": "deep"}})
    intent = "Map childcare subsidy trials."
    _seed_coverage_row(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=run_id,
    )
    seed_ids: list[str] = []
    for index in range(6):
        seed_id = f"https://openalex.org/Wseed{index}"
        seed_ids.append(seed_id)
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Seed positive {index}",
            confidence=0.99 - index / 100,
            backend_record_id=seed_id,
            referenced_works=[f"https://openalex.org/Wref{index}"],
        )
    generation = ScriptedGenerationBackend(
        reformulations=[_wire_queries([f"reformulated query {index}" for index in range(6)])],
        suggestions=[
            _wire_suggestions(
                [
                    {"title": "Suggested doi", "year": 2020, "doi": "10.1/doi"},
                    *[
                        {"title": f"Suggested title {index}", "year": 2020, "doi": None}
                        for index in range(7)
                    ],
                ]
            )
        ],
    )
    backend = ScriptedBackend(
        scripts={
            "search": [[] for _ in range(REFORMULATE_CALL_CAP + 1)],
            "fetch_citations": [
                [oa_record(f"cite-{index}", title=f"Citation {index}")]
                for index in range(SNOWBALL_SEEDS)
            ],
            "fetch_references": [[oa_record("backward", title="Backward reference")]],
            "lookup_dois": [[oa_record("doi", title="Suggested doi", doi="10.1/doi")]],
            "lookup_title": [
                [oa_record(f"title-{index}", title=f"Suggested title {index}")]
                for index in range(SUGGEST_CALL_CAP)
            ],
        }
    )

    counts = run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_deep_context(scope_id, intent=intent),
        backends=[backend],
        generation_backend=generation,
    )

    calls_by_verb: dict[str, list[BackendCall]] = {}
    for call in backend.calls:
        calls_by_verb.setdefault(call.verb, []).append(call)
    reformulate_events = [
        payload for payload in _search_payloads(conn, project_id)
        if payload["verb"] == "search" and payload["query_origin"] == "generated"
    ]
    assert len(reformulate_events) <= REFORMULATE_CALL_CAP
    assert not any(
        payload["query_origin"] in {"variant_sr", "variant_rct"}
        for payload in reformulate_events
    )
    assert [call.query for call in calls_by_verb["fetch_citations"]] == seed_ids[:SNOWBALL_SEEDS]
    assert len(calls_by_verb["fetch_references"]) == 1
    assert calls_by_verb["fetch_references"][0].values == [
        f"https://openalex.org/Wref{index}" for index in range(SNOWBALL_SEEDS)
    ]
    assert len(calls_by_verb["lookup_dois"]) == 1
    assert len(calls_by_verb.get("lookup_title", [])) <= SUGGEST_CALL_CAP - 1
    assert counts["search"]["arm_calls"]["diversity"] >= 1
    diversity_events = [
        payload for payload in _search_payloads(conn, project_id)
        if payload["query_origin"] in {"verbatim", "variant_sr"} and payload["query"] == intent
    ]
    assert len(diversity_events) == 1
    assert "Seed positive" not in diversity_events[0]["query"]
    # The diversity reserve is a bounded fraction of the per-call result target
    # (rubric 7): one extra un-steered call, deliberately smaller than a full
    # fan-out call rather than requesting the whole target.
    diversity_calls = [call for call in calls_by_verb["search"] if call.query == intent]
    assert len(diversity_calls) == 1
    expected_reserve = max(
        1, int(DEPTH_CONSTANTS["deep"]["result_cap_per_backend"] * DIVERSITY_FRACTION)
    )
    assert diversity_calls[0].max_results == expected_reserve


def test_standard_round_two_trims_snowball_and_suggest_arms(
    conn: Connection,
) -> None:
    """The 017 standard depth (contract rev 2.9) reuses the deep-round loop at
    round 2 but with a trimmed arm set: reformulate + diversity only. The
    backend below is fully snowball/suggest-capable, so the absence of those
    calls proves it is the depth's arm selection doing the trimming, not a
    capability gap.
    """
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id, context={"search": {"depth": "standard"}})
    intent = "Map digital skills training programmes."
    _seed_coverage_row(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=run_id,
        depth="standard",
    )
    for index in range(6):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Seed positive {index}",
            confidence=0.9 - index / 100,
            backend_record_id=f"https://openalex.org/Wstd{index}",
            referenced_works=[f"https://openalex.org/Wref{index}"],
        )
    generation = ScriptedGenerationBackend(
        reformulations=[_wire_queries(["reformulated standard query"])],
    )
    backend = ScriptedBackend(
        caps=BackendCaps(has_snowball=True, has_title_lookup=True, has_doi_lookup=True),
        scripts={"search": [[oa_record("std-reform", title="Reformulated hit")], []]},
    )

    counts = run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_standard_context(scope_id, intent=intent),
        backends=[backend],
        generation_backend=generation,
    )

    assert DEPTH_CONSTANTS["standard"]["round_cap"] == 2
    assert counts["search"]["depth"] == "standard"
    assert counts["search"]["round_index"] == 2
    assert counts["search"]["arm_calls"]["reformulate"] >= 1
    assert counts["search"]["arm_calls"]["diversity"] >= 1
    assert counts["search"]["arm_calls"]["snowball"] == 0
    assert counts["search"]["arm_calls"]["suggest"] == 0
    # Suggest gating happens before generation_backend.suggest is ever called.
    assert generation.suggest_payloads == []

    calls_by_verb: dict[str, list[BackendCall]] = {}
    for call in backend.calls:
        calls_by_verb.setdefault(call.verb, []).append(call)
    assert "fetch_citations" not in calls_by_verb
    assert "fetch_references" not in calls_by_verb
    assert "lookup_dois" not in calls_by_verb
    assert "lookup_title" not in calls_by_verb

    # Round 2 gets the depth's full per-call target directly — not whatever
    # was left of round 1's shared cap (the quota bug: round 2 used to share
    # round 1's leftovers, which was often almost nothing).
    reformulate_call = next(
        call for call in calls_by_verb["search"] if call.query == "reformulated standard query"
    )
    assert reformulate_call.max_results == DEPTH_CONSTANTS["standard"]["result_cap_per_backend"]

    origins = {payload["query_origin"] for payload in _search_payloads(conn, project_id)}
    assert not origins & {
        "snowball_forward",
        "snowball_backward",
        "suggestion_doi",
        "suggestion_title",
    }


def test_suggestion_grounding_matrix_and_screened_out_counter(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id, context={"search": {"depth": "deep"}})
    _seed_coverage_row(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=run_id,
    )
    _seed_screened_source(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        title="Positive exemplar",
        confidence=0.9,
    )
    generation = ScriptedGenerationBackend(
        reformulations=[_wire_queries([])],
        suggestions=[
            _wire_suggestions(
                [
                    {"title": "DOI Grounded", "year": 2020, "doi": "10.123/ABC"},
                    {"title": "Exact Title Grounded", "year": 2021, "doi": None},
                    {"title": "Ungrounded Suggestion", "year": 2022, "doi": None},
                    {"title": "Screened Out Grounded", "year": 2023, "doi": "10.123/OUT"},
                ]
            )
        ],
    )
    backend = ScriptedBackend(
        scripts={
            "lookup_dois": [
                [
                    oa_record("doi-a", title="DOI Grounded", doi="10.123/abc"),
                    oa_record("doi-out", title="Screened Out Grounded", doi="10.123/out"),
                ]
            ],
            "lookup_title": [
                [oa_record("title-a", title="exact title grounded")],
                [oa_record("title-b", title="A different title")],
            ],
            "search": [[]],
        }
    )

    counts = run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_deep_context(scope_id),
        backends=[backend],
        generation_backend=generation,
    )

    assert counts["search"]["suggestions_proposed"] == 4
    assert counts["search"]["suggestions_grounded"] == 3
    assert counts["search"]["suggestions_dropped"] == 1
    assert counts["acquired_pss_by_verb"]["lookup_dois"]
    assert counts["acquired_pss_by_verb"]["lookup_title"]
    assert len(counts["acquired_pss_by_verb"]["lookup_dois"]) == 2
    assert len(counts["acquired_pss_by_verb"]["lookup_title"]) == 1
    doi_call = next(call for call in backend.calls if call.verb == "lookup_dois")
    assert doi_call.values == ["10.123/abc", "10.123/out"]

    lookup_doi_pss_ids = cast("list[str]", counts["acquired_pss_by_verb"]["lookup_dois"])
    screened_out_pss = uuid.UUID(lookup_doi_pss_ids[1])
    _seed_screening(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        scope_id=scope_id,
        pss_id=screened_out_pss,
        status="not_relevant",
        confidence=0.95,
    )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=lambda: {"acquired_pss_by_verb": counts["acquired_pss_by_verb"]},
        screen_round=lambda: {"screened": 1},
        start_round=2,
        clock=_fixed_clock([0.0, 0.0, 1.0, 1.0]),
    )

    assert summary["suggest"]["grounded_screened_out"] == 1
    assert summary["suggest_grounded_screened_out"] == 1


def test_run_deep_rounds_target_reached_stop_finalises_latest_row(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    for index in range(TARGET_CONFIDENT_RELEVANT):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Target relevant {index}",
            confidence=CONFIDENT_FLOOR,
        )
    acquire_round, screen_round, coverage_run_ids = _scripted_round_runner(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        docs_screened=[0],
        new_confident=[0],
        coverage_start=datetime(2026, 1, 1, tzinfo=UTC),
    )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=acquire_round,
        screen_round=screen_round,
        start_round=2,
        clock=_fixed_clock([0.0, 0.0, 1.0, 1.0]),
    )

    rows = _coverage_rows(conn, project_id)
    assert len(rows) == 1
    assert coverage_run_ids == [rows[0].acquired_by_run_id]
    assert rows[0].stop_condition == "target_reached"
    assert summary["stop_condition"] == "target_reached"
    assert summary["overlay_applied"] is False


def test_run_deep_rounds_target_override_honoured(conn: Connection) -> None:
    """D5 search.target: a lower override stops the loop the as-built default would not.

    Only 5 confident-relevant docs are seeded — well below
    TARGET_CONFIDENT_RELEVANT — so the as-built default would not stop on
    "target_reached" here; passing target=5 does.
    """
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    override_target = 5
    for index in range(override_target):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Override relevant {index}",
            confidence=CONFIDENT_FLOOR,
        )
    acquire_round, screen_round, coverage_run_ids = _scripted_round_runner(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        docs_screened=[0],
        new_confident=[0],
        coverage_start=datetime(2026, 1, 1, tzinfo=UTC),
    )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=acquire_round,
        screen_round=screen_round,
        start_round=2,
        clock=_fixed_clock([0.0, 0.0, 1.0, 1.0]),
        target=override_target,
    )

    rows = _coverage_rows(conn, project_id)
    assert len(rows) == 1
    assert coverage_run_ids == [rows[0].acquired_by_run_id]
    assert rows[0].stop_condition == "target_reached"
    assert summary["stop_condition"] == "target_reached"
    assert summary["target_confident_relevant"] == override_target
    assert summary["overlay_applied"] is False


def test_run_deep_rounds_default_target_is_as_built_constant(conn: Connection) -> None:
    """Absent target ≡ as-built: run_deep_rounds' default equals TARGET_CONFIDENT_RELEVANT."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    for index in range(TARGET_CONFIDENT_RELEVANT):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Default target relevant {index}",
            confidence=CONFIDENT_FLOOR,
        )
    acquire_round, screen_round, _coverage_run_ids = _scripted_round_runner(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        docs_screened=[0],
        new_confident=[0],
        coverage_start=datetime(2026, 1, 1, tzinfo=UTC),
    )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=acquire_round,
        screen_round=screen_round,
        start_round=2,
        clock=_fixed_clock([0.0, 0.0, 1.0, 1.0]),
    )

    assert summary["stop_condition"] == "target_reached"
    assert summary["target_confident_relevant"] == TARGET_CONFIDENT_RELEVANT


# --- B1 search.guidance: query generation + provenance echo ---


def test_search_guidance_flows_to_query_generation_and_provenance(conn: Connection) -> None:
    """B1 behavioural + isolation: search.guidance reaches query GENERATION
    (QueriesPayload) and is echoed verbatim onto
    search_coverage_record.scope_filters — never rewriting evidence_scope
    itself (run_search takes an in-memory AcquireContext, never the row)."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    intent = "Evaluate home energy retrofit grants."
    guidance = ["prioritise UK policy evaluations", "avoid clinical literature"]
    generation = ScriptedGenerationBackend(queries=[_wire_queries(["home energy retrofit"])])
    openalex = ScriptedBackend(scripts={"search": [[oa_record("g1")]]})
    overton = ScriptedBackend(name="overton", scripts={"search": [[ov_record("g1")]]})

    run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=AcquireContext(
            scope_id=scope_id, intent=intent, context={"search": {"guidance": guidance}}
        ),
        backends=[openalex, overton],
        generation_backend=generation,
    )

    assert generation.query_payloads[0].guidance == guidance

    scope_filters = conn.execute(
        select(search_coverage_record.c.scope_filters)
        .where(search_coverage_record.c.project_id == project_id)
        .where(search_coverage_record.c.evidence_scope_id == scope_id)
    ).scalar_one()
    assert scope_filters["guidance"] == guidance


def test_search_guidance_absent_leaves_scope_filters_without_guidance_key(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    generation = ScriptedGenerationBackend(queries=[_wire_queries(["home energy retrofit"])])
    openalex = ScriptedBackend(scripts={"search": [[oa_record("g2")]]})
    overton = ScriptedBackend(name="overton", scripts={"search": [[ov_record("g2")]]})

    run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=_context(scope_id),
        backends=[openalex, overton],
        generation_backend=generation,
    )

    assert generation.query_payloads[0].guidance is None
    scope_filters = conn.execute(
        select(search_coverage_record.c.scope_filters)
        .where(search_coverage_record.c.project_id == project_id)
        .where(search_coverage_record.c.evidence_scope_id == scope_id)
    ).scalar_one()
    assert "guidance" not in scope_filters


def test_search_guidance_leaves_evidence_scope_row_unchanged(conn: Connection) -> None:
    """Isolation (mirrors the 017 screen-criteria precedent): a harness run
    over an acquire component carrying search.guidance never rewrites the
    evidence_scope row it read from."""
    project_id, run_id = seed_project_and_run(conn)
    directive = {"search": {"guidance": ["prioritise UK policy evaluations"]}}
    scope_id = seed_scope(conn, project_id, context=directive)

    config = compile(Plan(component="acquire", evidence_scope_id=scope_id))
    events.append(conn, project_id=project_id, run_id=run_id, event_type="run.started", payload={})
    events.append(
        conn, project_id=project_id, run_id=run_id, event_type="plan.compiled", payload={}
    )
    run_harness(
        conn, config=config, project_id=project_id, run_id=run_id, provider=StubEchoProvider()
    )

    row = conn.execute(
        select(evidence_scope).where(evidence_scope.c.evidence_scope_id == scope_id)
    ).one()
    assert dict(row.context) == directive


def test_run_deep_rounds_short_circuit_overlay_below_target(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    for index in range(THIN_CONFIDENT_RELEVANT - 1):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Thin relevant {index}",
            confidence=CONFIDENT_FLOOR,
        )
    acquire_round, screen_round, _coverage_run_ids = _scripted_round_runner(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        docs_screened=[10],
        new_confident=[0],
        coverage_start=datetime(2026, 1, 1, tzinfo=UTC),
    )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=acquire_round,
        screen_round=screen_round,
        start_round=2,
        clock=_fixed_clock([0.0, 0.0, 1.0, 1.0]),
    )

    rows = _coverage_rows(conn, project_id)
    assert len(rows) == 1
    assert rows[-1].stop_condition == "re_searched_still_thin"
    assert summary["stop_condition"] == "re_searched_still_thin"
    assert summary["overlay_applied"] is True


def test_run_deep_rounds_round_cap_budget_overlay_below_target(
    conn: Connection,
) -> None:
    project_id, _run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    docs = [100, 100]
    new_confident = [2, 2]
    assert new_confident[0] / docs[0] == pytest.approx(SHORT_CIRCUIT_RATE)
    acquire_round, screen_round, _coverage_run_ids = _scripted_round_runner(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        docs_screened=docs,
        new_confident=new_confident,
        coverage_start=datetime(2026, 1, 1, tzinfo=UTC),
    )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=acquire_round,
        screen_round=screen_round,
        start_round=ROUND_CAP - 1,
        clock=_fixed_clock([0.0, 0.0, 1.0, 2.0, 3.0, 4.0]),
    )

    rows = _coverage_rows(conn, project_id)
    assert len(rows) == 2
    assert rows[0].stop_condition == "breadth_truncated"
    assert rows[1].stop_condition == "re_searched_still_thin"
    assert summary["rounds"][-1]["round"] == ROUND_CAP
    assert summary["stop_condition"] == "re_searched_still_thin"
    assert summary["overlay_applied"] is True


def test_run_deep_rounds_elapsed_time_never_truncates_the_loop(
    conn: Connection,
) -> None:
    """Deep has no time budget: elapsed time cannot cut a round short.

    Standard and deep trade the wall clock for a per-round acquisition cap
    (``record_cap_per_backend``); only rapid still has a clock. Under the old
    150 s budget this clock would have stopped the loop with
    ``budget_exhausted`` before a single round ran.
    """
    assert DEEP_WALL_CLOCK_S is None
    project_id, _run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    acquire_round, screen_round, _coverage_run_ids = _scripted_round_runner(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        docs_screened=[100, 100],
        new_confident=[2, 2],
        coverage_start=datetime(2026, 1, 1, tzinfo=UTC),
    )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=acquire_round,
        screen_round=screen_round,
        start_round=2,
        clock=_fixed_clock([0.0, 10_000.0]),
    )

    assert [entry["round"] for entry in summary["rounds"]] == [2, ROUND_CAP]
    assert summary["wall_clock_s"] == 10_000.0


def test_should_escalate_boundary(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    for index in range(THIN_CONFIDENT_RELEVANT - 1):
        _seed_screened_source(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            title=f"Boundary relevant {index}",
            confidence=CONFIDENT_FLOOR,
        )

    assert confident_relevant_count(conn, project_id=project_id, scope_id=scope_id) == 7
    assert should_escalate(conn, project_id=project_id, scope_id=scope_id) is True

    _seed_screened_source(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        title="Boundary relevant 7",
        confidence=CONFIDENT_FLOOR,
    )

    assert confident_relevant_count(conn, project_id=project_id, scope_id=scope_id) == 8
    assert should_escalate(conn, project_id=project_id, scope_id=scope_id) is False


def test_rapid_thin_flow_runs_one_bounded_deep_continuation(
    conn: Connection,
) -> None:
    project_id, rapid_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    generation = ScriptedGenerationBackend(
        queries=[_wire_queries(["thin rapid query"])],
        reformulations=[_wire_queries([])],
        suggestions=[SearchSuggestWire(papers=[])],
    )
    rapid_backend = ScriptedBackend(
        scripts={
            "search": [
                [oa_record(f"thin-{index}", title=f"Relevant thin {index}") for index in range(7)],
                [],
                [],
            ]
        }
    )

    run_search(
        conn,
        project_id=project_id,
        run_id=rapid_run,
        context=_context(scope_id),
        backends=[rapid_backend],
        generation_backend=generation,
    )
    screen_sources(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=ScreenContext(scope_id=scope_id, intent="Test intent", context={}),
        screening_backend=TitleScriptedScreeningBackend(),
    )
    assert should_escalate(conn, project_id=project_id, scope_id=scope_id) is True

    deep_calls = {"count": 0}

    def acquire_round() -> dict[str, Any]:
        deep_calls["count"] += 1
        return run_search(
            conn,
            project_id=project_id,
            run_id=seed_run(conn, project_id),
            context=_deep_context(scope_id),
            backends=[
                ScriptedBackend(
                    caps=BackendCaps(has_snowball=False, has_title_lookup=False),
                    scripts={"search": [[]]},
                )
            ],
            generation_backend=generation,
        )

    summary = run_deep_rounds(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        acquire_round=acquire_round,
        screen_round=lambda: screen_sources(
            conn,
            project_id=project_id,
            run_id=seed_run(conn, project_id),
            context=ScreenContext(scope_id=scope_id, intent="Test intent", context={}),
            screening_backend=TitleScriptedScreeningBackend(),
        ),
        start_round=2,
        clock=_fixed_clock([0.0, 0.0, 1.0, 1.0]),
    )

    assert deep_calls["count"] == 1
    assert summary["stop_condition"] == "re_searched_still_thin"
    assert _coverage_rows(conn, project_id)[-1].stop_condition == "re_searched_still_thin"

    fat_project_id, fat_run = seed_project_and_run(conn)
    fat_scope_id = seed_scope(conn, fat_project_id)
    fat_generation = ScriptedGenerationBackend(queries=[_wire_queries(["fat rapid query"])])
    fat_backend = ScriptedBackend(
        scripts={
            "search": [
                [oa_record(f"fat-{index}", title=f"Relevant fat {index}") for index in range(8)],
                [],
                [],
            ]
        }
    )
    run_search(
        conn,
        project_id=fat_project_id,
        run_id=fat_run,
        context=_context(fat_scope_id),
        backends=[fat_backend],
        generation_backend=fat_generation,
    )
    screen_sources(
        conn,
        project_id=fat_project_id,
        run_id=seed_run(conn, fat_project_id),
        context=ScreenContext(scope_id=fat_scope_id, intent="Test intent", context={}),
        screening_backend=TitleScriptedScreeningBackend(),
    )
    assert should_escalate(conn, project_id=fat_project_id, scope_id=fat_scope_id) is False


def test_acquire_search_does_not_write_screening_rows(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id, context={"search": {"depth": "deep"}})
    _seed_screened_source(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        title="Seeded steering row",
        confidence=0.9,
    )
    before = _screening_count(conn, project_id)
    generation = ScriptedGenerationBackend(
        queries=[_wire_queries(["rapid query"])],
        reformulations=[_wire_queries(["deep query"])],
        suggestions=[SearchSuggestWire(papers=[])],
    )

    run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_context(scope_id),
        backends=[
            ScriptedBackend(
                scripts={"search": [[oa_record("rapid-new", title="Rapid acquired")], [], []]}
            )
        ],
        generation_backend=generation,
    )
    _seed_coverage_row(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=run_id,
    )
    run_search(
        conn,
        project_id=project_id,
        run_id=seed_run(conn, project_id),
        context=_deep_context(scope_id),
        backends=[
            ScriptedBackend(
                caps=BackendCaps(has_snowball=False, has_title_lookup=False),
                scripts={"search": [[oa_record("deep-new", title="Deep acquired")]]},
            )
        ],
        generation_backend=generation,
    )

    assert _screening_count(conn, project_id) == before
    assert (
        conn.execute(
            select(sa.func.count())
            .select_from(project_source_snapshot)
            .where(project_source_snapshot.c.project_id == project_id)
        ).scalar_one()
        > before
    )
