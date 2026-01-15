"""
Import/Export Service

Provides bulk import and export of prompts in various formats.
"""

import csv
import io
import json
import re
import uuid
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import structlog
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models.prompt import Prompt, PromptType
from hermes.schemas.prompt import PromptCreate

logger = structlog.get_logger()


class ImportExportService:
    """
    Service for bulk import and export of prompts.
    
    Supports formats:
    - JSON (single prompt or array)
    - CSV (tabular format)
    - Markdown (with YAML frontmatter)
    - ZIP archive (multiple files)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # =========================================================================
    # Export
    # =========================================================================
    
    async def export_prompts(
        self,
        prompt_ids: Optional[List[uuid.UUID]] = None,
        format: str = "json",
        include_metadata: bool = True,
        include_versions: bool = False,
    ) -> Union[str, bytes]:
        """
        Export prompts in the specified format.
        
        Args:
            prompt_ids: List of prompt IDs to export (None for all)
            format: Export format (json, csv, markdown, zip)
            include_metadata: Include prompt metadata
            include_versions: Include version history
            
        Returns:
            Exported data as string or bytes
        """
        # Fetch prompts
        query = select(Prompt).where(Prompt.is_latest == True)
        if prompt_ids:
            query = query.where(Prompt.id.in_(prompt_ids))
        
        result = await self.db.execute(query)
        prompts = result.scalars().all()
        
        if format == "json":
            return self._export_json(prompts, include_metadata)
        elif format == "csv":
            return self._export_csv(prompts, include_metadata)
        elif format == "markdown":
            return self._export_markdown_zip(prompts, include_metadata)
        elif format == "zip":
            return self._export_zip(prompts, include_metadata, include_versions)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self, prompts: List[Prompt], include_metadata: bool) -> str:
        """Export prompts as JSON."""
        data = []
        for prompt in prompts:
            item = {
                "name": prompt.name,
                "slug": prompt.slug,
                "description": prompt.description,
                "type": prompt.type.value if hasattr(prompt.type, 'value') else str(prompt.type),
                "category": prompt.category,
                "content": prompt.content,
                "variables": prompt.variables or {},
                "version": prompt.version,
            }
            if include_metadata:
                item["metadata"] = prompt.metadata or {}
                item["benchmark_score"] = prompt.benchmark_score
                item["status"] = prompt.status.value if hasattr(prompt.status, 'value') else str(prompt.status)
                item["created_at"] = prompt.created_at.isoformat() if prompt.created_at else None
                item["updated_at"] = prompt.updated_at.isoformat() if prompt.updated_at else None
            data.append(item)
        
        return json.dumps(data, indent=2)
    
    def _export_csv(self, prompts: List[Prompt], include_metadata: bool) -> str:
        """Export prompts as CSV."""
        output = io.StringIO()
        
        fieldnames = ["name", "slug", "type", "category", "description", "content", "variables", "version"]
        if include_metadata:
            fieldnames.extend(["metadata", "benchmark_score", "status", "created_at", "updated_at"])
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for prompt in prompts:
            row = {
                "name": prompt.name,
                "slug": prompt.slug,
                "type": prompt.type.value if hasattr(prompt.type, 'value') else str(prompt.type),
                "category": prompt.category,
                "description": prompt.description,
                "content": prompt.content,
                "variables": json.dumps(prompt.variables or {}),
                "version": prompt.version,
            }
            if include_metadata:
                row["metadata"] = json.dumps(prompt.metadata or {})
                row["benchmark_score"] = prompt.benchmark_score
                row["status"] = prompt.status.value if hasattr(prompt.status, 'value') else str(prompt.status)
                row["created_at"] = prompt.created_at.isoformat() if prompt.created_at else ""
                row["updated_at"] = prompt.updated_at.isoformat() if prompt.updated_at else ""
            writer.writerow(row)
        
        return output.getvalue()
    
    def _export_markdown_zip(self, prompts: List[Prompt], include_metadata: bool) -> bytes:
        """Export prompts as a ZIP of markdown files."""
        output = io.BytesIO()
        
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            for prompt in prompts:
                filename = f"{prompt.slug or prompt.name.lower().replace(' ', '-')}.md"
                content = self._prompt_to_markdown(prompt, include_metadata)
                zf.writestr(filename, content)
        
        return output.getvalue()
    
    def _prompt_to_markdown(self, prompt: Prompt, include_metadata: bool) -> str:
        """Convert a prompt to markdown with YAML frontmatter."""
        frontmatter = {
            "name": prompt.name,
            "slug": prompt.slug,
            "type": prompt.type.value if hasattr(prompt.type, 'value') else str(prompt.type),
            "category": prompt.category,
            "description": prompt.description,
            "version": prompt.version,
        }
        
        if prompt.variables:
            frontmatter["variables"] = prompt.variables
        
        if include_metadata:
            if prompt.metadata:
                frontmatter["metadata"] = prompt.metadata
            frontmatter["benchmark_score"] = prompt.benchmark_score
            frontmatter["status"] = prompt.status.value if hasattr(prompt.status, 'value') else str(prompt.status)
        
        yaml_content = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        
        return f"""---
{yaml_content}---

# {prompt.name}

{prompt.description or ""}

## Content

{prompt.content}
"""
    
    def _export_zip(
        self,
        prompts: List[Prompt],
        include_metadata: bool,
        include_versions: bool,
    ) -> bytes:
        """Export prompts as a comprehensive ZIP archive."""
        output = io.BytesIO()
        
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Export index JSON
            index = {
                "exported_at": datetime.utcnow().isoformat(),
                "total_prompts": len(prompts),
                "prompts": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "slug": p.slug,
                        "file": f"prompts/{p.slug or str(p.id)}.md",
                    }
                    for p in prompts
                ],
            }
            zf.writestr("index.json", json.dumps(index, indent=2))
            
            # Export each prompt
            for prompt in prompts:
                slug = prompt.slug or str(prompt.id)
                
                # Markdown file
                md_content = self._prompt_to_markdown(prompt, include_metadata)
                zf.writestr(f"prompts/{slug}.md", md_content)
                
                # JSON file (full data)
                json_content = json.dumps({
                    "id": str(prompt.id),
                    "name": prompt.name,
                    "slug": prompt.slug,
                    "description": prompt.description,
                    "type": prompt.type.value if hasattr(prompt.type, 'value') else str(prompt.type),
                    "category": prompt.category,
                    "content": prompt.content,
                    "variables": prompt.variables,
                    "metadata": prompt.metadata,
                    "version": prompt.version,
                    "benchmark_score": prompt.benchmark_score,
                    "status": prompt.status.value if hasattr(prompt.status, 'value') else str(prompt.status),
                    "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
                    "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
                }, indent=2)
                zf.writestr(f"prompts/{slug}.json", json_content)
        
        return output.getvalue()
    
    # =========================================================================
    # Import
    # =========================================================================
    
    async def import_prompts(
        self,
        data: Union[str, bytes],
        format: str = "json",
        owner_id: uuid.UUID = None,
        overwrite_existing: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Import prompts from the specified format.
        
        Args:
            data: Import data as string or bytes
            format: Import format (json, csv, markdown, zip)
            owner_id: Owner ID for imported prompts
            overwrite_existing: Whether to overwrite existing prompts
            dry_run: If True, validate without saving
            
        Returns:
            Import result with counts and errors
        """
        if format == "json":
            prompts_data = self._parse_json(data)
        elif format == "csv":
            prompts_data = self._parse_csv(data)
        elif format == "markdown":
            prompts_data = [self._parse_markdown(data)]
        elif format == "zip":
            prompts_data = self._parse_zip(data)
        else:
            raise ValueError(f"Unsupported import format: {format}")
        
        result = {
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "prompts": [],
        }
        
        for idx, prompt_data in enumerate(prompts_data):
            try:
                # Check for existing
                existing = None
                if prompt_data.get("slug"):
                    existing_query = select(Prompt).where(
                        Prompt.slug == prompt_data["slug"],
                        Prompt.is_latest == True,
                    )
                    existing_result = await self.db.execute(existing_query)
                    existing = existing_result.scalar_one_or_none()
                
                if existing and not overwrite_existing:
                    result["skipped"] += 1
                    continue
                
                # Create prompt
                from hermes.services.prompt_store import PromptStoreService
                
                if not dry_run:
                    store = PromptStoreService(self.db)
                    
                    # Map type string to enum
                    prompt_type = prompt_data.get("type", "user_template")
                    if isinstance(prompt_type, str):
                        type_map = {
                            "agent_system": PromptType.AGENT_SYSTEM,
                            "user_template": PromptType.USER_TEMPLATE,
                            "tool_definition": PromptType.TOOL_DEFINITION,
                            "mcp_instruction": PromptType.MCP_INSTRUCTION,
                        }
                        prompt_type = type_map.get(prompt_type, PromptType.USER_TEMPLATE)
                    
                    create_data = PromptCreate(
                        name=prompt_data.get("name", f"Imported Prompt {idx}"),
                        slug=prompt_data.get("slug"),
                        description=prompt_data.get("description"),
                        type=prompt_type,
                        category=prompt_data.get("category"),
                        content=prompt_data.get("content", ""),
                        variables=prompt_data.get("variables"),
                        metadata=prompt_data.get("metadata"),
                    )
                    
                    if existing:
                        # Update existing
                        from hermes.schemas.prompt import PromptUpdate
                        update_data = PromptUpdate(
                            name=create_data.name,
                            description=create_data.description,
                            content=create_data.content,
                            variables=create_data.variables,
                            metadata=create_data.metadata,
                        )
                        prompt = await store.update(existing.id, update_data)
                        result["updated"] += 1
                    else:
                        # Create new
                        prompt = await store.create(
                            create_data,
                            owner_id=owner_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
                        )
                        result["imported"] += 1
                    
                    result["prompts"].append({
                        "id": str(prompt.id),
                        "name": prompt.name,
                        "slug": prompt.slug,
                        "action": "updated" if existing else "created",
                    })
                else:
                    # Dry run - just validate
                    result["prompts"].append({
                        "name": prompt_data.get("name"),
                        "slug": prompt_data.get("slug"),
                        "action": "would_update" if existing else "would_create",
                    })
                    if existing:
                        result["updated"] += 1
                    else:
                        result["imported"] += 1
                        
            except Exception as e:
                result["errors"].append({
                    "index": idx,
                    "name": prompt_data.get("name"),
                    "error": str(e),
                })
                logger.warning("import_error", index=idx, error=str(e))
        
        return result
    
    def _parse_json(self, data: Union[str, bytes]) -> List[Dict[str, Any]]:
        """Parse JSON import data."""
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        
        parsed = json.loads(data)
        
        # Handle single object or array
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    
    def _parse_csv(self, data: Union[str, bytes]) -> List[Dict[str, Any]]:
        """Parse CSV import data."""
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        
        reader = csv.DictReader(io.StringIO(data))
        prompts = []
        
        for row in reader:
            prompt = dict(row)
            
            # Parse JSON fields
            if prompt.get("variables"):
                try:
                    prompt["variables"] = json.loads(prompt["variables"])
                except json.JSONDecodeError:
                    prompt["variables"] = {}
            
            if prompt.get("metadata"):
                try:
                    prompt["metadata"] = json.loads(prompt["metadata"])
                except json.JSONDecodeError:
                    prompt["metadata"] = {}
            
            prompts.append(prompt)
        
        return prompts
    
    def _parse_markdown(self, data: Union[str, bytes]) -> Dict[str, Any]:
        """Parse markdown with YAML frontmatter."""
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        
        # Extract frontmatter
        frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(frontmatter_pattern, data, re.DOTALL)
        
        if match:
            frontmatter = yaml.safe_load(match.group(1))
            content = match.group(2).strip()
            
            # Extract content from markdown
            content_pattern = r'##\s*Content\s*\n\n(.*)$'
            content_match = re.search(content_pattern, content, re.DOTALL)
            if content_match:
                frontmatter["content"] = content_match.group(1).strip()
            else:
                frontmatter["content"] = content
            
            return frontmatter
        else:
            # No frontmatter - treat as plain content
            return {
                "name": "Imported Prompt",
                "content": data,
            }
    
    def _parse_zip(self, data: bytes) -> List[Dict[str, Any]]:
        """Parse ZIP archive."""
        prompts = []
        
        with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
            for filename in zf.namelist():
                if filename.endswith('.json') and 'index' not in filename:
                    with zf.open(filename) as f:
                        prompt_data = json.loads(f.read().decode('utf-8'))
                        prompts.append(prompt_data)
                elif filename.endswith('.md'):
                    with zf.open(filename) as f:
                        md_content = f.read().decode('utf-8')
                        prompt_data = self._parse_markdown(md_content)
                        prompts.append(prompt_data)
        
        return prompts
    
    async def export_single_prompt(
        self,
        prompt_id: uuid.UUID,
        format: str = "json",
    ) -> Union[str, bytes]:
        """Export a single prompt."""
        return await self.export_prompts(
            prompt_ids=[prompt_id],
            format=format,
            include_metadata=True,
        )
