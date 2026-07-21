"""stop_condition grain widen + is_retracted screening exclusion

Task 019 Phase D (owner-approved gate decisions 2026-07-12, one migration file
riding both decisions, no new tables — count stays 26):

1. ``ck_scov_stop_condition`` widens to admit ``'completed'`` (the honest
   clean-completion stop, replacing ``breadth_truncated`` as the value acquire
   writes going forward) and ``'wall_clock_exceeded'`` (the rapid/standard
   fan-out's own wall-clock breach, mirroring the deep loop's
   ``budget_exhausted``). ``breadth_truncated`` stays IN the vocabulary —
   historical rows before this migration carry it, and it is never dropped
   from a widening CHECK — but acquire no longer writes it.
2. ``ck_ssr_status`` widens to admit ``'excluded_retracted'`` — a retracted
   document (OpenAlex ``is_retracted``) is excluded at screening as a
   distinct, visible status, never conflated with a ``not_relevant``
   relevance verdict (don't-flatten-status, owner decision).

Revision ID: 921d3a781f3f
Revises: 64ff33416d1a
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "921d3a781f3f"
down_revision: Union[str, None] = "64ff33416d1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCOV_WIDENED = (
    "stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error',"
    " 'short_circuit', 'budget_exhausted', 'target_reached', 'completed',"
    " 'wall_clock_exceeded')"
)
_SCOV_ORIGINAL = (
    "stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error',"
    " 'short_circuit', 'budget_exhausted', 'target_reached')"
)

_SSR_WIDENED = "status IN ('relevant', 'not_relevant', 'failed', 'excluded_retracted')"
_SSR_ORIGINAL = "status IN ('relevant', 'not_relevant', 'failed')"


def upgrade() -> None:
    op.drop_constraint("ck_scov_stop_condition", "search_coverage_record", type_="check")
    op.create_check_constraint(
        "ck_scov_stop_condition",
        "search_coverage_record",
        _SCOV_WIDENED,
    )

    op.drop_constraint("ck_ssr_status", "source_screening_result", type_="check")
    op.create_check_constraint(
        "ck_ssr_status",
        "source_screening_result",
        _SSR_WIDENED,
    )


def downgrade() -> None:
    # Restoring the narrow constraints requires no rows carrying the new
    # values; Postgres validates existing rows against a CHECK by default at
    # creation time, so a corpus that has run post-widen acquire/screen must
    # prune or rewrite those rows before downgrading — the same convention as
    # the 015 stop_condition widen (c9e4b7f2d1a8): this downgrade fails loudly
    # via the database's own constraint validation rather than converting
    # rows silently.
    op.drop_constraint("ck_ssr_status", "source_screening_result", type_="check")
    op.create_check_constraint(
        "ck_ssr_status",
        "source_screening_result",
        _SSR_ORIGINAL,
    )

    op.drop_constraint("ck_scov_stop_condition", "search_coverage_record", type_="check")
    op.create_check_constraint(
        "ck_scov_stop_condition",
        "search_coverage_record",
        _SCOV_ORIGINAL,
    )
