"""
Audit Middleware

Automatically logs API requests to the audit trail.
"""

import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically logs API requests to the audit trail.
    
    Features:
    - Generates request IDs for correlation
    - Logs request/response metadata
    - Tracks response times
    - Handles errors gracefully
    """
    
    # Paths to exclude from audit logging
    EXCLUDED_PATHS = {
        "/health",
        "/healthz",
        "/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
    
    # Actions to infer from HTTP method and path
    METHOD_ACTIONS = {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log to audit trail."""
        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        # Skip static files
        if request.url.path.startswith("/static"):
            return await call_next(request)
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Add request ID to state for access in handlers
        request.state.request_id = request_id
        
        # Record start time
        start_time = time.time()
        
        # Extract user info
        user_id = self._extract_user_id(request)
        api_key_id = self._extract_api_key_id(request)
        
        # Process request
        response = None
        error_message = None
        success = True
        
        try:
            response = await call_next(request)
            
            # Check for error status codes
            if response.status_code >= 400:
                success = False
                error_message = f"HTTP {response.status_code}"
                
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log the request
            await self._log_request(
                request=request,
                response=response,
                request_id=request_id,
                user_id=user_id,
                api_key_id=api_key_id,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
            )
        
        # Add request ID to response headers
        if response:
            response.headers["X-Request-ID"] = request_id
        
        return response
    
    def _extract_user_id(self, request: Request) -> Optional[uuid.UUID]:
        """Extract user ID from request."""
        # Check header
        user_id = request.headers.get("X-User-ID")
        if user_id:
            try:
                return uuid.UUID(user_id)
            except ValueError:
                pass
        
        # Check state (may be set by auth middleware)
        if hasattr(request.state, "user_id"):
            return request.state.user_id
        
        return None
    
    def _extract_api_key_id(self, request: Request) -> Optional[uuid.UUID]:
        """Extract API key ID from request."""
        # Check state (set by API key auth)
        if hasattr(request.state, "api_key_id"):
            return request.state.api_key_id
        
        return None
    
    def _infer_resource_info(self, request: Request) -> tuple[str, Optional[uuid.UUID]]:
        """Infer resource type and ID from request path."""
        path_parts = request.url.path.strip("/").split("/")
        
        resource_type = "unknown"
        resource_id = None
        
        # Skip 'api' and version prefix
        if len(path_parts) >= 2 and path_parts[0] == "api":
            path_parts = path_parts[2:]  # Skip 'api/v1'
        
        if path_parts:
            resource_type = path_parts[0]
            
            # Try to extract resource ID
            if len(path_parts) >= 2:
                try:
                    resource_id = uuid.UUID(path_parts[1])
                except ValueError:
                    pass
        
        return resource_type, resource_id
    
    async def _log_request(
        self,
        request: Request,
        response: Optional[Response],
        request_id: str,
        user_id: Optional[uuid.UUID],
        api_key_id: Optional[uuid.UUID],
        duration_ms: int,
        success: bool,
        error_message: Optional[str],
    ) -> None:
        """Log the request to audit trail."""
        # Infer action and resource
        action = self.METHOD_ACTIONS.get(request.method, "unknown")
        resource_type, resource_id = self._infer_resource_info(request)
        
        # Log to structured logger
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "user_id": str(user_id) if user_id else None,
            "api_key_id": str(api_key_id) if api_key_id else None,
            "client_ip": request.client.host if request.client else None,
            "duration_ms": duration_ms,
            "status_code": response.status_code if response else None,
            "success": success,
        }
        
        if success:
            logger.info("api_request", **log_data)
        else:
            logger.warning("api_request_failed", error=error_message, **log_data)
        
        # Optionally write to database audit log
        # This is done asynchronously to not block the response
        # In production, you might use a background task queue
        try:
            # Only log certain actions to database
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                await self._write_audit_log(
                    request=request,
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    success=success,
                    error_message=error_message,
                )
        except Exception as e:
            logger.error("audit_write_failed", error=str(e), request_id=request_id)
    
    async def _write_audit_log(
        self,
        request: Request,
        request_id: str,
        user_id: Optional[uuid.UUID],
        api_key_id: Optional[uuid.UUID],
        action: str,
        resource_type: str,
        resource_id: Optional[uuid.UUID],
        success: bool,
        error_message: Optional[str],
    ) -> None:
        """Write to database audit log."""
        # Import here to avoid circular imports
        from hermes.services.database import get_db_session
        from hermes.services.audit_service import AuditService
        
        try:
            async with get_db_session() as db:
                service = AuditService(db)
                
                await service.log_action(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                    request_id=request_id,
                    endpoint=request.url.path,
                    http_method=request.method,
                    success=success,
                    error_message=error_message,
                )
                
                await db.commit()
        except Exception as e:
            # Don't fail the request if audit logging fails
            logger.error("audit_db_write_failed", error=str(e))


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Simple middleware that adds request ID to all requests.
    
    Lighter weight than full audit middleware.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request and response."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response
