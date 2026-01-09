"""
Template Service

Jinja2-based template rendering and management.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import BaseLoader, Environment, TemplateSyntaxError, UndefinedError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models.template import (
    PromptTemplate,
    TemplateStatus,
    TemplateUsage,
    TemplateVersion,
    VariableType,
)

logger = logging.getLogger(__name__)


class TemplateValidationError(Exception):
    """Raised when template validation fails."""
    pass


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""
    pass


# Custom Jinja2 environment
def create_jinja_env() -> Environment:
    """Create Jinja2 environment with safe defaults."""
    env = Environment(
        loader=BaseLoader(),
        autoescape=False,
        variable_start_string="{{",
        variable_end_string="}}",
        block_start_string="{%",
        block_end_string="%}",
        comment_start_string="{#",
        comment_end_string="#}",
    )
    return env


jinja_env = create_jinja_env()


class TemplateService:
    """Service for template CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        slug: str,
        name: str,
        content: str,
        owner_id: uuid.UUID,
        variables: Optional[List[Dict]] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        parent_template_id: Optional[uuid.UUID] = None,
        visibility: str = "private",
    ) -> PromptTemplate:
        """Create a new template."""
        # Validate template content
        self._validate_template(content, variables or [])
        
        template = PromptTemplate(
            slug=slug,
            name=name,
            description=description,
            content=content,
            variables=variables or [],
            parent_template_id=parent_template_id,
            category=category,
            tags=tags or [],
            owner_id=owner_id,
            visibility=visibility,
        )
        
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        
        # Create initial version
        version = TemplateVersion(
            template_id=template.id,
            version=template.version,
            content=template.content,
            variables=template.variables,
            change_summary="Initial version",
            author_id=owner_id,
        )
        self.db.add(version)
        
        return template

    async def get(self, template_id: uuid.UUID) -> Optional[PromptTemplate]:
        """Get template by ID."""
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[PromptTemplate]:
        """Get template by slug."""
        query = select(PromptTemplate).where(PromptTemplate.slug == slug)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[uuid.UUID] = None,
        is_curated: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PromptTemplate], int]:
        """List templates with filtering."""
        query = select(PromptTemplate)
        
        if category:
            query = query.where(PromptTemplate.category == category)
        if status:
            query = query.where(PromptTemplate.status == status)
        if owner_id:
            query = query.where(PromptTemplate.owner_id == owner_id)
        if is_curated is not None:
            query = query.where(PromptTemplate.is_curated == is_curated)
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (PromptTemplate.name.ilike(search_pattern)) |
                (PromptTemplate.description.ilike(search_pattern)) |
                (PromptTemplate.slug.ilike(search_pattern))
            )
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Apply pagination
        query = query.order_by(PromptTemplate.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        templates = list(result.scalars().all())
        
        return templates, total

    async def update(
        self,
        template_id: uuid.UUID,
        author_id: uuid.UUID,
        change_summary: Optional[str] = None,
        **kwargs,
    ) -> Optional[PromptTemplate]:
        """Update a template and create new version."""
        template = await self.get(template_id)
        if not template:
            return None
        
        # Validate new content if provided
        new_content = kwargs.get("content", template.content)
        new_variables = kwargs.get("variables", template.variables)
        self._validate_template(new_content, new_variables)
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(template, key) and value is not None:
                setattr(template, key, value)
        
        # Increment version
        old_version = template.version
        template.version = self._increment_version(old_version)
        
        # Create version record
        version = TemplateVersion(
            template_id=template.id,
            version=template.version,
            content=template.content,
            variables=template.variables,
            change_summary=change_summary or f"Updated from {old_version}",
            author_id=author_id,
        )
        self.db.add(version)
        
        await self.db.flush()
        await self.db.refresh(template)
        
        return template

    async def fork(
        self,
        template_id: uuid.UUID,
        new_slug: str,
        owner_id: uuid.UUID,
        new_name: Optional[str] = None,
    ) -> PromptTemplate:
        """Fork a template."""
        original = await self.get(template_id)
        if not original:
            raise ValueError(f"Template {template_id} not found")
        
        # Create fork
        forked = PromptTemplate(
            slug=new_slug,
            name=new_name or f"{original.name} (Fork)",
            description=original.description,
            content=original.content,
            variables=original.variables.copy(),
            category=original.category,
            tags=original.tags.copy(),
            owner_id=owner_id,
            forked_from_id=original.id,
            visibility="private",
        )
        
        self.db.add(forked)
        
        # Increment fork count
        original.fork_count += 1
        
        await self.db.flush()
        await self.db.refresh(forked)
        
        # Create initial version
        version = TemplateVersion(
            template_id=forked.id,
            version=forked.version,
            content=forked.content,
            variables=forked.variables,
            change_summary=f"Forked from {original.slug}",
            author_id=owner_id,
        )
        self.db.add(version)
        
        return forked

    async def get_versions(
        self,
        template_id: uuid.UUID,
        limit: int = 20,
    ) -> List[TemplateVersion]:
        """Get version history for a template."""
        query = (
            select(TemplateVersion)
            .where(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def record_usage(
        self,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        variable_values: Dict[str, Any],
        prompt_id: Optional[uuid.UUID] = None,
    ):
        """Record template usage for analytics."""
        usage = TemplateUsage(
            template_id=template_id,
            prompt_id=prompt_id,
            user_id=user_id,
            variable_values=variable_values,
        )
        self.db.add(usage)
        
        # Increment usage count
        template = await self.get(template_id)
        if template:
            template.usage_count += 1
        
        await self.db.flush()

    def _validate_template(self, content: str, variables: List[Dict]):
        """Validate template content and variables."""
        try:
            # Try to parse the template
            jinja_env.from_string(content)
        except TemplateSyntaxError as e:
            raise TemplateValidationError(f"Template syntax error: {e}")
        
        # Extract variables from content
        content_vars = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", content))
        
        # Check all content variables are defined
        defined_vars = {v["name"] for v in variables}
        undefined = content_vars - defined_vars
        
        if undefined:
            raise TemplateValidationError(
                f"Variables used in template but not defined: {undefined}"
            )
        
        # Validate variable definitions
        for var in variables:
            if "name" not in var:
                raise TemplateValidationError("Variable must have a 'name' field")
            if "type" not in var:
                raise TemplateValidationError(f"Variable '{var['name']}' must have a 'type' field")
            
            var_type = var["type"]
            if var_type not in [t.value for t in VariableType]:
                raise TemplateValidationError(
                    f"Invalid variable type '{var_type}' for '{var['name']}'"
                )

    def _increment_version(self, version: str) -> str:
        """Increment minor version."""
        parts = version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
        return f"{version}.1"


class TemplateRenderer:
    """Renders templates with variable values."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = TemplateService(db)

    async def render(
        self,
        template_id: uuid.UUID,
        variables: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Render a template with given variable values.
        
        Args:
            template_id: Template to render
            variables: Variable values to substitute
            user_id: User performing the render (for usage tracking)
            
        Returns:
            Rendered template content
            
        Raises:
            TemplateRenderError: If rendering fails
        """
        template = await self.service.get(template_id)
        if not template:
            raise TemplateRenderError(f"Template {template_id} not found")
        
        return await self.render_content(
            template.content,
            template.variables,
            variables,
            template_id=template_id,
            user_id=user_id,
        )

    async def render_content(
        self,
        content: str,
        variable_definitions: List[Dict],
        values: Dict[str, Any],
        template_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Render template content with validation.
        
        Args:
            content: Template content
            variable_definitions: Variable definitions from template
            values: Variable values to substitute
            template_id: Optional template ID for usage tracking
            user_id: Optional user ID for usage tracking
            
        Returns:
            Rendered content
        """
        # Validate and prepare variables
        render_values = {}
        
        for var_def in variable_definitions:
            name = var_def["name"]
            var_type = var_def["type"]
            required = var_def.get("required", False)
            default = var_def.get("default")
            
            if name in values:
                value = values[name]
            elif default is not None:
                value = default
            elif required:
                raise TemplateRenderError(f"Required variable '{name}' not provided")
            else:
                value = ""
            
            # Type coercion
            try:
                render_values[name] = self._coerce_value(value, var_type, var_def)
            except ValueError as e:
                raise TemplateRenderError(f"Invalid value for '{name}': {e}")
        
        # Render template
        try:
            jinja_template = jinja_env.from_string(content)
            rendered = jinja_template.render(**render_values)
        except UndefinedError as e:
            raise TemplateRenderError(f"Undefined variable: {e}")
        except Exception as e:
            raise TemplateRenderError(f"Render error: {e}")
        
        # Track usage
        if template_id and user_id:
            await self.service.record_usage(template_id, user_id, values)
        
        return rendered

    async def preview(
        self,
        content: str,
        variable_definitions: List[Dict],
        values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Preview template rendering without saving.
        
        Returns both rendered content and validation results.
        """
        errors = []
        warnings = []
        rendered = None
        
        # Use defaults for missing values
        preview_values = {}
        for var_def in variable_definitions:
            name = var_def["name"]
            if values and name in values:
                preview_values[name] = values[name]
            elif var_def.get("default") is not None:
                preview_values[name] = var_def["default"]
                warnings.append(f"Using default value for '{name}'")
            else:
                preview_values[name] = f"[{name}]"
                warnings.append(f"No value provided for '{name}'")
        
        try:
            rendered = await self.render_content(
                content,
                variable_definitions,
                preview_values,
            )
        except TemplateRenderError as e:
            errors.append(str(e))
        
        return {
            "rendered": rendered,
            "errors": errors,
            "warnings": warnings,
            "variables_used": list(preview_values.keys()),
        }

    def _coerce_value(
        self,
        value: Any,
        var_type: str,
        var_def: Dict,
    ) -> Any:
        """Coerce value to the expected type."""
        if var_type == VariableType.STRING.value:
            return str(value)
        elif var_type == VariableType.TEXT.value:
            return str(value)
        elif var_type == VariableType.NUMBER.value:
            return float(value)
        elif var_type == VariableType.BOOLEAN.value:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "1", "yes")
        elif var_type == VariableType.SELECT.value:
            options = var_def.get("options", [])
            if value not in options:
                raise ValueError(f"Value must be one of: {options}")
            return value
        elif var_type == VariableType.MULTISELECT.value:
            options = var_def.get("options", [])
            if not isinstance(value, list):
                value = [value]
            for v in value:
                if v not in options:
                    raise ValueError(f"Value must be one of: {options}")
            return value
        elif var_type == VariableType.JSON.value:
            if isinstance(value, (dict, list)):
                return value
            import json
            return json.loads(value)
        else:
            return value
