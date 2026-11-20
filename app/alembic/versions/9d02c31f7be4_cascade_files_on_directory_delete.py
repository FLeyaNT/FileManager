"""Cascade file metadata when its directory is deleted."""

from alembic import op


revision = '9d02c31f7be4'
down_revision = '75e9a3b4f201'
branch_labels = None
depends_on = None


def _replace_owner_constraint(ondelete: str | None) -> None:
    op.drop_constraint('fk_files_owner_directory', 'files', type_='foreignkey')
    op.create_foreign_key(
        'fk_files_owner_directory', 'files', 'directories',
        ['owner_id', 'directory_id'], ['owner_id', 'id'], ondelete=ondelete,
    )


def upgrade() -> None:
    _replace_owner_constraint('CASCADE')
    op.create_foreign_key(
        'fk_files_directory_id_directories', 'files', 'directories',
        ['directory_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_files_directory_id_directories', 'files', type_='foreignkey')
    _replace_owner_constraint(None)
