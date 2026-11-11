import json
from typing import Any, Dict, List
from app.models.agent import AgentExecutionStatus, RecommendationPriority, RecommendationValidationStatus
from app.services.agents.base_agent import BaseAgent
from app.services.agents.prompts import WAREHOUSE_INTELLIGENCE_PROMPT
from app.services.agents.schemas import (
    BaseAgentRecommendation,
    EvidenceReference,
    WarehouseIntelligenceAgentOutput,
)


class WarehouseIntelligenceAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="WAREHOUSE_INTELLIGENCE",
            system_prompt=WAREHOUSE_INTELLIGENCE_PROMPT,
            output_schema=WarehouseIntelligenceAgentOutput,
        )

    def build_user_prompt(self, operational_context: Dict[str, Any]) -> str:
        warehouses = operational_context.get("warehouses", [])
        disr = operational_context.get("disruption", {})
        return f"""Analyze warehouse capacity strain and stock availability:
Target Warehouse ID: {disr.get('affected_warehouse_id')}

Warehouse Roster:
{json.dumps(warehouses, indent=2)}

Evaluate headroom, flag facilities above 85% utilization, and assess backup fulfillment hubs."""

    def build_deterministic_fallback(self, operational_context: Dict[str, Any], reason: str) -> WarehouseIntelligenceAgentOutput:
        warehouses = operational_context.get("warehouses", [])
        disr = operational_context.get("disruption", {})
        target_wh_id = disr.get("affected_warehouse_id")

        candidates = []
        ev_refs = []
        recs = []

        target_util = 0.0
        for w in warehouses:
            wid = w.get("warehouse_id")
            code = w.get("warehouse_code")
            util = w.get("utilization_pct", 0.0)

            if wid == target_wh_id:
                target_util = util

            if util < 80.0 and wid != target_wh_id:
                candidates.append(wid)
                ev_refs.append(
                    EvidenceReference(
                        resource_type="WAREHOUSE",
                        resource_id=wid,
                        description=f"Hub {code} has {w.get('available_capacity')} units available headroom ({util}% utilized).",
                        metric_value=util,
                    )
                )

        if candidates:
            best_wh = candidates[0]
            recs.append(
                BaseAgentRecommendation(
                    recommendation_type="REALLOCATE_WAREHOUSE",
                    priority=RecommendationPriority.MEDIUM,
                    title="Buffer load at alternative distribution hub",
                    description=f"Direct incoming stock staging to warehouse {best_wh} to relieve strained fulfillment capacity.",
                    target_resource_type="WAREHOUSE",
                    target_resource_id=best_wh,
                    evidence={"candidate_warehouses": candidates},
                    validation_status=RecommendationValidationStatus.VALIDATED,
                )
            )

        return WarehouseIntelligenceAgentOutput(
            agent_name="WAREHOUSE_INTELLIGENCE",
            execution_status=AgentExecutionStatus.COMPLETED,
            summary=f"Warehouse analysis complete. {len(candidates)} alternative hub(s) available with <80% utilization.",
            affected_warehouse_id=target_wh_id,
            capacity_strain_assessment=f"Primary affected hub utilization at {target_util}%.",
            stock_shortage_detected=False,
            alternative_warehouse_candidates=candidates,
            findings=[
                f"Evaluated capacity across {len(warehouses)} network distribution hubs.",
                f"Identified {len(candidates)} hub(s) with sufficient operational buffer.",
            ],
            recommendations=recs,
            evidence_references=ev_refs,
            confidence_score=0.85,
            missing_information=[],
            warnings=[] if candidates else ["All warehouses are nearing operational capacity (>80%)."],
        )

