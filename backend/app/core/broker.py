import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger("app.core.broker")


class BaseBroadcastBroker(ABC):
    """Abstract interface for WebSocket room connection and broadcast management."""

    @abstractmethod
    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        """Accepts and registers a client WebSocket in a room."""
        pass

    @abstractmethod
    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        """Unregisters a client WebSocket from a room."""
        pass

    @abstractmethod
    async def broadcast(self, room_id: str, message: Dict[str, Any]) -> None:
        """Broadcasts a payload to all connected clients in a room across all replicas."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Initializes any network listeners (e.g. Redis Pub/Sub)."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Shuts down broker connections and listeners."""
        pass


class LocalBroadcastBroker(BaseBroadcastBroker):
    """In-memory broadcast broker for single-instance or development environments."""

    def __init__(self):
        self._rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if room_id not in self._rooms:
            self._rooms[room_id] = set()
        self._rooms[room_id].add(websocket)
        logger.info(f"Local broker: client connected to room '{room_id}'. Total: {len(self._rooms[room_id])}")

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        if room_id in self._rooms and websocket in self._rooms[room_id]:
            self._rooms[room_id].remove(websocket)
            if not self._rooms[room_id]:
                del self._rooms[room_id]
        logger.info(f"Local broker: client disconnected from room '{room_id}'.")

    async def broadcast_local(self, room_id: str, message: Dict[str, Any]) -> None:
        """Delivers message directly to local sockets registered on this instance."""
        if room_id not in self._rooms:
            return
        dead_sockets: List[WebSocket] = []
        for ws in list(self._rooms[room_id]):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket: {e}")
                dead_sockets.append(ws)
        for ws in dead_sockets:
            self.disconnect(room_id, ws)

    async def broadcast(self, room_id: str, message: Dict[str, Any]) -> None:
        await self.broadcast_local(room_id, message)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self._rooms.clear()


class RedisBroadcastBroker(BaseBroadcastBroker):
    """
    Distributed broadcast broker leveraging Redis Pub/Sub.
    Allows multi-pod horizontal scaling: broadcasts emitted on Pod A are delivered
    to WebSockets connected on Pod B, Pod C, etc.
    """

    CHANNEL_PREFIX = "logipulse:sim:"

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._local = LocalBroadcastBroker()
        self._pub_client = None
        self._sub_client = None
        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        await self._local.connect(room_id, websocket)

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        self._local.disconnect(room_id, websocket)

    async def start(self) -> None:
        if self._running:
            return
        try:
            import redis.asyncio as aioredis
            self._pub_client = aioredis.from_url(self._redis_url, decode_responses=True)
            self._sub_client = aioredis.from_url(self._redis_url, decode_responses=True)
            self._running = True
            self._listener_task = asyncio.create_task(self._pubsub_listener())
            logger.info("RedisBroadcastBroker started successfully with Pub/Sub listener.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {self._redis_url}: {e}. Falling back to local broker.")
            self._running = False

    async def _pubsub_listener(self) -> None:
        try:
            pubsub = self._sub_client.pubsub()
            await pubsub.psubscribe(f"{self.CHANNEL_PREFIX}*")
            while self._running:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "pmessage":
                    channel = message.get("channel", "")
                    room_id = channel.replace(self.CHANNEL_PREFIX, "")
                    data_str = message.get("data")
                    if data_str:
                        try:
                            payload = json.loads(data_str)
                            await self._local.broadcast_local(room_id, payload)
                        except json.JSONDecodeError:
                            pass
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Redis Pub/Sub listener error: {e}")

    async def broadcast(self, room_id: str, message: Dict[str, Any]) -> None:
        # 1. Broadcast locally immediately for lowest latency
        await self._local.broadcast_local(room_id, message)

        # 2. Publish to Redis if connected so other pods receive it
        if self._running and self._pub_client:
            try:
                channel = f"{self.CHANNEL_PREFIX}{room_id}"
                await self._pub_client.publish(channel, json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to publish to Redis channel {room_id}: {e}")

    async def stop(self) -> None:
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pub_client:
            await self._pub_client.close()
        if self._sub_client:
            await self._sub_client.close()
        await self._local.stop()
        logger.info("RedisBroadcastBroker stopped.")


def create_broker() -> BaseBroadcastBroker:
    """Factory creating the appropriate broker based on runtime settings."""
    if settings.REDIS_URL and settings.REDIS_PUBSUB_ENABLED:
        return RedisBroadcastBroker(settings.REDIS_URL)
    return LocalBroadcastBroker()


# Global broadcast broker instance
broker: BaseBroadcastBroker = create_broker()
