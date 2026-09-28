"""task 046 intervention profile tags — three nullable text columns

The slice's one revision (plan S5, PA14; contract § Constraints, Schema).
Additive only: no existing row changes value, and a record written before
this revision reads back with null tags ("not tagged").

Upgrade
    ``intervention_profile_record.population_tag``  nullable text, closed to
                                                    ``on_target``, ``adjacent``,
                                                    ``other`` (``ck_ipr_population_tag``).
    ``intervention_profile_record.outcome_tag``     nullable free text (a plan
                                                    outcome's text, or ``other``).
    ``intervention_profile_record.object_tag``      nullable text, closed to
                                                    ``plan_object``, ``option``,
                                                    ``neither`` (``ck_ipr_object_tag``).

    ``finding_reference_union`` is not touched: it projects the shared
    reference columns by name, never these.

Downgrade
    Drops the two check constraints, then the three columns. The tags are
    lost; nothing else references them.

Revision ID: d8f3b6a2c4e1
Revises: c7e2a9f4b1d8
Create Date: 2026-09-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8f3b6a2c4e1"
down_revision: Union[str, None] = "c7e2a9f4b1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "intervention_profile_record"

# Frozen here, not imported: the revision must keep meaning what it meant
# whatever ``schema.py`` says later.
_POPULATION_TAGS = "('on_target', 'adjacent', 'other')"
_OBJECT_TAGS = "('plan_object', 'option', 'neither')"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("population_tag", sa.Text(), nullable=True))
    op.add_column(_TABLE, sa.Column("outcome_tag", sa.Text(), nullable=True))
    op.add_column(_TABLE, sa.Column("object_tag", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_ipr_population_tag",
        _TABLE,
        f"population_tag IS NULL OR population_tag IN {_POPULATION_TAGS}",
    )
    op.create_check_constraint(
        "ck_ipr_object_tag",
        _TABLE,
        f"object_tag IS NULL OR object_tag IN {_OBJECT_TAGS}",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ipr_object_tag", _TABLE, type_="check")
    op.drop_constraint("ck_ipr_population_tag", _TABLE, type_="check")
    op.drop_column(_TABLE, "object_tag")
    op.drop_column(_TABLE, "outcome_tag")
    op.drop_column(_TABLE, "population_tag")
