"""
Prompt Template Model

Reusable templates with variables for prompt generation.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hermes.models.base import Base, TimestampMixin, UUIDMixin


class VariableType(str, Enum):
    """Template variable types."""
    STRING = "string"
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTISELECT = "multiselect"
    JSON = "json"


class TemplateStatus(str, Enum):
    """Template status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PromptTemplate(Base, UUIDMixin, TimestampMixin):
    """
    Reusable prompt template with variables.

    Templates allow creating parameterized prompts that can be
    instantiated with different variable values.
    
    Attributes:
        id: Unique template ID
        slug: URL-friendly identifier
        name: Human-readable name
        description: Template description
        content: Template content with {{variable}} placeholders
        variables: List of variable definitions
        parent_template_id: For nested/composed templates
        category: Template category
        tags: Searchable tags
        version: Semantic version
        status: Template status
        owner_id: Template creator
        fork_count: Number of forks
        usage_count: Number of instantiations
    """

    __tablename__ = "prompt_templates"

    # Identity
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Template content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Variables: list of {name, type, description, default, required, options, validation}
    variables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Composition - for nested templates
    parent_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True,
        index=True,
    )
    
    # Forking
    forked_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Classification
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Version
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Status
    status: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default=TemplateStatus.DRAFT.value,
        index=True,
    )

    # Ownership
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="private")

    # Usage stats
    fork_count: Mapped[int] = mapped_column(nullable=False, default=0)
    usage_count: Mapped[int] = mapped_column(nullable=False, default=0)

    # Metadata
    template_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Featured/curated
    is_curated: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_featured: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Indexes
    __table_args__ = (
        Index("ix_templates_owner", "owner_id"),
        Index("ix_templates_status", "status"),
        Index("ix_templates_curated", "is_curated"),
        Index("ix_templates_featured", "is_featured"),
    )

    def __repr__(self) -> str:
        return f"<PromptTemplate(slug={self.slug}, name={self.name})>"


class TemplateVersion(Base, UUIDMixin, TimestampMixin):
    """
    Version history for templates.
    
    Attributes:
        id: Version ID
        template_id: Parent template
        version: Semantic version
        content: Template content at this version
        variables: Variables at this version
        change_summary: Description of changes
        author_id: Who made the change
    """

    __tablename__ = "template_versions"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_template_versions_template_version", "template_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<TemplateVersion(template_id={self.template_id}, version={self.version})>"


class TemplateUsage(Base, UUIDMixin, TimestampMixin):
    """
    Tracks template usage for analytics.
    
    Attributes:
        id: Usage record ID
        template_id: Template used
        prompt_id: Prompt created from template
        user_id: User who used the template
        variable_values: Values used for instantiation
    """

    __tablename__ = "template_usages"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    prompt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    variable_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Indexes
    __table_args__ = (
        Index("ix_template_usages_template", "template_id"),
        Index("ix_template_usages_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<TemplateUsage(template_id={self.template_id}, user_id={self.user_id})>"
