import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
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
from app.models.vehicle import Vehicle
from app.models.network import NetworkEdge
from app.models.order import Order
from app.models.simulation import (
    Simulation,
    SimulationEvent,
    SimulationEventType,
    SimulationVehicleState,
    SimulationVehicleStatus,
)
from app.models.warehouse import Warehouse
from app.schemas.disruption import (
    DisruptionAnalysisReport,
    DisruptionCancelRequest,
    DisruptionCreate,
    DisruptionResolveRequest,
    DisruptionUpdate,
)
from app.services.disruptions.exceptions import (
    DisruptionNotFoundError,
    InvalidDisruptionTransitionError,
    TargetResourceValidationError,
)
from app.services.disruptions.impact_analyzer import DisruptionImpactAnalyzer
from app.services.disruptions.severity import calculate_severity
from app.services.simulation.manager import ws_manager

logger = logging.getLogger("disruption_engine")


class DisruptionEngine:
    """
    Orchestrates deterministic logistics disruption management:
    creation, validation, activation, impact analysis, update, monitoring,
    resolution, cancellation, and WebSocket broadcasts.
    """

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = DisruptionImpactAnalyzer(db)

    # =========================================================================
    # LIFECYCLE: CREATE & VALIDATE
    # =========================================================================

    def create_disruption(
        self,
        payload: DisruptionCreate,
        user_id: Optional[str] = None,
    ) -> Disruption:
        """
        Creates a new disruption record in DETECTED status, validates target resources,
        computes severity deterministically if not provided, analyzes impact, and logs initial event.
        """
        # 1. Validate Target Resources
        self._validate_target_resources(payload)

        # 2. Generate unique code
        code_suffix = uuid.uuid4().hex[:8].upper()
        disruption_code = f"DISR-{payload.disruption_type.value[:4]}-{code_suffix}"

        # 3. Calculate Deterministic Severity if not provided
        res_context = self._get_resource_context(payload)
        severity = payload.severity or calculate_severity(
            payload.disruption_type,
            payload.parameters,
            res_context,
        )

        now = datetime.now(timezone.utc)
        start_time = payload.start_time or now

        disruption = Disruption(
            disruption_code=disruption_code,
            disruption_type=payload.disruption_type.value,
            severity=severity.value if isinstance(severity, DisruptionSeverity) else severity,
            status=DisruptionStatus.DETECTED.value,
            title=payload.title,
            description=payload.description,
            simulation_id=payload.simulation_id,
            affected_vehicle_id=payload.affected_vehicle_id,
            affected_warehouse_id=payload.affected_warehouse_id,
            affected_network_edge_id=payload.affected_network_edge_id,
            affected_order_id=payload.affected_order_id,
            location_latitude=payload.location_latitude,
            location_longitude=payload.location_longitude,
            parameters=payload.parameters or {},
            start_time=start_time,
            expected_end_time=payload.expected_end_time,
            created_by_user_id=user_id,
        )
        self.db.add(disruption)
        self.db.flush()

        # 4. Record Event
        self._record_event(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_CREATED.value,
            previous_status=None,
            new_status=DisruptionStatus.DETECTED.value,
            event_data={
                "code": disruption.disruption_code,
                "type": disruption.disruption_type,
                "severity": disruption.severity,
            },
            user_id=user_id,
        )

        # 5. Automatically perform baseline impact analysis
        self.analyzer.analyze(disruption, persist_impacts=True)

        self.db.commit()
        self.db.refresh(disruption)

        # Broadcast via WebSocket if simulation-scoped
        self._broadcast_event(disruption, "DISRUPTION_DETECTED")

        return disruption

    # =========================================================================
    # LIFECYCLE: ACTIVATE
    # =========================================================================

    def activate_disruption(self, disruption_id: str, user_id: Optional[str] = None) -> Disruption:
        """
        Transitions a disruption from DETECTED -> ACTIVE.
        Applies live effects:
        - If simulation-scoped VEHICLE_BREAKDOWN: sets SimulationVehicleState.status = 'BREAKDOWN'
        - If operational: real vehicles/orders are NOT mutated (isolation rule)
        """
        disruption = self._get_or_404(disruption_id)

        if disruption.status != DisruptionStatus.DETECTED.value:
            raise InvalidDisruptionTransitionError(
                f"Cannot activate disruption in status '{disruption.status}'. Only DETECTED disruptions can be activated."
            )

        prev_status = disruption.status
        disruption.status = DisruptionStatus.ACTIVE.value
        disruption.updated_at = datetime.now(timezone.utc)

        # Simulation vehicle status breakdown handling
        if disruption.simulation_id and disruption.disruption_type == DisruptionType.VEHICLE_BREAKDOWN.value:
            if disruption.affected_vehicle_id:
                sim_vehicle = self.db.scalars(
                    select(SimulationVehicleState).where(
                        SimulationVehicleState.simulation_id == disruption.simulation_id,
                        SimulationVehicleState.vehicle_id == disruption.affected_vehicle_id,
                    )
                ).first()
                if sim_vehicle:
                    sim_vehicle.status = SimulationVehicleStatus.BREAKDOWN.value
                    self.db.flush()

        # Record Event
        self._record_event(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_ACTIVATED.value,
            previous_status=prev_status,
            new_status=DisruptionStatus.ACTIVE.value,
            event_data={"activated_at": disruption.updated_at.isoformat()},
            user_id=user_id,
        )

        # Re-run impact analysis
        self.analyzer.analyze(disruption, persist_impacts=True)

        self.db.commit()
        self.db.refresh(disruption)

        self._broadcast_event(disruption, "DISRUPTION_ACTIVATED")
        return disruption

    # =========================================================================
    # LIFECYCLE: MONITORING
    # =========================================================================

    def set_monitoring(self, disruption_id: str, user_id: Optional[str] = None) -> Disruption:
        """Transitions ACTIVE -> MONITORING."""
        disruption = self._get_or_404(disruption_id)

        if disruption.status != DisruptionStatus.ACTIVE.value:
            raise InvalidDisruptionTransitionError(
                f"Cannot transition disruption in status '{disruption.status}' to MONITORING. Only ACTIVE disruptions can be set to MONITORING."
            )

        prev_status = disruption.status
        disruption.status = DisruptionStatus.MONITORING.value
        disruption.updated_at = datetime.now(timezone.utc)

        self._record_event(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_MONITORING.value,
            previous_status=prev_status,
            new_status=DisruptionStatus.MONITORING.value,
            event_data={"monitoring_started_at": disruption.updated_at.isoformat()},
            user_id=user_id,
        )

        self.db.commit()
        self.db.refresh(disruption)

        self._broadcast_event(disruption, "DISRUPTION_MONITORING")
        return disruption

    # =========================================================================
    # LIFECYCLE: UPDATE
    # =========================================================================

    def update_disruption(
        self,
        disruption_id: str,
        payload: DisruptionUpdate,
        user_id: Optional[str] = None,
    ) -> Disruption:
        disruption = self._get_or_404(disruption_id)

        if disruption.status in [DisruptionStatus.RESOLVED.value, DisruptionStatus.CANCELLED.value]:
            raise InvalidDisruptionTransitionError(
                f"Cannot update disruption in terminal status '{disruption.status}'."
            )

        if payload.title is not None:
            disruption.title = payload.title
        if payload.description is not None:
            disruption.description = payload.description
        if payload.severity is not None:
            disruption.severity = payload.severity.value
        if payload.expected_end_time is not None:
            disruption.expected_end_time = payload.expected_end_time
        if payload.parameters is not None:
            current_params = dict(disruption.parameters or {})
            current_params.update(payload.parameters)
            disruption.parameters = current_params

        disruption.updated_at = datetime.now(timezone.utc)

        self._record_event(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_UPDATED.value,
            previous_status=disruption.status,
            new_status=disruption.status,
            event_data={"updated_fields": payload.model_dump(exclude_unset=True)},
            user_id=user_id,
        )

        # Recompute impact
        self.analyzer.analyze(disruption, persist_impacts=True)

        self.db.commit()
        self.db.refresh(disruption)

        self._broadcast_event(disruption, "DISRUPTION_UPDATED")
        return disruption

    # =========================================================================
    # LIFECYCLE: RESOLVE
    # =========================================================================

    def resolve_disruption(
        self,
        disruption_id: str,
        payload: Optional[DisruptionResolveRequest] = None,
        user_id: Optional[str] = None,
    ) -> Disruption:
        disruption = self._get_or_404(disruption_id)

        if disruption.status not in [DisruptionStatus.ACTIVE.value, DisruptionStatus.MONITORING.value]:
            raise InvalidDisruptionTransitionError(
                f"Cannot resolve disruption in status '{disruption.status}'. Only ACTIVE or MONITORING can be resolved."
            )

        prev_status = disruption.status
        now = datetime.now(timezone.utc)
        disruption.status = DisruptionStatus.RESOLVED.value
        disruption.actual_end_time = (payload.actual_end_time if payload and payload.actual_end_time else now)
        disruption.resolved_by_user_id = user_id
        disruption.updated_at = now

        # Restore simulated vehicle status if breakdown
        if disruption.simulation_id and disruption.disruption_type == DisruptionType.VEHICLE_BREAKDOWN.value:
            if disruption.affected_vehicle_id:
                sim_vehicle = self.db.scalars(
                    select(SimulationVehicleState).where(
                        SimulationVehicleState.simulation_id == disruption.simulation_id,
                        SimulationVehicleState.vehicle_id == disruption.affected_vehicle_id,
                    )
                ).first()
                if sim_vehicle and sim_vehicle.status == SimulationVehicleStatus.BREAKDOWN.value:
                    sim_vehicle.status = SimulationVehicleStatus.EN_ROUTE.value
                    self.db.flush()

        notes = payload.notes if payload else None
        self._record_event(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_RESOLVED.value,
            previous_status=prev_status,
            new_status=DisruptionStatus.RESOLVED.value,
            event_data={"notes": notes, "actual_end_time": disruption.actual_end_time.isoformat()},
            user_id=user_id,
        )

        self.db.commit()
        self.db.refresh(disruption)

        self._broadcast_event(disruption, "DISRUPTION_RESOLVED")
        return disruption

    # =========================================================================
    # LIFECYCLE: CANCEL
    # =========================================================================

    def cancel_disruption(
        self,
        disruption_id: str,
        payload: Optional[DisruptionCancelRequest] = None,
        user_id: Optional[str] = None,
    ) -> Disruption:
        disruption = self._get_or_404(disruption_id)

        if disruption.status in [DisruptionStatus.RESOLVED.value, DisruptionStatus.CANCELLED.value]:
            raise InvalidDisruptionTransitionError(
                f"Cannot cancel disruption in terminal status '{disruption.status}'."
            )

        prev_status = disruption.status
        now = datetime.now(timezone.utc)
        disruption.status = DisruptionStatus.CANCELLED.value
        disruption.updated_at = now

        # Restore simulated vehicle status if needed
        if disruption.simulation_id and disruption.disruption_type == DisruptionType.VEHICLE_BREAKDOWN.value:
            if disruption.affected_vehicle_id:
                sim_vehicle = self.db.scalars(
                    select(SimulationVehicleState).where(
                        SimulationVehicleState.simulation_id == disruption.simulation_id,
                        SimulationVehicleState.vehicle_id == disruption.affected_vehicle_id,
                    )
                ).first()
                if sim_vehicle and sim_vehicle.status == SimulationVehicleStatus.BREAKDOWN.value:
                    sim_vehicle.status = SimulationVehicleStatus.EN_ROUTE.value
                    self.db.flush()

        reason = payload.reason if payload else None
        self._record_event(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_CANCELLED.value,
            previous_status=prev_status,
            new_status=DisruptionStatus.CANCELLED.value,
            event_data={"reason": reason},
            user_id=user_id,
        )

        self.db.commit()
        self.db.refresh(disruption)

        self._broadcast_event(disruption, "DISRUPTION_CANCELLED")
        return disruption

    # =========================================================================
    # IMPACT ANALYSIS ON-DEMAND
    # =========================================================================

    def get_impact_analysis(self, disruption_id: str) -> DisruptionAnalysisReport:
        disruption = self._get_or_404(disruption_id)
        report = self.analyzer.analyze(disruption, persist_impacts=False)

        self._record_event(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_IMPACT_ANALYZED.value,
            previous_status=disruption.status,
            new_status=disruption.status,
            event_data={
                "affected_vehicles_count": report.affected_vehicles_count,
                "affected_orders_count": report.affected_orders_count,
                "at_risk_orders_count": report.at_risk_orders_count,
                "total_estimated_delay_minutes": report.total_estimated_delay_minutes,
            },
        )
        self.db.commit()
        return report

    # =========================================================================
    # HELPERS & VALIDATION
    # =========================================================================

    def _get_or_404(self, disruption_id: str) -> Disruption:
        disruption = self.db.get(Disruption, disruption_id)
        if not disruption:
            raise DisruptionNotFoundError(f"Disruption '{disruption_id}' not found.")
        return disruption

    def _validate_target_resources(self, payload: DisruptionCreate) -> None:
        """Validates that referenced FK targets actually exist in the DB."""
        if payload.simulation_id:
            sim = self.db.get(Simulation, payload.simulation_id)
            if not sim:
                raise TargetResourceValidationError(f"Simulation '{payload.simulation_id}' does not exist.")

        if payload.affected_vehicle_id:
            v = self.db.get(Vehicle, payload.affected_vehicle_id)
            if not v:
                raise TargetResourceValidationError(f"Vehicle '{payload.affected_vehicle_id}' does not exist.")

        if payload.affected_warehouse_id:
            w = self.db.get(Warehouse, payload.affected_warehouse_id)
            if not w:
                raise TargetResourceValidationError(f"Warehouse '{payload.affected_warehouse_id}' does not exist.")

        if payload.affected_network_edge_id:
            edge = self.db.get(NetworkEdge, payload.affected_network_edge_id)
            if not edge:
                raise TargetResourceValidationError(f"Network edge '{payload.affected_network_edge_id}' does not exist.")

        if payload.affected_order_id:
            order = self.db.get(Order, payload.affected_order_id)
            if not order:
                raise TargetResourceValidationError(f"Order '{payload.affected_order_id}' does not exist.")

    def _get_resource_context(self, payload: DisruptionCreate) -> Dict[str, Any]:
        """Gathers context attributes from the DB for deterministic severity calculation."""
        ctx: Dict[str, Any] = {}
        if payload.affected_vehicle_id:
            v = self.db.get(Vehicle, payload.affected_vehicle_id)
            if v:
                ctx["current_load_kg"] = v.current_load_kg or 0.0
                ctx["is_idle"] = (v.status == "AVAILABLE")
                # Check if vehicle carries urgent orders
                has_urgent = self.db.scalar(
                    select(func.count())
                    .select_from(Order)
                    .where(
                        Order.assigned_vehicle_id == v.id,
                        Order.priority == "URGENT",
                    )
                ) or 0
                ctx["has_urgent_orders"] = (has_urgent > 0)
        if payload.affected_warehouse_id:
            w = self.db.get(Warehouse, payload.affected_warehouse_id)
            if w and w.total_capacity and w.total_capacity > 0:
                ctx["capacity_utilization_pct"] = ((w.used_capacity or 0.0) / w.total_capacity) * 100.0
        if payload.affected_order_id:
            o = self.db.get(Order, payload.affected_order_id)
            if o:
                ctx["is_urgent"] = (o.priority == "URGENT")
        return ctx

    def _record_event(
        self,
        disruption_id: str,
        event_type: str,
        previous_status: Optional[str],
        new_status: Optional[str],
        event_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> DisruptionEvent:
        event = DisruptionEvent(
            disruption_id=disruption_id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            event_data=event_data,
            performed_by_user_id=user_id,
        )
        self.db.add(event)
        return event

    def _broadcast_event(self, disruption: Disruption, event_name: str) -> None:
        """Safely fires WebSocket broadcast message if disruption is linked to a simulation."""
        if not disruption.simulation_id:
            return

        message = {
            "type": "DISRUPTION_UPDATE",
            "event": event_name,
            "disruption": {
                "id": disruption.id,
                "disruption_code": disruption.disruption_code,
                "disruption_type": disruption.disruption_type,
                "severity": disruption.severity,
                "status": disruption.status,
                "affected_vehicle_id": disruption.affected_vehicle_id,
                "affected_warehouse_id": disruption.affected_warehouse_id,
                "affected_network_edge_id": disruption.affected_network_edge_id,
                "affected_order_id": disruption.affected_order_id,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                asyncio.create_task(ws_manager.broadcast(disruption.simulation_id, message))
        except Exception as e:
            logger.warning(f"Failed to broadcast disruption WebSocket message: {e}")
