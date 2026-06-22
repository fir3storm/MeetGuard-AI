"""Face detection and cropping using MediaPipe."""

from __future__ import annotations

from typing import Any, Optional

import cv2
import numpy as np
import numpy.typing as npt

try:
    import mediapipe as mp
    _mp_face_detection = mp.solutions.face_detection
except ImportError:
    mp = None  # type: ignore[assignment]


Frame = npt.NDArray[np.uint8]  # (H, W, 3) BGR


class FaceExtractor:
    """Detect and crop faces from video frames.

    Uses MediaPipe Face Detection (lightweight, fast).
    Returns a list of face crops and bounding boxes per frame.
    """

    def __init__(self, min_detection_confidence: float = 0.5):
        self._model: Any = None
        self._confidence = min_detection_confidence
        if mp is not None:
            self._model = _mp_face_detection.FaceDetection(
                model_selection=0, min_detection_confidence=min_detection_confidence
            )

    def detect(self, frame: Frame) -> list[tuple[Frame, tuple[int, int, int, int]]]:
        """Return list of (face_crop, (x, y, w, h)) for each detected face."""
        if self._model is None:
            return []

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._model.process(rgb)

        faces: list[tuple[Frame, tuple[int, int, int, int]]] = []
        if results.detections is None:
            return faces

        h, w, _ = frame.shape
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            bw = int(bbox.width * w)
            bh = int(bbox.height * h)
            # Clamp to frame boundaries
            x, y = max(0, x), max(0, y)
            bw = min(bw, w - x)
            bh = min(bh, h - y)
            if bw < 10 or bh < 10:
                continue
            crop = frame[y:y + bh, x:x + bw]
            faces.append((crop, (x, y, bw, bh)))

        return faces

    def detect_largest(self, frame: Frame, target_size: tuple[int, int] = (224, 224)
                       ) -> Optional[Frame]:
        """Detect the largest face and return a resized square crop, or None."""
        faces = self.detect(frame)
        if not faces:
            return None
        # Pick the largest face by area
        largest = max(faces, key=lambda f: f[1][2] * f[1][3])
        crop = largest[0]
        return cv2.resize(crop, target_size, interpolation=cv2.INTER_LINEAR)

    def close(self) -> None:
        if self._model is not None:
            self._model.close()
