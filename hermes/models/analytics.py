"""
Analytics Models

Usage tracking and metrics for prompts and users.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hermes.models.base import Base, TimestampMixin, UUIDMixin


class MetricType(str, Enum):
    """Types of metrics tracked."""
    API_CALL = "api_call"
    PROMPT_USAGE = "prompt_usage"
    BENCHMARK_RUN = "benchmark_run"
    TEMPLATE_RENDER = "template_render"
    SEARCH_QUERY = "search_query"
    LOGIN = "login"
    DEPLOY = "deploy"


class UsageMetric(Base, UUIDMixin, TimestampMixin):
    """
    Usage metrics for analytics.

    Tracks individual events for analytics dashboards.
    
    Attributes:
        id: Metric ID
        metric_type: Type of metric
        user_id: User who triggered the metric
        prompt_id: Related prompt (if applicable)
        model_id: Model used (if applicable)
        value: Metric value (e.g., count, duration)
        metadata: Additional context
    """

    __tablename__ = "usage_metrics"

    # Metric type
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Context
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    prompt_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Value
    value: Mapped[float] = mapped_column(nullable=False, default=1.0)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # count, ms, tokens, etc.

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Time buckets for aggregation
    hour: Mapped[int] = mapped_column(nullable=False)
    day: Mapped[int] = mapped_column(nullable=False)
    week: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_usage_metrics_type_day", "metric_type", "day"),
        Index("ix_usage_metrics_user_type", "user_id", "metric_type"),
        Index("ix_usage_metrics_prompt_type", "prompt_id", "metric_type"),
        Index("ix_usage_metrics_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UsageMetric(type={self.metric_type}, value={self.value})>"


class AggregatedMetric(Base, UUIDMixin, TimestampMixin):
    """
    Pre-aggregated metrics for fast dashboard queries.

    Stores hourly/daily/weekly/monthly rollups.
    
    Attributes:
        id: Aggregate ID
        metric_type: Type of metric
        granularity: hour, day, week, month
        period_start: Start of the period
        total_value: Sum of values in period
        count: Number of events in period
        min_value: Minimum value in period
        max_value: Maximum value in period
        avg_value: Average value in period
    """

    __tablename__ = "aggregated_metrics"

    # Metric type
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Granularity
    granularity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # hour, day, week, month
    period_start: Mapped[datetime] = mapped_column(nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(nullable=False)

    # Dimensions (for slicing)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Aggregated values
    total_value: Mapped[float] = mapped_column(nullable=False, default=0.0)
    count: Mapped[int] = mapped_column(nullable=False, default=0)
    min_value: Mapped[Optional[float]] = mapped_column(nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(nullable=True)
    avg_value: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Unique constraint for upserts
    __table_args__ = (
        Index(
            "ix_agg_metrics_unique",
            "metric_type", "granularity", "period_start", "user_id", "team_id", "prompt_id", "model_id",
            unique=True,
        ),
        Index("ix_agg_metrics_period", "period_start", "granularity"),
    )

    def __repr__(self) -> str:
        return f"<AggregatedMetric(type={self.metric_type}, granularity={self.granularity}, count={self.count})>"
