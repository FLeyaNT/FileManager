from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Directory(Base):
    __tablename__ = 'directories'
    __table_args__ = (
        UniqueConstraint('owner_id', 'id'),
        UniqueConstraint('parent_id', 'name'),
        ForeignKeyConstraint(
            ('owner_id', 'parent_id'), ('directories.owner_id', 'directories.id'),
            name='fk_directories_owner_parent', ondelete='CASCADE',
        ),
        CheckConstraint(
            "(parent_id IS NULL AND name = '') OR "
            "(parent_id IS NOT NULL AND parent_id <> id AND name <> '')",
            name='root_or_child',
        ),
        Index('uq_directories_owner_root', 'owner_id', unique=True,
              postgresql_where=text('parent_id IS NULL')),
    )

    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey('directories.id', ondelete='CASCADE')
    )
