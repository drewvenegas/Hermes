"""
Audit Log Model

Stores audit trail for all actions in Hermes.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID, INET
from sqlalchemy.orm import Mapped, mapped_column

from hermes.models.base import Base, UUIDMixin


class AuditLog(Base, UUIDMixin):
    """
    Audit log entry for tracking user actions.

    Attributes:
        id: Unique audit log ID
        user_id: User who performed the action
        action: Action type (create, read, update, delete, etc.)
        resource_type: Type of resource affected (prompt, benchmark, etc.)
        resource_id: ID of the affected resource
        details: Additional details about the action
        ip_address: IP address of the request
        user_agent: User agent string
        request_id: Correlation ID for the request
        timestamp: When the action occurred
    """

    __tablename__ = "audit_logs"

    # Who
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    api_key_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # What
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Details
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    endpoint: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    http_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # When
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    # Status
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action}, resource={self.resource_type}:{self.resource_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "api_key_id": str(self.api_key_id) if self.api_key_id else None,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "details": self.details,
            "ip_address": self.ip_address,
            "request_id": self.request_id,
            "endpoint": self.endpoint,
            "http_method": self.http_method,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "error_message": self.error_message,
        }
