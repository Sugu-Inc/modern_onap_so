"""
Circuit breaker pattern implementation for fault tolerance.

Prevents cascading failures by monitoring operation failures and temporarily
blocking calls when failure rate exceeds threshold.
"""

import functools
import time
from enum import Enum
from typing import Any, Callable, TypeVar

from orchestrator.logging import logger

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation, calls are allowed
    OPEN = "OPEN"  # Circuit is open, calls are blocked
    HALF_OPEN = "HALF_OPEN"  # Testing if service has recovered


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Monitors operation failures and opens circuit when failure threshold is reached.
    After a timeout period, transitions to HALF_OPEN to test if service has recovered.

    States:
        CLOSED: Normal operation, all calls are allowed
        OPEN: Too many failures, all calls are blocked
        HALF_OPEN: Testing recovery, limited calls are allowed

    State transitions:
        CLOSED -> OPEN: When failure_count >= failure_threshold
        OPEN -> HALF_OPEN: After timeout period
        HALF_OPEN -> CLOSED: On successful call
        HALF_OPEN -> OPEN: On failed call

    Example:
        cb = CircuitBreaker(failure_threshold=5, timeout=60.0)

        @circuit_breaker_sync(cb)
        def call_external_service():
            return requests.get("https://api.example.com/data")
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Time in seconds to wait before transitioning from OPEN to HALF_OPEN
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self._state = CircuitBreakerState.CLOSED

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state

    def can_execute(self) -> bool:
        """
        Check if operation can be executed.

        Returns:
            True if operation can proceed, False if circuit is open
        """
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            # Check if timeout has elapsed
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time >= self.timeout
            ):
                logger.info(
                    "circuit_breaker_half_open",
                    timeout=self.timeout,
                )
                self._state = CircuitBreakerState.HALF_OPEN
                return True
            return False

        # HALF_OPEN state - allow one call to test
        return True

    def record_success(self) -> None:
        """Record successful operation execution."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            logger.info(
                "circuit_breaker_closed",
                previous_failures=self.failure_count,
            )
            self._state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
        elif self._state == CircuitBreakerState.CLOSED:
            # Reset failure count on success in CLOSED state
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed operation execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self._state == CircuitBreakerState.HALF_OPEN:
            logger.warning(
                "circuit_breaker_reopened",
                failure_count=self.failure_count,
            )
            self._state = CircuitBreakerState.OPEN
        elif self._state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    "circuit_breaker_opened",
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold,
                )
                self._state = CircuitBreakerState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        logger.info("circuit_breaker_reset")
        self._state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


def circuit_breaker_sync(breaker: CircuitBreaker) -> Callable[[F], F]:
    """
    Decorator for protecting synchronous functions with circuit breaker.

    Args:
        breaker: CircuitBreaker instance to use

    Returns:
        Decorated function protected by circuit breaker

    Raises:
        CircuitBreakerError: If circuit is open

    Example:
        cb = CircuitBreaker(failure_threshold=3, timeout=30.0)

        @circuit_breaker_sync(cb)
        def call_api():
            return requests.get("https://api.example.com")
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not breaker.can_execute():
                raise CircuitBreakerError(
                    f"Circuit breaker is {breaker.state.value} for {func.__name__}"
                )

            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def circuit_breaker_async(breaker: CircuitBreaker) -> Callable[[F], F]:
    """
    Decorator for protecting asynchronous functions with circuit breaker.

    Args:
        breaker: CircuitBreaker instance to use

    Returns:
        Decorated async function protected by circuit breaker

    Raises:
        CircuitBreakerError: If circuit is open

    Example:
        cb = CircuitBreaker(failure_threshold=3, timeout=30.0)

        @circuit_breaker_async(cb)
        async def call_api():
            async with httpx.AsyncClient() as client:
                return await client.get("https://api.example.com")
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not breaker.can_execute():
                raise CircuitBreakerError(
                    f"Circuit breaker is {breaker.state.value} for {func.__name__}"
                )

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
