"""Integration tests for the full pipeline."""

import numpy as np
import pytest

from meetguard.main import MeetGuardEngine


def test_engine_initializes():
    engine = MeetGuardEngine()
    assert engine.cfg is not None
    assert engine.face_extractor is not None
    assert engine.dashboard is not None


def test_tick_with_synthetic_data():
    engine = MeetGuardEngine()
    for _ in range(20):
        engine.frame_buffer.push(np.zeros((480, 640, 3), dtype=np.uint8))
    for _ in range(20):
        engine.audio_buffer.push(np.zeros(16000, dtype=np.float32))

    result = engine._tick()
    assert result is not None
    assert 0.0 <= result.total_risk <= 1.0
    assert result.level is not None


def test_dry_run_cli():
    """Test that --dry-run works (calls validate_config)."""
    from meetguard.config import load, validate_config
    cfg = load()
    warnings = validate_config(cfg)
    assert isinstance(warnings, list)


def test_session_lifecycle():
    """Test session creation and ending."""
    from meetguard.storage.session_log import SessionLog
    log = SessionLog()
    session_id = log.create_session("Zoom - Board Meeting")
    assert session_id is not None
    assert len(session_id) == 12

    sessions = log.get_sessions(limit=5)
    assert any(s["id"] == session_id for s in sessions)

    log.end_session(session_id)
    sessions = log.get_sessions(limit=5)
    ended = [s for s in sessions if s["id"] == session_id]
    assert ended[0]["ended_at"] != "ongoing"
