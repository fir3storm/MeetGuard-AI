"""Tests for the urgency language detector."""

from meetguard.detectors.urgency_language import UrgencyLanguageDetector


def test_normal_text():
    det = UrgencyLanguageDetector()
    assert det.predict("Let's review the presentation.") == 0.0


def test_urgent_text():
    det = UrgencyLanguageDetector()
    score = det.predict("Transfer now, don't tell anyone about this transaction.")
    assert score > 0.5
    assert score <= 1.0


def test_empty():
    det = UrgencyLanguageDetector()
    assert det.predict("") == 0.0
