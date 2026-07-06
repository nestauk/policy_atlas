"""Tests for the select component: allocation, directives, persistence, rerank."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas import events
from policy_atlas.characterise import ScreenedSource
from policy_atlas.grouping import GroupingDoc
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.plan import Plan, compile
from policy_atlas.ranking import RankedDoc
from policy_atlas.schema import (
    TOPIC_THEME,
    artefact,
    block,
    characterisation_result,
    project_source_snapshot,
    runs,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_snapshot,
)
from policy_atlas.select import (
    DEFAULT_SELECTION_BUDGET,
    DirectiveError,
    SelectContext,
    SelectError,
    SelectionCandidate,
    SelectionDirective,
    SelectionStratum,
    select_documents,
    select_scope,
)
from policy_atlas.tags import insert_source_tags
from tests.helpers import (
    delete_project_data,
    now,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
)
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


# --- Schema constraints ---


def test_schema_constraints_reject_bad_rows(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    docs = _docs(conn, pid, characterise_run_id, scope_id, "A", 2)
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": docs})
    _summary, row, run_id = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 2}}
    )
    selection_result_id = row._mapping["selection_result_id"]

    with pytest.raises(IntegrityError, match="ck_selr_strategy"), conn.begin_nested():
        conn.execute(
            selection_result.update()
            .where(selection_result.c.selection_result_id == selection_result_id)
            .values(strategy="bogus_strategy")
        )

    with pytest.raises(IntegrityError, match="ck_selr_budget_positive"), conn.begin_nested():
        conn.execute(
            selection_result.update()
            .where(selection_result.c.selection_result_id == selection_result_id)
            .values(budget=0)
        )

    # Duplicate (evidence_scope_id, run_id): the row above already occupies
    # (scope_id, run_id) — a second insert for the same pair must be rejected.
    with pytest.raises(IntegrityError, match="uq_selr_scope_run"), conn.begin_nested():
        conn.execute(selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=pid,
            evidence_scope_id=scope_id,
            run_id=run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={},
            selected=[],
            excluded={},
            flags={},
            created_at=now(),
        ))

    # Cross-project guard: evidence_scope_id belongs to project pid, but run_id
    # belongs to a different project (pid_b) — no (run_id, project_id=pid) row
    # exists in runs, so fk_selr_run_project rejects it.
    pid_b, run_b = seed_project_and_run(conn)
    with pytest.raises(IntegrityError), conn.begin_nested():
        conn.execute(selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=pid,
            evidence_scope_id=scope_id,
            run_id=run_b,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={},
            selected=[],
            excluded={},
            flags={},
            created_at=now(),
        ))
    del pid_b


# --- Eligibility ---


def test_eligibility_base_ladder_by_evidence_type(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="non-evidence", evidence_type=NON_EVIDENCE_TYPE,
    )
    unknown = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="unknown", evidence_type="Unknown / Insufficient information",
    )
    unclassified = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="unclassified", evidence_type=None,
    )
    _seed_characterisation(
        conn, pid, scope_id, characterise_run_id,
        themes={"A": [unknown, unclassified]},
    )

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 5}}
    )

    # 3 docs screened relevant: 1 "Other (Non-evidence documents)" excluded;
    # "Unknown / Insufficient information" and unclassified/NULL both eligible.
    # screened_in (3) == non_evidence (1) + eligible (2).
    assert summary["base"] == {"screened_in": 3, "non_evidence": 1, "eligible": 2}
    assert summary["base"]["screened_in"] == (
        summary["base"]["non_evidence"] + summary["base"]["eligible"]
    )
    assert row._mapping["excluded"]["base"]["non_evidence"] == 1


# --- Counting invariants ---


def test_counting_invariants_on_mixed_fixture(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 5)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 4)
    unclustered_docs = _docs(conn, pid, characterise_run_id, scope_id, "U", 1)
    _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="non-evidence", evidence_type=NON_EVIDENCE_TYPE,
    )
    _seed_select_doc(conn, pid, characterise_run_id, scope_id, title="late-eligible")
    _seed_characterisation(
        conn, pid, scope_id, characterise_run_id,
        themes={"A": theme_a, "B": theme_b},
        unclustered=unclustered_docs,
    )

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id,
        context={
            "selection": {"budget": 4, "must_include_ids": [str(theme_b[0])]},
        },
    )

    # screened_in = 5 + 4 + 1 + 1(late) + 1(non-evidence) = 12; non_evidence = 1;
    # eligible = 11.
    #
    # Floors (stratum order A(5), B(4), unclustered(1)): A has no must-include so
    # gets a floor (remaining 4->3); B's floor is skipped because it already has
    # a must-include; unclustered gets a floor (remaining 3->2). Capacities:
    # A = 5-0-1=4, B = 4-1-0=3, unclustered = 1-0-1=0. Ranked slots for the
    # remaining budget of 2 over capacities {A:4, B:3}: quotas A=8/7β‰ˆ1.14,
    # B=6/7β‰ˆ0.86; floor(quota) gives A=1, B=0, one leftover goes to B (larger
    # fraction) -> ranked A=1, B=1, unclustered=0.
    # Allocated: A=1+1=2, B=0+1=1 (+1 must), unclustered=1+0=1.
    # Selected = must(1) + breadth_floor(A:1, unclustered:1 = 2) + ranked(A:1, B:1 = 2) = 5.
    assert summary["base"] == {"screened_in": 12, "non_evidence": 1, "eligible": 11}
    assert summary["selected"] == {
        "count": 5,
        "by_reason": {"must_include": 1, "breadth_floor": 2, "ranked": 2},
    }
    # Excluded: A candidates(5) - selected(2) = 3 ranked_below_cut;
    # B candidates(4) - selected(2, incl. must) = 2 ranked_below_cut;
    # unclustered candidates(1) - selected(1) = 0 (no entry).
    assert row._mapping["excluded"]["by_stratum"] == {
        "A": {"ranked_below_cut": 3},
        "B": {"ranked_below_cut": 2},
    }
    assert row._mapping["excluded"]["base"]["not_in_characterisation"] == 1

    eligible = summary["base"]["eligible"]
    excluded_total = sum(
        sum(reasons.values())
        for reasons in row._mapping["excluded"]["by_stratum"].values()
    )
    not_in_characterisation = row._mapping["excluded"]["base"]["not_in_characterisation"]
    assert eligible == summary["selected"]["count"] + excluded_total + not_in_characterisation
    assert summary["selected"]["count"] == sum(summary["selected"]["by_reason"].values())

    strata_names = {stratum["name"] for stratum in summary["strata"]}
    for record in row._mapping["selected"]:
        assert record["stratum"] in strata_names


# --- Text-basis tilt (soft) ---


def test_text_basis_soft_tilt_ranks_full_text_above_but_never_excludes(
    conn: Connection,
) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    full_text_doc = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="full", text_basis="full_text", quality=3, year=2026, origin="uploaded",
    )
    abstract_doc = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="abstract", text_basis="abstract_only", quality=3, year=2026, origin="uploaded",
    )
    _seed_characterisation(
        conn, pid, scope_id, characterise_run_id,
        themes={"A": [full_text_doc, abstract_doc]},
    )

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 2}}
    )

    # Both docs share recency=1.0 (year 2026, age 0), quality=(3-1)/4=0.5,
    # screen_confidence=0.9 (default relevant screening), origin=1.0 (uploaded).
    # composite_full     = .25*1 + .25*.5 + .20*1.00 + .15*.9 + .15*1 = 0.86
    # composite_abstract = .25*1 + .25*.5 + .20*0.25 + .15*.9 + .15*1 = 0.71
    # difference = 0.20 * (1.0 - 0.25) = 0.15, matching 0.86 - 0.71.
    records = {record["pss_id"]: record for record in row._mapping["selected"]}
    assert records[str(full_text_doc)]["composite"] == pytest.approx(0.86)
    assert records[str(abstract_doc)]["composite"] == pytest.approx(0.71)
    assert (
        records[str(full_text_doc)]["composite"] - records[str(abstract_doc)]["composite"]
        == pytest.approx(0.15)
    )
    # Full-text ranks first (breadth floor goes to the top-composite doc); budget
    # covers both, so the abstract-only doc is still selected (flag, not block).
    assert row._mapping["selected"][0]["pss_id"] == str(full_text_doc)
    assert {str(full_text_doc), str(abstract_doc)} == set(records)
    assert summary["selected"]["count"] == 2


# --- Missing-signal flag-not-block ---


def test_missing_signals_flag_not_block() -> None:
    # NULL screen_confidence is unreachable through the DB for a "relevant"
    # screening row (ck_ssr_non_null_when_decided forbids it), so this signal
    # combination is exercised at the pure select_documents level instead of
    # through select_scope/DB fixtures, per the same ScreenedSource shape
    # screened_sources() would build.
    pss_id = uuid.uuid4()
    source = ScreenedSource(
        pss_id=pss_id,
        source_snapshot_id=uuid.uuid4(),
        full_text_snapshot_id=None,
        origin="uploaded",
        full_text_status="not_attempted",
        full_text_error=None,
        metadata={"title": "missing", "abstract": "Abstract."},  # no "year" key
        source_locator="test.pdf",
        text_basis="full_text",
        screen_basis="title_abstract",
        screen_confidence=None,  # NULL screen confidence
        primary_evidence_type=EVIDENCE_TYPE,
        quality_score=None,  # no appraisal row
        rubric_version=None,
    )
    candidate = SelectionCandidate(source=source, tags=())
    stratum = SelectionStratum(name="A", candidate_ids=(pss_id,))

    outcome = select_documents(
        [candidate],
        strata=[stratum],
        strategy="coverage_stratified_v1",
        directive=SelectionDirective(budget=1),
        intent="Test intent",
        ranking_backend=None,
    )

    # No year -> recency reads 0.5; no appraisal row -> quality reads 0.5;
    # NULL screen confidence -> screen_confidence reads 0.5. text_basis is set
    # (full_text) and origin is "uploaded", so those two stay non-missing.
    assert len(outcome.selected) == 1
    record = outcome.selected[0]
    assert record["pss_id"] == str(pss_id)
    assert record["signals"]["recency"] == 0.5
    assert record["signals"]["quality"] == 0.5
    assert record["signals"]["screen_confidence"] == 0.5
    assert record["missing_signals"] == ["recency", "quality", "screen_confidence"]

    assert outcome.provenance["signal_availability"]["recency"] == 1
    assert outcome.provenance["signal_availability"]["quality"] == 1
    assert outcome.provenance["signal_availability"]["screen_confidence"] == 1
    assert outcome.provenance["signal_availability"]["text_basis"] == 0
    assert outcome.provenance["signal_availability"]["origin"] == 0


# --- Directive semantics ---


def test_directive_tag_boost_reorders_stratum_and_never_excludes(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    better = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="better", quality=5, year=2026, origin="uploaded", text_basis="full_text",
    )
    worse = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id,
        title="worse", quality=1, year=2011, origin="acquired", text_basis="abstract_only",
    )
    insert_source_tags(
        conn, project_id=pid, run_id=characterise_run_id, now=now(),
        assertions=[(worse, "boosted", "test")],
    )
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": [better, worse]})

    # composite_better = .25*1(recency,2026) + .25*1((5-1)/4=1,quality) + .20*1(full_text)
    #                   + .15*.9(screen_confidence) + .15*1(uploaded) = 0.985
    # composite_worse   = .25*0(recency,2011,age15) + .25*0((1-1)/4=0,quality)
    #                   + .20*.25(abstract_only) + .15*.9 + .15*.5(acquired) = 0.26
    # weight 4 x 0.26 = 1.04 > 0.985, so a tag boost of 4 reorders the stratum.
    _summary_no_boost, row_no_boost, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 1}}
    )
    assert row_no_boost._mapping["selected"][0]["pss_id"] == str(better)

    boost_context = {
        "selection": {
            "budget": 1,
            "boosts": [{"match": {"tag_type": TOPIC_THEME, "tag": "boosted"}, "weight": 4}],
        }
    }
    _summary_boost, row_boost, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context=boost_context
    )
    assert row_boost._mapping["selected"][0]["pss_id"] == str(worse)

    # Boost can never exclude: with budget covering both, the unboosted
    # (higher-composite) doc is still selected alongside the boosted one.
    all_context = {
        "selection": {
            "budget": 2,
            "boosts": [{"match": {"tag_type": TOPIC_THEME, "tag": "boosted"}, "weight": 4}],
        }
    }
    _summary_all, row_all, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context=all_context
    )
    assert {record["pss_id"] for record in row_all._mapping["selected"]} == {
        str(better), str(worse),
    }


def test_directive_year_boost_matches_only_in_range_docs(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    in_range = _seed_select_doc(conn, pid, characterise_run_id, scope_id, title="in", year=2021)
    below_range = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id, title="below", year=2015
    )
    above_range = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id, title="above", year=2025
    )
    _seed_characterisation(
        conn, pid, scope_id, characterise_run_id,
        themes={"A": [in_range, below_range, above_range]},
    )

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id,
        context={
            "selection": {
                "budget": 3,
                "boosts": [
                    {"match": {"year": {"gte": 2020, "lte": 2022}}, "weight": 5},
                ],
            },
        },
    )

    # Only the year-2021 doc falls in [2020, 2022]; its boost_multiplier is the
    # weight (5), the other two docs stay unmultiplied (1.0).
    records = {record["pss_id"]: record for record in row._mapping["selected"]}
    assert records[str(in_range)]["boost_multiplier"] == 5
    assert records[str(below_range)]["boost_multiplier"] == 1.0
    assert records[str(above_range)]["boost_multiplier"] == 1.0
    assert row._mapping["selection_provenance"]["unmatched_boosts"] == []
    assert summary["selected"]["count"] == 3


def test_directive_boost_matching_zero_docs_flags_unmatched_and_completes(
    conn: Connection,
) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    doc = _seed_select_doc(conn, pid, characterise_run_id, scope_id, title="doc", origin="uploaded")
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": [doc]})

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id,
        context={
            "selection": {
                "budget": 1,
                "boosts": [{"match": {"column": "origin", "equals": "acquired"}, "weight": 2}],
            },
        },
    )

    # The only doc is "uploaded"; a boost matching "acquired" matches zero docs
    # (index 0 in the boosts list) but the run still completes normally.
    assert row._mapping["selection_provenance"]["unmatched_boosts"] == [0]
    assert summary["selected"]["count"] == 1


def test_directive_and_source_recorded_whole_in_provenance(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    doc = _seed_select_doc(conn, pid, characterise_run_id, scope_id, title="doc")
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": [doc]})

    _summary_default, row_default, _ = _run_select(conn, pid, scope_id, characterise_run_id)
    provenance_default = row_default._mapping["selection_provenance"]
    assert provenance_default["directive_source"] == "default"
    assert provenance_default["directive"] == {
        "budget": DEFAULT_SELECTION_BUDGET,
        "must_include_ids": [],
        "boosts": [],
        "weight_emphasis": {},
        "priority_strata": [],
    }

    _summary_ctx, row_ctx, _ = _run_select(
        conn, pid, scope_id, characterise_run_id,
        context={"selection": {"budget": 3, "must_include_ids": [str(doc)]}},
    )
    provenance_ctx = row_ctx._mapping["selection_provenance"]
    assert provenance_ctx["directive_source"] == "scope_context"
    assert provenance_ctx["directive"] == {
        "budget": 3,
        "must_include_ids": [str(doc)],
        "boosts": [],
        "weight_emphasis": {},
        "priority_strata": [],
    }


# --- Trigger-flag fixtures ---


def test_trigger_flag_large_stratum_excluded_detail_payload(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a = _docs(conn, pid, characterise_run_id, scope_id, "A", 6)
    theme_b = _docs(conn, pid, characterise_run_id, scope_id, "B", 5)
    _seed_characterisation(
        conn, pid, scope_id, characterise_run_id, themes={"A": theme_a, "B": theme_b}
    )

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 1}}
    )

    # Eligible total 11; 20% threshold = 2.2. Budget 1's one floor slot goes to
    # A (processed first: 6 > 5 candidates), leaving B (5 candidates, above the
    # 2.2 threshold) with zero selected.
    assert row._mapping["flags"]["large_stratum_excluded"] == ["B"]
    assert summary["selected"]["count"] == 1


def test_trigger_flag_thin_base(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    docs = _docs(conn, pid, characterise_run_id, scope_id, "A", 3)
    conn.execute(
        source_screening_result.update()
        .where(source_screening_result.c.project_source_snapshot_id.in_(docs))
        .values(screen_decision_confidence=0.5)
    )
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": docs})

    _summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 3}}
    )

    # All 3 eligible docs have confidence 0.5 < SUFFICIENT_CONFIDENCE (0.6), so
    # sufficiently_confident = 0, below the THIN_BASE_FLOOR of 10.
    assert row._mapping["flags"]["thin_base"] == {"sufficiently_confident": 0, "floor": 10}


def test_trigger_flag_thin_full_text(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    full = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id, title="full", text_basis="full_text"
    )
    abs1 = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id, title="abs1", text_basis="abstract_only"
    )
    abs2 = _seed_select_doc(
        conn, pid, characterise_run_id, scope_id, title="abs2", text_basis="abstract_only"
    )
    _seed_characterisation(
        conn, pid, scope_id, characterise_run_id, themes={"A": [full, abs1, abs2]}
    )

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 3}}
    )

    # Budget covers the whole stratum: all 3 selected. 1 of 3 is full_text, so
    # full_text_share = 1/3 β‰ˆ 0.333, below THIN_FULL_TEXT_SHARE (0.5).
    assert summary["selected"]["count"] == 3
    assert row._mapping["flags"]["thin_full_text"] == {
        "share": pytest.approx(1 / 3), "floor": 0.5,
    }


def test_trigger_flag_negative_case_has_no_flags(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    docs = _docs(conn, pid, characterise_run_id, scope_id, "A", 12)
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": docs})

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 12}}
    )

    # 12 eligible docs, all full_text, screen_confidence 0.9 (>= 10 sufficiently
    # confident docs, full_text_share 1.0); the single stratum is fully selected
    # (never zero): no trigger-flag threshold is crossed.
    assert summary["selected"]["count"] == 12
    assert row._mapping["flags"] == {}


# --- Rationale bidirectionality + shares ---


def test_rationale_bidirectional_with_hand_computed_full_text_shares(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    theme_a_full = [
        _seed_select_doc(
            conn, pid, characterise_run_id, scope_id, title=f"A-full-{i}", text_basis="full_text"
        )
        for i in range(2)
    ]
    theme_a_abs = [
        _seed_select_doc(
            conn, pid, characterise_run_id, scope_id, title=f"A-abs-{i}",
            text_basis="abstract_only",
        )
        for i in range(2)
    ]
    theme_b_full = [
        _seed_select_doc(
            conn, pid, characterise_run_id, scope_id, title="B-full", text_basis="full_text"
        )
    ]
    theme_b_abs = [
        _seed_select_doc(
            conn, pid, characterise_run_id, scope_id, title="B-abs", text_basis="abstract_only"
        )
    ]
    theme_a = theme_a_full + theme_a_abs
    theme_b = theme_b_full + theme_b_abs
    _seed_characterisation(
        conn, pid, scope_id, characterise_run_id, themes={"A": theme_a, "B": theme_b}
    )

    summary, row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 3}}
    )

    # All docs share identical non-text_basis signals, so full_text docs always
    # out-rank abstract_only docs within a stratum (0.86 vs 0.71 composite, per
    # the text-basis tilt test above).
    #
    # Stratum order A(4), B(2): floor A=1 (remaining 3->2), floor B=1
    # (remaining 2->1). Capacities: A=4-0-1=3, B=2-0-1=1. Ranked slot(s)=1 over
    # capacities {A:3, B:1}; quotas A=0.75, B=0.25 -> the 1 leftover goes to A
    # (larger fraction). Allocated: A=1+1=2, B=1+0=1.
    # A candidates=4, selected=2 (both full_text docs, higher composite) ->
    #   full_text_share_candidates=2/4=0.5, full_text_share_selected=2/2=1.0.
    # B candidates=2, selected=1 (the full_text doc) ->
    #   full_text_share_candidates=1/2=0.5, full_text_share_selected=1/1=1.0.
    # Excluded: A has 2 unselected with ranked_slots>0 -> ranked_below_cut:2;
    # B has 1 unselected with ranked_slots==0 -> budget_exhausted:1.
    strata_by_name = {stratum["name"]: stratum for stratum in summary["strata"]}
    assert strata_by_name["A"]["candidate_count"] == 4
    assert strata_by_name["A"]["allocated_count"] == 2
    assert strata_by_name["A"]["selected_count"] == 2
    assert strata_by_name["A"]["full_text_share_candidates"] == 0.5
    assert strata_by_name["A"]["full_text_share_selected"] == 1.0
    assert set(strata_by_name["A"]["selected_ids"]) == {str(pss_id) for pss_id in theme_a_full}

    assert strata_by_name["B"]["candidate_count"] == 2
    assert strata_by_name["B"]["allocated_count"] == 1
    assert strata_by_name["B"]["selected_count"] == 1
    assert strata_by_name["B"]["full_text_share_candidates"] == 0.5
    assert strata_by_name["B"]["full_text_share_selected"] == 1.0
    assert strata_by_name["B"]["selected_ids"] == [str(theme_b_full[0])]

    assert row._mapping["excluded"]["by_stratum"] == {
        "A": {"ranked_below_cut": 2},
        "B": {"budget_exhausted": 1},
    }
    # Bidirectional: both the selected list and the excluded aggregate are
    # present in the one persisted row.
    assert len(row._mapping["selected"]) == 3
    assert row._mapping["excluded"]["by_stratum"]


# --- Summary payload shape freeze ---


def test_summary_payload_shape_is_frozen(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    docs = _docs(conn, pid, characterise_run_id, scope_id, "A", 2)
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": docs})

    summary, _row, _ = _run_select(
        conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 2}}
    )

    assert set(summary.keys()) == {
        "strata", "selected", "excluded", "base", "characterisation_run_id",
        "flags", "provenance",
    }
    assert summary["strata"], "fixture must produce at least one stratum"
    for stratum in summary["strata"]:
        assert set(stratum.keys()) == {
            "name", "candidate_count", "allocated_count", "selected_count",
            "selected_ids", "full_text_share_candidates", "full_text_share_selected",
        }


# --- Harness round-trip ---


def test_harness_select_component_success(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    docs = _docs(conn, pid, characterise_run_id, scope_id, "A", 2)
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": docs})

    rid = seed_run(conn, pid)
    plan = Plan(
        component="select", evidence_scope_id=scope_id,
        characterisation_run_id=characterise_run_id,
    )
    config = compile(plan)
    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    log_entries = events.read(conn, pid)
    started = [
        e for e in log_entries
        if e["event_type"] == "component.started" and e["payload"].get("component") == "select"
    ]
    completed = [
        e for e in log_entries
        if e["event_type"] == "component.completed" and e["payload"].get("component") == "select"
    ]
    assert len(started) == 1
    assert len(completed) == 1
    payload = completed[0]["payload"]
    assert {
        "strata", "selected", "excluded", "base", "characterisation_run_id",
        "flags", "provenance",
    } <= set(payload.keys())

    count = conn.execute(
        select(sa.func.count())
        .select_from(selection_result)
        .where(selection_result.c.run_id == rid)
    ).scalar_one()
    assert count == 1

    run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert run_row.status == "succeeded"


def test_harness_select_component_missing_characterisation_fails(conn: Connection) -> None:
    pid, other_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_select_doc(conn, pid, other_run_id, scope_id, title="doc")

    rid = seed_run(conn, pid)
    plan = Plan(
        component="select", evidence_scope_id=scope_id,
        characterisation_run_id=uuid.uuid4(),
    )
    config = compile(plan)
    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    log_entries = events.read(conn, pid)
    failed = [
        e for e in log_entries
        if e["event_type"] == "component.failed" and e["payload"].get("component") == "select"
    ]
    assert len(failed) == 1
    assert "run characterise first" in failed[0]["payload"]["error"]

    count = conn.execute(
        select(sa.func.count())
        .select_from(selection_result)
        .where(selection_result.c.run_id == rid)
    ).scalar_one()
    assert count == 0

    run_failed = [e for e in log_entries if e["event_type"] == "run.failed"]
    assert len(run_failed) == 1
    run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert run_row.status == "failed"


# --- delete_project_data ---


def test_delete_project_data_removes_selection_result(conn: Connection) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    docs = _docs(conn, pid, characterise_run_id, scope_id, "A", 2)
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": docs})
    _run_select(conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 2}})

    conn.commit()
    delete_project_data(conn, pid)
    conn.commit()

    count = conn.execute(
        select(sa.func.count())
        .select_from(selection_result)
        .where(selection_result.c.project_id == pid)
    ).scalar_one()
    assert count == 0


# --- Downstream untouched ---


def test_select_writes_no_artefact_or_block_and_leaves_screening_untouched(
    conn: Connection,
) -> None:
    pid, characterise_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    docs = _docs(conn, pid, characterise_run_id, scope_id, "A", 2)
    _seed_characterisation(conn, pid, scope_id, characterise_run_id, themes={"A": docs})

    screening_before = conn.execute(
        select(source_screening_result)
        .where(source_screening_result.c.project_id == pid)
        .order_by(source_screening_result.c.project_source_snapshot_id)
    ).fetchall()

    _run_select(conn, pid, scope_id, characterise_run_id, context={"selection": {"budget": 2}})

    artefact_count = conn.execute(
        select(sa.func.count()).select_from(artefact).where(artefact.c.project_id == pid)
    ).scalar_one()
    block_count = conn.execute(
        select(sa.func.count())
        .select_from(block)
        .where(
            block.c.artefact_id.in_(
                select(artefact.c.artefact_id).where(artefact.c.project_id == pid)
            )
        )
    ).scalar_one()
    assert artefact_count == 0
    assert block_count == 0

    screening_after = conn.execute(
        select(source_screening_result)
        .where(source_screening_result.c.project_id == pid)
        .order_by(source_screening_result.c.project_source_snapshot_id)
    ).fetchall()
    assert screening_after == screening_before
