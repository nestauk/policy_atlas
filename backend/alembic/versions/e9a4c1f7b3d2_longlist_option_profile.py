"""task 046 amendment 2 option profile — one JSONB column on longlist_result

The amendment's one revision (amendment-2-final § 2.10; R45). Additive only:
a row written before this revision reads back ``{}`` ("no option profiled").

Upgrade
    ``longlist_result.option_profile``  JSONB, NOT NULL, keyed
                                        ``[option_id][design_version]`` as
                                        ``judgements`` is. Existing rows are
                                        filled with ``'{}'`` through a server
                                        default that is then dropped, so the
                                        table matches ``schema.py`` (no
                                        server default, as ``judgements``).

Downgrade
    Drops the column. The profiles are lost; nothing else references them.

Revision ID: e9a4c1f7b3d2
Revises: d8f3b6a2c4e1
Create Date: 2026-09-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9a4c1f7b3d2"
down_revision: Union[str, None] = "d8f3b6a2c4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "longlist_result"
_COLUMN = "option_profile"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column(_TABLE, _COLUMN, server_default=None)


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
