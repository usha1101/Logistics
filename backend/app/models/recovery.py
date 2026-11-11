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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RecoveryPlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPTIMIZING = "OPTIMIZING"
    OPTIMIZED = "OPTIMIZED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class OptimizationStrategy(str, enum.Enum):
    SINGLE_VEHICLE_RECOVERY = "SINGLE_VEHICLE_RECOVERY"
    MULTI_VEHICLE_RECOVERY = "MULTI_VEHICLE_RECOVERY"
    PRIORITY_BASED_RECOVERY = "PRIORITY_BASED_RECOVERY"
    ALTERNATIVE_ROUTE_RECOVERY = "ALTERNATIVE_ROUTE_RECOVERY"
    PARTIAL_RECOVERY = "PARTIAL_RECOVERY"


class RecoveryActionStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class RecoveryPlan(Base):
    __tablename__ = "recovery_plans"
    __table_args__ = (
        UniqueConstraint("recovery_code", name="uq_recovery_code"),
        Index("ix_recovery_plans_disr_status", "disruption_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    recovery_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
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
    agent_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RecoveryPlanStatus.DRAFT.value,
        index=True,
    )
    optimization_strategy: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=OptimizationStrategy.MULTI_VEHICLE_RECOVERY.value,
        index=True,
    )
    objective_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    estimated_total_distance_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    estimated_total_travel_time_minutes: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    estimated_total_delay_minutes: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    estimated_recovery_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    affected_order_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    reassigned_order_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    assigned_vehicle_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    optimization_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    disruption = relationship("Disruption", lazy="joined")
    simulation = relationship("Simulation", lazy="joined")
    agent_run = relationship("AgentRun", lazy="joined")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    approved_by_user = relationship("User", foreign_keys=[approved_by_user_id], lazy="joined")

    assignments = relationship(
        "RecoveryAssignment",
        back_populates="recovery_plan",
        cascade="all, delete-orphan",
        lazy="select",
    )
    actions = relationship(
        "RecoveryAction",
        back_populates="recovery_plan",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="RecoveryAction.created_at",
    )
    audit_logs = relationship(
        "RecoveryAuditLog",
        back_populates="recovery_plan",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="RecoveryAuditLog.created_at",
    )
    comparisons = relationship(
        "RecoveryComparison",
        back_populates="recovery_plan",
        cascade="all, delete-orphan",
        lazy="select",
    )


class RecoveryAssignment(Base):
    __tablename__ = "recovery_assignments"
    __table_args__ = (
        Index("ix_recovery_assignments_plan_order", "recovery_plan_id", "order_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recovery_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_vehicle_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposed_vehicle_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    origin_node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_nodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    destination_node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_nodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proposed_route_node_ids: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    proposed_route_edge_ids: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    estimated_distance_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    estimated_travel_time_minutes: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    estimated_delay_minutes: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    order_priority: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="NORMAL",
    )
    assignment_reason: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    validation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="VALIDATED",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    recovery_plan = relationship("RecoveryPlan", back_populates="assignments")
    order = relationship("Order", lazy="joined")
    previous_vehicle = relationship("Vehicle", foreign_keys=[previous_vehicle_id], lazy="joined")
    proposed_vehicle = relationship("Vehicle", foreign_keys=[proposed_vehicle_id], lazy="joined")
    origin_node = relationship("NetworkNode", foreign_keys=[origin_node_id], lazy="joined")
    destination_node = relationship("NetworkNode", foreign_keys=[destination_node_id], lazy="joined")


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recovery_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    target_resource_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    target_resource_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    action_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RecoveryActionStatus.PENDING.value,
        index=True,
    )
    execution_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    recovery_plan = relationship("RecoveryPlan", back_populates="actions")


class RecoveryAuditLog(Base):
    __tablename__ = "recovery_audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recovery_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    new_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    performed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    recovery_plan = relationship("RecoveryPlan", back_populates="audit_logs")
    performed_by_user = relationship("User", lazy="joined")


class RecoveryComparison(Base):
    __tablename__ = "recovery_comparisons"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recovery_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    baseline_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    proposed_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    improvement_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    improvement_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    unit: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    recovery_plan = relationship("RecoveryPlan", back_populates="comparisons")
