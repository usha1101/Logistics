import asyncio
import enum
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger("app.core.tasks")


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskInfo(BaseModel):
    task_id: str
    task_type: str
    status: TaskStatus
    progress_percentage: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BackgroundTaskManager:
    """
    Thread-safe asynchronous background task dispatcher and state registry.
    Offloads heavy operations (ReportLab PDF generation, Multi-agent LLM reasoning)
    from blocking synchronous request cycles.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[str, TaskInfo] = {}
        self._asyncio_tasks: Dict[str, Any] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Stores the active application event loop for threadpool submissions."""
        self._loop = loop

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.model_copy() if task else None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[TaskInfo]:
        with self._lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return [t.model_copy() for t in tasks]

    def update_progress(self, task_id: str, progress: float) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].progress_percentage = min(100.0, max(0.0, progress))

    def submit_task(
        self,
        task_type: str,
        coro_fn: Union[Callable[..., Coroutine[Any, Any, Any]], Coroutine[Any, Any, Any]],
        *args,
        **kwargs,
    ) -> TaskInfo:
        """Submits an async function or coroutine to be processed in the background."""
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            progress_percentage=0.0,
            created_at=now,
        )

        with self._lock:
            self._tasks[task_id] = task_info

        async def _runner():
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id].status = TaskStatus.RUNNING
                    self._tasks[task_id].started_at = datetime.now(timezone.utc)
            try:
                if asyncio.iscoroutine(coro_fn):
                    res = await coro_fn
                elif asyncio.iscoroutinefunction(coro_fn):
                    res = await coro_fn(*args, **kwargs)
                else:
                    res = coro_fn(*args, **kwargs)

                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].status = TaskStatus.COMPLETED
                        self._tasks[task_id].progress_percentage = 100.0
                        self._tasks[task_id].result = res
                        self._tasks[task_id].completed_at = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].status = TaskStatus.CANCELLED
                        self._tasks[task_id].completed_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.error(f"Background task {task_id} failed: {exc}", exc_info=True)
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].status = TaskStatus.FAILED
                        self._tasks[task_id].error = str(exc)
                        self._tasks[task_id].completed_at = datetime.now(timezone.utc)
            finally:
                with self._lock:
                    self._asyncio_tasks.pop(task_id, None)

        # Dispatch _runner across whatever loop/thread context is active
        try:
            current_loop = asyncio.get_running_loop()
            asyncio_task = current_loop.create_task(_runner())
            with self._lock:
                self._asyncio_tasks[task_id] = asyncio_task
        except RuntimeError:
            if self._loop and self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_runner(), self._loop)
                with self._lock:
                    self._asyncio_tasks[task_id] = future
            else:
                thread = threading.Thread(target=lambda: asyncio.run(_runner()), daemon=True)
                thread.start()

        return task_info.model_copy()

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            asyncio_task = self._asyncio_tasks.get(task_id)
            if asyncio_task and not asyncio_task.done():
                asyncio_task.cancel()
                if task_id in self._tasks:
                    self._tasks[task_id].status = TaskStatus.CANCELLED
                    self._tasks[task_id].completed_at = datetime.now(timezone.utc)
                return True
            return False


# Global task manager singleton
task_manager = BackgroundTaskManager()
