"""Configuration profiles for MeetGuard AI.

Each profile is a partial overlay merged on top of the base config.
Only keys specified in the profile override — everything else stays from YAML.
"""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "high-security": {
        "capture": {"fps": 15, "buffer_seconds": 20, "audio_sample_rate": 44100},
        "detectors": {
            "deepfake_face": {
                "enabled": True, "window_frames": 32,
                "threshold_suspicious": 0.30, "threshold_critical": 0.60,
            },
            "voice_mismatch": {"enabled": True, "similarity_threshold": 0.35},
            "lip_sync": {"enabled": True, "confidence_threshold": 0.20},
            "suspicious_nlp": {"enabled": True, "enable_llm_fallback": True},
            "urgency_language": {"enabled": True, "threshold": 0.40, "use_prosodic": True},
        },
        "fusion": {
            "weights": {"face": 0.25, "voice": 0.25, "lip": 0.20, "nlp": 0.20, "urgency": 0.10},
            "thresholds": {"monitor": 0.10, "suspicious": 0.30, "critical": 0.60},
            "cooldown_seconds": 30,
        },
        "alerting": {"clip_length_seconds": 60},
        "diarization": {"enabled": True},
    },
    "balanced": {},
    "low-resource": {
        "capture": {"fps": 3, "buffer_seconds": 6},
        "detectors": {
            "deepfake_face": {
                "enabled": True, "window_frames": 8,
                "threshold_suspicious": 0.60, "threshold_critical": 0.85,
            },
            "voice_mismatch": {"enabled": True, "similarity_threshold": 0.55},
            "lip_sync": {"enabled": False},
            "suspicious_nlp": {"enabled": True, "enable_llm_fallback": False},
            "urgency_language": {"enabled": True, "threshold": 0.70},
        },
        "fusion": {
            "weights": {"face": 0.40, "voice": 0.30, "lip": 0.0, "nlp": 0.20, "urgency": 0.10},
            "thresholds": {"monitor": 0.30, "suspicious": 0.55, "critical": 0.85},
            "cooldown_seconds": 120,
        },
        "alerting": {"desktop_notifications": False, "sound_alert": False, "clip_length_seconds": 15},
        "diarization": {"enabled": False},
    },
}


def resolve(profile_name: str | None) -> dict[str, Any]:
    """Return the profile overlay dict (empty if None or 'balanced')."""
    if not profile_name or profile_name == "balanced":
        return {}
    if profile_name not in PROFILES:
        valid = ", ".join(PROFILES.keys())
        raise ValueError(f"Unknown profile '{profile_name}'. Valid: {valid}")
    return PROFILES[profile_name]
