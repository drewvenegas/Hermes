"""
API Keys API Endpoints

REST API for managing API keys.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.services.database import get_db_session
from hermes.services.api_key_service import APIKeyService
from hermes.services.audit_service import AuditService, AuditActions, ResourceTypes
from hermes.models.api_key import STANDARD_SCOPES

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


# ============================================================================
# Request/Response Models
# ============================================================================

class APIKeyCreate(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for the key")
    description: Optional[str] = Field(None, max_length=500)
    scopes: List[str] = Field(default=["prompts:read"], description="Permission scopes")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")
    allowed_ips: Optional[List[str]] = Field(None, description="IP allowlist")
    metadata: Optional[dict] = None


class APIKeyResponse(BaseModel):
    """API key response (excludes sensitive data)."""
    id: str
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    use_count: int
    created_by: str
    created_at: Optional[datetime]
    is_active: bool
    is_valid: bool

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(APIKeyResponse):
    """Response when creating a new API key (includes the raw key)."""
    key: str = Field(..., description="The full API key - only shown once!")


class APIKeyScopesUpdate(BaseModel):
    """Request to update API key scopes."""
    scopes: List[str]


class APIKeyRevokeRequest(BaseModel):
    """Request to revoke an API key."""
    reason: Optional[str] = Field(None, max_length=500)


class APIKeyListResponse(BaseModel):
    """Paginated list of API keys."""
    keys: List[APIKeyResponse]
    total: int
    limit: int
    offset: int


class AvailableScopesResponse(BaseModel):
    """List of available scopes."""
    scopes: List[str]


# ============================================================================
# Dependency for current user (placeholder)
# ============================================================================

async def get_current_user_id(request: Request) -> uuid.UUID:
    """
    Get current user ID from request.
    
    In a real implementation, this would extract from JWT or session.
    """
    # For now, use a placeholder or check for X-User-ID header
    user_id = request.headers.get("X-User-ID")
    if user_id:
        try:
            return uuid.UUID(user_id)
        except ValueError:
            pass
    
    # Default to system user
    return uuid.UUID("00000000-0000-0000-0000-000000000000")


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API Key",
    description="Create a new API key. The raw key is only returned once!",
)
async def create_api_key(
    request: Request,
    data: APIKeyCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new API key."""
    service = APIKeyService(db)
    audit = AuditService(db)
    
    try:
        api_key, raw_key = await service.create_key(
            name=data.name,
            created_by=user_id,
            scopes=data.scopes,
            description=data.description,
            expires_in_days=data.expires_in_days,
            allowed_ips=data.allowed_ips,
            metadata=data.metadata,
        )
        
        # Audit log
        await audit.log_action(
            action=AuditActions.API_KEY_CREATE,
            resource_type=ResourceTypes.API_KEY,
            resource_id=api_key.id,
            user_id=user_id,
            details={"name": data.name, "scopes": data.scopes},
            ip_address=request.client.host if request.client else None,
        )
        
        await db.commit()
        
        return APIKeyCreatedResponse(
            id=str(api_key.id),
            name=api_key.name,
            description=api_key.description,
            key_prefix=api_key.key_prefix,
            scopes=api_key.scopes,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            use_count=api_key.use_count,
            created_by=str(api_key.created_by),
            created_at=api_key.created_at if hasattr(api_key, 'created_at') else None,
            is_active=api_key.is_active,
            is_valid=api_key.is_valid(),
            key=raw_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "",
    response_model=APIKeyListResponse,
    summary="List API Keys",
)
async def list_api_keys(
    include_revoked: bool = Query(False, description="Include revoked keys"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """List API keys for the current user."""
    service = APIKeyService(db)
    
    keys, total = await service.list_keys(
        created_by=user_id,
        include_revoked=include_revoked,
        limit=limit,
        offset=offset,
    )
    
    return APIKeyListResponse(
        keys=[
            APIKeyResponse(
                id=str(k.id),
                name=k.name,
                description=k.description,
                key_prefix=k.key_prefix,
                scopes=k.scopes,
                expires_at=k.expires_at,
                last_used_at=k.last_used_at,
                use_count=k.use_count,
                created_by=str(k.created_by),
                created_at=k.created_at if hasattr(k, 'created_at') else None,
                is_active=k.is_active,
                is_valid=k.is_valid(),
            )
            for k in keys
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/scopes",
    response_model=AvailableScopesResponse,
    summary="List Available Scopes",
)
async def list_available_scopes():
    """List all available API key scopes."""
    return AvailableScopesResponse(scopes=STANDARD_SCOPES)


@router.get(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Get API Key",
)
async def get_api_key(
    key_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Get details of an API key."""
    service = APIKeyService(db)
    
    api_key = await service.get_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Check ownership
    if api_key.created_by != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this key")
    
    return APIKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        use_count=api_key.use_count,
        created_by=str(api_key.created_by),
        created_at=api_key.created_at if hasattr(api_key, 'created_at') else None,
        is_active=api_key.is_active,
        is_valid=api_key.is_valid(),
    )


@router.put(
    "/{key_id}/scopes",
    response_model=APIKeyResponse,
    summary="Update Scopes",
)
async def update_api_key_scopes(
    key_id: uuid.UUID,
    data: APIKeyScopesUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Update the scopes of an API key."""
    service = APIKeyService(db)
    
    api_key = await service.get_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if api_key.created_by != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this key")
    
    try:
        updated = await service.update_scopes(key_id, data.scopes)
        await db.commit()
        
        return APIKeyResponse(
            id=str(updated.id),
            name=updated.name,
            description=updated.description,
            key_prefix=updated.key_prefix,
            scopes=updated.scopes,
            expires_at=updated.expires_at,
            last_used_at=updated.last_used_at,
            use_count=updated.use_count,
            created_by=str(updated.created_by),
            created_at=updated.created_at if hasattr(updated, 'created_at') else None,
            is_active=updated.is_active,
            is_valid=updated.is_valid(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{key_id}/revoke",
    response_model=APIKeyResponse,
    summary="Revoke API Key",
)
async def revoke_api_key(
    request: Request,
    key_id: uuid.UUID,
    data: APIKeyRevokeRequest = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke an API key."""
    service = APIKeyService(db)
    audit = AuditService(db)
    
    api_key = await service.get_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if api_key.created_by != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to revoke this key")
    
    reason = data.reason if data else None
    success = await service.revoke_key(key_id, user_id, reason)
    
    if success:
        await audit.log_action(
            action=AuditActions.API_KEY_REVOKE,
            resource_type=ResourceTypes.API_KEY,
            resource_id=key_id,
            user_id=user_id,
            details={"reason": reason},
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
    
    # Refresh
    api_key = await service.get_key(key_id)
    
    return APIKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        use_count=api_key.use_count,
        created_by=str(api_key.created_by),
        created_at=api_key.created_at if hasattr(api_key, 'created_at') else None,
        is_active=api_key.is_active,
        is_valid=api_key.is_valid(),
    )


@router.post(
    "/{key_id}/rotate",
    response_model=APIKeyCreatedResponse,
    summary="Rotate API Key",
)
async def rotate_api_key(
    request: Request,
    key_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Rotate an API key (create new, revoke old)."""
    service = APIKeyService(db)
    audit = AuditService(db)
    
    api_key = await service.get_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if api_key.created_by != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to rotate this key")
    
    new_key, raw_key = await service.rotate_key(key_id, user_id)
    
    if not new_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    await audit.log_action(
        action=AuditActions.API_KEY_ROTATE,
        resource_type=ResourceTypes.API_KEY,
        resource_id=new_key.id,
        user_id=user_id,
        details={"old_key_id": str(key_id)},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    
    return APIKeyCreatedResponse(
        id=str(new_key.id),
        name=new_key.name,
        description=new_key.description,
        key_prefix=new_key.key_prefix,
        scopes=new_key.scopes,
        expires_at=new_key.expires_at,
        last_used_at=new_key.last_used_at,
        use_count=new_key.use_count,
        created_by=str(new_key.created_by),
        created_at=new_key.created_at if hasattr(new_key, 'created_at') else None,
        is_active=new_key.is_active,
        is_valid=new_key.is_valid(),
        key=raw_key,
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API Key",
)
async def delete_api_key(
    request: Request,
    key_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Permanently delete an API key."""
    service = APIKeyService(db)
    
    api_key = await service.get_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if api_key.created_by != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this key")
    
    # Revoke first
    await service.revoke_key(key_id, user_id, "Deleted")
    await db.commit()
