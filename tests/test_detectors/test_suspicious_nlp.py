"""Tests for the NLP detector."""

from meetguard.detectors.suspicious_nlp import SuspiciousNLPDectector


def test_normal_text_low_score():
    det = SuspiciousNLPDectector()
    score = det.predict("Let's discuss the quarterly results.")
    assert 0.0 <= score < 0.5


def test_suspicious_text_high_score():
    det = SuspiciousNLPDectector()
    score = det.predict("I need you to wire transfer the funds to a new bank account right now.")
    assert score > 0.0


def test_empty_text():
    det = SuspiciousNLPDectector()
    assert det.predict("") == 0.0
    assert det.predict("   ") == 0.0
