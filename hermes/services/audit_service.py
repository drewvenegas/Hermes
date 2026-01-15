"""
Audit Service

Provides comprehensive audit logging for all Hermes operations.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models.audit import AuditLog

logger = structlog.get_logger()


class AuditService:
    """
    Service for audit logging.
    
    Records all significant actions in Hermes for compliance,
    debugging, and security analysis.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        api_key_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """
        Log an action to the audit trail.
        
        Args:
            action: Type of action (create, read, update, delete, deploy, etc.)
            resource_type: Type of resource affected (prompt, benchmark, api_key, etc.)
            resource_id: ID of the affected resource
            user_id: ID of the user who performed the action
            api_key_id: ID of the API key used (if applicable)
            details: Additional details about the action
            old_value: Previous state (for updates)
            new_value: New state (for creates/updates)
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
            endpoint: API endpoint called
            http_method: HTTP method used
            success: Whether the action was successful
            error_message: Error message if action failed
            
        Returns:
            The created AuditLog entry
        """
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            api_key_id=api_key_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            endpoint=endpoint,
            http_method=http_method,
            timestamp=datetime.utcnow(),
            success=success,
            error_message=error_message,
        )
        
        self.db.add(audit_log)
        
        # Log to structured logging as well
        log_method = logger.info if success else logger.warning
        log_method(
            "audit_action",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            user_id=str(user_id) if user_id else None,
            success=success,
            error=error_message,
        )
        
        return audit_log
    
    async def log_prompt_action(
        self,
        action: str,
        prompt_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        api_key_id: Optional[uuid.UUID] = None,
        old_prompt: Optional[Any] = None,
        new_prompt: Optional[Any] = None,
        **kwargs,
    ) -> AuditLog:
        """Convenience method for logging prompt-related actions."""
        old_value = None
        new_value = None
        
        if old_prompt:
            old_value = {
                "name": old_prompt.name,
                "content": old_prompt.content[:500] if old_prompt.content else None,
                "version": old_prompt.version,
                "status": str(old_prompt.status),
            }
        
        if new_prompt:
            new_value = {
                "name": new_prompt.name,
                "content": new_prompt.content[:500] if new_prompt.content else None,
                "version": new_prompt.version,
                "status": str(new_prompt.status),
            }
        
        return await self.log_action(
            action=action,
            resource_type="prompt",
            resource_id=prompt_id,
            user_id=user_id,
            api_key_id=api_key_id,
            old_value=old_value,
            new_value=new_value,
            **kwargs,
        )
    
    async def log_benchmark_action(
        self,
        action: str,
        prompt_id: uuid.UUID,
        benchmark_id: Optional[uuid.UUID] = None,
        result: Optional[Any] = None,
        **kwargs,
    ) -> AuditLog:
        """Convenience method for logging benchmark-related actions."""
        details = None
        if result:
            details = {
                "suite_id": result.suite_id,
                "overall_score": result.overall_score,
                "model_id": result.model_id,
                "gate_passed": getattr(result, 'gate_passed', None),
            }
        
        return await self.log_action(
            action=action,
            resource_type="benchmark",
            resource_id=benchmark_id,
            details=details,
            **kwargs,
        )
    
    async def log_deployment_action(
        self,
        action: str,
        deployment_id: uuid.UUID,
        prompt_id: uuid.UUID,
        target_apps: Optional[List[str]] = None,
        **kwargs,
    ) -> AuditLog:
        """Convenience method for logging deployment-related actions."""
        return await self.log_action(
            action=action,
            resource_type="deployment",
            resource_id=deployment_id,
            details={
                "prompt_id": str(prompt_id),
                "target_apps": target_apps,
            },
            **kwargs,
        )
    
    async def get_logs(
        self,
        user_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        request_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[AuditLog], int]:
        """
        Query audit logs with filters.
        
        Returns:
            Tuple of (list of AuditLog, total count)
        """
        query = select(AuditLog)
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if action:
            query = query.where(AuditLog.action == action)
        if request_id:
            query = query.where(AuditLog.request_id == request_id)
        if start_time:
            query = query.where(AuditLog.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLog.timestamp <= end_time)
        if success_only is not None:
            query = query.where(AuditLog.success == success_only)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination and ordering
        query = query.order_by(AuditLog.timestamp.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        logs = result.scalars().all()
        
        return list(logs), total
    
    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        limit: int = 50,
    ) -> List[AuditLog]:
        """Get audit history for a specific resource."""
        logs, _ = await self.get_logs(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        return logs
    
    async def get_user_activity(
        self,
        user_id: uuid.UUID,
        days: int = 30,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get recent activity for a user."""
        start_time = datetime.utcnow() - timedelta(days=days)
        logs, _ = await self.get_logs(
            user_id=user_id,
            start_time=start_time,
            limit=limit,
        )
        return logs
    
    async def get_action_summary(
        self,
        days: int = 7,
    ) -> Dict[str, int]:
        """Get summary of actions over a time period."""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(AuditLog.action, func.count(AuditLog.id))
            .where(AuditLog.timestamp >= start_time)
            .group_by(AuditLog.action)
        )
        
        result = await self.db.execute(query)
        return {row[0]: row[1] for row in result.all()}
    
    async def cleanup_old_logs(
        self,
        retention_days: int = 90,
    ) -> int:
        """
        Delete audit logs older than retention period.
        
        Returns:
            Number of logs deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        
        from sqlalchemy import delete
        
        result = await self.db.execute(
            delete(AuditLog).where(AuditLog.timestamp < cutoff)
        )
        
        deleted = result.rowcount or 0
        
        logger.info(
            "audit_cleanup",
            retention_days=retention_days,
            deleted_count=deleted,
        )
        
        return deleted


# Action constants
class AuditActions:
    """Standard audit action names."""
    
    # CRUD
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    
    # Prompts
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    ARCHIVE = "archive"
    RESTORE = "restore"
    
    # Versions
    VERSION_CREATE = "version_create"
    VERSION_COMPARE = "version_compare"
    
    # Benchmarks
    BENCHMARK_RUN = "benchmark_run"
    BENCHMARK_VIEW = "benchmark_view"
    
    # Experiments
    EXPERIMENT_START = "experiment_start"
    EXPERIMENT_STOP = "experiment_stop"
    EXPERIMENT_PROMOTE = "experiment_promote"
    
    # Sync
    SYNC_IMPORT = "sync_import"
    SYNC_EXPORT = "sync_export"
    CONFLICT_RESOLVE = "conflict_resolve"
    
    # API Keys
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    API_KEY_ROTATE = "api_key_rotate"
    
    # Auth
    LOGIN = "login"
    LOGOUT = "logout"
    AUTH_FAILURE = "auth_failure"


class ResourceTypes:
    """Standard resource type names."""
    
    PROMPT = "prompt"
    VERSION = "version"
    BENCHMARK = "benchmark"
    EXPERIMENT = "experiment"
    DEPLOYMENT = "deployment"
    API_KEY = "api_key"
    USER = "user"
    TEMPLATE = "template"
    SYNC = "sync"
