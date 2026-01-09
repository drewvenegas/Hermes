"""
Version Schemas

Pydantic models for version API operations.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class VersionResponse(BaseModel):
    """Schema for version response."""

    id: uuid.UUID
    prompt_id: uuid.UUID
    version: str
    content: str
    content_hash: str
    diff: Optional[str]
    change_summary: Optional[str]
    author_id: uuid.UUID
    variables: Optional[dict[str, Any]]
    metadata: Optional[dict[str, Any]]
    benchmark_results: Optional[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionListResponse(BaseModel):
    """Schema for paginated version list response."""

    items: list[VersionResponse]
    total: int
    limit: int
    offset: int


class RollbackRequest(BaseModel):
    """Schema for rollback request."""

    version: str = Field(..., description="Version to rollback to")


class DiffResponse(BaseModel):
    """Schema for diff response."""

    version_a: str
    version_b: str
    diff: str
    version_a_hash: str
    version_b_hash: str
    version_a_created: str
    version_b_created: str
