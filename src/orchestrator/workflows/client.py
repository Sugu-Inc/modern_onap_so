"""
Temporal client for workflow orchestration.

TODO: Implement when Temporal server is available.
"""

from temporalio.client import Client

from orchestrator.config import settings
from orchestrator.logging import logger


async def get_temporal_client() -> Client:
    """
    Get or create Temporal client.

    Returns:
        Temporal client instance

    TODO: Implement connection to Temporal server
    """
    logger.info("temporal_client_connecting", host=settings.temporal_host)

    # TODO: Implement actual connection
    # client = await Client.connect(settings.temporal_host)
    # return client

    raise NotImplementedError("Temporal client not yet implemented")
