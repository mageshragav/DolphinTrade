"""WebSocket event hub - broadcasts live events to all connected clients."""

import asyncio
import json
import logging

from fastapi import WebSocket

LOGGER = logging.getLogger('dolphin')

CLIENTS: list[WebSocket] = []


async def connect(ws: WebSocket):
    await ws.accept()
    CLIENTS.append(ws)
    try:
        await ws.send_text(json.dumps({'type': 'status', 'running': False}))
    except Exception:
        pass


def disconnect(ws: WebSocket):
    if ws in CLIENTS:
        CLIENTS.remove(ws)


async def broadcast(event: dict):
    if not CLIENTS:
        return
    dead = []
    data = json.dumps(event, default=str)
    for ws in list(CLIENTS):
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        disconnect(ws)


def broadcast_sync(event: dict):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast(event))
    except RuntimeError:
        asyncio.run(broadcast(event))
