import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.simulation import SimulationEvent, SimulationEventType


def create_simulation_event(
    db: Session,
    simulation_id: str,
    event_type: SimulationEventType,
    vehicle_id: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
    simulated_timestamp: Optional[datetime] = None,
) -> SimulationEvent:
    """Create and persist an immutable simulation audit event."""
    event = SimulationEvent(
        id=str(uuid.uuid4()),
        simulation_id=simulation_id,
        vehicle_id=vehicle_id,
        event_type=event_type.value if isinstance(event_type, SimulationEventType) else str(event_type),
        event_data=event_data or {},
        simulated_timestamp=simulated_timestamp or datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event

