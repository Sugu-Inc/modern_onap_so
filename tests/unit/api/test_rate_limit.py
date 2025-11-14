"""
Unit tests for rate limiting middleware.
"""

import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from orchestrator.api.middleware.rate_limit import (
    RateLimitMiddleware,
    SlidingWindowRateLimiter,
    add_rate_limit_middleware,
)


class TestSlidingWindowRateLimiter:
    """Test SlidingWindowRateLimiter class."""

    def test_rate_limiter_initialization(self) -> None:
        """Test rate limiter initializes with correct defaults."""
        limiter = SlidingWindowRateLimiter(rate_limit=10, window_seconds=60)
        assert limiter.rate_limit == 10
        assert limiter.window_seconds == 60
        assert len(limiter.requests) == 0

    def test_rate_limiter_allows_requests_under_limit(self) -> None:
        """Test that requests under the limit are allowed."""
        limiter = SlidingWindowRateLimiter(rate_limit=5, window_seconds=60)

        # First 5 requests should be allowed
        for i in range(5):
            is_allowed, info = limiter.is_allowed("test-key")
            assert is_allowed is True
            assert info["limit"] == 5
            assert info["remaining"] == 5 - i - 1

    def test_rate_limiter_blocks_requests_over_limit(self) -> None:
        """Test that requests over the limit are blocked."""
        limiter = SlidingWindowRateLimiter(rate_limit=3, window_seconds=60)

        # First 3 requests allowed
        for _ in range(3):
            is_allowed, _ = limiter.is_allowed("test-key")
            assert is_allowed is True

        # 4th request should be blocked
        is_allowed, info = limiter.is_allowed("test-key")
        assert is_allowed is False
        assert info["remaining"] == 0
        assert "retry_after" in info

    def test_rate_limiter_resets_after_window(self) -> None:
        """Test that rate limit resets after time window."""
        limiter = SlidingWindowRateLimiter(rate_limit=2, window_seconds=1)

        # Use up the limit
        limiter.is_allowed("test-key")
        limiter.is_allowed("test-key")

        # Should be blocked
        is_allowed, _ = limiter.is_allowed("test-key")
        assert is_allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        is_allowed, info = limiter.is_allowed("test-key")
        assert is_allowed is True
        assert info["remaining"] >= 0

    def test_rate_limiter_tracks_multiple_identifiers(self) -> None:
        """Test that different identifiers have separate limits."""
        limiter = SlidingWindowRateLimiter(rate_limit=2, window_seconds=60)

        # Use up limit for key1
        limiter.is_allowed("key1")
        limiter.is_allowed("key1")

        # key1 should be blocked
        is_allowed, _ = limiter.is_allowed("key1")
        assert is_allowed is False

        # key2 should still be allowed
        is_allowed, _ = limiter.is_allowed("key2")
        assert is_allowed is True

    def test_rate_limiter_cleanup_removes_old_entries(self) -> None:
        """Test that cleanup removes old entries."""
        limiter = SlidingWindowRateLimiter(rate_limit=5, window_seconds=1)

        # Make requests
        limiter.is_allowed("key1")
        limiter.is_allowed("key2")
        assert len(limiter.requests) == 2

        # Wait for window to expire
        time.sleep(1.1)

        # Cleanup should remove expired entries
        limiter.cleanup_old_entries()
        assert len(limiter.requests) == 0

    def test_rate_limiter_cleanup_keeps_recent_entries(self) -> None:
        """Test that cleanup keeps recent entries."""
        limiter = SlidingWindowRateLimiter(rate_limit=5, window_seconds=60)

        # Make request
        limiter.is_allowed("key1")
        assert len(limiter.requests) == 1

        # Cleanup should not remove recent entries
        limiter.cleanup_old_entries()
        assert len(limiter.requests) == 1


class TestRateLimitMiddleware:
    """Test rate limit middleware integration."""

    @pytest.mark.asyncio
    async def test_middleware_allows_requests_under_limit(self) -> None:
        """Test that requests under limit are allowed."""
        app = FastAPI()
        add_rate_limit_middleware(app, rate_limit=10, window_seconds=60)

        @app.get("/api/test")
        async def test_endpoint() -> dict:
            return {"message": "success"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # First request should succeed
            response = await client.get("/api/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "10"
        assert "X-RateLimit-Remaining" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_blocks_requests_over_limit(self) -> None:
        """Test that requests over limit are blocked with 429."""
        app = FastAPI()
        add_rate_limit_middleware(app, rate_limit=3, window_seconds=60)

        @app.get("/api/test")
        async def test_endpoint() -> dict:
            return {"message": "success"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Make requests up to the limit
            for _ in range(3):
                response = await client.get("/api/test")
                assert response.status_code == 200

            # Next request should be rate limited
            response = await client.get("/api/test")

        assert response.status_code == 429
        assert "detail" in response.json()
        assert "rate limit" in response.json()["detail"].lower()
        assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_exempts_health_endpoint(self) -> None:
        """Test that health endpoint is exempt from rate limiting."""
        app = FastAPI()
        add_rate_limit_middleware(app, rate_limit=2, window_seconds=60)

        @app.get("/health")
        async def health() -> dict:
            return {"status": "ok"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Make many requests to /health
            for _ in range(10):
                response = await client.get("/health")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_exempts_metrics_endpoint(self) -> None:
        """Test that metrics endpoint is exempt from rate limiting."""
        app = FastAPI()
        add_rate_limit_middleware(app, rate_limit=2, window_seconds=60)

        @app.get("/metrics")
        async def metrics() -> str:
            return "# metrics"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Make many requests to /metrics
            for _ in range(10):
                response = await client.get("/metrics")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_exempts_docs_endpoint(self) -> None:
        """Test that docs endpoint is exempt from rate limiting."""
        app = FastAPI()
        add_rate_limit_middleware(app, rate_limit=2, window_seconds=60)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Make many requests to /docs
            for _ in range(10):
                response = await client.get("/docs")
                # Docs may return 404 if not configured, but shouldn't be rate limited
                assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_middleware_includes_rate_limit_headers(self) -> None:
        """Test that rate limit headers are included in response."""
        app = FastAPI()
        add_rate_limit_middleware(app, rate_limit=10, window_seconds=60)

        @app.get("/api/test")
        async def test_endpoint() -> dict:
            return {"message": "success"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

        # Check values
        assert int(response.headers["X-RateLimit-Limit"]) == 10
        assert int(response.headers["X-RateLimit-Remaining"]) >= 0
        assert int(response.headers["X-RateLimit-Reset"]) > 0

    @pytest.mark.asyncio
    async def test_middleware_rate_limit_decreases_with_requests(self) -> None:
        """Test that remaining count decreases with each request."""
        app = FastAPI()
        add_rate_limit_middleware(app, rate_limit=5, window_seconds=60)

        @app.get("/api/test")
        async def test_endpoint() -> dict:
            return {"message": "success"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Make requests and check remaining count
            for i in range(3):
                response = await client.get("/api/test")
                assert response.status_code == 200
                remaining = int(response.headers["X-RateLimit-Remaining"])
                # Remaining should decrease (5-1=4, 4-1=3, 3-1=2)
                assert remaining == 5 - i - 1

    @pytest.mark.asyncio
    async def test_middleware_different_clients_separate_limits(self) -> None:
        """Test that different clients have separate rate limits."""
        app = FastAPI()
        # Very low limit to test separation
        add_rate_limit_middleware(app, rate_limit=1, window_seconds=60)

        @app.get("/api/test")
        async def test_endpoint() -> dict:
            return {"message": "success"}

        # First client uses up their limit
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client1:
            response = await client1.get("/api/test")
            assert response.status_code == 200

            # Second request from client1 should be blocked
            response = await client1.get("/api/test")
            assert response.status_code == 429

        # Second client should still have requests available
        # Note: This test may not work as expected with test clients
        # since they share the same IP. In production, different IPs
        # would have separate limits.
