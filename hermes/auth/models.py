"""
Authentication Models

User and token data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class User:
    """Authenticated user from PERSONA."""
    
    id: UUID
    email: str
    username: str
    display_name: str
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    teams: list[str] = field(default_factory=list)
    organization_id: Optional[UUID] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Check exact match
        if permission in self.permissions:
            return True
        # Check wildcard (e.g., prompts:* matches prompts:read)
        parts = permission.split(":")
        if len(parts) >= 2:
            wildcard = f"{parts[0]}:*"
            if wildcard in self.permissions:
                return True
        return False
    
    def has_any_permission(self, permissions: list[str]) -> bool:
        """Check if user has any of the specified permissions."""
        return any(self.has_permission(p) for p in permissions)
    
    def has_all_permissions(self, permissions: list[str]) -> bool:
        """Check if user has all specified permissions."""
        return all(self.has_permission(p) for p in permissions)
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles
    
    def is_in_team(self, team: str) -> bool:
        """Check if user is in a specific team."""
        return team in self.teams


@dataclass
class TokenData:
    """JWT token payload data."""
    
    sub: str  # Subject (user ID)
    email: str
    username: str
    name: str
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    teams: list[str] = field(default_factory=list)
    org_id: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    iss: Optional[str] = None
    aud: Optional[str] = None
