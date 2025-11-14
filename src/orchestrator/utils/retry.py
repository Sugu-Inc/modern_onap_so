"""
Retry utilities for resilient operation execution.

Provides decorators for retrying operations with exponential backoff.
"""

import asyncio
import functools
import time
from typing import Any, Callable, TypeVar, cast

from orchestrator.logging import logger

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


class RetryableError(Exception):
    """Exception that indicates an operation should be retried."""

    pass


def retry_sync(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (RetryableError,),
) -> Callable[[F], F]:
    """
    Decorator for retrying synchronous functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts before giving up
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        max_delay: Maximum delay between retries in seconds
        exceptions: Tuple of exception types to retry on

    Returns:
        Decorated function that will retry on specified exceptions

    Example:
        @retry_sync(max_attempts=3, delay=1.0)
        def unreliable_operation():
            if random.random() < 0.5:
                raise RetryableError("Temporary failure")
            return "success"
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e),
                        )
                        raise

                    logger.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=current_delay,
                        error=str(e),
                    )

                    # Sleep before next attempt
                    time.sleep(current_delay)

                    # Calculate next delay with exponential backoff
                    current_delay = min(current_delay * backoff_factor, max_delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            return None

        return cast(F, wrapper)

    return decorator


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (RetryableError,),
) -> Callable[[F], F]:
    """
    Decorator for retrying asynchronous functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts before giving up
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        max_delay: Maximum delay between retries in seconds
        exceptions: Tuple of exception types to retry on

    Returns:
        Decorated async function that will retry on specified exceptions

    Example:
        @retry_async(max_attempts=3, delay=1.0, exceptions=(ConnectionError,))
        async def fetch_data():
            response = await http_client.get("/api/data")
            if response.status >= 500:
                raise ConnectionError("Server error")
            return response.json()
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e),
                        )
                        raise

                    logger.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=current_delay,
                        error=str(e),
                    )

                    # Sleep before next attempt
                    await asyncio.sleep(current_delay)

                    # Calculate next delay with exponential backoff
                    current_delay = min(current_delay * backoff_factor, max_delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            return None

        return cast(F, wrapper)

    return decorator
