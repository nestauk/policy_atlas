"""Schema validation — tables, columns, constraints."""

import ast
import os
import re
import uuid
from pathlib import Path
from typing import get_args

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    EFFECT_BASES,
    EVIDENCE_TYPES,
    METHODOLOGICAL_STRUCTURAL,
    annotation,
    artefact,
    block,
    conversation,
    event_log,
    project,
    project_source_snapshot,
    runs,
    source_screening_result,
    source_snapshot,
    source_tag,
)
from policy_atlas.core.schema import (
    chunk as chunk_table,
)
from policy_atlas.core.schema import (
    citation as citation_table,
)
from policy_atlas.core.tags import insert_source_tags
from policy_atlas.evidence_base.extract import iof_prompt
from policy_atlas.evidence_base.extract.iof_records import EffectBasis
from tests.helpers import now, seed_project_and_run, seed_scope, seed_source


def test_all_fourteen_tables_exist(conn: Connection) -> None:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    expected = {
        "project", "artefact", "block", "addressable_unit", "annotation", "runs", "event_log",
        "source_snapshot", "project_source_snapshot", "chunk", "citation",
        "evidence_scope", "source_screening_result", "source_classification_result",
    }
    assert expected <= tables


def test_event_log_unique_project_sequence(conn: Connection) -> None:
    pid = uuid.uuid4()
    rid = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=pid, created_at=now(), name="Test project", status="active", updated_at=now()
        )
    )
    conn.execute(runs.insert().values(
        run_id=rid, project_id=pid, status="running", started_at=now()
    ))

    conn.execute(event_log.insert().values(
        event_id=uuid.uuid4(), run_id=rid, project_id=pid,
        sequence=1, event_type="run.started", occurred_at=now(), payload={},
    ))
    with pytest.raises(Exception, match="uq_event_log_project_sequence"):
        conn.execute(event_log.insert().values(
            event_id=uuid.uuid4(), run_id=rid, project_id=pid,
            sequence=1, event_type="duplicate", occurred_at=now(), payload={},
        ))


def test_addressable_unit_unique_block_unit_constraint_exists(conn: Connection) -> None:
    """uq_addressable_unit_block_unit backs the annotation composite FK — verify it's present.

    (block_id, unit_id) can't be violated independently of the PK since unit_id is already
    the PK; the constraint's purpose is to enable the annotation composite FK reference.)
    """
    inspector = inspect(conn)
    unique_names = {
        uc["name"] for uc in inspector.get_unique_constraints("addressable_unit")
    }
    assert "uq_addressable_unit_block_unit" in unique_names


def test_block_version_defaults_to_one(conn: Connection) -> None:
    """block.version has a DB server_default of 1 — an insert omitting it still gets 1."""
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    bid = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=pid, created_at=now(), name="Test project", status="active", updated_at=now()
        )
    )
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    conn.execute(block.insert().values(
        block_id=bid, artefact_id=aid, content="c", content_hash="h", created_at=now(),
    ))  # version intentionally omitted
    version = conn.execute(select(block.c.version).where(block.c.block_id == bid)).scalar_one()
    assert version == 1


def test_annotation_composite_fk_rejects_mismatch(conn: Connection) -> None:
    """annotation(block_id, unit_id) must match an existing addressable_unit row."""
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    bid = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=pid, created_at=now(), name="Test project", status="active", updated_at=now()
        )
    )
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    conn.execute(block.insert().values(
        block_id=bid, artefact_id=aid, version=1,
        content="c", content_hash="h", created_at=now(),
    ))
    # unit_id that does NOT exist in addressable_unit
    phantom_unit_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        conn.execute(annotation.insert().values(
            annotation_id=uuid.uuid4(),
            block_id=bid,
            unit_id=phantom_unit_id,
            annotation_type="citation",
            payload={"quote": "q", "verification_result": "pass"},
            created_at=now(),
        ))


def _seed_snapshot(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Return (source_snapshot_id, chunk_id) for a single-chunk snapshot."""
    sid = uuid.uuid4()
    cid = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=sid,
        content_hash="h",
        text_basis="full_text",
        source_locator="test.pdf",
        metadata={},
        created_at=now(),
    ))
    conn.execute(chunk_table.insert().values(
        chunk_id=cid,
        source_snapshot_id=sid,
        sequence=1,
        content="test content",
        content_hash="ch",
        locator={"sequence": 1},
        segmentation_policy="manual_v1",
        created_at=now(),
    ))
    return sid, cid


def test_citation_chunk_fk_fails_with_phantom_chunk_id(conn: Connection) -> None:
    """citation.chunk_id must reference an existing chunk row."""
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    bid = uuid.uuid4()
    uid = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=pid, created_at=now(), name="Test project", status="active", updated_at=now()
        )
    )
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    conn.execute(block.insert().values(
        block_id=bid, artefact_id=aid, version=1,
        content="c", content_hash="h", created_at=now(),
    ))
    from policy_atlas.core.schema import addressable_unit
    conn.execute(addressable_unit.insert().values(
        unit_id=uid, block_id=bid, unit_type="text_span",
        locator={"start": 0, "end": 1}, content="c", created_at=now(),
    ))
    ann_id = uuid.uuid4()
    conn.execute(annotation.insert().values(
        annotation_id=ann_id, block_id=bid, unit_id=uid,
        annotation_type="citation",
        payload={"quote": "q", "verification_result": "pass"},
        created_at=now(),
    ))
    with pytest.raises(IntegrityError):
        conn.execute(citation_table.insert().values(
            citation_id=uuid.uuid4(),
            annotation_id=ann_id,
            chunk_id=uuid.uuid4(),   # phantom — does not exist
            quote="q",
            verification_result="pass",
            created_at=now(),
        ))


def test_chunk_unique_snapshot_sequence_constraint(conn: Connection) -> None:
    """(source_snapshot_id, sequence) must be unique within a snapshot."""
    sid, _ = _seed_snapshot(conn)
    with pytest.raises(Exception, match="uq_chunk_snapshot_sequence"):
        conn.execute(chunk_table.insert().values(
            chunk_id=uuid.uuid4(),
            source_snapshot_id=sid,
            sequence=1,              # duplicate sequence for same snapshot
            content="other",
            content_hash="other_h",
            locator={"sequence": 1},
            segmentation_policy="manual_v1",
            created_at=now(),
        ))


def test_project_source_snapshot_unique_constraint(conn: Connection) -> None:
    """(project_id, source_snapshot_id) must be unique in project_source_snapshot."""
    pid = uuid.uuid4()
    sid, _ = _seed_snapshot(conn)
    conn.execute(
        project.insert().values(
            project_id=pid, created_at=now(), name="Test project", status="active", updated_at=now()
        )
    )
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=uuid.uuid4(), project_id=pid, source_snapshot_id=sid,
        origin="uploaded", run_id=None, ingested_at=now(),
    ))
    with pytest.raises(Exception, match="uq_project_source_snapshot"):
        conn.execute(project_source_snapshot.insert().values(
            project_source_snapshot_id=uuid.uuid4(), project_id=pid, source_snapshot_id=sid,
            origin="uploaded", run_id=None, ingested_at=now(),
        ))


def test_migration_roundtrip_portfolio_layer(engine: Engine) -> None:
    """``b3c7d914e0a2`` (the portfolio layer) downgrades and upgrades cleanly.

    Targets the revision by id rather than ``-1`` so the assertions cannot
    silently start exercising a different migration when the next one lands.
    Runs on its own connection for the same reason as the round-trip below, and
    leaves the database back at head.
    """
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    command.downgrade(cfg, "d8e4a1c7f2b9")
    with engine.connect() as down_conn:
        inspector = inspect(down_conn)
        assert "portfolio" not in inspector.get_table_names()
        assert "portfolio_id" not in {c["name"] for c in inspector.get_columns("project")}

    command.upgrade(cfg, "head")
    with engine.connect() as up_conn:
        inspector = inspect(up_conn)
        assert "portfolio" in inspector.get_table_names()
        assert "portfolio_membership" in inspector.get_table_names()
        # `org_id` and `visibility` join the set because this upgrades to *head*,
        # which now includes 033's tenancy migrations as well as the membership
        # layer — the equality is kept (it is what catches an unintended column)
        # and the two columns 033 adds to `portfolio` are named explicitly.
        assert {c["name"] for c in inspector.get_columns("portfolio")} == {
            "portfolio_id",
            "owner_user_id",
            "name",
            "description",
            "created_at",
            "org_id",
            "visibility",
        }
        assert {c["name"] for c in inspector.get_columns("portfolio_membership")} == {
            "portfolio_id",
            "project_id",
            "created_at",
        }
        assert "portfolio_id" not in {c["name"] for c in inspector.get_columns("project")}


def _seed_pre_033_project_and_conversation(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    owner_user_id: str | None,
    created_by: str | None = None,
) -> None:
    """Commit one project and one chat conversation on it.

    Committed rather than held in a transaction because alembic runs the
    migration on a connection of its own and cannot see an uncommitted row.
    ``created_by`` is omitted entirely when None so the same helper seeds at the
    pre-033 revision, where the column does not exist.
    """
    values: dict[str, object] = {
        "id": conversation_id,
        "project_id": project_id,
        "kind": "chat",
        "title": "Chat",
        "entry_artefact_id": None,
        "status": "active",
        "created_at": now(),
        "closed_at": None,
        "archived_at": None,
    }
    if created_by is not None:
        values["created_by"] = created_by
    with engine.begin() as seed_conn:
        seed_conn.execute(project.insert().values(
            project_id=project_id,
            created_at=now(),
            name="Tenancy migration fixture",
            status="active",
            updated_at=now(),
            owner_user_id=owner_user_id,
        ))
        seed_conn.execute(conversation.insert().values(**values))


def _delete_seeded_rows(engine: Engine, *project_ids: uuid.UUID) -> None:
    """Remove committed fixture rows — these tests write outside ``conn``."""
    with engine.begin() as cleanup_conn:
        cleanup_conn.execute(
            conversation.delete().where(conversation.c.project_id.in_(project_ids))
        )
        cleanup_conn.execute(project.delete().where(project.c.project_id.in_(project_ids)))


def test_migration_roundtrip_organisation_tenancy(engine: Engine) -> None:
    """``a4f1c8e3b6d2`` (organisation tenancy) round-trips, and ``created_by`` backfills.

    Down to ``b3c7d914e0a2`` and back by revision id rather than ``-1``, so the
    assertions cannot silently start exercising a later migration. Seeds two
    projects at the pre-033 revision — one owned, one not — because the backfill
    must attribute the first conversation and leave the second's author unknown.
    Always leaves the database at head with the fixture rows removed.
    """
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    owner = f"sub-owner-{uuid.uuid4()}"
    owned_project_id = uuid.uuid4()
    owned_conversation_id = uuid.uuid4()
    unowned_project_id = uuid.uuid4()
    unowned_conversation_id = uuid.uuid4()

    command.downgrade(cfg, "b3c7d914e0a2")
    try:
        with engine.connect() as down_conn:
            inspector = inspect(down_conn)
            assert "organisation" not in inspector.get_table_names()
            assert "app_user" not in inspector.get_table_names()
            for table in ("project", "portfolio"):
                columns = {c["name"] for c in inspector.get_columns(table)}
                assert "org_id" not in columns
                assert "visibility" not in columns
            assert "created_by" not in {
                c["name"] for c in inspector.get_columns("conversation")
            }

        _seed_pre_033_project_and_conversation(
            engine,
            project_id=owned_project_id,
            conversation_id=owned_conversation_id,
            owner_user_id=owner,
        )
        # A `runtime/orchestrate.py` CLI row: no owner, so no author to infer.
        _seed_pre_033_project_and_conversation(
            engine,
            project_id=unowned_project_id,
            conversation_id=unowned_conversation_id,
            owner_user_id=None,
        )
    finally:
        command.upgrade(cfg, "head")

    try:
        with engine.connect() as up_conn:
            inspector = inspect(up_conn)
            assert {"organisation", "app_user"} <= set(inspector.get_table_names())
            for table in ("project", "portfolio"):
                columns = {c["name"] for c in inspector.get_columns(table)}
                assert {"org_id", "visibility"} <= columns
            assert "created_by" in {
                c["name"] for c in inspector.get_columns("conversation")
            }
            assert "ix_project_org_visibility_status" in {
                ix["name"] for ix in inspector.get_indexes("project")
            }
            assert "ix_portfolio_org_visibility" in {
                ix["name"] for ix in inspector.get_indexes("portfolio")
            }

            # Existing rows arrive with no organisation. `org_id IS NULL` matches
            # no org leg, so 'org' on them is an inert default — the dark launch.
            existing = up_conn.execute(
                select(project.c.org_id, project.c.visibility).where(
                    project.c.project_id == owned_project_id
                )
            ).one()
            assert existing.org_id is None
            assert existing.visibility == "org"

            authors: dict[uuid.UUID, str | None] = {
                row.id: row.created_by
                for row in up_conn.execute(
                    select(conversation.c.id, conversation.c.created_by).where(
                        conversation.c.id.in_(
                            [owned_conversation_id, unowned_conversation_id]
                        )
                    )
                ).all()
            }
            assert authors[owned_conversation_id] == owner
            assert authors[unowned_conversation_id] is None
    finally:
        _delete_seeded_rows(engine, owned_project_id, unowned_project_id)


def test_the_tenancy_migrations_lock_timeout_cannot_outlive_the_migration() -> None:
    """``SET LOCAL``, both directions — a session GUC leaks into later revisions.

    The 5s ceiling exists because ``ALTER TABLE`` takes ACCESS EXCLUSIVE and a
    stray jumpbox session holding a conflicting lock would queue the deploy and
    every reader behind it. That is a statement about *this* revision, and a
    plain ``SET`` is session-scoped: on the connection that runs ``alembic
    upgrade head`` over a fresh database it silently imposed the same ceiling on
    every revision applied afterwards, which may legitimately want to wait
    longer. ``alembic/env.py`` runs migrations inside
    ``context.begin_transaction()``, so ``SET LOCAL`` has a transaction to be
    scoped to and reverts when it commits.

    Asserted against the source text because the leak is invisible in
    behaviour: a run that never contends for a lock passes either way, and the
    one that does contend is a production deploy.
    """
    script = ScriptDirectory.from_config(AlembicConfig("alembic.ini"))
    # Every tenancy-family migration whose ALTERs take ACCESS EXCLUSIVE.
    for revision_id in ("a4f1c8e3b6d2", "d8e2a6c4f7b1"):
        source = Path(script.get_revision(revision_id).path).read_text()
        statements = re.findall(r'op\.execute\("(SET[^"]*lock_timeout[^"]*)"\)', source)

        assert statements == ["SET LOCAL lock_timeout = '5s'"] * 2, (revision_id, statements)
        # One per direction, not two in `upgrade` and none in `downgrade`.
        module = ast.parse(source)
        for name in ("upgrade", "downgrade"):
            function = next(
                node
                for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            found = [
                node.value
                for node in ast.walk(function)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "lock_timeout" in node.value
            ]
            assert found == ["SET LOCAL lock_timeout = '5s'"], (revision_id, name, found)


def test_downgrade_erases_chat_authorship_exposing_colleague_chats(engine: Engine) -> None:
    """Evidence for the documented rollback exposure (contract § Rollback posture).

    A colleague's chat on someone else's project survives the 033 downgrade, but
    the schema stops recording who wrote it — and pre-033 code lists *every*
    conversation on a project to that project's owner. So a rollback after
    adoption hands the owner a colleague's private chat. Re-upgrading does not
    undo it either: the backfill can only attribute the row to the project owner,
    which is the wrong person. This is why the posture is roll forward, not back;
    rubric 32 requires the exposure proved rather than asserted.
    """
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    owner = f"sub-owner-{uuid.uuid4()}"
    colleague = f"sub-colleague-{uuid.uuid4()}"
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    _seed_pre_033_project_and_conversation(
        engine,
        project_id=project_id,
        conversation_id=conversation_id,
        owner_user_id=owner,
        created_by=colleague,
    )
    try:
        command.downgrade(cfg, "b3c7d914e0a2")
        try:
            with engine.connect() as down_conn:
                inspector = inspect(down_conn)
                assert "created_by" not in {
                    c["name"] for c in inspector.get_columns("conversation")
                }
                # The pre-033 per-project listing predicate, verbatim: ownership of
                # the project is the only filter, so the colleague's chat is in it.
                visible_to_owner = down_conn.execute(
                    text(
                        "SELECT c.id FROM conversation c "
                        "JOIN project p ON p.project_id = c.project_id "
                        "WHERE p.owner_user_id = :owner"
                    ),
                    {"owner": owner},
                ).scalars().all()
                assert conversation_id in visible_to_owner
        finally:
            command.upgrade(cfg, "head")

        with engine.connect() as up_conn:
            restored = up_conn.execute(
                select(conversation.c.created_by).where(
                    conversation.c.id == conversation_id
                )
            ).scalar_one()
            assert restored == owner
            assert restored != colleague
    finally:
        _delete_seeded_rows(engine, project_id)


def test_migration_roundtrip_screen_stage_and_classify_tags(engine: Engine) -> None:
    """Downgrading past e5c2a7f4b9d1 then ``upgrade head`` restores all four changes.

    Targets ``c9e4b7f2d1a8`` — e5c2a7f4b9d1's parent — by id. It previously said
    ``downgrade -1``, which reverts whatever the *newest* migration happens to be:
    fifteen revisions have landed above e5c2a7f4b9d1 since, so the test had long
    stopped exercising the migration its assertions are about while staying green.
    Naming the revision is the repair; nothing about the assertions changed.

    Runs on its own connection outside the rolled-back ``conn`` fixture transaction
    (the migration itself needs a connection it fully controls) and always leaves
    the session-scoped engine's database back at head — ``downgrade``/``upgrade``
    run back-to-back with no test logic in between, and each migration step is
    itself one transaction, so a failure there leaves the DB at its prior revision
    rather than stuck mid-migration.
    """
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    command.downgrade(cfg, "c9e4b7f2d1a8")
    command.upgrade(cfg, "head")

    with engine.connect() as verify_conn:
        trans = verify_conn.begin()
        try:
            inspector = inspect(verify_conn)
            cols = {c["name"] for c in inspector.get_columns("source_screening_result")}
            assert "screen_stage" in cols

            pid, rid = seed_project_and_run(verify_conn)
            scope_id = seed_scope(verify_conn, pid)
            _, pss_id = seed_source(verify_conn, pid)

            # ck_ssr_basis admits 'full_text' (a stage-2 row).
            verify_conn.execute(source_screening_result.insert().values(
                source_screening_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_source_snapshot_id=pss_id,
                project_id=pid,
                screened_by_run_id=rid,
                status="relevant",
                screen_basis="full_text",
                screen_decision_confidence=0.9,
                screen_stage=2,
                screened_at=now(),
            ))

            # uq_ssr_scope_source_stage: a second non-failed stage-2 row for the
            # same (scope, source) conflicts with the one above.
            with pytest.raises(IntegrityError), verify_conn.begin_nested():
                verify_conn.execute(source_screening_result.insert().values(
                    source_screening_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=pss_id,
                    project_id=pid,
                    screened_by_run_id=rid,
                    status="not_relevant",
                    screen_basis="full_text",
                    screen_decision_confidence=0.8,
                    screen_stage=2,
                    screened_at=now(),
                ))

            # ... but a failed row at the same stage never conflicts with it.
            verify_conn.execute(source_screening_result.insert().values(
                source_screening_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_source_snapshot_id=pss_id,
                project_id=pid,
                screened_by_run_id=rid,
                status="failed",
                screen_basis=None,
                screen_decision_confidence=None,
                screen_stage=2,
                screened_at=now(),
            ))

            # ck_stag_tag_type admits 'methodological_structural'.
            insert_source_tags(
                verify_conn,
                project_id=pid,
                run_id=rid,
                now=now(),
                assertions=[(pss_id, "rct", "test")],
                tag_type=METHODOLOGICAL_STRUCTURAL,
            )
            tag_row = verify_conn.execute(
                select(source_tag.c.tag_type).where(
                    source_tag.c.project_source_snapshot_id == pss_id
                )
            ).one()
            assert tag_row.tag_type == METHODOLOGICAL_STRUCTURAL
        finally:
            trans.rollback()


# --- CHECK-vocabulary agreement (task 020) ---------------------------------


def _check_constraint_allowed_values(conn: Connection, constraint_name: str) -> set[str]:
    """Read a live CHECK's ``= ANY (ARRAY[...])`` string vocabulary from Postgres.

    Args:
        conn: Open database connection.
        constraint_name: The CHECK constraint's name.

    Returns:
        The set of string literals the constraint's ``ARRAY[...]`` admits.
    """
    definition = conn.execute(
        text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
        {"name": constraint_name},
    ).scalar_one()
    return set(re.findall(r"'([^']*)'::text", definition))


def test_ck_ser_evidence_type_matches_schema_and_prompt_vocabulary(conn: Connection) -> None:
    """ck_ser_evidence_type's live allowed set is exactly EVIDENCE_TYPES plus the
    prompt's UNCLASSIFIED_EVIDENCE_TYPE sentinel — the two modules deliberately
    never import each other (schema.py keeps the literal in sync by comment),
    so this test is the drift guard."""
    allowed = _check_constraint_allowed_values(conn, "ck_ser_evidence_type")
    assert allowed == {*EVIDENCE_TYPES, iof_prompt.UNCLASSIFIED_EVIDENCE_TYPE}


def test_ck_iof_effect_basis_matches_effect_bases(conn: Connection) -> None:
    """ck_iof_effect_basis's live allowed set is exactly schema.EFFECT_BASES."""
    allowed = _check_constraint_allowed_values(conn, "ck_iof_effect_basis")
    assert allowed == set(EFFECT_BASES)


def test_effect_basis_literal_matches_effect_bases() -> None:
    """The wire/stored EffectBasis Literal agrees with schema.EFFECT_BASES —
    also asserted at iof_records import time; restated here as an
    explicit, independently discoverable test (not just a collection-time
    side effect)."""
    assert get_args(EffectBasis) == EFFECT_BASES
