"""
Import/Export API Endpoints

REST API for bulk import and export of prompts.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.services.database import get_db_session
from hermes.services.import_export import ImportExportService

router = APIRouter(prefix="/prompts", tags=["Import/Export"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ImportResult(BaseModel):
    """Result of an import operation."""
    imported: int = Field(..., description="Number of prompts imported")
    updated: int = Field(..., description="Number of prompts updated")
    skipped: int = Field(..., description="Number of prompts skipped")
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    prompts: List[Dict[str, Any]] = Field(default_factory=list)


class ImportRequest(BaseModel):
    """Request body for JSON import."""
    data: List[Dict[str, Any]] = Field(..., description="Array of prompts to import")
    overwrite_existing: bool = Field(False, description="Overwrite existing prompts")
    dry_run: bool = Field(False, description="Validate without saving")


class ExportRequest(BaseModel):
    """Request body for export."""
    prompt_ids: Optional[List[str]] = Field(None, description="Specific prompt IDs to export")
    include_metadata: bool = Field(True, description="Include metadata in export")
    include_versions: bool = Field(False, description="Include version history")


# ============================================================================
# Dependency for current user (placeholder)
# ============================================================================

async def get_current_user_id(request: Request) -> uuid.UUID:
    """Get current user ID from request."""
    user_id = request.headers.get("X-User-ID")
    if user_id:
        try:
            return uuid.UUID(user_id)
        except ValueError:
            pass
    return uuid.UUID("00000000-0000-0000-0000-000000000000")


# ============================================================================
# Export Endpoints
# ============================================================================

@router.get(
    "/export",
    summary="Export Prompts",
    description="Export prompts in the specified format.",
    responses={
        200: {
            "content": {
                "application/json": {},
                "text/csv": {},
                "application/zip": {},
            }
        }
    },
)
async def export_prompts(
    format: str = Query("json", description="Export format: json, csv, markdown, zip"),
    prompt_ids: Optional[str] = Query(None, description="Comma-separated prompt IDs"),
    include_metadata: bool = Query(True, description="Include metadata"),
    include_versions: bool = Query(False, description="Include version history"),
    db: AsyncSession = Depends(get_db_session),
):
    """Export prompts in various formats."""
    service = ImportExportService(db)
    
    # Parse prompt IDs if provided
    parsed_ids = None
    if prompt_ids:
        try:
            parsed_ids = [uuid.UUID(id.strip()) for id in prompt_ids.split(",")]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid prompt ID: {e}")
    
    try:
        result = await service.export_prompts(
            prompt_ids=parsed_ids,
            format=format,
            include_metadata=include_metadata,
            include_versions=include_versions,
        )
        
        # Return appropriate content type
        if format == "json":
            return Response(
                content=result,
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=prompts.json"},
            )
        elif format == "csv":
            return Response(
                content=result,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=prompts.csv"},
            )
        elif format in ("markdown", "zip"):
            return Response(
                content=result,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename=prompts.zip"},
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get(
    "/{prompt_id}/export",
    summary="Export Single Prompt",
    description="Export a single prompt.",
)
async def export_single_prompt(
    prompt_id: uuid.UUID,
    format: str = Query("json", description="Export format: json, markdown"),
    db: AsyncSession = Depends(get_db_session),
):
    """Export a single prompt."""
    service = ImportExportService(db)
    
    try:
        result = await service.export_single_prompt(prompt_id, format)
        
        if format == "json":
            return Response(
                content=result,
                media_type="application/json",
            )
        elif format == "markdown":
            # For single markdown, just return the content
            return Response(
                content=result,
                media_type="text/markdown",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============================================================================
# Import Endpoints
# ============================================================================

@router.post(
    "/import",
    response_model=ImportResult,
    summary="Import Prompts",
    description="Import prompts from JSON, CSV, or file upload.",
)
async def import_prompts_json(
    data: ImportRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Import prompts from JSON data."""
    service = ImportExportService(db)
    
    import json
    
    try:
        result = await service.import_prompts(
            data=json.dumps(data.data),
            format="json",
            owner_id=user_id,
            overwrite_existing=data.overwrite_existing,
            dry_run=data.dry_run,
        )
        
        if not data.dry_run:
            await db.commit()
        
        return ImportResult(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post(
    "/import/file",
    response_model=ImportResult,
    summary="Import Prompts from File",
    description="Import prompts from an uploaded file.",
)
async def import_prompts_file(
    file: UploadFile = File(..., description="File to import (JSON, CSV, MD, or ZIP)"),
    overwrite_existing: bool = Query(False, description="Overwrite existing prompts"),
    dry_run: bool = Query(False, description="Validate without saving"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Import prompts from an uploaded file."""
    service = ImportExportService(db)
    
    # Determine format from filename
    filename = file.filename.lower() if file.filename else ""
    
    if filename.endswith(".json"):
        format = "json"
    elif filename.endswith(".csv"):
        format = "csv"
    elif filename.endswith(".md") or filename.endswith(".markdown"):
        format = "markdown"
    elif filename.endswith(".zip"):
        format = "zip"
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use .json, .csv, .md, or .zip",
        )
    
    try:
        content = await file.read()
        
        result = await service.import_prompts(
            data=content,
            format=format,
            owner_id=user_id,
            overwrite_existing=overwrite_existing,
            dry_run=dry_run,
        )
        
        if not dry_run:
            await db.commit()
        
        return ImportResult(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post(
    "/import/validate",
    response_model=ImportResult,
    summary="Validate Import",
    description="Validate import data without saving.",
)
async def validate_import(
    file: UploadFile = File(..., description="File to validate"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Validate import data without saving."""
    # Just call import with dry_run=True
    return await import_prompts_file(
        file=file,
        overwrite_existing=False,
        dry_run=True,
        user_id=user_id,
        db=db,
    )
