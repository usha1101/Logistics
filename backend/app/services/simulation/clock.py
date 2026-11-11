from datetime import datetime, timedelta, timezone
from typing import Optional


class SimulationClock:
    """Manages virtual simulation time progression relative to wall-clock time."""

    def __init__(
        self,
        current_simulated_time: Optional[datetime] = None,
        speed_multiplier: float = 1.0,
    ):
        self.simulated_time = current_simulated_time or datetime.now(timezone.utc)
        self.speed_multiplier = max(0.1, min(100.0, speed_multiplier))
        self.is_paused = False

    def tick(self, wall_seconds: float) -> datetime:
        """Advance simulated time by wall_seconds * speed_multiplier if not paused."""
        if not self.is_paused and wall_seconds > 0:
            simulated_seconds = wall_seconds * self.speed_multiplier
            self.simulated_time += timedelta(seconds=simulated_seconds)
        return self.simulated_time

    def set_speed(self, multiplier: float) -> float:
        """Update speed multiplier within supported boundaries."""
        self.speed_multiplier = max(0.1, min(100.0, multiplier))
        return self.speed_multiplier

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

