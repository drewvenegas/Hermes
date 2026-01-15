"""
ARIA Nursery Synchronization Service

Production-ready bidirectional sync between Hermes prompts and ARIA Nursery.
Features:
- Bidirectional sync (import/export)
- Conflict detection and resolution
- Webhook integration for automatic sync
- Background sync scheduling
- Notification integration
"""

import asyncio
import base64
import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import structlog

from hermes.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class SyncDirection(str, Enum):
    """Sync direction."""
    IMPORT = "import"
    EXPORT = "export"
    BIDIRECTIONAL = "bidirectional"


class ConflictResolution(str, Enum):
    """Conflict resolution strategy."""
    HERMES = "hermes"  # Hermes version wins
    NURSERY = "nursery"  # Nursery version wins
    MANUAL = "manual"  # Require manual resolution
    NEWEST = "newest"  # Most recently modified wins


class SyncStatus(str, Enum):
    """Sync operation status."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    ERROR = "error"


@dataclass
class NurseryPrompt:
    """A prompt from the ARIA Nursery."""
    
    path: str
    name: str
    content: str
    content_hash: str
    agent_type: str
    agent_id: Optional[str] = None
    modified_at: Optional[datetime] = None
    commit_sha: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncConflict:
    """A sync conflict between Hermes and Nursery."""
    
    prompt_id: Optional[uuid.UUID]
    slug: str
    nursery_path: str
    hermes_hash: str
    nursery_hash: str
    hermes_modified: Optional[datetime]
    nursery_modified: Optional[datetime]
    resolution: Optional[ConflictResolution] = None
    resolved_at: Optional[datetime] = None


@dataclass
class SyncResult:
    """Result of a sync operation."""
    
    direction: SyncDirection
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    imported: int = 0
    exported: int = 0
    updated: int = 0
    skipped: int = 0
    conflicts: int = 0
    errors: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)
    conflict_details: List[SyncConflict] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        return len(self.errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "imported": self.imported,
            "exported": self.exported,
            "updated": self.updated,
            "skipped": self.skipped,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "details": self.details,
            "success": self.success,
        }


class NurserySyncService:
    """
    Production-ready service for syncing prompts with ARIA Nursery.
    
    The ARIA Nursery contains agent system prompts as Markdown files
    in the ARIA repository. This service enables:
    - Importing nursery prompts into Hermes
    - Exporting Hermes prompts back to nursery
    - Automatic conflict detection and resolution
    - Webhook-triggered sync on repository changes
    - Background sync scheduling
    """
    
    NURSERY_BASE_PATH = "Nursery"
    AGENT_TYPES = ["executive", "orchestration", "specialists", "subsystems"]
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        aria_repo: str = "DeepCreative/ARIA",
        branch: str = "main",
        default_resolution: ConflictResolution = ConflictResolution.MANUAL,
    ):
        """Initialize nursery sync service.
        
        Args:
            github_token: GitHub token for API access
            aria_repo: ARIA repository (owner/repo)
            branch: Git branch to sync with
            default_resolution: Default conflict resolution strategy
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.aria_repo = aria_repo
        self.branch = branch
        self.default_resolution = default_resolution
        self._client: Optional[httpx.AsyncClient] = None
        
        # Sync state
        self._last_sync: Optional[datetime] = None
        self._pending_conflicts: List[SyncConflict] = []
        
        logger.info(
            "Nursery sync service initialized",
            repo=aria_repo,
            branch=branch,
        )
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Hermes-Nursery-Sync/1.0",
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers=headers,
                timeout=60.0,
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def _compute_hash(self, content: str) -> str:
        """Compute content hash."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _parse_nursery_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from nursery prompt."""
        metadata = {}
        
        if content.startswith("---"):
            try:
                end_idx = content.index("---", 3)
                frontmatter = content[3:end_idx].strip()
                
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()
            except ValueError:
                pass
        
        return metadata
    
    def _extract_prompt_content(self, content: str) -> str:
        """Extract prompt content from nursery markdown."""
        # Remove frontmatter
        if content.startswith("---"):
            try:
                end_idx = content.index("---", 3)
                content = content[end_idx + 3:].strip()
            except ValueError:
                pass
        
        # Find the main prompt section
        lines = content.split("\n")
        prompt_lines = []
        in_prompt = False
        
        for line in lines:
            if line.startswith("#"):
                if "prompt" in line.lower() or "instruction" in line.lower():
                    in_prompt = True
                continue
            
            if in_prompt or not line.startswith("#"):
                prompt_lines.append(line)
        
        return "\n".join(prompt_lines).strip()
    
    def _generate_slug(self, np: NurseryPrompt) -> str:
        """Generate slug from nursery prompt."""
        name = Path(np.path).stem.lower()
        name = re.sub(r"[^a-z0-9]+", "-", name)
        return f"aria-{np.agent_type}-{name}"
    
    # =========================================================================
    # Nursery Listing
    # =========================================================================
    
    async def list_nursery_prompts(
        self,
        agent_types: List[str] = None,
    ) -> List[NurseryPrompt]:
        """List all prompts in the ARIA Nursery.
        
        Args:
            agent_types: Specific agent types to list (default: all)
            
        Returns:
            List of nursery prompts
        """
        client = await self._get_client()
        prompts = []
        types_to_scan = agent_types or self.AGENT_TYPES
        
        for agent_type in types_to_scan:
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
                        agent_id=metadata.get("agent_id"),
                        commit_sha=file_info.get("sha"),
                        metadata=metadata,
                    )
                    prompts.append(prompt)
                    
            except httpx.HTTPError as e:
                logger.error(f"Failed to list nursery prompts at {path}: {e}")
        
        logger.info(f"Listed {len(prompts)} prompts from nursery")
        return prompts
    
    # =========================================================================
    # Import from Nursery
    # =========================================================================
    
    async def import_from_nursery(
        self,
        db_session,
        prompt_store_service,
        owner_id: uuid.UUID,
        overwrite: bool = False,
        conflict_resolution: ConflictResolution = None,
        agent_types: List[str] = None,
        notify: bool = True,
    ) -> SyncResult:
        """Import prompts from ARIA Nursery into Hermes.
        
        Args:
            db_session: Database session
            prompt_store_service: Prompt store service instance
            owner_id: Owner ID for imported prompts
            overwrite: Whether to overwrite existing prompts
            conflict_resolution: How to resolve conflicts
            agent_types: Specific agent types to import
            notify: Whether to send notifications
            
        Returns:
            Sync result
        """
        from hermes.schemas.prompt import PromptCreate, PromptUpdate
        from hermes.models.prompt import PromptType
        
        resolution = conflict_resolution or self.default_resolution
        result = SyncResult(direction=SyncDirection.IMPORT)
        
        logger.info(
            "Starting nursery import",
            overwrite=overwrite,
            resolution=resolution.value,
        )
        
        try:
            nursery_prompts = await self.list_nursery_prompts(agent_types)
            
            for np in nursery_prompts:
                slug = self._generate_slug(np)
                
                try:
                    existing = await prompt_store_service.get_by_slug(slug)
                    
                    if existing:
                        if existing.content_hash == np.content_hash:
                            # Already synced
                            result.skipped += 1
                            continue
                        
                        if not overwrite and resolution == ConflictResolution.MANUAL:
                            # Record conflict for manual resolution
                            conflict = SyncConflict(
                                prompt_id=existing.id,
                                slug=slug,
                                nursery_path=np.path,
                                hermes_hash=existing.content_hash or "",
                                nursery_hash=np.content_hash,
                                hermes_modified=existing.updated_at,
                                nursery_modified=np.modified_at,
                            )
                            result.conflict_details.append(conflict)
                            result.conflicts += 1
                            result.details.append({
                                "slug": slug,
                                "action": "conflict",
                                "nursery_path": np.path,
                            })
                            continue
                        
                        # Resolve conflict based on strategy
                        should_update = self._should_update(
                            existing, np, resolution, overwrite
                        )
                        
                        if should_update:
                            update_data = PromptUpdate(
                                content=np.content,
                                change_summary=f"Synced from ARIA Nursery: {np.path}",
                            )
                            await prompt_store_service.update(
                                existing.id, update_data, author_id=owner_id
                            )
                            result.updated += 1
                            result.details.append({
                                "slug": slug,
                                "action": "updated",
                                "nursery_path": np.path,
                            })
                        else:
                            result.skipped += 1
                    else:
                        # Create new prompt
                        create_data = PromptCreate(
                            slug=slug,
                            name=np.name,
                            type=PromptType.AGENT_SYSTEM,
                            content=np.content,
                            category=np.agent_type,
                            description=f"Imported from ARIA Nursery: {np.path}",
                            visibility="organization",
                            metadata={
                                "nursery_path": np.path,
                                "agent_type": np.agent_type,
                                "agent_id": np.agent_id,
                                "sync_source": "nursery",
                            },
                        )
                        await prompt_store_service.create(
                            create_data, 
                            owner_id=owner_id,
                            nursery_path=np.path,
                        )
                        result.imported += 1
                        result.details.append({
                            "slug": slug,
                            "action": "created",
                            "nursery_path": np.path,
                        })
                    
                except Exception as e:
                    result.errors.append(f"Failed to import {slug}: {str(e)}")
                    logger.error(f"Import error for {slug}", error=str(e))
            
            result.completed_at = datetime.utcnow()
            self._last_sync = result.completed_at
            
            # Send notification if enabled
            if notify and (result.imported > 0 or result.updated > 0 or result.conflicts > 0):
                await self._send_sync_notification(result, owner_id)
            
            logger.info(
                "Nursery import completed",
                imported=result.imported,
                updated=result.updated,
                conflicts=result.conflicts,
                errors=len(result.errors),
            )
            
        except Exception as e:
            result.errors.append(f"Import failed: {str(e)}")
            logger.error("Nursery import failed", error=str(e))
        
        return result
    
    def _should_update(
        self,
        existing,
        nursery: NurseryPrompt,
        resolution: ConflictResolution,
        overwrite: bool,
    ) -> bool:
        """Determine if existing prompt should be updated."""
        if overwrite:
            return True
        
        if resolution == ConflictResolution.NURSERY:
            return True
        elif resolution == ConflictResolution.HERMES:
            return False
        elif resolution == ConflictResolution.NEWEST:
            if nursery.modified_at and existing.updated_at:
                return nursery.modified_at > existing.updated_at
            return False
        else:  # MANUAL
            return False
    
    # =========================================================================
    # Export to Nursery
    # =========================================================================
    
    async def export_to_nursery(
        self,
        prompts: List[Dict[str, Any]],
        commit_message: str = "Sync prompts from Hermes",
        dry_run: bool = False,
    ) -> SyncResult:
        """Export Hermes prompts to ARIA Nursery.
        
        Args:
            prompts: List of prompt data to export
            commit_message: Git commit message
            dry_run: If True, don't actually write to GitHub
            
        Returns:
            Sync result
        """
        client = await self._get_client()
        result = SyncResult(direction=SyncDirection.EXPORT)
        
        logger.info(
            "Starting nursery export",
            prompt_count=len(prompts),
            dry_run=dry_run,
        )
        
        for prompt in prompts:
            path = prompt.get("nursery_path")
            if not path:
                result.skipped += 1
                continue
            
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
                    
                    # Check if content changed
                    existing_content = base64.b64decode(
                        file_response.json().get("content", "")
                    ).decode()
                    if self._compute_hash(existing_content) == self._compute_hash(content):
                        result.skipped += 1
                        continue
                
                if dry_run:
                    result.exported += 1
                    result.details.append({
                        "slug": prompt["slug"],
                        "action": "would_export",
                        "nursery_path": path,
                    })
                    continue
                
                # Update or create file
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
                logger.error(f"Export error for {prompt['slug']}", error=str(e))
        
        result.completed_at = datetime.utcnow()
        
        logger.info(
            "Nursery export completed",
            exported=result.exported,
            skipped=result.skipped,
            errors=len(result.errors),
        )
        
        return result
    
    def _format_for_nursery(self, prompt: Dict[str, Any]) -> str:
        """Format prompt for ARIA Nursery format."""
        lines = [
            "---",
            f"name: {prompt['name']}",
            f"version: {prompt.get('version', '1.0.0')}",
            f"slug: {prompt['slug']}",
            f"hermes_id: {prompt['id']}",
            f"synced_at: {datetime.utcnow().isoformat()}",
            "---",
            "",
            f"# {prompt['name']}",
            "",
        ]
        
        if prompt.get("description"):
            lines.extend([prompt["description"], ""])
        
        lines.extend([
            "## System Prompt",
            "",
            prompt["content"],
        ])
        
        return "\n".join(lines)
    
    # =========================================================================
    # Conflict Management
    # =========================================================================
    
    async def resolve_conflict(
        self,
        db_session,
        prompt_store_service,
        conflict: SyncConflict,
        resolution: ConflictResolution,
        merged_content: str = None,
        user_id: uuid.UUID = None,
    ) -> bool:
        """Resolve a sync conflict.
        
        Args:
            db_session: Database session
            prompt_store_service: Prompt store service
            conflict: The conflict to resolve
            resolution: Resolution strategy
            merged_content: Content for manual merge resolution
            user_id: User resolving the conflict
            
        Returns:
            True if resolved successfully
        """
        from hermes.schemas.prompt import PromptUpdate
        
        try:
            if resolution == ConflictResolution.HERMES:
                # Keep Hermes version, export to nursery
                prompt = await prompt_store_service.get(conflict.prompt_id)
                if prompt:
                    await self.export_to_nursery([{
                        "id": str(prompt.id),
                        "slug": prompt.slug,
                        "name": prompt.name,
                        "content": prompt.content,
                        "version": prompt.version,
                        "description": prompt.description,
                        "nursery_path": conflict.nursery_path,
                    }], commit_message="Conflict resolution: Hermes wins")
                
            elif resolution == ConflictResolution.NURSERY:
                # Import nursery version
                nursery_prompts = await self.list_nursery_prompts()
                for np in nursery_prompts:
                    if np.path == conflict.nursery_path:
                        update_data = PromptUpdate(
                            content=np.content,
                            change_summary="Conflict resolution: Nursery wins",
                        )
                        await prompt_store_service.update(
                            conflict.prompt_id, update_data, author_id=user_id
                        )
                        break
                
            elif resolution == ConflictResolution.MANUAL and merged_content:
                # Use provided merged content
                update_data = PromptUpdate(
                    content=merged_content,
                    change_summary="Conflict resolution: Manual merge",
                )
                await prompt_store_service.update(
                    conflict.prompt_id, update_data, author_id=user_id
                )
            
            conflict.resolution = resolution
            conflict.resolved_at = datetime.utcnow()
            
            # Remove from pending conflicts
            self._pending_conflicts = [
                c for c in self._pending_conflicts
                if c.slug != conflict.slug
            ]
            
            logger.info(
                "Conflict resolved",
                slug=conflict.slug,
                resolution=resolution.value,
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve conflict: {e}")
            return False
    
    # =========================================================================
    # Status and Notifications
    # =========================================================================
    
    async def get_sync_status(
        self,
        db_session,
        prompt_store_service,
    ) -> Dict[str, Any]:
        """Get current sync status between Hermes and Nursery."""
        nursery_prompts = await self.list_nursery_prompts()
        
        status = {
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "nursery_count": len(nursery_prompts),
            "synced": 0,
            "pending_import": 0,
            "pending_export": 0,
            "conflicts": 0,
            "conflict_details": [],
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
                status["conflict_details"].append({
                    "slug": slug,
                    "nursery_path": np.path,
                    "hermes_id": str(existing.id) if existing else None,
                })
        
        return status
    
    async def _send_sync_notification(
        self,
        result: SyncResult,
        user_id: uuid.UUID,
    ):
        """Send notification about sync completion."""
        try:
            from hermes.integrations.beeper import get_beeper_client
            beeper = get_beeper_client()
            
            await beeper.notify_sync_complete(
                imported=result.imported,
                updated=result.updated,
                conflicts=result.conflicts,
                recipients=[str(user_id)],
            )
        except Exception as e:
            logger.warning(f"Failed to send sync notification: {e}")
    
    # =========================================================================
    # Webhook Handler
    # =========================================================================
    
    async def handle_webhook(
        self,
        event_type: str,
        payload: Dict[str, Any],
        db_session,
        prompt_store_service,
        owner_id: uuid.UUID,
    ) -> Optional[SyncResult]:
        """Handle GitHub webhook for automatic sync.
        
        Args:
            event_type: GitHub event type (e.g., "push")
            payload: Webhook payload
            db_session: Database session
            prompt_store_service: Prompt store service
            owner_id: Owner ID for imported prompts
            
        Returns:
            Sync result if sync was triggered
        """
        if event_type != "push":
            return None
        
        # Check if push affected nursery
        ref = payload.get("ref", "")
        if not ref.endswith(f"/{self.branch}"):
            return None
        
        commits = payload.get("commits", [])
        nursery_affected = any(
            any(self.NURSERY_BASE_PATH in f for f in c.get("modified", []) + c.get("added", []))
            for c in commits
        )
        
        if not nursery_affected:
            return None
        
        logger.info("Nursery change detected via webhook, triggering sync")
        
        return await self.import_from_nursery(
            db_session,
            prompt_store_service,
            owner_id,
            overwrite=False,
            conflict_resolution=ConflictResolution.MANUAL,
        )


# =============================================================================
# API Routes
# =============================================================================

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List as TypingList
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permissions
from hermes.auth.models import User
from hermes.services.database import get_db
from hermes.services.prompt_store import PromptStoreService

sync_router = APIRouter(prefix="/api/v1/sync/nursery", tags=["Nursery Sync"])


class ConflictResolutionRequest(BaseModel):
    """Request model for conflict resolution."""
    resolution: str  # hermes, nursery, manual
    merged_content: Optional[str] = None


@sync_router.get("/status")
async def get_nursery_sync_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sync status with ARIA Nursery."""
    sync_service = NurserySyncService()
    prompt_store = PromptStoreService(db)
    
    try:
        status = await sync_service.get_sync_status(db, prompt_store)
        return status
    finally:
        await sync_service.close()


@sync_router.post("/import")
async def import_from_nursery(
    background_tasks: BackgroundTasks,
    overwrite: bool = Query(False, description="Overwrite existing prompts"),
    resolution: str = Query("manual", description="Conflict resolution strategy"),
    agent_types: Optional[TypingList[str]] = Query(None, description="Agent types to import"),
    user: User = Depends(require_permissions(["nursery:sync"])),
    db: AsyncSession = Depends(get_db),
):
    """Import prompts from ARIA Nursery."""
    sync_service = NurserySyncService()
    prompt_store = PromptStoreService(db)
    
    try:
        conflict_res = ConflictResolution(resolution)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid resolution. Must be one of: {[r.value for r in ConflictResolution]}"
        )
    
    try:
        result = await sync_service.import_from_nursery(
            db, prompt_store, user.id,
            overwrite=overwrite,
            conflict_resolution=conflict_res,
            agent_types=agent_types,
        )
        await db.commit()
        return result.to_dict()
    finally:
        await sync_service.close()


@sync_router.post("/export")
async def export_to_nursery(
    prompt_ids: TypingList[str],
    commit_message: str = Query("Sync prompts from Hermes"),
    dry_run: bool = Query(False),
    user: User = Depends(require_permissions(["nursery:sync"])),
    db: AsyncSession = Depends(get_db),
):
    """Export prompts to ARIA Nursery."""
    from sqlalchemy import select
    from hermes.models import Prompt
    
    sync_service = NurserySyncService()
    
    try:
        query = select(Prompt).where(Prompt.id.in_([uuid.UUID(id) for id in prompt_ids]))
        result = await db.execute(query)
        prompts = list(result.scalars().all())
        
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
        
        sync_result = await sync_service.export_to_nursery(
            prompt_data, commit_message, dry_run
        )
        
        return sync_result.to_dict()
    finally:
        await sync_service.close()


@sync_router.post("/resolve-conflict")
async def resolve_sync_conflict(
    slug: str,
    request: ConflictResolutionRequest,
    user: User = Depends(require_permissions(["nursery:sync"])),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a sync conflict."""
    sync_service = NurserySyncService()
    prompt_store = PromptStoreService(db)
    
    try:
        resolution = ConflictResolution(request.resolution)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resolution strategy")
    
    try:
        # Get the prompt
        prompt = await prompt_store.get_by_slug(slug)
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Get sync status to find conflict details
        status = await sync_service.get_sync_status(db, prompt_store)
        conflict_info = next(
            (c for c in status.get("conflict_details", []) if c["slug"] == slug),
            None
        )
        
        if not conflict_info:
            raise HTTPException(status_code=404, detail="Conflict not found")
        
        # Create conflict object
        conflict = SyncConflict(
            prompt_id=prompt.id,
            slug=slug,
            nursery_path=conflict_info["nursery_path"],
            hermes_hash=prompt.content_hash or "",
            nursery_hash="",  # Will be fetched during resolution
            hermes_modified=prompt.updated_at,
            nursery_modified=None,
        )
        
        success = await sync_service.resolve_conflict(
            db, prompt_store, conflict, resolution,
            merged_content=request.merged_content,
            user_id=user.id,
        )
        
        if success:
            await db.commit()
            return {"status": "resolved", "resolution": resolution.value}
        else:
            raise HTTPException(status_code=500, detail="Failed to resolve conflict")
            
    finally:
        await sync_service.close()


@sync_router.post("/webhook")
async def handle_github_webhook(
    payload: Dict[str, Any],
    event_type: str = Query(..., alias="X-GitHub-Event"),
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub webhook for automatic sync."""
    sync_service = NurserySyncService()
    prompt_store = PromptStoreService(db)
    
    # Use system user for webhook-triggered syncs
    system_user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    
    try:
        result = await sync_service.handle_webhook(
            event_type, payload, db, prompt_store, system_user_id
        )
        
        if result:
            await db.commit()
            return result.to_dict()
        
        return {"status": "ignored", "reason": "Not a nursery change"}
    finally:
        await sync_service.close()
