"""SQLAlchemy Core table metadata — thirty-seven tables plus one read view.

No deferred columns (no same_content_as or lineage key).
"""

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ColumnElement,
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

# Task 033 tenancy: an organisation sits above the entity hierarchy, and a row's
# `org_id` is NULL until its owner is enrolled. NULL never matches NULL — the org
# leg is a SQL predicate everywhere, never a Python comparison of two loaded values.
organisation = Table(
    "organisation",
    metadata,
    Column("org_id", UUID(as_uuid=True), primary_key=True),
    Column("name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("name", name="uq_organisation_name"),
)

app_user = Table(
    "app_user",
    metadata,
    Column("user_id", Text, primary_key=True),  # the token `sub`
    Column("org_id", UUID(as_uuid=True), ForeignKey("organisation.org_id"), nullable=True),
    Column("display_name", Text, nullable=False),  # never falls back to the email
    Column("email", Text, nullable=True),  # ops- and admin-facing only
    Column("is_admin", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

# Splash-page Request-access intake. No FK to app_user — ops enrolment is the
# Cognito on-ramp; this table is a queue for humans, not an identity store.
waitlist_entry = Table(
    "waitlist_entry",
    metadata,
    Column("entry_id", UUID(as_uuid=True), primary_key=True),
    Column("email", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("organisation", Text, nullable=True),
    Column("role_or_reason", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("email", name="uq_waitlist_entry_email"),
)

portfolio = Table(
    "portfolio",
    metadata,
    Column("portfolio_id", UUID(as_uuid=True), primary_key=True),
    Column("owner_user_id", Text, nullable=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("org_id", UUID(as_uuid=True), ForeignKey("organisation.org_id"), nullable=True),
    Column("visibility", Text, nullable=False, server_default="private"),
    CheckConstraint("visibility IN ('org', 'private')", name="ck_portfolio_visibility"),
    Index("ix_portfolio_org_visibility", "org_id", "visibility"),
)

portfolio_membership = Table(
    "portfolio_membership",
    metadata,
    Column(
        "portfolio_id",
        UUID(as_uuid=True),
        ForeignKey("portfolio.portfolio_id"),
        primary_key=True,
    ),
    Column(
        "project_id",
        UUID(as_uuid=True),
        ForeignKey("project.project_id"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_portfolio_membership_project_id", "project_id"),
)

project = Table(
    "project",
    metadata,
    Column("project_id", UUID(as_uuid=True), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("name", Text, nullable=False),
    Column("question", Text, nullable=True),
    Column("status", Text, nullable=False),  # active|archived
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("archived_at", DateTime(timezone=True), nullable=True),
    Column("owner_user_id", Text, nullable=True),
    Column("org_id", UUID(as_uuid=True), ForeignKey("organisation.org_id"), nullable=True),
    Column("visibility", Text, nullable=False, server_default="private"),
    Column("is_public", Boolean, nullable=False, server_default=text("false")),
    CheckConstraint("status IN ('active', 'archived')", name="ck_project_status"),
    CheckConstraint(
        "(status = 'archived') = (archived_at IS NOT NULL)",
        name="ck_project_archived_at",
    ),
    CheckConstraint("visibility IN ('org', 'private')", name="ck_project_visibility"),
    Index("ix_project_org_visibility_status", "org_id", "visibility", "status"),
)

artefact = Table(
    "artefact",
    metadata,
    Column("artefact_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("capability_run_id", UUID(as_uuid=True), nullable=True),
    Column("title", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("summary", Text, nullable=True),
    Column("summary_status", Text, nullable=True),
    CheckConstraint(
        "summary_status IN ('pending', 'verified', 'failed')",
        name="ck_artefact_summary_status",
    ),
    UniqueConstraint("artefact_id", "project_id", name="uq_artefact_id_project"),
    ForeignKeyConstraint(
        ["capability_run_id", "project_id"],
        ["capability_run.capability_run_id", "capability_run.project_id"],
        name="fk_artefact_capability_run_project",
        match="SIMPLE",
    ),
)

conversation = Table(
    "conversation",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("entry_artefact_id", UUID(as_uuid=True), nullable=True),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("closed_at", DateTime(timezone=True), nullable=True),
    Column("archived_at", DateTime(timezone=True), nullable=True),
    # The author's `sub`. Nullable because rows predating task 033 have no
    # recorded author — those belong to the project owner (the legacy disjunct).
    Column("created_by", Text, nullable=True),
    ForeignKeyConstraint(
        ["entry_artefact_id", "project_id"],
        ["artefact.artefact_id", "artefact.project_id"],
        name="fk_conversation_entry_artefact_project",
        match="SIMPLE",
    ),
    CheckConstraint("kind IN ('planning', 'chat')", name="ck_conversation_kind"),
    CheckConstraint(
        "status IN ('active', 'closed', 'archived')", name="ck_conversation_status"
    ),
    CheckConstraint(
        "(status = 'archived') = (archived_at IS NOT NULL)",
        name="ck_conversation_archived_at",
    ),
    CheckConstraint(
        "kind = 'chat' OR status <> 'archived'",
        name="ck_conversation_planning_never_archived",
    ),
    Index(
        "uq_conversation_one_active_planning",
        "project_id",
        unique=True,
        postgresql_where=text("kind = 'planning' AND status = 'active'"),
    ),
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
    Column("summary", Text, nullable=True),
    Column("summary_status", Text, nullable=True),
    CheckConstraint(
        "summary_status IN ('pending', 'verified', 'failed')",
        name="ck_block_summary_status",
    ),
    # Deferred: block-lineage key; structured blocks
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
    # NULLABLE — resolved when this run executes within a capability_run walk;
    # the composite FK below binds only once it's set (MATCH SIMPLE, per
    # synthesis_result's optional-reference precedent).
    Column("capability_run_id", UUID(as_uuid=True), nullable=True),
    # Composite unique so event_log can FK on (run_id, project_id) and prevent cross-project events.
    UniqueConstraint("run_id", "project_id", name="uq_runs_run_project"),
    # Cross-project FK guard, per the synthesis-result/orchestration-plan
    # precedent: NULL capability_run_id skips the check (MATCH SIMPLE), so the
    # guard binds only once a run is actually attributed to a walk.
    ForeignKeyConstraint(
        ["capability_run_id", "project_id"],
        ["capability_run.capability_run_id", "capability_run.project_id"],
        name="fk_runs_capability_run_project",
    ),
    # Deferred: persisting plan/config on the run (compiled config travels in plan.compiled event)
)

event_log = Table(
    "event_log",
    metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True),
    # Nullable for project lifecycle audit events; steering events retain their
    # own non-null attachment invariant at their emission seam.
    Column("run_id", UUID(as_uuid=True), nullable=True),
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


def pss_owns_snapshot(snapshot_id: ColumnElement[uuid.UUID] | uuid.UUID) -> ColumnElement[bool]:
    """Return the corpus-ownership predicate for one candidate snapshot id.

    True when ``snapshot_id`` is either the envelope (``source_snapshot_id``)
    or the full-text (``full_text_snapshot_id``) snapshot linked by a
    ``project_source_snapshot`` row — the "does this chunk/snapshot belong to
    this project" predicate that was hand-written at five call sites across
    the API layer (task 029 delta-review). ``snapshot_id`` may be a column
    expression (e.g. ``chunk.c.source_snapshot_id``) or a bound scalar — both
    compare correctly against ``project_source_snapshot``'s two snapshot
    columns. Callers still add their own ``project_id`` scoping; this returns
    only the ownership half of the predicate, suitable for a ``.join()``
    on-clause or a ``.where()``.

    Args:
        snapshot_id: The candidate snapshot id/column to test ownership for.

    Returns:
        A SQLAlchemy boolean clause: ``pss.source_snapshot_id == snapshot_id
        OR pss.full_text_snapshot_id == snapshot_id``.
    """
    return (project_source_snapshot.c.source_snapshot_id == snapshot_id) | (
        project_source_snapshot.c.full_text_snapshot_id == snapshot_id
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
    # Stage provenance (task 014 decision 11): 1 = envelope screen, 2 = full-text
    # screen. Effective result = highest-stage non-failed row per (scope, source) —
    # a READ rule (the effective-screen helper), never a storage rule: stage-1 rows
    # are never mutated by a stage-2 pass.
    Column("screen_stage", Integer, nullable=False, server_default="1"),
    # Generation supersession (task 024 decision 7b): criteria-changed re-screen
    # writes fresh rows at generation = max+1; old rows are never mutated. The
    # effective-screen read rule orders generation DESC, stage DESC.
    Column("screen_generation", Integer, nullable=False, server_default="0"),
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
    # Partial unique (task 014, replacing the uq_ssr_scope_source constraint;
    # widened task 024 decision 7b to admit generation supersession): at most
    # one NON-FAILED row per (scope, source, stage, generation) — failed rows
    # are attempt history and never block retry (the 011 extraction-memo
    # precedent); a re-screen's fresh generation coexists with prior
    # generations rather than colliding with them.
    Index(
        "uq_ssr_scope_source_stage",
        "evidence_scope_id", "project_source_snapshot_id", "screen_stage",
        "screen_generation",
        unique=True,
        postgresql_where=text("status != 'failed'"),
    ),
    # 'excluded_retracted' (task 019 Phase D, owner decision): a retracted
    # document (OpenAlex is_retracted) is excluded at screening as policy, a
    # distinct terminal status never conflated with a 'not_relevant'
    # relevance verdict.
    CheckConstraint(
        "status IN ('relevant', 'not_relevant', 'failed', 'excluded_retracted')",
        name="ck_ssr_status",
    ),
    CheckConstraint(
        "screen_basis IS NULL"
        " OR screen_basis IN ('title_abstract', 'title_only', 'full_text')",
        name="ck_ssr_basis",
    ),
    CheckConstraint("screen_stage IN (1, 2)", name="ck_ssr_stage"),
    CheckConstraint("screen_generation >= 0", name="ck_ssr_generation_nonneg"),
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
    # 'saturated' deliberately absent — saturation-based stopping is a deferred seam (spec).
    # Task 015 widened the vocabulary with the deep loop's stops (short_circuit =
    # discovery-rate collapse within one run; budget_exhausted covers every budget
    # incl. the round cap; target_reached = confident-relevant target met).
    # Task 019 Phase D widened it again with the honest stop-grain pair: 'completed'
    # (a clean, unforced completion — acquire's new default, replacing the old
    # breadth_truncated default) and 'wall_clock_exceeded' (the rapid/standard
    # fan-out's own wall-clock breach). 'breadth_truncated' is retained in the
    # vocabulary for historical rows only — acquire no longer writes it.
    CheckConstraint(
        "stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error',"
        " 'short_circuit', 'budget_exhausted', 'target_reached', 'completed',"
        " 'wall_clock_exceeded')",
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

# --- Select model (task 010) ---

SELECTION_STRATEGIES: tuple[str, ...] = ("coverage_stratified_v1", "llm_rerank_v1")
_SELECTION_STRATEGIES_SQL_LIST = ", ".join(f"'{s}'" for s in SELECTION_STRATEGIES)

selection_result = Table(
    "selection_result",
    metadata,
    Column("selection_result_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("strategy", Text, nullable=False),
    Column("budget", Integer, nullable=False),
    # Required keys (test-asserted): strategy version, executed directive + source,
    # effective weights, signal availability; under llm_rerank_v1 additionally
    # prompt_version, model, batch_size, retry/fallback counts.
    Column("selection_provenance", JSONB, nullable=False),
    # Per doc: pss id, stratum, signal scores (+ llm score/reason where ranked),
    # text_basis, reason (must_include | breadth_floor | ranked).
    Column("selected", JSONB, nullable=False),
    # Per stratum: counts by reason class + notable flagged exclusions;
    # base-ladder counts incl. non_evidence. not_selected stays derivable
    # coverage state — never a doc-level status column.
    Column("excluded", JSONB, nullable=False),
    Column("flags", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards, per the characterisation-result precedent.
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_selr_scope_project",
    ),
    ForeignKeyConstraint(
        ["run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_selr_run_project",
    ),
    # Run-local by design: same-run re-execution is a loud error, retry = new run.
    UniqueConstraint("evidence_scope_id", "run_id", name="uq_selr_scope_run"),
    CheckConstraint(
        f"strategy IN ({_SELECTION_STRATEGIES_SQL_LIST})",
        name="ck_selr_strategy",
    ),
    CheckConstraint("budget > 0", name="ck_selr_budget_positive"),
)

# Tag types; writers import them via policy_atlas.core.tags.
TOPIC_THEME = "topic_theme"
# Classify's open methodological/structural tag proposals (task 014 decision 6).
METHODOLOGICAL_STRUCTURAL = "methodological_structural"

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
    Column("theme_id", UUID(as_uuid=True), nullable=True),
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
    CheckConstraint(
        f"tag_type IN ('{TOPIC_THEME}', '{METHODOLOGICAL_STRUCTURAL}')",
        name="ck_stag_tag_type",
    ),
)

# Shared bound for untrusted scope-context directive strings (select's selection
# directive, group's grouping directive) — each parser fails closed above it.
# Hoisted from select.py (012 review): the bound is cross-component, not select's.
DIRECTIVE_STRING_MAX = 200

# --- Extract / findings layer (task 011) ---

EXTRACTION_STATUSES: tuple[str, ...] = ("extracted", "no_findings", "extraction_failed")
EXTRACTION_BASES: tuple[str, ...] = ("full_text", "abstract_only")
EFFECT_DIRECTIONS: tuple[str, ...] = ("increase", "decrease", "no_effect", "mixed", "unclear")
EFFECT_BASES: tuple[str, ...] = ("observed", "modelled")
ESTIMATE_LEVELS: tuple[str, ...] = ("study", "pooled", "claim")
CAUSALITY_BY_DESIGN: tuple[str, ...] = (
    "attributable",
    "plausibly_causal",
    "associational",
    "descriptive",
)
CONTEXT_TYPES: tuple[str, ...] = (
    "mechanism",
    "barrier",
    "enabler",
    "implementation_condition",
    "delivery_process",
    "adaptation",
    "fidelity",
)
CLAIM_LEVELS: tuple[str, ...] = ("study", "pooled")
CLAIM_BASES: tuple[str, ...] = ("studied", "author_assertion", "cited_theory")
CONTEXT_LEVELS: tuple[str, ...] = ("system", "organisation", "provider", "recipient")

_EXTRACTION_STATUSES_SQL = ", ".join(f"'{s}'" for s in EXTRACTION_STATUSES)
_EXTRACTION_BASES_SQL = ", ".join(f"'{b}'" for b in EXTRACTION_BASES)
_EFFECT_DIRECTIONS_SQL = ", ".join(f"'{d}'" for d in EFFECT_DIRECTIONS)
_EFFECT_BASES_SQL = ", ".join(f"'{b}'" for b in EFFECT_BASES)
_ESTIMATE_LEVELS_SQL = ", ".join(f"'{lv}'" for lv in ESTIMATE_LEVELS)
_CAUSALITY_SQL = ", ".join(f"'{c}'" for c in CAUSALITY_BY_DESIGN)
_CONTEXT_TYPES_SQL = ", ".join(f"'{t}'" for t in CONTEXT_TYPES)
_CLAIM_LEVELS_SQL = ", ".join(f"'{lv}'" for lv in CLAIM_LEVELS)
_CLAIM_BASES_SQL = ", ".join(f"'{b}'" for b in CLAIM_BASES)
_CONTEXT_LEVELS_SQL = ", ".join(f"'{lv}'" for lv in CONTEXT_LEVELS)
# Keep this schema literal in sync with iof_prompt.UNCLASSIFIED_EVIDENCE_TYPE;
# schema.py deliberately does not import prompt modules.
_SER_UNCLASSIFIED_EVIDENCE_TYPE = "Unclassified"
_SER_EVIDENCE_TYPES_SQL_LIST = ", ".join(
    f"'{t}'" for t in (*EVIDENCE_TYPES, _SER_UNCLASSIFIED_EVIDENCE_TYPE)
)

# The two memo (success) states — a failed attempt inserts freely as attempt
# history and never satisfies or blocks the memo lookup (contract rev 1.5).
MEMO_STATUSES: tuple[str, ...] = ("extracted", "no_findings")
_MEMO_WHERE_SQL = "status IN ('extracted', 'no_findings')"

source_extraction_record = Table(
    "source_extraction_record",
    metadata,
    Column("extraction_record_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    # The extracted snapshot: the selected pss's full_text_snapshot_id (basis
    # full_text) or its envelope snapshot (basis abstract_only). source_snapshot
    # is content-keyed/shared, so the cross-project guard rides the pss link.
    Column(
        "source_snapshot_id",
        UUID(as_uuid=True),
        ForeignKey("source_snapshot.source_snapshot_id"),
        nullable=False,
    ),
    Column("project_source_snapshot_id", UUID(as_uuid=True), nullable=False),
    Column("extraction_fingerprint", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("basis", Text, nullable=False),
    # Extraction-call provenance: the evidence type actually sent to the prompt.
    # NULL means no prompt call was attempted; consumers keep reading the live
    # classification, and the two values may legitimately diverge.
    Column("primary_evidence_type", Text, nullable=True),
    Column("error", Text, nullable=True),  # reason-coded on failure
    Column("finding_count", Integer, nullable=False, server_default="0"),
    Column("run_id", UUID(as_uuid=True), nullable=False),  # creating run; assertion provenance
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards, per the screening-result precedent.
    ForeignKeyConstraint(
        ["run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_ser_run_project",
    ),
    ForeignKeyConstraint(
        ["project_source_snapshot_id", "project_id"],
        [
            "project_source_snapshot.project_source_snapshot_id",
            "project_source_snapshot.project_id",
        ],
        name="fk_ser_pss_project",
    ),
    # Composite unique target for the finding table's cross-project FK guard
    # (the uq_pss_id_project / uq_runs_run_project parent pattern).
    UniqueConstraint("extraction_record_id", "project_id", name="uq_ser_id_project"),
    # The memo key: partial unique over the two success states only, so a failed
    # attempt never blocks its own retry (contract rev 1.5).
    Index(
        "uq_ser_memo",
        "project_id",
        "source_snapshot_id",
        "extraction_fingerprint",
        unique=True,
        postgresql_where=text(_MEMO_WHERE_SQL),
    ),
    CheckConstraint(f"status IN ({_EXTRACTION_STATUSES_SQL})", name="ck_ser_status"),
    CheckConstraint(f"basis IN ({_EXTRACTION_BASES_SQL})", name="ck_ser_basis"),
    CheckConstraint(
        f"primary_evidence_type IS NULL OR primary_evidence_type IN "
        f"({_SER_EVIDENCE_TYPES_SQL_LIST})",
        name="ck_ser_evidence_type",
    ),
    # Failure is never silent: failed ⟺ reason-coded (the pss full-text precedent).
    CheckConstraint(
        "(status = 'extraction_failed') = (error IS NOT NULL)",
        name="ck_ser_error_presence",
    ),
)

intervention_outcome_finding = Table(
    "intervention_outcome_finding",
    metadata,
    Column("finding_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("extraction_record_id", UUID(as_uuid=True), nullable=False),
    # Source-named references — never canonical entities (data-model findings layer).
    Column("intervention", Text, nullable=False),
    Column("outcome", Text, nullable=False),  # base measure only; qualifiers are stratum
    Column("population", Text, nullable=True),
    Column("setting", Text, nullable=True),
    Column("comparator", Text, nullable=True),
    Column("effect_direction", Text, nullable=False),  # a reported null result is a finding
    Column("estimate_level", Text, nullable=True),
    Column("study_design", Text, nullable=True),
    Column("study_geography", Text, nullable=True),
    # Canonical sorted array of {type, value}; closed type vocabulary (contract rev 1.5).
    Column("stratum_qualifiers", JSONB, nullable=False),
    # Reported values only: effect size + type, CI/SE, p-value, N, k, I², τ².
    Column("statistics", JSONB, nullable=False),
    Column("causality_by_design", Text, nullable=True),
    Column("effect_basis", Text, nullable=True),
    Column("is_primary", Boolean, nullable=True),
    Column("is_prevalence_only", Boolean, nullable=True),
    # Per absent nullable field: not_extracted | unclear | not_applicable.
    Column("field_coverage", JSONB, nullable=False),
    # Anchors: chunk_id (NULL for abstract basis) · verbatim quote · match status ·
    # raw char interval when verified (rev 1.3/1.4).
    Column("grounding", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["extraction_record_id", "project_id"],
        [
            "source_extraction_record.extraction_record_id",
            "source_extraction_record.project_id",
        ],
        name="fk_iof_record_project",
    ),
    CheckConstraint(f"effect_direction IN ({_EFFECT_DIRECTIONS_SQL})", name="ck_iof_direction"),
    CheckConstraint(
        f"estimate_level IS NULL OR estimate_level IN ({_ESTIMATE_LEVELS_SQL})",
        name="ck_iof_estimate_level",
    ),
    CheckConstraint(
        f"causality_by_design IS NULL OR causality_by_design IN ({_CAUSALITY_SQL})",
        name="ck_iof_causality",
    ),
    CheckConstraint(
        f"effect_basis IS NULL OR effect_basis IN ({_EFFECT_BASES_SQL})",
        name="ck_iof_effect_basis",
    ),
    CheckConstraint("jsonb_typeof(stratum_qualifiers) = 'array'", name="ck_iof_strata_array"),
    CheckConstraint("jsonb_typeof(grounding) = 'array'", name="ck_iof_grounding_array"),
    Index("ix_iof_record", "extraction_record_id"),
)

implementation_context_finding = Table(
    "implementation_context_finding",
    metadata,
    Column("finding_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("extraction_record_id", UUID(as_uuid=True), nullable=False),
    # One implementation-context claim about a named intervention, grounded in one source.
    Column("context_type", Text, nullable=False),
    Column("claim", Text, nullable=False),
    Column("context_label", Text, nullable=True),
    # Source-named references — shared meaning with IOF; requiredness is per schema.
    Column("intervention", Text, nullable=False),
    Column("outcome", Text, nullable=True),
    Column("population", Text, nullable=True),
    Column("setting", Text, nullable=True),
    Column("study_geography", Text, nullable=True),
    Column("study_design", Text, nullable=True),
    Column("claim_level", Text, nullable=True),
    Column("claim_basis", Text, nullable=True),
    Column("level", Text, nullable=True),
    Column("resource_requirements", Text, nullable=True),
    Column("workforce_requirements", Text, nullable=True),
    # Per absent nullable field: not_extracted.
    Column("field_coverage", JSONB, nullable=False),
    # Anchors: same qv_v1 grounding payload shape as IOF.
    Column("grounding", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["extraction_record_id", "project_id"],
        [
            "source_extraction_record.extraction_record_id",
            "source_extraction_record.project_id",
        ],
        name="fk_icf_record_project",
    ),
    CheckConstraint(f"context_type IN ({_CONTEXT_TYPES_SQL})", name="ck_icf_context_type"),
    CheckConstraint(
        f"claim_level IS NULL OR claim_level IN ({_CLAIM_LEVELS_SQL})",
        name="ck_icf_claim_level",
    ),
    CheckConstraint(
        f"claim_basis IS NULL OR claim_basis IN ({_CLAIM_BASES_SQL})",
        name="ck_icf_claim_basis",
    ),
    CheckConstraint(
        f"level IS NULL OR level IN ({_CONTEXT_LEVELS_SQL})",
        name="ck_icf_level",
    ),
    CheckConstraint("jsonb_typeof(grounding) = 'array'", name="ck_icf_grounding_array"),
    Index("ix_icf_record", "extraction_record_id"),
)

finding_reference_union = Table(
    "finding_reference_union",
    metadata,
    Column("finding_id", UUID(as_uuid=True)),
    Column("kind", Text),
    Column("extraction_record_id", UUID(as_uuid=True)),
    Column("project_id", UUID(as_uuid=True)),
    Column("intervention", Text),
    Column("outcome", Text),
    Column("population", Text),
    Column("setting", Text),
    Column("study_geography", Text),
    Column("study_design", Text),
)

extraction_result = Table(
    "extraction_result",
    metadata,
    Column("extraction_result_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("selection_run_id", UUID(as_uuid=True), nullable=False),  # the executed reference
    # Fingerprint + full component map: profile, schema, prompt, model, mode,
    # field rules, verifier, window params, max output tokens, retry cap, pass count.
    Column("extraction_provenance", JSONB, nullable=False),
    # Per doc: pss id, status, basis, finding count, fresh|reused, error reason.
    Column("docs", JSONB, nullable=False),
    # Base ladder: selected, extracted, no_findings, failed, fresh, reused,
    # findings total, quote_unverified, basis shares.
    Column("counts", JSONB, nullable=False),
    Column("flags", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_exr_scope_project",
    ),
    ForeignKeyConstraint(
        ["run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_exr_run_project",
    ),
    # The executed selection must exist for this scope (targets uq_selr_scope_run),
    # so a roll-up can never reference a selection that was never written.
    ForeignKeyConstraint(
        ["evidence_scope_id", "selection_run_id"],
        ["selection_result.evidence_scope_id", "selection_result.run_id"],
        name="fk_exr_selection",
    ),
    # Run-local roll-up: same-run re-execution is a loud error, retry = new run.
    UniqueConstraint("evidence_scope_id", "run_id", name="uq_exr_scope_run"),
)

# --- Group / facet-level theming (task 012) ---

GROUPING_FACETS: tuple[str, ...] = (
    "intervention",
    "outcome",
    "population",
    "barrier_theme",
    "enabler_theme",
    "mechanism_theme",
)

grouping_result = Table(
    "grouping_result",
    metadata,
    Column("grouping_result_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("extraction_run_id", UUID(as_uuid=True), nullable=False),  # the executed reference
    # Required keys (test-asserted): prompt version, model, mode, facet + source,
    # call/repair counts, value cap, and the inherited extraction base —
    # fingerprint + profile, base-ladder counts, finding-set size + sha256,
    # facet coverage breakdown (contract rev 1.3).
    Column("grouping_provenance", JSONB, nullable=False),
    # Per group: label, description, member values, member finding ids, size,
    # direction spread; plus the ungrouped and no_value residuals, each with its
    # direction spread — run-local by design (capability.md § Cluster persistence):
    # memberships never promote to canonical state.
    Column("groups", JSONB, nullable=False),
    Column("counts", JSONB, nullable=False),
    Column("flags", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards, per the extraction-result precedent.
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_grr_scope_project",
    ),
    ForeignKeyConstraint(
        ["run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_grr_run_project",
    ),
    # The executed extraction must exist for this scope (targets uq_exr_scope_run),
    # so a grouping can never reference an extraction that was never written.
    ForeignKeyConstraint(
        ["evidence_scope_id", "extraction_run_id"],
        ["extraction_result.evidence_scope_id", "extraction_result.run_id"],
        name="fk_grr_extraction",
    ),
    # Run-local roll-up: same-run re-execution is a loud error, retry = new run.
    UniqueConstraint("evidence_scope_id", "run_id", name="uq_grr_scope_run"),
)

# --- Synthesise model (task 013) ---

synthesis_result = Table(
    "synthesis_result",
    metadata,
    Column("synthesis_result_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    # Resolved references (all optional — substrate-conditional, contract decision 2).
    # NULL run ids skip the composite FK check (MATCH SIMPLE), so each guard binds
    # only when that substrate actually resolved.
    Column("characterisation_run_id", UUID(as_uuid=True), nullable=True),
    Column("selection_run_id", UUID(as_uuid=True), nullable=True),
    Column("extraction_run_id", UUID(as_uuid=True), nullable=True),
    Column("grouping_run_id", UUID(as_uuid=True), nullable=True),
    # The minted artefact — zero-substrate runs fail structurally and write no row,
    # so the link is NOT NULL. The 001 substrate stores the artefact itself; this
    # table is the run-scoped execution roll-up (contract § Schema).
    Column(
        "artefact_id",
        UUID(as_uuid=True),
        ForeignKey("artefact.artefact_id"),
        nullable=False,
    ),
    # Required keys (test-asserted): three prompt-surface versions incl. tool schemas,
    # models, judge envelope-policy version, backend modes, per-phase call/turn/repair
    # counts, substrate profile, retrieval scope (doc/unit counts, selection prior +
    # boost, executed retrieval_boosts + unmatched_boosts, reranker mode), section set
    # + source, all caps, per-section tool-call counts + gathered-id hash, inherited
    # chain base per resolved reference.
    Column("synthesis_provenance", JSONB, nullable=False),
    # Per section: title/focus, block_id, assigned group ids, tool-call count, claim
    # counts by type, tier distribution, verification counters, flags.
    Column("blocks", JSONB, nullable=False),
    Column("counts", JSONB, nullable=False),
    Column("flags", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Cross-project FK guards, per the grouping-result precedent.
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_synr_scope_project",
    ),
    ForeignKeyConstraint(
        ["run_id", "project_id"],
        ["runs.run_id", "runs.project_id"],
        name="fk_synr_run_project",
    ),
    # Each resolved reference must exist for this scope (targets the parents'
    # (evidence_scope_id, run_id) uniques), so a roll-up can never reference an
    # upstream run that was never written.
    ForeignKeyConstraint(
        ["evidence_scope_id", "characterisation_run_id"],
        ["characterisation_result.evidence_scope_id", "characterisation_result.run_id"],
        name="fk_synr_characterisation",
    ),
    ForeignKeyConstraint(
        ["evidence_scope_id", "selection_run_id"],
        ["selection_result.evidence_scope_id", "selection_result.run_id"],
        name="fk_synr_selection",
    ),
    ForeignKeyConstraint(
        ["evidence_scope_id", "extraction_run_id"],
        ["extraction_result.evidence_scope_id", "extraction_result.run_id"],
        name="fk_synr_extraction",
    ),
    ForeignKeyConstraint(
        ["evidence_scope_id", "grouping_run_id"],
        ["grouping_result.evidence_scope_id", "grouping_result.run_id"],
        name="fk_synr_grouping",
    ),
    # Run-local roll-up: same-run re-execution is a loud error, retry = new run.
    UniqueConstraint("evidence_scope_id", "run_id", name="uq_synr_scope_run"),
)

# --- Orchestration plan (task 017) ---

orchestration_plan = Table(
    "orchestration_plan",
    metadata,
    Column("plan_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("conversation_id", UUID(as_uuid=True), ForeignKey("conversation.id"), nullable=True),
    # NULLABLE — resolved at approval time; the composite FK below binds only
    # once it's set (MATCH SIMPLE, per synthesis_result's optional references).
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=True),
    Column("version", Integer, nullable=False),  # 1..n; amendments append rows
    Column("status", Text, nullable=False),  # proposed|approved|superseded|abandoned
    Column("payload", JSONB, nullable=False),  # the validated OrchestrationPlan dump
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", Text, nullable=False),  # 'user'|'planner' attribution
    Column("approved_at", DateTime(timezone=True), nullable=True),
    # Cross-project FK guard, per the synthesis-result precedent: NULL
    # evidence_scope_id skips the check (MATCH SIMPLE), so the guard binds
    # only once a scope is actually resolved.
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_oplan_scope_project",
    ),
    # One plan lineage per project in v1 — amendments append new-version rows.
    UniqueConstraint("project_id", "version", name="uq_oplan_project_version"),
    CheckConstraint(
        "status IN ('proposed', 'approved', 'superseded', 'abandoned')",
        name="ck_oplan_status",
    ),
    CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_oplan_payload_object"),
)

# --- Durable planning transcript (task 027) ---

planning_transcript = Table(
    "planning_transcript",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("conversation_id", UUID(as_uuid=True), ForeignKey("conversation.id"), nullable=True),
    Column("client_turn_id", UUID(as_uuid=True), nullable=False),
    # This is the transcript's ordering coordinate. ``created_at`` remains
    # display metadata only: timestamp ordering is not a conversation order.
    Column("turn_index", Integer, nullable=False),
    Column("user_message", Text, nullable=False),
    Column("reply", Text, nullable=True),
    # ``planner_state`` is the raw PlanDraftWire dump used as the next call's
    # ``previous_draft``. ``response`` is the distinct projected API result.
    Column("planner_state", JSONB, nullable=True),
    Column("response", JSONB, nullable=True),
    Column("part", JSONB, nullable=True),
    Column("suggestions", JSONB, nullable=False),
    Column("status", Text, nullable=False),  # pending|completed|failed
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("project_id", "client_turn_id", name="uq_ptr_project_client_turn"),
    UniqueConstraint("project_id", "turn_index", name="uq_ptr_project_turn_index"),
    CheckConstraint(
        "status IN ('pending', 'completed', 'failed')", name="ck_ptr_status"
    ),
    CheckConstraint("jsonb_typeof(suggestions) = 'array'", name="ck_ptr_suggestions_array"),
)

# --- Capability run (task 024) ---
#
# The steering-surface walk entity (contract decision 2): one row per
# orchestrated capability walk (v1: 'evidence_base' only), carrying the
# approved plan identity at walk open and the walk's terminal status.
# `runs.capability_run_id` (nullable, MATCH SIMPLE) attributes each
# component run to the walk it executed within. Deliberately not modelled:
# composition fields, artefact back-refs (derivable), turn tables (025).

capability_run = Table(
    "capability_run",
    metadata,
    Column("capability_run_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("project.project_id"), nullable=False),
    Column("evidence_scope_id", UUID(as_uuid=True), nullable=False),
    Column("capability", Text, nullable=False),
    # The approved plan identity at walk open.
    Column("plan_id", UUID(as_uuid=True), nullable=False),
    Column("plan_version", Integer, nullable=False),
    Column(
        "status",
        Text,
        nullable=False,
    ),  # running|paused → succeeded/degraded/failed/aborted/interrupted
    Column("session_id", UUID(as_uuid=True), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    # Cross-project FK guard, per the selection-result precedent.
    ForeignKeyConstraint(
        ["evidence_scope_id", "project_id"],
        ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
        name="fk_capr_scope_project",
    ),
    # Composite-FK target for runs.capability_run_id.
    UniqueConstraint("capability_run_id", "project_id", name="uq_capr_id_project"),
    CheckConstraint("capability IN ('evidence_base')", name="ck_capr_capability"),
    CheckConstraint(
        "status IN ('running', 'paused', 'succeeded', 'degraded', 'failed', "
        "'aborted', 'interrupted')",
        name="ck_capr_status",
    ),
)

chat_turn = Table(
    "chat_turn",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("conversation_id", UUID(as_uuid=True), ForeignKey("conversation.id"), nullable=False),
    Column("turn_index", Integer, nullable=False),
    Column("client_turn_id", UUID(as_uuid=True), nullable=False),
    Column("user_message", Text, nullable=False),
    Column("answer", Text, nullable=True),
    Column("answer_payload", JSONB, nullable=True),
    Column(
        "capability_run_id",
        UUID(as_uuid=True),
        ForeignKey("capability_run.capability_run_id"),
        nullable=True,
    ),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("conversation_id", "turn_index", name="uq_chat_turn_conv_index"),
    UniqueConstraint("conversation_id", "client_turn_id", name="uq_chat_turn_conv_client"),
    CheckConstraint(
        "status IN ('pending', 'completed', 'failed', 'cancelled')",
        name="ck_chat_turn_status",
    ),
)
