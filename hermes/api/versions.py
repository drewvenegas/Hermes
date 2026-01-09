"""
Versions API Endpoints

Version history and rollback operations.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.schemas.prompt import PromptResponse
from hermes.schemas.version import (
    DiffResponse,
    RollbackRequest,
    VersionListResponse,
    VersionResponse,
)
from hermes.services.database import get_db
from hermes.services.version_control import VersionControlService

router = APIRouter()


# Temporary: Mock user ID until PERSONA integration
def get_current_user_id() -> uuid.UUID:
    """Get current user ID (placeholder for PERSONA integration)."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.get("/prompts/{prompt_id}/versions", response_model=VersionListResponse)
async def list_versions(
    prompt_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all versions of a prompt."""
    service = VersionControlService(db)
    versions = await service.list_versions(prompt_id, limit=limit, offset=offset)
    
    return VersionListResponse(
        items=[VersionResponse.model_validate(v) for v in versions],
        total=len(versions),  # Would need separate count query for accuracy
        limit=limit,
        offset=offset,
    )


@router.get("/prompts/{prompt_id}/versions/{version}", response_model=VersionResponse)
async def get_version(
    prompt_id: uuid.UUID,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific version of a prompt."""
    service = VersionControlService(db)
    ver = await service.get_version(prompt_id, version)
    
    if not ver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version}' not found for prompt '{prompt_id}'",
        )
    
    return ver


@router.get("/prompts/{prompt_id}/diff", response_model=DiffResponse)
async def get_diff(
    prompt_id: uuid.UUID,
    from_version: str = Query(..., description="Source version"),
    to_version: str = Query(..., description="Target version"),
    db: AsyncSession = Depends(get_db),
):
    """Get diff between two versions."""
    service = VersionControlService(db)
    result = await service.compare_versions(prompt_id, from_version, to_version)
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )
    
    return DiffResponse(**result)


@router.post("/prompts/{prompt_id}/rollback", response_model=PromptResponse)
async def rollback_prompt(
    prompt_id: uuid.UUID,
    data: RollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rollback a prompt to a previous version."""
    service = VersionControlService(db)
    user_id = get_current_user_id()
    
    prompt = await service.rollback(prompt_id, data.version, author_id=user_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{data.version}' not found for prompt '{prompt_id}'",
        )
    
    return prompt
