"""SQLAlchemy Core table metadata — seven tables, one alembic migration.

Schema is exactly as specified in the contract's *Initial schema*.
No deferred columns (no block/artefact summary, no same_content_as, no lineage key).
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

project = Table(
    "project",
    metadata,
    Column("project_id", UUID(as_uuid=True), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

artefact = Table(
    "artefact",
    metadata,
    Column("artefact_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("title", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Deferred: artefact summary field + pending/verified/failed marker
)

block = Table(
    "block",
    metadata,
    Column("block_id", UUID(as_uuid=True), primary_key=True),
    Column("artefact_id", UUID(as_uuid=True), ForeignKey("artefact.artefact_id"), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    Column("content", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Deferred: co-versioned summary + summary_status marker; block-lineage key; structured blocks
)

addressable_unit = Table(
    "addressable_unit",
    metadata,
    Column("unit_id", UUID(as_uuid=True), primary_key=True),
    Column("block_id", UUID(as_uuid=True), ForeignKey("block.block_id"), nullable=False),
    Column("unit_type", Text, nullable=False),  # "text_span" this slice
    Column("locator", JSONB, nullable=False),   # e.g. {"start": 0, "end": 42}
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("block_id", "unit_id", name="uq_addressable_unit_block_unit"),
    # Deferred: same_content_as link
)

annotation = Table(
    "annotation",
    metadata,
    Column("annotation_id", UUID(as_uuid=True), primary_key=True),
    Column("block_id", UUID(as_uuid=True), nullable=False),
    Column("unit_id", UUID(as_uuid=True), nullable=False),
    Column("annotation_type", Text, nullable=False),  # "citation" this slice
    Column("payload", JSONB, nullable=False),          # {source_ref, quote, verification_result}
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Composite FK: (block_id, unit_id) → addressable_unit(block_id, unit_id)
    # so annotation.block_id can never disagree with its unit's block_id.
    ForeignKeyConstraint(
        ["block_id", "unit_id"],
        ["addressable_unit.block_id", "addressable_unit.unit_id"],
        name="fk_annotation_block_unit",
    ),
)

runs = Table(
    "runs",
    metadata,
    Column("run_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("status", Text, nullable=False),  # running → succeeded/failed
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    # Composite unique so event_log can FK on (run_id, project_id) and prevent cross-project events.
    UniqueConstraint("run_id", "project_id", name="uq_runs_run_project"),
    # Deferred: persisting plan/config on the run (compiled config travels in plan.compiled event)
)

event_log = Table(
    "event_log",
    metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("sequence", BigInteger, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    # Composite FK: event_log(run_id, project_id) → runs(run_id, project_id)
    # Prevents appending a run from project B into project A's audit log.
    ForeignKeyConstraint(
        ["run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_event_log_run_project",
    ),
    # Ordering key: (project_id, sequence) — not occurred_at (ties/clock skew)
    UniqueConstraint("project_id", "sequence", name="uq_event_log_project_sequence"),
)
