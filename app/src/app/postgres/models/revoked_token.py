from sqlalchemy import Column, DateTime, Table, Uuid

from .base import Base


revoked_tokens = Table(
    'revoked_tokens',
    Base.metadata,
    Column('jti', Uuid(), primary_key=True),
    Column('expires_at', DateTime(timezone=True), nullable=False, index=True),
)
