import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AgentRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"


class AgentExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RecommendationPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationValidationStatus(str, enum.Enum):
    VALIDATED = "VALIDATED"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"
    REJECTED = "REJECTED"
    INFORMATIONAL = "INFORMATIONAL"


class RecommendationExecutionStatus(str, enum.Enum):
    RECOMMENDED_ONLY = "RECOMMENDED_ONLY"  # Stage 10 rule: NEVER automatically executed
    PENDING_APPROVAL = "PENDING_APPROVAL"


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_disr_status", "disruption_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    disruption_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("disruptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    simulation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("simulations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AgentRunStatus.PENDING.value,
        index=True,
    )
    primary_provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="gemini",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    execution_duration_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    error_summary: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    disruption = relationship("Disruption", lazy="joined")
    simulation = relationship("Simulation", lazy="joined")
    created_by_user = relationship("User", lazy="joined")

    executions = relationship(
        "AgentExecution",
        back_populates="agent_run",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="AgentExecution.started_at",
    )
    recommendations = relationship(
        "AgentRecommendation",
        back_populates="agent_run",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(AgentRecommendation.priority)",
    )


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        Index("ix_agent_exec_run_agent", "agent_run_id", "agent_name"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    agent_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AgentExecutionStatus.PENDING.value,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    input_summary: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    output: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    evidence_references: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
    )
    warnings: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
    )
    execution_duration_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    agent_run = relationship("AgentRun", back_populates="executions")


class AgentRecommendation(Base):
    __tablename__ = "agent_recommendations"
    __table_args__ = (
        Index("ix_agent_rec_run_priority", "agent_run_id", "priority"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    agent_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_agent: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    recommendation_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RecommendationPriority.MEDIUM.value,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_resource_type: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    target_resource_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    validation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RecommendationValidationStatus.REQUIRES_VALIDATION.value,
        index=True,
    )
    execution_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RecommendationExecutionStatus.RECOMMENDED_ONLY.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    agent_run = relationship("AgentRun", back_populates="recommendations")

