"""
Analytics Service

Usage tracking, metric aggregation, and dashboard data.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models.analytics import AggregatedMetric, MetricType, UsageMetric
from hermes.models.benchmark import BenchmarkResult
from hermes.models.collaboration import Activity
from hermes.models.prompt import Prompt

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: float
    label: Optional[str] = None


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    total: float
    count: int
    avg: float
    min_val: Optional[float]
    max_val: Optional[float]
    trend_percent: Optional[float] = None  # vs previous period


@dataclass
class DashboardData:
    """Data for analytics dashboard."""
    total_prompts: int
    total_users: int
    total_benchmarks: int
    avg_benchmark_score: float
    prompts_this_week: int
    benchmarks_this_week: int
    top_prompts: List[Dict[str, Any]]
    benchmark_trends: List[TimeSeriesPoint]
    activity_by_type: Dict[str, int]
    model_usage: Dict[str, int]


class AnalyticsService:
    """Service for analytics and metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_metric(
        self,
        metric_type: MetricType,
        value: float = 1.0,
        user_id: Optional[uuid.UUID] = None,
        team_id: Optional[uuid.UUID] = None,
        prompt_id: Optional[uuid.UUID] = None,
        template_id: Optional[uuid.UUID] = None,
        model_id: Optional[str] = None,
        unit: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a usage metric event."""
        now = datetime.utcnow()
        
        metric = UsageMetric(
            metric_type=metric_type.value,
            user_id=user_id,
            team_id=team_id,
            prompt_id=prompt_id,
            template_id=template_id,
            model_id=model_id,
            value=value,
            unit=unit,
            metadata=metadata,
            hour=now.hour,
            day=now.day,
            week=now.isocalendar()[1],
            month=now.month,
            year=now.year,
        )
        
        self.db.add(metric)
        await self.db.flush()

    async def get_metric_summary(
        self,
        metric_type: MetricType,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[uuid.UUID] = None,
        prompt_id: Optional[uuid.UUID] = None,
    ) -> MetricSummary:
        """Get summary statistics for a metric over a time range."""
        query = (
            select(
                func.sum(UsageMetric.value).label("total"),
                func.count(UsageMetric.id).label("count"),
                func.avg(UsageMetric.value).label("avg"),
                func.min(UsageMetric.value).label("min_val"),
                func.max(UsageMetric.value).label("max_val"),
            )
            .where(UsageMetric.metric_type == metric_type.value)
            .where(UsageMetric.created_at >= start_date)
            .where(UsageMetric.created_at < end_date)
        )
        
        if user_id:
            query = query.where(UsageMetric.user_id == user_id)
        if prompt_id:
            query = query.where(UsageMetric.prompt_id == prompt_id)
        
        result = await self.db.execute(query)
        row = result.fetchone()
        
        if not row or row.count == 0:
            return MetricSummary(total=0, count=0, avg=0, min_val=None, max_val=None)
        
        # Calculate trend vs previous period
        period_length = end_date - start_date
        prev_start = start_date - period_length
        prev_end = start_date
        
        prev_query = (
            select(func.sum(UsageMetric.value))
            .where(UsageMetric.metric_type == metric_type.value)
            .where(UsageMetric.created_at >= prev_start)
            .where(UsageMetric.created_at < prev_end)
        )
        
        if user_id:
            prev_query = prev_query.where(UsageMetric.user_id == user_id)
        if prompt_id:
            prev_query = prev_query.where(UsageMetric.prompt_id == prompt_id)
        
        prev_result = await self.db.execute(prev_query)
        prev_total = prev_result.scalar() or 0
        
        trend_percent = None
        if prev_total > 0:
            trend_percent = ((row.total - prev_total) / prev_total) * 100
        
        return MetricSummary(
            total=row.total or 0,
            count=row.count or 0,
            avg=row.avg or 0,
            min_val=row.min_val,
            max_val=row.max_val,
            trend_percent=trend_percent,
        )

    async def get_time_series(
        self,
        metric_type: MetricType,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "day",  # hour, day, week
        user_id: Optional[uuid.UUID] = None,
        prompt_id: Optional[uuid.UUID] = None,
    ) -> List[TimeSeriesPoint]:
        """Get time series data for a metric."""
        # Determine date truncation
        if granularity == "hour":
            date_trunc = "hour"
        elif granularity == "week":
            date_trunc = "week"
        else:
            date_trunc = "day"
        
        query = (
            select(
                func.date_trunc(date_trunc, UsageMetric.created_at).label("period"),
                func.sum(UsageMetric.value).label("total"),
            )
            .where(UsageMetric.metric_type == metric_type.value)
            .where(UsageMetric.created_at >= start_date)
            .where(UsageMetric.created_at < end_date)
            .group_by("period")
            .order_by("period")
        )
        
        if user_id:
            query = query.where(UsageMetric.user_id == user_id)
        if prompt_id:
            query = query.where(UsageMetric.prompt_id == prompt_id)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        return [
            TimeSeriesPoint(timestamp=row.period, value=row.total or 0)
            for row in rows
        ]

    async def get_benchmark_trends(
        self,
        days: int = 30,
        model_id: Optional[str] = None,
    ) -> List[TimeSeriesPoint]:
        """Get benchmark score trends over time."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(
                func.date_trunc("day", BenchmarkResult.executed_at).label("period"),
                func.avg(BenchmarkResult.overall_score).label("avg_score"),
            )
            .where(BenchmarkResult.executed_at >= cutoff)
            .group_by("period")
            .order_by("period")
        )
        
        if model_id:
            query = query.where(BenchmarkResult.model_id == model_id)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        return [
            TimeSeriesPoint(timestamp=row.period, value=row.avg_score or 0)
            for row in rows
        ]

    async def get_top_prompts(
        self,
        limit: int = 10,
        metric: str = "benchmark_score",  # benchmark_score, usage_count
    ) -> List[Dict[str, Any]]:
        """Get top prompts by a metric."""
        if metric == "usage_count":
            query = (
                select(
                    Prompt.id,
                    Prompt.slug,
                    Prompt.name,
                    func.count(UsageMetric.id).label("usage_count"),
                )
                .outerjoin(UsageMetric, UsageMetric.prompt_id == Prompt.id)
                .group_by(Prompt.id, Prompt.slug, Prompt.name)
                .order_by(func.count(UsageMetric.id).desc())
                .limit(limit)
            )
        else:
            query = (
                select(
                    Prompt.id,
                    Prompt.slug,
                    Prompt.name,
                    Prompt.benchmark_score,
                )
                .where(Prompt.benchmark_score.isnot(None))
                .order_by(Prompt.benchmark_score.desc())
                .limit(limit)
            )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        if metric == "usage_count":
            return [
                {"id": str(row.id), "slug": row.slug, "name": row.name, "usage_count": row.usage_count}
                for row in rows
            ]
        else:
            return [
                {"id": str(row.id), "slug": row.slug, "name": row.name, "benchmark_score": row.benchmark_score}
                for row in rows
            ]

    async def get_activity_by_type(
        self,
        days: int = 30,
        team_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, int]:
        """Get activity counts by type."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(
                Activity.activity_type,
                func.count(Activity.id).label("count"),
            )
            .where(Activity.created_at >= cutoff)
            .group_by(Activity.activity_type)
        )
        
        if team_id:
            query = query.where(Activity.team_id == team_id)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        return {row.activity_type: row.count for row in rows}

    async def get_model_usage(
        self,
        days: int = 30,
    ) -> Dict[str, int]:
        """Get benchmark runs by model."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(
                BenchmarkResult.model_id,
                func.count(BenchmarkResult.id).label("count"),
            )
            .where(BenchmarkResult.executed_at >= cutoff)
            .group_by(BenchmarkResult.model_id)
            .order_by(func.count(BenchmarkResult.id).desc())
        )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        return {row.model_id: row.count for row in rows}

    async def get_dashboard_data(
        self,
        team_id: Optional[uuid.UUID] = None,
    ) -> DashboardData:
        """Get data for the analytics dashboard."""
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        
        # Total prompts
        total_prompts_query = select(func.count(Prompt.id))
        total_prompts = (await self.db.execute(total_prompts_query)).scalar() or 0
        
        # Prompts this week
        prompts_week_query = select(func.count(Prompt.id)).where(Prompt.created_at >= week_ago)
        prompts_this_week = (await self.db.execute(prompts_week_query)).scalar() or 0
        
        # Total benchmarks
        total_benchmarks_query = select(func.count(BenchmarkResult.id))
        total_benchmarks = (await self.db.execute(total_benchmarks_query)).scalar() or 0
        
        # Benchmarks this week
        benchmarks_week_query = select(func.count(BenchmarkResult.id)).where(
            BenchmarkResult.executed_at >= week_ago
        )
        benchmarks_this_week = (await self.db.execute(benchmarks_week_query)).scalar() or 0
        
        # Average benchmark score
        avg_score_query = select(func.avg(BenchmarkResult.overall_score))
        avg_benchmark_score = (await self.db.execute(avg_score_query)).scalar() or 0
        
        # Unique users (from activities)
        total_users_query = select(func.count(func.distinct(Activity.actor_id)))
        total_users = (await self.db.execute(total_users_query)).scalar() or 0
        
        # Top prompts by benchmark score
        top_prompts = await self.get_top_prompts(limit=5)
        
        # Benchmark trends
        benchmark_trends = await self.get_benchmark_trends(days=30)
        
        # Activity by type
        activity_by_type = await self.get_activity_by_type(days=30, team_id=team_id)
        
        # Model usage
        model_usage = await self.get_model_usage(days=30)
        
        return DashboardData(
            total_prompts=total_prompts,
            total_users=total_users,
            total_benchmarks=total_benchmarks,
            avg_benchmark_score=avg_benchmark_score,
            prompts_this_week=prompts_this_week,
            benchmarks_this_week=benchmarks_this_week,
            top_prompts=top_prompts,
            benchmark_trends=benchmark_trends,
            activity_by_type=activity_by_type,
            model_usage=model_usage,
        )

    async def get_user_stats(
        self,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get statistics for a specific user."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Prompts created
        prompts_query = (
            select(func.count(Prompt.id))
            .where(Prompt.owner_id == user_id)
            .where(Prompt.created_at >= cutoff)
        )
        prompts_created = (await self.db.execute(prompts_query)).scalar() or 0
        
        # Benchmarks run
        benchmarks_query = (
            select(func.count(BenchmarkResult.id))
            .where(BenchmarkResult.executed_by == user_id)
            .where(BenchmarkResult.executed_at >= cutoff)
        )
        benchmarks_run = (await self.db.execute(benchmarks_query)).scalar() or 0
        
        # Reviews submitted
        from hermes.models.collaboration import Review
        reviews_query = (
            select(func.count(Review.id))
            .where(Review.reviewer_id == user_id)
            .where(Review.created_at >= cutoff)
        )
        reviews_submitted = (await self.db.execute(reviews_query)).scalar() or 0
        
        # Comments made
        from hermes.models.collaboration import Comment
        comments_query = (
            select(func.count(Comment.id))
            .where(Comment.author_id == user_id)
            .where(Comment.created_at >= cutoff)
        )
        comments_made = (await self.db.execute(comments_query)).scalar() or 0
        
        # Activity count
        activity_query = (
            select(func.count(Activity.id))
            .where(Activity.actor_id == user_id)
            .where(Activity.created_at >= cutoff)
        )
        activity_count = (await self.db.execute(activity_query)).scalar() or 0
        
        return {
            "prompts_created": prompts_created,
            "benchmarks_run": benchmarks_run,
            "reviews_submitted": reviews_submitted,
            "comments_made": comments_made,
            "activity_count": activity_count,
            "period_days": days,
        }
