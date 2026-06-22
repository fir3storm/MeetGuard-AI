"""Shared test fixtures for MeetGuard tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest


@pytest.fixture
def sample_frame() -> np.ndarray:
    """Return a dummy video frame (480x640x3 BGR)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_audio() -> np.ndarray:
    """Return a dummy audio chunk (1s of silence at 16kHz)."""
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def sample_face_crops() -> list[np.ndarray]:
    """Return a list of dummy face crops for detector tests."""
    return [np.zeros((224, 224, 3), dtype=np.uint8) for _ in range(16)]


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Return a minimal valid config for testing."""
    return {
        "capture": {
            "fps": 5,
            "audio_sample_rate": 16000,
            "buffer_seconds": 10,
            "window_title_patterns": ["Zoom*"],
            "diarization": {"enabled": False, "hf_token": ""},
    },
        "detectors": {
            "deepfake_face": {"enabled": True, "model_path": "", "window_frames": 16,
                             "threshold_suspicious": 0.5, "threshold_critical": 0.75},
            "voice_mismatch": {"enabled": True, "similarity_threshold": 0.45,
                              "enrollment_min_seconds": 30, "model": "test"},
            "lip_sync": {"enabled": True, "confidence_threshold": 0.3, "window_seconds": 2.0},
            "suspicious_nlp": {"enabled": True, "model": "test",
                              "enable_llm_fallback": False,
                              "llm": {"provider": "ollama", "model": "mistral:7b",
                                      "api_url": "http://localhost:11434"}},
            "urgency_language": {"enabled": True, "threshold": 0.6, "use_prosodic": False},
        },
        "diarization": {"enabled": False, "hf_token": ""},
        "fusion": {
            "weights": {"face": 0.30, "voice": 0.25, "lip": 0.15, "nlp": 0.20, "urgency": 0.10},
            "thresholds": {"monitor": 0.20, "suspicious": 0.45, "critical": 0.75},
            "cooldown_seconds": 60,
        },
        "alerting": {
            "desktop_notifications": True, "sound_alert": True,
            "auto_record_clip": True, "clip_length_seconds": 30, "log_sessions": True,
            "webhooks": {"slack_url": "", "discord_url": "",
                        "email": {"smtp_host": "", "smtp_port": 587, "from_addr": "", "to_addrs": []}},
        },
    }


@pytest.fixture
def tmp_meetguard_home(tmp_path: Path) -> Path:
    """Return a temporary MEETGUARD_HOME directory."""
    data_dir = tmp_path / ".meetguard"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
