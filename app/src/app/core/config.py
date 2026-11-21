import logging
from pathlib import Path
from typing import Literal

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict
)
from pydantic import BaseModel, Field

from .constants import LOG_DEFAULT_FORMAT


class LoggingConfig(BaseModel):
    log_level: Literal[
        'debug',
        'info',
        'warning',
        'error',
        'critical',
    ] = 'debug'
    log_format: str = LOG_DEFAULT_FORMAT

    @property
    def log_level_value(self):
        return logging.getLevelNamesMapping()[
            self.log_level.upper()
        ]

class RunConfig(BaseModel):
    host: str = 'localhost'
    port: int = 8000
    reload: bool = True


class FastAPIConfig(BaseModel):
    title: str = 'File Manager API'


class PostgresConfig(BaseModel):
    host: str = 'localhost'
    port: int = 5432
    db: str
    user: str
    password: str

    @property
    def async_database_url(self) -> str:
        return (
            f'postgresql+asyncpg://'
            f'{self.user}:{self.password}@{self.host}:'
            f'{self.port}/{self.db}'
        )


class JWTConfig(BaseModel):
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = 'HS256'
    access_token_ttl_minutes: int = 30
    revoked_cleanup_interval_seconds: int = Field(default=300, gt=0)


class FilesConfig(BaseModel):
    max_file_size: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
    )

    max_request_size: int = Field(
        default=12 * 1024 * 1024,
        gt=0,
    )

    max_user_size: int = Field(
        default=1 * 1024 * 1024,
        gt=0,
    )

    max_user_entries: int = Field(
        default=1_000,
        gt=0,
    )

    chunk_size: int = Field(
        default=64 * 1024,
        gt=0,
    )

    zip_max_entries: int = 1_000
    zip_max_total_size: int = 100 * 1024 * 1024
    zip_max_ratio: int = 100


class CookieConfig(BaseModel):
    name: str = 'access_token'
    secure: bool = False
    samesite: Literal[
        "lax",
        "strict",
        "none"
    ] = "strict"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_nested_delimiter='__',
        env_file='.env',
        extra='ignore'
    )

    run: RunConfig = RunConfig()
    fastapi: FastAPIConfig = FastAPIConfig()
    logging: LoggingConfig = LoggingConfig()
    files: FilesConfig = FilesConfig()
    cookie: CookieConfig = CookieConfig()
    postgres: PostgresConfig
    jwt: JWTConfig

    allowed_origins: list[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    storage_root: Path


settings = Settings() # type: ignore[call-arg]
