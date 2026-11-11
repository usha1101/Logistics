import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ReportType(str, enum.Enum):
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    FLEET_PERFORMANCE = "FLEET_PERFORMANCE"
    WAREHOUSE_PERFORMANCE = "WAREHOUSE_PERFORMANCE"
    DISRUPTION_REPORT = "DISRUPTION_REPORT"
    AI_INTELLIGENCE_REPORT = "AI_INTELLIGENCE_REPORT"
    RECOVERY_PERFORMANCE = "RECOVERY_PERFORMANCE"
    SIMULATION_REPORT = "SIMULATION_REPORT"


class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ReportMetadata(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("report_code", name="uq_report_code"),
        Index("ix_reports_type_status", "report_type", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    report_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="LOGIPULSE Analytics Report",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ReportStatus.COMPLETED.value,
        index=True,
    )
    requested_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    simulation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("simulations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    include_simulations: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    filters: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    summary_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    include_charts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    file_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    file_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )

    # Relationships
    requested_by_user = relationship("User", foreign_keys=[requested_by_user_id], lazy="joined")
