"""Real-time speech-to-text via faster-whisper."""

from __future__ import annotations

from typing import Callable, Optional

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]

import numpy as np
import numpy.typing as npt

AudioChunk = npt.NDArray[np.float32]


class Transcriber:
    """Runs faster-whisper on audio chunks and fires callbacks with text segments."""

    def __init__(self, model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8"):
        self._model: Optional[WhisperModel] = None  # type: ignore[arg-type]
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._buffer: list[float] = []

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        if WhisperModel is None:
            raise RuntimeError("faster-whisper not installed")
        self._model = WhisperModel(self._model_size, device=self._device, compute_type=self._compute_type)

    def transcribe(self, audio: AudioChunk) -> str:
        """Transcribe an audio chunk immediately. Returns full text."""
        self._ensure_model()
        if self._model is None:
            return ""
        segments, _ = self._model.transcribe(audio, beam_size=1)
        return " ".join(seg.text for seg in segments).strip()

    def transcribe_streaming(self, audio: AudioChunk, on_text: Callable[[str], None]) -> None:
        """Buffer audio and fire *on_text* when new speech is detected."""
        self._buffer.extend(audio.tolist())
        # Only run inference when we have ~3s of audio
        if len(self._buffer) >= 16000 * 3:
            chunk = np.array(self._buffer, dtype=np.float32)
            self._buffer = []
            text = self.transcribe(chunk)
            if text:
                on_text(text)
