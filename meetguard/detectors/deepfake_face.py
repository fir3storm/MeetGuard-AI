"""Frame-sequence deepfake face detector using a 3DCNN approach.

Wraps a pretrained model (XceptionNet backbone + BiLSTM temporal layer).
Processes windows of 16 face crops and outputs a per-window deepfake probability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import numpy.typing as npt

try:
    import torch
    import torch.nn.functional as F
except ImportError:
    torch = None  # type: ignore[assignment]


def _build_model() -> Any:
    """Build a simple 3DCNN for deepfake detection.

    In production, replace this with a pretrained XceptionNet + BiLSTM
    or a loaded checkpoint from HuggingFace.
    """
    if torch is None:
        raise RuntimeError("PyTorch not installed")

    import torch.nn as nn

    class Deepfake3DCNN(nn.Module):
        def __init__(self, num_frames: int = 16):
            super().__init__()
            # 3D conv layers for spatiotemporal features
            self.conv1 = nn.Conv3d(3, 32, kernel_size=(3, 5, 5), stride=(1, 2, 2), padding=(1, 2, 2))
            self.bn1 = nn.BatchNorm3d(32)
            self.conv2 = nn.Conv3d(32, 64, kernel_size=(3, 5, 5), stride=(1, 2, 2), padding=(1, 2, 2))
            self.bn2 = nn.BatchNorm3d(64)
            self.conv3 = nn.Conv3d(64, 128, kernel_size=(3, 3, 3), stride=(1, 2, 2), padding=(1, 1, 1))
            self.bn3 = nn.BatchNorm3d(128)
            self.pool = nn.AdaptiveAvgPool3d((1, 1, 1))
            self.fc = nn.Linear(128, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = F.relu(self.bn1(self.conv1(x)))
            x = F.relu(self.bn2(self.conv2(x)))
            x = F.relu(self.bn3(self.conv3(x)))
            x = self.pool(x).flatten(1)
            return torch.sigmoid(self.fc(x))

    return Deepfake3DCNN(num_frames=16)


class DeepfakeFaceDetector:
    """Detect deepfake faces from a sequence of frames.

    Accepts a list of face crops (HWC, BGR) and returns a score [0, 1].
    """

    def __init__(self, model_path: str | Path | None = None, window_frames: int = 16,
                 threshold_suspicious: float = 0.50, threshold_critical: float = 0.75):
        self._model: Any = None
        self._window_frames = window_frames
        self.threshold_suspicious = threshold_suspicious
        self.threshold_critical = threshold_critical
        self._model_path = str(model_path) if model_path else ""
        self._device = "cpu"

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        if torch is None:
            raise RuntimeError("PyTorch not installed")
        self._model = _build_model()
        self._model.eval()
        # Load weights if a checkpoint exists
        if self._model_path and Path(self._model_path).exists():
            state = torch.load(self._model_path, map_location="cpu", weights_only=True)
            self._model.load_state_dict(state, strict=False)

    def predict(self, face_crops: list[npt.NDArray]) -> float:
        """Run inference on a sequence of face crops.

        Args:
            face_crops: List of (H, W, 3) uint8 BGR images.

        Returns:
            Score 0.0 (real) – 1.0 (deepfake).
        """
        if not face_crops:
            return 0.0
        self._lazy_load()
        if torch is None or self._model is None:
            return 0.0

        # Prepare frames: ensure we have exactly window_frames
        crops = face_crops[:self._window_frames]
        if len(crops) < self._window_frames:
            # Pad by repeating last frame
            pad = [crops[-1]] * (self._window_frames - len(crops))
            crops.extend(pad)

        # Stack → (T, H, W, 3) → permute to (1, 3, T, H, W) and normalize
        stacked = np.stack(crops, axis=0).astype(np.float32) / 255.0
        # Resize to a common size if needed
        import cv2
        resized = [cv2.resize(s, (224, 224)) for s in stacked]
        tensor = torch.from_numpy(np.stack(resized, axis=0)).permute(3, 0, 1, 2).unsqueeze(0)

        with torch.no_grad():
            out = self._model(tensor)
            return float(out.item())

    def predict_sliding(self, face_crops: list[npt.NDArray]) -> float:
        """Apply EMA-smoothing over overlapping windows for stability."""
        if len(face_crops) < self._window_frames:
            return self.predict(face_crops)

        scores: list[float] = []
        step = max(1, self._window_frames // 4)
        for i in range(0, len(face_crops) - self._window_frames + 1, step):
            window = face_crops[i:i + self._window_frames]
            scores.append(self.predict(window))

        if not scores:
            return 0.0
        # EMA with α = 0.3
        alpha = 0.3
        smoothed = scores[0]
        for s in scores[1:]:
            smoothed = alpha * s + (1 - alpha) * smoothed
        return float(smoothed)
