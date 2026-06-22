"""Speaker diarization to isolate who is speaking when."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import numpy.typing as npt

try:
    from pyannote.audio import Pipeline
except ImportError:
    Pipeline = None  # type: ignore[assignment,misc]


AudioChunk = npt.NDArray[np.float32]


class AudioSplitter:
    """Wrap pyannote-audio diarization to isolate speaker segments.

    Returns audio chunks per speaker label so downstream detectors
    can analyse each participant separately.
    """

    def __init__(self, hf_token: str | None = None):
        self._pipeline: Any = None
        self._hf_token = hf_token

    def _lazy_load(self) -> None:
        if self._pipeline is not None:
            return
        if Pipeline is None:
            raise RuntimeError("pyannote-audio not installed; install with: pip install pyannote-audio")
        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.0",
            use_auth_token=self._hf_token,
        )

    def diarize(self, audio: AudioChunk, sample_rate: int = 16000
                ) -> dict[str, AudioChunk]:
        """Run diarization and return {speaker_label: audio_chunk}."""
        self._lazy_load()
        duration = len(audio) / sample_rate
        waveform = audio.reshape(1, -1)
        result = self._pipeline({"waveform": waveform, "sample_rate": sample_rate})

        speakers: dict[str, list[float]] = {}
        for turn, _, speaker in result.itertracks(yield_label=True):
            start = int(turn.start * sample_rate)
            end = int(turn.end * sample_rate)
            segment = audio[start:end]
            seg_list = speakers.setdefault(speaker, [])
            seg_list.extend(segment.tolist())

        return {spk: np.array(seg, dtype=np.float32) for spk, seg in speakers.items()}

    def isolate_active(self, audio: AudioChunk, sample_rate: int = 16000
                       ) -> Optional[AudioChunk]:
        """Return the audio of the most recently active speaker (last turn)."""
        speakers = self.diarize(audio, sample_rate)
        if not speakers:
            return None
        # Return the longest segment as the most relevant speaker
        longest = max(speakers.values(), key=lambda x: len(x))
        return longest
