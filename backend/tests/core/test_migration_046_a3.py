"""Round-trip coverage for the task 046 amendment 3 revision (``f1b6d3a8c2e5``).

amendment-3-final § 2.11 (R71, R73, R75): two nullable text columns on
``intervention_profile_record``; ``population`` → ``unit`` on it and on the two
finding tables, ``population_tag`` → ``unit_tag`` with its check; the union
view recreated with ``unit``; the stored grouping facet ``"population"`` →
``"unit"`` in every stored place (Q26): plan payloads, the grouping result
(keys, group ids, provenance) and every stored reference to a group id. The
downgrade reverses all of it and a finding row's text survives both ways. The ``engine`` fixture is
session-scoped and the test database shared, so the test leaves the chain at
head and removes the task it wrote.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    extraction_result,
    grouping_result,
    source_extraction_record,
    synthesis_result,
    task_plan,
)
from tests.conftest import _alembic_cfg
from tests.helpers import (
    delete_task_data,
    now,
    seed_run,
    seed_scope,
    seed_source,
    seed_task_and_run,
)

PRE_REVISION = "e9a4c1f7b3d2"
_IPR = "intervention_profile_record"
_FINDING_TABLES = ("intervention_outcome_finding", "implementation_context_finding")

_UNIT_TEXT = {
    "iof": "adults on low incomes",
    "icf": "local authorities in England",
    "interventions": "secondary schools",
}

_PLAN_WITH_FACET: dict[str, Any] = {
    "title": "Grouped by who",
    "grouping_facets": ["intervention", "population", "barrier_theme"],
    "steer_point_defaults": [
        {"steer_point": "search_review", "action": "proceed_flag"},
        {
            "steer_point": "finding_groups",
            "action": "proceed_flag",
            "option_id": "regroup",
            "delta": {"group": {"grouping": {"facets": ["population", "outcome"]}}},
        },
        {
            "steer_point": "finding_groups",
            "action": "proceed_flag",
            "option_id": "regroup",
            "delta": {"group": {"grouping": {"facet": "population"}}},
        },
    ],
}
_PLAN_WITHOUT_FACET: dict[str, Any] = {
    "title": "Grouped by what",
    "grouping_facets": ["intervention", "outcome"],
    "scoping_notes": ["the population of interest is adults"],
    "steer_point_defaults": [],
}


def _columns(conn: Connection, table: str) -> set[str]:
    return {str(column["name"]) for column in inspect(conn).get_columns(table)}


def _checks(conn: Connection) -> set[str]:
    return {str(check["name"]) for check in inspect(conn).get_check_constraints(_IPR)}


def _seed_pre_revision(
    conn: Connection,
) -> tuple[uuid.UUID, dict[str, uuid.UUID], dict[str, uuid.UUID]]:
    """Rows in the shape the tables had before this revision (``population``)."""
    task_id, run_id = seed_task_and_run(conn)
    snapshot_id, tss_id = seed_source(conn, task_id)
    record_id = uuid.uuid4()
    conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=record_id,
            task_id=task_id,
            source_snapshot_id=snapshot_id,
            task_source_snapshot_id=tss_id,
            extraction_fingerprint="fp",
            status="extracted",
            basis="abstract_only",
            finding_count=3,
            run_id=run_id,
            created_at=now(),
        )
    )
    ids = {kind: uuid.uuid4() for kind in _UNIT_TEXT}
    common = {"t": task_id, "r": record_id, "c": now()}
    conn.execute(
        text(
            "INSERT INTO intervention_outcome_finding (finding_id, task_id, "
            "extraction_record_id, intervention, outcome, population, effect_direction, "
            "stratum_qualifiers, statistics, field_coverage, grounding, created_at) "
            "VALUES (:f, :t, :r, 'Cash transfer', 'employment', :p, 'increase', "
            "'[]', '{}', '{}', '[]', :c)"
        ),
        {**common, "f": ids["iof"], "p": _UNIT_TEXT["iof"]},
    )
    conn.execute(
        text(
            "INSERT INTO implementation_context_finding (finding_id, task_id, "
            "extraction_record_id, context_type, claim, intervention, population, "
            "field_coverage, grounding, created_at) "
            "VALUES (:f, :t, :r, 'barrier', 'Staff turnover slowed delivery.', "
            "'Cash transfer', :p, '{}', '[]', :c)"
        ),
        {**common, "f": ids["icf"], "p": _UNIT_TEXT["icf"]},
    )
    conn.execute(
        text(
            "INSERT INTO intervention_profile_record (record_id, task_id, "
            "extraction_record_id, intervention, role, design_features, components, "
            "population, population_tag, field_coverage, grounding, created_at) "
            "VALUES (:f, :t, :r, 'Breakfast club', 'evaluated', '[]', '[]', :p, "
            "'adjacent', '{}', '[]', :c)"
        ),
        {**common, "f": ids["interventions"], "p": _UNIT_TEXT["interventions"]},
    )
    plans = {}
    for version, (name, payload) in enumerate(
        (("with", _PLAN_WITH_FACET), ("without", _PLAN_WITHOUT_FACET)), start=1
    ):
        plans[name] = uuid.uuid4()
        conn.execute(
            task_plan.insert().values(
                plan_id=plans[name],
                task_id=task_id,
                version=version,
                status="superseded" if version == 1 else "approved",
                payload=payload,
                created_at=now(),
                created_by="user",
            )
        )
    return task_id, ids, plans


def _payload(conn: Connection, plan_id: uuid.UUID) -> dict[str, Any]:
    return dict(
        conn.execute(select(task_plan.c.payload).where(task_plan.c.plan_id == plan_id)).scalar_one()
    )


def _view_units(conn: Connection, task_id: uuid.UUID, column: str) -> dict[str, str | None]:
    rows = conn.execute(
        text(f"SELECT kind, {column} FROM finding_reference_union WHERE task_id = :t"),
        {"t": task_id},
    ).all()
    return {str(row[0]): row[1] for row in rows}


def _swapped(payload: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """The expected payload: every stored facet value ``old`` written as ``new``."""
    raw = json.dumps(payload).replace(f'"{old}"', f'"{new}"')
    return dict(json.loads(raw))


def test_the_revision_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    task_id: uuid.UUID | None = None
    try:
        command.downgrade(cfg, PRE_REVISION)
        with engine.begin() as conn:
            task_id, ids, plans = _seed_pre_revision(conn)

        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            ipr_columns = _columns(conn, _IPR)
            assert {"unit", "unit_tag", "programme_name", "study_country"} <= ipr_columns
            assert not {"population", "population_tag"} & ipr_columns
            for table in _FINDING_TABLES:
                columns = _columns(conn, table)
                assert "unit" in columns
                assert "population" not in columns
            assert "ck_ipr_unit_tag" in _checks(conn)
            assert "ck_ipr_population_tag" not in _checks(conn)

            # An old row reads null in the two new columns and keeps its text under unit.
            row = conn.execute(
                text(
                    "SELECT unit, unit_tag, programme_name, study_country "
                    "FROM intervention_profile_record WHERE record_id = :r"
                ),
                {"r": ids["interventions"]},
            ).one()
            assert tuple(row) == (_UNIT_TEXT["interventions"], "adjacent", None, None)
            for kind, table in zip(("iof", "icf"), _FINDING_TABLES, strict=True):
                stored = conn.execute(
                    text(f"SELECT unit FROM {table} WHERE finding_id = :f"), {"f": ids[kind]}
                ).scalar_one()
                assert stored == _UNIT_TEXT[kind]

            # The union view returns unit from all three branches.
            assert _view_units(conn, task_id, "unit") == _UNIT_TEXT

            # The stored facet reads "unit" in the list and in the standing rules.
            assert _payload(conn, plans["with"]) == _swapped(_PLAN_WITH_FACET, "population", "unit")
            assert _payload(conn, plans["with"])["grouping_facets"] == [
                "intervention",
                "unit",
                "barrier_theme",
            ]
            # A plan without the facet is untouched, free text included.
            assert _payload(conn, plans["without"]) == _PLAN_WITHOUT_FACET

            with pytest.raises(IntegrityError, match="ck_ipr_unit_tag"), conn.begin_nested():
                conn.execute(
                    text(
                        "UPDATE intervention_profile_record SET unit_tag = 'wider' "
                        "WHERE record_id = :r"
                    ),
                    {"r": ids["interventions"]},
                )
            conn.execute(
                text(
                    "UPDATE intervention_profile_record SET programme_name = 'Magic Breakfast', "
                    "study_country = 'United Kingdom' WHERE record_id = :r"
                ),
                {"r": ids["interventions"]},
            )

        command.downgrade(cfg, PRE_REVISION)
        with engine.connect() as conn:
            ipr_columns = _columns(conn, _IPR)
            assert {"population", "population_tag"} <= ipr_columns
            assert not {"unit", "unit_tag", "programme_name", "study_country"} & ipr_columns
            assert "ck_ipr_population_tag" in _checks(conn)
            assert "ck_ipr_unit_tag" not in _checks(conn)
            # A finding row's text survives the downgrade.
            for kind, table in zip(("iof", "icf"), _FINDING_TABLES, strict=True):
                stored = conn.execute(
                    text(f"SELECT population FROM {table} WHERE finding_id = :f"),
                    {"f": ids[kind]},
                ).scalar_one()
                assert stored == _UNIT_TEXT[kind]
            assert _view_units(conn, task_id, "population") == _UNIT_TEXT
            assert _payload(conn, plans["with"]) == _PLAN_WITH_FACET
            assert _payload(conn, plans["without"]) == _PLAN_WITHOUT_FACET

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert _view_units(conn, task_id, "unit") == _UNIT_TEXT
            assert _payload(conn, plans["with"])["grouping_facets"][1] == "unit"
    finally:
        command.upgrade(cfg, "head")
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


# --- Q26: the grouping result and the stored group-id references -------------

_FINDING = "11111111-1111-1111-1111-111111111111"


def _bucket(facet: str) -> dict[str, Any]:
    residual: dict[str, Any] = {"finding_ids": [], "member_finding_ids": [], "direction_spread": {}}
    return {
        "groups": [
            {
                "group_id": f"{facet}:g01",
                "facet": facet,
                "label": "Adults in work",
                "description": "Adults in paid work.",
                "member_values": ["adults"],
                "member_finding_ids": [_FINDING],
                "size": 1,
                "direction_spread": {"increase": 1},
            }
        ],
        "ungrouped": {**residual, "values": []},
        "no_value": residual,
    }


_GROUPS = {"population": _bucket("population"), "intervention": _bucket("intervention")}
_COUNTS = {"population": {"groups": 1}, "intervention": {"groups": 1}}
_FLAGS = {"population": {"status": "succeeded"}, "intervention": {"status": "succeeded"}}
_PROVENANCE = {
    "prompt_version": "group_v1",
    "facet": None,
    "facets": ["intervention", "population"],
    "facet_runs": {"intervention": {"calls_used": 1}, "population": {"calls_used": 2}},
}
_SINGLE_PROVENANCE = {
    "prompt_version": "group_v1",
    "facet": "population",
    "facets": ["population"],
    "facet_runs": {"population": {"calls_used": 2}},
}
_THEME = {
    "claim_id": "c1",
    "claim_type": "theme",
    "text": "Adults in work respond.",
    "theme": {
        "source": "grouping",
        "referenced_ids": ["population:g01", "intervention:g01"],
        "base": "grouping run",
    },
}
_PATTERN = {
    "claim_id": "c2",
    "claim_type": "pattern",
    "text": "Most findings increase.",
    "pattern": {"computed_from": "group_direction_spread", "group_id": "population:g01"},
}
# Characterisation theme ids are not group ids: never rewritten.
_CHARACTERISATION_THEME = {
    "claim_id": "c3",
    "claim_type": "theme",
    "text": "A corpus theme.",
    "theme": {"source": "characterisation", "referenced_ids": ["population:t1"], "base": "b"},
}
_BLOCK_SPECS = [
    {"title": "Who", "block_id": "b-1", "group_ids": ["population:g01", "intervention:g01"]},
    {"title": "What", "block_id": "b-2", "group_ids": ["intervention:g01"]},
]


def _renamed(value: Any, old: str, new: str) -> Any:
    """The expected value: the facet ``old`` and the id prefix ``old:`` as ``new``."""
    raw = json.dumps(value).replace(f'"{old}"', f'"{new}"').replace(f'"{old}:', f'"{new}:')
    return json.loads(raw)


def _seed_grouping_chain(conn: Connection) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    """A grouping result with the facet, one without, and the rows citing its ids."""
    task_id, extraction_run = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run,
            extraction_provenance={},
            docs=[],
            counts={},
            flags={},
            created_at=now(),
        )
    )
    ids: dict[str, uuid.UUID] = {}
    rows: tuple[tuple[str, Any, Any, Any, Any], ...] = (
        ("with", _GROUPS, _COUNTS, _FLAGS, _PROVENANCE),
        ("single", {"population": _bucket("population")}, {"population": {}},
         {"population": {}}, _SINGLE_PROVENANCE),
        (
            "without",
            {"intervention": _bucket("intervention")},
            {"intervention": {"groups": 1}},
            {"intervention": {"status": "succeeded"}},
            {**_PROVENANCE, "facets": ["intervention"], "facet_runs": {"intervention": {}}},
        ),
    )
    grouping_runs: dict[str, uuid.UUID] = {}
    for name, groups, counts, flags, provenance in rows:
        grouping_runs[name] = seed_run(conn, task_id)
        ids[f"grouping_{name}"] = uuid.uuid4()
        conn.execute(
            grouping_result.insert().values(
                grouping_result_id=ids[f"grouping_{name}"],
                task_id=task_id,
                evidence_scope_id=scope_id,
                run_id=grouping_runs[name],
                extraction_run_id=extraction_run,
                grouping_provenance=provenance,
                groups=groups,
                counts=counts,
                flags=flags,
                created_at=now(),
            )
        )
    artefact_id, block_id = uuid.uuid4(), uuid.uuid4()
    conn.execute(
        artefact.insert().values(
            artefact_id=artefact_id, task_id=task_id, title="Report", created_at=now()
        )
    )
    conn.execute(
        block.insert().values(
            block_id=block_id,
            artefact_id=artefact_id,
            content="Adults in work respond.",
            content_hash="h",
            created_at=now(),
        )
    )
    for name, payload in (
        ("theme", _THEME),
        ("pattern", _PATTERN),
        ("characterisation", _CHARACTERISATION_THEME),
    ):
        unit_id = uuid.uuid4()
        conn.execute(
            addressable_unit.insert().values(
                unit_id=unit_id,
                block_id=block_id,
                unit_type="text_span",
                locator={"start": 0, "end": 5},
                content="Adults",
                created_at=now(),
            )
        )
        ids[f"annotation_{name}"] = uuid.uuid4()
        conn.execute(
            annotation.insert().values(
                annotation_id=ids[f"annotation_{name}"],
                block_id=block_id,
                unit_id=unit_id,
                annotation_type=name if name != "characterisation" else "theme",
                payload=payload,
                created_at=now(),
            )
        )
    for name, specs, grouping_run in (
        ("with", _BLOCK_SPECS, grouping_runs["with"]),
        ("without", [_BLOCK_SPECS[1]], grouping_runs["without"]),
    ):
        ids[f"synthesis_{name}"] = uuid.uuid4()
        conn.execute(
            synthesis_result.insert().values(
                synthesis_result_id=ids[f"synthesis_{name}"],
                task_id=task_id,
                evidence_scope_id=scope_id,
                run_id=seed_run(conn, task_id),
                grouping_run_id=grouping_run,
                artefact_id=artefact_id,
                synthesis_provenance={},
                blocks=specs,
                counts={},
                flags={},
                created_at=now(),
            )
        )
    return task_id, ids


def _grouping(conn: Connection, row_id: uuid.UUID) -> dict[str, Any]:
    row = conn.execute(
        select(
            grouping_result.c.groups,
            grouping_result.c.counts,
            grouping_result.c.flags,
            grouping_result.c.grouping_provenance,
        ).where(grouping_result.c.grouping_result_id == row_id)
    ).one()
    return {
        "groups": row.groups,
        "counts": row.counts,
        "flags": row.flags,
        "provenance": row.grouping_provenance,
    }


def _annotation(conn: Connection, row_id: uuid.UUID) -> Any:
    return conn.execute(
        select(annotation.c.payload).where(annotation.c.annotation_id == row_id)
    ).scalar_one()


def _blocks(conn: Connection, row_id: uuid.UUID) -> Any:
    return conn.execute(
        select(synthesis_result.c.blocks).where(synthesis_result.c.synthesis_result_id == row_id)
    ).scalar_one()


def _raw(conn: Connection, table: str, column: str, key: str, row_id: uuid.UUID) -> str:
    """The stored JSON text, to prove an untouched row is byte-identical."""
    return str(
        conn.execute(
            text(f"SELECT {column}::text FROM {table} WHERE {key} = :r"), {"r": row_id}
        ).scalar_one()
    )


def test_the_facet_key_and_its_group_ids_move_everywhere_and_back(engine: Engine) -> None:
    cfg = _alembic_cfg()
    task_id: uuid.UUID | None = None
    stored_before = {
        "with": {"groups": _GROUPS, "counts": _COUNTS, "flags": _FLAGS, "provenance": _PROVENANCE},
        "single": {
            "groups": {"population": _bucket("population")},
            "counts": {"population": {}},
            "flags": {"population": {}},
            "provenance": _SINGLE_PROVENANCE,
        },
    }
    try:
        command.downgrade(cfg, PRE_REVISION)
        with engine.begin() as conn:
            task_id, ids = _seed_grouping_chain(conn)
        with engine.connect() as conn:
            untouched = {
                "grouping": _raw(
                    conn, "grouping_result", "groups", "grouping_result_id",
                    ids["grouping_without"],
                ),
                "grouping_provenance": _raw(
                    conn, "grouping_result", "grouping_provenance", "grouping_result_id",
                    ids["grouping_without"],
                ),
                "characterisation": _raw(
                    conn, "annotation", "payload", "annotation_id",
                    ids["annotation_characterisation"],
                ),
                "synthesis": _raw(
                    conn, "synthesis_result", "blocks", "synthesis_result_id",
                    ids["synthesis_without"],
                ),
            }

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            for name, before in stored_before.items():
                after = _grouping(conn, ids[f"grouping_{name}"])
                assert after == _renamed(before, "population", "unit")
            after = _grouping(conn, ids["grouping_with"])
            assert set(after["groups"]) == {"unit", "intervention"}
            group = after["groups"]["unit"]["groups"][0]
            assert (group["group_id"], group["facet"]) == ("unit:g01", "unit")
            assert after["groups"]["intervention"] == _bucket("intervention")
            assert after["provenance"]["facets"] == ["intervention", "unit"]
            assert set(after["provenance"]["facet_runs"]) == {"intervention", "unit"}
            single = _grouping(conn, ids["grouping_single"])["provenance"]
            assert (single["facet"], single["facets"]) == ("unit", ["unit"])

            theme = _annotation(conn, ids["annotation_theme"])
            assert theme["theme"]["referenced_ids"] == ["unit:g01", "intervention:g01"]
            assert theme == _renamed(_THEME, "population", "unit")
            pattern = _annotation(conn, ids["annotation_pattern"])
            assert pattern["pattern"]["group_id"] == "unit:g01"
            blocks = _blocks(conn, ids["synthesis_with"])
            assert [spec["group_ids"] for spec in blocks] == [
                ["unit:g01", "intervention:g01"],
                ["intervention:g01"],
            ]

            # Rows without the facet stay byte-identical.
            assert untouched == {
                "grouping": _raw(
                    conn, "grouping_result", "groups", "grouping_result_id",
                    ids["grouping_without"],
                ),
                "grouping_provenance": _raw(
                    conn, "grouping_result", "grouping_provenance", "grouping_result_id",
                    ids["grouping_without"],
                ),
                "characterisation": _raw(
                    conn, "annotation", "payload", "annotation_id",
                    ids["annotation_characterisation"],
                ),
                "synthesis": _raw(
                    conn, "synthesis_result", "blocks", "synthesis_result_id",
                    ids["synthesis_without"],
                ),
            }

        command.downgrade(cfg, PRE_REVISION)
        with engine.connect() as conn:
            for name, before in stored_before.items():
                assert _grouping(conn, ids[f"grouping_{name}"]) == before
            assert _annotation(conn, ids["annotation_theme"]) == _THEME
            assert _annotation(conn, ids["annotation_pattern"]) == _PATTERN
            assert _annotation(conn, ids["annotation_characterisation"]) == (
                _CHARACTERISATION_THEME
            )
            assert _blocks(conn, ids["synthesis_with"]) == _BLOCK_SPECS
    finally:
        command.upgrade(cfg, "head")
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)
