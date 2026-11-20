from sqlalchemy import (
    String,
    Text
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from .base import Base


class User(Base):
    __tablename__ = 'users'

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True
    )
    password_hash: Mapped[str] = mapped_column(Text)
