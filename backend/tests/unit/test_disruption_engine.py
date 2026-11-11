import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionEvent,
    DisruptionEventType,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.order import Order, OrderPriority, OrderStatus
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse, WarehouseStatus
from app.schemas.disruption import DisruptionCreate
from app.services.disruptions.engine import DisruptionEngine
from app.services.disruptions.exceptions import (
    DisruptionNotFoundError,
    InvalidDisruptionTransitionError,
    TargetResourceValidationError,
)
from app.services.disruptions.severity import calculate_severity


def test_severity_calculation_vehicle_breakdown():
    # Empty/idle vehicle
    assert calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 0.0, "is_idle": True}) == DisruptionSeverity.LOW
    # Medium load
    assert calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 300.0}) == DisruptionSeverity.MEDIUM
    # High load
    assert calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 650.0}) == DisruptionSeverity.HIGH
    # Heavy load (> 1000 kg)
    assert calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 1200.0}) == DisruptionSeverity.CRITICAL
    # Urgent orders carried
    assert calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"has_urgent_orders": True, "current_load_kg": 100.0}) == DisruptionSeverity.CRITICAL


def test_severity_calculation_traffic_congestion():
    # Minor traffic
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 10.0, "delay_minutes": 5.0}) == DisruptionSeverity.LOW
    # Medium traffic
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 25.0, "delay_minutes": 18.0}) == DisruptionSeverity.MEDIUM
    # High traffic
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 45.0, "delay_minutes": 35.0}) == DisruptionSeverity.HIGH
    # Critical traffic
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 75.0, "delay_minutes": 70.0}) == DisruptionSeverity.CRITICAL


def test_severity_calculation_warehouse_shutdown():
    # Idle/empty warehouse
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 0.0, "active_orders": 0}) == DisruptionSeverity.LOW
    # Medium
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 20.0, "active_orders": 4}) == DisruptionSeverity.MEDIUM
    # High
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 55.0, "active_orders": 12}) == DisruptionSeverity.HIGH
    # Critical
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 85.0, "active_orders": 25}) == DisruptionSeverity.CRITICAL


def test_severity_calculation_demand_surge():
    # Low surge
    assert calculate_severity(DisruptionType.DEMAND_SURGE, {"surge_multiplier": 1.1, "extra_orders": 5}) == DisruptionSeverity.LOW
    # Medium surge
    assert calculate_severity(DisruptionType.DEMAND_SURGE, {"surge_multiplier": 1.4, "extra_orders": 12}) == DisruptionSeverity.MEDIUM
    # High surge
    assert calculate_severity(DisruptionType.DEMAND_SURGE, {"surge_multiplier": 2.2, "extra_orders": 30}) == DisruptionSeverity.HIGH
    # Critical surge
    assert calculate_severity(DisruptionType.DEMAND_SURGE, {"surge_multiplier": 3.5, "extra_orders": 60}) == DisruptionSeverity.CRITICAL


def test_severity_calculation_delivery_delay():
    # Low delay
    assert calculate_severity(DisruptionType.DELIVERY_DELAY, {"delay_minutes": 15.0}) == DisruptionSeverity.LOW
    # Medium delay
    assert calculate_severity(DisruptionType.DELIVERY_DELAY, {"delay_minutes": 35.0}) == DisruptionSeverity.MEDIUM
    # High delay
    assert calculate_severity(DisruptionType.DELIVERY_DELAY, {"delay_minutes": 75.0}) == DisruptionSeverity.HIGH
    # Critical delay / urgent
    assert calculate_severity(DisruptionType.DELIVERY_DELAY, {"delay_minutes": 130.0}) == DisruptionSeverity.CRITICAL
    assert calculate_severity(DisruptionType.DELIVERY_DELAY, {"delay_minutes": 10.0, "is_urgent": True}) == DisruptionSeverity.CRITICAL


def test_disruption_model_constraints(db_session: Session):
    d1 = Disruption(
        disruption_code="DISR-TEST-UQ-001",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        title="Traffic Test",
        severity=DisruptionSeverity.MEDIUM.value,
        status=DisruptionStatus.DETECTED.value,
    )
    db_session.add(d1)
    db_session.commit()

    # Duplicate disruption_code should fail
    d2 = Disruption(
        disruption_code="DISR-TEST-UQ-001",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        title="Duplicate Code",
        severity=DisruptionSeverity.MEDIUM.value,
        status=DisruptionStatus.DETECTED.value,
    )
    db_session.add(d2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_disruption_impact_unique_constraint(db_session: Session):
    d = Disruption(
        disruption_code="DISR-TEST-IMP-001",
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN.value,
        title="Breakdown Test",
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
    )
    db_session.add(d)
    db_session.commit()

    imp1 = DisruptionImpact(
        disruption_id=d.id,
        affected_resource_type=AffectedResourceType.VEHICLE.value,
        affected_resource_id="VEH-001",
        impact_category="DIRECT",
        severity="HIGH",
    )
    db_session.add(imp1)
    db_session.commit()

    # Same disruption, resource type, resource id should fail
    imp2 = DisruptionImpact(
        disruption_id=d.id,
        affected_resource_type=AffectedResourceType.VEHICLE.value,
        affected_resource_id="VEH-001",
        impact_category="INDIRECT",
        severity="MEDIUM",
    )
    db_session.add(imp2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_disruption_engine_lifecycle(db_session: Session):
    engine = DisruptionEngine(db_session)

    # 1. Create Disruption
    payload = DisruptionCreate(
        disruption_type=DisruptionType.TRAFFIC_CONGESTION,
        title="Heavy Rain Congestion",
        description="Rain causing traffic slowdowns",
        parameters={"speed_reduction_pct": 50.0, "delay_minutes": 40.0},
    )
    disruption = engine.create_disruption(payload)
    assert disruption.id is not None
    assert disruption.status == DisruptionStatus.DETECTED.value
    assert disruption.severity == DisruptionSeverity.HIGH.value
    assert len(disruption.events) >= 1
    assert disruption.events[0].event_type == DisruptionEventType.DISRUPTION_CREATED.value

    # 2. Activate Disruption
    disruption = engine.activate_disruption(disruption.id)
    assert disruption.status == DisruptionStatus.ACTIVE.value

    # 3. Put into Monitoring
    disruption = engine.set_monitoring(disruption.id)
    assert disruption.status == DisruptionStatus.MONITORING.value

    # 4. Resolve Disruption
    disruption = engine.resolve_disruption(disruption.id)
    assert disruption.status == DisruptionStatus.RESOLVED.value
    assert disruption.actual_end_time is not None

    # 5. Resolving already resolved disruption raises error
    with pytest.raises(InvalidDisruptionTransitionError):
        engine.resolve_disruption(disruption.id)

    # 6. Cancelling resolved disruption raises error
    with pytest.raises(InvalidDisruptionTransitionError):
        engine.cancel_disruption(disruption.id)


def test_disruption_invalid_target_validation(db_session: Session):
    engine = DisruptionEngine(db_session)
    payload = DisruptionCreate(
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN,
        title="Invalid Vehicle Breakdown",
        affected_vehicle_id="non-existent-uuid",
    )
    with pytest.raises(TargetResourceValidationError):
        engine.create_disruption(payload)

