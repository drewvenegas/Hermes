"""
Collaboration Service

Handles comments, reviews, and activity tracking.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hermes.models.collaboration import (
    Activity,
    ActivityType,
    Comment,
    Review,
    ReviewRequest,
    ReviewStatus,
)
from hermes.models.prompt import Prompt
from hermes.schemas.collaboration import (
    ActivityFeedFilters,
    CommentCreate,
    CommentUpdate,
    ReviewCreate,
    ReviewRequestCreate,
    ReviewSubmit,
)
from hermes.services.notifications import NotificationService

logger = logging.getLogger(__name__)


class CollaborationService:
    """Service for collaboration features."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.notifications = NotificationService()

    # =====================
    # Comments
    # =====================

    async def create_comment(
        self,
        data: CommentCreate,
        author_id: uuid.UUID,
        author_name: str,
        author_email: str,
    ) -> Comment:
        """Create a new comment."""
        # Extract mentions from content
        mentions = self._extract_mentions(data.content)
        mentions.extend([str(m) for m in data.mentions])
        mentions = list(set(mentions))  # Dedupe
        
        comment = Comment(
            prompt_id=data.prompt_id,
            version_id=data.version_id,
            parent_id=data.parent_id,
            author_id=author_id,
            author_name=author_name,
            author_email=author_email,
            content=data.content,
            mentions=[uuid.UUID(m) for m in mentions if self._is_valid_uuid(m)],
        )
        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)
        
        # Record activity
        await self._record_activity(
            type=ActivityType.COMMENT_ADDED,
            actor_id=author_id,
            actor_name=author_name,
            actor_email=author_email,
            prompt_id=data.prompt_id,
            summary=f"Added comment on prompt",
            details={"comment_id": str(comment.id)},
        )
        
        # Send notifications to mentioned users
        if comment.mentions:
            # TODO: Look up user emails and send notifications
            pass
        
        return comment

    def _extract_mentions(self, content: str) -> List[str]:
        """Extract @mentions from content."""
        # Match @uuid or @username patterns
        pattern = r"@([a-f0-9-]{36}|[a-zA-Z0-9_]+)"
        matches = re.findall(pattern, content)
        return matches

    def _is_valid_uuid(self, s: str) -> bool:
        """Check if string is a valid UUID."""
        try:
            uuid.UUID(s)
            return True
        except ValueError:
            return False

    async def get_comment(self, comment_id: uuid.UUID) -> Optional[Comment]:
        """Get a comment by ID."""
        return await self.db.get(Comment, comment_id)

    async def update_comment(
        self,
        comment_id: uuid.UUID,
        data: CommentUpdate,
        editor_id: uuid.UUID,
    ) -> Optional[Comment]:
        """Update a comment."""
        comment = await self.db.get(Comment, comment_id)
        if not comment:
            return None
        
        # Only author can edit
        if comment.author_id != editor_id:
            raise ValueError("Only the author can edit a comment")
        
        comment.content = data.content
        comment.edited_at = datetime.utcnow()
        comment.edit_count += 1
        comment.mentions = [uuid.UUID(m) for m in self._extract_mentions(data.content) if self._is_valid_uuid(m)]
        
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def delete_comment(self, comment_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a comment."""
        comment = await self.db.get(Comment, comment_id)
        if not comment:
            return False
        
        # Only author can delete (or admin)
        if comment.author_id != user_id:
            raise ValueError("Only the author can delete a comment")
        
        await self.db.delete(comment)
        return True

    async def resolve_comment(
        self,
        comment_id: uuid.UUID,
        resolver_id: uuid.UUID,
    ) -> Optional[Comment]:
        """Mark a comment as resolved."""
        comment = await self.db.get(Comment, comment_id)
        if not comment:
            return None
        
        comment.is_resolved = True
        comment.resolved_by = resolver_id
        comment.resolved_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def list_comments(
        self,
        prompt_id: uuid.UUID,
        version_id: Optional[uuid.UUID] = None,
        include_resolved: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Comment], int]:
        """List comments for a prompt."""
        query = select(Comment).where(Comment.prompt_id == prompt_id)
        
        if version_id:
            query = query.where(Comment.version_id == version_id)
        
        if not include_resolved:
            query = query.where(Comment.is_resolved == False)
        
        # Only top-level comments (replies loaded separately)
        query = query.where(Comment.parent_id.is_(None))
        
        # Load replies
        query = query.options(selectinload(Comment.replies))
        
        # Count
        count_query = select(func.count()).select_from(
            select(Comment).where(
                Comment.prompt_id == prompt_id,
                Comment.parent_id.is_(None),
            ).subquery()
        )
        total = await self.db.scalar(count_query)
        
        # Paginate
        query = query.order_by(Comment.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        comments = list(result.scalars().all())
        
        return comments, total or 0

    # =====================
    # Reviews
    # =====================

    async def create_review(
        self,
        data: ReviewCreate,
        reviewer_id: uuid.UUID,
        reviewer_name: str,
        reviewer_email: str,
    ) -> Review:
        """Create a new review."""
        review = Review(
            prompt_id=data.prompt_id,
            version_id=data.version_id,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            reviewer_email=reviewer_email,
            status=data.status,
            body=data.body,
        )
        self.db.add(review)
        await self.db.flush()
        await self.db.refresh(review)
        return review

    async def submit_review(
        self,
        review_id: uuid.UUID,
        data: ReviewSubmit,
        reviewer_id: uuid.UUID,
        reviewer_name: str,
        reviewer_email: str,
    ) -> Optional[Review]:
        """Submit a review with status."""
        review = await self.db.get(Review, review_id)
        if not review:
            return None
        
        # Only the assigned reviewer can submit
        if review.reviewer_id != reviewer_id:
            raise ValueError("Only the assigned reviewer can submit")
        
        review.status = data.status
        review.body = data.body
        review.submitted_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(review)
        
        # Record activity
        activity_type = (
            ActivityType.REVIEW_APPROVED
            if data.status == ReviewStatus.APPROVED
            else ActivityType.REVIEW_CHANGES_REQUESTED
            if data.status == ReviewStatus.CHANGES_REQUESTED
            else ActivityType.COMMENT_ADDED
        )
        await self._record_activity(
            type=activity_type,
            actor_id=reviewer_id,
            actor_name=reviewer_name,
            actor_email=reviewer_email,
            prompt_id=review.prompt_id,
            version_id=review.version_id,
            summary=f"Submitted review: {data.status.value}",
            details={"review_id": str(review.id)},
        )
        
        # Mark any pending review requests as completed
        await self._complete_review_request(review.prompt_id, review.version_id, reviewer_id, review.id)
        
        return review

    async def dismiss_review(
        self,
        review_id: uuid.UUID,
        dismisser_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Optional[Review]:
        """Dismiss a review."""
        review = await self.db.get(Review, review_id)
        if not review:
            return None
        
        review.dismissed = True
        review.dismissed_by = dismisser_id
        review.dismissed_at = datetime.utcnow()
        review.dismiss_reason = reason
        
        await self.db.flush()
        await self.db.refresh(review)
        return review

    async def list_reviews(
        self,
        prompt_id: uuid.UUID,
        version_id: Optional[uuid.UUID] = None,
        status: Optional[ReviewStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Review], int]:
        """List reviews for a prompt."""
        query = select(Review).where(Review.prompt_id == prompt_id)
        
        if version_id:
            query = query.where(Review.version_id == version_id)
        if status:
            query = query.where(Review.status == status)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # Paginate
        query = query.order_by(Review.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        reviews = list(result.scalars().all())
        
        return reviews, total or 0

    async def check_approval_status(
        self,
        prompt_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Check if a prompt version has required approvals."""
        # Get all review requests
        requests_query = select(ReviewRequest).where(
            ReviewRequest.prompt_id == prompt_id,
            ReviewRequest.version_id == version_id,
            ReviewRequest.is_required == True,
        )
        result = await self.db.execute(requests_query)
        requests = list(result.scalars().all())
        
        # Get all reviews
        reviews_query = select(Review).where(
            Review.prompt_id == prompt_id,
            Review.version_id == version_id,
            Review.dismissed == False,
        )
        result = await self.db.execute(reviews_query)
        reviews = list(result.scalars().all())
        
        approved_count = sum(1 for r in reviews if r.status == ReviewStatus.APPROVED)
        changes_requested = any(r.status == ReviewStatus.CHANGES_REQUESTED for r in reviews)
        pending_required = sum(1 for r in requests if not r.completed and r.is_required)
        
        return {
            "is_approved": approved_count > 0 and not changes_requested and pending_required == 0,
            "approved_count": approved_count,
            "changes_requested": changes_requested,
            "pending_required": pending_required,
            "total_reviews": len(reviews),
            "total_requests": len(requests),
        }

    # =====================
    # Review Requests
    # =====================

    async def request_review(
        self,
        data: ReviewRequestCreate,
        requester_id: uuid.UUID,
        requester_name: str,
        requester_email: str,
    ) -> ReviewRequest:
        """Request a review from a user."""
        request = ReviewRequest(
            prompt_id=data.prompt_id,
            version_id=data.version_id,
            requester_id=requester_id,
            reviewer_id=data.reviewer_id,
            is_required=data.is_required,
        )
        self.db.add(request)
        await self.db.flush()
        await self.db.refresh(request)
        
        # Record activity
        await self._record_activity(
            type=ActivityType.REVIEW_REQUESTED,
            actor_id=requester_id,
            actor_name=requester_name,
            actor_email=requester_email,
            prompt_id=data.prompt_id,
            version_id=data.version_id,
            summary=f"Requested review",
            details={"reviewer_id": str(data.reviewer_id)},
        )
        
        # TODO: Send notification to reviewer
        
        return request

    async def _complete_review_request(
        self,
        prompt_id: uuid.UUID,
        version_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        review_id: uuid.UUID,
    ):
        """Mark review request as completed."""
        query = select(ReviewRequest).where(
            ReviewRequest.prompt_id == prompt_id,
            ReviewRequest.version_id == version_id,
            ReviewRequest.reviewer_id == reviewer_id,
            ReviewRequest.completed == False,
        )
        result = await self.db.execute(query)
        request = result.scalar_one_or_none()
        
        if request:
            request.completed = True
            request.completed_at = datetime.utcnow()
            request.review_id = review_id

    async def list_pending_reviews(
        self,
        reviewer_id: uuid.UUID,
        limit: int = 50,
    ) -> List[ReviewRequest]:
        """Get pending review requests for a user."""
        query = select(ReviewRequest).where(
            ReviewRequest.reviewer_id == reviewer_id,
            ReviewRequest.completed == False,
        ).order_by(ReviewRequest.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =====================
    # Activity
    # =====================

    async def _record_activity(
        self,
        type: ActivityType,
        actor_id: uuid.UUID,
        actor_name: str,
        actor_email: str,
        summary: str,
        prompt_id: Optional[uuid.UUID] = None,
        version_id: Optional[uuid.UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        team_id: Optional[uuid.UUID] = None,
    ) -> Activity:
        """Record an activity event."""
        activity = Activity(
            type=type,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_email=actor_email,
            prompt_id=prompt_id,
            version_id=version_id,
            target_type=target_type,
            target_id=target_id,
            summary=summary,
            details=details or {},
            team_id=team_id,
        )
        self.db.add(activity)
        await self.db.flush()
        return activity

    async def get_activity_feed(
        self,
        filters: ActivityFeedFilters,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Activity], int, bool]:
        """Get activity feed with filters."""
        query = select(Activity)
        
        if filters.prompt_id:
            query = query.where(Activity.prompt_id == filters.prompt_id)
        if filters.actor_id:
            query = query.where(Activity.actor_id == filters.actor_id)
        if filters.team_id:
            query = query.where(Activity.team_id == filters.team_id)
        if filters.types:
            query = query.where(Activity.type.in_(filters.types))
        if filters.since:
            query = query.where(Activity.created_at >= filters.since)
        if filters.until:
            query = query.where(Activity.created_at <= filters.until)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0
        
        # Paginate
        query = query.order_by(Activity.created_at.desc())
        query = query.offset(offset).limit(limit + 1)  # Fetch one extra to check has_more
        
        result = await self.db.execute(query)
        activities = list(result.scalars().all())
        
        has_more = len(activities) > limit
        if has_more:
            activities = activities[:limit]
        
        return activities, total, has_more

    async def get_prompt_activity(
        self,
        prompt_id: uuid.UUID,
        limit: int = 50,
    ) -> List[Activity]:
        """Get activity for a specific prompt."""
        query = select(Activity).where(
            Activity.prompt_id == prompt_id
        ).order_by(Activity.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> List[Activity]:
        """Get activity by a specific user."""
        query = select(Activity).where(
            Activity.actor_id == user_id
        ).order_by(Activity.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
