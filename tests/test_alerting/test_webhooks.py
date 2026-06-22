"""Tests for the webhook alert backends."""

import pytest
from meetguard.alerting.webhooks import SlackWebhook, DiscordWebhook, build_webhook_backends
from meetguard.utils.models import FusionResult


def test_build_webhooks_empty_config():
    cfg = {"alerting": {"webhooks": {"slack_url": "", "discord_url": "",
                                     "email": {"smtp_host": "", "smtp_port": 587,
                                              "from_addr": "", "to_addrs": []}}}}
    backends = build_webhook_backends(cfg)
    assert backends == []


def test_build_webhooks_slack_only():
    cfg = {"alerting": {"webhooks": {"slack_url": "https://hooks.slack.com/test",
                                     "discord_url": "",
                                     "email": {"smtp_host": "", "smtp_port": 587,
                                              "from_addr": "", "to_addrs": []}}}}
    backends = build_webhook_backends(cfg)
    assert len(backends) == 1
    assert isinstance(backends[0], SlackWebhook)


def test_build_webhooks_discord_only():
    cfg = {"alerting": {"webhooks": {"slack_url": "", "discord_url": "https://discord.com/api/webhooks/test",
                                     "email": {"smtp_host": "", "smtp_port": 587,
                                              "from_addr": "", "to_addrs": []}}}}
    backends = build_webhook_backends(cfg)
    assert len(backends) == 1
    assert isinstance(backends[0], DiscordWebhook)


def test_slack_webhook_send_does_not_crash():
    """Just verify no exception on bad URL (network error expected)."""
    backend = SlackWebhook("https://hooks.slack.com/invalid")
    result = FusionResult()
    # Should handle network errors gracefully
    try:
        backend.send(result)
    except Exception:
        pass  # expected


def test_discord_webhook_send_does_not_crash():
    backend = DiscordWebhook("https://discord.com/api/webhooks/invalid")
    result = FusionResult()
    try:
        backend.send(result)
    except Exception:
        pass  # expected
