"""
Prompt Store Service

Core prompt storage and retrieval operations.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hermes.models import Prompt, PromptType, PromptStatus, PromptVersion
from hermes.schemas.prompt import PromptCreate, PromptUpdate, PromptQuery


class PromptStoreService:
    """Service for prompt CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA-256 hash of prompt content."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def create(
        self,
        data: PromptCreate,
        owner_id: uuid.UUID,
        owner_type: str = "user",
    ) -> Prompt:
        """Create a new prompt."""
        content_hash = self.compute_hash(data.content)

        prompt = Prompt(
            slug=data.slug,
            name=data.name,
            description=data.description,
            type=data.type,
            category=data.category,
            tags=data.tags,
            content=data.content,
            variables=data.variables,
            metadata=data.metadata,
            version="1.0.0",
            content_hash=content_hash,
            status=PromptStatus.DRAFT,
            owner_id=owner_id,
            owner_type=owner_type,
            team_id=data.team_id,
            visibility=data.visibility or "private",
            app_scope=data.app_scope,
            repo_scope=data.repo_scope,
        )

        self.db.add(prompt)
        await self.db.flush()

        # Create initial version
        version = PromptVersion(
            prompt_id=prompt.id,
            version="1.0.0",
            content=data.content,
            content_hash=content_hash,
            change_summary="Initial version",
            author_id=owner_id,
            variables=data.variables,
            metadata=data.metadata,
        )
        self.db.add(version)

        await self.db.flush()
        await self.db.refresh(prompt)

        return prompt

    async def get(
        self,
        prompt_id: uuid.UUID,
        include_versions: bool = False,
    ) -> Optional[Prompt]:
        """Get a prompt by ID."""
        query = select(Prompt).where(Prompt.id == prompt_id)

        if include_versions:
            query = query.options(selectinload(Prompt.versions))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Prompt]:
        """Get a prompt by slug."""
        query = select(Prompt).where(Prompt.slug == slug)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        query: PromptQuery,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Prompt], int]:
        """List prompts with filtering."""
        stmt = select(Prompt)

        # Apply filters
        if query.type:
            stmt = stmt.where(Prompt.type == query.type)
        if query.status:
            stmt = stmt.where(Prompt.status == query.status)
        if query.category:
            stmt = stmt.where(Prompt.category == query.category)
        if query.owner_id:
            stmt = stmt.where(Prompt.owner_id == query.owner_id)
        if query.team_id:
            stmt = stmt.where(Prompt.team_id == query.team_id)
        if query.visibility:
            stmt = stmt.where(Prompt.visibility == query.visibility)
        if query.search:
            search_term = f"%{query.search}%"
            stmt = stmt.where(
                or_(
                    Prompt.name.ilike(search_term),
                    Prompt.description.ilike(search_term),
                    Prompt.slug.ilike(search_term),
                )
            )

        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Apply pagination and ordering
        stmt = stmt.order_by(Prompt.updated_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        prompts = list(result.scalars().all())

        return prompts, total

    async def update(
        self,
        prompt_id: uuid.UUID,
        data: PromptUpdate,
        author_id: uuid.UUID,
    ) -> Optional[Prompt]:
        """Update a prompt, creating a new version if content changed."""
        prompt = await self.get(prompt_id)
        if not prompt:
            return None

        content_changed = False
        if data.content is not None and data.content != prompt.content:
            content_changed = True
            new_hash = self.compute_hash(data.content)
        else:
            new_hash = prompt.content_hash

        # Update fields
        if data.name is not None:
            prompt.name = data.name
        if data.description is not None:
            prompt.description = data.description
        if data.category is not None:
            prompt.category = data.category
        if data.tags is not None:
            prompt.tags = data.tags
        if data.content is not None:
            prompt.content = data.content
            prompt.content_hash = new_hash
        if data.variables is not None:
            prompt.variables = data.variables
        if data.metadata is not None:
            prompt.metadata = data.metadata
        if data.status is not None:
            prompt.status = data.status
            if data.status == PromptStatus.DEPLOYED:
                prompt.deployed_at = datetime.utcnow()
        if data.visibility is not None:
            prompt.visibility = data.visibility
        if data.app_scope is not None:
            prompt.app_scope = data.app_scope
        if data.repo_scope is not None:
            prompt.repo_scope = data.repo_scope

        # Create new version if content changed
        if content_changed:
            new_version = self._increment_version(prompt.version)
            prompt.version = new_version

            # Compute diff
            from hermes.services.version_control import VersionControlService
            vc = VersionControlService(self.db)
            diff = vc.compute_diff(prompt.content, data.content)

            version = PromptVersion(
                prompt_id=prompt.id,
                version=new_version,
                content=data.content,
                content_hash=new_hash,
                diff=diff,
                change_summary=data.change_summary or "Content updated",
                author_id=author_id,
                variables=prompt.variables,
                metadata=prompt.metadata,
            )
            self.db.add(version)

        await self.db.flush()
        await self.db.refresh(prompt)

        return prompt

    async def delete(self, prompt_id: uuid.UUID) -> bool:
        """Delete a prompt."""
        prompt = await self.get(prompt_id)
        if not prompt:
            return False

        await self.db.delete(prompt)
        await self.db.flush()
        return True

    def _increment_version(self, version: str) -> str:
        """Increment patch version."""
        import semver
        v = semver.Version.parse(version)
        return str(v.bump_patch())
