"""System audio loopback capture via sounddevice.

On Windows requires VB-Cable virtual audio device (or similar)
so that meeting audio (not mic) is captured.
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from threading import Event, Thread
from typing import Callable, Optional

import numpy as np
import numpy.typing as npt

try:
    import sounddevice as sd
except ImportError:
    sd = None  # type: ignore[assignment]


AudioBuffer = npt.NDArray[np.float32]  # shape (N,) mono 16 kHz


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    device: int | None = None      # None = default input (loopback device)
    blocksize: int = 4096          # frames per callback


class AudioCapture:
    """Captures system audio loopback.

    On Windows, set *device* to the VB-Cable virtual input.
    On macOS, use BlackHole.
    On Linux, use PulseAudio monitor.
    """

    def __init__(self, config: AudioConfig | None = None, logger=None):
        self.config = config or AudioConfig()
        self._running = Event()
        self._thread: Thread | None = None
        self._on_audio: Callable[[AudioBuffer], None] | None = None
        self._buffer: queue.Queue[AudioBuffer] = queue.Queue()
        self._log = logger or __import__("logging").getLogger(__name__)

    def start(self, on_audio: Callable[[AudioBuffer], None]) -> None:
        if self._running.is_set():
            return
        if sd is None:
            self._log.error("sounddevice not installed — audio capture unavailable")
            return
        self._on_audio = on_audio
        self._running.set()
        self._thread = Thread(target=self._loop, daemon=True, name="audio-capture")
        self._thread.start()
        self._log.info("Audio capture started (device=%s, %d Hz)",
                       self.config.device, self.config.sample_rate)

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=3)
        self._log.info("Audio capture stopped")

    def _loop(self) -> None:
        def callback(indata: np.ndarray, _frames: int, _time_info, _status) -> None:
            if self._running.is_set():
                mono = indata.mean(axis=1).astype(np.float32) if indata.ndim > 1 else indata
                self._buffer.put(mono)

        with sd.InputStream(
            samplerate=self.config.sample_rate,
            device=self.config.device,
            blocksize=self.config.blocksize,
            channels=1,
            callback=callback,
            dtype=np.float32,
        ):
            while self._running.is_set():
                try:
                    chunk = self._buffer.get(timeout=0.5)
                    if self._on_audio:
                        self._on_audio(chunk)
                except queue.Empty:
                    continue

    def list_devices(self) -> str:
        """Return a formatted list of audio devices for the user to choose from."""
        if sd is None:
            return "sounddevice not installed"
        info = sd.query_devices()
        lines = [f"{i}: {d['name']} (in:{d['max_input_channels']}, out:{d['max_output_channels']})"
                 for i, d in enumerate(info)]
        return "\n".join(lines)
