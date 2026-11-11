import json
from typing import Any, Dict, List
from app.models.agent import AgentExecutionStatus, RecommendationPriority, RecommendationValidationStatus
from app.services.agents.base_agent import BaseAgent
from app.services.agents.prompts import ORDER_PRIORITY_PROMPT
from app.services.agents.schemas import (
    BaseAgentRecommendation,
    EvidenceReference,
    OrderPriorityAgentOutput,
)


class OrderPriorityAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="ORDER_PRIORITY",
            system_prompt=ORDER_PRIORITY_PROMPT,
            output_schema=OrderPriorityAgentOutput,
        )

    def build_user_prompt(self, operational_context: Dict[str, Any]) -> str:
        orders = operational_context.get("orders", [])
        disr = operational_context.get("disruption", {})
        return f"""Analyze customer order priorities and delivery SLA risks:
Disruption Details:
{json.dumps(disr, indent=2)}

Impacted Orders Context:
{json.dumps(orders, indent=2)}

Rank orders by operational urgency, flag SLA breach risks, and recommend priority dispatch sequencing."""

    def build_deterministic_fallback(self, operational_context: Dict[str, Any], reason: str) -> OrderPriorityAgentOutput:
        orders = operational_context.get("orders", [])

        # Sort: URGENT first, then overdue, then normal
        def sort_key(o):
            prio_rank = 0 if o.get("priority") == "URGENT" else (1 if o.get("priority") == "HIGH" else 2)
            overdue_rank = 0 if o.get("is_overdue") else 1
            return (prio_rank, overdue_rank)

        sorted_orders = sorted(orders, key=sort_key)
        ranked_ids = [o.get("order_id") for o in sorted_orders if o.get("order_id")]
        urgent_count = sum(1 for o in orders if o.get("priority") == "URGENT")

        ev_refs = []
        sla_risks = []
        for o in sorted_orders:
            oid = o.get("order_id")
            num = o.get("order_number")
            prio = o.get("priority")
            is_od = o.get("is_overdue")

            if prio == "URGENT" or is_od:
                sla_risks.append({"order_id": oid, "order_number": num, "priority": prio, "is_overdue": is_od})
                ev_refs.append(
                    EvidenceReference(
                        resource_type="ORDER",
                        resource_id=oid,
                        description=f"Order {num} ({prio}) {'is currently OVERDUE' if is_od else 'has strict SLA'}.",
                        metric_value=prio,
                    )
                )

        recs = []
        if ranked_ids:
            recs.append(
                BaseAgentRecommendation(
                    recommendation_type="REPRIORITIZE_ORDER",
                    priority=RecommendationPriority.CRITICAL if urgent_count > 0 else RecommendationPriority.HIGH,
                    title="Prioritize delivery dispatch for critical SLA orders",
                    description=f"Sequence {len(ranked_ids)} order(s) placing {urgent_count} urgent deliveries at front of queue.",
                    target_resource_type="ORDER_QUEUE",
                    target_resource_id=ranked_ids[0],
                    evidence={"ranked_order_ids": ranked_ids[:5], "urgent_count": urgent_count},
                    validation_status=RecommendationValidationStatus.VALIDATED,
                )
            )

        return OrderPriorityAgentOutput(
            agent_name="ORDER_PRIORITY",
            execution_status=AgentExecutionStatus.COMPLETED,
            summary=f"Processed {len(orders)} orders; identified {urgent_count} URGENT and {len(sla_risks)} high-risk SLA deliveries.",
            total_impacted_orders=len(orders),
            urgent_orders_count=urgent_count,
            ranked_order_ids=ranked_ids,
            sla_breach_risks=sla_risks,
            findings=[
                f"Evaluated {len(orders)} order records.",
                f"Ranked delivery sequence prioritizing urgent shipments.",
            ],
            recommendations=recs,
            evidence_references=ev_refs,
            confidence_score=0.95,
            missing_information=[],
            warnings=["Urgent order(s) require immediate dispatch prioritization."] if urgent_count > 0 else [],
        )

