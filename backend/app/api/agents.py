from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.database.session import get_db
from app.models.agent import AgentExecution, AgentRecommendation, AgentRun, AgentRunStatus
from app.models.disruption import Disruption
from app.models.user import User, UserRole
from app.services.agents.exceptions import AgentRunNotFoundError
from app.services.agents.orchestrator import AgentOrchestrator
from app.services.agents.schemas import (
    AgentExecutionRead,
    AgentRecommendationRead,
    AgentRunRead,
    PaginatedAgentRunsResponse,
    ProviderStatusResponse,
)

router = APIRouter(prefix="/agents", tags=["Multi-Agent AI Intelligence"])


@router.post(
    "/analyze/{disruption_id}",
    response_model=AgentRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger multi-agent AI disruption analysis and recovery synthesis",
)
async def analyze_disruption(
    disruption_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    disruption = db.get(Disruption, disruption_id)
    if not disruption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disruption '{disruption_id}' not found.",
        )

    orchestrator = AgentOrchestrator(db)
    agent_run = await orchestrator.run_analysis(disruption_id, user_id=current_user.id)
    return agent_run


@router.get(
    "/runs",
    response_model=PaginatedAgentRunsResponse,
    summary="List paginated agent runs",
)
def list_agent_runs(
    disruption_id: Optional[str] = Query(None, description="Filter by disruption ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by run status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AgentRun)
    if disruption_id:
        query = query.where(AgentRun.disruption_id == disruption_id)
    if status_filter:
        query = query.where(AgentRun.status == status_filter)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = db.scalars(
        query.order_by(AgentRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedAgentRunsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunRead,
    summary="Get full intelligence report for an agent run",
)
def get_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run '{run_id}' not found.",
        )
    return run


@router.get(
    "/runs/{run_id}/executions",
    response_model=List[AgentExecutionRead],
    summary="Get specialist agent execution details for a run",
)
def get_agent_executions(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run '{run_id}' not found.",
        )
    return run.executions


@router.get(
    "/runs/{run_id}/recommendations",
    response_model=List[AgentRecommendationRead],
    summary="Get AI recovery recommendations for a run",
)
def get_agent_recommendations(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run '{run_id}' not found.",
        )
    return run.recommendations


@router.get(
    "/status",
    response_model=ProviderStatusResponse,
    summary="Check AI LLM provider configuration and availability status",
)
def get_ai_status(
    current_user: User = Depends(get_current_user),
):
    # Returns configuration availability WITHOUT exposing secret keys
    return ProviderStatusResponse(
        gemini_configured=bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip()),
        groq_configured=bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip()),
        primary_provider=settings.AI_PRIMARY_PROVIDER,
        fallback_provider=settings.AI_FALLBACK_PROVIDER,
        primary_model=settings.GEMINI_MODEL if settings.AI_PRIMARY_PROVIDER == "gemini" else settings.GROQ_MODEL,
        fallback_model=settings.GROQ_MODEL if settings.AI_FALLBACK_PROVIDER == "groq" else settings.GEMINI_MODEL,
        timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        max_retries=settings.AI_MAX_RETRIES,
    )


@router.post(
    "/runs/{run_id}/retry",
    response_model=AgentRunRead,
    summary="Retry a failed or partial agent run",
)
async def retry_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run '{run_id}' not found.",
        )

    orchestrator = AgentOrchestrator(db)
    new_run = await orchestrator.run_analysis(run.disruption_id, user_id=current_user.id)
    return new_run

