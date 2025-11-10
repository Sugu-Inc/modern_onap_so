"""
Metrics endpoint for Prometheus scraping.
"""

from fastapi import APIRouter, Response

from orchestrator.metrics import generate_metrics

router = APIRouter()


@router.get(
    "/metrics",
    summary="Prometheus Metrics",
    description="Endpoint for Prometheus to scrape application metrics",
    tags=["monitoring"],
)
async def metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    """
    metrics_output = generate_metrics()

    return Response(
        content=metrics_output,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
