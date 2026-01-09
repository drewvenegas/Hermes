"""
Hermes Authentication Module

OIDC authentication with PERSONA SSO.
"""

from hermes.auth.oidc import router as auth_router
from hermes.auth.dependencies import get_current_user, require_permission
from hermes.auth.models import User, TokenData

__all__ = [
    "auth_router",
    "get_current_user",
    "require_permission",
    "User",
    "TokenData",
]
