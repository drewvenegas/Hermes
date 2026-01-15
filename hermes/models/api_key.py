"""
API Key Model

Stores API keys for programmatic access to Hermes.
"""

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hermes.models.base import Base, UUIDMixin


class APIKey(Base, UUIDMixin):
    """
    API Key for programmatic access.

    Attributes:
        id: Unique API key ID
        name: Human-readable name for the key
        description: Optional description
        key_prefix: First 8 chars of key for identification (hrms_xxxx)
        key_hash: SHA-256 hash of the full key
        scopes: List of permission scopes
        expires_at: Optional expiration date
        last_used_at: Last time the key was used
        created_by: User who created the key
        is_active: Whether the key is active
    """

    __tablename__ = "api_keys"

    # Identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Permissions
    scopes: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Lifecycle
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    use_count: Mapped[int] = mapped_column(nullable=False, default=0)

    # Ownership
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    revoked_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    allowed_ips: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_api_keys_created_by", "created_by"),
        Index("ix_api_keys_active", "is_active"),
        Index("ix_api_keys_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<APIKey(name={self.name}, prefix={self.key_prefix})>"

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """
        Generate a new API key.
        
        Returns:
            Tuple of (full_key, key_prefix, key_hash)
        """
        # Generate 32 random bytes = 256 bits of entropy
        random_bytes = secrets.token_bytes(32)
        key_suffix = secrets.token_urlsafe(32)
        
        # Create the full key with prefix
        full_key = f"hrms_{key_suffix}"
        key_prefix = full_key[:12]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        
        return full_key, key_prefix, key_hash

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for comparison."""
        return hashlib.sha256(key.encode()).hexdigest()

    def is_valid(self) -> bool:
        """Check if the API key is valid."""
        if not self.is_active:
            return False
        if self.revoked_at:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        """Check if the key has a specific scope."""
        if "*" in self.scopes:
            return True
        if scope in self.scopes:
            return True
        # Check wildcard scopes (e.g., "prompts:*" matches "prompts:read")
        scope_prefix = scope.split(":")[0]
        return f"{scope_prefix}:*" in self.scopes

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary."""
        data = {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "use_count": self.use_count,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') else None,
            "is_active": self.is_active,
            "is_valid": self.is_valid(),
        }
        if include_sensitive:
            data["allowed_ips"] = self.allowed_ips
            data["metadata"] = self.metadata
        return data


# Standard scopes
STANDARD_SCOPES = [
    "prompts:read",
    "prompts:write",
    "prompts:delete",
    "benchmarks:read",
    "benchmarks:write",
    "experiments:read",
    "experiments:write",
    "versions:read",
    "versions:write",
    "templates:read",
    "templates:write",
    "api-keys:read",
    "api-keys:write",
    "audit:read",
    "agent:manage",
    "nursery:read",
    "nursery:sync",
    "gates:read",
    "gates:write",
    "*",  # Full access
]
