"""
Benchmark Result Model

Stores benchmark execution results for prompts.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermes.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from hermes.models.prompt import Prompt


class BenchmarkResult(Base, UUIDMixin):
    """
    Benchmark execution result.

    Attributes:
        id: Unique result ID
        prompt_id: Prompt that was benchmarked
        prompt_version: Version that was benchmarked
        suite_id: Benchmark suite identifier
        overall_score: Aggregate score (0-100)
        dimension_scores: Per-dimension breakdown
        model_id: D3N model used
        model_version: Model version
        execution_time_ms: Benchmark execution time
        token_usage: Token consumption details
        baseline_score: Previous version score (for comparison)
        delta: Improvement/regression delta
        gate_passed: Whether quality gate passed
        executed_at: When benchmark was run
        executed_by: User/agent/system that triggered
        environment: staging or production
    """

    __tablename__ = "benchmark_results"

    # Reference
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Suite info
    suite_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")

    # Scores
    overall_score: Mapped[float] = mapped_column(nullable=False)
    dimension_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Execution context
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(nullable=False)
    token_usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Comparison
    baseline_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    delta: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Quality gate
    gate_passed: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Metadata
    executed_at: Mapped[datetime] = mapped_column(nullable=False)
    executed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="staging")

    # Raw results
    raw_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="benchmark_results")

    # Indexes
    __table_args__ = (
        Index("ix_benchmark_results_prompt_version", "prompt_id", "prompt_version"),
        Index("ix_benchmark_results_executed_at", "executed_at"),
    )

    def __repr__(self) -> str:
        return f"<BenchmarkResult(prompt_id={self.prompt_id}, score={self.overall_score})>"
