"""
Benchmark Schemas

Pydantic models for benchmark API operations.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BenchmarkRequest(BaseModel):
    """Schema for benchmark execution request."""

    suite_id: str = Field(default="default", description="Benchmark suite to run")
    model_id: str = Field(default="aria01-d3n", description="D3N model to use")


class MultiModelBenchmarkRequest(BaseModel):
    """Schema for multi-model benchmark comparison request."""

    suite_id: str = Field(default="default", description="Benchmark suite to run")
    model_ids: list[str] = Field(
        default=["aria01-d3n"],
        description="List of D3N models to compare",
    )
    parallel: bool = Field(default=True, description="Run benchmarks in parallel")


class ModelBenchmarkResult(BaseModel):
    """Benchmark result for a single model."""

    model_id: str
    model_version: Optional[str]
    overall_score: float
    dimension_scores: dict[str, float]
    execution_time_ms: int
    token_usage: Optional[dict[str, Any]]
    gate_passed: bool


class MultiModelBenchmarkResponse(BaseModel):
    """Schema for multi-model comparison response."""

    id: uuid.UUID
    prompt_id: uuid.UUID
    prompt_version: str
    suite_id: str
    model_results: list[ModelBenchmarkResult]
    best_model: str
    best_score: float
    comparison_matrix: dict[str, dict[str, float]]  # model -> dimension -> score
    executed_at: datetime
    executed_by: uuid.UUID
    environment: str


class BenchmarkResponse(BaseModel):
    """Schema for benchmark result response."""

    id: uuid.UUID
    prompt_id: uuid.UUID
    prompt_version: str
    suite_id: str
    overall_score: float
    dimension_scores: dict[str, float]
    model_id: str
    model_version: Optional[str]
    execution_time_ms: int
    token_usage: Optional[dict[str, Any]]
    baseline_score: Optional[float]
    delta: Optional[float]
    gate_passed: bool
    executed_at: datetime
    executed_by: uuid.UUID
    environment: str

    model_config = {"from_attributes": True}


class BenchmarkListResponse(BaseModel):
    """Schema for paginated benchmark list response."""

    items: list[BenchmarkResponse]
    total: int
    limit: int
    offset: int
