"""Unified conversation model and legacy planning-turn backfill.

Task 029 introduces project conversations for planning lineages and read-only
chats. Existing planning turns are assigned to legacy planning conversations
according to the approved migration-time run-state truth table.

Revision ID: d8e4a1c7f2b9
Revises: f4a8c2d7e1b9
Create Date: 2026-08-10 00:00:00.000000

"""
from datetime import UTC, datetime
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping

# revision identifiers, used by Alembic.
revision: str = "d8e4a1c7f2b9"
down_revision: Union[str, None] = "f4a8c2d7e1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_legacy_planning_conversations() -> None:
    """Assign existing planning turns to conversations from migration-time state."""
    bind = op.get_bind()
    uuid_type = postgresql.UUID(as_uuid=True)
    conversation = sa.table(
        "conversation",
        sa.column("id", uuid_type),
        sa.column("project_id", uuid_type),
        sa.column("kind", sa.Text()),
        sa.column("title", sa.Text()),
        sa.column("entry_artefact_id", uuid_type),
        sa.column("status", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("closed_at", sa.DateTime(timezone=True)),
        sa.column("archived_at", sa.DateTime(timezone=True)),
    )
    planning_turn = sa.table(
        "planning_transcript",
        sa.column("id", uuid_type),
        sa.column("project_id", uuid_type),
        sa.column("conversation_id", uuid_type),
        sa.column("status", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    capability_run = sa.table(
        "capability_run",
        sa.column("capability_run_id", uuid_type),
        sa.column("project_id", uuid_type),
        sa.column("status", sa.Text()),
        sa.column("started_at", sa.DateTime(timezone=True)),
        sa.column("ended_at", sa.DateTime(timezone=True)),
    )
    orchestration_plan = sa.table(
        "orchestration_plan",
        sa.column("project_id", uuid_type),
        sa.column("version", sa.Integer()),
        sa.column("status", sa.Text()),
    )
    migration_at = datetime.now(UTC)

    project_ids = bind.execute(
        sa.select(planning_turn.c.project_id).distinct()
    ).scalars()
    for project_id in project_ids:
        turns = bind.execute(
            sa.select(
                planning_turn.c.id,
                planning_turn.c.status,
                planning_turn.c.created_at,
            )
            .where(planning_turn.c.project_id == project_id)
            .order_by(planning_turn.c.created_at, planning_turn.c.id)
        ).mappings().all()
        latest_run = bind.execute(
            sa.select(
                capability_run.c.status,
                capability_run.c.ended_at,
            )
            .where(capability_run.c.project_id == project_id)
            .order_by(capability_run.c.started_at.desc())
            .limit(1)
        ).mappings().first()

        def create_conversation(
            owned_turns: list[RowMapping],
            *,
            status: str,
            closed_at: datetime | None,
        ) -> None:
            conversation_id = uuid4()
            bind.execute(
                conversation.insert().values(
                    id=conversation_id,
                    project_id=project_id,
                    kind="planning",
                    title="Planning",
                    entry_artefact_id=None,
                    status=status,
                    created_at=min(turn["created_at"] for turn in owned_turns),
                    closed_at=closed_at,
                    archived_at=None,
                )
            )
            bind.execute(
                planning_turn.update()
                .where(planning_turn.c.id.in_([turn["id"] for turn in owned_turns]))
                .values(conversation_id=conversation_id)
            )

        if latest_run is None:
            create_conversation(turns, status="active", closed_at=None)
            continue

        run_status = latest_run["status"]
        run_ended_at = latest_run["ended_at"]
        if run_status in {"succeeded", "degraded"}:
            post_run_turns = (
                [turn for turn in turns if turn["created_at"] > run_ended_at]
                if run_ended_at is not None
                else []
            )
            has_completed_post_run_turn = any(
                turn["status"] == "completed" for turn in post_run_turns
            )
            if has_completed_post_run_turn:
                pre_run_turns = [
                    turn for turn in turns if turn["created_at"] <= run_ended_at
                ]
                create_conversation(
                    pre_run_turns,
                    status="closed",
                    closed_at=run_ended_at,
                )
                create_conversation(post_run_turns, status="active", closed_at=None)
            else:
                create_conversation(turns, status="closed", closed_at=run_ended_at)
            continue

        if run_status in {"failed", "aborted", "interrupted"}:
            latest_plan = bind.execute(
                sa.select(orchestration_plan.c.status)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_plan == "abandoned":
                create_conversation(turns, status="closed", closed_at=migration_at)
            else:
                create_conversation(turns, status="active", closed_at=None)
            continue

        create_conversation(turns, status="active", closed_at=None)


def upgrade() -> None:
    op.create_unique_constraint("uq_artefact_id_project", "artefact", ["artefact_id", "project_id"])

    op.create_table(
        "conversation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("entry_artefact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["entry_artefact_id", "project_id"],
            ["artefact.artefact_id", "artefact.project_id"],
            name="fk_conversation_entry_artefact_project",
            match="SIMPLE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('planning', 'chat')", name="ck_conversation_kind"),
        sa.CheckConstraint(
            "status IN ('active', 'closed', 'archived')", name="ck_conversation_status"
        ),
        sa.CheckConstraint(
            "(status = 'archived') = (archived_at IS NOT NULL)",
            name="ck_conversation_archived_at",
        ),
        sa.CheckConstraint(
            "kind = 'chat' OR status <> 'archived'",
            name="ck_conversation_planning_never_archived",
        ),
    )
    op.create_index(
        "uq_conversation_one_active_planning",
        "conversation",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'planning' AND status = 'active'"),
    )

    op.create_table(
        "chat_turn",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("client_turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answer_payload", postgresql.JSONB(), nullable=True),
        sa.Column("capability_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"]),
        sa.ForeignKeyConstraint(
            ["capability_run_id"], ["capability_run.capability_run_id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "turn_index", name="uq_chat_turn_conv_index"),
        sa.UniqueConstraint(
            "conversation_id", "client_turn_id", name="uq_chat_turn_conv_client"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'cancelled')",
            name="ck_chat_turn_status",
        ),
    )

    op.add_column(
        "planning_transcript",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_planning_transcript_conversation",
        "planning_transcript",
        "conversation",
        ["conversation_id"],
        ["id"],
    )
    op.add_column(
        "orchestration_plan",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_orchestration_plan_conversation",
        "orchestration_plan",
        "conversation",
        ["conversation_id"],
        ["id"],
    )
    op.add_column(
        "artefact",
        sa.Column("capability_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_artefact_capability_run_project",
        "artefact",
        "capability_run",
        ["capability_run_id", "project_id"],
        ["capability_run_id", "project_id"],
        match="SIMPLE",
    )

    _backfill_legacy_planning_conversations()


def downgrade() -> None:
    op.drop_table("chat_turn")

    op.drop_constraint(
        "fk_planning_transcript_conversation", "planning_transcript", type_="foreignkey"
    )
    op.drop_column("planning_transcript", "conversation_id")
    op.drop_constraint(
        "fk_orchestration_plan_conversation", "orchestration_plan", type_="foreignkey"
    )
    op.drop_column("orchestration_plan", "conversation_id")

    op.drop_table("conversation")

    op.drop_constraint("fk_artefact_capability_run_project", "artefact", type_="foreignkey")
    op.drop_column("artefact", "capability_run_id")
    op.drop_constraint("uq_artefact_id_project", "artefact", type_="unique")
