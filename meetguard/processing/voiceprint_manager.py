"""Voiceprint enrollment, storage, and comparison using ECAPA-TDNN."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import numpy.typing as npt

from meetguard.storage.voiceprint_db import VoiceprintDB
from meetguard.utils.models import VoiceprintRecord

try:
    import speechbrain.inference.speaker
except ImportError:
    speechbrain = None  # type: ignore[assignment]


AudioChunk = npt.NDArray[np.float32]  # shape (N,) 16kHz mono


class VoiceprintManager:
    """Enrol speakers and compare live audio against their voiceprints."""

    def __init__(self, db_path: str | Path | None = None, model_name: str = "speechbrain/spkrec-ecapa-voxceleb"):
        self._encoder: Optional[speechbrain.inference.speaker.Encode] = None  # type: ignore[arg-type]
        self._model_name = model_name
        self.db = VoiceprintDB(db_path)

    def _lazy_load(self) -> None:
        if self._encoder is not None:
            return
        if speechbrain is None:
            raise RuntimeError("speechbrain not installed")
        self._encoder = speechbrain.inference.speaker.Encode.from_hparams(
            source=self._model_name, savedir=Path.home() / ".meetguard" / "models" / "ecapa",
            run_opts={"device": "cpu"},
        )

    def embed(self, audio: AudioChunk) -> npt.NDArray[np.float32]:
        """Extract speaker embedding from audio chunk."""
        self._lazy_load()
        if self._encoder is None:
            raise RuntimeError("encoder not loaded")
        emb = self._encoder.encode_batch(audio.reshape(1, -1))
        return emb.squeeze(0).cpu().numpy().astype(np.float32)

    def enroll(self, name: str, audio: AudioChunk) -> VoiceprintRecord:
        """Enroll a new speaker from ~30s of audio."""
        embedding = self.embed(audio)
        record = VoiceprintRecord(
            name=name,
            embedding_bytes=embedding.tobytes(),
        )
        self.db.save(record)
        return record

    def compare(self, audio: AudioChunk) -> list[tuple[VoiceprintRecord, float]]:
        """Compare audio against all enrolled voiceprints.

        Returns list of (record, cosine_similarity), sorted descending.
        """
        emb = self.embed(audio)
        results: list[tuple[VoiceprintRecord, float]] = []
        for record in self.db.list_all():
            enrolled = np.frombuffer(record.embedding_bytes, dtype=np.float32)
            sim = float(np.dot(emb, enrolled) / (np.linalg.norm(emb) * np.linalg.norm(enrolled) + 1e-8))
            results.append((record, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def best_match(self, audio: AudioChunk, threshold: float = 0.45
                   ) -> tuple[Optional[VoiceprintRecord], float]:
        """Return closest match above threshold, or (None, 0.0)."""
        results = self.compare(audio)
        if results and results[0][1] >= threshold:
            return results[0]
        return None, 0.0
