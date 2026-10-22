from sqlalchemy import (
    String,
    UniqueConstraint,
    BigInteger,
    ForeignKey
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from .base import Base


class File(Base):
    __tablename__ = 'files'
    __table_args__ = (UniqueConstraint('owner_id', 'location'),)

    filename: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(1024))
    size: Mapped[int] = mapped_column(BigInteger)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE')
    )
