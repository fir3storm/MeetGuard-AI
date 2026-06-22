"""Weighted risk aggregation from all 5 detectors."""

from __future__ import annotations

from meetguard.utils.models import AlertLevel, DetectorScores, FusionResult


class RiskAggregator:
    """Combine individual detector scores into a total risk score.

    Uses configurable weights per detector.
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or {
            "face": 0.30,
            "voice": 0.25,
            "lip": 0.15,
            "nlp": 0.20,
            "urgency": 0.10,
        }

    def aggregate(self, scores: DetectorScores) -> float:
        """Compute weighted total risk score [0, 1]."""
        total = (
            scores.face * self.weights.get("face", 0) +
            scores.voice * self.weights.get("voice", 0) +
            scores.lip * self.weights.get("lip", 0) +
            scores.nlp * self.weights.get("nlp", 0) +
            scores.urgency * self.weights.get("urgency", 0)
        )
        return min(1.0, max(0.0, total))
