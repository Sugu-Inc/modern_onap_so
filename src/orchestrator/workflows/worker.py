"""
Temporal worker for executing workflows.

TODO: Implement when Temporal server is available and workflows are defined.
"""

from orchestrator.config import settings
from orchestrator.logging import logger


async def create_worker() -> None:
    """
    Create and start Temporal worker.

    TODO: Implement worker with registered workflows and activities
    """
    logger.info(
        "temporal_worker_starting",
        task_queue=settings.temporal_task_queue,
        namespace=settings.temporal_namespace,
    )

    # TODO: Implement actual worker
    # from temporalio.worker import Worker
    # from orchestrator.workflows.client import get_temporal_client
    #
    # client = await get_temporal_client()
    # worker = Worker(
    #     client,
    #     task_queue=settings.temporal_task_queue,
    #     workflows=[...],  # Register workflows
    #     activities=[...],  # Register activities
    # )
    # await worker.run()

    raise NotImplementedError("Temporal worker not yet implemented")
