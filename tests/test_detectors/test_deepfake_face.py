"""Tests for the deepfake face detector."""

import numpy as np
import pytest

from meetguard.detectors.deepfake_face import DeepfakeFaceDetector


def test_detector_returns_float():
    det = DeepfakeFaceDetector()
    dummy_crops = [np.zeros((224, 224, 3), dtype=np.uint8)] * 16
    score = det.predict(dummy_crops)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_detector_empty_input():
    det = DeepfakeFaceDetector()
    assert det.predict([]) == 0.0


def test_detector_less_than_window():
    det = DeepfakeFaceDetector()
    crops = [np.zeros((224, 224, 3), dtype=np.uint8)] * 3
    score = det.predict(crops)
    assert 0.0 <= score <= 1.0
