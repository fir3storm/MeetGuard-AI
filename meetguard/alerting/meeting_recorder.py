"""Save short video/audio clips of suspicious meeting segments."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Thread
from typing import Optional

import numpy as np

from meetguard.capture.frame_buffer import RingBuffer


class MeetingRecorder:
    """Maintains a rolling buffer and saves clip on alert.

    Uses a ring buffer of frames + audio, and on trigger writes
    the last N seconds to disk.
    """

    def __init__(self, output_dir: str | Path, clip_length_seconds: int = 30):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.clip_length = clip_length_seconds
        self._frame_buffer: Optional[RingBuffer[np.ndarray]] = None
        self._audio_buffer: Optional[RingBuffer[np.ndarray]] = None

    def set_buffers(self, frame_buf: RingBuffer[np.ndarray], audio_buf: RingBuffer[np.ndarray]) -> None:
        self._frame_buffer = frame_buf
        self._audio_buffer = audio_buf

    def save_clip(self, reason: str = "") -> Optional[Path]:
        """Write the current buffer contents to a timestamped file."""
        if self._frame_buffer is None or self._audio_buffer is None:
            return None

        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_reason = reason.replace(" ", "_")[:32] if reason else "alert"
        clip_dir = self.output_dir / f"{ts}_{safe_reason}"
        clip_dir.mkdir(exist_ok=True)

        # Save frames
        frames = self._frame_buffer.get_all()
        if frames:
            import cv2
            h, w = frames[0].shape[:2]
            video_path = clip_dir / "clip.mp4"
            out = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 5, (w, h))
            for f in frames:
                out.write(f)
            out.release()

        # Save audio
        audio = self._audio_buffer.get_all()
        if audio:
            import soundfile as sf  # type: ignore[import-untyped]
            concat = np.concatenate(audio) if len(audio) > 1 else audio[0]
            audio_path = clip_dir / "clip.wav"
            sf.write(str(audio_path), concat, 16000)

        return clip_dir
