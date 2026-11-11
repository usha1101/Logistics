from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import (
    AgentExecution,
    AgentExecutionStatus,
    AgentRecommendation,
    AgentRun,
    AgentRunStatus,
    RecommendationValidationStatus,
)
from app.schemas.analytics import AgentAnalyticsResponse, MetricAvailabilityStatus
from app.services.analytics.filters import (
    apply_date_filter,
    apply_simulation_scope,
    build_filter_meta,
)


def compute_agent_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> AgentAnalyticsResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    run_stmt = select(AgentRun)
    run_stmt = apply_date_filter(run_stmt, AgentRun.created_at, start_date, end_date)
    run_stmt = apply_simulation_scope(
        run_stmt, AgentRun.simulation_id, simulation_id, include_simulations
    )
    if status:
        run_stmt = run_stmt.where(AgentRun.status == status)
    if provider:
        run_stmt = run_stmt.where(AgentRun.primary_provider == provider)

    runs: List[AgentRun] = list(db.execute(run_stmt).scalars().all())
    total_runs = len(runs)

    runs_by_status: Dict[str, int] = {s.value: 0 for s in AgentRunStatus}
    run_durations: List[float] = []
    run_ids = [r.id for r in runs]

    for r in runs:
        runs_by_status[r.status] = runs_by_status.get(r.status, 0) + 1
        if r.execution_duration_ms is not None and r.execution_duration_ms >= 0:
            run_durations.append(float(r.execution_duration_ms))

    executions: List[AgentExecution] = []
    recommendations: List[AgentRecommendation] = []
    if run_ids:
        exec_stmt = select(AgentExecution).where(AgentExecution.agent_run_id.in_(run_ids))
        executions = list(db.execute(exec_stmt).scalars().all())

        rec_stmt = select(AgentRecommendation).where(AgentRecommendation.agent_run_id.in_(run_ids))
        recommendations = list(db.execute(rec_stmt).scalars().all())

    executions_by_status: Dict[str, int] = {s.value: 0 for s in AgentExecutionStatus}
    executions_by_agent: Dict[str, int] = {}
    provider_dist: Dict[str, int] = {}
    exec_durations: List[float] = []
    confidences: List[float] = []

    for ex in executions:
        executions_by_status[ex.status] = executions_by_status.get(ex.status, 0) + 1
        executions_by_agent[ex.agent_name] = executions_by_agent.get(ex.agent_name, 0) + 1
        prov = ex.provider or "NONE"
        provider_dist[prov] = provider_dist.get(prov, 0) + 1
        if ex.execution_duration_ms is not None and ex.execution_duration_ms >= 0:
            exec_durations.append(float(ex.execution_duration_ms))
        if ex.confidence_score is not None:
            confidences.append(float(ex.confidence_score))

    if not provider_dist and runs:
        for r in runs:
            prov = r.primary_provider or "NONE"
            provider_dist[prov] = provider_dist.get(prov, 0) + 1

    recs_by_val: Dict[str, int] = {s.value: 0 for s in RecommendationValidationStatus}
    recs_by_type: Dict[str, int] = {}

    for rec in recommendations:
        recs_by_val[rec.validation_status] = recs_by_val.get(rec.validation_status, 0) + 1
        recs_by_type[rec.recommendation_type] = recs_by_type.get(rec.recommendation_type, 0) + 1

    total_executions = len(executions)
    completed_executions = executions_by_status.get(AgentExecutionStatus.COMPLETED.value, 0)

    completed_runs = runs_by_status.get(AgentRunStatus.COMPLETED.value, 0)
    partially_completed_runs = runs_by_status.get(AgentRunStatus.PARTIALLY_COMPLETED.value, 0)
    failed_runs = runs_by_status.get(AgentRunStatus.FAILED.value, 0)
    ai_unavailable_runs = runs_by_status.get(AgentRunStatus.AI_UNAVAILABLE.value, 0)

    if total_executions > 0:
        agent_success_rate = round((completed_executions / total_executions) * 100.0, 2)
    elif total_runs > 0:
        agent_success_rate = round(
            ((completed_runs + partially_completed_runs) / total_runs) * 100.0, 2
        )
    else:
        agent_success_rate = 0.0

    avg_exec_duration: Optional[float] = (
        round(sum(exec_durations) / len(exec_durations), 2) if exec_durations else None
    )
    avg_run_duration: Optional[float] = (
        round(sum(run_durations) / len(run_durations), 2) if run_durations else None
    )
    avg_confidence: Optional[float] = (
        round(sum(confidences) / len(confidences), 3) if confidences else None
    )

    unavailable_metrics: List[str] = ["token_usage_total", "estimated_llm_cost_usd"]
    if avg_exec_duration is None:
        unavailable_metrics.append("average_agent_execution_duration_ms")
    if avg_run_duration is None:
        unavailable_metrics.append("average_run_duration_ms")
    if avg_confidence is None:
        unavailable_metrics.append("average_confidence_score")

    metric_classifications = {
        "total_agent_runs": MetricAvailabilityStatus.ACTUAL.value,
        "total_agent_executions": MetricAvailabilityStatus.ACTUAL.value,
        "total_recommendations": MetricAvailabilityStatus.ACTUAL.value,
        "agent_success_rate": MetricAvailabilityStatus.ACTUAL.value,
        "average_agent_execution_duration_ms": (
            MetricAvailabilityStatus.ACTUAL.value
            if avg_exec_duration is not None
            else MetricAvailabilityStatus.UNAVAILABLE.value
        ),
        "token_usage_total": MetricAvailabilityStatus.UNAVAILABLE.value,
        "estimated_llm_cost_usd": MetricAvailabilityStatus.UNAVAILABLE.value,
    }

    return AgentAnalyticsResponse(
        total_agent_runs=total_runs,
        completed_runs=completed_runs,
        partially_completed_runs=partially_completed_runs,
        failed_runs=failed_runs,
        ai_unavailable_runs=ai_unavailable_runs,
        runs_by_status=runs_by_status,
        total_agent_executions=total_executions,
        executions_by_status=executions_by_status,
        executions_by_agent_name=executions_by_agent,
        provider_usage_distribution=provider_dist,
        total_recommendations=len(recommendations),
        validated_recommendations=recs_by_val.get(
            RecommendationValidationStatus.VALIDATED.value, 0
        ),
        rejected_recommendations=recs_by_val.get(
            RecommendationValidationStatus.REJECTED.value, 0
        ),
        requires_validation_recommendations=recs_by_val.get(
            RecommendationValidationStatus.REQUIRES_VALIDATION.value, 0
        ),
        informational_recommendations=recs_by_val.get(
            RecommendationValidationStatus.INFORMATIONAL.value, 0
        ),
        recommendations_by_validation_status=recs_by_val,
        recommendations_by_type=recs_by_type,
        average_agent_execution_duration_ms=avg_exec_duration,
        average_run_duration_ms=avg_run_duration,
        average_confidence_score=avg_confidence,
        agent_success_rate=agent_success_rate,
        token_usage_total=None,
        estimated_llm_cost_usd=None,
        metric_classifications=metric_classifications,
        unavailable_metrics=unavailable_metrics,
        filter_meta=filter_meta,
    )

