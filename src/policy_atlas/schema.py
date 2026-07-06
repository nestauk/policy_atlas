"""SQLAlchemy Core table metadata — nineteen tables, nine alembic migrations.

No deferred columns (no block/artefact summary, no same_content_as, no lineage key).
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    SmallInteger,
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
    # Full-text attachment (task 008): the corpus document keeps its envelope snapshot
    # and gains a nullable link to its immutable full-text snapshot once ingested
    # (ADR 0003). full_text_status describes the fetch pipeline, not text availability
    # (that stays source_snapshot.text_basis); failure is never silent (ADR/contract
    # decision 3 — failure status ⟺ machine-readable reason present).
    Column(
        "full_text_snapshot_id",
        UUID(as_uuid=True),
        ForeignKey("source_snapshot.source_snapshot_id", name="fk_pss_full_text_snapshot"),
        nullable=True,
    ),
    Column("full_text_status", Text, nullable=False, server_default="not_attempted"),
    Column("full_text_error", Text, nullable=True),
    UniqueConstraint("project_id", "source_snapshot_id", name="uq_project_source_snapshot"),
    # Composite unique target for source_screening_result FK
    UniqueConstraint("project_source_snapshot_id", "project_id", name="uq_pss_id_project"),
    CheckConstraint(
        "full_text_status IN ('not_attempted', 'ingested', 'fetch_failed', 'parse_failed')",
        name="ck_pss_full_text_status",
    ),
    CheckConstraint(
        "(full_text_status = 'ingested') = (full_text_snapshot_id IS NOT NULL)",
        name="ck_pss_full_text_consistent",
    ),
    CheckConstraint(
        "(full_text_status IN ('fetch_failed', 'parse_failed')) = (full_text_error IS NOT NULL)",
        name="ck_pss_full_text_error_presence",
    ),
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

# --- Screening model (task 004) ---

evidence_scope = Table(
    "evidence_scope",
    metadata,
    Column("evidence_scope_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("intent", Text, nullable=False),
    Column("context", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Composite unique target for source_screening_result FK
    UniqueConstraint("evidence_scope_id", "project_id", name="uq_evidence_scope_id_project"),
)

source_screening_result = Table(
    "source_screening_result",
    metadata,
    Column("source_screening_result_id", UUID(as_uuid=True), primary_key=True),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("project_source_snapshot_id", UUID(as_uuid=True), nullable=False),
    Column("project_id", UUID(as_uuid=True), nullable=False),
    Column("screened_by_run_id", UUID(as_uuid=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("screen_basis", Text, nullable=True),
    Column("screen_decision_confidence", Float, nullable=True),
    Column("screened_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards: all three parents must share the same project_id
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_ssr_scope_project",
    ),
    ForeignKeyConstraint(
        ["project_source_snapshot_id", "project_id"],
        [
            "project_source_snapshot.project_source_snapshot_id",
            "project_source_snapshot.project_id",
        ],
        name="fk_ssr_pss_project",
    ),
    ForeignKeyConstraint(
        ["screened_by_run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_ssr_run_project",
    ),
    UniqueConstraint(
        "evidence_scope_id", "project_source_snapshot_id",
        name="uq_ssr_scope_source",
    ),
    CheckConstraint("status IN ('relevant', 'not_relevant', 'failed')", name="ck_ssr_status"),
    CheckConstraint(
        "screen_basis IS NULL OR screen_basis IN ('title_abstract', 'title_only')",
        name="ck_ssr_basis",
    ),
    CheckConstraint(
        "screen_decision_confidence IS NULL"
        " OR (screen_decision_confidence >= 0.0 AND screen_decision_confidence <= 1.0)",
        name="ck_ssr_confidence_range",
    ),
    CheckConstraint(
        "status = 'failed'"
        " OR (screen_basis IS NOT NULL AND screen_decision_confidence IS NOT NULL)",
        name="ck_ssr_non_null_when_decided",
    ),
    CheckConstraint(
        "status != 'failed' OR (screen_basis IS NULL AND screen_decision_confidence IS NULL)",
        name="ck_ssr_null_when_failed",
    ),
    Index("ix_ssr_scope_status", "evidence_scope_id", "status"),
)

# --- Classification model (task 005) ---

EVIDENCE_TYPES: tuple[str, ...] = (
    "Systematic Review and Meta-Analysis",
    "RCTs and Quasi-Experimental Studies",
    "Observational Research Studies",
    "Modelling & Simulation",
    "Policy Syntheses & Guidance Documents",
    "Qualitative & Contextual Evidence",
    "Expert Opinion and Commentary",
    "Other (Non-evidence documents)",
    "Unknown / Insufficient information",
)
_EVIDENCE_TYPES_SQL_LIST = ", ".join(f"'{t}'" for t in EVIDENCE_TYPES)

source_classification_result = Table(
    "source_classification_result",
    metadata,
    Column("source_classification_result_id", UUID(as_uuid=True), primary_key=True),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("project_source_snapshot_id", UUID(as_uuid=True), nullable=False),
    Column("project_id", UUID(as_uuid=True), nullable=False),
    Column("classified_by_run_id", UUID(as_uuid=True), nullable=False),
    Column("primary_evidence_type", Text, nullable=False),
    Column("classified_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards: all three parents must share the same project_id
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_scr_scope_project",
    ),
    ForeignKeyConstraint(
        ["project_source_snapshot_id", "project_id"],
        [
            "project_source_snapshot.project_source_snapshot_id",
            "project_source_snapshot.project_id",
        ],
        name="fk_scr_pss_project",
    ),
    ForeignKeyConstraint(
        ["classified_by_run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_scr_run_project",
    ),
    UniqueConstraint(
        "evidence_scope_id", "project_source_snapshot_id",
        name="uq_scr_scope_source",
    ),
    # open_tags retired in task 009 (decision 10) — source_tag is the single tag home.
    # Safe only because EVIDENCE_TYPES is a fixed, developer-controlled tuple (no user input,
    # no apostrophe-escaping) — never build a CHECK constraint this way from runtime data.
    CheckConstraint(
        f"primary_evidence_type IN ({_EVIDENCE_TYPES_SQL_LIST})",
        name="ck_scr_primary_evidence_type",
    ),
    Index("ix_scr_scope_type", "evidence_scope_id", "primary_evidence_type"),
)

# --- Appraisal model (task 006) ---

source_appraisal_result = Table(
    "source_appraisal_result",
    metadata,
    Column("source_appraisal_result_id", UUID(as_uuid=True), primary_key=True),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("project_source_snapshot_id", UUID(as_uuid=True), nullable=False),
    Column("project_id", UUID(as_uuid=True), nullable=False),
    Column("appraised_by_run_id", UUID(as_uuid=True), nullable=False),
    Column("quality_score", SmallInteger, nullable=False),  # 1..5, 5 = strongest (v2 rating)
    Column("rubric_version", Text, nullable=False),  # provenance travels with each appraisal
    Column("appraised_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards: all three parents must share the same project_id.
    # Deliberately no FK to source_classification_result — the "only classified rows are
    # appraised" invariant lives in the read path (appraise_sources selects from it);
    # a FK would harden the schema against the recorded re-run relaxation seams
    # (see docs/deferred.md).
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_sar_scope_project",
    ),
    ForeignKeyConstraint(
        ["project_source_snapshot_id", "project_id"],
        [
            "project_source_snapshot.project_source_snapshot_id",
            "project_source_snapshot.project_id",
        ],
        name="fk_sar_pss_project",
    ),
    ForeignKeyConstraint(
        ["appraised_by_run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_sar_run_project",
    ),
    UniqueConstraint(
        "evidence_scope_id", "project_source_snapshot_id",
        name="uq_sar_scope_source",
    ),
    CheckConstraint("quality_score BETWEEN 1 AND 5", name="ck_sar_quality_score"),
    Index("ix_sar_scope_score", "evidence_scope_id", "quality_score"),
)

# --- Acquisition model (task 007) ---

search_coverage_record = Table(
    "search_coverage_record",
    metadata,
    Column("search_coverage_record_id", UUID(as_uuid=True), primary_key=True),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("project_id", UUID(as_uuid=True), nullable=False),  # denormalized; cross-project guard
    Column("acquired_by_run_id", UUID(as_uuid=True), nullable=False),
    # [{"backend": ..., "trust_class": ..., "mode": ...}, ...] — the search-space boundary
    Column("backends", JSONB, nullable=False),
    Column("scope_filters", JSONB, nullable=False),  # v3.0: {} (no filters); shape reserved
    Column("stop_condition", Text, nullable=False),
    Column("adequacy_verdict", Text, nullable=False),
    Column("verdict_origin", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_scov_scope_project",
    ),
    ForeignKeyConstraint(
        ["acquired_by_run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_scov_run_project",
    ),
    UniqueConstraint("acquired_by_run_id", name="uq_scov_run"),  # one record per acquire run
    # 'saturated' deliberately absent — saturation-based stopping is a deferred seam (spec)
    CheckConstraint(
        "stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error')",
        name="ck_scov_stop_condition",
    ),
    CheckConstraint(
        "adequacy_verdict IN ('adequate', 'inadequate')",
        name="ck_scov_verdict",
    ),
    CheckConstraint(
        "verdict_origin IN ('model', 'human')",
        name="ck_scov_verdict_origin",
    ),
    CheckConstraint("jsonb_typeof(backends) = 'array'", name="ck_scov_backends_array"),
    CheckConstraint("jsonb_typeof(scope_filters) = 'object'", name="ck_scov_filters_object"),
)

# --- Characterise model (task 009) ---

chunk_embedding = Table(
    "chunk_embedding",
    metadata,
    Column("chunk_embedding_id", UUID(as_uuid=True), primary_key=True),
    Column("chunk_id", UUID(as_uuid=True), ForeignKey("chunk.chunk_id"), nullable=False),
    Column("embedding_profile", Text, nullable=False),  # e.g. "openai_text_embedding_3_small_v1"
    Column("unit_policy", Text, nullable=False),        # e.g. "embedding_unit_policy_v1"
    Column("unit_index", Integer, nullable=False),
    Column("unit_locator", JSONB, nullable=False),      # char offsets into the canonical chunk
    # Vector as a JSONB float array — code-validated (array, expected dims, finite floats);
    # pgvector arrives with the retrieve slice, the vectors' first reader (decision 3).
    Column("vector", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "chunk_id", "embedding_profile", "unit_policy", "unit_index",
        name="uq_chunk_embedding_unit",
    ),
)

characterisation_result = Table(
    "characterisation_result",
    metadata,
    Column("characterisation_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    # Required keys (test-asserted): prompt_version, discovery_model, assignment_model,
    # batch_size, retry counts.
    Column("grouping_provenance", JSONB, nullable=False),
    Column("coverage", JSONB, nullable=False),
    # Theme names, descriptions, member ids, sizes, the unclustered set — run-local by
    # design (capability.md): memberships never promote to canonical corpus state.
    Column("themes", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards, per the screening-result precedent.
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_char_scope_project",
    ),
    ForeignKeyConstraint(
        ["run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_char_run_project",
    ),
    UniqueConstraint("evidence_scope_id", "run_id", name="uq_char_scope_run"),
)

source_tag = Table(
    "source_tag",
    metadata,
    Column("source_tag_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("project_source_snapshot_id", UUID(as_uuid=True), nullable=False),
    Column("tag", Text, nullable=False),
    Column("tag_type", Text, nullable=False),
    # Assertion provenance: provider-curated ("openalex", "overton"), provider-LLM
    # ("overton_llm") and own-capability ("characterise") assertions never mix —
    # the same tag from two asserters is two rows (corroboration, not duplication).
    Column("asserted_by", Text, nullable=False),
    Column("created_by_run_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["project_source_snapshot_id", "project_id"],
        [
            "project_source_snapshot.project_source_snapshot_id",
            "project_source_snapshot.project_id",
        ],
        name="fk_stag_pss_project",
    ),
    ForeignKeyConstraint(
        ["created_by_run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_stag_run_project",
    ),
    UniqueConstraint(
        "project_source_snapshot_id", "tag_type", "tag", "asserted_by",
        name="uq_source_tag_assertion",
    ),
    # Widens by a one-line migration when the LLM classify tool's seam opens
    # ("methodological_structural") — no speculative value ships now (decision 10).
    CheckConstraint("tag_type IN ('topic_theme')", name="ck_stag_tag_type"),
)
