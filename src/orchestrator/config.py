"""
Application configuration using Pydantic Settings.

Loads configuration from environment variables with validation and type checking.
"""

from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: PostgresDsn = Field(  # type: ignore[assignment]
        default="postgresql+asyncpg://orchestrator:password@localhost:5432/orchestrator",
        description="PostgreSQL connection URL with asyncpg driver",
    )
    db_pool_size: int = Field(
        default=5,
        ge=1,
        description="Database connection pool size",
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        description="Maximum overflow connections beyond pool_size",
    )
    db_pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Timeout in seconds for getting connection from pool",
    )
    db_pool_recycle: int = Field(
        default=3600,
        ge=-1,
        description="Recycle connections after this many seconds (-1 to disable)",
    )

    # Temporal Configuration
    temporal_host: str = Field(
        default="localhost:7233",
        description="Temporal server host and port",
    )
    temporal_namespace: str = Field(
        default="default",
        description="Temporal namespace",
    )
    temporal_task_queue: str = Field(
        default="orchestrator-tasks",
        description="Temporal task queue name",
    )

    # OpenStack Configuration
    openstack_auth_url: str = Field(
        default="http://localhost:5000/v3",
        description="OpenStack Keystone authentication URL",
    )
    openstack_username: str = Field(
        default="admin",
        description="OpenStack username",
    )
    openstack_password: str = Field(
        default="secret",
        description="OpenStack password",
    )
    openstack_project_name: str = Field(
        default="admin",
        description="OpenStack project name",
    )
    openstack_project_domain_name: str = Field(
        default="Default",
        description="OpenStack project domain name",
    )
    openstack_user_domain_name: str = Field(
        default="Default",
        description="OpenStack user domain name",
    )
    openstack_region_name: str = Field(
        default="RegionOne",
        description="OpenStack region name",
    )

    # API Configuration
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host",
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API server port",
    )
    api_workers: int = Field(
        default=4,
        ge=1,
        description="Number of API workers",
    )
    api_reload: bool = Field(
        default=False,
        description="Enable auto-reload for development",
    )

    # Security Configuration
    api_keys: str = Field(
        default="dev-key-1:write,dev-key-2:read",
        description="Comma-separated API keys with permissions (key:permission)",
    )
    secret_key: str = Field(
        default="change-this-in-production-to-a-secure-random-string",
        min_length=32,
        description="Secret key for signing tokens",
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Log level",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log format (json or text)",
    )

    # Caching (Optional)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        ge=0,
        description="Cache TTL in seconds",
    )

    # Monitoring (Optional)
    prometheus_port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Prometheus metrics port",
    )
    sentry_dsn: str = Field(
        default="",
        description="Sentry DSN for error tracking",
    )

    # Ansible Configuration (Optional)
    ansible_ssh_key_path: str = Field(
        default="/keys/ansible_rsa",
        description="Path to Ansible SSH private key",
    )
    ansible_verbosity: int = Field(
        default=0,
        ge=0,
        le=4,
        description="Ansible verbosity level (0-4)",
    )

    # Development Settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    @field_validator("api_keys")
    @classmethod
    def validate_api_keys(cls, v: str) -> str:
        """Validate API keys format."""
        if not v:
            raise ValueError("At least one API key must be configured")

        for key_permission in v.split(","):
            parts = key_permission.split(":")
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid API key format: {key_permission}. Expected format: key:permission"
                )
            key, permission = parts
            if not key.strip():
                raise ValueError("API key cannot be empty")
            if permission.strip() not in ("read", "write"):
                raise ValueError(f"Invalid permission: {permission}. Must be 'read' or 'write'")

        return v

    @property
    def parsed_api_keys(self) -> dict[str, str]:
        """Parse API keys into a dictionary."""
        result = {}
        for key_permission in self.api_keys.split(","):
            key, permission = key_permission.split(":")
            result[key.strip()] = permission.strip()
        return result


# Global settings instance
settings = Settings()
