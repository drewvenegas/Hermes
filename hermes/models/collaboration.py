"""
Collaboration Models

Comments, reviews, and activity tracking for prompts.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermes.models.base import Base, TimestampMixin, UUIDMixin


class ReviewStatus(str, Enum):
    """Review status options."""
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"


class ActivityType(str, Enum):
    """Activity event types."""
    CREATED = "created"
    UPDATED = "updated"
    PUBLISHED = "published"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    COMMENT_ADDED = "comment_added"
    REVIEW_SUBMITTED = "review_submitted"
    REVIEW_APPROVED = "review_approved"
    BENCHMARK_RUN = "benchmark_run"
    VERSION_CREATED = "version_created"
    FORKED = "forked"


class Comment(Base, UUIDMixin, TimestampMixin):
    """
    Comment on a prompt or prompt version.

    Supports threaded replies and @mentions.
    
    Attributes:
        id: Unique comment ID
        prompt_id: The prompt being commented on
        version: Specific version being commented on (optional)
        parent_id: Parent comment for threads
        author_id: Comment author
        content: Comment content (markdown)
        mentions: List of @mentioned user IDs
        is_resolved: Whether comment thread is resolved
        resolved_by: User who resolved the thread
        resolved_at: When thread was resolved
    """

    __tablename__ = "comments"

    # Reference
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Threading
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Author
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Status
    is_resolved: Mapped[bool] = mapped_column(nullable=False, default=False)
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Edit tracking
    is_edited: Mapped[bool] = mapped_column(nullable=False, default=False)
    edited_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        backref="parent",
        remote_side="Comment.id",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_comments_prompt", "prompt_id"),
        Index("ix_comments_author", "author_id"),
        Index("ix_comments_parent", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, prompt_id={self.prompt_id})>"


class Review(Base, UUIDMixin, TimestampMixin):
    """
    Review on a prompt version.

    Implements approval workflow for deploying prompts.
    
    Attributes:
        id: Unique review ID
        prompt_id: The prompt being reviewed
        version: Version being reviewed
        reviewer_id: Reviewer user ID
        status: Review status (approved, changes_requested, commented)
        body: Review body/comments
        required: Whether this review was required
    """

    __tablename__ = "reviews"

    # Reference
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Reviewer
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reviewer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Review content
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ReviewStatus.PENDING.value,
        index=True,
    )
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Workflow
    required: Mapped[bool] = mapped_column(nullable=False, default=False)
    dismissed: Mapped[bool] = mapped_column(nullable=False, default=False)
    dismissed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_reviews_prompt_version", "prompt_id", "version"),
        Index("ix_reviews_reviewer", "reviewer_id"),
        Index("ix_reviews_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, prompt_id={self.prompt_id}, status={self.status})>"


class ReviewRequest(Base, UUIDMixin, TimestampMixin):
    """
    Request for review on a prompt version.
    
    Attributes:
        id: Request ID
        prompt_id: The prompt to be reviewed
        version: Version to review
        requester_id: User requesting the review
        reviewer_id: Requested reviewer
        message: Optional message to reviewer
        status: Request status
    """

    __tablename__ = "review_requests"

    # Reference
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Users
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Content
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_review_requests_prompt", "prompt_id"),
        Index("ix_review_requests_reviewer", "reviewer_id"),
    )

    def __repr__(self) -> str:
        return f"<ReviewRequest(id={self.id}, reviewer_id={self.reviewer_id})>"


class Activity(Base, UUIDMixin, TimestampMixin):
    """
    Activity log for prompts and user actions.

    Tracks all changes and events for audit and feed.
    
    Attributes:
        id: Activity ID
        prompt_id: Related prompt (if applicable)
        actor_id: User who performed the action
        activity_type: Type of activity
        description: Human-readable description
        metadata: Additional event data
    """

    __tablename__ = "activities"

    # Reference (optional - some activities may be user-only)
    prompt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Actor
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Activity details
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Visibility
    is_public: Mapped[bool] = mapped_column(nullable=False, default=True)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Indexes
    __table_args__ = (
        Index("ix_activities_prompt", "prompt_id"),
        Index("ix_activities_actor", "actor_id"),
        Index("ix_activities_type", "activity_type"),
        Index("ix_activities_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Activity(id={self.id}, type={self.activity_type})>"
