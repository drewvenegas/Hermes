"""
Collaboration API Endpoints

Comments, reviews, and activity feeds.
"""

import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permission
from hermes.auth.models import User
from hermes.models.collaboration import (
    Activity,
    ActivityType,
    Comment,
    Review,
    ReviewRequest,
    ReviewStatus,
)
from hermes.models.prompt import Prompt
from hermes.services.database import get_db

router = APIRouter()


# Comment Schemas
class CommentCreate(BaseModel):
    """Create comment request."""
    content: str = Field(..., min_length=1, max_length=10000)
    version: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None


class CommentUpdate(BaseModel):
    """Update comment request."""
    content: str = Field(..., min_length=1, max_length=10000)


class CommentResponse(BaseModel):
    """Comment response."""
    id: uuid.UUID
    prompt_id: uuid.UUID
    version: Optional[str]
    parent_id: Optional[uuid.UUID]
    author_id: uuid.UUID
    author_name: Optional[str]
    content: str
    mentions: List[str]
    is_resolved: bool
    resolved_by: Optional[uuid.UUID]
    resolved_at: Optional[datetime]
    is_edited: bool
    edited_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reply_count: int = 0

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    """Paginated comment list."""
    items: List[CommentResponse]
    total: int


# Review Schemas
class ReviewCreate(BaseModel):
    """Create review request."""
    status: str = Field(..., description="approved, changes_requested, or commented")
    body: Optional[str] = None


class ReviewResponse(BaseModel):
    """Review response."""
    id: uuid.UUID
    prompt_id: uuid.UUID
    version: str
    reviewer_id: uuid.UUID
    reviewer_name: Optional[str]
    status: str
    body: Optional[str]
    required: bool
    dismissed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewRequestCreate(BaseModel):
    """Request review request."""
    reviewer_id: uuid.UUID
    message: Optional[str] = None


class ReviewRequestResponse(BaseModel):
    """Review request response."""
    id: uuid.UUID
    prompt_id: uuid.UUID
    version: str
    requester_id: uuid.UUID
    reviewer_id: uuid.UUID
    message: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# Activity Schemas
class ActivityResponse(BaseModel):
    """Activity response."""
    id: uuid.UUID
    prompt_id: Optional[uuid.UUID]
    prompt_slug: Optional[str]
    prompt_name: Optional[str]
    version: Optional[str]
    actor_id: uuid.UUID
    actor_name: Optional[str]
    activity_type: str
    description: str
    metadata: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    """Paginated activity list."""
    items: List[ActivityResponse]
    total: int


# Helper functions
def extract_mentions(content: str) -> List[str]:
    """Extract @mentions from content."""
    pattern = r"@([a-zA-Z0-9_.-]+)"
    return list(set(re.findall(pattern, content)))


async def record_activity(
    db: AsyncSession,
    activity_type: ActivityType,
    description: str,
    actor_id: uuid.UUID,
    actor_name: Optional[str] = None,
    prompt_id: Optional[uuid.UUID] = None,
    prompt_slug: Optional[str] = None,
    prompt_name: Optional[str] = None,
    version: Optional[str] = None,
    metadata: Optional[dict] = None,
    team_id: Optional[uuid.UUID] = None,
):
    """Record an activity event."""
    activity = Activity(
        prompt_id=prompt_id,
        prompt_slug=prompt_slug,
        prompt_name=prompt_name,
        version=version,
        actor_id=actor_id,
        actor_name=actor_name,
        activity_type=activity_type.value,
        description=description,
        metadata=metadata,
        team_id=team_id,
    )
    db.add(activity)


# Comment Endpoints
@router.post("/prompts/{prompt_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    prompt_id: uuid.UUID,
    data: CommentCreate,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to a prompt.
    
    Requires: prompts:read permission
    
    Supports @mentions which will trigger notifications.
    """
    # Verify prompt exists
    query = select(Prompt).where(Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    # Verify parent comment if specified
    if data.parent_id:
        parent_query = select(Comment).where(Comment.id == data.parent_id)
        parent_result = await db.execute(parent_query)
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent comment '{data.parent_id}' not found",
            )
    
    # Extract mentions
    mentions = extract_mentions(data.content)
    
    comment = Comment(
        prompt_id=prompt_id,
        version=data.version,
        parent_id=data.parent_id,
        author_id=user.id,
        author_name=user.display_name,
        content=data.content,
        mentions=mentions,
    )
    
    db.add(comment)
    
    # Record activity
    await record_activity(
        db,
        ActivityType.COMMENT_ADDED,
        f"Added comment on {prompt.name}",
        actor_id=user.id,
        actor_name=user.display_name,
        prompt_id=prompt_id,
        prompt_slug=prompt.slug,
        prompt_name=prompt.name,
        version=data.version,
        metadata={"comment_id": str(comment.id)},
    )
    
    await db.flush()
    await db.refresh(comment)
    
    return CommentResponse.model_validate(comment)


@router.get("/prompts/{prompt_id}/comments", response_model=CommentListResponse)
async def list_comments(
    prompt_id: uuid.UUID,
    version: Optional[str] = Query(None),
    include_resolved: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """List comments on a prompt.
    
    Requires: prompts:read permission
    """
    query = select(Comment).where(Comment.prompt_id == prompt_id)
    
    # Only top-level comments (not replies)
    query = query.where(Comment.parent_id.is_(None))
    
    if version:
        query = query.where(Comment.version == version)
    if not include_resolved:
        query = query.where(Comment.is_resolved == False)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.order_by(Comment.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    comments = list(result.scalars().all())
    
    # Get reply counts
    response_items = []
    for comment in comments:
        reply_count_query = select(func.count()).where(Comment.parent_id == comment.id)
        reply_count = (await db.execute(reply_count_query)).scalar() or 0
        
        item = CommentResponse.model_validate(comment)
        item.reply_count = reply_count
        response_items.append(item)
    
    return CommentListResponse(items=response_items, total=total)


@router.get("/comments/{comment_id}/replies", response_model=List[CommentResponse])
async def list_replies(
    comment_id: uuid.UUID,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """List replies to a comment.
    
    Requires: prompts:read permission
    """
    query = (
        select(Comment)
        .where(Comment.parent_id == comment_id)
        .order_by(Comment.created_at.asc())
    )
    
    result = await db.execute(query)
    replies = list(result.scalars().all())
    
    return [CommentResponse.model_validate(r) for r in replies]


@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: uuid.UUID,
    data: CommentUpdate,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Update a comment.
    
    Requires: prompts:read permission
    
    Only the comment author can edit.
    """
    query = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(query)
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment '{comment_id}' not found",
        )
    
    if comment.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit another user's comment",
        )
    
    comment.content = data.content
    comment.mentions = extract_mentions(data.content)
    comment.is_edited = True
    comment.edited_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(comment)
    
    return CommentResponse.model_validate(comment)


@router.post("/comments/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    comment_id: uuid.UUID,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a comment thread.
    
    Requires: prompts:read permission
    """
    query = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(query)
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment '{comment_id}' not found",
        )
    
    comment.is_resolved = True
    comment.resolved_by = user.id
    comment.resolved_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(comment)
    
    return CommentResponse.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    user: User = Depends(require_permission("prompts:write")),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment.
    
    Requires: prompts:write permission
    
    Only the author or prompt owner can delete.
    """
    query = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(query)
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment '{comment_id}' not found",
        )
    
    # Allow author or admin to delete
    if comment.author_id != user.id and not user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete another user's comment",
        )
    
    await db.delete(comment)
    await db.flush()
    
    return None


# Review Endpoints
@router.post("/prompts/{prompt_id}/versions/{version}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    prompt_id: uuid.UUID,
    version: str,
    data: ReviewCreate,
    user: User = Depends(require_permission("prompts:write")),
    db: AsyncSession = Depends(get_db),
):
    """Submit a review on a prompt version.
    
    Requires: prompts:write permission
    """
    # Validate status
    if data.status not in [s.value for s in ReviewStatus]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in ReviewStatus]}",
        )
    
    # Verify prompt exists
    query = select(Prompt).where(Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    # Cannot review own prompt
    if prompt.owner_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot review your own prompt",
        )
    
    review = Review(
        prompt_id=prompt_id,
        version=version,
        reviewer_id=user.id,
        reviewer_name=user.display_name,
        status=data.status,
        body=data.body,
    )
    
    db.add(review)
    
    # Record activity
    activity_type = ActivityType.REVIEW_APPROVED if data.status == "approved" else ActivityType.REVIEW_SUBMITTED
    await record_activity(
        db,
        activity_type,
        f"Submitted {data.status} review on {prompt.name} v{version}",
        actor_id=user.id,
        actor_name=user.display_name,
        prompt_id=prompt_id,
        prompt_slug=prompt.slug,
        prompt_name=prompt.name,
        version=version,
        metadata={"review_status": data.status},
    )
    
    await db.flush()
    await db.refresh(review)
    
    return ReviewResponse.model_validate(review)


@router.get("/prompts/{prompt_id}/versions/{version}/reviews", response_model=List[ReviewResponse])
async def list_reviews(
    prompt_id: uuid.UUID,
    version: str,
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """List reviews for a prompt version.
    
    Requires: prompts:read permission
    """
    query = (
        select(Review)
        .where(Review.prompt_id == prompt_id)
        .where(Review.version == version)
        .where(Review.dismissed == False)
        .order_by(Review.created_at.desc())
    )
    
    result = await db.execute(query)
    reviews = list(result.scalars().all())
    
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.post("/prompts/{prompt_id}/versions/{version}/request-review", response_model=ReviewRequestResponse)
async def request_review(
    prompt_id: uuid.UUID,
    version: str,
    data: ReviewRequestCreate,
    user: User = Depends(require_permission("prompts:write")),
    db: AsyncSession = Depends(get_db),
):
    """Request a review from a specific user.
    
    Requires: prompts:write permission
    """
    # Verify prompt exists
    query = select(Prompt).where(Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt with ID '{prompt_id}' not found",
        )
    
    request = ReviewRequest(
        prompt_id=prompt_id,
        version=version,
        requester_id=user.id,
        reviewer_id=data.reviewer_id,
        message=data.message,
    )
    
    db.add(request)
    await db.flush()
    await db.refresh(request)
    
    return ReviewRequestResponse.model_validate(request)


@router.get("/reviews/pending", response_model=List[ReviewRequestResponse])
async def list_pending_reviews(
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """List pending review requests for current user.
    
    Requires: prompts:read permission
    """
    query = (
        select(ReviewRequest)
        .where(ReviewRequest.reviewer_id == user.id)
        .where(ReviewRequest.status == "pending")
        .order_by(ReviewRequest.created_at.desc())
    )
    
    result = await db.execute(query)
    requests = list(result.scalars().all())
    
    return [ReviewRequestResponse.model_validate(r) for r in requests]


# Activity Feed Endpoints
@router.get("/prompts/{prompt_id}/activity", response_model=ActivityListResponse)
async def get_prompt_activity(
    prompt_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get activity feed for a prompt.
    
    Requires: prompts:read permission
    """
    query = select(Activity).where(Activity.prompt_id == prompt_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.order_by(Activity.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    activities = list(result.scalars().all())
    
    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.get("/activity/user", response_model=ActivityListResponse)
async def get_user_activity(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get activity feed for current user.
    
    Requires: prompts:read permission
    """
    query = select(Activity).where(Activity.actor_id == user.id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.order_by(Activity.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    activities = list(result.scalars().all())
    
    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.get("/activity/team", response_model=ActivityListResponse)
async def get_team_activity(
    team_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get activity feed for a team.
    
    Requires: prompts:read permission
    
    If team_id not provided, uses user's primary team.
    """
    target_team_id = team_id
    if not target_team_id and user.teams:
        target_team_id = user.teams[0]
    
    if not target_team_id:
        return ActivityListResponse(items=[], total=0)
    
    query = select(Activity).where(Activity.team_id == target_team_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.order_by(Activity.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    activities = list(result.scalars().all())
    
    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.get("/activity/global", response_model=ActivityListResponse)
async def get_global_activity(
    activity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("prompts:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get global activity feed.
    
    Requires: prompts:read permission
    
    Shows public activities across all prompts.
    """
    query = select(Activity).where(Activity.is_public == True)
    
    if activity_type:
        query = query.where(Activity.activity_type == activity_type)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.order_by(Activity.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    activities = list(result.scalars().all())
    
    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )
