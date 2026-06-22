"""Webhook alert backends for Slack, Discord, and Email.

Each backend implements the AlertBackend protocol:
    def send(self, result: FusionResult) -> None
"""

from __future__ import annotations

import json
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from typing import Any

import requests

from meetguard.utils.models import FusionResult


class AlertBackend(ABC):
    """Protocol for webhook alert backends."""

    @abstractmethod
    def send(self, result: FusionResult) -> None:
        ...


class SlackWebhook(AlertBackend):
    """Send alerts to a Slack channel via Incoming Webhook."""

    def __init__(self, url: str):
        self.url = url

    def send(self, result: FusionResult) -> None:
        level_emoji = {
            "CRITICAL": "🚨",
            "SUSPICIOUS": "⚠️",
            "MONITOR": "👀",
        }
        emoji = level_emoji.get(result.level.value, "")
        payload = {
            "text": f"{emoji} *MeetGuard Alert: {result.level.value}*\n"
                    f"• Total Risk: `{result.total_risk:.2f}`\n"
                    f"• Face: `{result.scores.face:.2f}` | Voice: `{result.scores.voice:.2f}`\n"
                    f"• Lip-Sync: `{result.scores.lip:.2f}` | NLP: `{result.scores.nlp:.2f}`\n"
                    f"• Urgency: `{result.scores.urgency:.2f}`\n"
                    f"• Session: `{result.session_id}` @ `{result.timestamp.strftime('%H:%M:%S')}`",
        }
        requests.post(self.url, json=payload, timeout=10)


class DiscordWebhook(AlertBackend):
    """Send alerts to a Discord channel via Webhook."""

    def __init__(self, url: str):
        self.url = url

    def send(self, result: FusionResult) -> None:
        color = {"CRITICAL": 0xFF0000, "SUSPICIOUS": 0xFFA500, "MONITOR": 0xFFFF00}.get(result.level.value, 0x00FF00)
        embed = {
            "title": f"MeetGuard Alert: {result.level.value}",
            "color": color,
            "fields": [
                {"name": "Total Risk", "value": f"{result.total_risk:.2f}", "inline": True},
                {"name": "Face", "value": f"{result.scores.face:.2f}", "inline": True},
                {"name": "Voice", "value": f"{result.scores.voice:.2f}", "inline": True},
                {"name": "Lip-Sync", "value": f"{result.scores.lip:.2f}", "inline": True},
                {"name": "NLP", "value": f"{result.scores.nlp:.2f}", "inline": True},
                {"name": "Urgency", "value": f"{result.scores.urgency:.2f}", "inline": True},
            ],
            "footer": {"text": f"Session: {result.session_id}"},
            "timestamp": result.timestamp.isoformat(),
        }
        payload = {"embeds": [embed]}
        requests.post(self.url, json=payload, timeout=10)


class EmailAlert(AlertBackend):
    """Send alerts via SMTP email."""

    def __init__(self, smtp_host: str, smtp_port: int, from_addr: str,
                 to_addrs: list[str], username: str = "", password: str = ""):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.username = username
        self.password = password

    def send(self, result: FusionResult) -> None:
        if not self.to_addrs:
            return
        body = (
            f"MeetGuard Alert: {result.level.value}\n"
            f"{'=' * 40}\n"
            f"Time:       {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Session:    {result.session_id}\n"
            f"Total Risk: {result.total_risk:.2f}\n"
            f"\nDetector Scores:\n"
            f"  Face Deepfake:  {result.scores.face:.2f}\n"
            f"  Voice Mismatch: {result.scores.voice:.2f}\n"
            f"  Lip-Sync Drift: {result.scores.lip:.2f}\n"
            f"  Suspicious NLP: {result.scores.nlp:.2f}\n"
            f"  Urgency Lang:   {result.scores.urgency:.2f}\n"
        )
        msg = MIMEText(body)
        msg["Subject"] = f"[MeetGuard] {result.level.value} — Risk {result.total_risk:.2f}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.username:
                server.starttls()
                server.login(self.username, self.password)
            server.sendmail(self.from_addr, self.to_addrs, msg.as_string())


def build_webhook_backends(cfg: dict) -> list[AlertBackend]:
    """Instantiate webhook backends from config."""
    backends: list[AlertBackend] = []
    wh = cfg.get("alerting", {}).get("webhooks", {})

    slack_url = wh.get("slack_url", "")
    if slack_url:
        backends.append(SlackWebhook(slack_url))

    discord_url = wh.get("discord_url", "")
    if discord_url:
        backends.append(DiscordWebhook(discord_url))

    email_cfg = wh.get("email", {})
    if email_cfg.get("smtp_host") and email_cfg.get("to_addrs"):
        backends.append(EmailAlert(
            smtp_host=email_cfg["smtp_host"],
            smtp_port=email_cfg.get("smtp_port", 587),
            from_addr=email_cfg.get("from_addr", ""),
            to_addrs=email_cfg.get("to_addrs", []),
            username=email_cfg.get("username", ""),
            password=email_cfg.get("password", ""),
        ))

    return backends
