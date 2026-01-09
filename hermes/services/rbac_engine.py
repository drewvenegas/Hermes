"""
RBAC Engine

Role-Based Access Control for Hermes resources.
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from hermes.integrations.persona import User


class Permission(str, Enum):
    """Available permissions in Hermes."""
    
    # Prompt permissions
    PROMPT_CREATE = "prompt:create"
    PROMPT_READ = "prompt:read"
    PROMPT_UPDATE = "prompt:update"
    PROMPT_DELETE = "prompt:delete"
    PROMPT_DEPLOY = "prompt:deploy"
    PROMPT_ARCHIVE = "prompt:archive"
    
    # Version permissions
    VERSION_READ = "version:read"
    VERSION_ROLLBACK = "version:rollback"
    
    # Benchmark permissions
    BENCHMARK_RUN = "benchmark:run"
    BENCHMARK_READ = "benchmark:read"
    
    # Admin permissions
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_TEAM = "admin:team"


class Role(str, Enum):
    """Predefined roles in Hermes."""
    
    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    MAINTAINER = "maintainer"
    ADMIN = "admin"
    OWNER = "owner"


# Role to permission mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {
        Permission.PROMPT_READ,
        Permission.VERSION_READ,
        Permission.BENCHMARK_READ,
    },
    Role.CONTRIBUTOR: {
        Permission.PROMPT_CREATE,
        Permission.PROMPT_READ,
        Permission.PROMPT_UPDATE,
        Permission.VERSION_READ,
        Permission.BENCHMARK_RUN,
        Permission.BENCHMARK_READ,
    },
    Role.MAINTAINER: {
        Permission.PROMPT_CREATE,
        Permission.PROMPT_READ,
        Permission.PROMPT_UPDATE,
        Permission.PROMPT_DELETE,
        Permission.PROMPT_DEPLOY,
        Permission.VERSION_READ,
        Permission.VERSION_ROLLBACK,
        Permission.BENCHMARK_RUN,
        Permission.BENCHMARK_READ,
    },
    Role.ADMIN: {
        Permission.PROMPT_CREATE,
        Permission.PROMPT_READ,
        Permission.PROMPT_UPDATE,
        Permission.PROMPT_DELETE,
        Permission.PROMPT_DEPLOY,
        Permission.PROMPT_ARCHIVE,
        Permission.VERSION_READ,
        Permission.VERSION_ROLLBACK,
        Permission.BENCHMARK_RUN,
        Permission.BENCHMARK_READ,
        Permission.ADMIN_READ,
        Permission.ADMIN_WRITE,
    },
    Role.OWNER: set(Permission),  # All permissions
}


@dataclass
class AccessContext:
    """Context for access control decisions."""
    
    user: User
    resource_owner_id: Optional[uuid.UUID] = None
    resource_team_id: Optional[uuid.UUID] = None
    resource_visibility: str = "private"
    app_scope: Optional[list[str]] = None


class RBACEngine:
    """Role-Based Access Control engine."""

    def __init__(self):
        pass

    def get_user_role(self, user: User, context: AccessContext) -> Role:
        """Determine user's effective role for a resource."""
        # Owner has full access
        if context.resource_owner_id == user.id:
            return Role.OWNER

        # Check team membership
        if context.resource_team_id and context.resource_team_id in user.teams:
            # Team members get contributor role by default
            # Could be enhanced to check team-specific role assignments
            return Role.CONTRIBUTOR

        # Check visibility
        if context.resource_visibility == "public":
            return Role.VIEWER

        if context.resource_visibility == "organization":
            # Organization-wide visibility gives viewer access
            return Role.VIEWER

        # Check explicit roles from PERSONA
        for role_str in user.roles:
            try:
                role = Role(role_str)
                if role in [Role.ADMIN, Role.OWNER]:
                    return role
            except ValueError:
                continue

        # No access by default
        return Role.VIEWER

    def get_permissions(self, role: Role) -> set[Permission]:
        """Get permissions for a role."""
        return ROLE_PERMISSIONS.get(role, set())

    def has_permission(
        self,
        user: User,
        permission: Permission,
        context: AccessContext,
    ) -> bool:
        """Check if user has a specific permission."""
        # Get effective role
        role = self.get_user_role(user, context)
        
        # Get permissions for role
        permissions = self.get_permissions(role)
        
        # Check if permission is granted
        return permission in permissions

    def can_create_prompt(self, user: User) -> bool:
        """Check if user can create prompts."""
        # All authenticated users can create prompts
        return True

    def can_read_prompt(
        self,
        user: User,
        owner_id: uuid.UUID,
        team_id: Optional[uuid.UUID],
        visibility: str,
    ) -> bool:
        """Check if user can read a prompt."""
        context = AccessContext(
            user=user,
            resource_owner_id=owner_id,
            resource_team_id=team_id,
            resource_visibility=visibility,
        )
        return self.has_permission(user, Permission.PROMPT_READ, context)

    def can_update_prompt(
        self,
        user: User,
        owner_id: uuid.UUID,
        team_id: Optional[uuid.UUID],
    ) -> bool:
        """Check if user can update a prompt."""
        context = AccessContext(
            user=user,
            resource_owner_id=owner_id,
            resource_team_id=team_id,
        )
        return self.has_permission(user, Permission.PROMPT_UPDATE, context)

    def can_delete_prompt(
        self,
        user: User,
        owner_id: uuid.UUID,
    ) -> bool:
        """Check if user can delete a prompt."""
        context = AccessContext(
            user=user,
            resource_owner_id=owner_id,
        )
        return self.has_permission(user, Permission.PROMPT_DELETE, context)

    def can_deploy_prompt(
        self,
        user: User,
        owner_id: uuid.UUID,
        team_id: Optional[uuid.UUID],
    ) -> bool:
        """Check if user can deploy a prompt."""
        context = AccessContext(
            user=user,
            resource_owner_id=owner_id,
            resource_team_id=team_id,
        )
        return self.has_permission(user, Permission.PROMPT_DEPLOY, context)

    def can_run_benchmark(self, user: User) -> bool:
        """Check if user can run benchmarks."""
        # Contributors and above can run benchmarks
        return Permission.BENCHMARK_RUN in self.get_permissions(
            self.get_user_role(user, AccessContext(user=user))
        )

    def filter_visible_prompts(
        self,
        user: User,
        prompts: list[dict],
    ) -> list[dict]:
        """Filter prompts to only those visible to user."""
        visible = []
        for prompt in prompts:
            if self.can_read_prompt(
                user,
                owner_id=prompt.get("owner_id"),
                team_id=prompt.get("team_id"),
                visibility=prompt.get("visibility", "private"),
            ):
                visible.append(prompt)
        return visible
