"""SQLAlchemy Core table metadata — eleven tables, two alembic migrations.

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
    Column("version", Integer, nullable=False, server_default="1"),
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
    Column("payload", JSONB, nullable=False),          # {quote, verification_result}
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

# --- Corpus / source model (task 003) ---

source_snapshot = Table(
    "source_snapshot",
    metadata,
    Column("source_snapshot_id", UUID(as_uuid=True), primary_key=True),
    Column("content_hash", Text, nullable=False),
    Column("text_basis", Text, nullable=False),    # "full_text" | "abstract_only"
    Column("source_locator", Text, nullable=False),
    Column("metadata", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # No project_id — identity is content, not project.
)

project_source_snapshot = Table(
    "project_source_snapshot",
    metadata,
    Column("project_source_snapshot_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column(
        "source_snapshot_id",
        UUID(as_uuid=True),
        ForeignKey("source_snapshot.source_snapshot_id"),
        nullable=False,
    ),
    Column("origin", Text, nullable=False),        # "uploaded" | "acquired"
    Column("run_id", UUID(as_uuid=True), ForeignKey("runs.run_id"), nullable=True),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("project_id", "source_snapshot_id", name="uq_project_source_snapshot"),
)

chunk = Table(
    "chunk",
    metadata,
    Column("chunk_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "source_snapshot_id",
        UUID(as_uuid=True),
        ForeignKey("source_snapshot.source_snapshot_id"),
        nullable=False,
    ),
    Column("sequence", Integer, nullable=False),
    Column("content", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("locator", JSONB, nullable=False),
    Column("segmentation_policy", Text, nullable=False),  # mandatory; "manual_v1" this slice
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_snapshot_id", "sequence", name="uq_chunk_snapshot_sequence"),
)

citation = Table(
    "citation",
    metadata,
    Column("citation_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "annotation_id",
        UUID(as_uuid=True),
        ForeignKey("annotation.annotation_id"),
        nullable=False,
    ),
    Column("chunk_id", UUID(as_uuid=True), ForeignKey("chunk.chunk_id"), nullable=False),
    Column("quote", Text, nullable=False),
    Column("verification_result", Text, nullable=False),  # "pass" | "fail"
    Column("created_at", DateTime(timezone=True), nullable=False),
)
