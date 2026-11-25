import asyncio
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.broker import LocalBroadcastBroker, RedisBroadcastBroker, create_broker
from app.core.tasks import BackgroundTaskManager, TaskStatus, task_manager
from app.models.user import User


class MockWebSocket:
    """Mock WebSocket for testing broadcast broker without network sockets."""

    def __init__(self):
        self.accepted = False
        self.messages = []
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        if self.closed:
            raise RuntimeError("Socket closed")
        self.messages.append(data)


@pytest.mark.anyio
async def test_local_broadcast_broker():
    """Verify LocalBroadcastBroker connection and delivery."""
    broker = LocalBroadcastBroker()
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    await broker.connect("sim-test-1", ws1)
    await broker.connect("sim-test-1", ws2)
    assert ws1.accepted and ws2.accepted

    # Broadcast message
    payload = {"event": "TICK", "simulated_time": "2026-11-20T10:00:00Z"}
    await broker.broadcast("sim-test-1", payload)

    assert len(ws1.messages) == 1
    assert ws1.messages[0] == payload
    assert len(ws2.messages) == 1

    # Disconnect one
    broker.disconnect("sim-test-1", ws1)
    await broker.broadcast("sim-test-1", {"event": "TICK2"})
    assert len(ws1.messages) == 1  # Not delivered to ws1
    assert len(ws2.messages) == 2  # Delivered to ws2

    await broker.stop()


@pytest.mark.anyio
async def test_redis_broadcast_broker_local_fallback():
    """Verify RedisBroadcastBroker delegates to local broker when offline."""
    broker = RedisBroadcastBroker("redis://invalid-host-for-test:6379/0")
    ws = MockWebSocket()

    await broker.connect("sim-room-2", ws)
    assert ws.accepted

    # Local delivery must succeed regardless of Redis connection status
    msg = {"type": "TELEMETRY", "lat": 12.97, "lon": 77.59}
    await broker.broadcast("sim-room-2", msg)
    assert len(ws.messages) == 1
    assert ws.messages[0] == msg

    broker.disconnect("sim-room-2", ws)
    await broker.stop()


@pytest.mark.anyio
async def test_background_task_manager_lifecycle():
    """Verify BackgroundTaskManager tracks task progression and completion."""
    tm = BackgroundTaskManager()

    async def sample_job(x: int, y: int):
        await asyncio.sleep(0.05)
        return x + y

    task = tm.submit_task("MATH_ADD", sample_job, 10, 25)
    assert task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
    assert task.task_type == "MATH_ADD"

    # Wait for completion
    await asyncio.sleep(0.15)
    updated = tm.get_task(task.task_id)
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.progress_percentage == 100.0
    assert updated.result == 35
    assert updated.completed_at is not None


@pytest.mark.anyio
async def test_background_task_manager_failure_handling():
    """Verify BackgroundTaskManager catches and records task exceptions."""
    tm = BackgroundTaskManager()

    async def failing_job():
        await asyncio.sleep(0.01)
        raise ValueError("Simulated processing failure")

    task = tm.submit_task("FAILING_TASK", failing_job)
    await asyncio.sleep(0.05)

    updated = tm.get_task(task.task_id)
    assert updated is not None
    assert updated.status == TaskStatus.FAILED
    assert "Simulated processing failure" in updated.error


@pytest.mark.anyio
async def test_background_task_manager_cancellation():
    """Verify long-running task can be cancelled."""
    tm = BackgroundTaskManager()

    async def long_job():
        await asyncio.sleep(10.0)

    task = tm.submit_task("LONG_TASK", long_job)
    assert tm.cancel_task(task.task_id) is True

    await asyncio.sleep(0.05)
    updated = tm.get_task(task.task_id)
    assert updated is not None
    assert updated.status == TaskStatus.CANCELLED


def test_async_report_generation_api(client: TestClient, admin_headers: dict):
    """Verify asynchronous report generation endpoint submits task and provides polling."""
    req_body = {
        "report_type": "EXECUTIVE_SUMMARY",
        "title": "Phase 3 Async Report Test",
    }

    # Submit async report job
    submit_res = client.post(
        "/api/v1/reports/generate-async",
        json=req_body,
        headers=admin_headers,
    )
    assert submit_res.status_code == 202
    data = submit_res.json()
    assert "task_id" in data
    assert data["task_type"] == "REPORT_GENERATION"
    task_id = data["task_id"]

    # Poll status
    status_res = client.get(
        f"/api/v1/reports/tasks/{task_id}",
        headers=admin_headers,
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["task_id"] == task_id
    assert status_data["status"] in ("PENDING", "RUNNING", "COMPLETED")
