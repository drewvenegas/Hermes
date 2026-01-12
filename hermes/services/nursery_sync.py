"""
ARIA Nursery Synchronization Service

Bidirectional sync between Hermes prompts and ARIA Nursery.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

import httpx

from hermes.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class NurseryPrompt:
    """A prompt from the ARIA Nursery."""
    
    path: str
    name: str
    content: str
    content_hash: str
    agent_type: str
    modified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    
    imported: int = 0
    exported: int = 0
    conflicts: int = 0
    errors: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)


class NurserySyncService:
    """Service for syncing prompts with ARIA Nursery.
    
    The ARIA Nursery contains agent system prompts as Markdown files
    in the ARIA repository. This service enables:
    - Importing nursery prompts into Hermes
    - Exporting Hermes prompts back to nursery
    - Tracking sync status and conflicts
    """
    
    NURSERY_BASE_PATH = "Nursery"
    # Must match actual directories in ARIA/Nursery/
    AGENT_TYPES = ["executive", "orchestration", "specialists", "subsystems"]
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        aria_repo: str = "DeepCreative/ARIA",
        branch: str = "main",
    ):
        """Initialize nursery sync service.
        
        Args:
            github_token: GitHub token for API access
            aria_repo: ARIA repository (owner/repo)
            branch: Git branch to sync with
        """
        self.github_token = github_token
        self.aria_repo = aria_repo
        self.branch = branch
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {"Accept": "application/vnd.github.v3+json"}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers=headers,
                timeout=30.0,
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _compute_hash(self, content: str) -> str:
        """Compute content hash."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _parse_nursery_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from nursery prompt.
        
        Args:
            content: Markdown content with optional frontmatter
            
        Returns:
            Parsed frontmatter as dict
        """
        metadata = {}
        
        # Check for YAML frontmatter
        if content.startswith("---"):
            try:
                end_idx = content.index("---", 3)
                frontmatter = content[3:end_idx].strip()
                
                # Simple YAML parsing
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()
            except ValueError:
                pass
        
        return metadata
    
    def _extract_prompt_content(self, content: str) -> str:
        """Extract prompt content from nursery markdown.
        
        Args:
            content: Full markdown content
            
        Returns:
            Extracted prompt content
        """
        # Remove frontmatter
        if content.startswith("---"):
            try:
                end_idx = content.index("---", 3)
                content = content[end_idx + 3:].strip()
            except ValueError:
                pass
        
        # Find the main prompt section (usually after headers)
        lines = content.split("\n")
        prompt_lines = []
        in_prompt = False
        
        for line in lines:
            # Skip header lines until we find content
            if line.startswith("#"):
                if "prompt" in line.lower() or "instruction" in line.lower():
                    in_prompt = True
                continue
            
            if in_prompt or not line.startswith("#"):
                prompt_lines.append(line)
        
        return "\n".join(prompt_lines).strip()
    
    async def list_nursery_prompts(self) -> List[NurseryPrompt]:
        """List all prompts in the ARIA Nursery.
        
        Returns:
            List of nursery prompts
        """
        client = await self._get_client()
        prompts = []
        
        for agent_type in self.AGENT_TYPES:
            path = f"{self.NURSERY_BASE_PATH}/{agent_type}"
            
            try:
                response = await client.get(
                    f"/repos/{self.aria_repo}/contents/{path}",
                    params={"ref": self.branch},
                )
                
                if response.status_code == 404:
                    logger.debug(f"Nursery path not found: {path}")
                    continue
                
                response.raise_for_status()
                files = response.json()
                
                for file_info in files:
                    if not file_info["name"].endswith(".md"):
                        continue
                    
                    # Fetch file content
                    content_response = await client.get(file_info["download_url"])
                    content = content_response.text
                    
                    metadata = self._parse_nursery_frontmatter(content)
                    prompt_content = self._extract_prompt_content(content)
                    
                    prompt = NurseryPrompt(
                        path=file_info["path"],
                        name=Path(file_info["name"]).stem.replace("_", " ").title(),
                        content=prompt_content,
                        content_hash=self._compute_hash(prompt_content),
                        agent_type=agent_type,
                        metadata=metadata,
                    )
                    prompts.append(prompt)
                    
            except httpx.HTTPError as e:
                logger.error(f"Failed to list nursery prompts at {path}: {e}")
        
        return prompts
    
    async def import_from_nursery(
        self,
        db_session,
        prompt_store_service,
        owner_id,
        overwrite: bool = False,
    ) -> SyncResult:
        """Import prompts from ARIA Nursery into Hermes.
        
        Args:
            db_session: Database session
            prompt_store_service: Prompt store service instance
            owner_id: Owner ID for imported prompts
            overwrite: Whether to overwrite existing prompts
            
        Returns:
            Sync result
        """
        from hermes.schemas.prompt import PromptCreate, PromptUpdate
        from hermes.models.prompt import PromptType, PromptStatus
        
        result = SyncResult()
        nursery_prompts = await self.list_nursery_prompts()
        
        for np in nursery_prompts:
            slug = self._generate_slug(np)
            
            try:
                # Check if prompt exists
                existing = await prompt_store_service.get_by_slug(slug)
                
                if existing:
                    if not overwrite:
                        # Check for conflict
                        if existing.content_hash != np.content_hash:
                            result.conflicts += 1
                            result.details.append({
                                "slug": slug,
                                "action": "conflict",
                                "nursery_path": np.path,
                            })
                        continue
                    
                    # Update existing
                    update_data = PromptUpdate(
                        content=np.content,
                        change_summary=f"Synced from ARIA Nursery: {np.path}",
                    )
                    await prompt_store_service.update(
                        existing.id, update_data, author_id=owner_id
                    )
                    result.details.append({
                        "slug": slug,
                        "action": "updated",
                        "nursery_path": np.path,
                    })
                else:
                    # Create new
                    create_data = PromptCreate(
                        slug=slug,
                        name=np.name,
                        type=PromptType.AGENT_SYSTEM,
                        content=np.content,
                        category=np.agent_type,
                        visibility="organization",
                    )
                    await prompt_store_service.create(
                        create_data, owner_id=owner_id,
                        nursery_path=np.path,
                    )
                    result.details.append({
                        "slug": slug,
                        "action": "created",
                        "nursery_path": np.path,
                    })
                
                result.imported += 1
                
            except Exception as e:
                result.errors.append(f"Failed to import {slug}: {e}")
                logger.error(f"Failed to import {slug}: {e}")
        
        return result
    
    def _generate_slug(self, np: NurseryPrompt) -> str:
        """Generate slug from nursery prompt.
        
        Args:
            np: Nursery prompt
            
        Returns:
            Slug string
        """
        name = Path(np.path).stem.lower()
        name = re.sub(r"[^a-z0-9]+", "-", name)
        return f"aria-{np.agent_type}-{name}"
    
    async def export_to_nursery(
        self,
        prompts: List[Dict[str, Any]],
        commit_message: str = "Sync prompts from Hermes",
    ) -> SyncResult:
        """Export Hermes prompts to ARIA Nursery.
        
        Args:
            prompts: List of prompt data to export
            commit_message: Git commit message
            
        Returns:
            Sync result
        """
        client = await self._get_client()
        result = SyncResult()
        
        for prompt in prompts:
            if not prompt.get("nursery_path"):
                continue
            
            path = prompt["nursery_path"]
            content = self._format_for_nursery(prompt)
            
            try:
                # Get current file SHA
                file_response = await client.get(
                    f"/repos/{self.aria_repo}/contents/{path}",
                    params={"ref": self.branch},
                )
                
                sha = None
                if file_response.status_code == 200:
                    sha = file_response.json().get("sha")
                
                # Update or create file
                import base64
                encoded_content = base64.b64encode(content.encode()).decode()
                
                payload = {
                    "message": f"{commit_message}: {prompt['slug']}",
                    "content": encoded_content,
                    "branch": self.branch,
                }
                if sha:
                    payload["sha"] = sha
                
                response = await client.put(
                    f"/repos/{self.aria_repo}/contents/{path}",
                    json=payload,
                )
                response.raise_for_status()
                
                result.exported += 1
                result.details.append({
                    "slug": prompt["slug"],
                    "action": "exported",
                    "nursery_path": path,
                })
                
            except httpx.HTTPError as e:
                result.errors.append(f"Failed to export {prompt['slug']}: {e}")
                logger.error(f"Failed to export {prompt['slug']}: {e}")
        
        return result
    
    def _format_for_nursery(self, prompt: Dict[str, Any]) -> str:
        """Format prompt for ARIA Nursery format.
        
        Args:
            prompt: Prompt data
            
        Returns:
            Formatted markdown content
        """
        lines = [
            "---",
            f"name: {prompt['name']}",
            f"version: {prompt['version']}",
            f"slug: {prompt['slug']}",
            f"hermes_id: {prompt['id']}",
            "---",
            "",
            f"# {prompt['name']}",
            "",
            prompt.get("description", ""),
            "",
            "## System Prompt",
            "",
            prompt["content"],
        ]
        return "\n".join(lines)
    
    async def get_sync_status(
        self,
        db_session,
        prompt_store_service,
    ) -> Dict[str, Any]:
        """Get current sync status between Hermes and Nursery.
        
        Args:
            db_session: Database session
            prompt_store_service: Prompt store service
            
        Returns:
            Sync status information
        """
        nursery_prompts = await self.list_nursery_prompts()
        
        status = {
            "nursery_count": len(nursery_prompts),
            "synced": 0,
            "pending_import": 0,
            "pending_export": 0,
            "conflicts": 0,
        }
        
        for np in nursery_prompts:
            slug = self._generate_slug(np)
            existing = await prompt_store_service.get_by_slug(slug)
            
            if not existing:
                status["pending_import"] += 1
            elif existing.content_hash == np.content_hash:
                status["synced"] += 1
            else:
                status["conflicts"] += 1
        
        return status


# API routes for nursery sync
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import require_permission
from hermes.auth.models import User
from hermes.services.database import get_db
from hermes.services.prompt_store import PromptStoreService

sync_router = APIRouter(prefix="/api/v1/sync/nursery", tags=["Nursery Sync"])


@sync_router.get("/status")
async def get_nursery_sync_status(
    user: User = Depends(require_permission("nursery:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get sync status with ARIA Nursery."""
    import os
    
    sync_service = NurserySyncService(
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    prompt_store = PromptStoreService(db)
    
    try:
        status = await sync_service.get_sync_status(db, prompt_store)
        return status
    finally:
        await sync_service.close()


@sync_router.post("/import")
async def import_from_nursery(
    background_tasks: BackgroundTasks,
    overwrite: bool = False,
    user: User = Depends(require_permission("nursery:sync")),
    db: AsyncSession = Depends(get_db),
):
    """Import prompts from ARIA Nursery."""
    import os
    
    sync_service = NurserySyncService(
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    prompt_store = PromptStoreService(db)
    
    try:
        result = await sync_service.import_from_nursery(
            db, prompt_store, user.id, overwrite=overwrite
        )
        await db.commit()
        return {
            "status": "completed",
            "imported": result.imported,
            "conflicts": result.conflicts,
            "errors": result.errors,
            "details": result.details,
        }
    finally:
        await sync_service.close()


@sync_router.post("/export")
async def export_to_nursery(
    prompt_ids: List[str],
    user: User = Depends(require_permission("nursery:sync")),
    db: AsyncSession = Depends(get_db),
):
    """Export prompts to ARIA Nursery."""
    import os
    from sqlalchemy import select
    from hermes.models import Prompt
    
    sync_service = NurserySyncService(
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    
    try:
        # Get prompts
        query = select(Prompt).where(Prompt.id.in_([uuid.UUID(id) for id in prompt_ids]))
        result = await db.execute(query)
        prompts = list(result.scalars().all())
        
        # Convert to dicts
        prompt_data = [
            {
                "id": str(p.id),
                "slug": p.slug,
                "name": p.name,
                "content": p.content,
                "version": p.version,
                "description": p.description,
                "nursery_path": p.nursery_path,
            }
            for p in prompts if p.nursery_path
        ]
        
        sync_result = await sync_service.export_to_nursery(prompt_data)
        
        return {
            "status": "completed",
            "exported": sync_result.exported,
            "errors": sync_result.errors,
            "details": sync_result.details,
        }
    finally:
        await sync_service.close()
