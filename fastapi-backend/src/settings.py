# src/settings.py
from __future__ import annotations

import json
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    # Application
    app_name: str = Field(default="cereon-linkedin-analyzer-api", env="APP_NAME")
    app_version: str = Field(default="0.1.0", env="APP_VERSION")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # CORS
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"], env="CORS_ALLOW_ORIGINS")
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"], env="CORS_ALLOW_HEADERS")
    cors_allow_credentials: bool = Field(default=False, env="CORS_ALLOW_CREDENTIALS")

    # Neo4j
    neo4j_uri: Optional[str] = Field(default=None, env="NEO4J_URI")
    neo4j_user: Optional[str] = Field(default=None, env="NEO4J_USER")
    neo4j_password: Optional[str] = Field(default=None, env="NEO4J_PASSWORD")
    neo4j_database: Optional[str] = Field(default=None, env="NEO4J_DATABASE")
    # Neo4j connection retry behavior
    neo4j_connect_attempts: int = Field(default=3, env="NEO4J_CONNECT_ATTEMPTS")
    neo4j_connect_backoff: float = Field(default=1.0, env="NEO4J_CONNECT_BACKOFF")

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: Optional[str] = Field(default=None, env="OPENAI_MODEL")

    # Celery
    celery_broker_url: Optional[str] = Field(default=None, env="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(default=None, env="CELERY_RESULT_BACKEND")
    celery_task_default_queue: str = Field(default="default", env="CELERY_TASK_DEFAULT_QUEUE")

    # Host / Port for serving the app
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    # Optional database url for pgvector/checkpointer
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file="../.env",  # Look for .env in parent directory
        env_file_encoding="utf-8",
        protected_namespaces=(),
        validate_default=True,
        extra="ignore",
    )

    @staticmethod
    def _parse_list(value: object) -> List[str]:
        """
        Accept JSON array, '*' literal, or comma-separated string.
        Always returns a list of stripped strings. Empty parts are discarded.
        """
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            s = value.strip()
            if s == "*":
                return ["*"]
            # JSON array if it looks like one
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    if not isinstance(parsed, list):
                        raise ValueError("Expected JSON array")
                    return [str(v).strip() for v in parsed if str(v).strip()]
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON array: {e}") from e
            # Fallback: CSV
            return [part.strip() for part in s.split(",") if part.strip()]
        # Anything else is invalid
        raise TypeError(f"Unsupported list value type: {type(value).__name__}")

    @field_validator(
        "cors_allow_origins",
        "cors_allow_methods",
        "cors_allow_headers",
        mode="before",
    )
    @classmethod
    def _lists_from_env(cls, v: object) -> List[str]:
        return cls._parse_list(v)

    @field_validator("log_level", mode="after")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        x = (v or "INFO").upper()
        # Align with standard levels
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if x not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(valid)}")
        return x


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
