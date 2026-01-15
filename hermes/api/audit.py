"""
Audit Logs API Endpoints

REST API for querying audit logs.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.services.database import get_db_session
from hermes.services.audit_service import AuditService, AuditActions, ResourceTypes

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: str
    user_id: Optional[str]
    api_key_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    request_id: Optional[str]
    endpoint: Optional[str]
    http_method: Optional[str]
    timestamp: datetime
    success: bool
    error_message: Optional[str]

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""
    logs: List[AuditLogResponse]
    total: int
    limit: int
    offset: int


class AuditSummaryResponse(BaseModel):
    """Summary of audit actions."""
    period_days: int
    action_counts: Dict[str, int]


class AvailableFiltersResponse(BaseModel):
    """Available filter options."""
    actions: List[str]
    resource_types: List[str]


# ============================================================================
# Dependency for current user (placeholder)
# ============================================================================

async def get_current_user_id(request: Request) -> uuid.UUID:
    """Get current user ID from request."""
    user_id = request.headers.get("X-User-ID")
    if user_id:
        try:
            return uuid.UUID(user_id)
        except ValueError:
            pass
    return uuid.UUID("00000000-0000-0000-0000-000000000000")


async def check_audit_access(user_id: uuid.UUID = Depends(get_current_user_id)) -> uuid.UUID:
    """Check if user has access to audit logs."""
    # In production, check for audit:read scope or admin role
    return user_id


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List Audit Logs",
    description="Query audit logs with optional filters.",
)
async def list_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    request_id: Optional[str] = Query(None, description="Filter by request ID"),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    success_only: Optional[bool] = Query(None, description="Filter by success status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: uuid.UUID = Depends(check_audit_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Query audit logs with filters."""
    service = AuditService(db)
    
    # Parse UUIDs
    parsed_user_id = None
    parsed_resource_id = None
    
    if user_id:
        try:
            parsed_user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    if resource_id:
        try:
            parsed_resource_id = uuid.UUID(resource_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid resource_id format")
    
    logs, total = await service.get_logs(
        user_id=parsed_user_id,
        resource_type=resource_type,
        resource_id=parsed_resource_id,
        action=action,
        request_id=request_id,
        start_time=start_time,
        end_time=end_time,
        success_only=success_only,
        limit=limit,
        offset=offset,
    )
    
    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=str(log.id),
                user_id=str(log.user_id) if log.user_id else None,
                api_key_id=str(log.api_key_id) if log.api_key_id else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=str(log.resource_id) if log.resource_id else None,
                details=log.details,
                ip_address=log.ip_address,
                request_id=log.request_id,
                endpoint=log.endpoint,
                http_method=log.http_method,
                timestamp=log.timestamp,
                success=log.success,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/resource/{resource_type}/{resource_id}",
    response_model=AuditLogListResponse,
    summary="Get Resource History",
    description="Get audit history for a specific resource.",
)
async def get_resource_history(
    resource_type: str,
    resource_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=500),
    current_user: uuid.UUID = Depends(check_audit_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get audit history for a specific resource."""
    service = AuditService(db)
    
    logs = await service.get_resource_history(
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit,
    )
    
    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=str(log.id),
                user_id=str(log.user_id) if log.user_id else None,
                api_key_id=str(log.api_key_id) if log.api_key_id else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=str(log.resource_id) if log.resource_id else None,
                details=log.details,
                ip_address=log.ip_address,
                request_id=log.request_id,
                endpoint=log.endpoint,
                http_method=log.http_method,
                timestamp=log.timestamp,
                success=log.success,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=len(logs),
        limit=limit,
        offset=0,
    )


@router.get(
    "/user/{user_id}",
    response_model=AuditLogListResponse,
    summary="Get User Activity",
    description="Get recent activity for a specific user.",
)
async def get_user_activity(
    user_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(100, ge=1, le=500),
    current_user: uuid.UUID = Depends(check_audit_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get recent activity for a user."""
    service = AuditService(db)
    
    logs = await service.get_user_activity(
        user_id=user_id,
        days=days,
        limit=limit,
    )
    
    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=str(log.id),
                user_id=str(log.user_id) if log.user_id else None,
                api_key_id=str(log.api_key_id) if log.api_key_id else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=str(log.resource_id) if log.resource_id else None,
                details=log.details,
                ip_address=log.ip_address,
                request_id=log.request_id,
                endpoint=log.endpoint,
                http_method=log.http_method,
                timestamp=log.timestamp,
                success=log.success,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=len(logs),
        limit=limit,
        offset=0,
    )


@router.get(
    "/summary",
    response_model=AuditSummaryResponse,
    summary="Get Action Summary",
    description="Get summary of actions over a time period.",
)
async def get_action_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to summarize"),
    current_user: uuid.UUID = Depends(check_audit_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get summary of actions over a time period."""
    service = AuditService(db)
    
    summary = await service.get_action_summary(days=days)
    
    return AuditSummaryResponse(
        period_days=days,
        action_counts=summary,
    )


@router.get(
    "/filters",
    response_model=AvailableFiltersResponse,
    summary="Get Available Filters",
    description="Get lists of available filter options.",
)
async def get_available_filters():
    """Get lists of available filter options."""
    # Get all actions from AuditActions
    actions = [
        getattr(AuditActions, attr)
        for attr in dir(AuditActions)
        if not attr.startswith("_") and isinstance(getattr(AuditActions, attr), str)
    ]
    
    # Get all resource types from ResourceTypes
    resource_types = [
        getattr(ResourceTypes, attr)
        for attr in dir(ResourceTypes)
        if not attr.startswith("_") and isinstance(getattr(ResourceTypes, attr), str)
    ]
    
    return AvailableFiltersResponse(
        actions=actions,
        resource_types=resource_types,
    )


@router.get(
    "/{log_id}",
    response_model=AuditLogResponse,
    summary="Get Audit Log",
    description="Get a specific audit log entry by ID.",
)
async def get_audit_log(
    log_id: uuid.UUID,
    current_user: uuid.UUID = Depends(check_audit_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Get a specific audit log entry."""
    service = AuditService(db)
    
    logs, _ = await service.get_logs(limit=1)
    
    # Find the specific log
    from sqlalchemy import select
    from hermes.models.audit import AuditLog
    
    result = await db.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    return AuditLogResponse(
        id=str(log.id),
        user_id=str(log.user_id) if log.user_id else None,
        api_key_id=str(log.api_key_id) if log.api_key_id else None,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=str(log.resource_id) if log.resource_id else None,
        details=log.details,
        ip_address=log.ip_address,
        request_id=log.request_id,
        endpoint=log.endpoint,
        http_method=log.http_method,
        timestamp=log.timestamp,
        success=log.success,
        error_message=log.error_message,
    )
