"""FastAPI local dashboard server with WebSocket streaming.

Serves the real-time detection status to the Gradio UI and
any other local clients.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Optional

from meetguard.utils.models import AlertLevel, DetectorScores, FusionResult

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    import uvicorn
except ImportError:
    FastAPI = None  # type: ignore[assignment,misc]
    uvicorn = None  # type: ignore[assignment,misc]


class DashboardServer:
    """Lightweight FastAPI server that streams detection results via WebSocket."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8573):
        self.host = host
        self.port = port
        self._app: Any = FastAPI() if FastAPI is not None else None
        self._clients: list[WebSocket] = []
        self._latest: dict[str, Any] = {}
        self._thread: Optional[threading.Thread] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        if self._app is None:
            return

        app = self._app

        @app.get("/status")
        async def get_status():
            return self._latest

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            self._clients.append(ws)
            try:
                while True:
                    await ws.receive_text()  # keep alive
            except WebSocketDisconnect:
                self._clients.remove(ws)

    def update(self, result: FusionResult) -> None:
        """Broadcast the latest fusion result to all WebSocket clients."""
        self._latest = {
            "timestamp": result.timestamp.isoformat(),
            "total_risk": result.total_risk,
            "level": result.level.value,
            "scores": {
                "face": result.scores.face,
                "voice": result.scores.voice,
                "lip": result.scores.lip,
                "nlp": result.scores.nlp,
                "urgency": result.scores.urgency,
            },
            "meeting_active": result.meeting_active,
        }
        if self._app is None:
            return
        # Fire-and-forget broadcast
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._broadcast())
            loop.close()
        except Exception:
            pass

    async def _broadcast(self) -> None:
        dead: list[WebSocket] = []
        payload = json.dumps(self._latest, default=str)
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.remove(ws)

    def start(self) -> None:
        if self._app is None:
            return
        if uvicorn is None:
            return
        self._thread = threading.Thread(
            target=uvicorn.run,
            args=(self._app,),
            kwargs={"host": self.host, "port": self.port, "log_level": "warning"},
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        pass  # daemon thread dies with process
