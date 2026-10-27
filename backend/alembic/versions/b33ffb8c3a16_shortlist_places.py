"""task 055 — the shortlist: an option's place, the proposal's note, a new purpose

The slice's one revision (contract § Constraints; plan P3; amendments A1, A15,
A22). Additive on the way up: every existing row reads as "no place" and "no
proposal yet".

Upgrade
    ``option.shortlist_state``      nullable text, checked by
                                    ``ck_option_shortlist_state`` against
                                    ``proposed`` · ``added_by_you`` ·
                                    ``set_aside``. NULL means the option holds
                                    no place on the shortlist.
    ``option.shortlist_reason``     nullable text: the one-line reason for a
                                    Policy Atlas pick.
    ``longlist_result.shortlist``   JSONB, NOT NULL, holding the latest
                                    proposal's note and provenance. Existing
                                    rows are filled with ``'{}'`` through a
                                    server default that is **kept** (unlike
                                    ``e9a4c1f7b3d2``): the longlist writer's
                                    insert does not name this column, so the
                                    database must fill it (plan PR1).
                                    ``schema.py`` carries the same default.
    ``evidence_scope.ck_scope_purpose``
                                    dropped and re-created with ``shortlist``
                                    added to the allowed purposes (A1).

Downgrade
    1. Every ``evidence_scope`` row with purpose ``shortlist`` has its purpose
       set to NULL, so the old check can come back.
    2. The old purpose check is restored.
    3. The three new columns are dropped (their values are lost; nothing else
       references them).
    4. ``risk_appetite`` is removed from every stored ``plan.payload``
       (``payload - 'risk_appetite'``). **This step loses data** (A15): the
       plan field has no column of its own — it lives inside the plan's JSON
       document — and the plan model before this slice refuses unknown keys,
       so the key must go. A user's chosen appetite is not recoverable after
       a downgrade; an upgrade again reads every plan as the default
       ``mostly_tried``.

Revision ID: b33ffb8c3a16
Revises: f1b6d3a8c2e5
Create Date: 2026-10-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b33ffb8c3a16"
down_revision: Union[str, None] = "f1b6d3a8c2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen here, not imported: each check must keep meaning what it meant at
# this revision, whatever ``schema.py`` says later.
_SHORTLIST_STATES = "('proposed', 'added_by_you', 'set_aside')"
_PURPOSES_BEFORE = "('baseline', 'longlist', 'variant', 'targeted')"
_PURPOSES_AFTER = "('baseline', 'longlist', 'variant', 'targeted', 'shortlist')"


def upgrade() -> None:
    op.add_column("option", sa.Column("shortlist_state", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_option_shortlist_state",
        "option",
        f"shortlist_state IN {_SHORTLIST_STATES}",
    )
    op.add_column("option", sa.Column("shortlist_reason", sa.Text(), nullable=True))
    op.add_column(
        "longlist_result",
        sa.Column(
            "shortlist",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.drop_constraint("ck_scope_purpose", "evidence_scope", type_="check")
    op.create_check_constraint(
        "ck_scope_purpose",
        "evidence_scope",
        f"purpose IN {_PURPOSES_AFTER}",
    )


def downgrade() -> None:
    op.execute("UPDATE evidence_scope SET purpose = NULL WHERE purpose = 'shortlist'")
    op.drop_constraint("ck_scope_purpose", "evidence_scope", type_="check")
    op.create_check_constraint(
        "ck_scope_purpose",
        "evidence_scope",
        f"purpose IN {_PURPOSES_BEFORE}",
    )
    op.drop_column("longlist_result", "shortlist")
    op.drop_constraint("ck_option_shortlist_state", "option", type_="check")
    op.drop_column("option", "shortlist_reason")
    op.drop_column("option", "shortlist_state")
    # Lossy for ``risk_appetite`` (A15): see the module docstring.
    op.execute(
        "UPDATE plan SET payload = payload - 'risk_appetite' WHERE payload ? 'risk_appetite'"
    )
