"""WS /ws/positions — push the latest vehicle snapshot whenever the ingester updates."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..ingestion.state import register_listener, snapshot, unregister_listener

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/positions")
async def ws_positions(ws: WebSocket) -> None:
    await ws.accept()
    queue = register_listener()
    try:
        # Send initial snapshot on connect so the client renders immediately.
        await ws.send_json({"type": "snapshot", "vehicles": snapshot()})
        while True:
            payload = await queue.get()
            await ws.send_json({"type": "update", "vehicles": payload})
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.warning("ws_positions error: %s", e)
    finally:
        unregister_listener(queue)
