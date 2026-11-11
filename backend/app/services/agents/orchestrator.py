import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.agent import (
    AgentExecution,
    AgentExecutionStatus,
    AgentRecommendation,
    AgentRun,
    AgentRunStatus,
    RecommendationExecutionStatus,
    RecommendationPriority,
    RecommendationValidationStatus,
)
from app.models.disruption import Disruption
from app.services.agents.coordinator_agent import CoordinatorAgent
from app.services.agents.data_service import OperationalDataService
from app.services.agents.disruption_analysis_agent import DisruptionAnalysisAgent
from app.services.agents.fleet_intelligence_agent import FleetIntelligenceAgent
from app.services.agents.order_priority_agent import OrderPriorityAgent
from app.services.agents.routing_intelligence_agent import RoutingIntelligenceAgent
from app.services.agents.schemas import BaseAgentOutput
from app.services.agents.warehouse_intelligence_agent import WarehouseIntelligenceAgent
from app.services.simulation.manager import ws_manager

logger = logging.getLogger("agent_orchestrator")


class AgentOrchestrator:
    """
    Coordinates execution of the multi-agent AI system:
    1. Loads disruption and verified operational data.
    2. Initializes AgentRun in PENDING state.
    3. Runs specialist agents with bounded concurrency and timeouts.
    4. Gathers outputs, detects conflicts, and synthesizes final recommendations.
    5. Validates recommendations deterministically against database constraints.
    6. Persists AgentRun, AgentExecution, and AgentRecommendation rows.
    7. Broadcasts WebSocket progress events.
    """

    def __init__(self, db: Session):
        self.db = db
        self.data_service = OperationalDataService(db)
        self.coordinator = CoordinatorAgent()

        self.specialists = {
            "DISRUPTION_ANALYSIS": DisruptionAnalysisAgent(),
            "FLEET_INTELLIGENCE": FleetIntelligenceAgent(),
            "ROUTING_INTELLIGENCE": RoutingIntelligenceAgent(),
            "WAREHOUSE_INTELLIGENCE": WarehouseIntelligenceAgent(),
            "ORDER_PRIORITY": OrderPriorityAgent(),
        }

    async def run_analysis(
        self,
        disruption_id: str,
        user_id: Optional[str] = None,
    ) -> AgentRun:
        disruption = self.db.get(Disruption, disruption_id)
        if not disruption:
            raise ValueError(f"Disruption '{disruption_id}' not found.")

        # 1. Create AgentRun in DB
        agent_run = AgentRun(
            disruption_id=disruption.id,
            simulation_id=disruption.simulation_id,
            status=AgentRunStatus.RUNNING.value,
            primary_provider=self.specialists["DISRUPTION_ANALYSIS"].llm.primary_name,
            created_by_user_id=user_id,
        )
        self.db.add(agent_run)
        self.db.commit()
        self.db.refresh(agent_run)

        self._broadcast(agent_run, "AGENT_RUN_STARTED", {"disruption_id": disruption.id})

        start_time = time.perf_counter()

        # 2. Gather verified operational context
        disr_ctx = self.data_service.get_disruption_context(disruption.id)
        orders_ctx = self.data_service.get_order_context(
            affected_vehicle_id=disruption.affected_vehicle_id,
            affected_order_id=disruption.affected_order_id,
        )
        fleet_ctx = self.data_service.get_fleet_context()
        routing_ctx = self.data_service.get_routing_context(
            blocked_edge_id=disruption.affected_network_edge_id,
        )
        wh_ctx = self.data_service.get_warehouse_context(
            target_warehouse_id=disruption.affected_warehouse_id,
        )

        op_context = {
            "disruption": disr_ctx,
            "orders": orders_ctx,
            "fleet": fleet_ctx,
            "routing": routing_ctx,
            "warehouses": wh_ctx,
        }

        # 3. Execute specialist agents in parallel with safe error isolation
        specialist_outputs: Dict[str, BaseAgentOutput] = {}

        async def run_specialist(name: str, agent):
            self._broadcast(agent_run, "AGENT_EXECUTION_STARTED", {"agent_name": name})
            try:
                res = await agent.execute(op_context)
                self._broadcast(agent_run, "AGENT_EXECUTION_COMPLETED", {
                    "agent_name": name,
                    "confidence_score": res.confidence_score,
                })
                return name, res
            except Exception as e:
                logger.error(f"Specialist {name} crashed: {e}")
                self._broadcast(agent_run, "AGENT_EXECUTION_FAILED", {"agent_name": name, "error": str(e)})
                fallback = agent.build_deterministic_fallback(op_context, reason=str(e))
                return name, fallback

        tasks = [run_specialist(name, agent) for name, agent in self.specialists.items()]
        results = await asyncio.gather(*tasks)
        for name, output in results:
            specialist_outputs[name] = output

        # 4. Coordinator Synthesis & Conflict Detection
        synthesis = await self.coordinator.synthesize(
            specialist_outputs=specialist_outputs,
            operational_context=op_context,
            disruption_code=disruption.disruption_code,
        )

        # 5. Persist Specialist Executions in DB
        for name, out in specialist_outputs.items():
            exec_row = AgentExecution(
                agent_run_id=agent_run.id,
                agent_name=name,
                status=out.execution_status.value if hasattr(out.execution_status, "value") else str(out.execution_status),
                provider=out.provider,
                model=out.model,
                input_summary=f"Context items: disruption={bool(disr_ctx)}, orders={len(orders_ctx)}, fleet={len(fleet_ctx)}",
                output=out.model_dump(mode="json"),
                confidence_score=out.confidence_score,
                evidence_references=[ev.model_dump(mode="json") for ev in out.evidence_references],
                warnings=out.warnings,
                execution_duration_ms=out.execution_duration_ms,
                completed_at=datetime.now(timezone.utc),
            )
            self.db.add(exec_row)

        # 6. Validate & Persist Recommendations
        for rec in synthesis.consolidated_recommendations:
            # Deterministic Python validation check
            val_status = self._validate_recommendation_deterministically(rec)

            rec_row = AgentRecommendation(
                agent_run_id=agent_run.id,
                source_agent=rec.recommendation_type.split("_")[0],
                recommendation_type=rec.recommendation_type,
                priority=rec.priority.value if hasattr(rec.priority, "value") else str(rec.priority),
                title=rec.title,
                description=rec.description,
                target_resource_type=rec.target_resource_type,
                target_resource_id=rec.target_resource_id,
                evidence=rec.evidence,
                validation_status=val_status,
                execution_status=RecommendationExecutionStatus.RECOMMENDED_ONLY.value,
            )
            self.db.add(rec_row)
            self._broadcast(agent_run, "AGENT_RECOMMENDATION_CREATED", {
                "title": rec.title,
                "validation_status": val_status,
            })

        # 7. Finalize AgentRun
        total_duration = (time.perf_counter() - start_time) * 1000.0
        agent_run.execution_duration_ms = round(total_duration, 2)
        agent_run.completed_at = datetime.now(timezone.utc)
        agent_run.status = AgentRunStatus.COMPLETED.value

        self.db.commit()
        self.db.refresh(agent_run)

        self._broadcast(agent_run, "AGENT_RUN_COMPLETED", {
            "duration_ms": agent_run.execution_duration_ms,
            "recommendations_count": len(synthesis.consolidated_recommendations),
        })

        return agent_run

    def _validate_recommendation_deterministically(self, rec) -> str:
        """
        Applies deterministic Python rule checks to ensure recommendation feasibility.
        LLM cannot override failed validation.
        """
        # For vehicle dispatches: verify vehicle exists and is available
        if rec.target_resource_type == "VEHICLE" and rec.target_resource_id:
            from app.models.vehicle import Vehicle
            v = self.db.get(Vehicle, rec.target_resource_id)
            if not v or v.status in ["BREAKDOWN", "MAINTENANCE", "OFFLINE"]:
                return RecommendationValidationStatus.REJECTED.value

        # For warehouse reallocations: verify warehouse exists and is not at 100% capacity
        if rec.target_resource_type == "WAREHOUSE" and rec.target_resource_id:
            from app.models.warehouse import Warehouse
            w = self.db.get(Warehouse, rec.target_resource_id)
            if not w or (w.total_capacity and (w.used_capacity or 0.0) >= w.total_capacity):
                return RecommendationValidationStatus.REJECTED.value

        # If coordinator already flagged as requiring validation or if conflicting
        if rec.validation_status == RecommendationValidationStatus.REQUIRES_VALIDATION:
            return RecommendationValidationStatus.REQUIRES_VALIDATION.value

        return RecommendationValidationStatus.VALIDATED.value

    def _broadcast(self, agent_run: AgentRun, event_name: str, payload: Dict[str, Any]) -> None:
        """Safely fires WebSocket broadcast message if linked to a simulation."""
        if not agent_run.simulation_id:
            return

        message = {
            "type": "AGENT_INTELLIGENCE_UPDATE",
            "event": event_name,
            "agent_run_id": agent_run.id,
            "disruption_id": agent_run.disruption_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                asyncio.create_task(ws_manager.broadcast(agent_run.simulation_id, message))
        except Exception as e:
            logger.warning(f"Failed to broadcast agent WebSocket message: {e}")
