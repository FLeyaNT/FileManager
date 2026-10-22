from sqlalchemy import (
    String,
    UniqueConstraint,
    BigInteger,
    ForeignKey,
    Enum
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from .base import Base
from .enums.operation_type import OperationType
from .enums.utils import enum_values


class Operation(Base):
    __tablename__ = 'operations'

    operation_type: Mapped[OperationType] = mapped_column(
        Enum(
            OperationType,
            name='operation_type',
            values_callable=enum_values
        )
    )
    path: Mapped[str | None] = mapped_column(String(1024))
    file_id: Mapped[int | None] = mapped_column(
        ForeignKey('files.id', ondelete='SET NULL')
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'),
        index=True
    )
