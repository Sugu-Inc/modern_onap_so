"""
Rate limiting middleware for API protection.

Implements sliding window rate limiting to prevent API abuse.
"""

import time
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from orchestrator.logging import logger


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter.

    Tracks requests in a sliding time window and enforces rate limits
    based on API key or IP address.

    Attributes:
        rate_limit: Maximum number of requests allowed per window
        window_seconds: Time window in seconds
        requests: Dictionary mapping identifiers to request timestamps
    """

    def __init__(self, rate_limit: int = 100, window_seconds: int = 60) -> None:
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum requests allowed per window
            window_seconds: Time window in seconds (default: 60)
        """
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        # Use deque for efficient removal of old timestamps
        self.requests: dict[str, deque[float]] = defaultdict(lambda: deque())

    def is_allowed(self, identifier: str) -> tuple[bool, dict[str, Any]]:
        """
        Check if request is allowed based on rate limit.

        Args:
            identifier: Unique identifier (API key or IP address)

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Get request queue for this identifier
        request_queue = self.requests[identifier]

        # Remove requests outside the current window
        while request_queue and request_queue[0] < window_start:
            request_queue.popleft()

        # Count requests in current window
        current_count = len(request_queue)

        # Check if rate limit exceeded
        if current_count >= self.rate_limit:
            # Calculate when the oldest request will expire
            oldest_request = request_queue[0]
            retry_after = int(oldest_request + self.window_seconds - now) + 1

            return False, {
                "limit": self.rate_limit,
                "remaining": 0,
                "reset": int(oldest_request + self.window_seconds),
                "retry_after": retry_after,
            }

        # Allow the request and record it
        request_queue.append(now)

        return True, {
            "limit": self.rate_limit,
            "remaining": self.rate_limit - current_count - 1,
            "reset": int(now + self.window_seconds),
        }

    def cleanup_old_entries(self) -> None:
        """
        Clean up expired request entries to prevent memory leaks.

        Should be called periodically (e.g., every 5 minutes).
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Remove identifiers with no recent requests
        to_remove = []
        for identifier, request_queue in self.requests.items():
            # Remove old requests
            while request_queue and request_queue[0] < window_start:
                request_queue.popleft()

            # If no requests remain, mark for removal
            if not request_queue:
                to_remove.append(identifier)

        # Remove empty entries
        for identifier in to_remove:
            del self.requests[identifier]

        if to_remove:
            logger.info(
                "rate_limiter_cleanup",
                removed_count=len(to_remove),
                active_identifiers=len(self.requests),
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies rate limits based on API key (if authenticated) or IP address.
    Public endpoints like /health and /metrics are exempt from rate limiting.
    """

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json"}

    def __init__(
        self,
        app: FastAPI,
        rate_limit: int = 100,
        window_seconds: int = 60,
    ) -> None:
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            rate_limit: Maximum requests per window (default: 100)
            window_seconds: Time window in seconds (default: 60)
        """
        super().__init__(app)
        self.rate_limiter = SlidingWindowRateLimiter(
            rate_limit=rate_limit,
            window_seconds=window_seconds,
        )

    def _get_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting.

        Uses API key if available, otherwise falls back to IP address.

        Args:
            request: FastAPI request object

        Returns:
            Unique identifier string
        """
        # Try to get API key from auth context
        if hasattr(request.state, "auth") and request.state.auth:
            return f"api_key:{request.state.auth.api_key}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request with rate limiting.

        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain

        Returns:
            Response with rate limit headers
        """
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get identifier for rate limiting
        identifier = self._get_identifier(request)

        # Check rate limit
        is_allowed, rate_info = self.rate_limiter.is_allowed(identifier)

        if not is_allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=request.url.path,
                method=request.method,
                retry_after=rate_info["retry_after"],
            )

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Too many requests.",
                    "retry_after": rate_info["retry_after"],
                },
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                    "Retry-After": str(rate_info["retry_after"]),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])

        return response


def add_rate_limit_middleware(
    app: FastAPI,
    rate_limit: int = 100,
    window_seconds: int = 60,
) -> None:
    """
    Add rate limiting middleware to FastAPI application.

    Args:
        app: FastAPI application
        rate_limit: Maximum requests per window (default: 100)
        window_seconds: Time window in seconds (default: 60)
    """
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit=rate_limit,
        window_seconds=window_seconds,
    )
    logger.info(
        "rate_limit_middleware_added",
        rate_limit=rate_limit,
        window_seconds=window_seconds,
    )
