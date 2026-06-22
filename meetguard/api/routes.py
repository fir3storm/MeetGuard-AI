"""REST API for MeetGuard AI.

Provides endpoints for external integration — querying status, listing alerts,
managing voiceprints, and controlling the pipeline.
"""

from __future__ import annotations

import secrets
from typing import Any, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware

from meetguard.utils.models import FusionResult


def create_api(engine: Any = None) -> FastAPI:
    """Create the FastAPI application with all routes.

    Args:
        engine: Optional MeetGuardEngine instance for runtime control.
    """
    app = FastAPI(title="MeetGuard AI API", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    router = APIRouter(prefix="/api/v1")
    _engine = engine
    _api_key: str = ""

    def set_api_key(key: str) -> None:
        nonlocal _api_key
        _api_key = key

    async def verify_key(x_api_key: str = Header("")) -> bool:
        if not _api_key:
            return True  # no key configured → open access
        if not secrets.compare_digest(x_api_key, _api_key):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        return True

    # ── Status ────────────────────────────────────────────────────────

    @router.get("/status")
    async def get_status(auth=Depends(verify_key)):
        if _engine is None:
            return {"status": "not_initialized"}
        return {
            "status": "running" if _engine._running.is_set() else "stopped",
            "session_id": _engine._session_id or "",
            "running_since": getattr(_engine, "_start_time", 0),
            "tick_count": _engine._tick_count,
        }

    @router.get("/status/risk")
    async def get_risk(auth=Depends(verify_key)):
        if _engine is None:
            return {"total_risk": 0.0, "level": "SAFE"}
        dash = getattr(_engine, "dashboard", None)
        if dash is None or dash._latest is None:
            return {"total_risk": 0.0, "level": "SAFE"}
        r = dash._latest
        return {
            "total_risk": r.total_risk,
            "level": r.level.value,
            "scores": {
                "face": r.scores.face,
                "voice": r.scores.voice,
                "lip": r.scores.lip,
                "nlp": r.scores.nlp,
                "urgency": r.scores.urgency,
            },
            "timestamp": r.timestamp.isoformat(),
            "session_id": r.session_id,
        }

    # ── Alerts ────────────────────────────────────────────────────────

    @router.get("/alerts")
    async def get_alerts(limit: int = 50, auth=Depends(verify_key)):
        if _engine is None:
            return {"alerts": []}
        return {"alerts": _engine.session_log.get_recent_alerts(limit=limit)}

    @router.get("/sessions")
    async def get_sessions(limit: int = 20, auth=Depends(verify_key)):
        if _engine is None:
            return {"sessions": []}
        return {"sessions": _engine.session_log.get_sessions(limit=limit)}

    # ── Voiceprints ───────────────────────────────────────────────────

    @router.get("/voiceprints")
    async def list_voiceprints(auth=Depends(verify_key)):
        if _engine is None:
            return {"voiceprints": []}
        records = _engine.vp_manager.db.list_all()
        return {"voiceprints": [{"name": r.name, "created_at": r.created_at.isoformat(),
                                  "threshold": r.threshold} for r in records]}

    @router.delete("/voiceprints/{name}")
    async def delete_voiceprint(name: str, auth=Depends(verify_key)):
        if _engine is None:
            raise HTTPException(status_code=503, detail="Engine not initialized")
        _engine.vp_manager.db.delete(name)
        return {"deleted": name}

    @router.post("/voiceprints/enroll")
    async def enroll_voiceprint(name: str, auth=Depends(verify_key)):
        # This is a stub — real enrollment requires uploading WAV data
        raise HTTPException(status_code=501, detail="Use the CLI: meetguard --enroll NAME FILE.wav")

    # ── Pipeline control ──────────────────────────────────────────────

    @router.post("/start")
    async def start_pipeline(auth=Depends(verify_key)):
        if _engine is None:
            raise HTTPException(status_code=503, detail="Engine not initialized")
        if _engine._running.is_set():
            return {"status": "already_running"}
        import threading
        t = threading.Thread(target=_engine.start, daemon=True)
        t.start()
        return {"status": "started"}

    @router.post("/stop")
    async def stop_pipeline(auth=Depends(verify_key)):
        if _engine is None:
            raise HTTPException(status_code=503, detail="Engine not initialized")
        _engine.stop()
        return {"status": "stopped"}

    # ── Config ────────────────────────────────────────────────────────

    @router.get("/config")
    async def get_config(auth=Depends(verify_key)):
        if _engine is None:
            return {}
        return _engine.cfg

    # ── Health check ──────────────────────────────────────────────────

    @router.get("/health")
    async def health():
        return {"status": "ok"}

    app.include_router(router)
    app.set_api_key = set_api_key  # type: ignore[attr-defined]

    return app
