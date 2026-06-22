"""Tests for config validation."""

import pytest
from meetguard.config import validate_config, ConfigError


def test_valid_config(sample_config):
    warnings = validate_config(sample_config)
    assert len(warnings) == 0


def test_missing_weight_key(sample_config):
    del sample_config["fusion"]["weights"]["face"]
    with pytest.raises(ConfigError, match="weights missing keys"):
        validate_config(sample_config)


def test_invalid_fps(sample_config):
    sample_config["capture"]["fps"] = 0
    with pytest.raises(ConfigError, match="fps must be a positive integer"):
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
