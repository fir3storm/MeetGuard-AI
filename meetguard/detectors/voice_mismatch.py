"""Voice mismatch detection via ECAPA-TDNN voiceprint comparison.

Compares current speaker's embedding against all enrolled voiceprints.
Returns a mismatch score where higher = more suspicious.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import numpy.typing as npt

from meetguard.processing.voiceprint_manager import VoiceprintManager

AudioChunk = npt.NDArray[np.float32]


class VoiceMismatchDetector:
    """Detect if the current speaker doesn't match any enrolled voiceprint.

    score = 1.0 - best_similarity
    So 0 = perfect match, 1 = complete mismatch.
    """

    def __init__(self, vp_manager: VoiceprintManager, similarity_threshold: float = 0.45):
        self.vp = vp_manager
        self.threshold = similarity_threshold

    def predict(self, audio: AudioChunk) -> float:
        """Run voice mismatch detection on an audio chunk.

        Returns score 0.0 (match) – 1.0 (mismatch).
        Returns 0.0 if no voiceprints enrolled (can't detect).
        """
        enrolled = self.vp.db.list_all()
        if not enrolled:
            return 0.0  # no voiceprints to compare against

        _, sim = self.vp.best_match(audio, threshold=self.threshold)
        # Convert similarity to a mismatch score
        mismatch = max(0.0, 1.0 - sim)
        return min(1.0, mismatch)
