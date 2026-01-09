"""
Analytics API Endpoints

Usage metrics, trends, and dashboard data.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permission
from hermes.auth.models import User
from hermes.models.analytics import MetricType
from hermes.services.analytics_service import AnalyticsService
from hermes.services.database import get_db

router = APIRouter()


# Schemas
class TimeSeriesPointResponse(BaseModel):
    """Time series data point."""
    timestamp: datetime
    value: float
    label: Optional[str] = None


class MetricSummaryResponse(BaseModel):
    """Metric summary statistics."""
    total: float
    count: int
    avg: float
    min_val: Optional[float]
    max_val: Optional[float]
    trend_percent: Optional[float] = None


class DashboardResponse(BaseModel):
    """Dashboard data response."""
    total_prompts: int
    total_users: int
    total_benchmarks: int
    avg_benchmark_score: float
    prompts_this_week: int
    benchmarks_this_week: int
    top_prompts: List[Dict[str, Any]]
    benchmark_trends: List[TimeSeriesPointResponse]
    activity_by_type: Dict[str, int]
    model_usage: Dict[str, int]


class UserStatsResponse(BaseModel):
    """User statistics response."""
    prompts_created: int
    benchmarks_run: int
    reviews_submitted: int
    comments_made: int
    activity_count: int
    period_days: int


# Endpoints
@router.get("/analytics/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    team_id: Optional[uuid.UUID] = Query(None),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get analytics dashboard data.
    
    Requires: prompts:read permission
    
    Returns aggregate metrics, trends, and top performers.
    """
    service = AnalyticsService(db)
    data = await service.get_dashboard_data(team_id=team_id)
    
    return DashboardResponse(
        total_prompts=data.total_prompts,
        total_users=data.total_users,
        total_benchmarks=data.total_benchmarks,
        avg_benchmark_score=data.avg_benchmark_score,
        prompts_this_week=data.prompts_this_week,
        benchmarks_this_week=data.benchmarks_this_week,
        top_prompts=data.top_prompts,
        benchmark_trends=[
            TimeSeriesPointResponse(timestamp=t.timestamp, value=t.value, label=t.label)
            for t in data.benchmark_trends
        ],
        activity_by_type=data.activity_by_type,
        model_usage=data.model_usage,
    )


@router.get("/analytics/user", response_model=UserStatsResponse)
async def get_user_stats(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's activity statistics.
    
    Requires: prompts:read permission
    """
    service = AnalyticsService(db)
    stats = await service.get_user_stats(user.id, days=days)
    return UserStatsResponse(**stats)


@router.get("/analytics/user/{user_id}", response_model=UserStatsResponse)
async def get_user_stats_by_id(
    user_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user's activity statistics.
    
    Requires: prompts:read permission
    """
    service = AnalyticsService(db)
    stats = await service.get_user_stats(user_id, days=days)
    return UserStatsResponse(**stats)


@router.get("/analytics/metrics/{metric_type}/summary", response_model=MetricSummaryResponse)
async def get_metric_summary(
    metric_type: str,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    prompt_id: Optional[uuid.UUID] = Query(None),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get summary statistics for a metric.
    
    Requires: prompts:read permission
    """
    try:
        mt = MetricType(metric_type)
    except ValueError:
        mt = MetricType.API_CALL  # Default fallback
    
    service = AnalyticsService(db)
    summary = await service.get_metric_summary(
        metric_type=mt,
        start_date=start_date,
        end_date=end_date,
        user_id=user.id,
        prompt_id=prompt_id,
    )
    
    return MetricSummaryResponse(
        total=summary.total,
        count=summary.count,
        avg=summary.avg,
        min_val=summary.min_val,
        max_val=summary.max_val,
        trend_percent=summary.trend_percent,
    )


@router.get("/analytics/metrics/{metric_type}/timeseries", response_model=List[TimeSeriesPointResponse])
async def get_metric_timeseries(
    metric_type: str,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    granularity: str = Query("day", regex="^(hour|day|week)$"),
    prompt_id: Optional[uuid.UUID] = Query(None),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get time series data for a metric.
    
    Requires: prompts:read permission
    """
    try:
        mt = MetricType(metric_type)
    except ValueError:
        mt = MetricType.API_CALL
    
    service = AnalyticsService(db)
    data = await service.get_time_series(
        metric_type=mt,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        user_id=user.id,
        prompt_id=prompt_id,
    )
    
    return [
        TimeSeriesPointResponse(timestamp=t.timestamp, value=t.value, label=t.label)
        for t in data
    ]


@router.get("/analytics/benchmarks/trends", response_model=List[TimeSeriesPointResponse])
async def get_benchmark_trends(
    days: int = Query(30, ge=7, le=90),
    model_id: Optional[str] = Query(None),
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get benchmark score trends over time.
    
    Requires: benchmarks:read permission
    """
    service = AnalyticsService(db)
    data = await service.get_benchmark_trends(days=days, model_id=model_id)
    
    return [
        TimeSeriesPointResponse(timestamp=t.timestamp, value=t.value, label=t.label)
        for t in data
    ]


@router.get("/analytics/prompts/top", response_model=List[Dict[str, Any]])
async def get_top_prompts(
    limit: int = Query(10, ge=1, le=50),
    metric: str = Query("benchmark_score", regex="^(benchmark_score|usage_count)$"),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get top prompts by a metric.
    
    Requires: prompts:read permission
    """
    service = AnalyticsService(db)
    return await service.get_top_prompts(limit=limit, metric=metric)


@router.get("/analytics/activity/by-type", response_model=Dict[str, int])
async def get_activity_by_type(
    days: int = Query(30, ge=1, le=90),
    team_id: Optional[uuid.UUID] = Query(None),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get activity counts by type.
    
    Requires: prompts:read permission
    """
    service = AnalyticsService(db)
    return await service.get_activity_by_type(days=days, team_id=team_id)


@router.get("/analytics/models/usage", response_model=Dict[str, int])
async def get_model_usage(
    days: int = Query(30, ge=1, le=90),
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get benchmark runs by model.
    
    Requires: benchmarks:read permission
    """
    service = AnalyticsService(db)
    return await service.get_model_usage(days=days)
