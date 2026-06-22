"""Urgency language detector.

Scores transcribed speech for pressure tactics commonly used in
CEO fraud / whaling attacks: "transfer now", "don't tell anyone",
"new account number", etc.
"""

from __future__ import annotations

import re
from typing import Optional

import numpy as np

# ── Lexical urgency patterns with weights ─────────────────────────────

URGENCY_PATTERNS: list[tuple[str, float]] = [
    ("transfer now", 0.9),
    ("right away", 0.7),
    ("don't tell anyone", 1.0),
    ("do not tell anyone", 1.0),
    ("keep this confidential", 0.8),
    ("keep this quiet", 0.8),
    ("new account number", 0.8),
    ("update the routing", 0.7),
    ("this is urgent", 0.6),
    ("immediately", 0.5),
    ("asap", 0.5),
    ("as soon as possible", 0.5),
    ("the ceo requested", 0.8),
    ("the board instructed", 0.6),
    ("confidential matter", 0.7),
    ("confidential deal", 0.7),
    ("this stays between us", 0.9),
    ("no one else knows", 0.7),
    ("act now", 0.7),
    ("time sensitive", 0.6),
    ("urgent action", 0.7),
    ("don't question", 0.8),
    ("just do it", 0.6),
    ("bypass the process", 0.9),
    ("skip the usual", 0.8),
    ("exception to policy", 0.7),
    ("override", 0.5),
]

COMPILED_URGENCY = [(re.compile(re.escape(p), re.IGNORECASE), w) for p, w in URGENCY_PATTERNS]


class UrgencyLanguageDetector:
    """Score transcribed text for urgency/pressure language.

    score: 0.0 (normal) → 1.0 (very urgent / pressure).
    """

    def __init__(self, threshold: float = 0.60, use_prosodic: bool = False):
        self.threshold = threshold
        self.use_prosodic = use_prosodic  # Phase 2: audio-based prosodic analysis

    def predict(self, text: str) -> float:
        """Score text for urgency language.

        Returns score 0.0 – 1.0.
        """
        if not text or not text.strip():
            return 0.0

        text_lower = text.lower()
        found: list[float] = []
        for pattern, weight in COMPILED_URGENCY:
            if pattern.search(text_lower):
                found.append(weight)

        if not found:
            return 0.0

        # Weighted aggregation: highest urgency + average boost
        max_weight = max(found)
        avg_weight = np.mean(found)
        score = max_weight * 0.7 + avg_weight * 0.3
        return min(1.0, score)
