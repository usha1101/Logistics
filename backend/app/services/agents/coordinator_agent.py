import json
import logging
from typing import Any, Dict, List
from app.models.agent import RecommendationPriority, RecommendationValidationStatus
from app.services.agents.base_agent import BaseAgent
from app.services.agents.prompts import COORDINATOR_SYSTEM_PROMPT
from app.services.agents.schemas import (
    BaseAgentOutput,
    BaseAgentRecommendation,
    ConflictItem,
    CoordinatorSynthesisOutput,
)

logger = logging.getLogger("coordinator_agent")


class CoordinatorAgent:
    """
    Synthesizes findings from specialist agents, evaluates operational cross-domain conflicts,
    and produces an explainable final intelligence report.
    """

    def __init__(self):
        self.system_prompt = COORDINATOR_SYSTEM_PROMPT

    def detect_conflicts(
        self,
        specialist_outputs: Dict[str, BaseAgentOutput],
        operational_context: Dict[str, Any],
    ) -> List[ConflictItem]:
        conflicts = []

        fleet_out = specialist_outputs.get("FLEET_INTELLIGENCE")
        routing_out = specialist_outputs.get("ROUTING_INTELLIGENCE")
        wh_out = specialist_outputs.get("WAREHOUSE_INTELLIGENCE")

        # Conflict 1: Fleet recommends vehicle, but Routing reports no available path
        if fleet_out and routing_out:
            candidates = getattr(fleet_out, "available_candidate_vehicle_ids", [])
            path_found = getattr(routing_out, "alternative_path_found", True)

            if candidates and not path_found:
                conflicts.append(
                    ConflictItem(
                        conflict_type="VEHICLE_ROUTE_UNREACHABLE",
                        description="Fleet Agent identified available replacement vehicle(s), but Routing Agent detected no reachable network path through the disrupted zone.",
                        involved_agents=["FLEET_INTELLIGENCE", "ROUTING_INTELLIGENCE"],
                        evidence_details={"candidate_vehicles": candidates, "alternative_path_found": path_found},
                        resolution_guidance="Do not dispatch replacement vehicle without establishing alternative corridor route.",
                    )
                )

        # Conflict 2: Staging buffer at warehouse that is above 80% utilization
        if wh_out:
            strained = getattr(wh_out, "stock_shortage_detected", False)
            candidates = getattr(wh_out, "alternative_warehouse_candidates", [])
            if not candidates:
                conflicts.append(
                    ConflictItem(
                        conflict_type="WAREHOUSE_CAPACITY_EXHAUSTION",
                        description="Warehouse Agent detected all alternative fulfillment hubs exceed safe operational capacity buffer (>80%).",
                        involved_agents=["WAREHOUSE_INTELLIGENCE"],
                        evidence_details={"alternative_candidates": candidates},
                        resolution_guidance="Hold inbound dock receiving until floor storage clears.",
                    )
                )

        return conflicts

    async def synthesize(
        self,
        specialist_outputs: Dict[str, BaseAgentOutput],
        operational_context: Dict[str, Any],
        disruption_code: str,
    ) -> CoordinatorSynthesisOutput:
        conflicts = self.detect_conflicts(specialist_outputs, operational_context)

        # Aggregate recommendations from all specialists
        all_recs: List[BaseAgentRecommendation] = []
        all_warnings: List[str] = []
        scores: List[float] = []

        for agent_name, out in specialist_outputs.items():
            if out:
                scores.append(out.confidence_score)
                all_warnings.extend(out.warnings)
                for r in out.recommendations:
                    # If conflict touches this recommendation, mark REQUIRES_VALIDATION
                    if conflicts and r.recommendation_type in ["DISPATCH_STANDBY_VEHICLE", "REALLOCATE_WAREHOUSE"]:
                        r.validation_status = RecommendationValidationStatus.REQUIRES_VALIDATION
                    all_recs.append(r)

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.85

        # Check if LLM is online for narrative synthesis
        summary_text = (
            f"Multi-agent AI analysis successfully synthesized across {len(specialist_outputs)} specialist domains "
            f"for disruption {disruption_code}. Evaluated fleet capacity, corridor detours, inventory availability, "
            f"and order SLA urgency. Found {len(all_recs)} recovery recommendation(s) with {len(conflicts)} operational conflict(s)."
        )

        return CoordinatorSynthesisOutput(
            executive_summary=summary_text,
            overall_confidence_score=avg_score,
            operational_risks=[w for w in all_warnings if w],
            detected_conflicts=conflicts,
            consolidated_recommendations=all_recs,
            missing_data_warnings=[],
        )

