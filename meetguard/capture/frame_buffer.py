"""Thread-safe ring buffer for frames and audio chunks — with backpressure."""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


class RingBuffer(Generic[T]):
    """A thread-safe fixed-size ring buffer.

    Supports optional backpressure: `push_with_backpressure()` drops the
    oldest item if the buffer is full and returns False.
    """

    def __init__(self, maxlen: int):
        self._buf: deque[T] = deque(maxlen=maxlen)
        self._lock = Lock()

    @property
    def maxlen(self) -> int:
        return self._buf.maxlen

    @property
    def fill_ratio(self) -> float:
        """Return 0.0–1.0 indicating how full the buffer is."""
        with self._lock:
            return len(self._buf) / self._buf.maxlen if self._buf.maxlen else 0.0

    def push(self, item: T) -> None:
        with self._lock:
            self._buf.append(item)

    def push_with_backpressure(self, item: T) -> bool:
        """Push item, dropping oldest if full.

        Returns True if push succeeded, False if buffer was full (item dropped).
        """
        with self._lock:
            dropped = len(self._buf) >= self._buf.maxlen
            self._buf.append(item)
            return not dropped

    def extend(self, items: list[T]) -> None:
        with self._lock:
            for it in items:
                self._buf.append(it)

    def get_all(self) -> list[T]:
        with self._lock:
            return list(self._buf)

    def get_last(self, n: int) -> list[T]:
        with self._lock:
            total = len(self._buf)
            if n >= total:
                return list(self._buf)
            return [self._buf[i] for i in range(total - n, total)]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def __repr__(self) -> str:
        with self._lock:
            return f"RingBuffer({len(self._buf)}/{self._buf.maxlen})"


def time_to_frames(seconds: float, fps: float) -> int:
    return int(seconds * fps)


def frames_to_time(frames: int, fps: float) -> float:
    return frames / fps
