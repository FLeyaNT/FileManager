"""Add the explicit cascading directory parent foreign key."""

from alembic import op


revision = '4b96a2fc831d'
down_revision = '9d02c31f7be4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        'fk_directories_parent_id_directories', 'directories', 'directories',
        ['parent_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_directories_parent_id_directories', 'directories', type_='foreignkey')
