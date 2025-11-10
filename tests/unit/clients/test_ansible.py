"""Tests for AnsibleClient."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.clients.ansible.client import AnsibleClient, PlaybookStatus


class TestAnsibleClient:
    """Test AnsibleClient class."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default settings."""
        client = AnsibleClient()

        assert client.timeout == 300
        assert client.verbosity == 0

    def test_init_with_custom_settings(self) -> None:
        """Test client initialization with custom settings."""
        client = AnsibleClient(timeout=600, verbosity=2)

        assert client.timeout == 600
        assert client.verbosity == 2

    @pytest.mark.asyncio
    async def test_run_playbook_success(self) -> None:
        """Test successful playbook execution."""
        client = AnsibleClient()

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "successful"
        mock_result.rc = 0
        mock_result.stats = {"ok": {"test-host": 5}, "failures": {}, "changed": {"test-host": 2}}
        mock_runner_module.run_async.return_value = (mock_thread, mock_result)

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None  # Thread join completes

                # Execute playbook
                result = await client.run_playbook(
                    playbook_path=Path("/path/to/playbook.yml"),
                    inventory="test-host,",
                    extra_vars={"var1": "value1"},
                )

                # Verify result
                assert result.status == PlaybookStatus.SUCCESSFUL
                assert result.return_code == 0
                assert result.stats["ok"]["test-host"] == 5
                assert result.stats["changed"]["test-host"] == 2

                # Verify ansible-runner was called correctly
                mock_runner_module.run_async.assert_called_once()
                call_kwargs = mock_runner_module.run_async.call_args[1]
                assert str(call_kwargs["playbook"]) == "/path/to/playbook.yml"
                assert call_kwargs["inventory"] == "test-host,"
                assert call_kwargs["extravars"] == {"var1": "value1"}

    @pytest.mark.asyncio
    async def test_run_playbook_failure(self) -> None:
        """Test playbook execution with failures."""
        client = AnsibleClient()

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "failed"
        mock_result.rc = 2
        mock_result.stats = {
            "ok": {"test-host": 3},
            "failures": {"test-host": 1},
            "changed": {"test-host": 1},
        }
        mock_runner_module.run_async.return_value = (mock_thread, mock_result)

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None

                # Execute playbook
                result = await client.run_playbook(
                    playbook_path=Path("/path/to/playbook.yml"),
                    inventory="test-host,",
                )

                # Verify result
                assert result.status == PlaybookStatus.FAILED
                assert result.return_code == 2
                assert result.stats["failures"]["test-host"] == 1

    @pytest.mark.asyncio
    async def test_run_playbook_timeout(self) -> None:
        """Test playbook execution with timeout."""
        client = AnsibleClient(timeout=1)

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "timeout"
        mock_result.rc = None
        mock_result.stats = {}
        mock_runner_module.run_async.return_value = (mock_thread, mock_result)

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None

                # Execute playbook
                result = await client.run_playbook(
                    playbook_path=Path("/path/to/playbook.yml"),
                    inventory="test-host,",
                )

                # Verify result
                assert result.status == PlaybookStatus.TIMEOUT
                assert result.return_code is None

    @pytest.mark.asyncio
    async def test_run_playbook_with_verbosity(self) -> None:
        """Test playbook execution with verbosity setting."""
        client = AnsibleClient(verbosity=3)

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "successful"
        mock_result.rc = 0
        mock_result.stats = {"ok": {"test-host": 1}}
        mock_runner_module.run_async.return_value = (mock_thread, mock_result)

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None

                # Execute playbook
                await client.run_playbook(
                    playbook_path=Path("/path/to/playbook.yml"),
                    inventory="test-host,",
                )

                # Verify verbosity was passed
                call_kwargs = mock_runner_module.run_async.call_args[1]
                assert call_kwargs["verbosity"] == 3

    @pytest.mark.asyncio
    async def test_run_playbook_with_limit(self) -> None:
        """Test playbook execution with host limit."""
        client = AnsibleClient()

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "successful"
        mock_result.rc = 0
        mock_result.stats = {"ok": {"specific-host": 1}}
        mock_runner_module.run_async.return_value = (mock_thread, mock_result)

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None

                # Execute playbook with limit
                await client.run_playbook(
                    playbook_path=Path("/path/to/playbook.yml"),
                    inventory="host1,host2,",
                    limit="host1",
                )

                # Verify limit was passed
                call_kwargs = mock_runner_module.run_async.call_args[1]
                assert call_kwargs["limit"] == "host1"

    @pytest.mark.asyncio
    async def test_get_playbook_status_running(self) -> None:
        """Test getting status of a running playbook."""
        client = AnsibleClient()

        # Mock in-progress playbook
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        with patch.object(client, "_running_playbooks", {uuid4(): mock_thread}):
            playbook_id = list(client._running_playbooks.keys())[0]
            status = await client.get_playbook_status(playbook_id)

            assert status.status == PlaybookStatus.RUNNING
            assert status.return_code is None

    @pytest.mark.asyncio
    async def test_get_playbook_status_not_found(self) -> None:
        """Test getting status of a non-existent playbook."""
        client = AnsibleClient()

        status = await client.get_playbook_status(uuid4())

        assert status.status == PlaybookStatus.NOT_FOUND
        assert status.return_code is None

    @pytest.mark.asyncio
    async def test_run_playbook_stores_execution(self) -> None:
        """Test that playbook execution is stored for status tracking."""
        client = AnsibleClient()

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "successful"
        mock_result.rc = 0
        mock_result.stats = {"ok": {"test-host": 1}}
        mock_runner_module.run_async.return_value = (mock_thread, mock_result)

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None

                # Execute playbook
                result = await client.run_playbook(
                    playbook_path=Path("/path/to/playbook.yml"),
                    inventory="test-host,",
                )

                # Verify execution ID was generated
                assert result.execution_id is not None

    @pytest.mark.asyncio
    async def test_run_playbook_exception_handling(self) -> None:
        """Test playbook execution handles exceptions gracefully."""
        client = AnsibleClient()

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_runner_module.run_async.side_effect = Exception("Ansible runner error")

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            # Execute playbook - should not raise exception
            result = await client.run_playbook(
                playbook_path=Path("/path/to/playbook.yml"),
                inventory="test-host,",
            )

            # Verify result indicates error
            assert result.status == PlaybookStatus.FAILED
            assert "Ansible runner error" in str(result.error)

    @pytest.mark.asyncio
    async def test_run_playbook_with_ssh_key(self) -> None:
        """Test playbook execution with SSH private key."""
        client = AnsibleClient()

        # Mock ansible-runner module (lazy import)
        mock_runner_module = MagicMock()
        mock_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "successful"
        mock_result.rc = 0
        mock_result.stats = {"ok": {"test-host": 1}}
        mock_runner_module.run_async.return_value = (mock_thread, mock_result)

        with patch.dict("sys.modules", {"ansible_runner": mock_runner_module}):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None

                # Execute playbook with SSH key
                await client.run_playbook(
                    playbook_path=Path("/path/to/playbook.yml"),
                    inventory="test-host,",
                    ssh_private_key_path=Path("/path/to/key.pem"),
                )

                # Verify SSH key was passed
                call_kwargs = mock_runner_module.run_async.call_args[1]
                assert "ssh_key" in call_kwargs
                assert str(call_kwargs["ssh_key"]) == "/path/to/key.pem"


class TestPlaybookStatus:
    """Test PlaybookStatus enum."""

    def test_playbook_status_values(self) -> None:
        """Test PlaybookStatus enum values."""
        assert PlaybookStatus.RUNNING.value == "running"
        assert PlaybookStatus.SUCCESSFUL.value == "successful"
        assert PlaybookStatus.FAILED.value == "failed"
        assert PlaybookStatus.TIMEOUT.value == "timeout"
        assert PlaybookStatus.NOT_FOUND.value == "not_found"
