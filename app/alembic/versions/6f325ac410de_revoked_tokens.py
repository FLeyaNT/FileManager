"""Store revoked access token identifiers until they expire."""

import sqlalchemy as sa
from alembic import op


revision = '6f325ac410de'
down_revision = '4b96a2fc831d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'revoked_tokens',
        sa.Column('jti', sa.Uuid(), primary_key=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])


def downgrade() -> None:
    op.drop_table('revoked_tokens')
