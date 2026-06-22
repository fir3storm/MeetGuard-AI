"""Alert cooldown and escalation rules."""

from __future__ import annotations

import time
from collections import defaultdict

from meetguard.utils.models import AlertLevel


class AlertRules:
    """Suppress duplicate alerts within a cooldown window.

    Prevents alert fatigue during sustained deepfake attacks.
    """

    def __init__(self, cooldown_seconds: float = 60.0):
        self.cooldown = cooldown_seconds
        self._last_alert: dict[str, float] = defaultdict(float)  # detector_name → timestamp

    def should_alert(self, level: AlertLevel, detector_name: str = "") -> bool:
        """Return True if this alert should be fired (not suppressed)."""
        now = time.time()
        if level != AlertLevel.CRITICAL:
            return True  # only cooldown critical alerts

        key = detector_name or "generic"
        if now - self._last_alert.get(key, 0) < self.cooldown:
            return False
        self._last_alert[key] = now
        return True

    def reset(self) -> None:
        self._last_alert.clear()
