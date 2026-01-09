"""
Benchmarks API Endpoints

Benchmark execution and results.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models import BenchmarkResult, Prompt
from hermes.schemas.benchmark import (
    BenchmarkListResponse,
    BenchmarkRequest,
    BenchmarkResponse,
)
from hermes.services.database import get_db

router = APIRouter()


# Temporary: Mock user ID until PERSONA integration
def get_current_user_id() -> uuid.UUID:
    """Get current user ID (placeholder for PERSONA integration)."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.post("/prompts/{prompt_id}/benchmark", response_model=BenchmarkResponse)
async def run_benchmark(
    prompt_id: uuid.UUID,
    data: BenchmarkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a benchmark on a prompt."""
    # Get prompt
    query = select(Prompt).where(Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    user_id = get_current_user_id()
    
    # TODO: Integrate with ATE for actual benchmarking
    # For now, create a mock benchmark result
    import random
    
    overall_score = random.uniform(0.7, 0.95)
    dimension_scores = {
        "quality": random.uniform(0.7, 0.95),
        "safety": random.uniform(0.85, 0.99),
        "performance": random.uniform(0.6, 0.9),
        "clarity": random.uniform(0.7, 0.95),
    }
    
    benchmark = BenchmarkResult(
        prompt_id=prompt_id,
        prompt_version=prompt.version,
        suite_id=data.suite_id,
        overall_score=overall_score * 100,
        dimension_scores={k: v * 100 for k, v in dimension_scores.items()},
        model_id=data.model_id,
        model_version="1.0.0",
        execution_time_ms=random.randint(100, 500),
        token_usage={"input": random.randint(100, 500), "output": random.randint(200, 1000)},
        baseline_score=prompt.benchmark_score,
        delta=(overall_score * 100 - prompt.benchmark_score) if prompt.benchmark_score else None,
        gate_passed=overall_score >= 0.8,
        executed_at=datetime.utcnow(),
        executed_by=user_id,
        environment="staging",
    )
    
    db.add(benchmark)
    
    # Update prompt benchmark score
    prompt.benchmark_score = overall_score * 100
    prompt.last_benchmark_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(benchmark)
    
    return benchmark


@router.get("/prompts/{prompt_id}/benchmarks", response_model=BenchmarkListResponse)
async def list_benchmarks(
    prompt_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List benchmark results for a prompt."""
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
        total=len(benchmarks),
        limit=limit,
        offset=offset,
    )


@router.get("/benchmarks/{benchmark_id}", response_model=BenchmarkResponse)
async def get_benchmark(
    benchmark_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific benchmark result."""
    query = select(BenchmarkResult).where(BenchmarkResult.id == benchmark_id)
    result = await db.execute(query)
    benchmark = result.scalar_one_or_none()
    
    if not benchmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark with ID '{benchmark_id}' not found",
        )
    
    return benchmark
