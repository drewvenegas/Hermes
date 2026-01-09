"""
Template Schemas

Pydantic models for prompt template API operations.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class VariableDefinition(BaseModel):
    """Variable definition in a template."""
    
    name: str = Field(..., description="Variable name (used in {{name}})")
    type: str = Field(default="string", description="Variable type")
    description: str = Field(default="", description="Human-readable description")
    default: Optional[str] = Field(None, description="Default value")
    required: bool = Field(default=True, description="Whether variable is required")
    validation: dict[str, Any] = Field(default_factory=dict, description="Validation rules")


class TemplateExample(BaseModel):
    """Example variable values and output."""
    
    name: str = Field(..., description="Example name")
    variables: dict[str, Any] = Field(..., description="Variable values")
    output: Optional[str] = Field(None, description="Expected output")


class TemplateCreate(BaseModel):
    """Schema for creating a template."""
    
    name: str = Field(..., description="Template display name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Template description")
    content: str = Field(..., description="Template content with {{variable}} placeholders")
    variables: list[VariableDefinition] = Field(default_factory=list)
    category: Optional[str] = Field(None, description="Template category")
    tags: list[str] = Field(default_factory=list)
    is_public: bool = False
    visibility: str = Field(default="private")
    examples: list[TemplateExample] = Field(default_factory=list)
    nested_templates: list[str] = Field(default_factory=list, description="Nested template slugs")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""
    
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[list[VariableDefinition]] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    is_public: Optional[bool] = None
    visibility: Optional[str] = None
    examples: Optional[list[TemplateExample]] = None
    nested_templates: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None
    change_summary: Optional[str] = None


class TemplateResponse(BaseModel):
    """Schema for template response."""
    
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    content: str
    variables: list[dict[str, Any]]
    category: Optional[str]
    tags: list[str]
    is_public: bool
    visibility: str
    fork_count: int
    usage_count: int
    parent_id: Optional[uuid.UUID]
    owner_id: uuid.UUID
    team_id: Optional[uuid.UUID]
    version: str
    metadata: dict[str, Any]
    examples: list[dict[str, Any]]
    nested_templates: list[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    """Schema for paginated template list."""
    
    items: list[TemplateResponse]
    total: int
    limit: int
    offset: int


class RenderRequest(BaseModel):
    """Schema for template rendering request."""
    
    variables: dict[str, Any] = Field(..., description="Variable values")
    validate_output: bool = Field(default=False, description="Validate rendered output")


class RenderResponse(BaseModel):
    """Schema for rendered template response."""
    
    template_id: uuid.UUID
    template_slug: str
    rendered_content: str
    variables_used: dict[str, Any]
    missing_variables: list[str]
    validation_errors: list[str]
    rendered_at: datetime


class ForkRequest(BaseModel):
    """Schema for forking a template."""
    
    new_slug: str = Field(..., description="Slug for the forked template")
    new_name: Optional[str] = Field(None, description="Name for the forked template")


class TemplateVersionResponse(BaseModel):
    """Schema for template version response."""
    
    id: uuid.UUID
    template_id: uuid.UUID
    version: str
    content: str
    variables: list[dict[str, Any]]
    change_summary: Optional[str]
    author_id: uuid.UUID
    created_at: datetime
    
    model_config = {"from_attributes": True}
