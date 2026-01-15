"""
Hermes gRPC Client

Provides a client for communicating with the Hermes gRPC API.
"""

import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import grpc
from grpc import aio
import structlog

from hermes.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Import generated code
try:
    from hermes.grpc.generated import hermes_pb2, hermes_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    logger.warning("gRPC generated code not available")


@dataclass
class PromptData:
    """Prompt data structure."""
    id: str
    slug: str
    name: str
    description: str
    type: str
    category: str
    content: str
    version: str
    status: str
    benchmark_score: float
    metadata: Dict[str, str]
    variables: Dict[str, str]


@dataclass
class BenchmarkResultData:
    """Benchmark result data structure."""
    id: str
    prompt_id: str
    prompt_version: str
    suite_id: str
    overall_score: float
    dimension_scores: Dict[str, float]
    model_id: str
    execution_time_ms: int
    gate_passed: bool


@dataclass
class SuggestionData:
    """Improvement suggestion data structure."""
    id: str
    category: str
    severity: str
    description: str
    suggested_change: str
    confidence: float


class HermesClient:
    """
    Async gRPC client for Hermes API.
    
    Usage:
        async with HermesClient() as client:
            prompt = await client.get_prompt("prompt-id")
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        timeout: float = 30.0,
    ):
        self.host = host or settings.grpc_host
        self.port = port or settings.grpc_port
        self.timeout = timeout
        self._channel: Optional[aio.Channel] = None
        self._prompt_stub = None
        self._version_stub = None
        self._benchmark_stub = None
    
    async def __aenter__(self):
        """Enter async context."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.close()
    
    async def connect(self):
        """Establish gRPC connection."""
        if not GRPC_AVAILABLE:
            raise RuntimeError("gRPC generated code not available")
        
        target = f"{self.host}:{self.port}"
        logger.debug("Connecting to Hermes gRPC", target=target)
        
        self._channel = aio.insecure_channel(
            target,
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
            ]
        )
        
        self._prompt_stub = hermes_pb2_grpc.PromptServiceStub(self._channel)
        self._version_stub = hermes_pb2_grpc.VersionServiceStub(self._channel)
        self._benchmark_stub = hermes_pb2_grpc.BenchmarkServiceStub(self._channel)
        
        logger.info("Connected to Hermes gRPC", target=target)
    
    async def close(self):
        """Close gRPC connection."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            logger.debug("Closed Hermes gRPC connection")
    
    # =========================================================================
    # Prompt Operations
    # =========================================================================
    
    async def create_prompt(
        self,
        name: str,
        content: str,
        type: str = "user_template",
        slug: str = None,
        description: str = None,
        category: str = None,
        variables: Dict[str, str] = None,
        metadata: Dict[str, str] = None,
    ) -> PromptData:
        """Create a new prompt."""
        type_map = {
            "agent_system": hermes_pb2.PROMPT_TYPE_AGENT_SYSTEM,
            "user_template": hermes_pb2.PROMPT_TYPE_USER_TEMPLATE,
            "tool_definition": hermes_pb2.PROMPT_TYPE_TOOL_DEFINITION,
            "mcp_instruction": hermes_pb2.PROMPT_TYPE_MCP_INSTRUCTION,
        }
        
        request = hermes_pb2.CreatePromptRequest(
            name=name,
            content=content,
            type=type_map.get(type, hermes_pb2.PROMPT_TYPE_USER_TEMPLATE),
            slug=slug or "",
            description=description or "",
            category=category or "",
        )
        
        if variables:
            for k, v in variables.items():
                request.variables[k] = v
        if metadata:
            for k, v in metadata.items():
                request.metadata[k] = v
        
        response = await self._prompt_stub.CreatePrompt(
            request,
            timeout=self.timeout
        )
        
        return self._proto_to_prompt(response)
    
    async def get_prompt(
        self,
        prompt_id: str,
        version: str = None,
    ) -> Optional[PromptData]:
        """Get a prompt by ID."""
        try:
            response = await self._prompt_stub.GetPrompt(
                hermes_pb2.GetPromptRequest(id=prompt_id, version=version or ""),
                timeout=self.timeout
            )
            return self._proto_to_prompt(response)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
    
    async def get_prompt_by_slug(
        self,
        slug: str,
        app: str = None,
    ) -> Optional[PromptData]:
        """Get a prompt by slug."""
        try:
            response = await self._prompt_stub.GetPromptBySlug(
                hermes_pb2.GetPromptBySlugRequest(slug=slug, app=app or ""),
                timeout=self.timeout
            )
            return self._proto_to_prompt(response)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
    
    async def update_prompt(
        self,
        prompt_id: str,
        content: str,
        change_summary: str = None,
        name: str = None,
        description: str = None,
    ) -> PromptData:
        """Update a prompt (creates new version)."""
        request = hermes_pb2.UpdatePromptRequest(
            id=prompt_id,
            content=content,
            change_summary=change_summary or "",
        )
        
        if name:
            request.name = name
        if description:
            request.description = description
        
        response = await self._prompt_stub.UpdatePrompt(
            request,
            timeout=self.timeout
        )
        
        return self._proto_to_prompt(response)
    
    async def delete_prompt(
        self,
        prompt_id: str,
        hard_delete: bool = False,
    ) -> None:
        """Delete a prompt."""
        await self._prompt_stub.DeletePrompt(
            hermes_pb2.DeletePromptRequest(id=prompt_id, hard_delete=hard_delete),
            timeout=self.timeout
        )
    
    async def list_prompts(
        self,
        type: str = None,
        status: str = None,
        category: str = None,
        team_id: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[PromptData], int]:
        """List prompts with filtering."""
        type_map = {
            "agent_system": hermes_pb2.PROMPT_TYPE_AGENT_SYSTEM,
            "user_template": hermes_pb2.PROMPT_TYPE_USER_TEMPLATE,
            "tool_definition": hermes_pb2.PROMPT_TYPE_TOOL_DEFINITION,
            "mcp_instruction": hermes_pb2.PROMPT_TYPE_MCP_INSTRUCTION,
        }
        status_map = {
            "draft": hermes_pb2.PROMPT_STATUS_DRAFT,
            "review": hermes_pb2.PROMPT_STATUS_REVIEW,
            "staged": hermes_pb2.PROMPT_STATUS_STAGED,
            "deployed": hermes_pb2.PROMPT_STATUS_DEPLOYED,
            "archived": hermes_pb2.PROMPT_STATUS_ARCHIVED,
        }
        
        response = await self._prompt_stub.ListPrompts(
            hermes_pb2.ListPromptsRequest(
                type=type_map.get(type, 0) if type else 0,
                status=status_map.get(status, 0) if status else 0,
                category=category or "",
                team_id=team_id or "",
                limit=limit,
                offset=offset,
            ),
            timeout=self.timeout
        )
        
        prompts = [self._proto_to_prompt(p) for p in response.prompts]
        return prompts, response.total
    
    async def search_prompts(
        self,
        query: str,
        type: str = None,
        category: str = None,
        limit: int = 20,
    ) -> List[tuple[PromptData, float]]:
        """Search prompts."""
        type_map = {
            "agent_system": hermes_pb2.PROMPT_TYPE_AGENT_SYSTEM,
            "user_template": hermes_pb2.PROMPT_TYPE_USER_TEMPLATE,
            "tool_definition": hermes_pb2.PROMPT_TYPE_TOOL_DEFINITION,
            "mcp_instruction": hermes_pb2.PROMPT_TYPE_MCP_INSTRUCTION,
        }
        
        response = await self._prompt_stub.SearchPrompts(
            hermes_pb2.SearchPromptsRequest(
                query=query,
                type=type_map.get(type, 0) if type else 0,
                category=category or "",
                limit=limit,
            ),
            timeout=self.timeout
        )
        
        return [
            (self._proto_to_prompt(r.prompt), r.score)
            for r in response.results
        ]
    
    # =========================================================================
    # Version Operations
    # =========================================================================
    
    async def get_version_history(
        self,
        prompt_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get version history for a prompt."""
        response = await self._version_stub.GetVersionHistory(
            hermes_pb2.GetVersionHistoryRequest(
                prompt_id=prompt_id,
                limit=limit,
            ),
            timeout=self.timeout
        )
        
        return [
            {
                "id": v.id,
                "prompt_id": v.prompt_id,
                "version": v.version,
                "content_hash": v.content_hash,
                "change_summary": v.change_summary,
                "author_id": v.author_id,
            }
            for v in response.versions
        ]
    
    async def diff_versions(
        self,
        prompt_id: str,
        from_version: str,
        to_version: str,
    ) -> Dict[str, Any]:
        """Compare two versions."""
        response = await self._version_stub.DiffVersions(
            hermes_pb2.DiffVersionsRequest(
                prompt_id=prompt_id,
                from_version=from_version,
                to_version=to_version,
            ),
            timeout=self.timeout
        )
        
        return {
            "from_version": response.from_version,
            "to_version": response.to_version,
            "diff": response.diff,
            "chunks": [
                {
                    "type": c.type,
                    "old_start": c.old_start,
                    "old_lines": c.old_lines,
                    "new_start": c.new_start,
                    "new_lines": c.new_lines,
                    "lines": list(c.lines),
                }
                for c in response.chunks
            ],
        }
    
    async def rollback_version(
        self,
        prompt_id: str,
        to_version: str,
        reason: str = None,
    ) -> PromptData:
        """Rollback to a previous version."""
        response = await self._version_stub.RollbackVersion(
            hermes_pb2.RollbackVersionRequest(
                prompt_id=prompt_id,
                to_version=to_version,
                reason=reason or "",
            ),
            timeout=self.timeout
        )
        
        return self._proto_to_prompt(response)
    
    # =========================================================================
    # Benchmark Operations
    # =========================================================================
    
    async def run_benchmark(
        self,
        prompt_id: str,
        suite_id: str = "default",
        model_id: str = "aria01-d3n",
        notify: bool = True,
    ) -> BenchmarkResultData:
        """Run a benchmark on a prompt."""
        response = await self._benchmark_stub.RunBenchmark(
            hermes_pb2.RunBenchmarkRequest(
                prompt_id=prompt_id,
                suite_id=suite_id,
                model_id=model_id,
                notify=notify,
            ),
            timeout=120.0  # Longer timeout for benchmarks
        )
        
        return self._proto_to_benchmark_result(response)
    
    async def run_self_critique(
        self,
        prompt_id: str,
    ) -> Dict[str, Any]:
        """Run self-critique via ASRBS."""
        response = await self._benchmark_stub.RunSelfCritique(
            hermes_pb2.RunSelfCritiqueRequest(prompt_id=prompt_id),
            timeout=120.0
        )
        
        return {
            "overall_assessment": response.overall_assessment,
            "quality_score": response.quality_score,
            "suggestions": [
                SuggestionData(
                    id=s.id,
                    category=s.category,
                    severity=s.severity,
                    description=s.description,
                    suggested_change=s.suggested_change,
                    confidence=s.confidence,
                )
                for s in response.suggestions
            ],
            "knowledge_gaps": list(response.knowledge_gaps),
            "overconfidence_areas": list(response.overconfidence_areas),
            "training_data_needs": list(response.training_data_needs),
        }
    
    async def get_benchmark_results(
        self,
        prompt_id: str,
        limit: int = 20,
    ) -> List[BenchmarkResultData]:
        """Get benchmark results for a prompt."""
        response = await self._benchmark_stub.GetBenchmarkResults(
            hermes_pb2.GetBenchmarkResultsRequest(
                prompt_id=prompt_id,
                limit=limit,
            ),
            timeout=self.timeout
        )
        
        return [self._proto_to_benchmark_result(r) for r in response.results]
    
    async def get_benchmark_trends(
        self,
        prompt_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get benchmark trends."""
        response = await self._benchmark_stub.GetBenchmarkTrends(
            hermes_pb2.GetBenchmarkTrendsRequest(
                prompt_id=prompt_id,
                days=days,
            ),
            timeout=self.timeout
        )
        
        return {
            "trend": response.trend,
            "change": response.change,
            "current_score": response.current_score,
            "history": [
                {"score": h.score, "version": h.version}
                for h in response.history
            ],
        }
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _proto_to_prompt(self, proto) -> PromptData:
        """Convert protobuf message to PromptData."""
        type_map = {
            hermes_pb2.PROMPT_TYPE_AGENT_SYSTEM: "agent_system",
            hermes_pb2.PROMPT_TYPE_USER_TEMPLATE: "user_template",
            hermes_pb2.PROMPT_TYPE_TOOL_DEFINITION: "tool_definition",
            hermes_pb2.PROMPT_TYPE_MCP_INSTRUCTION: "mcp_instruction",
        }
        status_map = {
            hermes_pb2.PROMPT_STATUS_DRAFT: "draft",
            hermes_pb2.PROMPT_STATUS_REVIEW: "review",
            hermes_pb2.PROMPT_STATUS_STAGED: "staged",
            hermes_pb2.PROMPT_STATUS_DEPLOYED: "deployed",
            hermes_pb2.PROMPT_STATUS_ARCHIVED: "archived",
        }
        
        return PromptData(
            id=proto.id,
            slug=proto.slug,
            name=proto.name,
            description=proto.description,
            type=type_map.get(proto.type, "user_template"),
            category=proto.category,
            content=proto.content,
            version=proto.version,
            status=status_map.get(proto.status, "draft"),
            benchmark_score=proto.benchmark_score,
            metadata=dict(proto.metadata),
            variables=dict(proto.variables),
        )
    
    def _proto_to_benchmark_result(self, proto) -> BenchmarkResultData:
        """Convert protobuf message to BenchmarkResultData."""
        return BenchmarkResultData(
            id=proto.id,
            prompt_id=proto.prompt_id,
            prompt_version=proto.prompt_version,
            suite_id=proto.suite_id,
            overall_score=proto.overall_score,
            dimension_scores=dict(proto.dimension_scores),
            model_id=proto.model_id,
            execution_time_ms=proto.execution_time_ms,
            gate_passed=proto.gate_passed,
        )


# Convenience function for quick client creation
async def get_hermes_client() -> HermesClient:
    """Create and connect a Hermes client."""
    client = HermesClient()
    await client.connect()
    return client
