"""
Unit tests for caching utilities.
"""

import time

import pytest

from orchestrator.utils.cache import (
    DeploymentCache,
    InMemoryCache,
    TemplateCache,
)


class TestInMemoryCache:
    """Test InMemoryCache class."""

    def test_cache_initialization(self) -> None:
        """Test cache initializes correctly."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=60)
        assert cache.ttl_seconds == 60
        assert len(cache.cache) == 0

    def test_cache_set_and_get(self) -> None:
        """Test setting and getting cache values."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=60)

        cache.set("key1", "value1")
        value = cache.get("key1")

        assert value == "value1"

    def test_cache_get_nonexistent_key(self) -> None:
        """Test getting non-existent key returns None."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=60)

        value = cache.get("nonexistent")

        assert value is None

    def test_cache_expiration(self) -> None:
        """Test that cache entries expire after TTL."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=1)

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        value = cache.get("key1")
        assert value is None

    def test_cache_delete(self) -> None:
        """Test deleting cache entries."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=60)

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        cache.delete("key1")
        assert cache.get("key1") is None

    def test_cache_delete_nonexistent_key(self) -> None:
        """Test deleting non-existent key doesn't raise error."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=60)

        # Should not raise error
        cache.delete("nonexistent")

    def test_cache_clear(self) -> None:
        """Test clearing all cache entries."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=60)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache.cache) == 2

        cache.clear()

        assert len(cache.cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_cleanup_expired(self) -> None:
        """Test cleanup removes expired entries."""
        cache: InMemoryCache[str] = InMemoryCache(ttl_seconds=1)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Wait for expiration
        time.sleep(1.1)

        # Add a fresh entry
        cache.set("key3", "value3")

        # Cleanup should remove expired entries
        cache.cleanup_expired()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"

    def test_cache_stores_different_types(self) -> None:
        """Test cache can store different types."""
        cache_str: InMemoryCache[str] = InMemoryCache(ttl_seconds=60)
        cache_int: InMemoryCache[int] = InMemoryCache(ttl_seconds=60)
        cache_dict: InMemoryCache[dict] = InMemoryCache(ttl_seconds=60)

        cache_str.set("key1", "string_value")
        cache_int.set("key2", 42)
        cache_dict.set("key3", {"nested": "dict"})

        assert cache_str.get("key1") == "string_value"
        assert cache_int.get("key2") == 42
        assert cache_dict.get("key3") == {"nested": "dict"}


class TestTemplateCache:
    """Test TemplateCache class."""

    def test_template_cache_initialization(self) -> None:
        """Test template cache initializes correctly."""
        cache = TemplateCache(ttl_seconds=60)
        assert cache.cache.ttl_seconds == 60

    def test_template_cache_set_and_get(self) -> None:
        """Test caching templates."""
        cache = TemplateCache(ttl_seconds=60)

        template = {
            "vm_config": {
                "flavor": "m1.small",
                "image": "ubuntu-20.04",
            }
        }

        # Cache the template
        cache.set(template)

        # Retrieve from cache
        cached = cache.get(template)

        assert cached is not None
        assert cached == template

    def test_template_cache_same_content_same_key(self) -> None:
        """Test that identical templates generate the same cache key."""
        cache = TemplateCache(ttl_seconds=60)

        template1 = {
            "vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}
        }
        template2 = {
            "vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}
        }

        # Different objects but same content
        assert template1 is not template2

        cache.set(template1)
        cached = cache.get(template2)

        # Should retrieve the same cached value
        assert cached is not None

    def test_template_cache_different_content_different_key(self) -> None:
        """Test that different templates generate different cache keys."""
        cache = TemplateCache(ttl_seconds=60)

        template1 = {
            "vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}
        }
        template2 = {
            "vm_config": {"flavor": "m1.large", "image": "ubuntu-20.04"}
        }

        cache.set(template1)

        # Different template should not be in cache
        cached = cache.get(template2)
        assert cached is None

    def test_template_cache_key_order_independent(self) -> None:
        """Test that template key generation is order-independent."""
        cache = TemplateCache(ttl_seconds=60)

        # Different key ordering
        template1 = {"b": 2, "a": 1}
        template2 = {"a": 1, "b": 2}

        cache.set(template1)
        cached = cache.get(template2)

        # Should retrieve despite different ordering
        assert cached is not None

    def test_template_cache_invalidate(self) -> None:
        """Test invalidating cached templates."""
        cache = TemplateCache(ttl_seconds=60)

        template = {
            "vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}
        }

        cache.set(template)
        assert cache.get(template) is not None

        cache.invalidate(template)
        assert cache.get(template) is None

    def test_template_cache_clear(self) -> None:
        """Test clearing all cached templates."""
        cache = TemplateCache(ttl_seconds=60)

        template1 = {"vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}}
        template2 = {"vm_config": {"flavor": "m1.large", "image": "ubuntu-20.04"}}

        cache.set(template1)
        cache.set(template2)

        cache.clear()

        assert cache.get(template1) is None
        assert cache.get(template2) is None


class TestDeploymentCache:
    """Test DeploymentCache class."""

    def test_deployment_cache_initialization(self) -> None:
        """Test deployment cache initializes correctly."""
        cache = DeploymentCache(ttl_seconds=60)
        assert cache.cache.ttl_seconds == 60

    def test_deployment_cache_set_and_get(self) -> None:
        """Test caching deployment data."""
        cache = DeploymentCache(ttl_seconds=60)

        deployment_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "test-deployment",
            "status": "COMPLETED",
        }

        cache.set("deployment-1", deployment_data)
        cached = cache.get("deployment-1")

        assert cached is not None
        assert cached == deployment_data

    def test_deployment_cache_get_nonexistent(self) -> None:
        """Test getting non-existent deployment returns None."""
        cache = DeploymentCache(ttl_seconds=60)

        cached = cache.get("nonexistent-id")

        assert cached is None

    def test_deployment_cache_invalidate(self) -> None:
        """Test invalidating cached deployments."""
        cache = DeploymentCache(ttl_seconds=60)

        deployment_data = {
            "id": "deployment-1",
            "name": "test-deployment",
        }

        cache.set("deployment-1", deployment_data)
        assert cache.get("deployment-1") is not None

        cache.invalidate("deployment-1")
        assert cache.get("deployment-1") is None

    def test_deployment_cache_clear(self) -> None:
        """Test clearing all cached deployments."""
        cache = DeploymentCache(ttl_seconds=60)

        cache.set("deployment-1", {"id": "1"})
        cache.set("deployment-2", {"id": "2"})

        cache.clear()

        assert cache.get("deployment-1") is None
        assert cache.get("deployment-2") is None

    def test_deployment_cache_separate_ids(self) -> None:
        """Test that different deployment IDs are cached separately."""
        cache = DeploymentCache(ttl_seconds=60)

        cache.set("deployment-1", {"data": "one"})
        cache.set("deployment-2", {"data": "two"})

        assert cache.get("deployment-1") == {"data": "one"}
        assert cache.get("deployment-2") == {"data": "two"}

    def test_deployment_cache_expiration(self) -> None:
        """Test that deployment cache entries expire."""
        cache = DeploymentCache(ttl_seconds=1)

        cache.set("deployment-1", {"id": "1"})
        assert cache.get("deployment-1") is not None

        # Wait for expiration
        time.sleep(1.1)

        assert cache.get("deployment-1") is None
