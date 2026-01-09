"""
Benchmark Suite Schemas

Pydantic models for benchmark suite API operations.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TestCaseInput(BaseModel):
    """A single test case in a benchmark suite."""
    
    id: str = Field(..., description="Unique test case ID")
    name: str = Field(..., description="Test case name")
    input: str = Field(..., description="Test input/prompt")
    expected_output: Optional[str] = Field(None, description="Expected output pattern")
    dimensions: list[str] = Field(default_factory=list, description="Dimensions to evaluate")
    weight: float = Field(default=1.0, description="Weight in overall score")
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkSuiteCreate(BaseModel):
    """Schema for creating a benchmark suite."""
    
    name: str = Field(..., description="Suite display name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Suite description")
    category: str = Field(default="general", description="Suite category")
    test_cases: list[TestCaseInput] = Field(default_factory=list)
    dimensions: list[str] = Field(
        default=["quality", "safety", "performance", "clarity"],
        description="Scoring dimensions",
    )
    thresholds: dict[str, float] = Field(
        default={"overall": 0.8, "safety": 0.9},
        description="Pass/fail thresholds",
    )
    is_default: bool = False
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkSuiteUpdate(BaseModel):
    """Schema for updating a benchmark suite."""
    
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    test_cases: Optional[list[TestCaseInput]] = None
    dimensions: Optional[list[str]] = None
    thresholds: Optional[dict[str, float]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class BenchmarkSuiteResponse(BaseModel):
    """Schema for benchmark suite response."""
    
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    category: str
    test_cases: list[dict[str, Any]]
    dimensions: list[str]
    thresholds: dict[str, float]
    is_default: bool
    is_active: bool
    owner_id: uuid.UUID
    version: str
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class BenchmarkSuiteListResponse(BaseModel):
    """Schema for paginated suite list."""
    
    items: list[BenchmarkSuiteResponse]
    total: int
    limit: int
    offset: int


class BenchmarkTrendResponse(BaseModel):
    """Schema for benchmark trend data."""
    
    id: uuid.UUID
    prompt_id: uuid.UUID
    suite_id: str
    model_id: str
    period_start: datetime
    period_end: datetime
    period_type: str
    avg_score: float
    min_score: float
    max_score: float
    score_stddev: float
    dimension_avgs: dict[str, float]
    run_count: int
    pass_count: int
    fail_count: int
    regression_detected: bool
    regression_delta: Optional[float]
    prev_period_avg: Optional[float]
    change_percent: Optional[float]
    
    model_config = {"from_attributes": True}


class TrendChartData(BaseModel):
    """Chart-ready trend data."""
    
    labels: list[str]  # x-axis labels (dates)
    datasets: list[dict[str, Any]]  # Chart.js compatible datasets


class RegressionAlert(BaseModel):
    """Regression alert notification."""
    
    prompt_id: uuid.UUID
    prompt_slug: str
    prompt_name: str
    suite_id: str
    model_id: str
    current_avg: float
    previous_avg: float
    delta: float
    delta_percent: float
    severity: str  # warning, critical
    detected_at: datetime
