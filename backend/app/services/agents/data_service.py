from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.disruption import Disruption, DisruptionImpact
from app.models.network import NetworkEdge, NetworkNode
from app.models.order import Order, OrderStatus
from app.models.simulation import SimulationVehicleState
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.warehouse import InventoryItem, Warehouse, WarehouseStatus
from app.services.network_graph_service import NetworkGraphService


class OperationalDataService:
    """
    Controlled, read-only data service that extracts verified operational snapshots
    from the database for specialist agents.
    Strictly forbids SQL generation, arbitrary tables, or database mutations.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_disruption_context(self, disruption_id: str) -> Dict[str, Any]:
        d = self.db.get(Disruption, disruption_id)
        if not d:
            return {}

        impacts = self.db.scalars(
            select(DisruptionImpact).where(DisruptionImpact.disruption_id == disruption_id)
        ).all()

        return {
            "id": d.id,
            "disruption_code": d.disruption_code,
            "disruption_type": d.disruption_type,
            "severity": d.severity,
            "status": d.status,
            "title": d.title,
            "description": d.description,
            "simulation_id": d.simulation_id,
            "affected_vehicle_id": d.affected_vehicle_id,
            "affected_warehouse_id": d.affected_warehouse_id,
            "affected_network_edge_id": d.affected_network_edge_id,
            "affected_order_id": d.affected_order_id,
            "location": {"latitude": d.location_latitude, "longitude": d.location_longitude},
            "parameters": d.parameters or {},
            "start_time": d.start_time.isoformat() if d.start_time else None,
            "expected_end_time": d.expected_end_time.isoformat() if d.expected_end_time else None,
            "impact_records": [
                {
                    "resource_type": imp.affected_resource_type,
                    "resource_id": imp.affected_resource_id,
                    "severity": imp.severity,
                    "category": imp.impact_category,
                    "estimated_delay_minutes": imp.estimated_delay_minutes,
                    "details": imp.impact_details,
                }
                for imp in impacts
            ],
        }

    def get_fleet_context(self, required_min_capacity_kg: float = 0.0) -> List[Dict[str, Any]]:
        vehicles = self.db.scalars(
            select(Vehicle).where(Vehicle.is_active == True)
        ).all()

        results = []
        for v in vehicles:
            results.append({
                "vehicle_id": v.id,
                "vehicle_code": v.vehicle_code,
                "registration_number": v.registration_number,
                "vehicle_type": v.vehicle_type,
                "status": v.status,
                "capacity_kg": v.capacity_kg,
                "current_load_kg": v.current_load_kg,
                "remaining_capacity_kg": max(0.0, (v.capacity_kg or 0.0) - (v.current_load_kg or 0.0)),
                "is_candidate": (
                    v.status in [VehicleStatus.AVAILABLE.value, VehicleStatus.IDLE.value]
                    and (v.capacity_kg or 0.0) >= required_min_capacity_kg
                ),
                "home_warehouse_id": v.home_warehouse_id,
                "location": {"latitude": v.current_latitude, "longitude": v.current_longitude},
            })
        return results

    def get_routing_context(
        self,
        origin_node_id: Optional[str] = None,
        destination_node_id: Optional[str] = None,
        blocked_edge_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Provides verified network graph metrics and calculates detour paths if endpoints are given."""
        edge_info = None
        if blocked_edge_id:
            edge = self.db.get(NetworkEdge, blocked_edge_id)
            if edge:
                edge_info = {
                    "edge_id": edge.id,
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "distance_km": edge.distance_km,
                    "road_type": edge.road_type,
                }
                if not origin_node_id:
                    origin_node_id = edge.source_node_id
                if not destination_node_id:
                    destination_node_id = edge.target_node_id

        path_result = None
        if origin_node_id and destination_node_id and origin_node_id != destination_node_id:
            try:
                nodes = list(self.db.scalars(select(NetworkNode)).all())
                edges = list(self.db.scalars(select(NetworkEdge)).all())
                res = NetworkGraphService.calculate_shortest_path(
                    nodes=nodes,
                    edges=edges,
                    origin_node_id=origin_node_id,
                    destination_node_id=destination_node_id,
                    weight="distance",
                )
                path_result = {
                    "path_found": True,
                    "node_ids": res.ordered_node_ids,
                    "total_distance_km": res.total_distance_km,
                    "estimated_minutes": res.estimated_travel_minutes,
                }
            except Exception as e:
                path_result = {"path_found": False, "error": str(e)}

        return {
            "blocked_edge": edge_info,
            "origin_node_id": origin_node_id,
            "destination_node_id": destination_node_id,
            "detour_path": path_result,
        }

    def get_warehouse_context(self, target_warehouse_id: Optional[str] = None) -> List[Dict[str, Any]]:
        warehouses = self.db.scalars(select(Warehouse)).all()
        results = []
        for w in warehouses:
            stock_items = self.db.scalars(
                select(InventoryItem).where(InventoryItem.warehouse_id == w.id)
            ).all()

            results.append({
                "warehouse_id": w.id,
                "warehouse_code": w.warehouse_code,
                "status": w.status,
                "total_capacity": w.total_capacity,
                "used_capacity": w.used_capacity,
                "available_capacity": max(0.0, (w.total_capacity or 0.0) - (w.used_capacity or 0.0)),
                "utilization_pct": round(((w.used_capacity or 0.0) / w.total_capacity) * 100.0, 2) if w.total_capacity else 0.0,
                "is_target": (w.id == target_warehouse_id),
                "sku_count": len(stock_items),
                "total_quantity_on_hand": sum(item.quantity_on_hand or 0 for item in stock_items),
            })
        return results

    def get_order_context(self, affected_vehicle_id: Optional[str] = None, affected_order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = select(Order)
        if affected_order_id:
            query = query.where(Order.id == affected_order_id)
        elif affected_vehicle_id:
            query = query.where(
                Order.assigned_vehicle_id == affected_vehicle_id,
                Order.status.in_([OrderStatus.READY_FOR_DISPATCH.value, OrderStatus.DISPATCHED.value, OrderStatus.IN_TRANSIT.value]),
            )
        else:
            query = query.where(
                Order.status.in_([OrderStatus.READY_FOR_DISPATCH.value, OrderStatus.DISPATCHED.value, OrderStatus.IN_TRANSIT.value])
            ).limit(20)

        orders = self.db.scalars(query).all()
        now = datetime.now(timezone.utc)
        results = []
        for o in orders:
            exp = o.expected_delivery_at
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            is_overdue = bool(exp and exp < now)

            results.append({
                "order_id": o.id,
                "order_number": o.order_number,
                "priority": o.priority,
                "status": o.status,
                "assigned_vehicle_id": o.assigned_vehicle_id,
                "warehouse_id": o.warehouse_id,
                "total_weight_kg": o.total_weight_kg,
                "expected_delivery_at": exp.isoformat() if exp else None,
                "is_overdue": is_overdue,
                "delivery_address": o.delivery_address,
            })
        return results
