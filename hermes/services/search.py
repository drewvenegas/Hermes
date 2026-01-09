"""
Elasticsearch Search Service

Full-text search for prompts with faceted filtering.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from elasticsearch import AsyncElasticsearch, NotFoundError

from hermes.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Index name
PROMPTS_INDEX = "hermes-prompts"

# Index mapping
PROMPTS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "prompt_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"],
                }
            }
        },
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "slug": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "prompt_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "description": {"type": "text", "analyzer": "prompt_analyzer"},
            "content": {"type": "text", "analyzer": "prompt_analyzer"},
            "type": {"type": "keyword"},
            "category": {"type": "keyword"},
            "status": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "version": {"type": "keyword"},
            "owner_id": {"type": "keyword"},
            "owner_type": {"type": "keyword"},
            "team_id": {"type": "keyword"},
            "visibility": {"type": "keyword"},
            "app_scope": {"type": "keyword"},
            "benchmark_score": {"type": "float"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "deployed_at": {"type": "date"},
        }
    },
}


@dataclass
class SearchResult:
    """A search result item."""
    
    id: str
    slug: str
    name: str
    description: Optional[str]
    type: str
    status: str
    score: float
    highlights: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Search response with results and metadata."""
    
    results: List[SearchResult]
    total: int
    took_ms: int
    facets: Dict[str, Dict[str, int]] = field(default_factory=dict)


class SearchService:
    """Elasticsearch search service for prompts.
    
    Provides full-text search with:
    - Query across name, description, content, tags
    - Faceted filtering by type, status, category
    - Relevance scoring
    - Highlighting
    """
    
    def __init__(self, es_url: Optional[str] = None):
        """Initialize search service.
        
        Args:
            es_url: Elasticsearch URL (defaults to settings)
        """
        self.es_url = es_url or settings.elasticsearch_url
        self._client: Optional[AsyncElasticsearch] = None
    
    async def _get_client(self) -> AsyncElasticsearch:
        """Get or create Elasticsearch client."""
        if self._client is None:
            self._client = AsyncElasticsearch(hosts=[self.es_url])
        return self._client
    
    async def close(self):
        """Close Elasticsearch client."""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def ensure_index(self):
        """Ensure the prompts index exists with correct mapping."""
        client = await self._get_client()
        
        try:
            exists = await client.indices.exists(index=PROMPTS_INDEX)
            if not exists:
                await client.indices.create(
                    index=PROMPTS_INDEX,
                    body=PROMPTS_MAPPING,
                )
                logger.info(f"Created index: {PROMPTS_INDEX}")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise
    
    async def index_prompt(self, prompt: Dict[str, Any]):
        """Index a prompt for search.
        
        Args:
            prompt: Prompt data to index
        """
        client = await self._get_client()
        
        # Prepare document
        doc = {
            "id": str(prompt["id"]),
            "slug": prompt["slug"],
            "name": prompt["name"],
            "description": prompt.get("description"),
            "content": prompt["content"],
            "type": prompt["type"],
            "category": prompt.get("category"),
            "status": prompt["status"],
            "tags": prompt.get("tags", []),
            "version": prompt["version"],
            "owner_id": str(prompt["owner_id"]),
            "owner_type": prompt.get("owner_type", "user"),
            "team_id": str(prompt["team_id"]) if prompt.get("team_id") else None,
            "visibility": prompt.get("visibility", "private"),
            "app_scope": prompt.get("app_scope", []),
            "benchmark_score": prompt.get("benchmark_score"),
            "created_at": prompt.get("created_at"),
            "updated_at": prompt.get("updated_at"),
            "deployed_at": prompt.get("deployed_at"),
        }
        
        try:
            await client.index(
                index=PROMPTS_INDEX,
                id=str(prompt["id"]),
                document=doc,
                refresh=True,
            )
            logger.debug(f"Indexed prompt: {prompt['slug']}")
        except Exception as e:
            logger.error(f"Failed to index prompt {prompt['slug']}: {e}")
            raise
    
    async def delete_prompt(self, prompt_id: str):
        """Delete a prompt from the index.
        
        Args:
            prompt_id: Prompt ID to delete
        """
        client = await self._get_client()
        
        try:
            await client.delete(
                index=PROMPTS_INDEX,
                id=prompt_id,
                refresh=True,
            )
            logger.debug(f"Deleted prompt from index: {prompt_id}")
        except NotFoundError:
            pass
        except Exception as e:
            logger.error(f"Failed to delete prompt {prompt_id}: {e}")
            raise
    
    async def search(
        self,
        query: str,
        type_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        owner_id: Optional[str] = None,
        team_id: Optional[str] = None,
        visibility: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """Search prompts.
        
        Args:
            query: Search query string
            type_filter: Filter by prompt type
            status_filter: Filter by status
            category_filter: Filter by category
            owner_id: Filter by owner
            team_id: Filter by team
            visibility: Filter by visibility
            min_score: Minimum benchmark score
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Search response with results and facets
        """
        client = await self._get_client()
        
        # Build query
        must_clauses = []
        filter_clauses = []
        
        # Text search
        if query:
            must_clauses.append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "name^3",
                        "description^2",
                        "content",
                        "tags^2",
                        "slug",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            })
        else:
            must_clauses.append({"match_all": {}})
        
        # Filters
        if type_filter:
            filter_clauses.append({"term": {"type": type_filter}})
        if status_filter:
            filter_clauses.append({"term": {"status": status_filter}})
        if category_filter:
            filter_clauses.append({"term": {"category": category_filter}})
        if owner_id:
            filter_clauses.append({"term": {"owner_id": owner_id}})
        if team_id:
            filter_clauses.append({"term": {"team_id": team_id}})
        if visibility:
            filter_clauses.append({"term": {"visibility": visibility}})
        if min_score is not None:
            filter_clauses.append({"range": {"benchmark_score": {"gte": min_score}}})
        
        # Build search body
        body = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
            "highlight": {
                "fields": {
                    "name": {},
                    "description": {},
                    "content": {"fragment_size": 150, "number_of_fragments": 3},
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
            },
            "aggs": {
                "types": {"terms": {"field": "type", "size": 10}},
                "statuses": {"terms": {"field": "status", "size": 10}},
                "categories": {"terms": {"field": "category", "size": 20}},
                "visibility": {"terms": {"field": "visibility", "size": 5}},
            },
            "from": offset,
            "size": limit,
            "_source": [
                "id", "slug", "name", "description", "type", "status",
                "category", "version", "benchmark_score",
            ],
        }
        
        try:
            response = await client.search(index=PROMPTS_INDEX, body=body)
        except NotFoundError:
            # Index doesn't exist yet
            return SearchResponse(results=[], total=0, took_ms=0)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
        
        # Parse results
        results = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            highlights = hit.get("highlight", {})
            
            results.append(SearchResult(
                id=source["id"],
                slug=source["slug"],
                name=source["name"],
                description=source.get("description"),
                type=source["type"],
                status=source["status"],
                score=hit["_score"],
                highlights=highlights,
            ))
        
        # Parse facets
        facets = {}
        for agg_name, agg_data in response.get("aggregations", {}).items():
            facets[agg_name] = {
                bucket["key"]: bucket["doc_count"]
                for bucket in agg_data.get("buckets", [])
            }
        
        return SearchResponse(
            results=results,
            total=response["hits"]["total"]["value"],
            took_ms=response["took"],
            facets=facets,
        )
    
    async def suggest(
        self,
        prefix: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Get search suggestions based on prefix.
        
        Args:
            prefix: Search prefix
            limit: Maximum suggestions
            
        Returns:
            List of suggestions
        """
        client = await self._get_client()
        
        body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "prefix": {
                                "name.keyword": {
                                    "value": prefix.lower(),
                                    "boost": 2.0,
                                }
                            }
                        },
                        {
                            "prefix": {
                                "slug": {
                                    "value": prefix.lower(),
                                }
                            }
                        },
                    ]
                }
            },
            "size": limit,
            "_source": ["id", "slug", "name", "type"],
        }
        
        try:
            response = await client.search(index=PROMPTS_INDEX, body=body)
        except NotFoundError:
            return []
        
        return [
            {
                "id": hit["_source"]["id"],
                "slug": hit["_source"]["slug"],
                "name": hit["_source"]["name"],
                "type": hit["_source"]["type"],
            }
            for hit in response["hits"]["hits"]
        ]
    
    async def reindex_all(self, prompts: List[Dict[str, Any]]):
        """Reindex all prompts.
        
        Args:
            prompts: List of prompts to index
        """
        client = await self._get_client()
        
        # Delete and recreate index
        try:
            await client.indices.delete(index=PROMPTS_INDEX, ignore=[404])
        except Exception:
            pass
        
        await self.ensure_index()
        
        # Bulk index
        operations = []
        for prompt in prompts:
            operations.append({"index": {"_index": PROMPTS_INDEX, "_id": str(prompt["id"])}})
            operations.append({
                "id": str(prompt["id"]),
                "slug": prompt["slug"],
                "name": prompt["name"],
                "description": prompt.get("description"),
                "content": prompt["content"],
                "type": prompt["type"] if isinstance(prompt["type"], str) else prompt["type"].value,
                "category": prompt.get("category"),
                "status": prompt["status"] if isinstance(prompt["status"], str) else prompt["status"].value,
                "tags": prompt.get("tags", []),
                "version": prompt["version"],
                "owner_id": str(prompt["owner_id"]),
                "visibility": prompt.get("visibility", "private"),
                "benchmark_score": prompt.get("benchmark_score"),
            })
        
        if operations:
            await client.bulk(operations=operations, refresh=True)
            logger.info(f"Reindexed {len(prompts)} prompts")


# Global search service instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get or create search service."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
