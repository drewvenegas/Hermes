"""
Prompts API Endpoints

CRUD operations for prompts.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models.prompt import PromptStatus, PromptType
from hermes.schemas.prompt import (
    PromptCreate,
    PromptListResponse,
    PromptQuery,
    PromptResponse,
    PromptUpdate,
)
from hermes.services.database import get_db
from hermes.services.prompt_store import PromptStoreService

router = APIRouter()


# Temporary: Mock user ID until PERSONA integration
def get_current_user_id() -> uuid.UUID:
    """Get current user ID (placeholder for PERSONA integration)."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.post("/prompts", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    data: PromptCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new prompt."""
    service = PromptStoreService(db)
    
    # Check if slug already exists
    existing = await service.get_by_slug(data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Prompt with slug '{data.slug}' already exists",
        )
    
    user_id = get_current_user_id()
    prompt = await service.create(data, owner_id=user_id)
    
    return prompt


@router.get("/prompts", response_model=PromptListResponse)
async def list_prompts(
    type: Optional[PromptType] = Query(None),
    status: Optional[PromptStatus] = Query(None),
    category: Optional[str] = Query(None),
    owner_id: Optional[uuid.UUID] = Query(None),
    team_id: Optional[uuid.UUID] = Query(None),
    visibility: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List prompts with filtering and pagination."""
    service = PromptStoreService(db)
    
    query = PromptQuery(
        type=type,
        status=status,
        category=category,
        owner_id=owner_id,
        team_id=team_id,
        visibility=visibility,
        search=search,
    )
    
    prompts, total = await service.list(query, limit=limit, offset=offset)
    
    return PromptListResponse(
        items=[PromptResponse.model_validate(p) for p in prompts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/prompts/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a prompt by ID."""
    service = PromptStoreService(db)
    prompt = await service.get(prompt_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    return prompt


@router.get("/prompts/by-slug/{slug}", response_model=PromptResponse)
async def get_prompt_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a prompt by slug."""
    service = PromptStoreService(db)
    prompt = await service.get_by_slug(slug)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with slug '{slug}' not found",
        )
    
    return prompt


@router.put("/prompts/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: uuid.UUID,
    data: PromptUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a prompt."""
    service = PromptStoreService(db)
    user_id = get_current_user_id()
    
    prompt = await service.update(prompt_id, data, author_id=user_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    return prompt


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a prompt."""
    service = PromptStoreService(db)
    deleted = await service.delete(prompt_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    return None
