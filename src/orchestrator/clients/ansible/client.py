"""
Ansible client for running playbooks on deployed VMs.

Uses ansible-runner for executing Ansible playbooks.
"""

import asyncio
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from orchestrator.logging import logger


class PlaybookStatus(str, Enum):
    """Playbook execution status."""

    RUNNING = "running"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"


class PlaybookResult(BaseModel):
    """Result of playbook execution."""

    execution_id: UUID = Field(..., description="Unique execution ID")
    status: PlaybookStatus = Field(..., description="Execution status")
    return_code: int | None = Field(None, description="Ansible return code")
    stats: dict[str, Any] = Field(
        default_factory=dict, description="Ansible execution statistics"
    )
    error: str | None = Field(None, description="Error message if failed")


class AnsibleClient:
    """
    Client for executing Ansible playbooks.

    Uses ansible-runner library to execute playbooks asynchronously.
    """

    def __init__(
        self,
        timeout: int = 300,
        verbosity: int = 0,
    ):
        """
        Initialize Ansible client.

        Args:
            timeout: Playbook execution timeout in seconds (default: 300)
            verbosity: Ansible verbosity level 0-4 (default: 0)
        """
        self.timeout = timeout
        self.verbosity = verbosity
        self._running_playbooks: dict[UUID, Any] = {}

    async def run_playbook(
        self,
        playbook_path: Path,
        inventory: str,
        extra_vars: dict[str, Any] | None = None,
        limit: str | None = None,
        ssh_private_key_path: Path | None = None,
    ) -> PlaybookResult:
        """
        Run Ansible playbook asynchronously.

        Args:
            playbook_path: Path to Ansible playbook YAML file
            inventory: Ansible inventory (can be comma-separated hosts or inventory file)
            extra_vars: Extra variables to pass to playbook
            limit: Limit execution to specific hosts
            ssh_private_key_path: Path to SSH private key for authentication

        Returns:
            PlaybookResult with execution status and statistics
        """
        execution_id = uuid4()

        logger.info(
            "ansible_playbook_starting",
            execution_id=str(execution_id),
            playbook=str(playbook_path),
            inventory=inventory,
        )

        try:
            # Import ansible_runner here to avoid import errors if not installed
            import ansible_runner

            # Build ansible-runner kwargs
            runner_kwargs: dict[str, Any] = {
                "playbook": str(playbook_path),
                "inventory": inventory,
                "verbosity": self.verbosity,
                "quiet": False,
            }

            if extra_vars:
                runner_kwargs["extravars"] = extra_vars

            if limit:
                runner_kwargs["limit"] = limit

            if ssh_private_key_path:
                runner_kwargs["ssh_key"] = str(ssh_private_key_path)

            # Run playbook asynchronously
            thread, runner = ansible_runner.run_async(**runner_kwargs)

            # Store thread for status tracking
            self._running_playbooks[execution_id] = thread

            # Wait for completion with timeout
            await asyncio.to_thread(thread.join, timeout=self.timeout)

            # Determine status
            if runner.status == "successful":
                status = PlaybookStatus.SUCCESSFUL
            elif runner.status == "failed":
                status = PlaybookStatus.FAILED
            elif runner.status == "timeout":
                status = PlaybookStatus.TIMEOUT
            else:
                status = PlaybookStatus.FAILED

            # Get statistics
            stats = runner.stats if hasattr(runner, "stats") else {}

            logger.info(
                "ansible_playbook_completed",
                execution_id=str(execution_id),
                status=status.value,
                return_code=runner.rc,
            )

            return PlaybookResult(
                execution_id=execution_id,
                status=status,
                return_code=runner.rc,
                stats=stats,
            )

        except Exception as e:
            logger.error(
                "ansible_playbook_error",
                execution_id=str(execution_id),
                error=str(e),
            )

            return PlaybookResult(
                execution_id=execution_id,
                status=PlaybookStatus.FAILED,
                return_code=None,
                stats={},
                error=str(e),
            )

        finally:
            # Clean up stored thread
            if execution_id in self._running_playbooks:
                del self._running_playbooks[execution_id]

    async def get_playbook_status(self, execution_id: UUID) -> PlaybookResult:
        """
        Get status of a running playbook execution.

        Args:
            execution_id: Execution ID from run_playbook

        Returns:
            PlaybookResult with current status
        """
        if execution_id not in self._running_playbooks:
            logger.warning(
                "ansible_playbook_not_found",
                execution_id=str(execution_id),
            )
            return PlaybookResult(
                execution_id=execution_id,
                status=PlaybookStatus.NOT_FOUND,
                return_code=None,
                stats={},
            )

        thread = self._running_playbooks[execution_id]

        if thread.is_alive():
            logger.info(
                "ansible_playbook_still_running",
                execution_id=str(execution_id),
            )
            return PlaybookResult(
                execution_id=execution_id,
                status=PlaybookStatus.RUNNING,
                return_code=None,
                stats={},
            )

        # Thread completed - should have been cleaned up by run_playbook
        return PlaybookResult(
            execution_id=execution_id,
            status=PlaybookStatus.NOT_FOUND,
            return_code=None,
            stats={},
        )
