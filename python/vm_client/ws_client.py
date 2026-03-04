from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets


class WSClient:
    # Default 10MB max message size to prevent memory exhaustion attacks
    DEFAULT_MAX_MESSAGE_SIZE = 10 * 1024 * 1024
    
    def __init__(self, url: str, max_size: int | None = None):
        self.url = url
        self.ws: websockets.WebSocketClientProtocol | None = None
        self._send_lock = asyncio.Lock()
        # Use provided max_size or default, but never None (which disables limit)
        self.max_size = max_size if max_size is not None else self.DEFAULT_MAX_MESSAGE_SIZE

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.url, max_size=self.max_size)

    async def send(self, payload: dict[str, Any]) -> None:
        if self.ws is None:
            raise RuntimeError("websocket not connected")
        data = json.dumps(payload, separators=(",", ":"))
        async with self._send_lock:
            await self.ws.send(data)

    async def recv_json(self) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("websocket not connected")
        msg = await self.ws.recv()
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", errors="replace")
        data = json.loads(msg)
        if isinstance(data, dict):
            return data
        return {"type": "error", "detail": "non-object message"}

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
