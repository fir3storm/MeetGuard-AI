"""Classify total risk into threat levels."""

from __future__ import annotations

from meetguard.utils.models import AlertLevel


class ThreatClassifier:
    """Map a total_risk score to an AlertLevel."""

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = thresholds or {
            "monitor": 0.20,
            "suspicious": 0.45,
            "critical": 0.75,
        }

    def classify(self, total_risk: float) -> AlertLevel:
        if total_risk >= self.thresholds.get("critical", 0.75):
            return AlertLevel.CRITICAL
        if total_risk >= self.thresholds.get("suspicious", 0.45):
            return AlertLevel.SUSPICIOUS
        if total_risk >= self.thresholds.get("monitor", 0.20):
            return AlertLevel.MONITOR
        return AlertLevel.SAFE
