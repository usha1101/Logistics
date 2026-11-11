from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.agent import (
    AgentExecution,
    AgentExecutionStatus,
    AgentRecommendation,
    AgentRun,
    AgentRunStatus,
    RecommendationPriority,
    RecommendationValidationStatus,
)
from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.network import NetworkNode, NodeType
from app.models.order import Customer, Order, OrderPriority, OrderStatus
from app.models.recovery import (
    OptimizationStrategy,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryComparison,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.models.simulation import (
    Simulation,
    SimulationStatus,
    SimulationTelemetry,
    SimulationVehicleState,
    SimulationVehicleStatus,
)
from app.models.vehicle import (
    LocationSource,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
    VehicleStatusHistory,
    VehicleType,
)
from app.models.warehouse import (
    InventoryItem,
    InventoryMovement,
    MovementType,
    Warehouse,
    WarehouseStatus,
    WarehouseType,
)
from app.schemas.analytics import TrendGrouping
from app.services.analytics import (
    InvalidDateRangeError,
    compute_agent_analytics,
    compute_agent_trends,
    compute_disruption_analytics,
    compute_disruption_trends,
    compute_fleet_analytics,
    compute_fleet_trends,
    compute_order_analytics,
    compute_order_trends,
    compute_overview_analytics,
    compute_performance_comparisons,
    compute_recovery_analytics,
    compute_recovery_trends,
    compute_simulation_analytics,
    compute_warehouse_analytics,
    compute_warehouse_trends,
)


def _seed_base_network(db: Session):
    wh_node = NetworkNode(
        name="BLR Hub Alpha",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9716,
        longitude=77.5946,
        is_active=True,
    )
    cust_node = NetworkNode(
        name="Cust Koramangala",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.9352,
        longitude=77.6245,
        is_active=True,
    )
    db.add_all([wh_node, cust_node])
    db.commit()

    wh = Warehouse(
        network_node_id=wh_node.id,
        warehouse_code="WH-ANL-01",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=1000.0,
        used_capacity=400.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    cust = Customer(
        customer_code="CUST-ANL-01",
        name="Acme Logistics Client",
        email="client@acme.io",
        phone="9876543210",
        address_line="Koramangala",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560034",
        latitude=12.9352,
        longitude=77.6245,
    )
    db.add_all([wh, cust])
    db.commit()
    return wh_node, cust_node, wh, cust


def test_empty_db_analytics_return_zero_or_null(db_session: Session):
    ov = compute_overview_analytics(db_session)
    assert ov.total_orders == 0
    assert ov.delivery_success_rate == 0.0
    assert ov.on_time_delivery_rate == 0.0
    assert ov.fleet_utilization_rate == 0.0
    assert ov.warehouse_utilization_rate == 0.0
    assert ov.recovery_success_rate == 0.0

    ord_res = compute_order_analytics(db_session)
    assert ord_res.total_orders == 0
    assert ord_res.average_delivery_duration_minutes is None
    assert ord_res.average_estimated_delay_minutes is None
    assert "average_delivery_duration_minutes" in ord_res.unavailable_metrics

    fl_res = compute_fleet_analytics(db_session)
    assert fl_res.total_vehicles == 0
    assert fl_res.total_distance_travelled_km is None
    assert "total_distance_travelled_km" in fl_res.unavailable_metrics


def test_invalid_date_range_raises_error(db_session: Session):
    now = datetime.now(timezone.utc)
    with pytest.raises(InvalidDateRangeError):
        compute_overview_analytics(
            db_session,
            start_date=now,
            end_date=now - timedelta(days=2),
        )


def test_order_analytics_formulas_and_overdue_vs_delayed(db_session: Session):
    _, _, wh, cust = _seed_base_network(db_session)
    now = datetime.now(timezone.utc)

    # 1. Delivered on-time (duration 60 min)
    o1 = Order(
        order_number="ORD-ANL-1",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.DELIVERED.value,
        priority=OrderPriority.HIGH.value,
        order_date=now - timedelta(hours=3),
        expected_delivery_at=now - timedelta(hours=1),
        delivered_at=now - timedelta(hours=2),
        delivery_address="Koramangala",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=50.0,
        total_amount=500.0,
    )
    # 2. Delivered late (duration 120 min)
    o2 = Order(
        order_number="ORD-ANL-2",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.DELIVERED.value,
        priority=OrderPriority.NORMAL.value,
        order_date=now - timedelta(hours=4),
        expected_delivery_at=now - timedelta(hours=3),
        delivered_at=now - timedelta(hours=2),
        delivery_address="Koramangala",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=30.0,
        total_amount=300.0,
    )
    # 3. Overdue in-transit order (expected_delivery_at in past)
    o3 = Order(
        order_number="ORD-ANL-3",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.URGENT.value,
        order_date=now - timedelta(hours=5),
        expected_delivery_at=now - timedelta(hours=1),
        delivery_address="Koramangala",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=20.0,
        total_amount=200.0,
    )
    # 4. Cancelled order (excluded from eligible denominator)
    o4 = Order(
        order_number="ORD-ANL-4",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.CANCELLED.value,
        priority=OrderPriority.LOW.value,
        order_date=now - timedelta(hours=2),
        expected_delivery_at=now + timedelta(hours=2),
        delivery_address="Koramangala",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=10.0,
        total_amount=100.0,
    )
    db_session.add_all([o1, o2, o3, o4])
    db_session.commit()

    # Add a disruption impacting o3 with estimated delay 45 min
    dis = Disruption(
        disruption_code="DIS-ANL-1",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Traffic Jam",
        affected_order_id=o3.id,
    )
    db_session.add(dis)
    db_session.commit()

    imp = DisruptionImpact(
        disruption_id=dis.id,
        affected_resource_type=AffectedResourceType.ORDER.value,
        affected_resource_id=o3.id,
        severity=DisruptionSeverity.HIGH.value,
        estimated_delay_minutes=45,
    )
    db_session.add(imp)
    db_session.commit()

    res = compute_order_analytics(db_session)
    assert res.total_orders == 4
    assert res.cancelled_orders == 1
    assert res.eligible_orders == 3
    assert res.delivered_orders == 2
    assert res.on_time_delivered_orders == 1
    assert res.late_delivered_orders == 1
    assert res.overdue_orders == 1
    assert res.estimated_delayed_orders == 1
    # delivery_success_rate = 2 / 3 * 100 = 66.67%
    assert res.delivery_success_rate == 66.67
    # on_time_delivery_rate = 1 / 2 * 100 = 50.0%
    assert res.on_time_delivery_rate == 50.0
    # average delivery duration = (60 + 120) / 2 = 90.0 min
    assert res.average_delivery_duration_minutes == 90.0
    assert res.average_estimated_delay_minutes == 45.0


def test_fleet_analytics_utilization_and_haversine_distance(db_session: Session):
    _, _, wh, _ = _seed_base_network(db_session)
    now = datetime.now(timezone.utc)

    v1 = Vehicle(
        vehicle_code="VEH-ANL-1",
        registration_number="KA01ANL0001",
        vehicle_type=VehicleType.MEDIUM_TRUCK.value,
        capacity_kg=1000.0,
        current_load_kg=500.0,
        status=VehicleStatus.IN_TRANSIT.value,
        home_warehouse_id=wh.id,
        is_active=True,
    )
    v2 = Vehicle(
        vehicle_code="VEH-ANL-2",
        registration_number="KA01ANL0002",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=500.0,
        current_load_kg=0.0,
        status=VehicleStatus.AVAILABLE.value,
        home_warehouse_id=wh.id,
        is_active=True,
    )
    db_session.add_all([v1, v2])
    db_session.commit()

    # Add 2 GPS location points for v1 (~4.8 km apart)
    loc1 = VehicleLocation(
        vehicle_id=v1.id,
        latitude=12.9716,
        longitude=77.5946,
        speed_kmph=40.0,
        recorded_at=now - timedelta(minutes=15),
        source=LocationSource.GPS.value,
    )
    loc2 = VehicleLocation(
        vehicle_id=v1.id,
        latitude=12.9352,
        longitude=77.6245,
        speed_kmph=35.0,
        recorded_at=now - timedelta(minutes=5),
        source=LocationSource.GPS.value,
    )
    db_session.add_all([loc1, loc2])
    db_session.commit()

    res = compute_fleet_analytics(db_session)
    assert res.total_vehicles == 2
    assert res.in_transit_vehicles == 1
    assert res.available_vehicles == 1
    assert res.total_fleet_capacity_kg == 1500.0
    assert res.total_current_load_kg == 500.0
    # fleet capacity utilization = 500 / 1500 * 100 = 33.33%
    assert res.fleet_capacity_utilization_percentage == 33.33
    # average load utilization = (50% + 0%) / 2 = 25.0%
    assert res.average_load_utilization_percentage == 25.0
    assert res.total_distance_travelled_km is not None
    assert res.total_distance_travelled_km > 4.0


def test_warehouse_analytics_stock_statuses_and_movements(db_session: Session):
    _, _, wh, _ = _seed_base_network(db_session)

    item_in = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-IN-1",
        product_name="In Stock Item",
        category="Electronics",
        quantity=100,
        reorder_level=20,
        unit="pcs",
        unit_volume=1.0,
    )
    item_low = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-LOW-1",
        product_name="Low Stock Item",
        category="Electronics",
        quantity=15,
        reorder_level=20,
        unit="pcs",
        unit_volume=1.0,
    )
    item_out = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-OUT-1",
        product_name="Out of Stock Item",
        category="Electronics",
        quantity=0,
        reorder_level=10,
        unit="pcs",
        unit_volume=1.0,
    )
    db_session.add_all([item_in, item_low, item_out])
    db_session.commit()

    m1 = InventoryMovement(
        inventory_item_id=item_in.id,
        movement_type=MovementType.STOCK_RECEIVED.value,
        quantity=50,
        previous_quantity=50,
        new_quantity=100,
    )
    m2 = InventoryMovement(
        inventory_item_id=item_low.id,
        movement_type=MovementType.STOCK_DISPATCHED.value,
        quantity=10,
        previous_quantity=25,
        new_quantity=15,
    )
    m3 = InventoryMovement(
        inventory_item_id=item_out.id,
        movement_type=MovementType.STOCK_ADJUSTMENT.value,
        quantity=5,
        previous_quantity=5,
        new_quantity=0,
    )
    db_session.add_all([m1, m2, m3])
    db_session.commit()

    res = compute_warehouse_analytics(db_session)
    assert res.total_warehouses == 1
    assert res.overall_utilization_percentage == 40.0
    assert res.total_inventory_items == 3
    assert res.in_stock_items == 1
    assert res.low_stock_items == 1
    assert res.out_of_stock_items == 1
    assert res.total_inventory_movements == 3
    assert res.inbound_quantity_total == 50
    assert res.outbound_quantity_total == 10
    assert res.adjustment_quantity_total == 5


def test_disruption_analytics_resolution_and_impacts(db_session: Session):
    now = datetime.now(timezone.utc)
    d1 = Disruption(
        disruption_code="DIS-U-1",
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN.value,
        severity=DisruptionSeverity.CRITICAL.value,
        status=DisruptionStatus.RESOLVED.value,
        title="Resolved Breakdown",
        start_time=now - timedelta(minutes=90),
        actual_end_time=now - timedelta(minutes=30),
    )
    d2 = Disruption(
        disruption_code="DIS-U-2",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        severity=DisruptionSeverity.MEDIUM.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Active Traffic",
        start_time=now - timedelta(minutes=20),
    )
    db_session.add_all([d1, d2])
    db_session.commit()

    imp = DisruptionImpact(
        disruption_id=d1.id,
        affected_resource_type=AffectedResourceType.VEHICLE.value,
        affected_resource_id="veh-123",
        severity=DisruptionSeverity.CRITICAL.value,
        estimated_delay_minutes=60,
    )
    db_session.add(imp)
    db_session.commit()

    res = compute_disruption_analytics(db_session)
    assert res.total_disruptions == 2
    assert res.active_disruptions == 1
    assert res.resolved_disruptions == 1
    assert res.average_resolution_time_minutes == 60.0
    assert res.estimated_total_delay_minutes == 60.0
    assert res.affected_vehicles_count == 1


def test_agent_analytics_and_unavailable_tokens(db_session: Session):
    d = Disruption(
        disruption_code="DIS-AG-1",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Delay",
    )
    db_session.add(d)
    db_session.commit()

    run = AgentRun(
        disruption_id=d.id,
        status=AgentRunStatus.COMPLETED.value,
        primary_provider="GEMINI",
        execution_duration_ms=420,
    )
    db_session.add(run)
    db_session.commit()

    ex1 = AgentExecution(
        agent_run_id=run.id,
        agent_name="DisruptionAnalysisAgent",
        status=AgentExecutionStatus.COMPLETED.value,
        provider="GEMINI",
        model="gemini-2.5-flash",
        confidence_score=0.9,
        execution_duration_ms=200,
    )
    ex2 = AgentExecution(
        agent_run_id=run.id,
        agent_name="FleetRecoveryAgent",
        status=AgentExecutionStatus.FAILED.value,
        provider="GROQ",
        model="llama-3.3-70b",
        confidence_score=0.5,
        execution_duration_ms=220,
    )
    rec = AgentRecommendation(
        agent_run_id=run.id,
        source_agent="DisruptionAnalysisAgent",
        recommendation_type="REASSIGN_VEHICLE",
        priority=RecommendationPriority.HIGH.value,
        title="Reassign vehicle",
        description="Reassign order to backup vehicle",
        validation_status=RecommendationValidationStatus.VALIDATED.value,
    )
    db_session.add_all([ex1, ex2, rec])
    db_session.commit()

    res = compute_agent_analytics(db_session)
    assert res.total_agent_runs == 1
    assert res.completed_runs == 1
    assert res.total_agent_executions == 2
    assert res.agent_success_rate == 50.0
    assert res.average_agent_execution_duration_ms == 210.0
    assert res.validated_recommendations == 1
    assert res.token_usage_total is None
    assert res.estimated_llm_cost_usd is None
    assert "token_usage_total" in res.unavailable_metrics


def test_recovery_analytics_unexecuted_not_counted_as_recovered(db_session: Session):
    d = Disruption(
        disruption_code="DIS-REC-1",
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN.value,
        severity=DisruptionSeverity.CRITICAL.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Breakdown",
    )
    db_session.add(d)
    db_session.commit()

    now = datetime.now(timezone.utc)
    # Plan 1: PENDING_APPROVAL with 5 proposed reassignments (must NOT count as recovered!)
    p_pending = RecoveryPlan(
        recovery_code="REC-U-1",
        disruption_id=d.id,
        status=RecoveryPlanStatus.PENDING_APPROVAL.value,
        optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        affected_order_count=5,
        reassigned_order_count=5,
        assigned_vehicle_count=2,
    )
    # Plan 2: EXECUTED with 3 reassignments (MUST count as recovered!)
    p_exec = RecoveryPlan(
        recovery_code="REC-U-2",
        disruption_id=d.id,
        status=RecoveryPlanStatus.EXECUTED.value,
        optimization_strategy=OptimizationStrategy.MULTI_VEHICLE_RECOVERY.value,
        affected_order_count=3,
        reassigned_order_count=3,
        assigned_vehicle_count=1,
        created_at=now - timedelta(minutes=20),
        executed_at=now - timedelta(minutes=10),
    )
    db_session.add_all([p_pending, p_exec])
    db_session.commit()

    act = RecoveryAction(
        recovery_plan_id=p_exec.id,
        action_type="REASSIGN_VEHICLE",
        target_resource_type="ORDER",
        target_resource_id="ord-1",
        status=RecoveryActionStatus.EXECUTED.value,
    )
    comp = RecoveryComparison(
        recovery_plan_id=p_exec.id,
        metric_name="total_delivery_delay",
        baseline_value=120.0,
        proposed_value=30.0,
        improvement_value=90.0,
        improvement_percentage=75.0,
        unit="minutes",
    )
    db_session.add_all([act, comp])
    db_session.commit()

    res = compute_recovery_analytics(db_session)
    assert res.total_recovery_plans == 2
    assert res.pending_approval_plans == 1
    assert res.executed_plans == 1
    assert res.total_reassigned_orders_proposed == 8
    assert res.total_recovered_orders == 3
    assert res.recovery_success_rate == 50.0
    assert res.estimated_delay_reduction_minutes == 90.0


def test_simulation_analytics_and_operational_separation(db_session: Session):
    wh_node, cust_node, wh, _ = _seed_base_network(db_session)
    v = Vehicle(
        vehicle_code="VEH-SIM-1",
        registration_number="KA01SIM0001",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=600.0,
        current_load_kg=100.0,
        status=VehicleStatus.AVAILABLE.value,
        home_warehouse_id=wh.id,
        is_active=True,
    )
    sim = Simulation(
        id="SIM-ANL-001",
        name="Test Sim",
        seed=42,
        status=SimulationStatus.COMPLETED.value,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        stopped_at=datetime.now(timezone.utc),
    )
    db_session.add_all([v, sim])
    db_session.commit()

    svs = SimulationVehicleState(
        simulation_id=sim.id,
        vehicle_id=v.id,
        origin_node_id=wh_node.id,
        destination_node_id=cust_node.id,
        route_node_ids=[wh_node.id, cust_node.id],
        current_latitude=12.9352,
        current_longitude=77.6245,
        status=SimulationVehicleStatus.ARRIVED.value,
        progress_percentage=100.0,
    )
    t1 = SimulationTelemetry(
        simulation_id=sim.id,
        vehicle_id=v.id,
        latitude=12.9716,
        longitude=77.5946,
        speed_kmph=40.0,
    )
    t2 = SimulationTelemetry(
        simulation_id=sim.id,
        vehicle_id=v.id,
        latitude=12.9352,
        longitude=77.6245,
        speed_kmph=40.0,
    )
    dis_sim = Disruption(
        disruption_code="DIS-SIM-ONLY",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        severity=DisruptionSeverity.LOW.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Sim Traffic",
        simulation_id=sim.id,
    )
    db_session.add_all([svs, t1, t2, dis_sim])
    db_session.commit()

    # Operational disruption analytics should NOT include simulated disruption by default
    op_dis = compute_disruption_analytics(db_session, include_simulations=False)
    assert op_dis.total_disruptions == 0

    # Simulation analytics should include simulated disruption and telemetry distance
    sim_res = compute_simulation_analytics(db_session, simulation_id=sim.id)
    assert sim_res.total_simulations == 1
    assert sim_res.completed_simulations == 1
    assert sim_res.total_simulated_vehicles == 1
    assert sim_res.total_simulated_distance_km is not None
    assert sim_res.total_simulated_distance_km > 4.0
    assert sim_res.simulated_disruptions_count == 1
    assert sim_res.average_simulation_duration_seconds == 120.0


def test_trends_bucketing_day_week_month(db_session: Session):
    _, _, wh, cust = _seed_base_network(db_session)
    o = Order(
        order_number="ORD-TRD-1",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.DELIVERED.value,
        priority=OrderPriority.NORMAL.value,
        expected_delivery_at=datetime.now(timezone.utc) + timedelta(hours=2),
        delivery_address="Koramangala",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=10.0,
        total_amount=100.0,
    )
    db_session.add(o)
    db_session.commit()

    for grp in (TrendGrouping.DAY, TrendGrouping.WEEK, TrendGrouping.MONTH):
        tr = compute_order_trends(db_session, grouping=grp)
        assert tr.grouping == grp
        assert tr.total_points == 1
        assert tr.data_points[0].value == 1.0
        assert tr.data_points[0].secondary_value == 100.0


def test_fleet_and_warehouse_trends_with_and_without_history(db_session: Session):
    _, _, wh, _ = _seed_base_network(db_session)
    # Without history
    fl_empty = compute_fleet_trends(db_session)
    assert fl_empty.is_historical is False
    assert fl_empty.total_points == 0

    wh_empty = compute_warehouse_trends(db_session)
    assert wh_empty.is_historical is False
    assert wh_empty.total_points == 0

    # Add vehicle status history and inventory movement
    v = Vehicle(
        vehicle_code="VEH-TRD-1",
        registration_number="KA01TRD0001",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=500.0,
        current_load_kg=100.0,
        status=VehicleStatus.IN_TRANSIT.value,
        home_warehouse_id=wh.id,
    )
    item = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-TRD-1",
        product_name="Trend Item",
        category="General",
        quantity=50,
        reorder_level=10,
        unit="pcs",
    )
    db_session.add_all([v, item])
    db_session.commit()

    vsh = VehicleStatusHistory(
        vehicle_id=v.id,
        previous_status=VehicleStatus.AVAILABLE.value,
        new_status=VehicleStatus.IN_TRANSIT.value,
    )
    mov = InventoryMovement(
        inventory_item_id=item.id,
        movement_type=MovementType.STOCK_RECEIVED.value,
        quantity=25,
        previous_quantity=25,
        new_quantity=50,
    )
    db_session.add_all([vsh, mov])
    db_session.commit()

    fl_tr = compute_fleet_trends(db_session)
    assert fl_tr.is_historical is True
    assert fl_tr.total_points == 1

    wh_tr = compute_warehouse_trends(db_session)
    assert wh_tr.is_historical is True
    assert wh_tr.total_points == 1
    assert wh_tr.data_points[0].value == 25.0


def test_disruption_agent_recovery_trends(db_session: Session):
    d = Disruption(
        disruption_code="DIS-TRD-1",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        severity=DisruptionSeverity.MEDIUM.value,
        status=DisruptionStatus.RESOLVED.value,
        title="Resolved traffic",
    )
    db_session.add(d)
    db_session.commit()

    run = AgentRun(
        disruption_id=d.id,
        status=AgentRunStatus.COMPLETED.value,
        primary_provider="GEMINI",
    )
    plan = RecoveryPlan(
        recovery_code="REC-TRD-1",
        disruption_id=d.id,
        status=RecoveryPlanStatus.EXECUTED.value,
        optimization_strategy=OptimizationStrategy.MULTI_VEHICLE_RECOVERY.value,
        reassigned_order_count=2,
    )
    db_session.add_all([run, plan])
    db_session.commit()

    d_tr = compute_disruption_trends(db_session)
    assert d_tr.total_points == 1
    assert d_tr.data_points[0].value == 1.0

    a_tr = compute_agent_trends(db_session)
    assert a_tr.total_points == 1
    assert a_tr.data_points[0].value == 100.0

    r_tr = compute_recovery_trends(db_session)
    assert r_tr.total_points == 1
    assert r_tr.data_points[0].value == 100.0
    assert r_tr.data_points[0].secondary_value == 2.0


def test_performance_comparisons_with_and_without_plans(db_session: Session):
    # Empty comparison returns null values, never fake zeroes
    empty_comp = compute_performance_comparisons(db_session)
    assert empty_comp.total_comparisons_evaluated == 0
    for m in empty_comp.metrics:
        assert m.before_value is None
        assert m.after_value is None

    # Seed plan + comparison
    d = Disruption(
        disruption_code="DIS-CMP-1",
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN.value,
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Breakdown",
    )
    db_session.add(d)
    db_session.commit()

    plan = RecoveryPlan(
        recovery_code="REC-CMP-1",
        disruption_id=d.id,
        status=RecoveryPlanStatus.EXECUTED.value,
        optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        affected_order_count=4,
        reassigned_order_count=4,
        assigned_vehicle_count=2,
        estimated_total_distance_km=18.5,
        estimated_total_delay_minutes=20.0,
        estimated_recovery_cost=250.0,
    )
    db_session.add(plan)
    db_session.commit()

    rc = RecoveryComparison(
        recovery_plan_id=plan.id,
        metric_name="total_delivery_delay",
        baseline_value=100.0,
        proposed_value=20.0,
        improvement_value=80.0,
        improvement_percentage=80.0,
        unit="minutes",
    )
    db_session.add(rc)
    db_session.commit()

    comp = compute_performance_comparisons(db_session, recovery_plan_id=plan.id)
    assert comp.total_comparisons_evaluated == 1
    delay_metric = next(m for m in comp.metrics if m.metric_name == "estimated_delay_minutes")
    assert delay_metric.before_value == 100.0
    assert delay_metric.after_value == 20.0
    assert delay_metric.absolute_difference == -80.0
    assert delay_metric.percentage_change == -80.0
    assert delay_metric.is_improved is True


def test_order_analytics_filter_by_priority_and_status(db_session: Session):
    _, _, wh, cust = _seed_base_network(db_session)
    now = datetime.now(timezone.utc)
    o_high = Order(
        order_number="ORD-FLT-1",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.CREATED.value,
        priority=OrderPriority.HIGH.value,
        expected_delivery_at=now + timedelta(hours=4),
        delivery_address="Koramangala",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=15.0,
        total_amount=150.0,
    )
    o_low = Order(
        order_number="ORD-FLT-2",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.CONFIRMED.value,
        priority=OrderPriority.LOW.value,
        expected_delivery_at=now + timedelta(hours=4),
        delivery_address="Koramangala",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=25.0,
        total_amount=250.0,
    )
    db_session.add_all([o_high, o_low])
    db_session.commit()

    res_high = compute_order_analytics(
        db_session, priority=OrderPriority.HIGH.value, status=OrderStatus.CREATED.value
    )
    assert res_high.total_orders == 1
    assert res_high.total_order_weight_kg == 15.0


def test_fleet_analytics_filter_by_vehicle_and_status(db_session: Session):
    _, _, wh, _ = _seed_base_network(db_session)
    v1 = Vehicle(
        vehicle_code="VEH-FLT-1",
        registration_number="KA01FLT0001",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        capacity_kg=2000.0,
        current_load_kg=1000.0,
        status=VehicleStatus.MAINTENANCE.value,
        home_warehouse_id=wh.id,
    )
    db_session.add(v1)
    db_session.commit()

    res = compute_fleet_analytics(
        db_session, vehicle_id=v1.id, status=VehicleStatus.MAINTENANCE.value
    )
    assert res.total_vehicles == 1
    assert res.maintenance_vehicles == 1
    assert res.average_load_utilization_percentage == 50.0


def test_fleet_analytics_simulation_telemetry_distance(db_session: Session):
    _, _, wh, _ = _seed_base_network(db_session)
    v = Vehicle(
        vehicle_code="VEH-SIM-DIST",
        registration_number="KA01SMD0001",
        vehicle_type=VehicleType.ELECTRIC_VAN.value,
        capacity_kg=400.0,
        current_load_kg=200.0,
        status=VehicleStatus.IN_TRANSIT.value,
        home_warehouse_id=wh.id,
    )
    sim = Simulation(id="SIM-DIST-1", name="Dist Sim", seed=11, status=SimulationStatus.RUNNING.value)
    db_session.add_all([v, sim])
    db_session.commit()

    t1 = SimulationTelemetry(
        simulation_id=sim.id,
        vehicle_id=v.id,
        latitude=12.9716,
        longitude=77.5946,
        speed_kmph=35.0,
    )
    t2 = SimulationTelemetry(
        simulation_id=sim.id,
        vehicle_id=v.id,
        latitude=12.9352,
        longitude=77.6245,
        speed_kmph=35.0,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    res = compute_fleet_analytics(db_session, simulation_id=sim.id)
    assert res.total_distance_travelled_km is not None
    assert res.vehicles[0].distance_data_source == "TELEMETRY_SEGMENTS"


def test_warehouse_analytics_filter_by_warehouse_and_status(db_session: Session):
    _, _, wh, _ = _seed_base_network(db_session)
    res = compute_warehouse_analytics(
        db_session, warehouse_id=wh.id, status=WarehouseStatus.OPERATIONAL.value
    )
    assert res.total_warehouses == 1
    assert res.operational_warehouses == 1

    res_none = compute_warehouse_analytics(db_session, status=WarehouseStatus.CLOSED.value)
    assert res_none.total_warehouses == 0


def test_disruption_analytics_filter_by_type_and_severity(db_session: Session):
    d = Disruption(
        disruption_code="DIS-FLT-1",
        disruption_type=DisruptionType.WAREHOUSE_SHUTDOWN.value,
        severity=DisruptionSeverity.CRITICAL.value,
        status=DisruptionStatus.MONITORING.value,
        title="Power outage",
    )
    db_session.add(d)
    db_session.commit()

    res = compute_disruption_analytics(
        db_session,
        disruption_type=DisruptionType.WAREHOUSE_SHUTDOWN.value,
        severity=DisruptionSeverity.CRITICAL.value,
        status=DisruptionStatus.MONITORING.value,
    )
    assert res.total_disruptions == 1
    assert res.active_disruptions == 1


def test_agent_analytics_filter_by_status_and_provider(db_session: Session):
    d = Disruption(
        disruption_code="DIS-AG-FLT",
        disruption_type=DisruptionType.DEMAND_SURGE.value,
        severity=DisruptionSeverity.MEDIUM.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Surge",
    )
    db_session.add(d)
    db_session.commit()

    r = AgentRun(
        disruption_id=d.id,
        status=AgentRunStatus.AI_UNAVAILABLE.value,
        primary_provider="GROQ",
    )
    db_session.add(r)
    db_session.commit()

    res = compute_agent_analytics(
        db_session, status=AgentRunStatus.AI_UNAVAILABLE.value, provider="GROQ"
    )
    assert res.total_agent_runs == 1
    assert res.ai_unavailable_runs == 1


def test_recovery_analytics_partially_executed_plan_actions(db_session: Session):
    d = Disruption(
        disruption_code="DIS-REC-PART",
        disruption_type=DisruptionType.DELIVERY_DELAY.value,
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Delay",
    )
    db_session.add(d)
    db_session.commit()

    p = RecoveryPlan(
        recovery_code="REC-PART-1",
        disruption_id=d.id,
        status=RecoveryPlanStatus.PARTIALLY_EXECUTED.value,
        optimization_strategy=OptimizationStrategy.PARTIAL_RECOVERY.value,
        affected_order_count=2,
        reassigned_order_count=2,
    )
    db_session.add(p)
    db_session.commit()

    a1 = RecoveryAction(
        recovery_plan_id=p.id,
        action_type="REASSIGN_VEHICLE",
        target_resource_type="ORDER",
        target_resource_id="o-1",
        status=RecoveryActionStatus.EXECUTED.value,
    )
    a2 = RecoveryAction(
        recovery_plan_id=p.id,
        action_type="REASSIGN_VEHICLE",
        target_resource_type="ORDER",
        target_resource_id="o-2",
        status=RecoveryActionStatus.FAILED.value,
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    res = compute_recovery_analytics(
        db_session,
        status=RecoveryPlanStatus.PARTIALLY_EXECUTED.value,
        strategy=OptimizationStrategy.PARTIAL_RECOVERY.value,
    )
    assert res.partially_executed_plans == 1
    assert res.total_recovered_orders == 1
    assert res.executed_actions == 1
    assert res.failed_actions == 1


def test_simulation_analytics_filter_by_status(db_session: Session):
    s1 = Simulation(id="SIM-ST-1", name="Stopped Sim", seed=1, status=SimulationStatus.STOPPED.value)
    s2 = Simulation(id="SIM-ST-2", name="Paused Sim", seed=2, status=SimulationStatus.PAUSED.value)
    db_session.add_all([s1, s2])
    db_session.commit()

    res_stopped = compute_simulation_analytics(db_session, status=SimulationStatus.STOPPED.value)
    assert res_stopped.total_simulations == 1
    assert res_stopped.cancelled_simulations == 1
