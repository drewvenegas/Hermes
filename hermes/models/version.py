"""
Prompt Version Model

Version history for prompts with diff tracking.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermes.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from hermes.models.prompt import Prompt


class PromptVersion(Base, UUIDMixin, TimestampMixin):
    """
    Version history entry for a prompt.

    Attributes:
        id: Unique version ID
        prompt_id: Parent prompt ID
        version: Semantic version string
        content: Prompt content at this version
        content_hash: SHA-256 hash of content
        diff: Diff from previous version
        change_summary: Human-readable change description
        author_id: Who created this version
        benchmark_results: Snapshot of benchmark results
    """

    __tablename__ = "prompt_versions"

    # Reference
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Version info
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Change tracking
    diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Metadata at version time
    variables: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    version_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Benchmark snapshot
    benchmark_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="versions")

    # Indexes
    __table_args__ = (
        Index("ix_prompt_versions_prompt_version", "prompt_id", "version", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PromptVersion(prompt_id={self.prompt_id}, version='{self.version}')>"
