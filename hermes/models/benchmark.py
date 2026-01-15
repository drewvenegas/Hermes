"""
Benchmark Result Model

Stores benchmark execution results for prompts.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String, Text
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
        gate_threshold: The threshold used for the gate
        is_regression: Whether this result represents a regression
        content_hash: SHA-256 hash of prompt content
        executed_at: When benchmark was run
        executed_by: User/agent/system that triggered
        environment: staging, production, or simulation
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
    gate_threshold: Mapped[Optional[float]] = mapped_column(nullable=True, default=0.8)
    is_regression: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Content integrity
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Metadata
    executed_at: Mapped[datetime] = mapped_column(nullable=False)
    executed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="staging")

    # Raw results
    raw_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="benchmark_results")

    # Indexes
    __table_args__ = (
        Index("ix_benchmark_results_prompt_version", "prompt_id", "prompt_version"),
        Index("ix_benchmark_results_executed_at", "executed_at"),
        Index("ix_benchmark_results_gate_passed", "gate_passed"),
        Index("ix_benchmark_results_is_regression", "is_regression"),
        Index("ix_benchmark_results_suite_id", "suite_id"),
    )

    def __repr__(self) -> str:
        return f"<BenchmarkResult(prompt_id={self.prompt_id}, score={self.overall_score}, gate={self.gate_passed})>"

    @property
    def passed_threshold(self) -> bool:
        """Check if score meets threshold."""
        if self.gate_threshold is None:
            return True
        return self.overall_score >= (self.gate_threshold * 100)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "prompt_id": str(self.prompt_id),
            "prompt_version": self.prompt_version,
            "suite_id": self.suite_id,
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "execution_time_ms": self.execution_time_ms,
            "token_usage": self.token_usage,
            "baseline_score": self.baseline_score,
            "delta": self.delta,
            "gate_passed": self.gate_passed,
            "gate_threshold": self.gate_threshold,
            "is_regression": self.is_regression,
            "content_hash": self.content_hash,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "executed_by": str(self.executed_by),
            "environment": self.environment,
            "error": self.error,
        }
