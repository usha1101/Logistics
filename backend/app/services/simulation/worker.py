import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.broker import broker
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.simulation import Simulation, SimulationStatus
from app.services.simulation.manager import simulation_manager

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("simulation_worker")


class StandaloneSimulationWorker:
    """
    Decoupled background simulation tick runner.
    Can be deployed as a dedicated container/process separate from the FastAPI web server.
    """

    def __init__(self, tick_interval_seconds: float = 1.0):
        self.tick_interval_seconds = tick_interval_seconds
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Initializing StandaloneSimulationWorker...")
        await broker.start()
        simulation_manager.set_event_loop(asyncio.get_running_loop())

        logger.info("StandaloneSimulationWorker started. Polling and executing simulation ticks...")
        try:
            while self._running:
                await self._process_active_simulations()
                await asyncio.sleep(self.tick_interval_seconds)
        except asyncio.CancelledError:
            logger.info("StandaloneSimulationWorker loop cancelled.")
        finally:
            await self.stop()

    async def _process_active_simulations(self) -> None:
        """Finds any RUNNING simulations in DB and ensures they have background runners active."""
        db = SessionLocal()
        try:
            stmt = select(Simulation).where(Simulation.status == SimulationStatus.RUNNING.value)
            active_sims = db.execute(stmt).scalars().all()
            for sim in active_sims:
                if sim.id not in simulation_manager._running_tasks:
                    logger.info(f"Worker picked up running simulation '{sim.id}' ('{sim.name}')")
                    try:
                        simulation_manager.start_simulation(db, sim.id)
                    except Exception as e:
                        logger.warning(f"Worker could not resume simulation {sim.id}: {e}")
        except Exception as exc:
            logger.error(f"Error querying active simulations: {exc}")
        finally:
            db.close()

    async def stop(self) -> None:
        self._running = False
        await broker.stop()
        logger.info("StandaloneSimulationWorker shut down cleanly.")


async def main():
    worker = StandaloneSimulationWorker()

    def _sig_handler():
        logger.info("Received termination signal, shutting down...")
        asyncio.create_task(worker.stop())

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except (NotImplementedError, RuntimeError):
            # Windows signal handlers may not support loop.add_signal_handler
            pass

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
