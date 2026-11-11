from datetime import datetime, timezone
from typing import Any, Optional, Tuple
from app.schemas.analytics import AnalyticsFilterMeta
from app.services.analytics.exceptions import InvalidDateRangeError


def normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_date_range(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    s = normalize_utc(start_date)
    e = normalize_utc(end_date)
    if s is not None and e is not None and s > e:
        raise InvalidDateRangeError("start_date cannot be greater than end_date.")
    return s, e


def resolve_data_scope(
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> str:
    if simulation_id:
        return "SIMULATION_SPECIFIC"
    if include_simulations:
        return "OPERATIONAL_AND_SIMULATED"
    return "OPERATIONAL"


def build_filter_meta(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> AnalyticsFilterMeta:
    s, e = validate_date_range(start_date, end_date)
    return AnalyticsFilterMeta(
        start_date=s,
        end_date=e,
        simulation_id=simulation_id,
        include_simulations=include_simulations,
        data_scope=resolve_data_scope(simulation_id, include_simulations),
        generated_at=datetime.now(timezone.utc),
    )


def apply_date_filter(stmt: Any, column: Any, start_date: Optional[datetime], end_date: Optional[datetime]) -> Any:
    s, e = validate_date_range(start_date, end_date)
    if s is not None:
        stmt = stmt.where(column >= s)
    if e is not None:
        stmt = stmt.where(column <= e)
    return stmt


def apply_simulation_scope(
    stmt: Any,
    sim_column: Any,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> Any:
    if simulation_id is not None:
        return stmt.where(sim_column == simulation_id)
    if not include_simulations:
        return stmt.where(sim_column.is_(None))
    return stmt

