import json
from typing import Any, Dict, List
from app.models.agent import AgentExecutionStatus, RecommendationPriority, RecommendationValidationStatus
from app.services.agents.base_agent import BaseAgent
from app.services.agents.prompts import ROUTING_INTELLIGENCE_PROMPT
from app.services.agents.schemas import (
    BaseAgentRecommendation,
    EvidenceReference,
    RoutingIntelligenceAgentOutput,
)


class RoutingIntelligenceAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="ROUTING_INTELLIGENCE",
            system_prompt=ROUTING_INTELLIGENCE_PROMPT,
            output_schema=RoutingIntelligenceAgentOutput,
        )

    def build_user_prompt(self, operational_context: Dict[str, Any]) -> str:
        routing = operational_context.get("routing", {})
        disr = operational_context.get("disruption", {})
        return f"""Analyze route feasibility and detour paths:
Disruption Context:
{json.dumps(disr, indent=2)}

Routing & Graph Metrics:
{json.dumps(routing, indent=2)}

Evaluate whether blocked edge requires alternate paths, verify detour connectivity, distance and travel time."""

    def build_deterministic_fallback(self, operational_context: Dict[str, Any], reason: str) -> RoutingIntelligenceAgentOutput:
        routing = operational_context.get("routing", {})
        detour = routing.get("detour_path") or {}
        blocked = routing.get("blocked_edge") or {}

        path_found = detour.get("path_found", False)
        node_ids = detour.get("node_ids", [])
        dist = detour.get("total_distance_km")
        mins = detour.get("estimated_minutes")

        ev_refs = []
        recs = []

        if blocked:
            ev_refs.append(
                EvidenceReference(
                    resource_type="NETWORK_EDGE",
                    resource_id=blocked.get("edge_id", "UNKNOWN"),
                    description=f"Blocked edge between node {blocked.get('source_node_id')} and {blocked.get('target_node_id')}",
                    metric_value=blocked.get("distance_km"),
                )
            )

        if path_found and node_ids:
            recs.append(
                BaseAgentRecommendation(
                    recommendation_type="REROUTE_EDGE",
                    priority=RecommendationPriority.HIGH,
                    title="Adopt verified detour corridor",
                    description=f"Reroute transit through bypass sequence ({len(node_ids)} nodes, {dist} km, ~{mins} mins).",
                    target_resource_type="NETWORK_PATH",
                    target_resource_id=" -> ".join(node_ids[:3]) + "...",
                    evidence={"path_nodes": node_ids, "distance_km": dist, "estimated_minutes": mins},
                    validation_status=RecommendationValidationStatus.VALIDATED,
                )
            )

        return RoutingIntelligenceAgentOutput(
            agent_name="ROUTING_INTELLIGENCE",
            execution_status=AgentExecutionStatus.COMPLETED,
            summary=f"Detour path {'verified' if path_found else 'not found'} for disrupted corridor.",
            primary_route_impediment=f"Blocked edge {blocked.get('edge_id')}" if blocked else None,
            alternative_path_found=path_found,
            alternative_path_node_ids=node_ids,
            distance_km=dist,
            estimated_travel_minutes=mins,
            findings=[
                f"Graph analysis evaluated route connectivity.",
                f"Alternative path found: {path_found} (Distance: {dist} km)." if path_found else "No valid alternate connected path found.",
            ],
            recommendations=recs,
            evidence_references=ev_refs,
            confidence_score=0.92 if path_found else 0.5,
            missing_information=[] if path_found else ["Alternative network edges"],
            warnings=[] if path_found else ["Detour path unavailable across active network graph."],
        )

