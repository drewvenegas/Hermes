"""
Search API Endpoints

Full-text search for prompts with faceted filtering.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from hermes.auth.dependencies import get_current_user_optional
from hermes.auth.models import User
from hermes.services.search import SearchService, get_search_service

router = APIRouter()


class SearchResultItem(BaseModel):
    """Search result item."""
    
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    type: str
    status: str
    score: float
    highlights: Dict[str, List[str]] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Search response."""
    
    results: List[SearchResultItem]
    total: int
    took_ms: int
    facets: Dict[str, Dict[str, int]] = Field(default_factory=dict)


class SuggestionItem(BaseModel):
    """Search suggestion."""
    
    id: str
    slug: str
    name: str
    type: str


@router.get("/prompts/search", response_model=SearchResponse)
async def search_prompts(
    q: str = Query("", description="Search query"),
    type: Optional[str] = Query(None, description="Filter by prompt type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    visibility: Optional[str] = Query(None, description="Filter by visibility"),
    min_score: Optional[float] = Query(None, description="Minimum benchmark score"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Search prompts with full-text search and faceted filtering.
    
    Returns results with relevance scoring, highlights, and facet counts.
    """
    search_service = get_search_service()
    
    # Get user context for filtering
    owner_id = str(user.id) if user else None
    team_id = None
    if user and user.teams:
        team_id = user.teams[0] if user.teams else None
    
    result = await search_service.search(
        query=q,
        type_filter=type,
        status_filter=status,
        category_filter=category,
        visibility=visibility,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )
    
    return SearchResponse(
        results=[
            SearchResultItem(
                id=r.id,
                slug=r.slug,
                name=r.name,
                description=r.description,
                type=r.type,
                status=r.status,
                score=r.score,
                highlights=r.highlights,
            )
            for r in result.results
        ],
        total=result.total,
        took_ms=result.took_ms,
        facets=result.facets,
    )


@router.get("/prompts/suggest", response_model=List[SuggestionItem])
async def suggest_prompts(
    q: str = Query(..., min_length=1, description="Search prefix"),
    limit: int = Query(10, ge=1, le=50, description="Max suggestions"),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Get search suggestions based on prefix.
    
    Used for autocomplete in search box.
    """
    search_service = get_search_service()
    
    suggestions = await search_service.suggest(prefix=q, limit=limit)
    
    return [
        SuggestionItem(
            id=s["id"],
            slug=s["slug"],
            name=s["name"],
            type=s["type"],
        )
        for s in suggestions
    ]


@router.post("/admin/search/reindex")
async def reindex_all_prompts(
    user: User = Depends(get_current_user_optional),
):
    """Reindex all prompts in Elasticsearch.
    
    Admin-only operation for search maintenance.
    """
    from sqlalchemy import select
    from hermes.models import Prompt
    from hermes.services.database import get_async_engine
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # TODO: Add admin permission check
    
    search_service = get_search_service()
    
    # Fetch all prompts
    async with AsyncSession(get_async_engine()) as session:
        result = await session.execute(select(Prompt))
        prompts = list(result.scalars().all())
    
    # Convert to dicts
    prompt_data = [
        {
            "id": str(p.id),
            "slug": p.slug,
            "name": p.name,
            "description": p.description,
            "content": p.content,
            "type": p.type,
            "category": p.category,
            "status": p.status,
            "tags": p.tags,
            "version": p.version,
            "owner_id": str(p.owner_id),
            "visibility": p.visibility,
            "benchmark_score": p.benchmark_score,
        }
        for p in prompts
    ]
    
    await search_service.reindex_all(prompt_data)
    
    return {"status": "completed", "indexed": len(prompt_data)}
