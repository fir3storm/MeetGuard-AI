"""YAML config loader with validation, profiles, defaults, and runtime overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when configuration is invalid."""


try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
APP_DATA_DIR = Path(os.environ.get("MEETGUARD_HOME", Path.home() / ".meetguard"))
VALID_SAMPLE_RATES = {8000, 16000, 44100, 48000}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _defaults() -> dict:
    """Baked-in defaults so the app works even without the YAML file."""
    return {
        "capture": {
            "fps": 5, "audio_sample_rate": 16000, "buffer_seconds": 10,
            "window_title_patterns": ["Zoom*", "Google Meet*", "Microsoft Teams*", "*Meet*"],
        },
        "detectors": {
            "deepfake_face": {
                "enabled": True,
                "model_path": str(APP_DATA_DIR / "models" / "deepfake_3dcnn.pth"),
                "window_frames": 16, "threshold_suspicious": 0.50, "threshold_critical": 0.75,
            },
            "voice_mismatch": {
                "enabled": True, "similarity_threshold": 0.45, "enrollment_min_seconds": 30,
                "model": "speechbrain/spkrec-ecapa-voxceleb",
            },
            "lip_sync": {"enabled": True, "confidence_threshold": 0.30, "window_seconds": 2.0},
            "suspicious_nlp": {
                "enabled": True, "model": "sentence-transformers/all-MiniLM-L6-v2",
                "enable_llm_fallback": False,
                "llm": {"provider": "ollama", "model": "mistral:7b", "api_url": "http://localhost:11434"},
            },
            "urgency_language": {"enabled": True, "threshold": 0.60, "use_prosodic": False},
        },
        "diarization": {"enabled": False, "hf_token": ""},
        "fusion": {
            "weights": {"face": 0.30, "voice": 0.25, "lip": 0.15, "nlp": 0.20, "urgency": 0.10},
            "thresholds": {"monitor": 0.20, "suspicious": 0.45, "critical": 0.75},
            "cooldown_seconds": 60,
        },
        "alerting": {
            "desktop_notifications": True, "sound_alert": True, "auto_record_clip": True,
            "clip_length_seconds": 30, "log_sessions": True,
            "webhooks": {
                "slack_url": "", "discord_url": "",
                "email": {"smtp_host": "", "smtp_port": 587, "from_addr": "", "to_addrs": []},
            },
        },
    }


def validate_config(cfg: dict) -> list[str]:
    """Validate config and return warning messages. Raises ConfigError on fatal issues."""
    warnings: list[str] = []
    weights = cfg.get("fusion", {}).get("weights", {})
    required = {"face", "voice", "lip", "nlp", "urgency"}
    missing = required - set(weights.keys())
    if missing:
        raise ConfigError(f"Fusion weights missing keys: {missing}")
    if abs(sum(weights.values()) - 1.0) > 0.01:
        warnings.append(f"Fusion weights sum to {sum(weights.values()):.2f} (expected ~1.0)")

    t = cfg.get("fusion", {}).get("thresholds", {})
    m, s, c = t.get("monitor", 0), t.get("suspicious", 0), t.get("critical", 0)
    if not (m < s < c):
        warnings.append(f"Thresholds not monotonic: {m} < {s} < {c}")

    cap = cfg.get("capture", {})
    fps = cap.get("fps", 0)
    if not isinstance(fps, int) or fps < 1:
        raise ConfigError(f"capture.fps must be positive, got {fps}")
    buf = cap.get("buffer_seconds", 0)
    if buf < 1:
        raise ConfigError(f"capture.buffer_seconds must be >= 1, got {buf}")
    if cap.get("audio_sample_rate", 0) not in VALID_SAMPLE_RATES:
        warnings.append(f"capture.audio_sample_rate {cap.get('audio_sample_rate')} not in {VALID_SAMPLE_RATES}")

    for det_name, det_cfg in cfg.get("detectors", {}).items():
        if isinstance(det_cfg, dict) and det_cfg.get("model_path"):
            if not Path(det_cfg["model_path"]).exists():
                warnings.append(f"Model not found: {det_name}.model_path = {det_cfg['model_path']}")

    cd = cfg.get("fusion", {}).get("cooldown_seconds", 0)
    if cd < 0:
        raise ConfigError(f"fusion.cooldown_seconds must be >= 0, got {cd}")

    return warnings


def load(path: str | Path | None = None, profile: str | None = None) -> dict:
    """Load config — merge YAML file over baked-in defaults, then overlay profile.

    Args:
        path: Optional path to custom YAML config.
        profile: Optional profile name (high-security, balanced, low-resource).

    Raises ConfigError on validation failure, ValueError on unknown profile.
    """
    cfg = _defaults()

    yaml_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if yaml_path.exists() and yaml is not None:
        with open(yaml_path) as f:
            overrides = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, overrides)

    if profile:
        from meetguard.profiles import resolve
        cfg = _deep_merge(cfg, resolve(profile))

    try:
        validate_config(cfg)
    except ConfigError:
        raise
    except Exception as e:
        raise ConfigError(str(e)) from e

    return cfg
