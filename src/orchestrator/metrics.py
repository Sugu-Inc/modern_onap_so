"""
Prometheus metrics configuration.

Provides application metrics for monitoring and alerting.
"""

from prometheus_client import Counter, Histogram, Info, generate_latest

# Application info
app_info = Info("orchestrator_app", "Application information")

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

# Deployment metrics (to be incremented by services)
deployments_total = Counter(
    "deployments_total",
    "Total deployment operations",
    ["status", "cloud_region"],
)

deployments_duration_seconds = Histogram(
    "deployments_duration_seconds",
    "Deployment operation duration in seconds",
    ["operation", "cloud_region"],
)


def setup_metrics() -> None:
    """
    Setup and configure Prometheus metrics.

    Initializes application info and metric collectors.
    """
    # Set application info
    app_info.info(
        {
            "version": "1.0.0",
            "name": "modern-orchestrator",
        }
    )


def get_metrics() -> dict:
    """
    Get current metrics collectors.

    Returns:
        Dictionary of metric collectors
    """
    return {
        "app_info": app_info,
        "http_requests_total": http_requests_total,
        "http_request_duration_seconds": http_request_duration_seconds,
        "deployments_total": deployments_total,
        "deployments_duration_seconds": deployments_duration_seconds,
    }


def generate_metrics() -> bytes:
    """
    Generate Prometheus metrics output.

    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest()
