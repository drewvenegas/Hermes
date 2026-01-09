"""
Collaboration Schemas

Pydantic models for comments, reviews, and activity.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from hermes.models.collaboration import ActivityType, ReviewStatus


# =====================
# Comments
# =====================


class CommentCreate(BaseModel):
    """Schema for creating a comment."""
    
    prompt_id: uuid.UUID
    version_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None
    content: str = Field(..., min_length=1, max_length=10000)
    mentions: list[uuid.UUID] = Field(default_factory=list)


class CommentUpdate(BaseModel):
    """Schema for updating a comment."""
    
    content: str = Field(..., min_length=1, max_length=10000)


class CommentResponse(BaseModel):
    """Schema for comment response."""
    
    id: uuid.UUID
    prompt_id: uuid.UUID
    version_id: Optional[uuid.UUID]
    parent_id: Optional[uuid.UUID]
    author_id: uuid.UUID
    author_name: str
    author_email: str
    content: str
    mentions: list[uuid.UUID]
    is_resolved: bool
    resolved_by: Optional[uuid.UUID]
    resolved_at: Optional[datetime]
    edited_at: Optional[datetime]
    edit_count: int
    created_at: datetime
    updated_at: datetime
    replies: list["CommentResponse"] = Field(default_factory=list)
    
    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    """Schema for paginated comment list."""
    
    items: list[CommentResponse]
    total: int


# =====================
# Reviews
# =====================


class ReviewCreate(BaseModel):
    """Schema for creating a review."""
    
    prompt_id: uuid.UUID
    version_id: uuid.UUID
    status: ReviewStatus = ReviewStatus.PENDING
    body: Optional[str] = Field(None, max_length=50000)


class ReviewSubmit(BaseModel):
    """Schema for submitting a review."""
    
    status: ReviewStatus
    body: Optional[str] = Field(None, max_length=50000)


class ReviewResponse(BaseModel):
    """Schema for review response."""
    
    id: uuid.UUID
    prompt_id: uuid.UUID
    version_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_name: str
    reviewer_email: str
    status: ReviewStatus
    body: Optional[str]
    submitted_at: Optional[datetime]
    dismissed: bool
    dismissed_by: Optional[uuid.UUID]
    dismissed_at: Optional[datetime]
    dismiss_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    """Schema for paginated review list."""
    
    items: list[ReviewResponse]
    total: int


class ReviewRequestCreate(BaseModel):
    """Schema for requesting a review."""
    
    prompt_id: uuid.UUID
    version_id: uuid.UUID
    reviewer_id: uuid.UUID
    is_required: bool = True


class ReviewRequestResponse(BaseModel):
    """Schema for review request response."""
    
    id: uuid.UUID
    prompt_id: uuid.UUID
    version_id: uuid.UUID
    requester_id: uuid.UUID
    reviewer_id: uuid.UUID
    is_required: bool
    completed: bool
    completed_at: Optional[datetime]
    review_id: Optional[uuid.UUID]
    created_at: datetime
    
    model_config = {"from_attributes": True}


# =====================
# Activity
# =====================


class ActivityResponse(BaseModel):
    """Schema for activity response."""
    
    id: uuid.UUID
    type: ActivityType
    actor_id: uuid.UUID
    actor_name: str
    actor_email: str
    prompt_id: Optional[uuid.UUID]
    version_id: Optional[uuid.UUID]
    target_type: Optional[str]
    target_id: Optional[uuid.UUID]
    summary: str
    details: dict[str, Any]
    team_id: Optional[uuid.UUID]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    """Schema for paginated activity list."""
    
    items: list[ActivityResponse]
    total: int
    has_more: bool


class ActivityFeedFilters(BaseModel):
    """Filters for activity feed."""
    
    prompt_id: Optional[uuid.UUID] = None
    actor_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None
    types: Optional[list[ActivityType]] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
