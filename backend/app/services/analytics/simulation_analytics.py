from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.disruption import Disruption
from app.models.recovery import RecoveryPlan, RecoveryPlanStatus
from app.models.simulation import (
    Simulation,
    SimulationStatus,
    SimulationTelemetry,
    SimulationVehicleState,
)
from app.schemas.analytics import MetricAvailabilityStatus, SimulationAnalyticsResponse
from app.services.analytics.filters import (
    apply_date_filter,
    build_filter_meta,
    normalize_utc,
)
from app.services.analytics.fleet_analytics import _compute_path_distance


def compute_simulation_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    simulation_id: Optional[str] = None,
    status: Optional[str] = None,
) -> SimulationAnalyticsResponse:
    filter_meta = build_filter_meta(
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
        include_simulations=True,
    )
    if not simulation_id:
        filter_meta.data_scope = "SIMULATED"

    stmt = select(Simulation)
    stmt = apply_date_filter(stmt, Simulation.created_at, start_date, end_date)
    if simulation_id:
        stmt = stmt.where(Simulation.id == simulation_id)
    if status:
        stmt = stmt.where(Simulation.status == status)

    sims: List[Simulation] = list(db.execute(stmt).scalars().all())
    total_sims = len(sims)

    sims_by_status: Dict[str, int] = {s.value: 0 for s in SimulationStatus}
    durations_sec: List[float] = []
    sim_ids = [s.id for s in sims]

    for s in sims:
        sims_by_status[s.status] = sims_by_status.get(s.status, 0) + 1
        st_dt = normalize_utc(s.started_at)
        end_dt = normalize_utc(s.stopped_at)
        if st_dt and end_dt and end_dt >= st_dt:
            durations_sec.append((end_dt - st_dt).total_seconds())

    total_sim_vehicles = 0
    total_sim_distance: Optional[float] = None
    sim_disruptions_count = 0
    sim_plans_count = 0
    sim_recovery_success_rate = 0.0

    if sim_ids:
        total_sim_vehicles = (
            db.scalar(
                select(func.count(SimulationVehicleState.id)).where(
                    SimulationVehicleState.simulation_id.in_(sim_ids)
                )
            )
            or 0
        )

        # Telemetry path distances grouped by (simulation_id, vehicle_id)
        tel_stmt = (
            select(
                SimulationTelemetry.simulation_id,
                SimulationTelemetry.vehicle_id,
                SimulationTelemetry.latitude,
                SimulationTelemetry.longitude,
            )
            .where(SimulationTelemetry.simulation_id.in_(sim_ids))
            .order_by(
                SimulationTelemetry.simulation_id.asc(),
                SimulationTelemetry.vehicle_id.asc(),
                SimulationTelemetry.recorded_at.asc(),
            )
        )
        tel_rows = db.execute(tel_stmt).all()
        grouped_pts: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}
        for r in tel_rows:
            key = (str(r[0]), str(r[1]))
            grouped_pts.setdefault(key, []).append((float(r[2]), float(r[3])))

        path_distances: List[float] = []
        for pts in grouped_pts.values():
            d = _compute_path_distance(pts)
            if d is not None:
                path_distances.append(d)

        if path_distances:
            total_sim_distance = round(sum(path_distances), 3)

        sim_disruptions_count = (
            db.scalar(
                select(func.count(Disruption.id)).where(Disruption.simulation_id.in_(sim_ids))
            )
            or 0
        )

        sim_plans: List[RecoveryPlan] = list(
            db.execute(
                select(RecoveryPlan).where(RecoveryPlan.simulation_id.in_(sim_ids))
            ).scalars().all()
        )
        sim_plans_count = len(sim_plans)
        if sim_plans_count > 0:
            exec_count = sum(
                1 for p in sim_plans if p.status == RecoveryPlanStatus.EXECUTED.value
            )
            sim_recovery_success_rate = round((exec_count / sim_plans_count) * 100.0, 2)

    avg_duration: Optional[float] = (
        round(sum(durations_sec) / len(durations_sec), 2) if durations_sec else None
    )

    unavailable_metrics: List[str] = []
    if total_sim_distance is None:
        unavailable_metrics.append("total_simulated_distance_km")
    if avg_duration is None:
        unavailable_metrics.append("average_simulation_duration_seconds")

    metric_classifications = {
        "total_simulations": MetricAvailabilityStatus.SIMULATED.value,
        "total_simulated_vehicles": MetricAvailabilityStatus.SIMULATED.value,
        "total_simulated_distance_km": (
            MetricAvailabilityStatus.SIMULATED.value
            if total_sim_distance is not None
            else MetricAvailabilityStatus.UNAVAILABLE.value
        ),
        "average_simulation_duration_seconds": (
            MetricAvailabilityStatus.SIMULATED.value
            if avg_duration is not None
            else MetricAvailabilityStatus.UNAVAILABLE.value
        ),
        "simulated_disruptions_count": MetricAvailabilityStatus.SIMULATED.value,
        "simulated_recovery_plans_count": MetricAvailabilityStatus.SIMULATED.value,
        "simulated_recovery_success_rate": MetricAvailabilityStatus.SIMULATED.value,
    }

    return SimulationAnalyticsResponse(
        total_simulations=total_sims,
        running_simulations=sims_by_status.get(SimulationStatus.RUNNING.value, 0),
        paused_simulations=sims_by_status.get(SimulationStatus.PAUSED.value, 0),
        completed_simulations=sims_by_status.get(SimulationStatus.COMPLETED.value, 0),
        failed_simulations=sims_by_status.get(SimulationStatus.FAILED.value, 0),
        cancelled_simulations=sims_by_status.get(SimulationStatus.STOPPED.value, 0),
        simulations_by_status=sims_by_status,
        total_simulated_vehicles=total_sim_vehicles,
        total_simulated_distance_km=total_sim_distance,
        average_simulation_duration_seconds=avg_duration,
        simulated_disruptions_count=sim_disruptions_count,
        simulated_recovery_plans_count=sim_plans_count,
        simulated_recovery_success_rate=sim_recovery_success_rate,
        metric_classifications=metric_classifications,
        unavailable_metrics=unavailable_metrics,
        filter_meta=filter_meta,
    )

