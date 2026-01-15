"""
Experiments API

REST API endpoints for A/B testing and prompt experiments.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permissions
from hermes.auth.models import User
from hermes.services.database import get_db
from hermes.services.ab_testing import (
    ABTestingService,
    Experiment,
    ExperimentStatus,
    TrafficSplitStrategy,
    get_ab_testing_service,
)

router = APIRouter(prefix="/experiments", tags=["Experiments"])


# =============================================================================
# Request/Response Models
# =============================================================================

class VariantCreate(BaseModel):
    """Request model for creating a variant."""
    name: str = Field(..., description="Variant name")
    prompt_id: str = Field(..., description="Prompt UUID")
    prompt_version: str = Field("latest", description="Prompt version")
    weight: float = Field(0.5, ge=0, le=1, description="Traffic weight")
    is_control: bool = Field(False, description="Is this the control variant")


class MetricCreate(BaseModel):
    """Request model for creating a metric."""
    name: str = Field(..., description="Metric name")
    type: str = Field("conversion", description="Metric type")
    goal: str = Field("maximize", description="Optimization goal")
    is_primary: bool = Field(False, description="Is primary metric")


class ExperimentCreate(BaseModel):
    """Request model for creating an experiment."""
    name: str = Field(..., description="Experiment name")
    description: str = Field("", description="Experiment description")
    variants: List[VariantCreate] = Field(..., min_length=2)
    metrics: List[MetricCreate] = Field(..., min_length=1)
    traffic_split: str = Field("equal", description="Traffic split strategy")
    traffic_percentage: float = Field(100, ge=0, le=100)
    min_sample_size: int = Field(1000, ge=100)
    max_duration_days: int = Field(14, ge=1, le=90)
    confidence_threshold: float = Field(0.95, ge=0.8, le=0.99)
    auto_promote: bool = Field(False)


class ExperimentResponse(BaseModel):
    """Response model for experiment."""
    id: str
    name: str
    description: str
    status: str
    variants: List[Dict[str, Any]]
    metrics: List[Dict[str, Any]]
    traffic_split: str
    traffic_percentage: float
    min_sample_size: int
    max_duration_days: int
    confidence_threshold: float
    auto_promote: bool
    created_at: str
    started_at: Optional[str]
    ended_at: Optional[str]


class ExperimentStatsResponse(BaseModel):
    """Response model for experiment statistics."""
    experiment_id: str
    status: str
    duration_hours: float
    variants: Dict[str, Dict[str, Any]]
    is_significant: bool
    confidence: float
    p_value: float
    recommended_action: str


class RecordEventRequest(BaseModel):
    """Request model for recording an event."""
    user_id: str = Field(..., description="User identifier")
    value: float = Field(1.0, description="Event value")


# =============================================================================
# Experiment Management
# =============================================================================

@router.post(
    "/",
    response_model=ExperimentResponse,
    summary="Create a new experiment",
)
async def create_experiment(
    data: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["experiments:write"])),
):
    """Create a new A/B experiment."""
    service = get_ab_testing_service(db)
    
    try:
        traffic_split = TrafficSplitStrategy(data.traffic_split)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid traffic split. Must be one of: {[s.value for s in TrafficSplitStrategy]}"
        )
    
    experiment = await service.create_experiment(
        name=data.name,
        description=data.description,
        variants=[v.model_dump() for v in data.variants],
        metrics=[m.model_dump() for m in data.metrics],
        traffic_split=traffic_split,
        traffic_percentage=data.traffic_percentage,
        min_sample_size=data.min_sample_size,
        max_duration_days=data.max_duration_days,
        confidence_threshold=data.confidence_threshold,
        auto_promote=data.auto_promote,
    )
    
    return _experiment_to_response(experiment)


@router.get(
    "/",
    response_model=List[ExperimentResponse],
    summary="List experiments",
)
async def list_experiments(
    status: Optional[str] = Query(None, description="Filter by status"),
    prompt_id: Optional[str] = Query(None, description="Filter by prompt ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List experiments with optional filtering."""
    service = get_ab_testing_service(db)
    
    status_filter = None
    if status:
        try:
            status_filter = ExperimentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    
    prompt_filter = uuid.UUID(prompt_id) if prompt_id else None
    
    experiments = await service.list_experiments(
        status=status_filter,
        prompt_id=prompt_filter,
    )
    
    return [_experiment_to_response(e) for e in experiments]


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Get experiment details",
)
async def get_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get experiment details."""
    service = get_ab_testing_service(db)
    experiment = await service.get_experiment(experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return _experiment_to_response(experiment)


@router.post(
    "/{experiment_id}/start",
    response_model=ExperimentResponse,
    summary="Start an experiment",
)
async def start_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["experiments:write"])),
):
    """Start a draft experiment."""
    service = get_ab_testing_service(db)
    
    try:
        experiment = await service.start_experiment(experiment_id)
        return _experiment_to_response(experiment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{experiment_id}/pause",
    response_model=ExperimentResponse,
    summary="Pause an experiment",
)
async def pause_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["experiments:write"])),
):
    """Pause a running experiment."""
    service = get_ab_testing_service(db)
    
    try:
        experiment = await service.pause_experiment(experiment_id)
        return _experiment_to_response(experiment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{experiment_id}/resume",
    response_model=ExperimentResponse,
    summary="Resume an experiment",
)
async def resume_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["experiments:write"])),
):
    """Resume a paused experiment."""
    service = get_ab_testing_service(db)
    
    try:
        experiment = await service.resume_experiment(experiment_id)
        return _experiment_to_response(experiment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{experiment_id}/stop",
    response_model=ExperimentResponse,
    summary="Stop an experiment",
)
async def stop_experiment(
    experiment_id: uuid.UUID,
    compute_results: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["experiments:write"])),
):
    """Stop an experiment and compute final results."""
    service = get_ab_testing_service(db)
    
    try:
        experiment = await service.stop_experiment(
            experiment_id, compute_results=compute_results
        )
        return _experiment_to_response(experiment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Statistics & Analysis
# =============================================================================

@router.get(
    "/{experiment_id}/stats",
    response_model=ExperimentStatsResponse,
    summary="Get experiment statistics",
)
async def get_experiment_stats(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get real-time experiment statistics."""
    service = get_ab_testing_service(db)
    
    stats = await service.get_experiment_stats(experiment_id)
    
    if not stats:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return ExperimentStatsResponse(
        experiment_id=stats["experiment_id"],
        status=stats["status"],
        duration_hours=stats["duration_hours"],
        variants=stats["variants"],
        is_significant=stats["is_significant"],
        confidence=stats.get("confidence", 0),
        p_value=stats.get("p_value", 1.0),
        recommended_action=stats["recommended_action"],
    )


# =============================================================================
# Traffic Assignment
# =============================================================================

@router.get(
    "/assign/{prompt_id}",
    summary="Assign a variant for a user",
)
async def assign_variant(
    prompt_id: uuid.UUID,
    user_id: str = Query(..., description="User identifier"),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign a variant for a user requesting a prompt.
    
    Returns the assigned variant or null if not in an experiment.
    """
    service = get_ab_testing_service(db)
    
    variant = await service.assign_variant(prompt_id, user_id)
    
    if not variant:
        return {"in_experiment": False, "variant": None}
    
    return {
        "in_experiment": True,
        "variant": {
            "id": variant.id,
            "name": variant.name,
            "prompt_id": str(variant.prompt_id),
            "prompt_version": variant.prompt_version,
        },
    }


# =============================================================================
# Event Recording
# =============================================================================

@router.post(
    "/{experiment_id}/variants/{variant_id}/impression",
    summary="Record an impression",
)
async def record_impression(
    experiment_id: uuid.UUID,
    variant_id: str,
    event: RecordEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record that a variant was shown to a user."""
    service = get_ab_testing_service(db)
    
    await service.record_impression(experiment_id, variant_id, event.user_id)
    
    return {"status": "recorded"}


@router.post(
    "/{experiment_id}/variants/{variant_id}/conversion",
    summary="Record a conversion",
)
async def record_conversion(
    experiment_id: uuid.UUID,
    variant_id: str,
    event: RecordEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a conversion event for a variant."""
    service = get_ab_testing_service(db)
    
    await service.record_conversion(
        experiment_id, variant_id, event.user_id, event.value
    )
    
    return {"status": "recorded"}


@router.post(
    "/{experiment_id}/check-promote",
    summary="Check and auto-promote winner",
)
async def check_and_promote(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["experiments:write"])),
):
    """
    Check if experiment has a significant winner and auto-promote if configured.
    """
    service = get_ab_testing_service(db)
    
    promoted = await service.check_and_promote(experiment_id)
    
    return {"promoted": promoted}


# =============================================================================
# Helpers
# =============================================================================

def _experiment_to_response(experiment: Experiment) -> ExperimentResponse:
    """Convert experiment to response model."""
    data = experiment.to_dict()
    return ExperimentResponse(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        status=data["status"],
        variants=data["variants"],
        metrics=data["metrics"],
        traffic_split=data["traffic_split"],
        traffic_percentage=data["traffic_percentage"],
        min_sample_size=data["min_sample_size"],
        max_duration_days=data["max_duration_days"],
        confidence_threshold=data["confidence_threshold"],
        auto_promote=data["auto_promote"],
        created_at=data["created_at"],
        started_at=data["started_at"],
        ended_at=data["ended_at"],
    )
