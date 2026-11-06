"""task 054 theory of change, iteration 3 step 2 — six layers and short codes

Contract § Iteration 3, decisions C34 and C35.

Upgrade
    ``toc_box.layer``  the single ``outcome`` layer splits into
                       ``outcome_short`` and ``outcome_long`` (the Magenta
                       Book's short-term and long-term outcomes). Stored
                       ``outcome`` boxes become ``outcome_short``, and
                       ``ck_toc_box_layer`` allows the six new values.
    ``toc_box.code``   a short, stable label shown on the canvas: a layer
                       letter and a number (``A1`` inputs and activities,
                       ``P1`` outputs, ``S1`` short-term, ``L1`` long-term,
                       ``I1`` impact, ``F1`` failure outcome).
    ``toc_link.code``  ``#1``, ``#2``, ... per task.
    Both code columns are nullable. Existing rows are numbered per task (and
    per layer for boxes) in creation order. New rows get their code from
    ``theory_of_change.store.insert``.

Downgrade
    Drops both code columns and maps both outcome layers back to ``outcome``.
    Not lossless: which outcomes were long-term is forgotten.

Revision ID: 80f4e6c430b0
Revises: 9127f849697f
Create Date: 2026-10-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "80f4e6c430b0"
down_revision: str | Sequence[str] | None = "9127f849697f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_LAYERS = (
    "layer IN ('input', 'output', 'outcome_short', 'outcome_long', 'impact', 'failure_outcome')"
)
_OLD_LAYERS = "layer IN ('input', 'output', 'outcome', 'impact', 'failure_outcome')"


def upgrade() -> None:
    """Split the outcome layer, add the code columns and number existing rows."""
    op.drop_constraint("ck_toc_box_layer", "toc_box", type_="check")
    op.execute("UPDATE toc_box SET layer = 'outcome_short' WHERE layer = 'outcome'")
    op.create_check_constraint("ck_toc_box_layer", "toc_box", _NEW_LAYERS)
    op.add_column("toc_box", sa.Column("code", sa.Text(), nullable=True))
    op.add_column("toc_link", sa.Column("code", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE toc_box b SET code = n.prefix || n.number
        FROM (
            SELECT box_id,
                   CASE layer WHEN 'input' THEN 'A' WHEN 'output' THEN 'P'
                              WHEN 'outcome_short' THEN 'S' WHEN 'outcome_long' THEN 'L'
                              WHEN 'impact' THEN 'I' ELSE 'F' END AS prefix,
                   row_number() OVER (
                       PARTITION BY task_id, layer ORDER BY created_at, box_id
                   ) AS number
            FROM toc_box
        ) n
        WHERE b.box_id = n.box_id
        """
    )
    op.execute(
        """
        UPDATE toc_link l SET code = '#' || n.number
        FROM (
            SELECT link_id,
                   row_number() OVER (PARTITION BY task_id ORDER BY created_at, link_id) AS number
            FROM toc_link
        ) n
        WHERE l.link_id = n.link_id
        """
    )


def downgrade() -> None:
    """Drop the codes and fold both outcome layers back into ``outcome``."""
    op.drop_column("toc_link", "code")
    op.drop_column("toc_box", "code")
    op.drop_constraint("ck_toc_box_layer", "toc_box", type_="check")
    op.execute(
        "UPDATE toc_box SET layer = 'outcome' WHERE layer IN ('outcome_short', 'outcome_long')"
    )
    op.create_check_constraint("ck_toc_box_layer", "toc_box", _OLD_LAYERS)
