from datetime import datetime, timedelta, timezone
import pytest
from app.models.disruption import Disruption, DisruptionSeverity, DisruptionStatus, DisruptionType
from app.models.network import NetworkNode, NodeType
from app.models.order import Customer, Order, OrderPriority, OrderStatus
from app.models.recovery import (
    OptimizationStrategy,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryAssignment,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseType
from app.services.recovery.validator import RecoveryPlanValidator


@pytest.fixture
def validator_fixtures(db_session):
    node = NetworkNode(
        name="Validator Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9716,
        longitude=77.5946,
        region="Central",
        address="Central Hub Road",
        is_active=True,
    )
    db_session.add(node)
    db_session.commit()

    wh = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-VAL-01",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=10000.0,
        used_capacity=100.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    db_session.add(wh)
    db_session.commit()

    cust = Customer(
        customer_code="CUST-VAL-01",
        name="Validator Customer",
        phone="+91-80-99887766",
        address_line="Koramangala, Bengaluru",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560034",
        latitude=12.9352,
        longitude=77.6245,
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    veh = Vehicle(
        vehicle_code="KA-VAL-01",
        registration_number="KA-01-VAL-001",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        status=VehicleStatus.AVAILABLE.value,
        capacity_kg=1000.0,
        current_load_kg=200.0,
        is_active=True,
    )
    db_session.add(veh)
    db_session.commit()

    disr = Disruption(
        disruption_code="DIS-VAL-001",
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN.value,
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Vehicle Breakdown on Ring Road",
    )
    db_session.add(disr)
    db_session.commit()

    now = datetime.now(timezone.utc)
    ord1 = Order(
        order_number="ORD-VAL-001",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.CREATED.value,
        priority=OrderPriority.HIGH.value,
        expected_delivery_at=now + timedelta(hours=24),
        delivery_address="789 Indiranagar",
        delivery_latitude=12.9784,
        delivery_longitude=77.6408,
        total_weight_kg=150.0,
        total_amount=2500.0,
    )
    db_session.add(ord1)
    db_session.commit()

    return {
        "node": node,
        "warehouse": wh,
        "customer": cust,
        "vehicle": veh,
        "disruption": disr,
        "order": ord1,
    }


class TestRecoveryPlanValidator:
    def test_valid_plan_passes_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        plan = RecoveryPlan(
            recovery_code="REC-VAL-001",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
            estimated_delay_minutes=5.0,
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)

        assert report.is_valid is True
        assert report.status == "VALIDATED"
        assert len(report.violations) == 0

    def test_missing_order_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        plan = RecoveryPlan(
            recovery_code="REC-VAL-002",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            id="test-assign-missing-ord",
            recovery_plan_id=plan.id,
            order_id="non-existent-order-id",
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        plan.assignments.append(assign)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("no longer exists in database" in v for v in report.violations)

    def test_delivered_order_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        f["order"].status = OrderStatus.DELIVERED.value
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-003",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("terminal status" in v for v in report.violations)

    def test_cancelled_order_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        f["order"].status = OrderStatus.CANCELLED.value
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-004",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("terminal status" in v for v in report.violations)

    def test_missing_vehicle_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        plan = RecoveryPlan(
            recovery_code="REC-VAL-005",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            id="test-assign-missing-veh",
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id="missing-vehicle-id",
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        plan.assignments.append(assign)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("no longer exists" in v for v in report.violations)

    def test_breakdown_vehicle_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        f["vehicle"].status = VehicleStatus.BREAKDOWN.value
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-006",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("non-operational status 'BREAKDOWN'" in v for v in report.violations)

    def test_maintenance_vehicle_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        f["vehicle"].status = VehicleStatus.MAINTENANCE.value
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-007",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("non-operational status 'MAINTENANCE'" in v for v in report.violations)

    def test_offline_vehicle_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        f["vehicle"].status = VehicleStatus.OFFLINE.value
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-008",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("non-operational status 'OFFLINE'" in v for v in report.violations)

    def test_inactive_vehicle_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        f["vehicle"].is_active = False
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-009",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("non-operational status" in v for v in report.violations)

    def test_vehicle_capacity_headroom_exceeded_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        # capacity: 1000, current load: 200, headroom: 800.
        # Order weight: 950 -> exceeds headroom!
        f["order"].total_weight_kg = 950.0
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-010",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("capacity exceeded" in v for v in report.violations)

    def test_cumulative_multiple_orders_exceed_capacity(self, db_session, validator_fixtures):
        f = validator_fixtures
        now = datetime.now(timezone.utc)
        # vehicle headroom: 800. Two orders: 500kg and 400kg = 900kg -> exceeds headroom!
        ord2 = Order(
            order_number="ORD-VAL-002",
            customer_id=f["customer"].id,
            warehouse_id=f["warehouse"].id,
            status=OrderStatus.CREATED.value,
            priority=OrderPriority.HIGH.value,
            expected_delivery_at=now + timedelta(hours=24),
            delivery_address="789 Indiranagar",
            delivery_latitude=12.9784,
            delivery_longitude=77.6408,
            total_weight_kg=400.0,
            total_amount=2500.0,
        )
        f["order"].total_weight_kg = 500.0
        db_session.add(ord2)
        db_session.commit()

        plan = RecoveryPlan(
            recovery_code="REC-VAL-011",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign1 = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        assign2 = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=ord2.id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[f["node"].id],
        )
        db_session.add_all([assign1, assign2])
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("capacity exceeded" in v for v in report.violations)

    def test_empty_route_node_sequence_fails_validation(self, db_session, validator_fixtures):
        f = validator_fixtures
        plan = RecoveryPlan(
            recovery_code="REC-VAL-012",
            disruption_id=f["disruption"].id,
            status=RecoveryPlanStatus.PENDING_APPROVAL.value,
            optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        )
        db_session.add(plan)
        db_session.commit()

        assign = RecoveryAssignment(
            recovery_plan_id=plan.id,
            order_id=f["order"].id,
            proposed_vehicle_id=f["vehicle"].id,
            origin_node_id=f["node"].id,
            destination_node_id=f["node"].id,
            proposed_route_node_ids=[],
        )
        db_session.add(assign)
        db_session.commit()
        db_session.refresh(plan)

        validator = RecoveryPlanValidator(db_session)
        report = validator.validate_plan(plan)
        assert report.is_valid is False
        assert any("empty or invalid route node sequence" in v for v in report.violations)
