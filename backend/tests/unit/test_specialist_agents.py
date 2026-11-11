import pytest
from app.models.agent import RecommendationValidationStatus
from app.services.agents.coordinator_agent import CoordinatorAgent
from app.services.agents.disruption_analysis_agent import DisruptionAnalysisAgent
from app.services.agents.fleet_intelligence_agent import FleetIntelligenceAgent
from app.services.agents.order_priority_agent import OrderPriorityAgent
from app.services.agents.routing_intelligence_agent import RoutingIntelligenceAgent
from app.services.agents.warehouse_intelligence_agent import WarehouseIntelligenceAgent


def test_disruption_analysis_agent_deterministic():
    agent = DisruptionAnalysisAgent()
    ctx = {
        "disruption": {
            "id": "disr-123",
            "disruption_code": "DISR-DEMO-001",
            "disruption_type": "TRAFFIC_CONGESTION",
            "severity": "HIGH",
            "status": "ACTIVE",
            "impact_records": [{"resource_type": "VEHICLE", "resource_id": "v1"}],
        }
    }
    out = agent.build_deterministic_fallback(ctx, reason="Offline")
    assert out.agent_name == "DISRUPTION_ANALYSIS"
    assert "HIGH" in out.severity_assessment
    assert len(out.recommendations) >= 1
    assert out.confidence_score >= 0.8


def test_fleet_intelligence_agent_deterministic():
    agent = FleetIntelligenceAgent()
    ctx = {
        "disruption": {"affected_vehicle_id": "v-bad"},
        "orders": [{"total_weight_kg": 400.0}],
        "fleet": [
            {"vehicle_id": "v-1", "vehicle_code": "TRK-001", "status": "AVAILABLE", "capacity_kg": 1000.0, "remaining_capacity_kg": 1000.0},
            {"vehicle_id": "v-2", "vehicle_code": "TRK-002", "status": "BREAKDOWN", "capacity_kg": 1500.0},
            {"vehicle_id": "v-3", "vehicle_code": "VAN-003", "status": "AVAILABLE", "capacity_kg": 200.0}, # insufficient capacity
        ],
    }
    out = agent.build_deterministic_fallback(ctx, reason="Offline")
    assert out.agent_name == "FLEET_INTELLIGENCE"
    assert "v-1" in out.available_candidate_vehicle_ids
    assert "v-2" not in out.available_candidate_vehicle_ids # excluded breakdown
    assert "v-3" not in out.available_candidate_vehicle_ids # excluded insufficient
    assert len(out.recommendations) == 1
    assert out.recommendations[0].target_resource_id == "v-1"


def test_routing_intelligence_agent_deterministic():
    agent = RoutingIntelligenceAgent()
    ctx = {
        "routing": {
            "blocked_edge": {"edge_id": "e-1", "source_node_id": "n1", "target_node_id": "n2", "distance_km": 10.0},
            "detour_path": {"path_found": True, "node_ids": ["n1", "n3", "n2"], "total_distance_km": 14.5, "estimated_minutes": 25.0},
        }
    }
    out = agent.build_deterministic_fallback(ctx, reason="Offline")
    assert out.agent_name == "ROUTING_INTELLIGENCE"
    assert out.alternative_path_found is True
    assert len(out.alternative_path_node_ids) == 3
    assert out.distance_km == 14.5
    assert len(out.recommendations) == 1


def test_warehouse_intelligence_agent_deterministic():
    agent = WarehouseIntelligenceAgent()
    ctx = {
        "disruption": {"affected_warehouse_id": "wh-bad"},
        "warehouses": [
            {"warehouse_id": "wh-bad", "warehouse_code": "WH-001", "utilization_pct": 95.0, "available_capacity": 50.0},
            {"warehouse_id": "wh-alt", "warehouse_code": "WH-002", "utilization_pct": 60.0, "available_capacity": 2000.0},
        ],
    }
    out = agent.build_deterministic_fallback(ctx, reason="Offline")
    assert out.agent_name == "WAREHOUSE_INTELLIGENCE"
    assert "wh-alt" in out.alternative_warehouse_candidates
    assert "wh-bad" not in out.alternative_warehouse_candidates
    assert len(out.recommendations) == 1


def test_order_priority_agent_deterministic():
    agent = OrderPriorityAgent()
    ctx = {
        "orders": [
            {"order_id": "ord-1", "order_number": "ORD-001", "priority": "NORMAL", "is_overdue": False},
            {"order_id": "ord-2", "order_number": "ORD-002", "priority": "URGENT", "is_overdue": False},
            {"order_id": "ord-3", "order_number": "ORD-003", "priority": "HIGH", "is_overdue": True},
        ],
    }
    out = agent.build_deterministic_fallback(ctx, reason="Offline")
    assert out.agent_name == "ORDER_PRIORITY"
    assert out.urgent_orders_count == 1
    # URGENT order should rank first
    assert out.ranked_order_ids[0] == "ord-2"
    assert len(out.recommendations) == 1


@pytest.mark.anyio
async def test_coordinator_conflict_detection():
    coord = CoordinatorAgent()
    fleet_out = FleetIntelligenceAgent().build_deterministic_fallback({
        "fleet": [{"vehicle_id": "v-1", "vehicle_code": "TRK-001", "status": "AVAILABLE", "capacity_kg": 1000.0}],
        "orders": [],
    }, reason="")
    routing_out = RoutingIntelligenceAgent().build_deterministic_fallback({
        "routing": {
            "blocked_edge": {"edge_id": "e-1"},
            "detour_path": {"path_found": False}, # No detour
        }
    }, reason="")

    specialists = {
        "FLEET_INTELLIGENCE": fleet_out,
        "ROUTING_INTELLIGENCE": routing_out,
    }

    conflicts = coord.detect_conflicts(specialists, {})
    assert len(conflicts) >= 1
    assert conflicts[0].conflict_type == "VEHICLE_ROUTE_UNREACHABLE"

    synthesis = await coord.synthesize(specialists, {}, "DISR-TEST")
    assert len(synthesis.detected_conflicts) >= 1
    # Recommendation should be downgraded to REQUIRES_VALIDATION
    for rec in synthesis.consolidated_recommendations:
        if rec.recommendation_type == "DISPATCH_STANDBY_VEHICLE":
            assert rec.validation_status == RecommendationValidationStatus.REQUIRES_VALIDATION

