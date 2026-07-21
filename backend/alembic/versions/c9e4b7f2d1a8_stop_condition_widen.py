"""stop_condition CHECK widening for depth-graded search

Task 015 (approved gated change 2): one migration, one change, no new
tables (count stays 25):

``ck_scov_stop_condition`` widens to admit ``'short_circuit'``,
``'budget_exhausted'`` and ``'target_reached'`` — the deep loop's stop
vocabulary (contract decisions 15/17; rev 3.14 added ``target_reached``
as the loop's honest successful exit). Existing three values stand;
``'saturated'`` stays out per spec (corpus saturation is a deferred seam,
distinct from within-run yield collapse).

Revision ID: c9e4b7f2d1a8
Revises: e5c2a7f4b9d1
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e4b7f2d1a8"
down_revision: Union[str, None] = "e5c2a7f4b9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WIDENED = (
    "stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error',"
    " 'short_circuit', 'budget_exhausted', 'target_reached')"
)
_ORIGINAL = "stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error')"


def upgrade() -> None:
    op.drop_constraint("ck_scov_stop_condition", "search_coverage_record", type_="check")
    op.create_check_constraint(
        "ck_scov_stop_condition",
        "search_coverage_record",
        _WIDENED,
    )


def downgrade() -> None:
    # Restoring the narrow constraint requires no rows carrying the loop's stop
    # values; a corpus that has run deep search must prune or rewrite those
    # coverage records before downgrading.
    op.drop_constraint("ck_scov_stop_condition", "search_coverage_record", type_="check")
    op.create_check_constraint(
        "ck_scov_stop_condition",
        "search_coverage_record",
        _ORIGINAL,
    )
