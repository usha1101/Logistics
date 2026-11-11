import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.order import Order, OrderStatus
from app.models.simulation import SimulationTelemetry
from app.models.vehicle import LocationSource, Vehicle, VehicleLocation, VehicleStatus, VehicleType
from app.schemas.analytics import (
    FleetAnalyticsResponse,
    MetricAvailabilityStatus,
    VehiclePerformanceSummary,
)
from app.services.analytics.filters import apply_date_filter, build_filter_meta


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r * c


def _compute_path_distance(points: List[Tuple[float, float]]) -> Optional[float]:
    if len(points) < 2:
        return None
    total = 0.0
    for idx in range(1, len(points)):
        lat1, lon1 = points[idx - 1]
        lat2, lon2 = points[idx]
        total += _haversine_km(lat1, lon1, lat2, lon2)
    return round(total, 3)


def compute_fleet_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    vehicle_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    status: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> FleetAnalyticsResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    v_stmt = select(Vehicle)
    if vehicle_id:
        v_stmt = v_stmt.where(Vehicle.id == vehicle_id)
    if warehouse_id:
        v_stmt = v_stmt.where(Vehicle.home_warehouse_id == warehouse_id)
    if status:
        v_stmt = v_stmt.where(Vehicle.status == status)

    vehicles: List[Vehicle] = list(db.execute(v_stmt).scalars().all())
    total_vehicles = len(vehicles)

    vehicles_by_status: Dict[str, int] = {s.value: 0 for s in VehicleStatus}
    vehicles_by_type: Dict[str, int] = {t.value: 0 for t in VehicleType}

    total_capacity = 0.0
    total_load = 0.0
    load_utilizations: List[float] = []

    # Assigned orders per vehicle (active/assigned orders)
    order_counts_stmt = (
        select(Order.assigned_vehicle_id, func.count(Order.id))
        .where(
            Order.assigned_vehicle_id.is_not(None),
            Order.status.notin_([OrderStatus.CANCELLED.value]),
        )
        .group_by(Order.assigned_vehicle_id)
    )
    order_counts_stmt = apply_date_filter(order_counts_stmt, Order.created_at, start_date, end_date)
    order_counts_map: Dict[str, int] = {
        row[0]: int(row[1]) for row in db.execute(order_counts_stmt).all() if row[0]
    }

    # Location history / telemetry points per vehicle
    vehicle_Summaries: List[VehiclePerformanceSummary] = []
    valid_distances: List[float] = []

    for v in vehicles:
        st = v.status
        vt = v.vehicle_type
        vehicles_by_status[st] = vehicles_by_status.get(st, 0) + 1
        vehicles_by_type[vt] = vehicles_by_type.get(vt, 0) + 1

        cap = float(v.capacity_kg or 0.0)
        load = float(v.current_load_kg or 0.0)
        total_capacity += cap
        total_load += load
        util_pct = round((load / cap) * 100.0, 2) if cap > 0 else 0.0
        load_utilizations.append(util_pct)

        dist_km: Optional[float] = None
        dist_source = "UNAVAILABLE"

        if simulation_id:
            tel_stmt = (
                select(SimulationTelemetry.latitude, SimulationTelemetry.longitude)
                .where(
                    SimulationTelemetry.simulation_id == simulation_id,
                    SimulationTelemetry.vehicle_id == v.id,
                )
                .order_by(SimulationTelemetry.recorded_at.asc())
            )
            tel_stmt = apply_date_filter(tel_stmt, SimulationTelemetry.recorded_at, start_date, end_date)
            pts = [(float(r[0]), float(r[1])) for r in db.execute(tel_stmt).all()]
            dist_km = _compute_path_distance(pts)
            if dist_km is not None:
                dist_source = "TELEMETRY_SEGMENTS"
        else:
            loc_stmt = (
                select(VehicleLocation.latitude, VehicleLocation.longitude)
                .where(VehicleLocation.vehicle_id == v.id)
                .order_by(VehicleLocation.recorded_at.asc())
            )
            if not include_simulations:
                loc_stmt = loc_stmt.where(VehicleLocation.source != LocationSource.SIMULATION.value)
            loc_stmt = apply_date_filter(loc_stmt, VehicleLocation.recorded_at, start_date, end_date)
            pts = [(float(r[0]), float(r[1])) for r in db.execute(loc_stmt).all()]
            dist_km = _compute_path_distance(pts)
            if dist_km is not None:
                dist_source = "LOCATION_HISTORY_SEGMENTS"
            elif include_simulations:
                tel_stmt = (
                    select(SimulationTelemetry.latitude, SimulationTelemetry.longitude)
                    .where(SimulationTelemetry.vehicle_id == v.id)
                    .order_by(SimulationTelemetry.recorded_at.asc())
                )
                tel_stmt = apply_date_filter(
                    tel_stmt, SimulationTelemetry.recorded_at, start_date, end_date
                )
                t_pts = [(float(r[0]), float(r[1])) for r in db.execute(tel_stmt).all()]
                dist_km = _compute_path_distance(t_pts)
                if dist_km is not None:
                    dist_source = "TELEMETRY_SEGMENTS"

        if dist_km is not None:
            valid_distances.append(dist_km)

        vehicle_Summaries.append(
            VehiclePerformanceSummary(
                vehicle_id=v.id,
                vehicle_code=v.vehicle_code,
                registration_number=v.registration_number,
                vehicle_type=vt,
                status=st,
                capacity_kg=round(cap, 2),
                current_load_kg=round(load, 2),
                load_utilization_percentage=util_pct,
                assigned_orders_count=order_counts_map.get(v.id, 0),
                distance_travelled_km=dist_km,
                distance_data_source=dist_source,
            )
        )

    available_vehicles = vehicles_by_status.get(VehicleStatus.AVAILABLE.value, 0)
    in_transit_vehicles = vehicles_by_status.get(VehicleStatus.IN_TRANSIT.value, 0)
    idle_vehicles = vehicles_by_status.get(VehicleStatus.IDLE.value, 0)
    breakdown_vehicles = vehicles_by_status.get(VehicleStatus.BREAKDOWN.value, 0)
    maintenance_vehicles = vehicles_by_status.get(VehicleStatus.MAINTENANCE.value, 0)
    offline_vehicles = vehicles_by_status.get(VehicleStatus.OFFLINE.value, 0)

    avg_load_util = (
        round(sum(load_utilizations) / len(load_utilizations), 2)
        if load_utilizations
        else 0.0
    )
    fleet_cap_util = (
        round((total_load / total_capacity) * 100.0, 2) if total_capacity > 0 else 0.0
    )
    active_vehicle_util = (
        round((in_transit_vehicles / total_vehicles) * 100.0, 2)
        if total_vehicles > 0
        else 0.0
    )

    total_distance: Optional[float] = (
        round(sum(valid_distances), 3) if valid_distances else None
    )
    avg_distance: Optional[float] = (
        round(sum(valid_distances) / len(valid_distances), 3)
        if valid_distances
        else None
    )

    unavailable_metrics: List[str] = []
    if total_distance is None:
        unavailable_metrics.extend(["total_distance_travelled_km", "average_distance_per_vehicle_km"])

    metric_classifications = {
        "total_vehicles": MetricAvailabilityStatus.ACTUAL.value,
        "fleet_capacity_utilization_percentage": MetricAvailabilityStatus.ACTUAL.value,
        "average_load_utilization_percentage": MetricAvailabilityStatus.ACTUAL.value,
        "active_vehicle_utilization_rate": MetricAvailabilityStatus.ACTUAL.value,
        "total_distance_travelled_km": (
            MetricAvailabilityStatus.SIMULATED.value
            if simulation_id and total_distance is not None
            else (
                MetricAvailabilityStatus.ACTUAL.value
                if total_distance is not None
                else MetricAvailabilityStatus.UNAVAILABLE.value
            )
        ),
    }

    return FleetAnalyticsResponse(
        total_vehicles=total_vehicles,
        available_vehicles=available_vehicles,
        in_transit_vehicles=in_transit_vehicles,
        idle_vehicles=idle_vehicles,
        breakdown_vehicles=breakdown_vehicles,
        maintenance_vehicles=maintenance_vehicles,
        offline_vehicles=offline_vehicles,
        vehicles_by_status=vehicles_by_status,
        vehicles_by_type=vehicles_by_type,
        total_fleet_capacity_kg=round(total_capacity, 2),
        total_current_load_kg=round(total_load, 2),
        average_load_utilization_percentage=avg_load_util,
        fleet_capacity_utilization_percentage=fleet_cap_util,
        active_vehicle_utilization_rate=active_vehicle_util,
        total_distance_travelled_km=total_distance,
        average_distance_per_vehicle_km=avg_distance,
        vehicles=vehicle_Summaries,
        metric_classifications=metric_classifications,
        unavailable_metrics=unavailable_metrics,
        filter_meta=filter_meta,
    )

