"""Realtime channel for the dashboard (transcript, score, actions, callbacks)."""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import bus
from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await bus.connect(websocket)
    try:
        await websocket.send_text(
            json.dumps({"type": "connected", "data": {"message": "Live channel open"}})
        )
        while True:
            # The client only needs to keep the socket warm; anything it sends
            # is treated as a ping.
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if message == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "data": {}}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat", "data": {}}))
    except WebSocketDisconnect:
        await bus.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001
        log.debug("WebSocket closed: %s", exc)
        await bus.disconnect(websocket)


@router.get("/events/recent")
async def recent_events(limit: int = 50) -> dict:
    """HTTP fallback if WebSockets are blocked by a proxy."""
    return {"events": bus.recent(limit)}
