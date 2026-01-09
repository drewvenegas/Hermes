"""
Version Control Service

Git-like version control for prompts.
"""

import difflib
import uuid
from typing import Optional

import semver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models import Prompt, PromptVersion


class VersionControlService:
    """Service for prompt version control operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def compute_diff(old_content: str, new_content: str) -> str:
        """Compute unified diff between two content versions."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
        return "".join(diff)

    @staticmethod
    def parse_version(version: str) -> semver.Version:
        """Parse a semantic version string."""
        return semver.Version.parse(version)

    @staticmethod
    def increment_version(
        version: str,
        bump: str = "patch",
    ) -> str:
        """Increment version by specified component."""
        v = semver.Version.parse(version)
        if bump == "major":
            return str(v.bump_major())
        elif bump == "minor":
            return str(v.bump_minor())
        else:
            return str(v.bump_patch())

    async def get_version(
        self,
        prompt_id: uuid.UUID,
        version: str,
    ) -> Optional[PromptVersion]:
        """Get a specific version of a prompt."""
        query = select(PromptVersion).where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version == version,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        prompt_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptVersion]:
        """List all versions of a prompt."""
        query = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_diff(
        self,
        prompt_id: uuid.UUID,
        from_version: str,
        to_version: str,
    ) -> Optional[str]:
        """Get diff between two versions."""
        from_v = await self.get_version(prompt_id, from_version)
        to_v = await self.get_version(prompt_id, to_version)

        if not from_v or not to_v:
            return None

        return self.compute_diff(from_v.content, to_v.content)

    async def rollback(
        self,
        prompt_id: uuid.UUID,
        to_version: str,
        author_id: uuid.UUID,
    ) -> Optional[Prompt]:
        """Rollback prompt to a previous version."""
        # Get target version
        target = await self.get_version(prompt_id, to_version)
        if not target:
            return None

        # Get current prompt
        query = select(Prompt).where(Prompt.id == prompt_id)
        result = await self.db.execute(query)
        prompt = result.scalar_one_or_none()
        if not prompt:
            return None

        # Compute diff from current to target
        diff = self.compute_diff(prompt.content, target.content)

        # Create new version (rollback creates a new version, doesn't delete history)
        new_version = self.increment_version(prompt.version)
        
        import hashlib
        content_hash = hashlib.sha256(target.content.encode()).hexdigest()

        version = PromptVersion(
            prompt_id=prompt.id,
            version=new_version,
            content=target.content,
            content_hash=content_hash,
            diff=diff,
            change_summary=f"Rollback to version {to_version}",
            author_id=author_id,
            variables=target.variables,
            metadata=target.metadata,
        )
        self.db.add(version)

        # Update prompt
        prompt.content = target.content
        prompt.content_hash = content_hash
        prompt.version = new_version
        prompt.variables = target.variables

        await self.db.flush()
        await self.db.refresh(prompt)

        return prompt

    async def compare_versions(
        self,
        prompt_id: uuid.UUID,
        version_a: str,
        version_b: str,
    ) -> dict:
        """Compare two versions of a prompt."""
        v_a = await self.get_version(prompt_id, version_a)
        v_b = await self.get_version(prompt_id, version_b)

        if not v_a or not v_b:
            return {"error": "One or both versions not found"}

        diff = self.compute_diff(v_a.content, v_b.content)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "diff": diff,
            "version_a_hash": v_a.content_hash,
            "version_b_hash": v_b.content_hash,
            "version_a_created": v_a.created_at.isoformat(),
            "version_b_created": v_b.created_at.isoformat(),
        }
