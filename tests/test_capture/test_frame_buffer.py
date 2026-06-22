"""Tests for the capture layer."""

import numpy as np
import pytest

from meetguard.capture.frame_buffer import RingBuffer, time_to_frames, frames_to_time


class TestRingBuffer:
    def test_push_and_get_all(self):
        buf = RingBuffer[int](maxlen=5)
        for i in range(10):
            buf.push(i)
        assert buf.get_all() == [5, 6, 7, 8, 9]

    def test_get_last(self):
        buf = RingBuffer[int](maxlen=10)
        for i in range(10):
            buf.push(i)
        assert buf.get_last(3) == [7, 8, 9]

    def test_get_last_less_than_total(self):
        buf = RingBuffer[int](maxlen=10)
        buf.push(1)
        buf.push(2)
        assert buf.get_last(5) == [1, 2]

    def test_clear(self):
        buf = RingBuffer[int](maxlen=5)
        buf.push(1)
        buf.clear()
        assert len(buf) == 0

    def test_fill_ratio(self):
        buf = RingBuffer[int](maxlen=10)
        assert buf.fill_ratio == 0.0
        for i in range(5):
            buf.push(i)
        assert buf.fill_ratio == 0.5

    def test_backpressure_returns_true_when_not_full(self):
        buf = RingBuffer[int](maxlen=5)
        assert buf.push_with_backpressure(1) is True
        assert buf.push_with_backpressure(2) is True

    def test_backpressure_returns_false_when_full(self):
        buf = RingBuffer[int](maxlen=3)
        buf.push(1)
        buf.push(2)
        buf.push(3)
        result = buf.push_with_backpressure(4)
        assert result is False  # dropped oldest
        assert buf.get_all() == [2, 3, 4]

    def test_time_conversions(self):
        assert time_to_frames(2.0, 5) == 10
        assert frames_to_time(10, 5) == 2.0
        assert time_to_frames(0, 5) == 0


class TestWindowSelector:
    def test_find_no_meeting(self):
        from meetguard.capture.window_selector import find_meeting_window
        result = find_meeting_window(["NoMatch*"])
        assert result is None


class TestScreenCaptureFPS:
    def test_measured_fps_returns_default_when_no_frames(self):
        try:
            import cv2
        except ImportError:
            import pytest
            pytest.skip("opencv-python not installed")
        from meetguard.capture.screen_capture import ScreenCapture, CaptureConfig
        cap = ScreenCapture(CaptureConfig(fps=10))
        assert cap.measured_fps == 10.0
