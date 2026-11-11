import json
from typing import Any, Dict, List
from app.models.agent import AgentExecutionStatus, RecommendationPriority, RecommendationValidationStatus
from app.services.agents.base_agent import BaseAgent
from app.services.agents.prompts import DISRUPTION_ANALYSIS_PROMPT
from app.services.agents.schemas import (
    BaseAgentRecommendation,
    DisruptionAnalysisAgentOutput,
    EvidenceReference,
)


class DisruptionAnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="DISRUPTION_ANALYSIS",
            system_prompt=DISRUPTION_ANALYSIS_PROMPT,
            output_schema=DisruptionAnalysisAgentOutput,
        )

    def build_user_prompt(self, operational_context: Dict[str, Any]) -> str:
        disr = operational_context.get("disruption", {})
        return f"""Analyze this logistics disruption event:
Disruption Data:
{json.dumps(disr, indent=2)}

Synthesize findings, severity drivers, blast radius, and recovery recommendations."""

    def build_deterministic_fallback(self, operational_context: Dict[str, Any], reason: str) -> DisruptionAnalysisAgentOutput:
        disr = operational_context.get("disruption", {})
        code = disr.get("disruption_code", "UNKNOWN")
        d_type = disr.get("disruption_type", "UNKNOWN")
        severity = disr.get("severity", "MEDIUM")

        ev_refs = [
            EvidenceReference(
                resource_type="DISRUPTION",
                resource_id=disr.get("id", "UNKNOWN"),
                description=f"Disruption {code} of type {d_type} with severity {severity}",
            )
        ]

        return DisruptionAnalysisAgentOutput(
            agent_name="DISRUPTION_ANALYSIS",
            execution_status=AgentExecutionStatus.COMPLETED,
            summary=f"Deterministic assessment of {d_type} ({code}) with {severity} severity.",
            severity_assessment=f"Evaluated as {severity} according to active disruption parameters.",
            blast_radius_summary=f"Impacts recorded for {len(disr.get('impact_records', []))} direct resources.",
            criticality_drivers=[f"Disruption type: {d_type}", f"Status: {disr.get('status')}"],
            findings=[
                f"Disruption {code} is in status {disr.get('status')}.",
                f"Identified {len(disr.get('impact_records', []))} impacted downstream logistics assets.",
            ],
            recommendations=[
                BaseAgentRecommendation(
                    recommendation_type="ISOLATE_DISRUPTED_RESOURCE",
                    priority=RecommendationPriority.HIGH if severity in ["HIGH", "CRITICAL"] else RecommendationPriority.MEDIUM,
                    title=f"Isolate {d_type} impact boundary",
                    description=f"Halt standard dispatch routing through affected asset {code} until mitigation is validated.",
                    target_resource_type="DISRUPTION",
                    target_resource_id=disr.get("id"),
                    validation_status=RecommendationValidationStatus.VALIDATED,
                )
            ],
            evidence_references=ev_refs,
            confidence_score=0.9,
            missing_information=[],
            warnings=[],
        )

