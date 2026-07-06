"""Tests for the select component: allocation, directives, persistence, rerank."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.grouping import GroupingDoc
from policy_atlas.ranking import RankedDoc
from policy_atlas.schema import (
    characterisation_result,
    project_source_snapshot,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
)
from policy_atlas.select import (
    DirectiveError,
    SelectContext,
    SelectError,
    select_scope,
)
from tests.helpers import now, seed_project_and_run, seed_run, seed_scope, seed_screening_result
from tests.helpers import seed_source as helper_seed_source

EVIDENCE_TYPE = "RCTs and Quasi-Experimental Studies"
NON_EVIDENCE_TYPE = "Other (Non-evidence documents)"


def _seed_select_doc(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    title: str,
    evidence_type: str | None = EVIDENCE_TYPE,
    quality: int | None = 3,
    year: int = 2026,
    origin: str = "uploaded",
    text_basis: str = "full_text",
) -> uuid.UUID:
    snap_id, pss_id = helper_seed_source(
        conn,
        project_id,
        meta={"title": title, "abstract": f"Abstract for {title}.", "year": year},
    )
    conn.execute(
        sa.update(project_source_snapshot)
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
        .values(origin=origin)
    )
    conn.execute(
        sa.update(source_snapshot)
        .where(source_snapshot.c.source_snapshot_id == snap_id)
        .values(text_basis=text_basis)
    )
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    if evidence_type is not None:
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            classified_by_run_id=run_id,
            primary_evidence_type=evidence_type,
            classified_at=now(),
        ))
    if quality is not None:
        conn.execute(source_appraisal_result.insert().values(
            source_appraisal_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            appraised_by_run_id=run_id,
            quality_score=quality,
            rubric_version="test-rubric",
            appraised_at=now(),
        ))
    return pss_id


def _seed_characterisation(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    themes: dict[str, list[uuid.UUID]],
    unclustered: list[uuid.UUID] | None = None,
) -> None:
    conn.execute(characterisation_result.insert().values(
        characterisation_id=uuid.uuid4(),
        project_id=project_id,
        evidence_scope_id=scope_id,
        run_id=run_id,
        grouping_provenance={"backend_mode": "stub"},
        coverage={"base": "screened"},
        themes={
            "themes": [
                {
                    "name": name,
                    "description": f"{name} documents",
                    "member_ids": [str(pss_id) for pss_id in ids],
                    "size": len(ids),
                }
                for name, ids in themes.items()
            ],
            "unclustered_ids": [str(pss_id) for pss_id in (unclustered or [])],
        },
        created_at=now(),
    ))


def _run_select(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    characterisation_run_id: uuid.UUID,
    *,
    context: dict[str, Any] | None = None,
    backend: Any = None,
) -> tuple[dict[str, Any], Any, uuid.UUID]:
    run_id = seed_run(conn, project_id)
    summary = select_scope(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=SelectContext(
            scope_id=scope_id,
            intent="Select the best evidence.",
            context=context or {},
            characterisation_run_id=characterisation_run_id,
        ),
        ranking_backend=backend,
    )
    row = conn.execute(
        select(selection_result)
        .where(selection_result.c.project_id == project_id)
        .where(selection_result.c.run_id == run_id)
    ).one()
    return summary, row, run_id


def _selection_row_count(conn: Connection, project_id: uuid.UUID) -> int:
    return int(
        conn.execute(
            select(sa.func.count())
            .select_from(selection_result)
            .where(selection_result.c.project_id == project_id)
        ).scalar_one()
    )


def _payload_columns(row: Any) -> dict[str, Any]:
    mapping = row._mapping
    return {
        "strategy": mapping["strategy"],
        "budget": mapping["budget"],
        "selection_provenance": json.loads(json.dumps(mapping["selection_provenance"])),
        "selected": json.loads(json.dumps(mapping["selected"])),
        "excluded": json.loads(json.dumps(mapping["excluded"])),
        "flags": json.loads(json.dumps(mapping["flags"])),
    }


def _docs(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    prefix: str,
    count: int,
) -> list[uuid.UUID]:
    return [
        _seed_select_doc(conn, project_id, run_id, scope_id, title=f"{prefix}-{index}")
        for index in range(count)
    ]


def test_allocation_math_matches_hand_computed_fixture(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 10)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 6)
    theme_c = _docs(conn, pid, characterise_run_id, scope_id, "C", 2)
    unclustered = _docs(conn, pid, characterise_run_id, scope_id, "U", 2)
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": theme_a, "B": theme_b, "C": theme_c},
        unclustered=unclustered,
    )

    summary, row, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={"selection": {"budget": 8}},
    )

    # Four non-empty strata get breadth floors: A/B/C/unclustered = 1 each.
    # Remainder is 4 over remaining capacities A=9, B=5, C=1, unclustered=1
    # (total 16): quotas A=2.25, B=1.25, C=0.25, U=0.25. Floors give A=2,
    # B=1 and one leftover; all fractions tie at 0.25, so stratum order gives
    # it to A. Final allocations: A=4, B=2, C=1, unclustered=1.
    assert {
        item["name"]: item["allocated_count"]
        for item in summary["strata"]
    } == {"A": 4, "B": 2, "C": 1, "unclustered": 1}
    assert summary["selected"] == {
        "count": 8,
        "by_reason": {"breadth_floor": 4, "ranked": 4},
    }
    assert row._mapping["excluded"]["by_stratum"] == {
        "A": {"ranked_below_cut": 6},
        "B": {"ranked_below_cut": 4},
        "C": {"budget_exhausted": 1},
        "unclustered": {"budget_exhausted": 1},
    }
    assert row._mapping["excluded"]["base"] == {
        "screened_in": 20,
        "non_evidence": 0,
        "eligible": 20,
        "not_in_characterisation": 0,
    }
    assert row._mapping["flags"] == {}


def test_budget_below_strata_grants_floors_in_stratum_order(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 4)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 3)
    theme_c = _docs(conn, pid, characterise_run_id, scope_id, "C", 2)
    theme_d = _docs(conn, pid, characterise_run_id, scope_id, "D", 1)
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": theme_a, "B": theme_b, "C": theme_c, "D": theme_d},
    )

    summary, row, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={"selection": {"budget": 2}},
    )

    # Budget 2 is exhausted by breadth floors. Stratum order is count desc then
    # name: A(4), B(3), C(2), D(1), so only A and B get one selected doc.
    assert [
        (item["name"], item["allocated_count"], item["selected_count"])
        for item in summary["strata"]
    ] == [("A", 1, 1), ("B", 1, 1), ("C", 0, 0), ("D", 0, 0), ("unclustered", 0, 0)]
    assert row._mapping["excluded"]["by_stratum"] == {
        "A": {"budget_exhausted": 3},
        "B": {"budget_exhausted": 2},
        "C": {"budget_exhausted": 2},
        "D": {"budget_exhausted": 1},
    }
    assert row._mapping["flags"]["large_stratum_excluded"] == ["C"]


def test_exhausted_stratum_surplus_redistributes(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 1)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 9)
    theme_c = _docs(conn, pid, characterise_run_id, scope_id, "C", 9)
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": theme_a, "B": theme_b, "C": theme_c},
    )

    summary, _row, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={"selection": {"budget": 8}},
    )

    # Floors spend 3 slots: A=1, B=1, C=1. Remaining budget is 5. A has no
    # remaining capacity, B and C each have 8. Quotas are B=2.5, C=2.5; floors
    # give 2+2 and the one leftover goes to B by stratum-order tie-break.
    assert {
        item["name"]: item["allocated_count"]
        for item in summary["strata"]
    } == {"B": 4, "C": 3, "A": 1, "unclustered": 0}
    assert summary["selected"]["count"] == 8


def test_must_include_bypasses_budget_and_conflict_is_notable(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 3)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 3)
    missing_id = uuid.uuid4()
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": theme_a, "B": theme_b},
    )

    summary, row, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={
            "selection": {
                "budget": 2,
                "must_include_ids": [str(theme_a[0]), str(missing_id)],
            }
        },
    )

    # The A must-include is outside budget and covers A's floor. Budget 2 then
    # gives B one breadth floor and the one proportional leftover to A, so total
    # selected is budget 2 + one valid must-include = 3.
    assert summary["selected"] == {
        "count": 3,
        "by_reason": {"must_include": 1, "breadth_floor": 1, "ranked": 1},
    }
    assert row._mapping["excluded"]["notable"] == [
        {"pss_id": str(missing_id), "flag": "must_include_not_in_scope"}
    ]
    assert row._mapping["flags"]["must_include_conflict"] == [str(missing_id)]
    a_records = [record for record in row._mapping["selected"] if record["stratum"] == "A"]
    assert a_records[0]["pss_id"] == str(theme_a[0])
    assert a_records[0]["reason"] == "must_include"


def test_deterministic_runs_write_identical_payload_columns(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 3)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 2)
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": theme_a, "B": theme_b},
    )

    _summary_1, row_1, _ = _run_select(conn, pid, scope_id, characterise_run_id)
    _summary_2, row_2, _ = _run_select(conn, pid, scope_id, characterise_run_id)

    assert json.dumps(_payload_columns(row_1), sort_keys=True) == json.dumps(
        _payload_columns(row_2),
        sort_keys=True,
    )


def test_directive_validation_empty_equivalence_and_boost_reordering(
    conn: Connection,
) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    uploaded = _seed_select_doc(
        conn,
        pid,
        characterise_run_id,
        scope_id,
        title="uploaded",
        origin="uploaded",
        quality=3,
    )
    acquired = _seed_select_doc(
        conn,
        pid,
        characterise_run_id,
        scope_id,
        title="acquired",
        origin="acquired",
        quality=3,
    )
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": [uploaded, acquired]},
    )

    with pytest.raises(DirectiveError):
        _run_select(conn, pid, scope_id, characterise_run_id, context={"selection": {"bad": 1}})
    with pytest.raises(DirectiveError):
        _run_select(
            conn,
            pid,
            scope_id,
            characterise_run_id,
            context={
                "selection": {
                    "boosts": [{"match": {"column": "origin", "equals": "acquired"},
                                "weight": 11}]
                }
            },
        )
    assert _selection_row_count(conn, pid) == 0

    _summary_absent, row_absent, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
    )
    _summary_empty, row_empty, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={"selection": {}},
    )
    assert json.dumps(_payload_columns(row_absent), sort_keys=True) == json.dumps(
        _payload_columns(row_empty),
        sort_keys=True,
    )

    _summary_default, row_default, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={"selection": {"budget": 1}},
    )
    _summary_boost, row_boost, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={
            "selection": {
                "budget": 1,
                "boosts": [
                    {"match": {"column": "origin", "equals": "acquired"}, "weight": 10}
                ],
            }
        },
    )

    # With no boost, uploaded composite is 0.735: recency 0.25 + quality 0.125
    # + text_basis 0.20 + screen_confidence 0.135 + origin 0.15. Acquired is
    # 0.660 because origin contributes 0.075, so uploaded wins. The acquired
    # boost multiplies 0.660 by 10, so acquired deterministically wins budget 1.
    assert row_default._mapping["selected"][0]["pss_id"] == str(uploaded)
    assert row_boost._mapping["selected"][0]["pss_id"] == str(acquired)
    _summary_all, row_all, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={
            "selection": {
                "budget": 2,
                "boosts": [
                    {"match": {"column": "origin", "equals": "acquired"}, "weight": 10}
                ],
            }
        },
    )
    assert {record["pss_id"] for record in row_all._mapping["selected"]} == {
        str(uploaded),
        str(acquired),
    }


def test_missing_characterisation_empty_scope_and_unclustered_select_all(
    conn: Connection,
) -> None:
    pid, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_select_doc(conn, pid, run_id, scope_id, title="missing-char")

    with pytest.raises(SelectError, match="run characterise first"):
        _run_select(conn, pid, scope_id, uuid.uuid4())
    assert _selection_row_count(conn, pid) == 0

    empty_scope = seed_scope(conn, pid)
    summary = select_scope(
        conn,
        project_id=pid,
        run_id=seed_run(conn, pid),
        context=SelectContext(
            scope_id=empty_scope,
            intent="Empty",
            context={},
            characterisation_run_id=uuid.uuid4(),
        ),
        ranking_backend=None,
    )
    assert summary["flags"] == {"empty_scope": {"eligible": 0}}
    assert _selection_row_count(conn, pid) == 0

    unclustered_scope = seed_scope(conn, pid)
    docs = _docs(conn, pid, run_id, unclustered_scope, "U", 3)
    _seed_characterisation(
        conn,
        pid,
        unclustered_scope,
        run_id,
        themes={},
        unclustered=docs,
    )
    summary_all, row_all, _ = _run_select(
        conn,
        pid,
        unclustered_scope,
        run_id,
        context={"selection": {"budget": 5}},
    )
    # One unclustered stratum gets one floor, then the remaining two docs are
    # selected by ranked remainder because budget exceeds the candidate count.
    assert summary_all["strata"] == [{
        "name": "unclustered",
        "candidate_count": 3,
        "allocated_count": 3,
        "selected_count": 3,
        "selected_ids": summary_all["strata"][0]["selected_ids"],
        "full_text_share_candidates": 1.0,
        "full_text_share_selected": 1.0,
    }]
    assert row_all._mapping["excluded"]["by_stratum"] == {}
    assert summary_all["selected"]["by_reason"] == {"breadth_floor": 1, "ranked": 2}


def test_non_evidence_and_not_in_characterisation_are_base_counts(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    in_characterisation = _docs(conn, pid, characterise_run_id, scope_id, "A", 2)
    _seed_select_doc(
        conn,
        pid,
        characterise_run_id,
        scope_id,
        title="non-evidence",
        evidence_type=NON_EVIDENCE_TYPE,
    )
    _seed_select_doc(conn, pid, characterise_run_id, scope_id, title="late-eligible")
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": in_characterisation},
    )

    summary, row, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={"selection": {"budget": 5}},
    )

    assert summary["base"] == {"screened_in": 4, "non_evidence": 1, "eligible": 3}
    assert row._mapping["excluded"]["base"] == {
        "screened_in": 4,
        "non_evidence": 1,
        "eligible": 3,
        "not_in_characterisation": 1,
    }
    assert summary["selected"]["count"] == 2


class _PartialRankingBackend:
    mode = "stub"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.scored_id: str | None = None

    def rank(self, batch: list[GroupingDoc], *, intent: str) -> list[RankedDoc]:
        del intent
        ids = [doc["id"] for doc in batch]
        self.calls.append(ids)
        self.scored_id = ids[0]
        return [{"doc_id": ids[0], "score": 0, "reason": "Only valid scored doc."}]


def test_llm_rerank_contested_scope_and_fallback_ordering(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 4)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 1)
    _seed_characterisation(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        themes={"A": theme_a, "B": theme_b},
    )
    backend = _PartialRankingBackend()

    summary, row, _ = _run_select(
        conn,
        pid,
        scope_id,
        characterise_run_id,
        context={"selection": {"budget": 3}},
        backend=backend,
    )

    # Floors spend A=1 and B=1. The one remaining slot goes to A because B is
    # exhausted, so A is contested: 2 of 4 rankable docs selected. B is wholly
    # selected and must not be sent to the reranker. The backend scores one A doc
    # and omits three; scored docs sort before fallback docs even with score 0.
    assert len(backend.calls) == 1
    assert set(backend.calls[0]) == {str(pss_id) for pss_id in theme_a}
    assert set(backend.calls[0]).isdisjoint({str(pss_id) for pss_id in theme_b})
    assert summary["selected"]["count"] == 3

    selected_a = [record for record in row._mapping["selected"] if record["stratum"] == "A"]
    assert len(selected_a) == 2
    assert selected_a[0]["pss_id"] == backend.scored_id
    assert selected_a[0]["llm_score"] == 0
    assert selected_a[0]["llm_reason"] == "Only valid scored doc."
    assert selected_a[0]["rank_fallback"] is False
    assert selected_a[1]["rank_fallback"] is True
    assert "llm_score" not in selected_a[1]

    selected_b = [record for record in row._mapping["selected"] if record["stratum"] == "B"]
    assert len(selected_b) == 1
    assert "llm_score" not in selected_b[0]
    assert "rank_fallback" not in selected_b[0]

    provenance = row._mapping["selection_provenance"]
    assert provenance["strategy_version"] == "llm_rerank_v1"
    assert provenance["prompt_version"] == "select_rerank_v1"
    assert provenance["model"] == "gpt-5-mini"
    assert provenance["call_budget"] == {"baseline": 1, "maximum": 2, "used": 1}
    assert provenance["retry_count"] == 0
    assert provenance["fallback_count"] == 3
