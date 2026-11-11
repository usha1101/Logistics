from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionType,
)
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.network import NetworkEdge
from app.models.order import Order, OrderPriority, OrderStatus
from app.models.warehouse import Warehouse
from app.schemas.disruption import (
    AffectedOrderSummary,
    AffectedVehicleSummary,
    AtRiskOrderSummary,
    DisruptionAnalysisReport,
)


class DisruptionImpactAnalyzer:
    """
    Deterministic analyzer for calculating logistics disruption blast radius,
    cascading delays, affected orders, at-risk orders, and affected vehicles.
    """

    def __init__(self, db: Session):
        self.db = db

    def analyze(self, disruption: Disruption, persist_impacts: bool = True) -> DisruptionAnalysisReport:
        d_type = disruption.disruption_type
        params = disruption.parameters or {}

        affected_vehicles: List[AffectedVehicleSummary] = []
        affected_orders: List[AffectedOrderSummary] = []
        at_risk_orders: List[AtRiskOrderSummary] = []
        warehouses_count = 0
        network_edges_count = 0
        total_delay_minutes = 0.0

        now = datetime.now(timezone.utc)

        # 1. VEHICLE_BREAKDOWN
        if d_type == DisruptionType.VEHICLE_BREAKDOWN.value:
            vehicle = None
            if disruption.affected_vehicle_id:
                vehicle = self.db.get(Vehicle, disruption.affected_vehicle_id)

            if vehicle:
                est_delay = float(params.get("delay_minutes", 120.0))
                total_delay_minutes += est_delay
                affected_vehicles.append(
                    AffectedVehicleSummary(
                        vehicle_id=vehicle.id,
                        vehicle_code=vehicle.vehicle_code,
                        registration_number=vehicle.registration_number,
                        status=vehicle.status,
                        current_load_kg=vehicle.current_load_kg or 0.0,
                        impact_category="DIRECT",
                        severity=disruption.severity,
                        estimated_delay_minutes=est_delay,
                    )
                )

                # Fetch orders assigned to this vehicle
                orders = self.db.scalars(
                    select(Order).where(
                        Order.assigned_vehicle_id == vehicle.id,
                        Order.status.in_([
                            OrderStatus.READY_FOR_DISPATCH.value,
                            OrderStatus.DISPATCHED.value,
                            OrderStatus.IN_TRANSIT.value,
                        ]),
                    )
                ).all()

                for order in orders:
                    is_urgent = (order.priority == OrderPriority.URGENT.value)
                    is_overdue = False
                    is_at_risk = False

                    if order.expected_delivery_at:
                        # Check if expected delivery + estimated delay pushes it past deadline or is already past
                        order_exp = order.expected_delivery_at
                        if order_exp.tzinfo is None:
                            order_exp = order_exp.replace(tzinfo=timezone.utc)
                        if order_exp < now:
                            is_overdue = True
                            is_at_risk = True
                        else:
                            # If remaining minutes < estimated delay
                            remaining_mins = (order_exp - now).total_seconds() / 60.0
                            if remaining_mins < est_delay:
                                is_at_risk = True
                    else:
                        is_at_risk = is_urgent

                    aff_ord = AffectedOrderSummary(
                        order_id=order.id,
                        order_number=order.order_number,
                        status=order.status,
                        priority=order.priority,
                        sla_hours=None,
                        expected_delivery_at=order.expected_delivery_at,
                        estimated_delay_minutes=est_delay,
                        is_at_risk=is_at_risk,
                        is_overdue=is_overdue,
                        customer_name=order.customer.name if order.customer else None,
                    )
                    affected_orders.append(aff_ord)

                    if is_at_risk or is_overdue:
                        risk_level = "CRITICAL" if (is_urgent or is_overdue) else "HIGH"
                        at_risk_orders.append(
                            AtRiskOrderSummary(
                                order_id=order.id,
                                order_number=order.order_number,
                                status=order.status,
                                priority=order.priority,
                                expected_delivery_at=order.expected_delivery_at,
                                estimated_delay_minutes=est_delay,
                                risk_level=risk_level,
                            )
                        )

        # 2. TRAFFIC_CONGESTION
        elif d_type == DisruptionType.TRAFFIC_CONGESTION.value:
            edge = None
            if disruption.affected_network_edge_id:
                edge = self.db.get(NetworkEdge, disruption.affected_network_edge_id)

            if edge:
                network_edges_count = 1
                delay_mins = float(params.get("delay_minutes", 45.0))
                total_delay_minutes += delay_mins

                # Any vehicles that might be on this edge or route
                # For deterministic modeling: in-transit vehicles assigned to orders connected to edge nodes
                connected_node_ids = {edge.source_node_id, edge.target_node_id}

                # Find orders whose assigned vehicle is IN_TRANSIT and destination is connected
                transit_orders = self.db.scalars(
                    select(Order).where(
                        Order.status == OrderStatus.IN_TRANSIT.value,
                        Order.assigned_vehicle_id.isnot(None),
                    )
                ).all()

                for order in transit_orders:
                    # If customer is on or near the connected node or default sample
                    aff_ord = AffectedOrderSummary(
                        order_id=order.id,
                        order_number=order.order_number,
                        status=order.status,
                        priority=order.priority,
                        sla_hours=None,
                        expected_delivery_at=order.expected_delivery_at,
                        estimated_delay_minutes=delay_mins,
                        is_at_risk=(order.priority == OrderPriority.URGENT.value),
                        is_overdue=False,
                        customer_name=order.customer.name if order.customer else None,
                    )
                    affected_orders.append(aff_ord)

                    if order.assigned_vehicle:
                        v = order.assigned_vehicle
                        if not any(av.vehicle_id == v.id for av in affected_vehicles):
                            affected_vehicles.append(
                                AffectedVehicleSummary(
                                    vehicle_id=v.id,
                                    vehicle_code=v.vehicle_code,
                                    registration_number=v.registration_number,
                                    status=v.status,
                                    current_load_kg=v.current_load_kg or 0.0,
                                    impact_category="INDIRECT",
                                    severity=disruption.severity,
                                    estimated_delay_minutes=delay_mins,
                                )
                            )

        # 3. WAREHOUSE_SHUTDOWN
        elif d_type == DisruptionType.WAREHOUSE_SHUTDOWN.value:
            warehouse = None
            if disruption.affected_warehouse_id:
                warehouse = self.db.get(Warehouse, disruption.affected_warehouse_id)

            if warehouse:
                warehouses_count = 1
                delay_mins = float(params.get("delay_minutes", 180.0))
                total_delay_minutes += delay_mins

                # Find all pending or active orders originating from or associated with this warehouse
                wh_orders = self.db.scalars(
                    select(Order).where(
                        Order.warehouse_id == warehouse.id,
                        Order.status.in_([
                            OrderStatus.CREATED.value,
                            OrderStatus.CONFIRMED.value,
                            OrderStatus.PROCESSING.value,
                            OrderStatus.READY_FOR_DISPATCH.value,
                        ]),
                    )
                ).all()

                for order in wh_orders:
                    is_urgent = (order.priority == OrderPriority.URGENT.value)
                    is_at_risk = True  # Shutdown warehouse immediately puts orders at risk
                    aff_ord = AffectedOrderSummary(
                        order_id=order.id,
                        order_number=order.order_number,
                        status=order.status,
                        priority=order.priority,
                        sla_hours=None,
                        expected_delivery_at=order.expected_delivery_at,
                        estimated_delay_minutes=delay_mins,
                        is_at_risk=is_at_risk,
                        is_overdue=False,
                        customer_name=order.customer.name if order.customer else None,
                    )
                    affected_orders.append(aff_ord)

                    risk_level = "CRITICAL" if is_urgent else "HIGH"
                    at_risk_orders.append(
                        AtRiskOrderSummary(
                            order_id=order.id,
                            order_number=order.order_number,
                            status=order.status,
                            priority=order.priority,
                            expected_delivery_at=order.expected_delivery_at,
                            estimated_delay_minutes=delay_mins,
                            risk_level=risk_level,
                        )
                    )

        # 4. DEMAND_SURGE
        elif d_type == DisruptionType.DEMAND_SURGE.value:
            if disruption.affected_warehouse_id:
                warehouse = self.db.get(Warehouse, disruption.affected_warehouse_id)
                if warehouse:
                    warehouses_count = 1

            surge_delay = float(params.get("delay_minutes", 60.0))
            total_delay_minutes += surge_delay

            # Any pending orders in the affected area/warehouse
            query = select(Order).where(
                Order.status.in_([
                    OrderStatus.CREATED.value,
                    OrderStatus.CONFIRMED.value,
                    OrderStatus.PROCESSING.value,
                ])
            )
            if disruption.affected_warehouse_id:
                query = query.where(Order.warehouse_id == disruption.affected_warehouse_id)
            pending_orders = self.db.scalars(query).all()

            for order in pending_orders:
                affected_orders.append(
                    AffectedOrderSummary(
                        order_id=order.id,
                        order_number=order.order_number,
                        status=order.status,
                        priority=order.priority,
                        sla_hours=None,
                        expected_delivery_at=order.expected_delivery_at,
                        estimated_delay_minutes=surge_delay,
                        is_at_risk=(order.priority == OrderPriority.URGENT.value),
                        is_overdue=False,
                        customer_name=order.customer.name if order.customer else None,
                    )
                )

        # 5. DELIVERY_DELAY
        elif d_type == DisruptionType.DELIVERY_DELAY.value:
            order = None
            if disruption.affected_order_id:
                order = self.db.get(Order, disruption.affected_order_id)

            if order:
                delay_mins = float(params.get("delay_minutes", 60.0))
                total_delay_minutes += delay_mins
                is_urgent = (order.priority == OrderPriority.URGENT.value)
                is_overdue = False
                is_at_risk = True

                if order.expected_delivery_at:
                    order_exp = order.expected_delivery_at
                    if order_exp.tzinfo is None:
                        order_exp = order_exp.replace(tzinfo=timezone.utc)
                    if order_exp < now:
                        is_overdue = True

                aff_ord = AffectedOrderSummary(
                    order_id=order.id,
                    order_number=order.order_number,
                    status=order.status,
                    priority=order.priority,
                    sla_hours=None,
                    expected_delivery_at=order.expected_delivery_at,
                    estimated_delay_minutes=delay_mins,
                    is_at_risk=is_at_risk,
                    is_overdue=is_overdue,
                    customer_name=order.customer.name if order.customer else None,
                )
                affected_orders.append(aff_ord)

                at_risk_orders.append(
                    AtRiskOrderSummary(
                        order_id=order.id,
                        order_number=order.order_number,
                        status=order.status,
                        priority=order.priority,
                        expected_delivery_at=order.expected_delivery_at,
                        estimated_delay_minutes=delay_mins,
                        risk_level="CRITICAL" if (is_urgent or is_overdue) else "HIGH",
                    )
                )

                if order.assigned_vehicle:
                    v = order.assigned_vehicle
                    affected_vehicles.append(
                        AffectedVehicleSummary(
                            vehicle_id=v.id,
                            vehicle_code=v.vehicle_code,
                            registration_number=v.registration_number,
                            status=v.status,
                            current_load_kg=v.current_load_kg or 0.0,
                            impact_category="DIRECT",
                            severity=disruption.severity,
                            estimated_delay_minutes=delay_mins,
                        )
                    )

        # Build analysis report
        urgent_orders_count = sum(1 for o in affected_orders if o.priority == OrderPriority.URGENT.value)
        overdue_orders_count = sum(1 for o in affected_orders if o.is_overdue)
        at_risk_orders_count = len(at_risk_orders)

        report = DisruptionAnalysisReport(
            disruption_id=disruption.id,
            disruption_code=disruption.disruption_code,
            disruption_type=disruption.disruption_type,
            severity=disruption.severity,
            status=disruption.status,
            affected_vehicles_count=len(affected_vehicles),
            affected_orders_count=len(affected_orders),
            urgent_orders_count=urgent_orders_count,
            overdue_orders_count=overdue_orders_count,
            at_risk_orders_count=at_risk_orders_count,
            affected_warehouses_count=warehouses_count,
            affected_network_edges_count=network_edges_count,
            total_estimated_delay_minutes=total_delay_minutes,
            affected_vehicles=affected_vehicles,
            affected_orders=affected_orders,
            at_risk_orders=at_risk_orders,
            analyzed_at=now,
        )

        if persist_impacts:
            self._persist_impact_records(disruption, report)

        return report

    def _persist_impact_records(self, disruption: Disruption, report: DisruptionAnalysisReport) -> None:
        """Saves or updates individual DisruptionImpact rows in the database."""
        # Remove existing impacts for clean re-analysis snapshot
        existing_impacts = self.db.scalars(
            select(DisruptionImpact).where(DisruptionImpact.disruption_id == disruption.id)
        ).all()
        for imp in existing_impacts:
            self.db.delete(imp)
        self.db.flush()

        # Vehicles
        for v in report.affected_vehicles:
            imp = DisruptionImpact(
                disruption_id=disruption.id,
                affected_resource_type=AffectedResourceType.VEHICLE.value,
                affected_resource_id=v.vehicle_id,
                impact_category=v.impact_category,
                severity=v.severity,
                estimated_delay_minutes=v.estimated_delay_minutes,
                impact_details={
                    "vehicle_code": v.vehicle_code,
                    "status": v.status,
                    "current_load_kg": v.current_load_kg,
                },
            )
            self.db.add(imp)

        # Orders
        for o in report.affected_orders:
            imp = DisruptionImpact(
                disruption_id=disruption.id,
                affected_resource_type=AffectedResourceType.ORDER.value,
                affected_resource_id=o.order_id,
                impact_category="DIRECT" if o.is_at_risk else "INDIRECT",
                severity=disruption.severity,
                estimated_delay_minutes=o.estimated_delay_minutes,
                impact_details={
                    "order_number": o.order_number,
                    "priority": o.priority,
                    "is_at_risk": o.is_at_risk,
                    "is_overdue": o.is_overdue,
                },
            )
            self.db.add(imp)

        # Warehouse
        if disruption.affected_warehouse_id:
            imp = DisruptionImpact(
                disruption_id=disruption.id,
                affected_resource_type=AffectedResourceType.WAREHOUSE.value,
                affected_resource_id=disruption.affected_warehouse_id,
                impact_category="DIRECT",
                severity=disruption.severity,
                estimated_delay_minutes=report.total_estimated_delay_minutes,
                impact_details={"warehouse_id": disruption.affected_warehouse_id},
            )
            self.db.add(imp)

        # Network Edge
        if disruption.affected_network_edge_id:
            imp = DisruptionImpact(
                disruption_id=disruption.id,
                affected_resource_type=AffectedResourceType.NETWORK_EDGE.value,
                affected_resource_id=disruption.affected_network_edge_id,
                impact_category="DIRECT",
                severity=disruption.severity,
                estimated_delay_minutes=report.total_estimated_delay_minutes,
                impact_details={"network_edge_id": disruption.affected_network_edge_id},
            )
            self.db.add(imp)

        self.db.flush()
