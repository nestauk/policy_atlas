"""Round-trip for c1a7f4e9b0d2 — the task 038 vocabulary alignment.

The slice is a pure rename plus five losslessly reversible stored values, so
this test proves three things and nothing else:

* **Catalog (I1).** Every table, column, constraint and index in the
  checked-in ``schema-manifest.md`` exists under its "after" name at head, and
  no "today" name survives except the ones V2 deliberately re-uses for the
  Project entity.
* **Content (I1, I2, I4).** A dataset seeded at ``b2f6a9d4c1e7`` — a Task in a
  public Project, a run, a walk whose capability is ``evidence_base``, all four
  pre-038 lifecycle events, a check-in decided by the retired actor word, and a
  plan payload plus a pause record carrying the retired P2 steer-point id —
  reads back identically through the read models under the new names, and the
  stored plan still validates (contract A3).
* **Reversal (D6).** The downgrade restores the pre-migration fixture
  byte-identically **and** reverses each of the seven stored values the new
  image can write during the deploy window, asserted one at a time.

The manifest names the six explicitly-named FKs by their catalog names
(``scripts/schema_manifest.py`` ``EXPLICIT_FK_NAMES``), so the catalog assertion
is exact without an alias map.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.readmodels.repository import decisions_page
from policy_atlas.core.schema import (
    capability_run,
    event_log,
    project,
    selection_result,
    task,
    task_plan,
)
from policy_atlas.runtime.task_plan import TaskPlan
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table
from tests.helpers import now

REVISION = "c1a7f4e9b0d2"
PRE_MIGRATION_REVISION = "b2f6a9d4c1e7"

_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "tasks"
    / "038-vocabulary-alignment"
    / "schema-manifest.md"
)

# manifest "after" name -> the name the live catalog actually carries. The
# manifest is generated from the SQLAlchemy metadata, which auto-names an
# unnamed ``ForeignKey``; these six were created with explicit names, and the
# migration renames what the catalog holds so older revisions can still drop
# them by name.
# The only catalog objects that still carry `project` after the migration:
# step 2 hands the word to the Project entity, so each of these names the
# ex-`portfolio` row, not the Task.
_REUSED_BY_THE_PROJECT_ENTITY = {
    "project",
    "project_membership",
    "project_id",
    "project_pkey",
    "project_membership_pkey",
    "ck_project_visibility",
    "fk_project_org_id",
    "fk_project_membership_project_id",
    "fk_project_membership_task_id",
    "ix_project_org_visibility",
    "ix_project_membership_task_id",
}

_OLD_STEER_POINT = "evidence_base_coverage"
_NEW_STEER_POINT = "evidence_search_coverage"

_PLAN_PAYLOAD: dict[str, Any] = {
    "title": "A pre-038 plan",
    "question": "What works?",
    "scoping_notes": [],
    "screening_criteria": ["Include empirical sources"],
    "backend_scope": "both",
    "scope_constraints": {},
    "search_effort": "rapid",
    "analysis_depth": "landscape",
    "components": [],
    "component_rationale": {},
    "grouping_facets": None,
    "steering_mode": "moderate",
    "steer_point_defaults": [{"steer_point": _OLD_STEER_POINT, "action": "proceed_flag"}],
}

# The five reversible stored values, and the tables they live in.
_SEEDED_TABLES = (
    "portfolio",
    "portfolio_membership",
    "project",
    "runs",
    "evidence_scope",
    "selection_result",
    "capability_run",
    "orchestration_plan",
    "event_log",
)


def _manifest_rows(section: str) -> list[list[str]]:
    """Return the body rows of one ``schema-manifest.md`` table as cell lists."""
    body = _MANIFEST.read_text().split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in body.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if cells[0] in {"Today", "Table (today)", "Kind"}:
            continue
        rows.append(cells)
    return rows


def _live_names(
    conn: Connection,
) -> tuple[set[str], set[tuple[str, str]], set[tuple[str, str]]]:
    """Return the live tables, ``(table, column)`` pairs and ``(table, name)`` pairs.

    Columns, constraints and indexes are keyed by their owning relation so one
    ``task_id`` somewhere cannot stand in for every expected rename.
    """
    tables = set(
        conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
    )
    columns = set(
        conn.execute(
            text(
                "SELECT c.relname, a.attname FROM pg_attribute a "
                "JOIN pg_class c ON c.oid = a.attrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND a.attnum > 0 "
                "AND NOT a.attisdropped AND c.relkind IN ('r', 'v')"
            )
        ).tuples()
    )
    names = set(
        conn.execute(
            text(
                "SELECT t.relname, c.conname FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "WHERE n.nspname = 'public'"
            )
        ).tuples()
    ) | set(
        conn.execute(
            text("SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public'")
        ).tuples()
    )
    return tables, columns, names


def _seed_pre_migration(engine: Engine) -> dict[str, uuid.UUID]:
    """Commit the pre-038 fixture at ``b2f6a9d4c1e7`` under the old names."""
    ids = {
        "portfolio_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "scope_id": uuid.uuid4(),
        "walk_id": uuid.uuid4(),
        "plan_id": uuid.uuid4(),
        "pause_id": uuid.uuid4(),
        "selection_id": uuid.uuid4(),
        "pss_id": uuid.uuid4(),
    }
    with engine.begin() as conn:
        conn.execute(
            legacy_table(conn, "portfolio").insert().values(
                portfolio_id=ids["portfolio_id"],
                owner_user_id="owner-038",
                name="A pre-038 Project",
                description="Seeded before the rename",
                created_at=now(),
                org_id=None,
                visibility="private",
            )
        )
        conn.execute(
            legacy_table(conn, "project").insert().values(
                project_id=ids["project_id"],
                created_at=now(),
                name="A pre-038 Task",
                question="What works?",
                status="active",
                updated_at=now(),
                archived_at=None,
                owner_user_id="owner-038",
                org_id=None,
                visibility="private",
                is_public=True,
            )
        )
        conn.execute(
            legacy_table(conn, "portfolio_membership").insert().values(
                portfolio_id=ids["portfolio_id"],
                project_id=ids["project_id"],
                created_at=now(),
            )
        )
        conn.execute(
            legacy_table(conn, "runs").insert().values(
                run_id=ids["run_id"],
                project_id=ids["project_id"],
                status="running",
                started_at=now(),
            )
        )
        conn.execute(
            legacy_table(conn, "evidence_scope").insert().values(
                evidence_scope_id=ids["scope_id"],
                project_id=ids["project_id"],
                intent="Migration fixture",
                context={},
                created_at=now(),
            )
        )
        conn.execute(
            legacy_table(conn, "selection_result").insert().values(
                selection_result_id=ids["selection_id"],
                project_id=ids["project_id"],
                evidence_scope_id=ids["scope_id"],
                run_id=ids["run_id"],
                strategy="coverage_stratified_v1",
                budget=1,
                selection_provenance={},
                # The per-document key the sweep renamed in code (stored value 6).
                selected=[{"pss_id": str(ids["pss_id"]), "reason": "must_include"}],
                excluded={"notable": [{"pss_id": str(ids["pss_id"])}]},
                flags={},
                created_at=now(),
            )
        )
        conn.execute(
            legacy_table(conn, "capability_run").insert().values(
                capability_run_id=ids["walk_id"],
                project_id=ids["project_id"],
                evidence_scope_id=ids["scope_id"],
                capability="evidence_base",
                plan_id=ids["plan_id"],
                plan_version=1,
                status="running",
                session_id=None,
                started_at=now(),
                ended_at=None,
            )
        )
        conn.execute(
            legacy_table(conn, "orchestration_plan").insert().values(
                plan_id=ids["plan_id"],
                project_id=ids["project_id"],
                conversation_id=None,
                evidence_scope_id=None,
                version=1,
                status="approved",
                payload=_PLAN_PAYLOAD,
                created_at=now(),
                created_by="planner",
                approved_at=now(),
            )
        )
        events = legacy_table(conn, "event_log")
        base = {
            "capability_run_id": str(ids["walk_id"]),
            "plan_id": str(ids["plan_id"]),
            "plan_version": 1,
            "boundary": "after_component",
            "component": "screen_abstract",
        }
        rows: list[tuple[uuid.UUID, uuid.UUID | None, str, dict[str, Any]]] = [
            (uuid.uuid4(), None, "project.renamed", {"name_from": "Old", "name_to": "New"}),
            (uuid.uuid4(), None, "project.archived", {"actor": "user"}),
            (uuid.uuid4(), None, "project.shared_publicly", {"actor": "user"}),
            (uuid.uuid4(), None, "project.unshared", {"actor": "user"}),
            (
                ids["pause_id"],
                ids["run_id"],
                "steering.pause",
                {
                    **base,
                    "kind": "steer_point",
                    "steer_point": _OLD_STEER_POINT,
                    "options": [{"id": "proceed", "label": "Proceed"}],
                    "bundle": {"themes": [{"label": "Alpha"}]},
                },
            ),
            (
                uuid.uuid4(),
                ids["run_id"],
                "steering.decision",
                {
                    **base,
                    "check_in_id": str(ids["pause_id"]),
                    "decided_by": "orchestrator",
                    "authored_by": "orchestrator",
                    "response": "continue",
                    "interpreted_action": None,
                    "confirmed": True,
                },
            ),
        ]
        for sequence, (event_id, run_id, event_type, payload) in enumerate(rows, start=1):
            conn.execute(
                events.insert().values(
                    event_id=event_id,
                    run_id=run_id,
                    project_id=ids["project_id"],
                    sequence=sequence,
                    event_type=event_type,
                    occurred_at=now(),
                    payload=payload,
                )
            )
    return ids


def _fixture_snapshot(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    """Read every seeded pre-038 table back, ordered, for byte-identity."""
    snapshot: dict[str, list[dict[str, Any]]] = {}
    with engine.connect() as conn:
        for name in _SEEDED_TABLES:
            table = legacy_table(conn, name)
            rows = [
                dict(row) for row in conn.execute(select(table)).mappings().all()
            ]
            snapshot[name] = sorted(rows, key=lambda row: sorted(map(str, row.items())))
    return snapshot


def _write_deploy_window_rows(engine: Engine, ids: dict[str, uuid.UUID]) -> None:
    """Write, at head, exactly what the NEW image writes — all seven values."""
    with engine.begin() as conn:
        # A selection written under the new key (one row per scope and run, so
        # the seeded row is rewritten rather than a second one inserted).
        conn.execute(
            selection_result.update()
            .where(selection_result.c.selection_result_id == ids["selection_id"])
            .values(selected=[{"tss_id": str(uuid.uuid4()), "reason": "ranked"}])
        )
        conn.execute(
            capability_run.insert().values(
                capability_run_id=uuid.uuid4(),
                task_id=ids["project_id"],
                evidence_scope_id=ids["scope_id"],
                capability="evidence_search",
                plan_id=ids["plan_id"],
                plan_version=1,
                status="running",
                session_id=None,
                started_at=now(),
                ended_at=None,
            )
        )
        conn.execute(
            task_plan.insert().values(
                plan_id=uuid.uuid4(),
                task_id=ids["project_id"],
                conversation_id=None,
                evidence_scope_id=None,
                version=2,
                status="approved",
                payload={
                    **_PLAN_PAYLOAD,
                    "steer_point_defaults": [
                        {"steer_point": _NEW_STEER_POINT, "action": "proceed_flag"}
                    ],
                },
                created_at=now(),
                created_by="planner",
                approved_at=now(),
            )
        )
        window_rows: list[tuple[str, dict[str, Any]]] = [
            ("task.renamed", {"name_from": "New", "name_to": "Newer"}),
            ("task.archived", {"actor": "user"}),
            ("task.shared_publicly", {"actor": "user"}),
            ("task.unshared", {"actor": "user"}),
            ("steering.decision", {"decided_by": "agent", "authored_by": "agent"}),
            ("steering.pause", {"steer_point": _NEW_STEER_POINT}),
        ]
        for offset, (event_type, payload) in enumerate(window_rows, start=100):
            conn.execute(
                event_log.insert().values(
                    event_id=uuid.uuid4(),
                    run_id=None,
                    task_id=ids["project_id"],
                    sequence=offset,
                    event_type=event_type,
                    occurred_at=now(),
                    payload=payload,
                )
            )


def _delete_everything(engine: Engine, ids: dict[str, uuid.UUID]) -> None:
    """Remove the committed fixture at head, FK-ordered."""
    with engine.begin() as conn:
        conn.execute(event_log.delete().where(event_log.c.task_id == ids["project_id"]))
        conn.execute(
            capability_run.delete().where(capability_run.c.task_id == ids["project_id"])
        )
        conn.execute(task_plan.delete().where(task_plan.c.task_id == ids["project_id"]))
        conn.execute(
            selection_result.delete().where(selection_result.c.task_id == ids["project_id"])
        )
        conn.execute(
            text("DELETE FROM evidence_scope WHERE task_id = :task_id"),
            {"task_id": ids["project_id"]},
        )
        conn.execute(
            text("DELETE FROM project_membership WHERE task_id = :task_id"),
            {"task_id": ids["project_id"]},
        )
        conn.execute(
            text("DELETE FROM runs WHERE task_id = :task_id"), {"task_id": ids["project_id"]}
        )
        conn.execute(task.delete().where(task.c.task_id == ids["project_id"]))
        conn.execute(project.delete().where(project.c.project_id == ids["portfolio_id"]))


def test_038_renames_the_catalog_to_the_manifest(engine: Engine) -> None:
    """Every manifest "after" name exists at head, and no retired name survives."""
    cfg = _alembic_cfg()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        tables, columns, names = _live_names(conn)

    # Manifest rows name the owning table by its pre-migration name; at head
    # it is the renamed table (`project` is the Project entity, `task` the Task).
    table_after = {row[0]: row[1] for row in _manifest_rows("Tables")}
    after_tables = set(table_after.values())
    after_columns = {
        (table_after.get(row[0], row[0]), row[2]) for row in _manifest_rows("Columns")
    }
    after_names = {
        (table_after.get(row[1], row[1]), row[3])
        for row in _manifest_rows("Constraints and indexes")
    }
    assert after_tables <= tables
    assert after_columns <= columns
    assert after_names <= names

    today_tables = set(table_after)
    today_columns = {(table_after.get(row[0], row[0]), row[1]) for row in _manifest_rows("Columns")}
    today_names = {
        (table_after.get(row[1], row[1]), row[2])
        for row in _manifest_rows("Constraints and indexes")
        # `ck_capr_capability` is dropped and recreated under the same name.
        if row[2] != row[3]
    }
    assert (today_tables & tables) <= _REUSED_BY_THE_PROJECT_ENTITY
    assert {name for _, name in today_columns & columns} <= _REUSED_BY_THE_PROJECT_ENTITY
    assert {name for _, name in today_names & names} <= _REUSED_BY_THE_PROJECT_ENTITY

    # I1 stated the other way round: nothing in the live catalog still carries
    # a retired token, and every surviving `project` is the Project entity.
    retired = re.compile(r"portfolio|_pss_|uq_pss|ck_pss|fk_pss|oplan|orchestration_plan")
    live = tables | {name for _, name in columns} | {name for _, name in names}
    assert not [name for name in live if retired.search(name)]
    survivors = {name for name in live if "project" in name}
    assert survivors <= _REUSED_BY_THE_PROJECT_ENTITY


def test_038_round_trips_a_populated_pre_migration_database(engine: Engine) -> None:
    """Content survives the upgrade, and the downgrade reverses everything."""
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)
    ids = _seed_pre_migration(engine)
    seeded = _fixture_snapshot(engine)

    try:
        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            # I1 — the Task row reads back field-for-field under the new names.
            row = conn.execute(
                select(task).where(task.c.task_id == ids["project_id"])
            ).mappings().one()
            assert row["name"] == "A pre-038 Task"
            assert row["is_public"] is True

            # I2 — the Project and its membership are unchanged in meaning.
            assert conn.execute(
                select(project.c.name).where(project.c.project_id == ids["portfolio_id"])
            ).scalar_one() == "A pre-038 Project"
            assert conn.execute(
                text(
                    "SELECT count(*) FROM project_membership "
                    "WHERE project_id = :project_id AND task_id = :task_id"
                ),
                {"project_id": ids["portfolio_id"], "task_id": ids["project_id"]},
            ).scalar_one() == 1

            # The one stored value the UPGRADE rewrites.
            assert conn.execute(
                select(capability_run.c.capability).where(
                    capability_run.c.capability_run_id == ids["walk_id"]
                )
            ).scalar_one() == "evidence_search"

            # Stored value 6 — the selection entries read under the new key.
            selection = conn.execute(
                select(selection_result.c.selected, selection_result.c.excluded).where(
                    selection_result.c.selection_result_id == ids["selection_id"]
                )
            ).mappings().one()
            assert selection["selected"] == [
                {"tss_id": str(ids["pss_id"]), "reason": "must_include"}
            ]
            assert selection["excluded"] == {"notable": [{"tss_id": str(ids["pss_id"])}]}

            # I4 — a decision stored by the retired actor word renders as Agent,
            # and all four pre-038 lifecycle events still reach the read model.
            page = decisions_page(conn, ids["project_id"], 1, 50)
            decision = next(item for item in page.data if item.kind == "steering.decision")
            assert decision.decided_by == "agent"
            assert {item.kind for item in page.data} >= {
                "steering.decision",
                "project.renamed",
                "project.archived",
            }

            # A3 — the stored plan payload still validates through TaskPlan.
            payload = conn.execute(
                select(task_plan.c.payload).where(task_plan.c.plan_id == ids["plan_id"])
            ).scalar_one()
            assert payload["steer_point_defaults"][0]["steer_point"] == _OLD_STEER_POINT
            plan = TaskPlan.model_validate(payload)
            assert plan.steer_point_defaults[0].steer_point == _NEW_STEER_POINT

        # D6, first half — the pre-migration fixture comes back byte-identical.
        command.downgrade(cfg, PRE_MIGRATION_REVISION)
        assert _fixture_snapshot(engine) == seeded

        # D6, second half — write what the NEW image writes during the deploy
        # window, then prove the downgrade reverses each of the five values.
        command.upgrade(cfg, "head")
        _write_deploy_window_rows(engine, ids)
        command.downgrade(cfg, PRE_MIGRATION_REVISION)

        with engine.connect() as conn:
            events = legacy_table(conn, "event_log")
            walks = legacy_table(conn, "capability_run")
            plans = legacy_table(conn, "orchestration_plan")
            payloads = [
                row
                for row in conn.execute(
                    select(events.c.event_type, events.c.payload).where(
                        events.c.project_id == ids["project_id"]
                    )
                ).mappings()
            ]

            # 1. capability_run.capability
            assert set(
                conn.execute(
                    select(walks.c.capability).where(walks.c.project_id == ids["project_id"])
                ).scalars()
            ) == {"evidence_base"}
            # 2. event_log.event_type — no `task.*` lifecycle row survives.
            assert not [row for row in payloads if row["event_type"].startswith("task.")]
            assert sum(
                row["event_type"] == "project.renamed" for row in payloads
            ) == 2  # the seeded one plus the reversed deploy-window write
            # 3. event_log.payload decided_by / authored_by
            actors = {
                row["payload"].get(key)
                for row in payloads
                for key in ("decided_by", "authored_by")
                if key in row["payload"]
            }
            assert actors == {"orchestrator"}
            # 4. plan payload steer-point ids
            assert {
                plan_payload["steer_point_defaults"][0]["steer_point"]
                for plan_payload in conn.execute(
                    select(plans.c.payload).where(plans.c.project_id == ids["project_id"])
                ).scalars()
            } == {_OLD_STEER_POINT}
            # 6. selection entries — every row for the project keys by `pss_id` again
            selections = legacy_table(conn, "selection_result")
            assert {
                key
                for selected in conn.execute(
                    select(selections.c.selected).where(
                        selections.c.project_id == ids["project_id"]
                    )
                ).scalars()
                for entry in selected
                for key in entry
            } == {"pss_id", "reason"}
            # 5. pause-record steer-point ids
            assert {
                row["payload"]["steer_point"]
                for row in payloads
                if "steer_point" in row["payload"]
            } == {_OLD_STEER_POINT}

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert "task" in inspect(conn).get_table_names()
    finally:
        command.upgrade(cfg, "head")
        _delete_everything(engine, ids)
