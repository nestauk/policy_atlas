"""effect_direction vocabulary rename

Renames the ``intervention_outcome_finding.effect_direction`` vocabulary
(task 018 rider A5, approved schema migration): 'positive' -> 'increase',
'negative' -> 'decrease'. 'no_effect', 'mixed' and 'unclear' are unchanged.
Pure vocabulary rename — no shape change. Neither the old nor the new
constraint ever admits both vocabularies at once, so the constraint is
dropped first in both directions: the in-flight UPDATE then runs with no
CHECK in place to reject the transitional value, and the replacement
constraint (validated against every row at creation) is only added once
every row already carries the target vocabulary.

Revision ID: 64ff33416d1a
Revises: d2f8a4c1e9b7
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64ff33416d1a"
down_revision: Union[str, None] = "d2f8a4c1e9b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW = (
    "effect_direction IN ('increase', 'decrease', 'no_effect', 'mixed', 'unclear')"
)
_OLD = (
    "effect_direction IN ('positive', 'negative', 'no_effect', 'mixed', 'unclear')"
)


def upgrade() -> None:
    op.drop_constraint("ck_iof_direction", "intervention_outcome_finding", type_="check")
    op.execute(
        "UPDATE intervention_outcome_finding SET effect_direction = 'increase' "
        "WHERE effect_direction = 'positive'"
    )
    op.execute(
        "UPDATE intervention_outcome_finding SET effect_direction = 'decrease' "
        "WHERE effect_direction = 'negative'"
    )
    op.create_check_constraint(
        "ck_iof_direction",
        "intervention_outcome_finding",
        _NEW,
    )


def downgrade() -> None:
    op.drop_constraint("ck_iof_direction", "intervention_outcome_finding", type_="check")
    op.execute(
        "UPDATE intervention_outcome_finding SET effect_direction = 'positive' "
        "WHERE effect_direction = 'increase'"
    )
    op.execute(
        "UPDATE intervention_outcome_finding SET effect_direction = 'negative' "
        "WHERE effect_direction = 'decrease'"
    )
    op.create_check_constraint(
        "ck_iof_direction",
        "intervention_outcome_finding",
        _OLD,
    )
