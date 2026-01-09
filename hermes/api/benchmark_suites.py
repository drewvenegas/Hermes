"""
Benchmark Suites API Endpoints

Benchmark suite management.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permission
from hermes.auth.models import User
from hermes.models.benchmark_suite import BenchmarkSuite, BenchmarkTestCase
from hermes.services.benchmark_service import BenchmarkSuiteService
from hermes.services.database import get_db

router = APIRouter()


# Schemas
class TestCaseCreate(BaseModel):
    """Create test case request."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    input_text: str = Field(..., min_length=1)
    expected_output: Optional[str] = None
    expected_patterns: Optional[List[str]] = None
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class TestCaseResponse(BaseModel):
    """Test case response."""
    id: uuid.UUID
    suite_id: uuid.UUID
    name: str
    description: Optional[str]
    input_text: str
    expected_output: Optional[str]
    expected_patterns: Optional[List[Any]]
    weight: float
    category: Optional[str]
    tags: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SuiteCreate(BaseModel):
    """Create suite request."""
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    dimensions: List[str] = Field(default=["quality", "safety", "performance", "clarity"])
    weights: Dict[str, float] = Field(default={"quality": 0.4, "safety": 0.3, "performance": 0.15, "clarity": 0.15})
    threshold: float = Field(default=80.0, ge=0.0, le=100.0)
    test_cases: List[TestCaseCreate] = Field(default_factory=list)


class SuiteUpdate(BaseModel):
    """Update suite request."""
    name: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[List[str]] = None
    weights: Optional[Dict[str, float]] = None
    threshold: Optional[float] = None
    is_active: Optional[bool] = None


class SuiteResponse(BaseModel):
    """Suite response."""
    id: uuid.UUID
    slug: str
    name: str
    description: Optional[str]
    test_cases: List[Dict]
    dimensions: List[str]
    weights: Dict[str, float]
    threshold: float
    owner_id: uuid.UUID
    is_default: bool
    is_active: bool
    version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SuiteListResponse(BaseModel):
    """Paginated suite list."""
    items: List[SuiteResponse]
    total: int
    limit: int
    offset: int


# Endpoints
@router.post("/benchmark-suites", response_model=SuiteResponse, status_code=status.HTTP_201_CREATED)
async def create_suite(
    data: SuiteCreate,
    user: User = Depends(require_permission("benchmarks:run")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new benchmark suite.
    
    Requires: benchmarks:run permission
    """
    service = BenchmarkSuiteService(db)
    
    # Check slug uniqueness
    existing = await service.get_suite_by_slug(data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Suite with slug '{data.slug}' already exists",
        )
    
    suite = await service.create_suite(
        slug=data.slug,
        name=data.name,
        owner_id=user.id,
        description=data.description,
        test_cases=[tc.model_dump() for tc in data.test_cases],
        dimensions=data.dimensions,
        weights=data.weights,
        threshold=data.threshold,
    )
    
    return SuiteResponse.model_validate(suite)


@router.get("/benchmark-suites", response_model=SuiteListResponse)
async def list_suites(
    include_inactive: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """List benchmark suites.
    
    Requires: benchmarks:read permission
    """
    service = BenchmarkSuiteService(db)
    
    suites, total = await service.list_suites(
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )
    
    return SuiteListResponse(
        items=[SuiteResponse.model_validate(s) for s in suites],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/benchmark-suites/default", response_model=SuiteResponse)
async def get_default_suite(
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get the default benchmark suite.
    
    Requires: benchmarks:read permission
    """
    service = BenchmarkSuiteService(db)
    suite = await service.get_default_suite()
    
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default suite configured",
        )
    
    return SuiteResponse.model_validate(suite)


@router.get("/benchmark-suites/{suite_id}", response_model=SuiteResponse)
async def get_suite(
    suite_id: uuid.UUID,
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a benchmark suite by ID.
    
    Requires: benchmarks:read permission
    """
    service = BenchmarkSuiteService(db)
    suite = await service.get_suite(suite_id)
    
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite with ID '{suite_id}' not found",
        )
    
    return SuiteResponse.model_validate(suite)


@router.get("/benchmark-suites/by-slug/{slug}", response_model=SuiteResponse)
async def get_suite_by_slug(
    slug: str,
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a benchmark suite by slug.
    
    Requires: benchmarks:read permission
    """
    service = BenchmarkSuiteService(db)
    suite = await service.get_suite_by_slug(slug)
    
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite with slug '{slug}' not found",
        )
    
    return SuiteResponse.model_validate(suite)


@router.put("/benchmark-suites/{suite_id}", response_model=SuiteResponse)
async def update_suite(
    suite_id: uuid.UUID,
    data: SuiteUpdate,
    user: User = Depends(require_permission("benchmarks:run")),
    db: AsyncSession = Depends(get_db),
):
    """Update a benchmark suite.
    
    Requires: benchmarks:run permission
    """
    service = BenchmarkSuiteService(db)
    
    suite = await service.update_suite(
        suite_id,
        **data.model_dump(exclude_unset=True),
    )
    
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite with ID '{suite_id}' not found",
        )
    
    return SuiteResponse.model_validate(suite)


@router.post("/benchmark-suites/{suite_id}/test-cases", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
async def add_test_case(
    suite_id: uuid.UUID,
    data: TestCaseCreate,
    user: User = Depends(require_permission("benchmarks:run")),
    db: AsyncSession = Depends(get_db),
):
    """Add a test case to a suite.
    
    Requires: benchmarks:run permission
    """
    service = BenchmarkSuiteService(db)
    
    # Verify suite exists
    suite = await service.get_suite(suite_id)
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite with ID '{suite_id}' not found",
        )
    
    test_case = await service.add_test_case(
        suite_id=suite_id,
        name=data.name,
        input_text=data.input_text,
        expected_output=data.expected_output,
        expected_patterns=data.expected_patterns,
        weight=data.weight,
        category=data.category,
    )
    
    return TestCaseResponse.model_validate(test_case)


@router.get("/benchmark-suites/{suite_id}/test-cases", response_model=List[TestCaseResponse])
async def list_test_cases(
    suite_id: uuid.UUID,
    user: User = Depends(require_permission("benchmarks:read")),
    db: AsyncSession = Depends(get_db),
):
    """List test cases for a suite.
    
    Requires: benchmarks:read permission
    """
    service = BenchmarkSuiteService(db)
    test_cases = await service.get_test_cases(suite_id)
    
    return [TestCaseResponse.model_validate(tc) for tc in test_cases]
