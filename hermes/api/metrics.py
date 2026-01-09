"""
Prometheus Metrics Endpoint

Exposes application metrics for monitoring.
"""

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

router = APIRouter()

# Define metrics
PROMPT_REQUESTS = Counter(
    "hermes_prompt_requests_total",
    "Total prompt API requests",
    ["method", "endpoint", "status"],
)

PROMPT_LATENCY = Histogram(
    "hermes_prompt_request_duration_seconds",
    "Prompt request duration in seconds",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

BENCHMARK_RUNS = Counter(
    "hermes_benchmark_runs_total",
    "Total benchmark runs",
    ["prompt_type", "status"],
)

BENCHMARK_SCORE = Histogram(
    "hermes_benchmark_score",
    "Benchmark scores",
    ["prompt_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
