"""In-process pub/sub that fans events out to every connected WebSocket client.

Keeps the conversation engine decoupled from transport: the engine just calls
`await broadcast(...)`, the dashboard receives it live.
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from app.core.logging import get_logger

log = get_logger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
        self._history: List[Dict[str, Any]] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        log.info("WS client connected (total=%d)", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        log.info("WS client disconnected (total=%d)", len(self._connections))

    async def broadcast(
        self, event_type: str, payload: Dict[str, Any], call_id: Optional[int] = None
    ) -> None:
        message = {
            "type": event_type,
            "call_id": call_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }
        self._history.append(message)
        self._history = self._history[-200:]

        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:  # client vanished mid-send
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._history[-limit:]


bus = EventBus()
