"""
Hermes Configuration

Application settings loaded from environment variables.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Hermes"
    app_version: str = "0.1.0"
    app_url: str = Field(
        default="https://hermes.bravozero.ai",
        description="Public URL of the application",
    )
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    grpc_port: int = 50051
    workers: int = 4

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://hermes:hermes@localhost:5432/hermes",
        description="PostgreSQL connection URL",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_ttl: int = 3600  # 1 hour default cache TTL

    # Elasticsearch
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch URL",
    )
    elasticsearch_index: str = "hermes-prompts"

    # PERSONA Auth
    persona_url: str = Field(
        default="https://persona.bravozero.ai",
        description="PERSONA authentication service URL",
    )
    persona_client_id: str = Field(default="hermes", description="OAuth2 client ID")
    persona_client_secret: str = Field(default="", description="OAuth2 client secret")
    jwt_algorithm: str = "RS256"
    jwt_audience: str = "hermes"

    # ATE Integration
    ate_grpc_url: str = Field(
        default="localhost:50052",
        description="ATE benchmark service gRPC URL",
    )
    ate_enabled: bool = True

    # ASRBS Integration
    asrbs_grpc_url: str = Field(
        default="localhost:50053",
        description="ASRBS critique service gRPC URL",
    )
    asrbs_enabled: bool = True

    # Beeper Integration
    beeper_url: str = Field(
        default="https://beeper.bravozero.ai",
        description="Beeper notification service URL",
    )
    beeper_api_key: str = Field(default="", description="Beeper API key")
    beeper_enabled: bool = True

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://hermes.bravozero.ai",
        "https://hydra.bravozero.ai",
    ]

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
