"""Limit the audit enum to file operations."""

from alembic import op
from sqlalchemy.dialects import postgresql


revision = '85c9410b7d2a'
down_revision = '3ac48ec46e12'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    old_type = postgresql.ENUM(name='operation_type_old')
    file_operations = postgresql.ENUM(
        'create', 'read', 'modify', 'delete', 'archive', 'extract',
        name='operation_type',
    )

    op.execute('ALTER TYPE operation_type RENAME TO operation_type_old')
    file_operations.create(bind, checkfirst=False)
    # If an older deployment contains login entries, the cast fails and preserves them.
    op.alter_column(
        'operations',
        'operation_type',
        type_=file_operations,
        postgresql_using='operation_type::text::operation_type',
    )
    old_type.drop(bind, checkfirst=False)


def downgrade() -> None:
    op.execute("ALTER TYPE operation_type ADD VALUE 'login' BEFORE 'create'")
