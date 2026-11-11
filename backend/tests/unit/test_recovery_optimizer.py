import pytest
from app.models.recovery import OptimizationStrategy
from app.services.recovery.optimizer import (
    AssignmentOptimizationResult,
    solve_vehicle_order_assignment,
)

@pytest.fixture
def sample_candidate_vehicles():
    return [
        {
            "vehicle_id": "v-1",
            "vehicle_code": "KA-01-V1",
            "status": "AVAILABLE",
            "capacity_kg": 1000.0,
            "current_load_kg": 0.0,
            "remaining_capacity_kg": 1000.0,
        },
        {
            "vehicle_id": "v-2",
            "vehicle_code": "KA-01-V2",
            "status": "AVAILABLE",
            "capacity_kg": 500.0,
            "current_load_kg": 0.0,
            "remaining_capacity_kg": 500.0,
        },
    ]

@pytest.fixture
def sample_candidate_orders():
    return [
        {
            "order_id": "ord-1",
            "order_number": "ORD-001",
            "priority": "URGENT",
            "total_weight_kg": 200.0,
            "estimated_distance_km": 15.0,
            "estimated_travel_minutes": 25.0,
            "estimated_delay_minutes": 10.0,
        },
        {
            "order_id": "ord-2",
            "order_number": "ORD-002",
            "priority": "HIGH",
            "total_weight_kg": 300.0,
            "estimated_distance_km": 20.0,
            "estimated_travel_minutes": 35.0,
            "estimated_delay_minutes": 15.0,
        },
        {
            "order_id": "ord-3",
            "order_number": "ORD-003",
            "priority": "NORMAL",
            "total_weight_kg": 400.0,
            "estimated_distance_km": 25.0,
            "estimated_travel_minutes": 45.0,
            "estimated_delay_minutes": 20.0,
        },
    ]

class TestRecoveryOptimizer:
    def test_single_vehicle_sufficient_capacity(self, sample_candidate_orders):
        vehicles = [
            {
                "vehicle_id": "v-large",
                "vehicle_code": "KA-01-V-LARGE",
                "status": "AVAILABLE",
                "capacity_kg": 2000.0,
                "current_load_kg": 0.0,
                "remaining_capacity_kg": 2000.0,
            }
        ]
        result = solve_vehicle_order_assignment(
            orders=sample_candidate_orders,
            candidate_vehicles=vehicles,
        )
        assert result.is_feasible is True
        assert len(result.assignments) == 3
        assert len(result.unassigned_order_ids) == 0
        assert result.metadata["assigned_orders"] == 3

    def test_capacity_constraint_enforcement(self):
        # 1 vehicle with 400kg capacity, 2 orders of 250kg each -> only 1 fits
        vehicles = [
            {
                "vehicle_id": "v-small",
                "vehicle_code": "KA-01-SMALL",
                "status": "AVAILABLE",
                "capacity_kg": 400.0,
                "current_load_kg": 0.0,
                "remaining_capacity_kg": 400.0,
            }
        ]
        orders = [
            {
                "order_id": "ord-heavy-1",
                "order_number": "ORD-H1",
                "priority": "URGENT",
                "total_weight_kg": 250.0,
                "estimated_distance_km": 10.0,
                "estimated_travel_minutes": 20.0,
                "estimated_delay_minutes": 15.0,
            },
            {
                "order_id": "ord-heavy-2",
                "order_number": "ORD-H2",
                "priority": "LOW",
                "total_weight_kg": 250.0,
                "estimated_distance_km": 10.0,
                "estimated_travel_minutes": 20.0,
                "estimated_delay_minutes": 15.0,
            },
        ]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles)
        assert result.is_feasible is True
        assert len(result.assignments) == 1
        # URGENT order should be chosen over LOW priority
        assigned_order_id = result.assignments[0]["order"]["order_id"]
        assert assigned_order_id == "ord-heavy-1"
        assert result.unassigned_order_ids == ["ord-heavy-2"]

    def test_exclude_breakdown_maintenance_offline_vehicles(self):
        vehicles = [
            {"vehicle_id": "v-1", "vehicle_code": "V1", "status": "BREAKDOWN", "capacity_kg": 1000.0, "current_load_kg": 0.0, "remaining_capacity_kg": 1000.0},
            {"vehicle_id": "v-2", "vehicle_code": "V2", "status": "MAINTENANCE", "capacity_kg": 1000.0, "current_load_kg": 0.0, "remaining_capacity_kg": 1000.0},
            {"vehicle_id": "v-3", "vehicle_code": "V3", "status": "OFFLINE", "capacity_kg": 1000.0, "current_load_kg": 0.0, "remaining_capacity_kg": 1000.0},
            {"vehicle_id": "v-4", "vehicle_code": "V4", "status": "AVAILABLE", "capacity_kg": 1000.0, "current_load_kg": 0.0, "remaining_capacity_kg": 1000.0},
        ]
        orders = [
            {"order_id": "ord-1", "order_number": "ORD-1", "priority": "HIGH", "total_weight_kg": 100.0}
        ]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles)
        assert result.is_feasible is True
        assert len(result.assignments) == 1
        assert result.assignments[0]["vehicle"]["vehicle_id"] == "v-4"

    def test_existing_load_reduces_headroom(self):
        vehicles = [
            {
                "vehicle_id": "v-loaded",
                "vehicle_code": "V-LOADED",
                "status": "AVAILABLE",
                "capacity_kg": 1000.0,
                "current_load_kg": 850.0,
                "remaining_capacity_kg": 150.0,
            }
        ]
        order_fits = {
            "order_id": "ord-fit",
            "order_number": "ORD-FIT",
            "priority": "NORMAL",
            "total_weight_kg": 120.0,
        }
        order_heavy = {
            "order_id": "ord-heavy",
            "order_number": "ORD-HEAVY",
            "priority": "HIGH",
            "total_weight_kg": 200.0,
        }
        result = solve_vehicle_order_assignment(
            orders=[order_heavy, order_fits],
            candidate_vehicles=vehicles,
        )
        assert result.is_feasible is True
        assert len(result.assignments) == 1
        assert result.assignments[0]["order"]["order_id"] == "ord-fit"
        assert "ord-heavy" in result.unassigned_order_ids

    def test_multi_vehicle_distribution(self, sample_candidate_vehicles, sample_candidate_orders):
        result = solve_vehicle_order_assignment(
            orders=sample_candidate_orders,
            candidate_vehicles=sample_candidate_vehicles,
        )
        assert result.is_feasible is True
        assert len(result.unassigned_order_ids) == 0
        assert len(result.assignments) == 3

    def test_empty_vehicles_returns_unassigned(self, sample_candidate_orders):
        result = solve_vehicle_order_assignment(
            orders=sample_candidate_orders,
            candidate_vehicles=[],
        )
        assert result.is_feasible is False
        assert len(result.assignments) == 0
        assert len(result.unassigned_order_ids) == len(sample_candidate_orders)

    def test_empty_orders_returns_empty_assignments(self, sample_candidate_vehicles):
        result = solve_vehicle_order_assignment(
            orders=[],
            candidate_vehicles=sample_candidate_vehicles,
        )
        assert result.is_feasible is False
        assert len(result.assignments) == 0
        assert len(result.unassigned_order_ids) == 0

    def test_allow_partial_false_infeasible_when_capacity_exceeded(self):
        vehicles = [
            {"vehicle_id": "v1", "vehicle_code": "V1", "status": "AVAILABLE", "capacity_kg": 100.0, "current_load_kg": 0.0, "remaining_capacity_kg": 100.0}
        ]
        orders = [
            {"order_id": "o1", "order_number": "O1", "priority": "HIGH", "total_weight_kg": 80.0},
            {"order_id": "o2", "order_number": "O2", "priority": "HIGH", "total_weight_kg": 80.0},
        ]
        result = solve_vehicle_order_assignment(
            orders=orders,
            candidate_vehicles=vehicles,
            allow_partial=False,
        )
        assert result.is_feasible is False
        assert len(result.assignments) == 0
        assert set(result.unassigned_order_ids) == {"o1", "o2"}

    def test_custom_weights_configuration(self, sample_candidate_vehicles, sample_candidate_orders):
        custom_weights = {"distance": 0.5, "travel_time": 0.2, "delay": 0.3}
        result = solve_vehicle_order_assignment(
            orders=sample_candidate_orders,
            candidate_vehicles=sample_candidate_vehicles,
            weights=custom_weights,
        )
        assert result.is_feasible is True
        assert len(result.assignments) == 3

    def test_solver_deterministic_output(self, sample_candidate_vehicles, sample_candidate_orders):
        res1 = solve_vehicle_order_assignment(orders=sample_candidate_orders, candidate_vehicles=sample_candidate_vehicles)
        res2 = solve_vehicle_order_assignment(orders=sample_candidate_orders, candidate_vehicles=sample_candidate_vehicles)
        assert len(res1.assignments) == len(res2.assignments)
        assert res1.unassigned_order_ids == res2.unassigned_order_ids
        assert res1.objective_value == res2.objective_value

    def test_zero_capacity_vehicle_excluded(self):
        vehicles = [
            {"vehicle_id": "v0", "vehicle_code": "V0", "status": "AVAILABLE", "capacity_kg": 0.0, "current_load_kg": 0.0, "remaining_capacity_kg": 0.0}
        ]
        orders = [{"order_id": "o1", "order_number": "O1", "priority": "NORMAL", "total_weight_kg": 10.0}]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles)
        assert result.is_feasible is True
        assert len(result.assignments) == 0
        assert "o1" in result.unassigned_order_ids

    def test_all_priority_multipliers(self):
        vehicles = [
            {"vehicle_id": f"v-{i}", "vehicle_code": f"V{i}", "status": "AVAILABLE", "capacity_kg": 500.0, "current_load_kg": 0.0, "remaining_capacity_kg": 500.0}
            for i in range(4)
        ]
        orders = [
            {"order_id": "o-crit", "order_number": "O-CRIT", "priority": "URGENT", "total_weight_kg": 50.0},
            {"order_id": "o-high", "order_number": "O-HIGH", "priority": "HIGH", "total_weight_kg": 50.0},
            {"order_id": "o-norm", "order_number": "O-NORM", "priority": "NORMAL", "total_weight_kg": 50.0},
            {"order_id": "o-low", "order_number": "O-LOW", "priority": "LOW", "total_weight_kg": 50.0},
        ]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles)
        assert result.is_feasible is True
        assert len(result.assignments) == 4
        assert len(result.unassigned_order_ids) == 0

    def test_heavy_batch_scaling(self):
        # 10 vehicles, 25 orders
        vehicles = [
            {"vehicle_id": f"v-{i}", "vehicle_code": f"V{i}", "status": "AVAILABLE", "capacity_kg": 500.0, "current_load_kg": 0.0, "remaining_capacity_kg": 500.0}
            for i in range(10)
        ]
        orders = [
            {"order_id": f"o-{i}", "order_number": f"ORD-{i}", "priority": "NORMAL", "total_weight_kg": 50.0}
            for i in range(25)
        ]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles)
        assert result.is_feasible is True
        assert len(result.assignments) == 25
        assert len(result.unassigned_order_ids) == 0

    def test_single_order_too_heavy_for_any_vehicle(self):
        vehicles = [
            {"vehicle_id": "v1", "vehicle_code": "V1", "status": "AVAILABLE", "capacity_kg": 100.0, "current_load_kg": 0.0, "remaining_capacity_kg": 100.0},
            {"vehicle_id": "v2", "vehicle_code": "V2", "status": "AVAILABLE", "capacity_kg": 200.0, "current_load_kg": 0.0, "remaining_capacity_kg": 200.0},
        ]
        orders = [
            {"order_id": "heavy", "order_number": "HEAVY", "priority": "URGENT", "total_weight_kg": 500.0}
        ]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles)
        assert result.is_feasible is True
        assert len(result.assignments) == 0
        assert result.unassigned_order_ids == ["heavy"]

    def test_multi_attribute_cost_minimization(self):
        # Two vehicles with same capacity, but vehicle 1 has much closer distance and travel time
        vehicles = [
            {"vehicle_id": "v-far", "vehicle_code": "V-FAR", "status": "AVAILABLE", "capacity_kg": 500.0, "current_load_kg": 0.0, "remaining_capacity_kg": 500.0},
            {"vehicle_id": "v-close", "vehicle_code": "V-CLOSE", "status": "AVAILABLE", "capacity_kg": 500.0, "current_load_kg": 0.0, "remaining_capacity_kg": 500.0},
        ]
        # Order specifying distance and travel time per vehicle or general
        orders = [
            {"order_id": "o1", "order_number": "O1", "priority": "NORMAL", "total_weight_kg": 100.0, "estimated_distance_km": 10.0, "estimated_travel_minutes": 20.0}
        ]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles)
        assert result.is_feasible is True
        assert len(result.assignments) == 1

    def test_allow_partial_true_with_mixed_weights(self):
        vehicles = [
            {"vehicle_id": "v1", "vehicle_code": "V1", "status": "AVAILABLE", "capacity_kg": 150.0, "current_load_kg": 0.0, "remaining_capacity_kg": 150.0}
        ]
        orders = [
            {"order_id": "o1", "order_number": "O1", "priority": "URGENT", "total_weight_kg": 100.0},
            {"order_id": "o2", "order_number": "O2", "priority": "LOW", "total_weight_kg": 100.0},
        ]
        result = solve_vehicle_order_assignment(orders=orders, candidate_vehicles=vehicles, allow_partial=True)
        assert result.is_feasible is True
        assert len(result.assignments) == 1
        assert result.assignments[0]["order"]["order_id"] == "o1"
        assert result.unassigned_order_ids == ["o2"]

    def test_metadata_fields_populated(self, sample_candidate_vehicles, sample_candidate_orders):
        result = solve_vehicle_order_assignment(orders=sample_candidate_orders, candidate_vehicles=sample_candidate_vehicles)
        assert "solver_status" in result.metadata
        assert "total_orders" in result.metadata
        assert "assigned_orders" in result.metadata
        assert "unassigned_orders" in result.metadata
        assert "solver_iterations" in result.metadata
