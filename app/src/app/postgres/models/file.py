from sqlalchemy import (
    String,
    UniqueConstraint,
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from .base import Base


class File(Base):
    __tablename__ = 'files'
    __table_args__ = (
        UniqueConstraint('directory_id', 'filename'),
        ForeignKeyConstraint(
            ('owner_id', 'directory_id'), ('directories.owner_id', 'directories.id'),
            name='fk_files_owner_directory',
            ondelete='CASCADE',
        ),
    )

    filename: Mapped[str] = mapped_column(String(255))
    directory_id: Mapped[int] = mapped_column(
        ForeignKey('directories.id', ondelete='CASCADE')
    )
    size: Mapped[int] = mapped_column(BigInteger)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE')
    )
