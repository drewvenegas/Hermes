"""
Quality Gates API

REST API endpoints for quality gate management and evaluation.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permissions
from hermes.auth.models import User
from hermes.services.database import get_db
from hermes.services.prompt_store import PromptStoreService
from hermes.services.quality_gates import (
    GateConfig,
    GateStatus,
    GateType,
    QualityGateService,
    get_quality_gate_service,
)

router = APIRouter(prefix="/quality-gates", tags=["Quality Gates"])


# =============================================================================
# Request/Response Models
# =============================================================================

class GateConfigCreate(BaseModel):
    """Request model for creating a gate."""
    id: str = Field(..., description="Unique gate identifier")
    name: str = Field(..., description="Human-readable gate name")
    gate_type: str = Field(..., description="Type of gate")
    enabled: bool = Field(True)
    blocking: bool = Field(True, description="Whether gate failure blocks deployment")
    threshold: float = Field(0.8, ge=0, le=1)
    dimension: Optional[str] = Field(None, description="For dimension-specific gates")
    max_age_hours: int = Field(24, description="For freshness gates")
    regression_threshold: float = Field(5.0, description="Percentage drop threshold")


class GateConfigResponse(BaseModel):
    """Response model for gate configuration."""
    id: str
    name: str
    gate_type: str
    enabled: bool
    blocking: bool
    threshold: float
    dimension: Optional[str]
    max_age_hours: int
    regression_threshold: float

    class Config:
        from_attributes = True


class GateEvaluationResponse(BaseModel):
    """Response model for a single gate evaluation."""
    gate_id: str
    gate_name: str
    gate_type: str
    status: str
    blocking: bool
    message: str
    details: Dict[str, Any]


class GateReportResponse(BaseModel):
    """Response model for complete gate evaluation report."""
    prompt_id: str
    prompt_version: str
    overall_status: str
    can_deploy: bool
    evaluations: List[GateEvaluationResponse]
    summary: str
    evaluated_at: str
    metadata: Dict[str, Any]


class DeploymentReadinessResponse(BaseModel):
    """Response model for deployment readiness check."""
    ready: bool
    gate_report: GateReportResponse
    blockers: List[str]
    warnings: List[str]
    recommendations: List[str]


# =============================================================================
# Gate Evaluation Endpoints
# =============================================================================

@router.post(
    "/evaluate/{prompt_id}",
    response_model=GateReportResponse,
    summary="Evaluate quality gates for a prompt",
)
async def evaluate_gates(
    prompt_id: uuid.UUID,
    environment: str = Query("production", description="Target deployment environment"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Evaluate all quality gates for a prompt.
    
    Returns a complete report of all gate evaluations and overall deployment eligibility.
    """
    # Get prompt
    store = PromptStoreService(db)
    prompt = await store.get(prompt_id)
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Evaluate gates
    service = get_quality_gate_service(db)
    report = await service.evaluate_gates(prompt, target_environment=environment)
    
    return GateReportResponse(
        prompt_id=str(report.prompt_id),
        prompt_version=report.prompt_version,
        overall_status=report.overall_status.value,
        can_deploy=report.can_deploy,
        evaluations=[
            GateEvaluationResponse(
                gate_id=e.gate_id,
                gate_name=e.gate_name,
                gate_type=e.gate_type.value,
                status=e.status.value,
                blocking=e.blocking,
                message=e.message,
                details=e.details,
            )
            for e in report.evaluations
        ],
        summary=report.summary,
        evaluated_at=report.evaluated_at.isoformat(),
        metadata=report.metadata,
    )


@router.get(
    "/readiness/{prompt_id}",
    response_model=DeploymentReadinessResponse,
    summary="Check deployment readiness",
)
async def check_deployment_readiness(
    prompt_id: uuid.UUID,
    environment: str = Query("production"),
    target_apps: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Check if a prompt is ready for deployment.
    
    Evaluates quality gates and provides actionable recommendations.
    """
    store = PromptStoreService(db)
    prompt = await store.get(prompt_id)
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    service = get_quality_gate_service(db)
    report = await service.evaluate_gates(prompt, target_environment=environment)
    
    # Build readiness response
    blockers = []
    warnings = []
    recommendations = []
    
    for evaluation in report.evaluations:
        if evaluation.status == GateStatus.FAILED:
            if evaluation.blocking:
                blockers.append(f"{evaluation.gate_name}: {evaluation.message}")
            else:
                warnings.append(f"{evaluation.gate_name}: {evaluation.message}")
        elif evaluation.status == GateStatus.WARNING:
            warnings.append(f"{evaluation.gate_name}: {evaluation.message}")
        elif evaluation.status == GateStatus.PENDING:
            recommendations.append(f"Run benchmark to satisfy: {evaluation.gate_name}")
        
        # Add recommendations from details
        if "recommendation" in evaluation.details:
            recommendations.append(evaluation.details["recommendation"])
    
    # Add general recommendations
    if not report.can_deploy:
        if any(e.status == GateStatus.PENDING for e in report.evaluations):
            recommendations.append("Run a benchmark before deployment")
        if any("safety" in (e.details.get("dimension", "") or "") for e in report.evaluations if e.status == GateStatus.FAILED):
            recommendations.append("Review and improve safety-related content")
    
    return DeploymentReadinessResponse(
        ready=report.can_deploy,
        gate_report=GateReportResponse(
            prompt_id=str(report.prompt_id),
            prompt_version=report.prompt_version,
            overall_status=report.overall_status.value,
            can_deploy=report.can_deploy,
            evaluations=[
                GateEvaluationResponse(
                    gate_id=e.gate_id,
                    gate_name=e.gate_name,
                    gate_type=e.gate_type.value,
                    status=e.status.value,
                    blocking=e.blocking,
                    message=e.message,
                    details=e.details,
                )
                for e in report.evaluations
            ],
            summary=report.summary,
            evaluated_at=report.evaluated_at.isoformat(),
            metadata=report.metadata,
        ),
        blockers=blockers,
        warnings=warnings,
        recommendations=list(set(recommendations)),  # Dedupe
    )


# =============================================================================
# Gate Configuration Endpoints
# =============================================================================

@router.get(
    "/",
    response_model=List[GateConfigResponse],
    summary="List all quality gates",
)
async def list_gates(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all configured quality gates."""
    service = get_quality_gate_service(db)
    gates = service.get_all_gates()
    
    return [
        GateConfigResponse(
            id=g.id,
            name=g.name,
            gate_type=g.gate_type.value,
            enabled=g.enabled,
            blocking=g.blocking,
            threshold=g.threshold,
            dimension=g.dimension,
            max_age_hours=g.max_age_hours,
            regression_threshold=g.regression_threshold,
        )
        for g in gates
    ]


@router.get(
    "/{gate_id}",
    response_model=GateConfigResponse,
    summary="Get a specific gate",
)
async def get_gate(
    gate_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific quality gate configuration."""
    service = get_quality_gate_service(db)
    gate = service.get_gate(gate_id)
    
    if not gate:
        raise HTTPException(status_code=404, detail="Gate not found")
    
    return GateConfigResponse(
        id=gate.id,
        name=gate.name,
        gate_type=gate.gate_type.value,
        enabled=gate.enabled,
        blocking=gate.blocking,
        threshold=gate.threshold,
        dimension=gate.dimension,
        max_age_hours=gate.max_age_hours,
        regression_threshold=gate.regression_threshold,
    )


@router.post(
    "/",
    response_model=GateConfigResponse,
    summary="Create a custom gate",
    dependencies=[Depends(require_permissions(["gates:write"]))],
)
async def create_gate(
    gate_data: GateConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new custom quality gate."""
    service = get_quality_gate_service(db)
    
    # Check if gate already exists
    if service.get_gate(gate_data.id):
        raise HTTPException(status_code=409, detail="Gate with this ID already exists")
    
    # Map gate type
    try:
        gate_type = GateType(gate_data.gate_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid gate type. Must be one of: {[t.value for t in GateType]}"
        )
    
    gate = GateConfig(
        id=gate_data.id,
        name=gate_data.name,
        gate_type=gate_type,
        enabled=gate_data.enabled,
        blocking=gate_data.blocking,
        threshold=gate_data.threshold,
        dimension=gate_data.dimension,
        max_age_hours=gate_data.max_age_hours,
        regression_threshold=gate_data.regression_threshold,
    )
    
    service.add_gate(gate)
    
    return GateConfigResponse(
        id=gate.id,
        name=gate.name,
        gate_type=gate.gate_type.value,
        enabled=gate.enabled,
        blocking=gate.blocking,
        threshold=gate.threshold,
        dimension=gate.dimension,
        max_age_hours=gate.max_age_hours,
        regression_threshold=gate.regression_threshold,
    )


@router.put(
    "/{gate_id}",
    response_model=GateConfigResponse,
    summary="Update a gate",
    dependencies=[Depends(require_permissions(["gates:write"]))],
)
async def update_gate(
    gate_id: str,
    updates: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update an existing quality gate configuration."""
    service = get_quality_gate_service(db)
    gate = service.get_gate(gate_id)
    
    if not gate:
        raise HTTPException(status_code=404, detail="Gate not found")
    
    # Apply updates
    service.update_gate(gate_id, **updates)
    gate = service.get_gate(gate_id)
    
    return GateConfigResponse(
        id=gate.id,
        name=gate.name,
        gate_type=gate.gate_type.value,
        enabled=gate.enabled,
        blocking=gate.blocking,
        threshold=gate.threshold,
        dimension=gate.dimension,
        max_age_hours=gate.max_age_hours,
        regression_threshold=gate.regression_threshold,
    )


@router.delete(
    "/{gate_id}",
    summary="Delete a gate",
    dependencies=[Depends(require_permissions(["gates:write"]))],
)
async def delete_gate(
    gate_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a quality gate."""
    service = get_quality_gate_service(db)
    
    if not service.get_gate(gate_id):
        raise HTTPException(status_code=404, detail="Gate not found")
    
    service.remove_gate(gate_id)
    
    return {"message": f"Gate {gate_id} deleted"}


# =============================================================================
# Batch Operations
# =============================================================================

@router.post(
    "/evaluate-batch",
    summary="Evaluate gates for multiple prompts",
)
async def evaluate_gates_batch(
    prompt_ids: List[uuid.UUID],
    environment: str = Query("production"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Evaluate quality gates for multiple prompts.
    
    Useful for deployment planning and release management.
    """
    store = PromptStoreService(db)
    service = get_quality_gate_service(db)
    
    results = []
    for prompt_id in prompt_ids:
        prompt = await store.get(prompt_id)
        if prompt:
            report = await service.evaluate_gates(prompt, target_environment=environment)
            results.append({
                "prompt_id": str(prompt_id),
                "prompt_name": prompt.name,
                "can_deploy": report.can_deploy,
                "overall_status": report.overall_status.value,
                "summary": report.summary,
            })
        else:
            results.append({
                "prompt_id": str(prompt_id),
                "error": "Prompt not found",
            })
    
    # Calculate summary
    deployable = sum(1 for r in results if r.get("can_deploy", False))
    blocked = sum(1 for r in results if not r.get("can_deploy", True) and "error" not in r)
    
    return {
        "results": results,
        "summary": {
            "total": len(prompt_ids),
            "deployable": deployable,
            "blocked": blocked,
            "errors": len(prompt_ids) - deployable - blocked,
        },
    }
