"""
Benchmark Suite Model

Defines benchmark suites with test cases for prompt evaluation.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hermes.models.base import Base, TimestampMixin, UUIDMixin


class BenchmarkSuite(Base, UUIDMixin, TimestampMixin):
    """
    Benchmark suite definition.

    A suite contains test cases and configuration for evaluating prompts.
    
    Attributes:
        id: Unique suite ID
        slug: URL-friendly identifier
        name: Human-readable name
        description: Suite description
        test_cases: List of test case definitions
        dimensions: Scoring dimensions evaluated
        weights: Dimension weights for overall score
        threshold: Minimum passing score
        model_config: Default model configuration
        owner_id: Suite creator
        is_default: Whether this is the default suite
        is_active: Whether suite is available for use
    """

    __tablename__ = "benchmark_suites"

    # Identity
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Test cases: list of {input, expected_output, metadata}
    test_cases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Scoring configuration
    dimensions: Mapped[list[str]] = mapped_column(
        ARRAY(String), 
        nullable=False, 
        default=["quality", "safety", "performance", "clarity"]
    )
    weights: Mapped[dict] = mapped_column(
        JSONB, 
        nullable=False, 
        default={"quality": 0.4, "safety": 0.3, "performance": 0.15, "clarity": 0.15}
    )
    threshold: Mapped[float] = mapped_column(nullable=False, default=80.0)

    # Model configuration
    model_config_data: Mapped[Optional[dict]] = mapped_column(
        "model_config",
        JSONB, 
        nullable=True
    )

    # Ownership
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Status
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Version tracking
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Indexes
    __table_args__ = (
        Index("ix_benchmark_suites_owner", "owner_id"),
        Index("ix_benchmark_suites_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<BenchmarkSuite(slug={self.slug}, name={self.name})>"


class BenchmarkTestCase(Base, UUIDMixin, TimestampMixin):
    """
    Individual test case for a benchmark suite.
    
    Attributes:
        id: Unique test case ID
        suite_id: Parent suite
        name: Test case name
        description: Test case description
        input_text: Input to send to the prompt
        expected_patterns: Expected patterns/outputs
        scoring_criteria: How to score this test case
        weight: Weight in suite scoring
    """

    __tablename__ = "benchmark_test_cases"

    # Reference
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Test configuration
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_patterns: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    expected_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scoring
    scoring_criteria: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default={"method": "semantic_similarity", "threshold": 0.8}
    )
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)

    # Metadata
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Indexes
    __table_args__ = (
        Index("ix_benchmark_test_cases_suite", "suite_id"),
        Index("ix_benchmark_test_cases_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<BenchmarkTestCase(name={self.name}, suite_id={self.suite_id})>"
