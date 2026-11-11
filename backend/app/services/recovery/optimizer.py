import logging
from typing import Any, Dict, List, Optional, Tuple
from ortools.linear_solver import pywraplp

logger = logging.getLogger("recovery_solver")


class AssignmentOptimizationResult:
    def __init__(
        self,
        is_feasible: bool,
        objective_value: float,
        assignments: List[Dict[str, Any]],
        unassigned_order_ids: List[str],
        metadata: Dict[str, Any],
    ):
        self.is_feasible = is_feasible
        self.objective_value = objective_value
        self.assignments = assignments
        self.unassigned_order_ids = unassigned_order_ids
        self.metadata = metadata


def solve_vehicle_order_assignment(
    orders: List[Dict[str, Any]],
    candidate_vehicles: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
    allow_partial: bool = True,
) -> AssignmentOptimizationResult:
    """
    Formulates and solves a Mixed-Integer Linear Program (MILP) using Google OR-Tools CBC solver.

    Decision Variables:
      x[i, j] in {0, 1}: 1 if order i is assigned to vehicle j, 0 otherwise.

    Hard Constraints:
      1. Order Single Assignment: sum_j x[i, j] <= 1 for each order i.
         (or == 1 if allow_partial is False)
      2. Vehicle Capacity: sum_i (weight_i * x[i, j]) <= remaining_capacity_j for each vehicle j.
      3. Exclusion: Non-operational vehicles (BREAKDOWN, MAINTENANCE, OFFLINE) have capacity 0.

    Objective:
      Minimize weighted cost:
      - Travel distance / estimated duration per assignment.
      - Delay penalties weighted by order priority (URGENT > HIGH > NORMAL).
      - Penalty for unassigned orders when partial recovery is enabled.
    """
    solver = pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        logger.warning("OR-Tools CBC solver unavailable, falling back to SCIP or GLOP")
        solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        # Final fallback
        solver = pywraplp.Solver.CreateSolver("GLOP")

    w = weights or {"distance": 0.3, "travel_time": 0.4, "delay": 0.3}

    num_orders = len(orders)
    num_vehicles = len(candidate_vehicles)

    if num_orders == 0 or num_vehicles == 0:
        return AssignmentOptimizationResult(
            is_feasible=False,
            objective_value=0.0,
            assignments=[],
            unassigned_order_ids=[o["order_id"] for o in orders],
            metadata={"reason": "No orders or no vehicles available for assignment"},
        )

    # Variables: x[i][j]
    x = {}
    for i in range(num_orders):
        for j in range(num_vehicles):
            x[i, j] = solver.BoolVar(f"x_{i}_{j}")

    # Constraint 1: Order Assignment (at most 1 vehicle per order)
    for i in range(num_orders):
        if not allow_partial:
            solver.Add(solver.Sum(x[i, j] for j in range(num_vehicles)) == 1)
        else:
            solver.Add(solver.Sum(x[i, j] for j in range(num_vehicles)) <= 1)

    # Constraint 2: Vehicle Capacity Constraints
    for j in range(num_vehicles):
        v = candidate_vehicles[j]
        # Calculate available headroom
        rem_cap = float(v.get("remaining_capacity_kg", v.get("capacity_kg", 0.0) - v.get("current_load_kg", 0.0)))
        status = v.get("status", "AVAILABLE")

        # Hard constraint: non-operational status forces capacity to 0
        if status in ["BREAKDOWN", "MAINTENANCE", "OFFLINE"] or rem_cap <= 0:
            rem_cap = 0.0

        solver.Add(
            solver.Sum(float(orders[i].get("total_weight_kg", 0.0)) * x[i, j] for i in range(num_orders)) <= rem_cap
        )

    # Objective Function
    objective = solver.Objective()

    # Priority penalties for delay & unassigned orders
    priority_multipliers = {
        "URGENT": 5.0,
        "HIGH": 3.0,
        "NORMAL": 1.0,
        "LOW": 0.5,
    }

    for i in range(num_orders):
        order = orders[i]
        prio = order.get("priority", "NORMAL")
        p_mult = priority_multipliers.get(prio, 1.0)
        weight_kg = float(order.get("total_weight_kg", 1.0))

        for j in range(num_vehicles):
            veh = candidate_vehicles[j]

            # Approximate baseline travel cost: distance & travel time
            dist_km = float(order.get("estimated_distance_km", 12.0))
            time_mins = float(order.get("estimated_travel_minutes", 25.0))
            delay_mins = float(order.get("estimated_delay_minutes", 15.0))

            cost_coeff = (
                w.get("distance", 0.3) * dist_km
                + w.get("travel_time", 0.4) * time_mins
                + (w.get("delay", 0.3) * delay_mins * p_mult)
            )

            # Assigning an order saves the unassigned penalty (scaled by priority)
            unassigned_reward = 1000.0 * p_mult
            objective.SetCoefficient(x[i, j], cost_coeff - unassigned_reward)

    objective.SetMinimization()

    status = solver.Solve()

    if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        assignments = []
        assigned_order_indices = set()

        for i in range(num_orders):
            for j in range(num_vehicles):
                if x[i, j].solution_value() > 0.5:
                    assigned_order_indices.add(i)
                    assignments.append({
                        "order": orders[i],
                        "vehicle": candidate_vehicles[j],
                        "assigned_weight_kg": float(orders[i].get("total_weight_kg", 0.0)),
                    })

        unassigned_ids = [
            orders[i]["order_id"]
            for i in range(num_orders)
            if i not in assigned_order_indices
        ]

        return AssignmentOptimizationResult(
            is_feasible=True,
            objective_value=float(solver.Objective().Value()),
            assignments=assignments,
            unassigned_order_ids=unassigned_ids,
            metadata={
                "solver_status": "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE",
                "total_orders": num_orders,
                "assigned_orders": len(assigned_order_indices),
                "unassigned_orders": len(unassigned_ids),
                "solver_iterations": solver.iterations(),
            },
        )
    else:
        return AssignmentOptimizationResult(
            is_feasible=False,
            objective_value=0.0,
            assignments=[],
            unassigned_order_ids=[o["order_id"] for o in orders],
            metadata={"solver_status": "INFEASIBLE_OR_FAILED"},
        )
