"""Keep file identifiers and rename paths in the operation history."""

from alembic import op
import sqlalchemy as sa


revision = '3ac48ec46e12'
down_revision = '15ab933da01a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE operation_type ADD VALUE IF NOT EXISTS 'read'")
    op.add_column('operations', sa.Column('file_id_snapshot', sa.Integer()))
    op.add_column('operations', sa.Column('previous_path', sa.String(length=1024)))
    op.execute('UPDATE operations SET file_id_snapshot = file_id')


def downgrade() -> None:
    op.drop_column('operations', 'previous_path')
    op.drop_column('operations', 'file_id_snapshot')
    # The initial migration already declares the read value.
