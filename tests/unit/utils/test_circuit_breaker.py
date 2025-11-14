"""
Unit tests for circuit breaker utility.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    circuit_breaker_async,
    circuit_breaker_sync,
)


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    def test_circuit_breaker_initial_state(self) -> None:
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3, timeout=1.0)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_opens_after_threshold(self) -> None:
        """Test that circuit opens after failure threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3, timeout=1.0)

        # Record failures
        for _ in range(2):
            cb.record_failure()
            assert cb.state == CircuitBreakerState.CLOSED

        # Third failure should open the circuit
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_allows_call_when_closed(self) -> None:
        """Test that calls are allowed when circuit is closed."""
        cb = CircuitBreaker(failure_threshold=3, timeout=1.0)
        assert cb.can_execute() is True

    def test_circuit_breaker_blocks_call_when_open(self) -> None:
        """Test that calls are blocked when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1, timeout=1.0)
        cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False

    def test_circuit_breaker_transitions_to_half_open(self) -> None:
        """Test transition from OPEN to HALF_OPEN after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Should transition to HALF_OPEN on next can_execute check
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_closes_from_half_open_on_success(self) -> None:
        """Test circuit closes from HALF_OPEN after successful call."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(0.15)
        cb.can_execute()  # Transition to HALF_OPEN

        # Record success should close the circuit
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_reopens_from_half_open_on_failure(self) -> None:
        """Test circuit reopens from HALF_OPEN on failure."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        cb.record_failure()

        time.sleep(0.15)
        cb.can_execute()  # Transition to HALF_OPEN
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Failure in HALF_OPEN should reopen the circuit
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_resets(self) -> None:
        """Test circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1.0)
        cb.record_failure()
        cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

        cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0


class TestCircuitBreakerSyncDecorator:
    """Test synchronous circuit breaker decorator."""

    def test_sync_decorator_successful_calls(self) -> None:
        """Test successful calls through circuit breaker."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        mock_func = MagicMock(return_value="success")

        @circuit_breaker_sync(cb)
        def test_func() -> str:
            return mock_func()

        result = test_func()

        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert mock_func.call_count == 1

    def test_sync_decorator_opens_on_failures(self) -> None:
        """Test circuit opens after failures."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        mock_func = MagicMock(side_effect=Exception("error"))

        @circuit_breaker_sync(cb)
        def test_func() -> str:
            return mock_func()

        # First failure
        with pytest.raises(Exception, match="error"):
            test_func()
        assert cb.state == CircuitBreakerState.CLOSED

        # Second failure - should open circuit
        with pytest.raises(Exception, match="error"):
            test_func()
        assert cb.state == CircuitBreakerState.OPEN

    def test_sync_decorator_blocks_when_open(self) -> None:
        """Test that calls are blocked when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        mock_func = MagicMock()

        @circuit_breaker_sync(cb)
        def test_func() -> str:
            return mock_func()

        # Open the circuit
        cb.record_failure()

        # Call should be blocked
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is OPEN"):
            test_func()

        # Function should not be called
        mock_func.assert_not_called()

    def test_sync_decorator_half_open_recovery(self) -> None:
        """Test recovery through HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        call_count = 0

        @circuit_breaker_sync(cb)
        def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return "success"

        # Open circuit
        with pytest.raises(Exception, match="First call fails"):
            test_func()
        assert cb.state == CircuitBreakerState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Next call should succeed and close circuit
        result = test_func()
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerAsyncDecorator:
    """Test asynchronous circuit breaker decorator."""

    @pytest.mark.asyncio
    async def test_async_decorator_successful_calls(self) -> None:
        """Test successful async calls through circuit breaker."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        mock_func = AsyncMock(return_value="success")

        @circuit_breaker_async(cb)
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_async_decorator_opens_on_failures(self) -> None:
        """Test async circuit opens after failures."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        mock_func = AsyncMock(side_effect=Exception("error"))

        @circuit_breaker_async(cb)
        async def test_func() -> str:
            return await mock_func()

        # First failure
        with pytest.raises(Exception, match="error"):
            await test_func()
        assert cb.state == CircuitBreakerState.CLOSED

        # Second failure - should open circuit
        with pytest.raises(Exception, match="error"):
            await test_func()
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_async_decorator_blocks_when_open(self) -> None:
        """Test that async calls are blocked when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        mock_func = AsyncMock()

        @circuit_breaker_async(cb)
        async def test_func() -> str:
            return await mock_func()

        # Open the circuit
        cb.record_failure()

        # Call should be blocked
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is OPEN"):
            await test_func()

        # Function should not be called
        mock_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_decorator_half_open_recovery(self) -> None:
        """Test async recovery through HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        call_count = 0

        @circuit_breaker_async(cb)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return "success"

        # Open circuit
        with pytest.raises(Exception, match="First call fails"):
            await test_func()
        assert cb.state == CircuitBreakerState.OPEN

        # Wait for timeout
        import asyncio

        await asyncio.sleep(0.15)

        # Next call should succeed and close circuit
        result = await test_func()
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerError:
    """Test CircuitBreakerError exception."""

    def test_circuit_breaker_error_message(self) -> None:
        """Test CircuitBreakerError with message."""
        error = CircuitBreakerError("Circuit is open")
        assert str(error) == "Circuit is open"

    def test_circuit_breaker_error_is_exception(self) -> None:
        """Test that CircuitBreakerError is an Exception."""
        error = CircuitBreakerError("Test")
        assert isinstance(error, Exception)
