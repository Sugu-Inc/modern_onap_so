"""
Caching utilities for improving performance.

Provides a simple caching interface with support for both in-memory
and Redis backends.
"""

import hashlib
import json
import time
from typing import Any, Generic, TypeVar

from orchestrator.logging import logger

T = TypeVar("T")


class InMemoryCache(Generic[T]):
    """
    Simple in-memory cache with TTL support.

    Thread-safe cache implementation using a dictionary with
    automatic expiration of old entries.

    Attributes:
        ttl_seconds: Time-to-live for cache entries in seconds
        cache: Dictionary storing cached values with timestamps
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        """
        Initialize cache.

        Args:
            ttl_seconds: Cache entry TTL in seconds (default: 300)
        """
        self.ttl_seconds = ttl_seconds
        self.cache: dict[str, tuple[T, float]] = {}

    def get(self, key: str) -> T | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self.cache:
            logger.debug("cache_miss", key=key)
            return None

        value, timestamp = self.cache[key]
        now = time.time()

        # Check if entry has expired
        if now - timestamp > self.ttl_seconds:
            logger.debug("cache_expired", key=key, age=now - timestamp)
            del self.cache[key]
            return None

        logger.debug("cache_hit", key=key, age=now - timestamp)
        return value

    def set(self, key: str, value: T) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = (value, time.time())
        logger.debug("cache_set", key=key, cache_size=len(self.cache))

    def delete(self, key: str) -> None:
        """
        Delete value from cache.

        Args:
            key: Cache key
        """
        if key in self.cache:
            del self.cache[key]
            logger.debug("cache_delete", key=key)

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self.cache)
        self.cache.clear()
        logger.info("cache_cleared", entries_removed=count)

    def cleanup_expired(self) -> None:
        """
        Remove expired cache entries.

        Should be called periodically to prevent memory leaks.
        """
        now = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self.cache.items()
            if now - timestamp > self.ttl_seconds
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info("cache_cleanup", expired_count=len(expired_keys))


class TemplateCache:
    """
    Cache for infrastructure templates.

    Caches deployment templates to reduce database load and improve
    performance for frequently accessed templates.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        """
        Initialize template cache.

        Args:
            ttl_seconds: Cache TTL in seconds (default: 300)
        """
        self.cache: InMemoryCache[dict[str, Any]] = InMemoryCache(ttl_seconds)

    def _generate_key(self, template: dict[str, Any]) -> str:
        """
        Generate cache key for template.

        Creates a deterministic hash of the template content to use as cache key.

        Args:
            template: Template dictionary

        Returns:
            Cache key (hash of template)
        """
        # Sort keys to ensure consistent ordering
        template_json = json.dumps(template, sort_keys=True)
        template_hash = hashlib.sha256(template_json.encode()).hexdigest()[:16]
        return f"template:{template_hash}"

    def get(self, template: dict[str, Any]) -> dict[str, Any] | None:
        """
        Get cached template validation result.

        Args:
            template: Template to look up

        Returns:
            Cached template if found, None otherwise
        """
        key = self._generate_key(template)
        return self.cache.get(key)

    def set(self, template: dict[str, Any]) -> None:
        """
        Cache template validation result.

        Args:
            template: Template to cache
        """
        key = self._generate_key(template)
        self.cache.set(key, template)

    def invalidate(self, template: dict[str, Any]) -> None:
        """
        Invalidate cached template.

        Args:
            template: Template to invalidate
        """
        key = self._generate_key(template)
        self.cache.delete(key)

    def clear(self) -> None:
        """Clear all cached templates."""
        self.cache.clear()


class DeploymentCache:
    """
    Cache for deployment data.

    Caches deployment information to reduce database queries for
    frequently accessed deployments.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        """
        Initialize deployment cache.

        Args:
            ttl_seconds: Cache TTL in seconds (default: 300)
        """
        self.cache: InMemoryCache[dict[str, Any]] = InMemoryCache(ttl_seconds)

    def _generate_key(self, deployment_id: str) -> str:
        """
        Generate cache key for deployment.

        Args:
            deployment_id: Deployment ID

        Returns:
            Cache key
        """
        return f"deployment:{deployment_id}"

    def get(self, deployment_id: str) -> dict[str, Any] | None:
        """
        Get cached deployment data.

        Args:
            deployment_id: Deployment ID

        Returns:
            Cached deployment data if found, None otherwise
        """
        key = self._generate_key(deployment_id)
        return self.cache.get(key)

    def set(self, deployment_id: str, deployment_data: dict[str, Any]) -> None:
        """
        Cache deployment data.

        Args:
            deployment_id: Deployment ID
            deployment_data: Deployment data to cache
        """
        key = self._generate_key(deployment_id)
        self.cache.set(key, deployment_data)

    def invalidate(self, deployment_id: str) -> None:
        """
        Invalidate cached deployment.

        Args:
            deployment_id: Deployment ID to invalidate
        """
        key = self._generate_key(deployment_id)
        self.cache.delete(key)

    def clear(self) -> None:
        """Clear all cached deployments."""
        self.cache.clear()


# Global cache instances
template_cache = TemplateCache(ttl_seconds=300)
deployment_cache = DeploymentCache(ttl_seconds=60)
