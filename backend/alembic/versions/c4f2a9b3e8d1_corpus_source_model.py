"""corpus source model

Revision ID: c4f2a9b3e8d1
Revises: 68afc1c2def1
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c4f2a9b3e8d1'
down_revision: Union[str, Sequence[str], None] = '68afc1c2def1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('source_snapshot',
        sa.Column('source_snapshot_id', sa.UUID(), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('text_basis', sa.Text(), nullable=False),
        sa.Column('source_locator', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('source_snapshot_id'),
    )
    op.create_table('project_source_snapshot',
        sa.Column('project_source_snapshot_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('source_snapshot_id', sa.UUID(), nullable=False),
        sa.Column('origin', sa.Text(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], ),
        sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], ),
        sa.ForeignKeyConstraint(['source_snapshot_id'], ['source_snapshot.source_snapshot_id'], ),
        sa.PrimaryKeyConstraint('project_source_snapshot_id'),
        sa.UniqueConstraint('project_id', 'source_snapshot_id', name='uq_project_source_snapshot'),
    )
    op.create_table('chunk',
        sa.Column('chunk_id', sa.UUID(), nullable=False),
        sa.Column('source_snapshot_id', sa.UUID(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('locator', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('segmentation_policy', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_snapshot_id'], ['source_snapshot.source_snapshot_id'], ),
        sa.PrimaryKeyConstraint('chunk_id'),
        sa.UniqueConstraint('source_snapshot_id', 'sequence', name='uq_chunk_snapshot_sequence'),
    )
    op.create_table('citation',
        sa.Column('citation_id', sa.UUID(), nullable=False),
        sa.Column('annotation_id', sa.UUID(), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=False),
        sa.Column('quote', sa.Text(), nullable=False),
        sa.Column('verification_result', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['annotation_id'], ['annotation.annotation_id'], ),
        sa.ForeignKeyConstraint(['chunk_id'], ['chunk.chunk_id'], ),
        sa.PrimaryKeyConstraint('citation_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('citation')
    op.drop_table('chunk')
    op.drop_table('project_source_snapshot')
    op.drop_table('source_snapshot')
