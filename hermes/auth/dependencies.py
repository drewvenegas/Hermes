"""
Authentication Dependencies

FastAPI dependencies for authentication and authorization.
"""

from functools import wraps
from typing import Callable, Optional
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from hermes.auth.models import User, TokenData
from hermes.config import get_settings

settings = get_settings()

# JWKS cache
_jwks_cache: Optional[dict] = None


async def _get_jwks() -> dict:
    """Fetch JWKS from PERSONA."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    
    jwks_url = f"{settings.persona_url}/oauth2/jwks"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


async def get_current_user(request: Request) -> User:
    """Get current authenticated user from request.
    
    Validates JWT token and returns User object.
    
    Raises:
        HTTPException: If not authenticated or token invalid
    """
    # Try to get token from cookie or header
    access_token = request.cookies.get("hermes_access_token")
    if not access_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode and validate JWT
    try:
        # For development, skip signature validation if no JWKS
        # In production, always validate signature
        if settings.debug:
            payload = jwt.decode(
                access_token,
                options={"verify_signature": False},
            )
        else:
            jwks = await _get_jwks()
            payload = jwt.decode(
                access_token,
                jwks,
                algorithms=["RS256"],
                audience=settings.persona_client_id,
            )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user data from token
    token_data = TokenData(
        sub=payload.get("sub", ""),
        email=payload.get("email", ""),
        username=payload.get("preferred_username", payload.get("email", "")),
        name=payload.get("name", ""),
        roles=payload.get("roles", []),
        permissions=payload.get("permissions", []),
        teams=payload.get("teams", []),
        org_id=payload.get("org_id"),
        exp=payload.get("exp"),
        iat=payload.get("iat"),
        iss=payload.get("iss"),
        aud=payload.get("aud"),
    )
    
    # Build User object
    user = User(
        id=UUID(token_data.sub) if token_data.sub else UUID(int=0),
        email=token_data.email,
        username=token_data.username,
        display_name=token_data.name or token_data.username,
        roles=token_data.roles,
        permissions=token_data.permissions,
        teams=token_data.teams,
        organization_id=UUID(token_data.org_id) if token_data.org_id else None,
    )
    
    return user


async def get_current_user_optional(request: Request) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


def require_permission(permission: str):
    """Dependency that requires a specific permission.
    
    Usage:
        @router.get("/prompts")
        async def list_prompts(user: User = Depends(require_permission("prompts:read"))):
            ...
    """
    async def permission_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires {permission}",
            )
        return user
    return permission_checker


def require_any_permission(permissions: list[str]):
    """Dependency that requires any of the specified permissions."""
    async def permission_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_any_permission(permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires one of {permissions}",
            )
        return user
    return permission_checker


def require_role(role: str):
    """Dependency that requires a specific role."""
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role}",
            )
        return user
    return role_checker
