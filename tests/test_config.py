"""Tests for config validation and profiles."""

import pytest
from meetguard.config import validate_config, ConfigError, load


def test_valid_config(sample_config):
    warnings = validate_config(sample_config)
    assert len(warnings) == 0


def test_missing_weight_key(sample_config):
    del sample_config["fusion"]["weights"]["face"]
    with pytest.raises(ConfigError, match="weights missing keys"):
        validate_config(sample_config)


def test_invalid_fps(sample_config):
    sample_config["capture"]["fps"] = 0
    with pytest.raises(ConfigError, match="fps must be positive"):
        validate_config(sample_config)


def test_invalid_buffer(sample_config):
    sample_config["capture"]["buffer_seconds"] = 0
    with pytest.raises(ConfigError, match="buffer_seconds must be >= 1"):
        validate_config(sample_config)


def test_non_monotonic_thresholds(sample_config):
    sample_config["fusion"]["thresholds"]["monitor"] = 0.8
    warnings = validate_config(sample_config)
    assert any("monotonic" in w for w in warnings)


def test_negative_cooldown(sample_config):
    sample_config["fusion"]["cooldown_seconds"] = -1
    with pytest.raises(ConfigError, match="cooldown_seconds must be >= 0"):
        validate_config(sample_config)


def test_bad_sample_rate(sample_config):
    sample_config["capture"]["audio_sample_rate"] = 12345
    warnings = validate_config(sample_config)
    assert any("audio_sample_rate" in w for w in warnings)


def test_diarization_default_disabled(sample_config):
    assert "diarization" in sample_config
    assert sample_config["diarization"]["enabled"] is False


# ── Profiles ─────────────────────────────────────────────────────────────


def test_profile_balanced_returns_empty():
    from meetguard.profiles import resolve
    assert resolve(None) == {}
    assert resolve("balanced") == {}


def test_profile_high_security():
    from meetguard.profiles import resolve
    profile = resolve("high-security")
    assert profile["capture"]["fps"] == 15
    assert profile["fusion"]["thresholds"]["critical"] == 0.60


def test_profile_low_resource():
    from meetguard.profiles import resolve
    profile = resolve("low-resource")
    assert profile["capture"]["fps"] == 3
    assert profile["detectors"]["lip_sync"]["enabled"] is False


def test_profile_unknown():
    from meetguard.profiles import resolve
    with pytest.raises(ValueError, match="Unknown profile"):
        resolve("invalid")


def test_load_with_profile():
    cfg = load(profile="high-security")
    assert cfg["capture"]["fps"] == 15
    assert cfg["fusion"]["thresholds"]["critical"] == 0.60
