"""
Prompt Model

Core prompt entity for storing all prompt types.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermes.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from hermes.models.version import PromptVersion
    from hermes.models.benchmark import BenchmarkResult


class PromptType(str, enum.Enum):
    """Types of prompts managed by Hermes."""

    AGENT_SYSTEM = "agent_system"
    USER_TEMPLATE = "user_template"
    TOOL_DEFINITION = "tool_definition"
    MCP_INSTRUCTION = "mcp_instruction"


class PromptStatus(str, enum.Enum):
    """Lifecycle status of a prompt."""

    DRAFT = "draft"
    REVIEW = "review"
    STAGED = "staged"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"


class Prompt(Base, UUIDMixin, TimestampMixin):
    """
    Prompt entity representing a versioned prompt.

    Attributes:
        id: Unique identifier (UUID)
        slug: Human-readable unique identifier
        name: Display name
        description: Purpose and usage notes
        type: Prompt type (agent_system, user_template, etc.)
        category: Organizational category
        content: Current prompt content
        variables: Template variable schema (JSON)
        metadata: Custom metadata (JSON)
        version: Current semantic version
        status: Lifecycle status
        owner_id: Creator user/agent ID
        owner_type: Type of owner (user, agent, system)
        team_id: Owning team (optional)
        visibility: Access visibility level
        app_scope: Allowed applications
        repo_scope: Linked Forge repositories
        benchmark_score: Aggregate benchmark score
        last_benchmark_at: Last benchmark timestamp
        deployed_at: Production deployment timestamp
    """

    __tablename__ = "prompts"

    # Identity
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    type: Mapped[PromptType] = mapped_column(
        Enum(PromptType, name="prompt_type"),
        nullable=False,
        index=True,
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    prompt_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Versioning
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256

    # Lifecycle
    status: Mapped[PromptStatus] = mapped_column(
        Enum(PromptStatus, name="prompt_status"),
        nullable=False,
        default=PromptStatus.DRAFT,
        index=True,
    )
    deployed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Ownership
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Access Control
    visibility: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="private",
    )
    app_scope: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    repo_scope: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)

    # Benchmarking
    benchmark_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    last_benchmark_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # External sync
    nursery_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_commit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # Relationships
    versions: Mapped[list["PromptVersion"]] = relationship(
        "PromptVersion",
        back_populates="prompt",
        order_by="desc(PromptVersion.created_at)",
        cascade="all, delete-orphan",
    )
    benchmark_results: Mapped[list["BenchmarkResult"]] = relationship(
        "BenchmarkResult",
        back_populates="prompt",
        order_by="desc(BenchmarkResult.executed_at)",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_prompts_owner_status", "owner_id", "status"),
        Index("ix_prompts_type_category", "type", "category"),
        Index("ix_prompts_visibility", "visibility"),
    )

    def __repr__(self) -> str:
        return f"<Prompt(id={self.id}, slug='{self.slug}', version='{self.version}')>"
