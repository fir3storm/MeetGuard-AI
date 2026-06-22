"""Cross-platform screen capture using MSS (fast, 30+ FPS capable)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event, Thread
from typing import Callable, Optional

import cv2
import numpy as np
import numpy.typing as npt

try:
    import mss
    import mss.tools
except ImportError:
    mss = None  # type: ignore[assignment]


FrameBuffer = npt.NDArray[np.uint8]  # shape (H, W, 3) in BGR


@dataclass
class CaptureConfig:
    fps: int = 5
    region: tuple[int, int, int, int] | None = None  # left, top, width, height


class ScreenCapture:
    """Captures a monitor or a specific screen region.

    Callbacks receive BGR frames at the configured FPS.
    """

    def __init__(self, config: CaptureConfig | None = None, logger=None):
        self.config = config or CaptureConfig()
        self._running = Event()
        self._thread: Thread | None = None
        self._on_frame: Callable[[FrameBuffer], None] | None = None
        self._log = logger or __import__("logging").getLogger(__name__)
        self._last_frame: FrameBuffer | None = None

    @property
    def last_frame(self) -> FrameBuffer | None:
        return self._last_frame

    def start(self, on_frame: Callable[[FrameBuffer], None]) -> None:
        """Begin capturing in a background thread."""
        if self._running.is_set():
            return
        self._on_frame = on_frame
        self._running.set()
        self._thread = Thread(target=self._loop, daemon=True, name="screen-capture")
        self._thread.start()
        self._log.info("Screen capture started at %d FPS", self.config.fps)

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=3)
        self._log.info("Screen capture stopped")

    def _loop(self) -> None:
        if mss is None:
            self._log.error("mss not installed — screen capture unavailable")
            return

        interval = 1.0 / max(self.config.fps, 1)
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            region = self.config.region
            bbox: dict = (
                {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
                if region
                else {"left": monitor["left"], "top": monitor["top"],
                      "width": monitor["width"], "height": monitor["height"]}
            )

            while self._running.is_set():
                t0 = time.perf_counter()
                raw = sct.grab(bbox)
                frame: FrameBuffer = np.array(raw)[:, :, :3]  # BGRA → BGR
                self._last_frame = frame
                if self._on_frame:
                    try:
                        self._on_frame(frame)
                    except Exception:
                        self._log.exception("frame callback error")
                elapsed = time.perf_counter() - t0
                sleep = max(0, interval - elapsed)
                if sleep > 0:
                    time.sleep(sleep)

    def grab_one(self) -> FrameBuffer | None:
        """Synchronous grab — useful for testing."""
        if mss is None:
            return None
        with mss.mss() as sct:
            mon = sct.monitors[1]
            raw = sct.grab(mon)
            return np.array(raw)[:, :, :3]
