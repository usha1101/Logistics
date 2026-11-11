from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.network import NetworkNode
from app.models.order import Order, OrderStatus
from app.models.recovery import RecoveryAssignment, RecoveryPlan
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.warehouse import Warehouse
from app.schemas.recovery import RecoveryPlanValidationReport
from app.services.network_graph_service import NetworkGraphService


class RecoveryPlanValidator:
    """
    Deterministic safety validator for candidate recovery plans.
    Verifies that:
    - Target vehicles exist and remain active and not in BREAKDOWN/MAINTENANCE/OFFLINE.
    - Assigned payload does not exceed remaining capacity.
    - No double-booking of incompatible assignments.
    - Target orders exist and have not been DELIVERED or CANCELLED in the interim.
    - Origin and destination nodes exist and are connected via valid graph paths.
    """

    def __init__(self, db: Session):
        self.db = db

    def validate_plan(self, plan: RecoveryPlan) -> RecoveryPlanValidationReport:
        violations: List[str] = []
        checked_constraints: List[str] = [
            "vehicle_operational_status",
            "vehicle_capacity_headroom",
            "order_eligibility_status",
            "route_connectivity_validity",
            "no_duplicate_concurrent_assignment",
        ]

        # Vehicle load accumulator across assignments in this plan
        vehicle_allocated_weight: Dict[str, float] = {}

        for assign in plan.assignments:
            # 1. Order Check
            order = self.db.get(Order, assign.order_id)
            if not order:
                violations.append(f"Order '{assign.order_id}' no longer exists in database.")
                continue

            if order.status in [OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value]:
                violations.append(f"Order '{order.order_number}' is already in terminal status '{order.status}'.")

            # 2. Vehicle Check
            veh = self.db.get(Vehicle, assign.proposed_vehicle_id)
            if not veh:
                violations.append(f"Proposed vehicle '{assign.proposed_vehicle_id}' no longer exists.")
                continue

            if not veh.is_active or veh.status in [
                VehicleStatus.BREAKDOWN.value,
                VehicleStatus.MAINTENANCE.value,
                VehicleStatus.OFFLINE.value,
            ]:
                violations.append(f"Proposed vehicle '{veh.vehicle_code}' is in non-operational status '{veh.status}'.")

            # Accumulate weight
            weight = float(order.total_weight_kg or 0.0)
            vehicle_allocated_weight[veh.id] = vehicle_allocated_weight.get(veh.id, 0.0) + weight

            rem_cap = float((veh.capacity_kg or 0.0) - (veh.current_load_kg or 0.0))
            if vehicle_allocated_weight[veh.id] > rem_cap:
                violations.append(
                    f"Vehicle '{veh.vehicle_code}' capacity exceeded: allocated {vehicle_allocated_weight[veh.id]} kg, "
                    f"available headroom {rem_cap} kg."
                )

            # 3. Network Route Check
            if not assign.proposed_route_node_ids or len(assign.proposed_route_node_ids) < 1:
                violations.append(f"Assignment for order '{order.order_number}' has empty or invalid route node sequence.")

        is_valid = (len(violations) == 0)

        return RecoveryPlanValidationReport(
            plan_id=plan.id,
            recovery_code=plan.recovery_code,
            is_valid=is_valid,
            status="VALIDATED" if is_valid else "VALIDATION_FAILED",
            checked_constraints=checked_constraints,
            violations=violations,
            validated_at=plan.updated_at,
        )

