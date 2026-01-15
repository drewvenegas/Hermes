"""
Hermes gRPC Server

Implements the gRPC services for the Hermes Prompt Engineering Platform.
"""

import asyncio
import uuid
from concurrent import futures
from datetime import datetime
from typing import Optional

import grpc
from grpc import aio
import structlog

from hermes.config import get_settings
from hermes.services.database import get_db_session
from hermes.services.prompt_store import PromptStoreService
from hermes.services.version_control import VersionControlService
from hermes.services.benchmark_engine import BenchmarkEngine

logger = structlog.get_logger()
settings = get_settings()


# Import generated code (will be available after proto compilation)
try:
    from hermes.grpc.generated import hermes_pb2, hermes_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    logger.warning("gRPC generated code not available. Run scripts/compile_protos.sh")


def _prompt_to_proto(prompt) -> "hermes_pb2.Prompt":
    """Convert a Prompt model to protobuf message."""
    from google.protobuf.timestamp_pb2 import Timestamp
    
    proto = hermes_pb2.Prompt(
        id=str(prompt.id),
        slug=prompt.slug or "",
        name=prompt.name,
        description=prompt.description or "",
        type=_prompt_type_to_proto(prompt.type),
        category=prompt.category or "",
        content=prompt.content,
        version=prompt.version,
        parent_id=str(prompt.parent_id) if prompt.parent_id else "",
        is_latest=prompt.is_latest,
        content_hash=prompt.content_hash or "",
        owner_id=str(prompt.owner_id) if prompt.owner_id else "",
        owner_type=prompt.owner_type or "",
        team_id=str(prompt.team_id) if prompt.team_id else "",
        visibility=_visibility_to_proto(prompt.visibility),
        status=_status_to_proto(prompt.status),
        benchmark_score=prompt.benchmark_score or 0.0,
    )
    
    # Set timestamps
    if prompt.created_at:
        proto.created_at.FromDatetime(prompt.created_at)
    if prompt.updated_at:
        proto.updated_at.FromDatetime(prompt.updated_at)
    if prompt.deployed_at:
        proto.deployed_at.FromDatetime(prompt.deployed_at)
    if prompt.last_benchmark_at:
        proto.last_benchmark_at.FromDatetime(prompt.last_benchmark_at)
    
    # Set metadata and variables
    if prompt.metadata:
        for k, v in prompt.metadata.items():
            proto.metadata[k] = str(v)
    if prompt.variables:
        for k, v in prompt.variables.items():
            proto.variables[k] = str(v)
    
    return proto


def _prompt_type_to_proto(prompt_type) -> int:
    """Convert prompt type to protobuf enum."""
    type_map = {
        "agent_system": hermes_pb2.PROMPT_TYPE_AGENT_SYSTEM,
        "user_template": hermes_pb2.PROMPT_TYPE_USER_TEMPLATE,
        "tool_definition": hermes_pb2.PROMPT_TYPE_TOOL_DEFINITION,
        "mcp_instruction": hermes_pb2.PROMPT_TYPE_MCP_INSTRUCTION,
    }
    if hasattr(prompt_type, 'value'):
        return type_map.get(prompt_type.value, hermes_pb2.PROMPT_TYPE_UNSPECIFIED)
    return type_map.get(str(prompt_type), hermes_pb2.PROMPT_TYPE_UNSPECIFIED)


def _visibility_to_proto(visibility) -> int:
    """Convert visibility to protobuf enum."""
    vis_map = {
        "private": hermes_pb2.VISIBILITY_PRIVATE,
        "team": hermes_pb2.VISIBILITY_TEAM,
        "organization": hermes_pb2.VISIBILITY_ORGANIZATION,
        "public": hermes_pb2.VISIBILITY_PUBLIC,
    }
    if hasattr(visibility, 'value'):
        return vis_map.get(visibility.value, hermes_pb2.VISIBILITY_UNSPECIFIED)
    return vis_map.get(str(visibility), hermes_pb2.VISIBILITY_UNSPECIFIED)


def _status_to_proto(status) -> int:
    """Convert status to protobuf enum."""
    status_map = {
        "draft": hermes_pb2.PROMPT_STATUS_DRAFT,
        "review": hermes_pb2.PROMPT_STATUS_REVIEW,
        "staged": hermes_pb2.PROMPT_STATUS_STAGED,
        "deployed": hermes_pb2.PROMPT_STATUS_DEPLOYED,
        "archived": hermes_pb2.PROMPT_STATUS_ARCHIVED,
    }
    if hasattr(status, 'value'):
        return status_map.get(status.value, hermes_pb2.PROMPT_STATUS_UNSPECIFIED)
    return status_map.get(str(status), hermes_pb2.PROMPT_STATUS_UNSPECIFIED)


class PromptServiceServicer(hermes_pb2_grpc.PromptServiceServicer):
    """Implements the PromptService gRPC service."""
    
    async def CreatePrompt(self, request, context):
        """Create a new prompt."""
        logger.info("gRPC CreatePrompt", name=request.name)
        
        async with get_db_session() as db:
            store = PromptStoreService(db)
            
            # Map proto type to model type
            type_map = {
                hermes_pb2.PROMPT_TYPE_AGENT_SYSTEM: "agent_system",
                hermes_pb2.PROMPT_TYPE_USER_TEMPLATE: "user_template",
                hermes_pb2.PROMPT_TYPE_TOOL_DEFINITION: "tool_definition",
                hermes_pb2.PROMPT_TYPE_MCP_INSTRUCTION: "mcp_instruction",
            }
            
            from hermes.schemas.prompt import PromptCreate
            
            prompt_data = PromptCreate(
                name=request.name,
                slug=request.slug or None,
                description=request.description or None,
                type=type_map.get(request.type, "user_template"),
                category=request.category or None,
                content=request.content,
                variables=dict(request.variables) if request.variables else None,
                metadata=dict(request.metadata) if request.metadata else None,
            )
            
            # Create with a system owner for gRPC calls
            owner_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            prompt = await store.create(prompt_data, owner_id=owner_id)
            await db.commit()
            
            return _prompt_to_proto(prompt)
    
    async def GetPrompt(self, request, context):
        """Get a prompt by ID."""
        logger.info("gRPC GetPrompt", id=request.id)
        
        async with get_db_session() as db:
            store = PromptStoreService(db)
            
            prompt = await store.get(
                uuid.UUID(request.id),
                version=request.version if request.version else None
            )
            
            if not prompt:
                context.abort(grpc.StatusCode.NOT_FOUND, "Prompt not found")
            
            return _prompt_to_proto(prompt)
    
    async def GetPromptBySlug(self, request, context):
        """Get a prompt by slug."""
        logger.info("gRPC GetPromptBySlug", slug=request.slug)
        
        async with get_db_session() as db:
            store = PromptStoreService(db)
            
            prompt = await store.get_by_slug(
                request.slug,
                app=request.app if request.app else None
            )
            
            if not prompt:
                context.abort(grpc.StatusCode.NOT_FOUND, "Prompt not found")
            
            return _prompt_to_proto(prompt)
    
    async def UpdatePrompt(self, request, context):
        """Update a prompt (creates new version)."""
        logger.info("gRPC UpdatePrompt", id=request.id)
        
        async with get_db_session() as db:
            store = PromptStoreService(db)
            
            from hermes.schemas.prompt import PromptUpdate
            
            update_data = PromptUpdate(
                content=request.content,
                name=request.name if request.HasField("name") else None,
                description=request.description if request.HasField("description") else None,
                variables=dict(request.variables) if request.variables else None,
                metadata=dict(request.metadata) if request.metadata else None,
            )
            
            prompt = await store.update(
                uuid.UUID(request.id),
                update_data,
                change_summary=request.change_summary
            )
            await db.commit()
            
            return _prompt_to_proto(prompt)
    
    async def DeletePrompt(self, request, context):
        """Delete a prompt."""
        logger.info("gRPC DeletePrompt", id=request.id, hard=request.hard_delete)
        
        async with get_db_session() as db:
            store = PromptStoreService(db)
            await store.delete(uuid.UUID(request.id), hard=request.hard_delete)
            await db.commit()
        
        from google.protobuf.empty_pb2 import Empty
        return Empty()
    
    async def ListPrompts(self, request, context):
        """List prompts with filtering."""
        logger.info("gRPC ListPrompts")
        
        async with get_db_session() as db:
            store = PromptStoreService(db)
            
            from hermes.schemas.prompt import PromptQuery
            
            query = PromptQuery(
                type=request.type if request.type else None,
                status=request.status if request.status else None,
                category=request.category if request.category else None,
                team_id=request.team_id if request.team_id else None,
                owner_id=request.owner_id if request.owner_id else None,
                limit=request.limit or 50,
                offset=request.offset or 0,
            )
            
            prompts, total = await store.list(query)
            
            return hermes_pb2.ListPromptsResponse(
                prompts=[_prompt_to_proto(p) for p in prompts],
                total=total,
                limit=query.limit,
                offset=query.offset,
            )
    
    async def SearchPrompts(self, request, context):
        """Search prompts."""
        logger.info("gRPC SearchPrompts", query=request.query)
        
        async with get_db_session() as db:
            store = PromptStoreService(db)
            
            results = await store.search(
                query=request.query,
                type=request.type if request.type else None,
                category=request.category if request.category else None,
                limit=request.limit or 20,
                offset=request.offset or 0,
            )
            
            return hermes_pb2.SearchPromptsResponse(
                results=[
                    hermes_pb2.PromptSearchResult(
                        prompt=_prompt_to_proto(r.prompt),
                        score=r.score,
                        highlights=r.highlights,
                    )
                    for r in results.results
                ],
                total=results.total,
            )


class VersionServiceServicer(hermes_pb2_grpc.VersionServiceServicer):
    """Implements the VersionService gRPC service."""
    
    async def GetVersionHistory(self, request, context):
        """Get version history for a prompt."""
        logger.info("gRPC GetVersionHistory", prompt_id=request.prompt_id)
        
        async with get_db_session() as db:
            vc = VersionControlService(db)
            
            versions = await vc.history(
                uuid.UUID(request.prompt_id),
                limit=request.limit or 50,
            )
            
            return hermes_pb2.GetVersionHistoryResponse(
                versions=[_version_to_proto(v) for v in versions],
                total=len(versions),
            )
    
    async def GetVersion(self, request, context):
        """Get a specific version."""
        logger.info("gRPC GetVersion", prompt_id=request.prompt_id, version=request.version)
        
        async with get_db_session() as db:
            vc = VersionControlService(db)
            
            version = await vc.get_version(
                uuid.UUID(request.prompt_id),
                request.version
            )
            
            if not version:
                context.abort(grpc.StatusCode.NOT_FOUND, "Version not found")
            
            return _version_to_proto(version)
    
    async def DiffVersions(self, request, context):
        """Compare two versions."""
        logger.info("gRPC DiffVersions", 
                    prompt_id=request.prompt_id,
                    from_v=request.from_version,
                    to_v=request.to_version)
        
        async with get_db_session() as db:
            vc = VersionControlService(db)
            
            diff_result = await vc.diff(
                uuid.UUID(request.prompt_id),
                request.from_version,
                request.to_version
            )
            
            return hermes_pb2.DiffVersionsResponse(
                from_version=request.from_version,
                to_version=request.to_version,
                diff=diff_result.diff,
                chunks=[
                    hermes_pb2.DiffChunk(
                        type=c.type,
                        old_start=c.old_start,
                        old_lines=c.old_lines,
                        new_start=c.new_start,
                        new_lines=c.new_lines,
                        lines=c.lines,
                    )
                    for c in diff_result.chunks
                ],
            )
    
    async def RollbackVersion(self, request, context):
        """Rollback to a previous version."""
        logger.info("gRPC RollbackVersion", 
                    prompt_id=request.prompt_id, 
                    to_version=request.to_version)
        
        async with get_db_session() as db:
            vc = VersionControlService(db)
            
            prompt = await vc.rollback(
                uuid.UUID(request.prompt_id),
                request.to_version
            )
            await db.commit()
            
            return _prompt_to_proto(prompt)


class BenchmarkServiceServicer(hermes_pb2_grpc.BenchmarkServiceServicer):
    """Implements the BenchmarkService gRPC service."""
    
    async def RunBenchmark(self, request, context):
        """Run a benchmark on a prompt."""
        logger.info("gRPC RunBenchmark", 
                    prompt_id=request.prompt_id,
                    suite=request.suite_id)
        
        async with get_db_session() as db:
            from hermes.services.prompt_store import PromptStoreService
            
            store = PromptStoreService(db)
            prompt = await store.get(uuid.UUID(request.prompt_id))
            
            if not prompt:
                context.abort(grpc.StatusCode.NOT_FOUND, "Prompt not found")
            
            engine = BenchmarkEngine(db)
            result = await engine.run_benchmark(
                prompt=prompt,
                suite_id=request.suite_id or "default",
                model_id=request.model_id or "aria01-d3n",
                notify=request.notify,
            )
            await db.commit()
            
            return _benchmark_result_to_proto(result)
    
    async def RunSelfCritique(self, request, context):
        """Run self-critique via ASRBS."""
        logger.info("gRPC RunSelfCritique", prompt_id=request.prompt_id)
        
        async with get_db_session() as db:
            from hermes.services.prompt_store import PromptStoreService
            
            store = PromptStoreService(db)
            prompt = await store.get(uuid.UUID(request.prompt_id))
            
            if not prompt:
                context.abort(grpc.StatusCode.NOT_FOUND, "Prompt not found")
            
            engine = BenchmarkEngine(db)
            result = await engine.run_self_critique(prompt)
            
            return hermes_pb2.SelfCritiqueResult(
                overall_assessment=result.get("overall_assessment", ""),
                quality_score=result.get("quality_score", 0.0),
                suggestions=[
                    hermes_pb2.ImprovementSuggestion(
                        id=s.get("id", ""),
                        category=s.get("category", ""),
                        severity=s.get("severity", ""),
                        description=s.get("description", ""),
                        suggested_change=s.get("suggested_change", ""),
                        confidence=s.get("confidence", 0.0),
                    )
                    for s in result.get("suggestions", [])
                ],
                knowledge_gaps=result.get("knowledge_gaps", []),
                overconfidence_areas=result.get("overconfidence_areas", []),
                training_data_needs=result.get("training_data_needs", []),
            )
    
    async def GetBenchmarkResults(self, request, context):
        """Get benchmark results for a prompt."""
        logger.info("gRPC GetBenchmarkResults", prompt_id=request.prompt_id)
        
        async with get_db_session() as db:
            engine = BenchmarkEngine(db)
            results = await engine.get_benchmark_history(
                uuid.UUID(request.prompt_id),
                limit=request.limit or 20,
            )
            
            return hermes_pb2.GetBenchmarkResultsResponse(
                results=[_benchmark_result_to_proto(r) for r in results],
                total=len(results),
            )
    
    async def GetBenchmarkTrends(self, request, context):
        """Get benchmark trends."""
        logger.info("gRPC GetBenchmarkTrends", prompt_id=request.prompt_id)
        
        async with get_db_session() as db:
            engine = BenchmarkEngine(db)
            trends = await engine.get_benchmark_trends(
                uuid.UUID(request.prompt_id),
                days=request.days or 30,
            )
            
            from google.protobuf.timestamp_pb2 import Timestamp
            
            return hermes_pb2.BenchmarkTrends(
                trend=trends.get("trend", "neutral"),
                change=trends.get("change", 0.0),
                current_score=trends.get("current_score", 0.0),
                history=[
                    hermes_pb2.TrendPoint(
                        score=h.get("score", 0.0),
                        version=h.get("version", ""),
                    )
                    for h in trends.get("history", [])
                ],
            )


def _version_to_proto(version) -> "hermes_pb2.PromptVersion":
    """Convert a PromptVersion model to protobuf message."""
    proto = hermes_pb2.PromptVersion(
        id=str(version.id),
        prompt_id=str(version.prompt_id),
        version=version.version,
        content_hash=version.content_hash or "",
        content=version.content or "",
        diff=version.diff or "",
        change_summary=version.change_summary or "",
        author_id=str(version.author_id) if version.author_id else "",
    )
    
    if version.created_at:
        proto.created_at.FromDatetime(version.created_at)
    
    return proto


def _benchmark_result_to_proto(result) -> "hermes_pb2.BenchmarkResult":
    """Convert a BenchmarkResult model to protobuf message."""
    proto = hermes_pb2.BenchmarkResult(
        id=str(result.id),
        prompt_id=str(result.prompt_id),
        prompt_version=result.prompt_version or "",
        suite_id=result.suite_id or "",
        overall_score=result.overall_score or 0.0,
        model_id=result.model_id or "",
        model_version=result.model_version or "",
        execution_time_ms=result.execution_time_ms or 0,
        baseline_score=result.baseline_score or 0.0,
        delta=result.delta or 0.0,
        gate_passed=result.gate_passed if hasattr(result, 'gate_passed') else True,
        environment=result.environment or "",
        executed_by=str(result.executed_by) if result.executed_by else "",
    )
    
    if result.executed_at:
        proto.executed_at.FromDatetime(result.executed_at)
    
    if result.dimension_scores:
        for k, v in result.dimension_scores.items():
            proto.dimension_scores[k] = float(v)
    
    if result.token_usage:
        proto.token_usage.CopyFrom(hermes_pb2.TokenUsage(
            input_tokens=result.token_usage.get("input_tokens", 0),
            output_tokens=result.token_usage.get("output_tokens", 0),
            total_tokens=result.token_usage.get("total_tokens", 0),
        ))
    
    return proto


class DeploymentServiceServicer(hermes_pb2_grpc.DeploymentServiceServicer):
    """Implements the DeploymentService gRPC service."""
    
    async def DeployPrompt(self, request, context):
        """Deploy a prompt to applications."""
        logger.info("gRPC DeployPrompt", prompt_id=request.prompt_id)
        
        async with get_db_session() as db:
            from hermes.services.deployment import DeploymentService
            
            service = DeploymentService(db)
            deployment = await service.deploy(
                prompt_id=uuid.UUID(request.prompt_id),
                version=request.version if request.version else None,
                target_apps=list(request.target_apps) if request.target_apps else [],
                strategy=request.strategy or "immediate",
                canary_percentage=request.canary_percentage if request.canary_percentage else 0.0,
            )
            await db.commit()
            
            return _deployment_to_proto(deployment)
    
    async def GetDeploymentStatus(self, request, context):
        """Get deployment status."""
        logger.info("gRPC GetDeploymentStatus", deployment_id=request.deployment_id)
        
        async with get_db_session() as db:
            from hermes.services.deployment import DeploymentService
            
            service = DeploymentService(db)
            deployment = await service.get_status(uuid.UUID(request.deployment_id))
            
            if not deployment:
                context.abort(grpc.StatusCode.NOT_FOUND, "Deployment not found")
            
            return _deployment_to_proto(deployment)
    
    async def RollbackDeployment(self, request, context):
        """Rollback a deployment."""
        logger.info("gRPC RollbackDeployment", deployment_id=request.deployment_id)
        
        async with get_db_session() as db:
            from hermes.services.deployment import DeploymentService
            
            service = DeploymentService(db)
            deployment = await service.rollback(
                deployment_id=uuid.UUID(request.deployment_id),
                reason=request.reason,
            )
            await db.commit()
            
            return _deployment_to_proto(deployment)
    
    async def ListDeployments(self, request, context):
        """List deployments."""
        logger.info("gRPC ListDeployments")
        
        async with get_db_session() as db:
            from hermes.services.deployment import DeploymentService
            
            service = DeploymentService(db)
            deployments, total = await service.list_deployments(
                prompt_id=uuid.UUID(request.prompt_id) if request.prompt_id else None,
                app_id=request.app_id if request.app_id else None,
                status=request.status if request.status else None,
                limit=request.limit or 20,
                offset=request.offset or 0,
            )
            
            return hermes_pb2.ListDeploymentsResponse(
                deployments=[_deployment_to_proto(d) for d in deployments],
                total=total,
            )


class NurseryServiceServicer(hermes_pb2_grpc.NurseryServiceServicer):
    """Implements the NurseryService gRPC service."""
    
    async def SyncFromNursery(self, request, context):
        """Sync agent prompts from Nursery."""
        logger.info("gRPC SyncFromNursery", agents=list(request.agent_ids))
        
        async with get_db_session() as db:
            from hermes.services.nursery_sync import NurserySyncService
            
            service = NurserySyncService(db)
            result = await service.import_from_nursery(
                agent_ids=list(request.agent_ids) if request.agent_ids else None,
                force=request.force,
            )
            await db.commit()
            
            return _sync_result_to_proto(result)
    
    async def SyncToNursery(self, request, context):
        """Export prompts to Nursery."""
        logger.info("gRPC SyncToNursery", prompts=list(request.prompt_ids))
        
        async with get_db_session() as db:
            from hermes.services.nursery_sync import NurserySyncService
            
            service = NurserySyncService(db)
            result = await service.export_to_nursery(
                prompt_ids=[uuid.UUID(p) for p in request.prompt_ids] if request.prompt_ids else None,
                commit_message=request.commit_message,
            )
            await db.commit()
            
            return _sync_result_to_proto(result)
    
    async def GetSyncStatus(self, request, context):
        """Get sync status."""
        logger.info("gRPC GetSyncStatus")
        
        async with get_db_session() as db:
            from hermes.services.nursery_sync import NurserySyncService
            
            service = NurserySyncService(db)
            status = await service.get_sync_status()
            
            response = hermes_pb2.SyncStatus(
                sync_state=status.get("state", "unknown"),
                pending_changes=status.get("pending_changes", 0),
                conflicts=status.get("conflicts", 0),
            )
            
            if status.get("last_sync_at"):
                response.last_sync_at.FromDatetime(status["last_sync_at"])
            
            return response
    
    async def ResolveConflict(self, request, context):
        """Resolve sync conflict."""
        logger.info("gRPC ResolveConflict", prompt_id=request.prompt_id)
        
        async with get_db_session() as db:
            from hermes.services.nursery_sync import NurserySyncService
            
            service = NurserySyncService(db)
            prompt = await service.resolve_conflict(
                prompt_id=uuid.UUID(request.prompt_id),
                resolution=request.resolution,
                merged_content=request.merged_content if request.merged_content else None,
            )
            await db.commit()
            
            return _prompt_to_proto(prompt)


def _deployment_to_proto(deployment) -> "hermes_pb2.DeploymentStatus":
    """Convert a deployment model to protobuf message."""
    proto = hermes_pb2.DeploymentStatus(
        id=str(deployment.id) if hasattr(deployment, 'id') else str(deployment.get("id", "")),
        prompt_id=str(deployment.prompt_id) if hasattr(deployment, 'prompt_id') else str(deployment.get("prompt_id", "")),
        version=deployment.version if hasattr(deployment, 'version') else deployment.get("version", ""),
        status=deployment.status if hasattr(deployment, 'status') else deployment.get("status", ""),
        error_message=deployment.error_message if hasattr(deployment, 'error_message') else deployment.get("error_message", "") or "",
    )
    
    started_at = deployment.started_at if hasattr(deployment, 'started_at') else deployment.get("started_at")
    completed_at = deployment.completed_at if hasattr(deployment, 'completed_at') else deployment.get("completed_at")
    
    if started_at:
        proto.started_at.FromDatetime(started_at)
    if completed_at:
        proto.completed_at.FromDatetime(completed_at)
    
    return proto


def _sync_result_to_proto(result) -> "hermes_pb2.SyncResult":
    """Convert a sync result to protobuf message."""
    return hermes_pb2.SyncResult(
        imported=result.get("imported", 0),
        updated=result.get("updated", 0),
        skipped=result.get("skipped", 0),
        failed=result.get("failed", 0),
        errors=result.get("errors", []),
        conflicts=[
            hermes_pb2.SyncConflict(
                prompt_id=str(c.get("prompt_id", "")),
                nursery_path=c.get("nursery_path", ""),
                local_version=c.get("local_version", ""),
                nursery_version=c.get("nursery_version", ""),
                conflict_type=c.get("conflict_type", ""),
            )
            for c in result.get("conflicts", [])
        ],
    )


class GRPCServer:
    """Hermes gRPC Server."""
    
    def __init__(self, port: int = 50051, max_workers: int = 10):
        self.port = port
        self.max_workers = max_workers
        self.server: Optional[aio.Server] = None
    
    async def start(self):
        """Start the gRPC server."""
        if not GRPC_AVAILABLE:
            logger.error("Cannot start gRPC server: generated code not available")
            raise RuntimeError("gRPC generated code not available. Run scripts/compile_protos.sh")
        
        self.server = aio.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
            ]
        )
        
        # Add service implementations
        hermes_pb2_grpc.add_PromptServiceServicer_to_server(
            PromptServiceServicer(), self.server
        )
        hermes_pb2_grpc.add_VersionServiceServicer_to_server(
            VersionServiceServicer(), self.server
        )
        hermes_pb2_grpc.add_BenchmarkServiceServicer_to_server(
            BenchmarkServiceServicer(), self.server
        )
        hermes_pb2_grpc.add_DeploymentServiceServicer_to_server(
            DeploymentServiceServicer(), self.server
        )
        hermes_pb2_grpc.add_NurseryServiceServicer_to_server(
            NurseryServiceServicer(), self.server
        )
        
        # Add health check
        from grpc_health.v1 import health, health_pb2_grpc
        health_servicer = health.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(health_servicer, self.server)
        
        # Bind to port
        listen_addr = f"[::]:{self.port}"
        self.server.add_insecure_port(listen_addr)
        
        logger.info("Starting gRPC server", address=listen_addr)
        await self.server.start()
        logger.info("gRPC server started", port=self.port)
    
    async def stop(self, grace: float = 5.0):
        """Stop the gRPC server gracefully."""
        if self.server:
            logger.info("Stopping gRPC server")
            await self.server.stop(grace)
            logger.info("gRPC server stopped")
    
    async def wait_for_termination(self):
        """Wait for the server to terminate."""
        if self.server:
            await self.server.wait_for_termination()


def create_grpc_server(port: int = None, max_workers: int = None) -> GRPCServer:
    """Create a new gRPC server instance."""
    return GRPCServer(
        port=port or settings.grpc_port,
        max_workers=max_workers or settings.grpc_workers,
    )


async def serve():
    """Start the gRPC server and run until termination."""
    server = create_grpc_server()
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
