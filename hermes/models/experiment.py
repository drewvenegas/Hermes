"""
Experiment Models

Models for A/B testing experiments and events.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermes.models.base import Base, UUIDMixin


class ExperimentStatus(str, Enum):
    """Experiment lifecycle status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Experiment(Base, UUIDMixin):
    """
    A/B Experiment for comparing prompt variants.

    Attributes:
        id: Unique experiment ID
        name: Human-readable experiment name
        description: Detailed description
        status: Current lifecycle status
        variants: JSON array of variant configurations
        metrics: JSON array of metric configurations
        traffic_split: Traffic splitting strategy
        traffic_percentage: % of traffic in experiment
        min_sample_size: Minimum samples before significance testing
        max_duration_days: Maximum experiment duration
        confidence_threshold: Statistical confidence threshold
        auto_promote: Whether to auto-promote winner
        started_at: When experiment started
        ended_at: When experiment ended
        result: Final experiment results
        created_by: User who created the experiment
    """

    __tablename__ = "experiments"

    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ExperimentStatus.DRAFT.value,
        index=True,
    )

    # Configuration
    variants: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Array of variant configs
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Array of metric configs
    traffic_split: Mapped[str] = mapped_column(String(50), nullable=False, default="equal")
    traffic_percentage: Mapped[float] = mapped_column(nullable=False, default=100.0)

    # Thresholds
    min_sample_size: Mapped[int] = mapped_column(nullable=False, default=1000)
    max_duration_days: Mapped[int] = mapped_column(nullable=False, default=14)
    confidence_threshold: Mapped[float] = mapped_column(nullable=False, default=0.95)
    auto_promote: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Lifecycle
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Results
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    winner_variant_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Ownership
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Metadata
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    events: Mapped[List["ExperimentEvent"]] = relationship(
        "ExperimentEvent",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_experiments_status", "status"),
        Index("ix_experiments_created_by", "created_by"),
        Index("ix_experiments_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<Experiment(name={self.name}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "variants": self.variants,
            "metrics": self.metrics,
            "traffic_split": self.traffic_split,
            "traffic_percentage": self.traffic_percentage,
            "min_sample_size": self.min_sample_size,
            "max_duration_days": self.max_duration_days,
            "confidence_threshold": self.confidence_threshold,
            "auto_promote": self.auto_promote,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "result": self.result,
            "winner_variant_id": self.winner_variant_id,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') else None,
            "tags": self.tags,
        }


class ExperimentEvent(Base, UUIDMixin):
    """
    Event recorded during an experiment.

    Attributes:
        id: Unique event ID
        experiment_id: Parent experiment
        variant_id: Variant that received the event
        user_id: User/session identifier
        event_type: Type of event (impression, conversion, etc.)
        value: Numeric value for the event
        metadata: Additional event data
        timestamp: When the event occurred
    """

    __tablename__ = "experiment_events"

    # Reference
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # User/session
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Event data
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[float] = mapped_column(nullable=False, default=1.0)
    metric_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Context
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    # Relationships
    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="events")

    # Indexes
    __table_args__ = (
        Index("ix_experiment_events_experiment_variant", "experiment_id", "variant_id"),
        Index("ix_experiment_events_timestamp", "timestamp"),
        Index("ix_experiment_events_type", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<ExperimentEvent(experiment={self.experiment_id}, type={self.event_type})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "experiment_id": str(self.experiment_id),
            "variant_id": self.variant_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "value": self.value,
            "metric_id": self.metric_id,
            "timestamp": self.timestamp.isoformat(),
        }
