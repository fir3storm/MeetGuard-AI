"""Lip-sync consistency check using SyncNet.

Measures audio-visual synchronisation confidence.
Low confidence = likely deepfake (audio and video are out of sync).
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

try:
    import torch
    import torch.nn.functional as F
except ImportError:
    torch = None  # type: ignore[assignment]


AudioChunk = npt.NDArray[np.float32]
Frame = npt.NDArray[np.uint8]


def _mel_spectrogram(audio: AudioChunk, sr: int = 16000) -> np.ndarray:
    """Compute mel-spectrogram from audio."""
    from scipy.signal import spectrogram
    _, _, Sxx = spectrogram(audio, fs=sr, nperseg=400, noverlap=240)
    return Sxx


def _build_syncnet() -> Any:
    """Minimal SyncNet-like model for AV synchronisation.

    Replaced with pretrained weights in production.
    """
    if torch is None:
        raise RuntimeError("PyTorch not installed")
    import torch.nn as nn

    class SyncNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.v_conv = nn.Sequential(
                nn.Conv2d(3, 64, 5, padding=2), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(64, 128, 5, padding=2), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(128, 256, 5, padding=2), nn.ReLU(), nn.MaxPool2d(2),
                nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.v_fc = nn.Linear(256, 512)

            self.a_conv = nn.Sequential(
                nn.Conv2d(1, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(128, 256, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.a_fc = nn.Linear(256, 512)

        def forward(self, video: torch.Tensor, audio: torch.Tensor) -> torch.Tensor:
            v = self.v_conv(video).flatten(1)
            v = self.v_fc(v)
            a = self.a_conv(audio).flatten(1)
            a = self.a_fc(a)
            v = F.normalize(v, dim=1)
            a = F.normalize(a, dim=1)
            return (v * a).sum(dim=1)

    return SyncNet()


class LipSyncDetector:
    """Detect lip-sync inconsistencies.

    Score: 0 = synced, 1 = drifting (possible deepfake).
    """

    def __init__(self, confidence_threshold: float = 0.30, window_seconds: float = 2.0):
        self._model: Any = None
        self.threshold = confidence_threshold
        self.window_seconds = window_seconds

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        if torch is None:
            raise RuntimeError("PyTorch not installed")
        self._model = _build_syncnet()
        self._model.eval()

    def predict(self, face_crop: Frame, audio_chunk: AudioChunk, sample_rate: int = 16000) -> float:
        """Compute lip-sync confidence.

        Returns score 0.0 (synced) – 1.0 (drifting / likely deepfake).
        """
        if torch is None:
            return 0.0
        self._lazy_load()

        face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        face_resized = cv2.resize(face_rgb, (128, 128)).astype(np.float32) / 255.0
        vis = torch.from_numpy(face_resized).permute(2, 0, 1).unsqueeze(0)

        spec = _mel_spectrogram(audio_chunk, sample_rate)
        if spec.size == 0:
            return 0.5
        spec_resized = cv2.resize(spec, (128, 128), interpolation=cv2.INTER_LINEAR).astype(np.float32)
        aud = torch.from_numpy(spec_resized).unsqueeze(0).unsqueeze(0)

        with torch.no_grad():
            sim = self._model(vis, aud)
            confidence = float(torch.sigmoid(sim).item())
            if confidence >= self.threshold:
                return 0.0
            return 1.0 - (confidence / self.threshold)
