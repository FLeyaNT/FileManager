"""Catalog user directories and remove paths from the file audit."""

import stat
from collections.abc import Iterator
from os import scandir
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from app.core.exceptions import UnsafePathError
from app.utils.paths import MAX_DEPTH, reject_link, validate_name
from src.app.core.config import settings


revision = '75e9a3b4f201'
down_revision = '85c9410b7d2a'
branch_labels = None
depends_on = None


def _existing_directories(root: Path) -> Iterator[tuple[str, ...]]:
    try:
        info = root.lstat()
        reject_link(info)
    except (FileNotFoundError, UnsafePathError):
        return
    if not stat.S_ISDIR(info.st_mode):
        return

    pending: list[tuple[str, ...]] = [()]
    while pending:
        parts = pending.pop()
        if len(parts) >= MAX_DEPTH:
            continue
        with scandir(root.joinpath(*parts)) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    continue
                try:
                    validate_name(entry.name)
                    reject_link(info)
                except UnsafePathError:
                    continue
                child = (*parts, entry.name)
                pending.append(child)
                yield child


def _backfill_directories(bind: Connection) -> None:
    roots = bind.execute(sa.text("""
        INSERT INTO directories (owner_id, name)
        SELECT id, '' FROM users
        RETURNING owner_id, id
    """)).tuples().all()
    ids = {(owner, ()): directory for owner, directory in roots}
    insert_directory = sa.text("""
        INSERT INTO directories (owner_id, parent_id, name)
        VALUES (:owner, :parent, :name) RETURNING id
    """)

    def ensure(owner: int, parts: tuple[str, ...]) -> int:
        for level, name in enumerate(parts, start=1):
            key = (owner, parts[:level])
            if key not in ids:
                ids[key] = bind.execute(insert_directory, {
                    'owner': owner, 'parent': ids[(owner, parts[:level - 1])], 'name': name,
                }).scalar_one()
        return ids[(owner, parts)]

    update_file = sa.text('UPDATE files SET directory_id = :directory, filename = :name WHERE id = :id')
    legacy_files = bind.execute(sa.text('SELECT id, owner_id, location FROM files')).tuples().all()
    for file_id, owner_id, location in legacy_files:
        *parent, filename = location.split('/')
        for name in (*parent, filename):
            validate_name(name)
        directory = ensure(owner_id, tuple(parent))
        bind.execute(update_file, {'directory': directory, 'name': filename, 'id': file_id})

    storage_root = settings.storage_root.resolve()
    for owner_id, _ in roots:
        user_root = storage_root / str(owner_id)
        try:
            for parts in _existing_directories(user_root):
                ensure(owner_id, parts)
        except PermissionError as exc:
            raise RuntimeError(
                f'Cannot list existing directories under {user_root}. '
                'Run Alembic with permission to read the personal storage directories.'
            ) from exc


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError('Run this migration against PostgreSQL with the storage directory available.')

    op.create_table(
        'directories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_id', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('owner_id', 'id'),
        sa.UniqueConstraint('parent_id', 'name'),
        sa.ForeignKeyConstraint(
            ('owner_id', 'parent_id'), ('directories.owner_id', 'directories.id'),
            name='fk_directories_owner_parent', ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            "(parent_id IS NULL AND name = '') OR "
            "(parent_id IS NOT NULL AND parent_id <> id AND name <> '')",
            name='root_or_child',
        ),
    )
    op.create_index('ix_directories_id', 'directories', ['id'])
    op.create_index('uq_directories_owner_root', 'directories', ['owner_id'], unique=True,
                    postgresql_where=sa.text('parent_id IS NULL'))
    op.add_column('files', sa.Column('directory_id', sa.Integer()))
    _backfill_directories(op.get_bind())
    op.alter_column('files', 'directory_id', nullable=False)
    op.create_foreign_key('fk_files_owner_directory', 'files', 'directories',
                          ['owner_id', 'directory_id'], ['owner_id', 'id'])
    op.create_unique_constraint('uq_files_directory_id_filename', 'files', ['directory_id', 'filename'])
    op.drop_constraint('uq_files_owner_id_location', 'files', type_='unique')
    op.drop_column('files', 'location')
    op.drop_column('operations', 'previous_path')
    op.drop_column('operations', 'path')


def downgrade() -> None:
    op.add_column('files', sa.Column('location', sa.String(1024)))
    op.execute("""
        WITH RECURSIVE tree AS (
            SELECT id, owner_id, ''::text AS path FROM directories WHERE parent_id IS NULL
            UNION ALL
            SELECT child.id, child.owner_id, concat_ws('/', nullif(tree.path, ''), child.name)
            FROM directories AS child
            JOIN tree ON child.parent_id = tree.id AND child.owner_id = tree.owner_id
        )
        UPDATE files
        SET location = concat_ws('/', nullif(tree.path, ''), files.filename)
        FROM tree WHERE files.directory_id = tree.id AND files.owner_id = tree.owner_id
    """)
    op.alter_column('files', 'location', nullable=False)
    op.create_unique_constraint('uq_files_owner_id_location', 'files', ['owner_id', 'location'])
    op.drop_constraint('uq_files_directory_id_filename', 'files', type_='unique')
    op.drop_constraint('fk_files_owner_directory', 'files', type_='foreignkey')
    op.drop_column('files', 'directory_id')
    op.drop_table('directories')
    # Paths from earlier audit entries cannot be recovered from the current tree.
    op.add_column('operations', sa.Column('path', sa.String(1024)))
    op.add_column('operations', sa.Column('previous_path', sa.String(1024)))
