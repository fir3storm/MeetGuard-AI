"""Tests for all detectors."""

import numpy as np
import pytest

from meetguard.detectors.deepfake_face import DeepfakeFaceDetector
from meetguard.detectors.suspicious_nlp import SuspiciousNLPDectector
from meetguard.detectors.urgency_language import UrgencyLanguageDetector
from meetguard.detectors.voice_mismatch import VoiceMismatchDetector
from meetguard.detectors.lip_sync import LipSyncDetector


class TestDeepfakeFace:
    def test_returns_float(self, sample_face_crops):
        det = DeepfakeFaceDetector()
        score = det.predict(sample_face_crops)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_empty_input(self):
        det = DeepfakeFaceDetector()
        assert det.predict([]) == 0.0

    def test_less_than_window(self):
        det = DeepfakeFaceDetector()
        crops = [np.zeros((224, 224, 3), dtype=np.uint8)] * 3
        score = det.predict(crops)
        assert 0.0 <= score <= 1.0


class TestSuspiciousNLP:
    def test_normal_text_low_score(self):
        det = SuspiciousNLPDectector()
        score = det.predict("Let's discuss the quarterly results.")
        assert 0.0 <= score < 0.5

    def test_suspicious_text_high_score(self):
        det = SuspiciousNLPDectector()
        score = det.predict("I need you to wire transfer the funds to a new bank account right now.")
        assert score > 0.0

    def test_empty_text(self):
        det = SuspiciousNLPDectector()
        assert det.predict("") == 0.0
        assert det.predict("   ") == 0.0


class TestUrgencyLanguage:
    def test_normal_text(self):
        det = UrgencyLanguageDetector()
        assert det.predict("Let's review the presentation.") == 0.0

    def test_urgent_text(self):
        det = UrgencyLanguageDetector()
        score = det.predict("Transfer now, don't tell anyone about this transaction.")
        assert score > 0.5
        assert score <= 1.0

    def test_empty(self):
        det = UrgencyLanguageDetector()
        assert det.predict("") == 0.0


class TestVoiceMismatch:
    def test_no_enrolled_returns_zero(self):
        from meetguard.processing.voiceprint_manager import VoiceprintManager
        vp = VoiceprintManager()
        det = VoiceMismatchDetector(vp)
        assert det.predict(np.zeros(16000, dtype=np.float32)) == 0.0


class TestLipSync:
    def test_empty_returns_safe(self):
        det = LipSyncDetector()
        score = det.predict(np.zeros((224, 224, 3), dtype=np.uint8),
                            np.zeros(16000, dtype=np.float32))
        # Should return something in range without crashing
        assert 0.0 <= score <= 1.0
