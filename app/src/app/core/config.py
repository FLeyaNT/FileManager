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

    @property
    def database_url(self) -> str:
        return (
            f'postgresql://'
            f'{self.user}:{self.password}@{self.host}:'
            f'{self.port}/{self.db}'
        )


class JWTConfig(BaseModel):
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = 'HS256'
    access_token_ttl_minutes: int = 30


class FilesConfig(BaseModel):
    max_file_size: int = 10 * 1024 * 1024
    zip_max_entries: int = 1_000
    zip_max_total_size: int = 100 * 1024 * 1024
    zip_max_ratio: int = 100


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
    postgres: PostgresConfig
    jwt: JWTConfig


settings = Settings() # type: ignore[call-arg]
