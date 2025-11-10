"""
Unit tests for retry utility.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.utils.retry import (
    RetryableError,
    retry_async,
    retry_sync,
)


class TestRetrySyncDecorator:
    """Test synchronous retry decorator."""

    def test_retry_sync_success_on_first_attempt(self) -> None:
        """Test that successful function doesn't retry."""
        mock_func = MagicMock(return_value="success")

        @retry_sync(max_attempts=3)
        def test_func() -> str:
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_sync_success_after_failures(self) -> None:
        """Test that function retries and eventually succeeds."""
        mock_func = MagicMock(side_effect=[
            RetryableError("fail 1"),
            RetryableError("fail 2"),
            "success",
        ])

        @retry_sync(max_attempts=3, delay=0.01)
        def test_func() -> str:
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_sync_exhausts_retries(self) -> None:
        """Test that function fails after max attempts."""
        mock_func = MagicMock(side_effect=RetryableError("persistent failure"))

        @retry_sync(max_attempts=3, delay=0.01)
        def test_func() -> str:
            return mock_func()

        with pytest.raises(RetryableError, match="persistent failure"):
            test_func()

        assert mock_func.call_count == 3

    def test_retry_sync_with_exponential_backoff(self) -> None:
        """Test exponential backoff calculation."""
        mock_func = MagicMock(side_effect=[
            RetryableError("fail 1"),
            RetryableError("fail 2"),
            "success",
        ])

        @retry_sync(max_attempts=3, delay=0.01, backoff_factor=2.0)
        def test_func() -> str:
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_sync_non_retryable_error(self) -> None:
        """Test that non-retryable errors are not retried."""
        mock_func = MagicMock(side_effect=ValueError("not retryable"))

        @retry_sync(max_attempts=3)
        def test_func() -> str:
            return mock_func()

        with pytest.raises(ValueError, match="not retryable"):
            test_func()

        # Should fail immediately without retry
        assert mock_func.call_count == 1

    def test_retry_sync_with_custom_exceptions(self) -> None:
        """Test retry with custom exception types."""
        mock_func = MagicMock(side_effect=[
            ConnectionError("network error"),
            ConnectionError("network error"),
            "success",
        ])

        @retry_sync(max_attempts=3, delay=0.01, exceptions=(ConnectionError,))
        def test_func() -> str:
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_sync_with_max_delay(self) -> None:
        """Test that delay is capped at max_delay."""
        mock_func = MagicMock(side_effect=[
            RetryableError("fail 1"),
            RetryableError("fail 2"),
            "success",
        ])

        @retry_sync(
            max_attempts=3,
            delay=1.0,
            backoff_factor=100.0,  # Would cause very long delay
            max_delay=0.1,  # But capped at 0.1 seconds
        )
        def test_func() -> str:
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 3


class TestRetryAsyncDecorator:
    """Test asynchronous retry decorator."""

    @pytest.mark.asyncio
    async def test_retry_async_success_on_first_attempt(self) -> None:
        """Test that successful async function doesn't retry."""
        mock_func = AsyncMock(return_value="success")

        @retry_async(max_attempts=3)
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_success_after_failures(self) -> None:
        """Test that async function retries and eventually succeeds."""
        mock_func = AsyncMock(side_effect=[
            RetryableError("fail 1"),
            RetryableError("fail 2"),
            "success",
        ])

        @retry_async(max_attempts=3, delay=0.01)
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_exhausts_retries(self) -> None:
        """Test that async function fails after max attempts."""
        mock_func = AsyncMock(side_effect=RetryableError("persistent failure"))

        @retry_async(max_attempts=3, delay=0.01)
        async def test_func() -> str:
            return await mock_func()

        with pytest.raises(RetryableError, match="persistent failure"):
            await test_func()

        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_with_exponential_backoff(self) -> None:
        """Test async exponential backoff."""
        mock_func = AsyncMock(side_effect=[
            RetryableError("fail 1"),
            RetryableError("fail 2"),
            "success",
        ])

        @retry_async(max_attempts=3, delay=0.01, backoff_factor=2.0)
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_non_retryable_error(self) -> None:
        """Test that non-retryable async errors are not retried."""
        mock_func = AsyncMock(side_effect=ValueError("not retryable"))

        @retry_async(max_attempts=3)
        async def test_func() -> str:
            return await mock_func()

        with pytest.raises(ValueError, match="not retryable"):
            await test_func()

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_with_custom_exceptions(self) -> None:
        """Test async retry with custom exception types."""
        mock_func = AsyncMock(side_effect=[
            ConnectionError("network error"),
            TimeoutError("timeout"),
            "success",
        ])

        @retry_async(
            max_attempts=3,
            delay=0.01,
            exceptions=(ConnectionError, TimeoutError),
        )
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 3


class TestRetryableError:
    """Test RetryableError exception."""

    def test_retryable_error_message(self) -> None:
        """Test RetryableError with message."""
        error = RetryableError("Test error message")
        assert str(error) == "Test error message"

    def test_retryable_error_is_exception(self) -> None:
        """Test that RetryableError is an Exception."""
        error = RetryableError("Test")
        assert isinstance(error, Exception)
