import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.order import Order, OrderAssignmentHistory, OrderStatus, OrderStatusHistory
from app.models.recovery import (
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryAuditLog,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.models.simulation import SimulationVehicleState, SimulationVehicleStatus
from app.models.vehicle import Vehicle, VehicleStatus
from app.services.recovery.exceptions import (
    InvalidPlanStatusTransitionError,
    PlanValidationFailedError,
    RecoveryExecutionError,
    StalePlanStateError,
)
from app.services.recovery.validator import RecoveryPlanValidator
from app.services.simulation.manager import ws_manager

logger = logging.getLogger("recovery_executor")


class RecoveryPlanExecutor:
    """
    Executes an APPROVED recovery plan within an atomic database transaction.
    - Strictly obeys simulation vs operational isolation:
      * If simulation_id is present: updates simulation-scoped vehicle states and preserves production tables.
      * If operational: reassigns orders, updates vehicle loads, and generates audit logs.
    """

    def __init__(self, db: Session):
        self.db = db
        self.validator = RecoveryPlanValidator(db)

    def execute_plan(self, plan: RecoveryPlan, user_id: Optional[str] = None) -> RecoveryPlan:
        if plan.status != RecoveryPlanStatus.APPROVED.value:
            raise InvalidPlanStatusTransitionError(
                f"Cannot execute plan in status '{plan.status}'. Plan must be APPROVED first."
            )

        # 1. Pre-Execution Revalidation against live DB state
        val_report = self.validator.validate_plan(plan)
        if not val_report.is_valid:
            plan.status = RecoveryPlanStatus.VALIDATION_FAILED.value
            self.db.commit()
            raise StalePlanStateError(
                f"Live database state changed since approval. Violations: {'; '.join(val_report.violations)}"
            )

        now = datetime.now(timezone.utc)
        plan.status = RecoveryPlanStatus.EXECUTING.value
        self._record_audit_log(plan, "EXECUTION_STARTED", RecoveryPlanStatus.APPROVED.value, plan.status, user_id)
        self.db.flush()
        self._broadcast(plan, "RECOVERY_EXECUTION_STARTED", {})

        is_simulation = bool(plan.simulation_id)
        executed_actions_count = 0

        try:
            for assign in plan.assignments:
                order = self.db.get(Order, assign.order_id)
                new_veh = self.db.get(Vehicle, assign.proposed_vehicle_id)

                if is_simulation:
                    # SIMULATION SCOPED: Update simulation-scoped state ONLY
                    sim_state = self.db.query(SimulationVehicleState).filter_by(
                        simulation_id=plan.simulation_id,
                        vehicle_id=assign.proposed_vehicle_id,
                    ).first()
                    if sim_state:
                        sim_state.status = SimulationVehicleStatus.EN_ROUTE.value
                        sim_state.route_node_ids = assign.proposed_route_node_ids
                        self.db.flush()

                    action = RecoveryAction(
                        recovery_plan_id=plan.id,
                        action_type="SIMULATION_VEHICLE_DISPATCH",
                        target_resource_type="SIMULATION_VEHICLE",
                        target_resource_id=assign.proposed_vehicle_id,
                        action_payload={"route_nodes": assign.proposed_route_node_ids},
                        status=RecoveryActionStatus.EXECUTED.value,
                        execution_result={"simulated": True},
                        executed_at=now,
                    )
                    self.db.add(action)
                    executed_actions_count += 1

                else:
                    # OPERATIONAL SCOPED: Real assignment and vehicle load update
                    prev_vid = order.assigned_vehicle_id
                    weight = float(order.total_weight_kg or 0.0)

                    # Deduct from previous vehicle if applicable
                    if prev_vid:
                        old_veh = self.db.get(Vehicle, prev_vid)
                        if old_veh:
                            old_veh.current_load_kg = max(0.0, float(old_veh.current_load_kg or 0.0) - weight)
                            self.db.flush()

                    # Assign new vehicle
                    order.assigned_vehicle_id = new_veh.id
                    if order.status == OrderStatus.CREATED.value:
                        order.status = OrderStatus.CONFIRMED.value

                    # Increase new vehicle load
                    new_veh.current_load_kg = float(new_veh.current_load_kg or 0.0) + weight

                    # Audit Assignment History
                    assign_hist = OrderAssignmentHistory(
                        order_id=order.id,
                        previous_vehicle_id=prev_vid,
                        new_vehicle_id=new_veh.id,
                        assigned_by_user_id=user_id,
                        reason=assign.assignment_reason or f"Recovery Plan {plan.recovery_code} executed",
                    )
                    self.db.add(assign_hist)

                    action = RecoveryAction(
                        recovery_plan_id=plan.id,
                        action_type="REASSIGN_ORDER_VEHICLE",
                        target_resource_type="ORDER",
                        target_resource_id=order.id,
                        action_payload={"order_id": order.id, "new_vehicle_id": new_veh.id, "weight_kg": weight},
                        status=RecoveryActionStatus.EXECUTED.value,
                        execution_result={"success": True},
                        executed_at=now,
                    )
                    self.db.add(action)
                    executed_actions_count += 1

            # 2. Finalize Plan Success
            plan.status = RecoveryPlanStatus.EXECUTED.value
            plan.executed_at = now
            self._record_audit_log(plan, "PLAN_EXECUTED", RecoveryPlanStatus.EXECUTING.value, plan.status, user_id)

            self.db.commit()
            self.db.refresh(plan)
            self._broadcast(plan, "RECOVERY_EXECUTION_COMPLETED", {"actions_count": executed_actions_count})
            return plan

        except Exception as e:
            self.db.rollback()
            logger.error(f"Recovery execution transaction aborted: {e}")

            # Re-fetch and mark FAILED in a clean transaction
            failed_plan = self.db.get(RecoveryPlan, plan.id)
            if failed_plan:
                failed_plan.status = RecoveryPlanStatus.FAILED.value
                self._record_audit_log(failed_plan, "EXECUTION_FAILED", RecoveryPlanStatus.EXECUTING.value, failed_plan.status, user_id, {"error": str(e)})
                self.db.commit()

            self._broadcast(plan, "RECOVERY_EXECUTION_FAILED", {"error": str(e)})
            raise RecoveryExecutionError(f"Recovery execution failed: {e}")

    def _record_audit_log(
        self,
        plan: RecoveryPlan,
        action: str,
        prev_status: Optional[str],
        new_status: str,
        user_id: Optional[str],
        details: Optional[Dict[str, Any]] = None,
    ) -> RecoveryAuditLog:
        log = RecoveryAuditLog(
            recovery_plan_id=plan.id,
            action=action,
            previous_status=prev_status,
            new_status=new_status,
            performed_by_user_id=user_id,
            details=details or {},
        )
        self.db.add(log)
        return log

    def _broadcast(self, plan: RecoveryPlan, event_name: str, data: Dict[str, Any]) -> None:
        if not plan.simulation_id:
            return

        message = {
            "type": "RECOVERY_UPDATE",
            "event": event_name,
            "recovery_plan_id": plan.id,
            "disruption_id": plan.disruption_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                asyncio.create_task(ws_manager.broadcast(plan.simulation_id, message))
        except Exception as e:
            logger.warning(f"Failed to broadcast recovery WebSocket message: {e}")

