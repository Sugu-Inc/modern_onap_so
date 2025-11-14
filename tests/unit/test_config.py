"""Tests for application configuration."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from orchestrator.config import Settings


class TestSettings:
    """Test suite for Settings class."""

    def test_settings_default_values(self) -> None:
        """Test that settings load with default values."""
        settings = Settings()

        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.temporal_host == "localhost:7233"
        assert settings.log_level == "INFO"
        assert settings.debug is False

    def test_settings_from_environment(self) -> None:
        """Test that settings load from environment variables."""
        env_vars = {
            "API_HOST": "127.0.0.1",
            "API_PORT": "9000",
            "LOG_LEVEL": "DEBUG",
            "DEBUG": "true",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.api_host == "127.0.0.1"
            assert settings.api_port == 9000
            assert settings.log_level == "DEBUG"
            assert settings.debug is True

    def test_api_port_validation(self) -> None:
        """Test API port validation."""
        # Valid port
        settings = Settings(api_port=8080)
        assert settings.api_port == 8080

        # Invalid port (too low)
        with pytest.raises(ValidationError) as exc_info:
            Settings(api_port=0)
        assert "greater than or equal to 1" in str(exc_info.value)

        # Invalid port (too high)
        with pytest.raises(ValidationError) as exc_info:
            Settings(api_port=70000)
        assert "less than or equal to 65535" in str(exc_info.value)

    def test_api_keys_validation(self) -> None:
        """Test API keys validation."""
        # Valid API keys
        settings = Settings(api_keys="key1:write,key2:read")
        assert settings.api_keys == "key1:write,key2:read"

        # Empty API keys
        with pytest.raises(ValidationError) as exc_info:
            Settings(api_keys="")
        assert "At least one API key must be configured" in str(exc_info.value)

        # Invalid format (missing colon)
        with pytest.raises(ValidationError) as exc_info:
            Settings(api_keys="key1-write")
        assert "Invalid API key format" in str(exc_info.value)

        # Invalid permission
        with pytest.raises(ValidationError) as exc_info:
            Settings(api_keys="key1:admin")
        assert "Invalid permission" in str(exc_info.value)

    def test_parsed_api_keys(self) -> None:
        """Test parsed API keys property."""
        settings = Settings(api_keys="key1:write,key2:read,key3:write")

        parsed = settings.parsed_api_keys
        assert parsed == {
            "key1": "write",
            "key2": "read",
            "key3": "write",
        }

    def test_secret_key_minimum_length(self) -> None:
        """Test secret key minimum length validation."""
        # Valid secret key
        settings = Settings(secret_key="a" * 32)
        assert len(settings.secret_key) == 32

        # Too short
        with pytest.raises(ValidationError) as exc_info:
            Settings(secret_key="short")
        assert "at least 32 characters" in str(exc_info.value)

    def test_log_level_validation(self) -> None:
        """Test log level validation."""
        # Valid log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(log_level=level)
            assert settings.log_level == level

        # Invalid log level
        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")

    def test_log_format_validation(self) -> None:
        """Test log format validation."""
        # Valid formats
        settings_json = Settings(log_format="json")
        assert settings_json.log_format == "json"

        settings_text = Settings(log_format="text")
        assert settings_text.log_format == "text"

        # Invalid format
        with pytest.raises(ValidationError):
            Settings(log_format="xml")

    def test_database_url_format(self) -> None:
        """Test database URL format."""
        # Valid PostgreSQL URL
        settings = Settings(database_url="postgresql+asyncpg://user:pass@localhost:5432/db")
        assert "postgresql+asyncpg://" in str(settings.database_url)

    def test_workers_validation(self) -> None:
        """Test workers validation."""
        # Valid worker count
        settings = Settings(api_workers=8)
        assert settings.api_workers == 8

        # Invalid (zero workers)
        with pytest.raises(ValidationError) as exc_info:
            Settings(api_workers=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_cache_ttl_validation(self) -> None:
        """Test cache TTL validation."""
        # Valid TTL
        settings = Settings(cache_ttl_seconds=600)
        assert settings.cache_ttl_seconds == 600

        # Zero TTL (valid - means no caching)
        settings_no_cache = Settings(cache_ttl_seconds=0)
        assert settings_no_cache.cache_ttl_seconds == 0

        # Negative TTL (invalid)
        with pytest.raises(ValidationError) as exc_info:
            Settings(cache_ttl_seconds=-1)
        assert "greater than or equal to 0" in str(exc_info.value)
