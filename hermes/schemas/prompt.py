"""
Prompt Schemas

Pydantic models for prompt API operations.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from hermes.models.prompt import PromptType, PromptStatus


class PromptBase(BaseModel):
    """Base prompt fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: PromptType
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[list[str]] = None
    content: str = Field(..., min_length=1)
    variables: Optional[dict[str, Any]] = None
    prompt_metadata: Optional[dict[str, Any]] = None


class PromptCreate(PromptBase):
    """Schema for creating a prompt."""

    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    team_id: Optional[uuid.UUID] = None
    visibility: Optional[str] = Field(default="private", pattern=r"^(private|team|organization|public)$")
    app_scope: Optional[list[str]] = None
    repo_scope: Optional[list[str]] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is lowercase and valid."""
        return v.lower()


class PromptUpdate(BaseModel):
    """Schema for updating a prompt."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[list[str]] = None
    content: Optional[str] = Field(None, min_length=1)
    variables: Optional[dict[str, Any]] = None
    prompt_metadata: Optional[dict[str, Any]] = None
    status: Optional[PromptStatus] = None
    visibility: Optional[str] = Field(None, pattern=r"^(private|team|organization|public)$")
    app_scope: Optional[list[str]] = None
    repo_scope: Optional[list[str]] = None
    change_summary: Optional[str] = Field(None, max_length=500)


class PromptResponse(BaseModel):
    """Schema for prompt response."""

    id: uuid.UUID
    slug: str
    name: str
    description: Optional[str]
    type: PromptType
    category: Optional[str]
    tags: Optional[list[str]]
    content: str
    variables: Optional[dict[str, Any]]
    prompt_metadata: Optional[dict[str, Any]]
    version: str
    content_hash: str
    status: PromptStatus
    owner_id: uuid.UUID
    owner_type: str
    team_id: Optional[uuid.UUID]
    visibility: str
    app_scope: Optional[list[str]]
    repo_scope: Optional[list[str]]
    benchmark_score: Optional[float]
    last_benchmark_at: Optional[datetime]
    deployed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromptQuery(BaseModel):
    """Schema for prompt list query parameters."""

    type: Optional[PromptType] = None
    status: Optional[PromptStatus] = None
    category: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None
    visibility: Optional[str] = None
    search: Optional[str] = None


class PromptListResponse(BaseModel):
    """Schema for paginated prompt list response."""

    items: list[PromptResponse]
    total: int
    limit: int
    offset: int
