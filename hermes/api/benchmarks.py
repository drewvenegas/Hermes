"""
Benchmarks API Endpoints

Benchmark execution and results.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permission
from hermes.auth.models import User
from hermes.config import get_settings
from hermes.models import BenchmarkResult, Prompt
from hermes.schemas.benchmark import (
    BenchmarkListResponse,
    BenchmarkRequest,
    BenchmarkResponse,
    ModelBenchmarkResult,
    MultiModelBenchmarkRequest,
    MultiModelBenchmarkResponse,
)
from hermes.services.benchmark_service import BenchmarkService, BenchmarkSuiteService
from hermes.services.database import get_db

router = APIRouter()
settings = get_settings()


class BenchmarkTriggerResponse(BaseModel):
    """Response for benchmark trigger."""
    
    status: str = "queued"
    benchmark_id: Optional[uuid.UUID] = None
    message: str = ""


class ATEWebhookPayload(BaseModel):
    """Payload from ATE benchmark webhook."""
    
    prompt_id: uuid.UUID
    version: str
    overall_score: float = Field(..., ge=0, le=100)
    category_scores: dict[str, float] = Field(default_factory=dict)
    latency_ms: float = 0.0
    tokens_per_second: float = 0.0
    test_count: int = 0
    success_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    executed_at: datetime
    metadata: dict = Field(default_factory=dict)


async def _trigger_ate_benchmark(
    prompt_id: uuid.UUID,
    prompt_slug: str,
    prompt_version: str,
    model_id: str,
):
    """Background task to trigger ATE benchmark.
    
    Args:
        prompt_id: Prompt UUID
        prompt_slug: Prompt slug
        prompt_version: Prompt version
        model_id: Model ID to benchmark against
    """
    import httpx
    import logging
    
    logger = logging.getLogger(__name__)
    
    ate_url = settings.ate_grpc_url
    
    # For now, use REST - would be gRPC in production
    payload = {
        "prompt_id": str(prompt_id),
        "prompt_slug": prompt_slug,
        "prompt_version": prompt_version,
        "model_id": model_id,
        "callback_url": f"{settings.app_url}/api/v1/benchmarks/webhook",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # This would call ATE's benchmark trigger endpoint
            # For now, log the intent
            logger.info(f"Would trigger ATE benchmark: {payload}")
            # response = await client.post(f"http://{ate_url}/benchmark", json=payload)
            # response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to trigger ATE benchmark: {e}")


@router.post("/prompts/{prompt_id}/benchmark", response_model=BenchmarkTriggerResponse)
async def trigger_benchmark(
    prompt_id: uuid.UUID,
    data: BenchmarkRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_permission("benchmarks:run")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a benchmark run on a prompt.
    
    Requires: benchmarks:run permission
    
    The benchmark is executed asynchronously by ATE. Results are pushed
    back via webhook when complete.
    """
    # Get prompt
    query = select(Prompt).where(Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    # Create pending benchmark result
    benchmark = BenchmarkResult(
        prompt_id=prompt_id,
        prompt_version=prompt.version,
        suite_id=data.suite_id,
        overall_score=0.0,
        dimension_scores={},
        model_id=data.model_id,
        model_version="pending",
        execution_time_ms=0,
        token_usage={},
        baseline_score=prompt.benchmark_score,
        gate_passed=False,
        executed_at=datetime.utcnow(),
        executed_by=user.id,
        environment=data.environment or "staging",
    )
    
    db.add(benchmark)
    await db.flush()
    await db.refresh(benchmark)
    
    # Queue ATE benchmark
    if settings.ate_enabled:
        background_tasks.add_task(
            _trigger_ate_benchmark,
            prompt_id,
            prompt.slug,
            prompt.version,
            data.model_id,
        )
    
    return BenchmarkTriggerResponse(
        status="queued",
        benchmark_id=benchmark.id,
        message=f"Benchmark queued for {prompt.slug} v{prompt.version}",
    )


@router.post("/benchmarks/webhook", status_code=status.HTTP_201_CREATED)
async def benchmark_webhook(
    payload: ATEWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """Webhook endpoint for ATE to push benchmark results.
    
    Called by ATE when a benchmark completes.
    """
    # Get prompt
    query = select(Prompt).where(Prompt.id == payload.prompt_id)
    result = await db.execute(query)
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{payload.prompt_id}' not found",
        )
    
    # Create benchmark result
    benchmark = BenchmarkResult(
        prompt_id=payload.prompt_id,
        prompt_version=payload.version,
        suite_id="ate-default",
        overall_score=payload.overall_score,
        dimension_scores=payload.category_scores,
        model_id=payload.metadata.get("model_id", "aria-01"),
        model_version=payload.metadata.get("model_version", "1.0.0"),
        execution_time_ms=int(payload.latency_ms),
        token_usage={
            "tests": payload.test_count,
            "successes": payload.success_count,
        },
        baseline_score=prompt.benchmark_score,
        delta=(payload.overall_score - prompt.benchmark_score) if prompt.benchmark_score else None,
        gate_passed=payload.overall_score >= 80.0,
        executed_at=payload.executed_at,
        environment="production",
        recommendations=payload.recommendations,
    )
    
    db.add(benchmark)
    
    # Update prompt benchmark score
    prompt.benchmark_score = payload.overall_score
    prompt.last_benchmark_at = payload.executed_at
    
    await db.flush()
    await db.refresh(benchmark)
    
    # Send Beeper notification
    from hermes.services.notifications import get_beeper_client
    beeper = get_beeper_client()
    await beeper.notify_benchmark_complete(
        prompt_slug=prompt.slug,
        prompt_name=prompt.name,
        score=payload.overall_score,
        previous_score=benchmark.baseline_score,
        recommendations=payload.recommendations,
    )
    
    return {"status": "received", "benchmark_id": str(benchmark.id)}


@router.post("/prompts/{prompt_id}/benchmark/sync", response_model=BenchmarkResponse)
async def run_benchmark_sync(
    prompt_id: uuid.UUID,
    data: BenchmarkRequest,
    user: User = Depends(require_permission("benchmarks:run")),
    db: AsyncSession = Depends(get_db),
):
    """Run a synchronous benchmark on a prompt.
    
    Requires: benchmarks:run permission
    
    For development/testing. Runs mock benchmark inline.
    """
    # Get prompt
    query = select(Prompt).where(Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    # Mock benchmark for development
    import random
    
    overall_score = random.uniform(70, 95)
    dimension_scores = {
        "quality": random.uniform(70, 95),
        "safety": random.uniform(85, 99),
        "latency": random.uniform(60, 90),
        "consistency": random.uniform(75, 95),
    }
    
    benchmark = BenchmarkResult(
        prompt_id=prompt_id,
        prompt_version=prompt.version,
        suite_id=data.suite_id,
        overall_score=overall_score,
        dimension_scores=dimension_scores,
        model_id=data.model_id,
        model_version="1.0.0",
        execution_time_ms=random.randint(100, 500),
        token_usage={"input": random.randint(100, 500), "output": random.randint(200, 1000)},
        baseline_score=prompt.benchmark_score,
        delta=(overall_score - prompt.benchmark_score) if prompt.benchmark_score else None,
        gate_passed=overall_score >= 80.0,
        executed_at=datetime.utcnow(),
        executed_by=user.id,
        environment=data.environment or "development",
    )
    
    db.add(benchmark)
    
    # Update prompt benchmark score
    prompt.benchmark_score = overall_score
    prompt.last_benchmark_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(benchmark)
    
    return benchmark


@router.get("/prompts/{prompt_id}/benchmarks", response_model=BenchmarkListResponse)
async def list_benchmarks(
    prompt_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """List benchmark results for a prompt.
    
    Requires: benchmarks:read permission
    """
    # Count total
    count_query = select(func.count()).select_from(BenchmarkResult).where(
        BenchmarkResult.prompt_id == prompt_id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get results
    query = (
        select(BenchmarkResult)
        .where(BenchmarkResult.prompt_id == prompt_id)
        .order_by(BenchmarkResult.executed_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    result = await db.execute(query)
    benchmarks = list(result.scalars().all())
    
    return BenchmarkListResponse(
        items=[BenchmarkResponse.model_validate(b) for b in benchmarks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/benchmarks/{benchmark_id}", response_model=BenchmarkResponse)
async def get_benchmark(
    benchmark_id: uuid.UUID,
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific benchmark result.
    
    Requires: benchmarks:read permission
    """
    query = select(BenchmarkResult).where(BenchmarkResult.id == benchmark_id)
    result = await db.execute(query)
    benchmark = result.scalar_one_or_none()
    
    if not benchmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark with ID '{benchmark_id}' not found",
        )
    
    return benchmark


# Multi-model benchmark comparison
@router.post("/prompts/{prompt_id}/benchmark/compare", response_model=MultiModelBenchmarkResponse)
async def compare_models(
    prompt_id: uuid.UUID,
    data: MultiModelBenchmarkRequest,
    user: User = Depends(require_permission("benchmarks:run")),
    db: AsyncSession = Depends(get_db),
):
    """Compare benchmark results across multiple models.
    
    Requires: benchmarks:run permission
    
    Runs the same prompt against multiple D3N models and returns
    a comparison matrix showing dimension scores for each model.
    """
    service = BenchmarkService(db)
    
    try:
        result = await service.run_multi_model_benchmark(
            prompt_id=prompt_id,
            model_ids=data.model_ids,
            suite_id=data.suite_id,
            executed_by=user.id,
            parallel=data.parallel,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    return MultiModelBenchmarkResponse(
        id=uuid.uuid4(),
        prompt_id=result.prompt_id,
        prompt_version=result.prompt_version,
        suite_id=result.suite_id,
        model_results=[
            ModelBenchmarkResult(
                model_id=r.model_id,
                model_version=r.model_version,
                overall_score=r.overall_score,
                dimension_scores=r.dimension_scores,
                execution_time_ms=r.execution_time_ms,
                token_usage=r.token_usage,
                gate_passed=r.gate_passed,
            )
            for r in result.model_results
        ],
        best_model=result.best_model,
        best_score=result.best_score,
        comparison_matrix=result.comparison_matrix,
        executed_at=result.executed_at,
        executed_by=user.id,
        environment="staging",
    )


# Benchmark trends
class TrendPointResponse(BaseModel):
    """Single trend data point."""
    timestamp: datetime
    score: float
    version: str
    model_id: str


class BenchmarkTrendsResponse(BaseModel):
    """Benchmark trends analysis response."""
    prompt_id: uuid.UUID
    trend_data: list[TrendPointResponse]
    rolling_avg_7d: Optional[float]
    rolling_avg_30d: Optional[float]
    score_delta_7d: Optional[float]
    score_delta_30d: Optional[float]
    is_regressing: bool
    regression_alert: Optional[str]


@router.get("/prompts/{prompt_id}/benchmark/trends", response_model=BenchmarkTrendsResponse)
async def get_benchmark_trends(
    prompt_id: uuid.UUID,
    days: int = Query(30, ge=7, le=90),
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get benchmark trends and regression analysis for a prompt.
    
    Requires: benchmarks:read permission
    
    Returns rolling averages, score deltas, and regression alerts.
    """
    service = BenchmarkService(db)
    trends = await service.get_benchmark_trends(prompt_id, days=days)
    
    return BenchmarkTrendsResponse(
        prompt_id=trends.prompt_id,
        trend_data=[
            TrendPointResponse(
                timestamp=t.timestamp,
                score=t.score,
                version=t.version,
                model_id=t.model_id,
            )
            for t in trends.trend_data
        ],
        rolling_avg_7d=trends.rolling_avg_7d,
        rolling_avg_30d=trends.rolling_avg_30d,
        score_delta_7d=trends.score_delta_7d,
        score_delta_30d=trends.score_delta_30d,
        is_regressing=trends.is_regressing,
        regression_alert=trends.regression_alert,
    )


class RegressionAlert(BaseModel):
    """Regression alert for a prompt."""
    prompt_id: str
    alert: str
    rolling_avg_7d: Optional[float]
    score_delta_7d: Optional[float]


@router.get("/benchmarks/alerts/regressions", response_model=list[RegressionAlert])
async def get_regression_alerts(
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get all active benchmark regression alerts.
    
    Requires: benchmarks:read permission
    
    Returns prompts with sustained score regressions over the last 7 days.
    """
    service = BenchmarkService(db)
    alerts = await service.check_regression_alerts()
    
    return [RegressionAlert(**a) for a in alerts]
