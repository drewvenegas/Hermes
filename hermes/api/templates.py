"""
Templates API Endpoints

Prompt template management and rendering.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permission
from hermes.auth.models import User
from hermes.models.template import TemplateStatus
from hermes.services.database import get_db
from hermes.services.template_service import (
    TemplateRenderer,
    TemplateRenderError,
    TemplateService,
    TemplateValidationError,
)

router = APIRouter()


# Schemas
class VariableDefinition(BaseModel):
    """Template variable definition."""
    name: str
    type: str = "string"
    description: Optional[str] = None
    default: Optional[Any] = None
    required: bool = False
    options: Optional[List[str]] = None
    validation: Optional[Dict[str, Any]] = None


class TemplateCreate(BaseModel):
    """Schema for creating a template."""
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    variables: List[VariableDefinition] = Field(default_factory=list)
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    visibility: str = "private"


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[List[VariableDefinition]] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    visibility: Optional[str] = None
    change_summary: Optional[str] = None


class TemplateResponse(BaseModel):
    """Template response schema."""
    id: uuid.UUID
    slug: str
    name: str
    description: Optional[str]
    content: str
    variables: List[Dict]
    parent_template_id: Optional[uuid.UUID]
    forked_from_id: Optional[uuid.UUID]
    category: Optional[str]
    tags: List[str]
    version: str
    status: str
    owner_id: uuid.UUID
    visibility: str
    fork_count: int
    usage_count: int
    is_curated: bool
    is_featured: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    """Paginated template list."""
    items: List[TemplateResponse]
    total: int
    limit: int
    offset: int


class VersionResponse(BaseModel):
    """Template version response."""
    id: uuid.UUID
    template_id: uuid.UUID
    version: str
    content: str
    variables: List[Dict]
    change_summary: Optional[str]
    author_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class RenderRequest(BaseModel):
    """Template render request."""
    variables: Dict[str, Any] = Field(default_factory=dict)


class RenderResponse(BaseModel):
    """Template render response."""
    rendered: str
    template_id: uuid.UUID
    version: str


class PreviewRequest(BaseModel):
    """Template preview request."""
    content: str
    variables: List[VariableDefinition]
    values: Optional[Dict[str, Any]] = None


class PreviewResponse(BaseModel):
    """Template preview response."""
    rendered: Optional[str]
    errors: List[str]
    warnings: List[str]
    variables_used: List[str]


class ForkRequest(BaseModel):
    """Template fork request."""
    new_slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    new_name: Optional[str] = None


# Endpoints
@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    user: User = Depends(require_permission("prompts:write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new prompt template.
    
    Requires: prompts:write permission
    """
    service = TemplateService(db)
    
    # Check slug uniqueness
    existing = await service.get_by_slug(data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with slug '{data.slug}' already exists",
        )
    
    try:
        template = await service.create(
            slug=data.slug,
            name=data.name,
            content=data.content,
            owner_id=user.id,
            variables=[v.model_dump() for v in data.variables],
            description=data.description,
            category=data.category,
            tags=data.tags,
            visibility=data.visibility,
        )
    except TemplateValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return template


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_curated: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """List templates with filtering.
    
    Requires: prompts:read permission
    """
    service = TemplateService(db)
    
    templates, total = await service.list(
        category=category,
        status=status,
        is_curated=is_curated,
        search=search,
        limit=limit,
        offset=offset,
    )
    
    return TemplateListResponse(
        items=[TemplateResponse.model_validate(t) for t in templates],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/templates/curated", response_model=TemplateListResponse)
async def list_curated_templates(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """List curated template library.
    
    Requires: prompts:read permission
    """
    service = TemplateService(db)
    
    templates, total = await service.list(
        category=category,
        status=TemplateStatus.PUBLISHED.value,
        is_curated=True,
        limit=limit,
        offset=offset,
    )
    
    return TemplateListResponse(
        items=[TemplateResponse.model_validate(t) for t in templates],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a template by ID.
    
    Requires: prompts:read permission
    """
    service = TemplateService(db)
    template = await service.get(template_id)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID '{template_id}' not found",
        )
    
    return template


@router.get("/templates/by-slug/{slug}", response_model=TemplateResponse)
async def get_template_by_slug(
    slug: str,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a template by slug.
    
    Requires: prompts:read permission
    """
    service = TemplateService(db)
    template = await service.get_by_slug(slug)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with slug '{slug}' not found",
        )
    
    return template


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    user: User = Depends(require_permission("prompts:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update a template.
    
    Requires: prompts:write permission
    
    Creates a new version on update.
    """
    service = TemplateService(db)
    
    update_data = data.model_dump(exclude_unset=True)
    if "variables" in update_data:
        update_data["variables"] = [
            v if isinstance(v, dict) else v.model_dump()
            for v in update_data["variables"]
        ]
    
    try:
        template = await service.update(
            template_id,
            author_id=user.id,
            **update_data,
        )
    except TemplateValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID '{template_id}' not found",
        )
    
    return template


@router.post("/templates/{template_id}/fork", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def fork_template(
    template_id: uuid.UUID,
    data: ForkRequest,
    user: User = Depends(require_permission("prompts:write")),
    db: AsyncSession = Depends(get_db),
):
    """Fork a template.
    
    Requires: prompts:write permission
    
    Creates a copy of the template under the current user's ownership.
    """
    service = TemplateService(db)
    
    # Check new slug doesn't exist
    existing = await service.get_by_slug(data.new_slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with slug '{data.new_slug}' already exists",
        )
    
    try:
        forked = await service.fork(
            template_id=template_id,
            new_slug=data.new_slug,
            owner_id=user.id,
            new_name=data.new_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    
    return forked


@router.get("/templates/{template_id}/versions", response_model=List[VersionResponse])
async def list_template_versions(
    template_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """List version history for a template.
    
    Requires: prompts:read permission
    """
    service = TemplateService(db)
    versions = await service.get_versions(template_id, limit=limit)
    return [VersionResponse.model_validate(v) for v in versions]


@router.post("/templates/{template_id}/render", response_model=RenderResponse)
async def render_template(
    template_id: uuid.UUID,
    data: RenderRequest,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Render a template with variable values.
    
    Requires: prompts:read permission
    """
    service = TemplateService(db)
    renderer = TemplateRenderer(db)
    
    template = await service.get(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID '{template_id}' not found",
        )
    
    try:
        rendered = await renderer.render(
            template_id=template_id,
            variables=data.variables,
            user_id=user.id,
        )
    except TemplateRenderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return RenderResponse(
        rendered=rendered,
        template_id=template_id,
        version=template.version,
    )


@router.post("/templates/preview", response_model=PreviewResponse)
async def preview_template(
    data: PreviewRequest,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Preview template rendering without saving.
    
    Requires: prompts:read permission
    
    Useful for testing templates before creating them.
    """
    renderer = TemplateRenderer(db)
    
    result = await renderer.preview(
        content=data.content,
        variable_definitions=[v.model_dump() for v in data.variables],
        values=data.values,
    )
    
    return PreviewResponse(**result)
