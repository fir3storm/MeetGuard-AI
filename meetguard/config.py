"""YAML config loader with validation, defaults, and runtime overrides."""

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
            "fps": 5,
            "audio_sample_rate": 16000,
            "buffer_seconds": 10,
            "window_title_patterns": [
                "Zoom*",
                "Google Meet*",
                "Microsoft Teams*",
                "*Meet*",
            ],
        },
        "detectors": {
            "deepfake_face": {
                "enabled": True,
                "model_path": str(APP_DATA_DIR / "models" / "deepfake_3dcnn.pth"),
                "window_frames": 16,
                "threshold_suspicious": 0.50,
                "threshold_critical": 0.75,
            },
            "voice_mismatch": {
                "enabled": True,
                "similarity_threshold": 0.45,
                "enrollment_min_seconds": 30,
                "model": "speechbrain/spkrec-ecapa-voxceleb",
            },
            "lip_sync": {
                "enabled": True,
                "confidence_threshold": 0.30,
                "window_seconds": 2.0,
            },
            "suspicious_nlp": {
                "enabled": True,
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "enable_llm_fallback": False,
                "llm": {
                    "provider": "ollama",
                    "model": "mistral:7b",
                    "api_url": "http://localhost:11434",
                },
            },
            "urgency_language": {
                "enabled": True,
                "threshold": 0.60,
                "use_prosodic": False,
            },
        },
        "fusion": {
            "weights": {"face": 0.30, "voice": 0.25, "lip": 0.15, "nlp": 0.20, "urgency": 0.10},
            "thresholds": {"monitor": 0.20, "suspicious": 0.45, "critical": 0.75},
            "cooldown_seconds": 60,
        },
        "alerting": {
            "desktop_notifications": True,
            "sound_alert": True,
            "auto_record_clip": True,
            "clip_length_seconds": 30,
            "log_sessions": True,
            "webhooks": {
                "slack_url": "",
                "discord_url": "",
                "email": {
                    "smtp_host": "",
                    "smtp_port": 587,
                    "from_addr": "",
                    "to_addrs": [],
                },
            },
        },
    }


def validate_config(cfg: dict) -> list[str]:
    """Validate config and return list of warning messages.

    Raises ConfigError on fatal issues.
    """
    warnings: list[str] = []

    # ── weights ────────────────────────────────────────────────────
    weights = cfg.get("fusion", {}).get("weights", {})
    required_weights = {"face", "voice", "lip", "nlp", "urgency"}
    missing = required_weights - set(weights.keys())
    if missing:
        raise ConfigError(f"Fusion weights missing keys: {missing}")
    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        warnings.append(f"Fusion weights sum to {weight_sum:.2f} (expected ~1.0)")

    # ── thresholds ─────────────────────────────────────────────────
    thresh = cfg.get("fusion", {}).get("thresholds", {})
    m = thresh.get("monitor", 0)
    s = thresh.get("suspicious", 0)
    c = thresh.get("critical", 0)
    if not (m < s < c):
        warnings.append(f"Thresholds not monotonic: monitor={m} < suspicious={s} < critical={c}")

    # ── capture ────────────────────────────────────────────────────
    cap = cfg.get("capture", {})
    fps = cap.get("fps", 0)
    if not isinstance(fps, int) or fps < 1:
        raise ConfigError(f"capture.fps must be a positive integer, got {fps}")
    buf = cap.get("buffer_seconds", 0)
    if not isinstance(buf, (int, float)) or buf < 1:
        raise ConfigError(f"capture.buffer_seconds must be >= 1, got {buf}")
    sr = cap.get("audio_sample_rate", 0)
    if sr not in VALID_SAMPLE_RATES:
        warnings.append(f"capture.audio_sample_rate {sr} not in standard set {VALID_SAMPLE_RATES}")

    # ── model paths ─────────────────────────────────────────────────
    for det_name, det_cfg in cfg.get("detectors", {}).items():
        if not isinstance(det_cfg, dict):
            continue
        model_path = det_cfg.get("model_path", "")
        if model_path and not Path(model_path).exists():
            warnings.append(f"Model not found: {det_name}.model_path = {model_path}")

    # ── cooldown ───────────────────────────────────────────────────
    cd = cfg.get("fusion", {}).get("cooldown_seconds", 0)
    if not isinstance(cd, (int, float)) or cd < 0:
        raise ConfigError(f"fusion.cooldown_seconds must be >= 0, got {cd}")

    return warnings


def load(path: str | Path | None = None) -> dict:
    """Load config — merge YAML file over baked-in defaults.

    Raises ConfigError on validation failure.
    """
    cfg = _defaults()

    yaml_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if yaml_path.exists() and yaml is not None:
        with open(yaml_path) as f:
            overrides = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, overrides)

    # Validate
    try:
        validate_config(cfg)
    except ConfigError:
        raise
    except Exception as e:
        raise ConfigError(str(e)) from e

    return cfg


# ── typed access helpers ──────────────────────────────────────────────

def get(cfg: dict, *keys: str, default: Any = None) -> Any:
    """Safely drill into nested dict, e.g. get(cfg, 'detectors', 'deepfake_face', 'threshold')."""
    cur: Any = cfg
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur
