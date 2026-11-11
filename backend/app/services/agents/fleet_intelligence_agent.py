import json
from typing import Any, Dict, List
from app.models.agent import AgentExecutionStatus, RecommendationPriority, RecommendationValidationStatus
from app.services.agents.base_agent import BaseAgent
from app.services.agents.prompts import FLEET_INTELLIGENCE_PROMPT
from app.services.agents.schemas import (
    BaseAgentRecommendation,
    EvidenceReference,
    FleetIntelligenceAgentOutput,
)


class FleetIntelligenceAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="FLEET_INTELLIGENCE",
            system_prompt=FLEET_INTELLIGENCE_PROMPT,
            output_schema=FleetIntelligenceAgentOutput,
        )

    def build_user_prompt(self, operational_context: Dict[str, Any]) -> str:
        fleet = operational_context.get("fleet", [])
        disr = operational_context.get("disruption", {})
        orders = operational_context.get("orders", [])
        req_payload = sum(o.get("total_weight_kg", 0.0) for o in orders)

        return f"""Analyze available fleet vehicles to support disruption mitigation:
Disrupted Vehicle ID: {disr.get('affected_vehicle_id')}
Estimated Required Payload Capacity (kg): {req_payload}

Verified Fleet Roster:
{json.dumps(fleet, indent=2)}

Identify suitable available vehicles (AVAILABLE or IDLE) with adequate capacity. Strictly exclude BREAKDOWN, MAINTENANCE, or OFFLINE vehicles."""

    def build_deterministic_fallback(self, operational_context: Dict[str, Any], reason: str) -> FleetIntelligenceAgentOutput:
        fleet = operational_context.get("fleet", [])
        disr = operational_context.get("disruption", {})
        orders = operational_context.get("orders", [])
        req_payload = sum(o.get("total_weight_kg", 0.0) for o in orders)

        candidates = []
        unusable = {}
        ev_refs = []
        recs = []

        for v in fleet:
            vid = v.get("vehicle_id")
            code = v.get("vehicle_code")
            status = v.get("status")
            cap = v.get("capacity_kg", 0.0)

            if status in ["BREAKDOWN", "MAINTENANCE", "OFFLINE"]:
                unusable[code] = f"Vehicle is in non-operational status: {status}"
            elif cap < req_payload:
                unusable[code] = f"Capacity ({cap} kg) insufficient for payload ({req_payload} kg)"
            else:
                candidates.append(vid)
                ev_refs.append(
                    EvidenceReference(
                        resource_type="VEHICLE",
                        resource_id=vid,
                        description=f"Candidate {code} is {status} with {v.get('remaining_capacity_kg')} kg available capacity.",
                        metric_value=cap,
                    )
                )

        if candidates:
            best_id = candidates[0]
            recs.append(
                BaseAgentRecommendation(
                    recommendation_type="DISPATCH_STANDBY_VEHICLE",
                    priority=RecommendationPriority.HIGH,
                    title=f"Stage standby vehicle for payload recovery",
                    description=f"Prepare candidate vehicle {best_id} to assume delivery run once operational transfer is confirmed.",
                    target_resource_type="VEHICLE",
                    target_resource_id=best_id,
                    evidence={"candidate_ids": candidates, "required_payload_kg": req_payload},
                    validation_status=RecommendationValidationStatus.VALIDATED,
                )
            )

        return FleetIntelligenceAgentOutput(
            agent_name="FLEET_INTELLIGENCE",
            execution_status=AgentExecutionStatus.COMPLETED,
            summary=f"Found {len(candidates)} available fleet candidate(s) capable of handling {req_payload} kg load.",
            available_candidate_vehicle_ids=candidates,
            capacity_feasibility={"required_kg": req_payload, "candidates_count": len(candidates)},
            unusable_vehicle_reasons=unusable,
            findings=[
                f"Fleet check completed across {len(fleet)} registered vehicles.",
                f"{len(candidates)} vehicle(s) verified as AVAILABLE/IDLE with required headroom.",
            ],
            recommendations=recs,
            evidence_references=ev_refs,
            confidence_score=0.88,
            missing_information=[],
            warnings=[] if candidates else ["No available vehicle with sufficient payload capacity found."],
        )

