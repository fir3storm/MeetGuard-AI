"""NLP detector for suspicious payment/vendor-change instructions.

Two-stage: regex pre-filter (fast) → semantic embedding comparison (accurate).
Optionally supports LLM fallback for ambiguous cases.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import numpy as np
import numpy.typing as npt

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment,misc]


# ── Stage 1: Regex patterns ───────────────────────────────────────────

SUSPICIOUS_PATTERNS: list[tuple[str, float]] = [
    # Payment / banking changes
    (r"bank\s*account", 0.7),
    (r"wire\s*transfer", 0.8),
    (r"routing\s*number", 0.8),
    (r"vendor\s*change", 0.8),
    (r"new\s*payment", 0.7),
    (r"new\s*account\s*number", 0.9),
    (r"update\s+(the\s+)?(routing|payment|bank)", 0.8),
    (r"change\s+(the\s+)?(vendor|payment|account)", 0.8),
    (r"send\s+(the\s+)?(money|funds|payment)", 0.8),
    (r"authorize\s+(a\s+)?(transfer|payment)", 0.8),
    (r"sign\s+this\s+urgently", 0.7),
    (r"approve\s+(the\s+)?(payment|transfer)", 0.8),
    # Whaling / impersonation markers
    (r"the\s+ceo\s+(requested|asked|wants)", 0.8),
    (r"board\s+(instructed|approved|directed)", 0.7),
    (r"confidential\s+(transaction|matter|deal)", 0.7),
]

COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), w) for p, w in SUSPICIOUS_PATTERNS]


# ── Stage 2: Semantic templates ───────────────────────────────────────

SUSPICIOUS_TEMPLATES = [
    "Change the vendor payment details to a new bank account",
    "Authorize an urgent wire transfer to this account",
    "Update the routing number for the next payment",
    "Send the funds now, don't tell anyone about this",
    "The CEO needs you to approve this confidential payment",
    "Change the account number for vendor payments immediately",
    "This is urgent — transfer the money right away",
]


class SuspiciousNLPDectector:
    """Detect suspicious financial instructions in transcribed text.

    score: 0.0 (normal) → 1.0 (highly suspicious).
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                 enable_llm_fallback: bool = False):
        self._encoder: Any = None
        self._model_name = model_name
        self._enable_llm = enable_llm_fallback
        self._template_embeddings: Optional[npt.NDArray] = None

    def _lazy_load(self) -> None:
        if self._encoder is not None:
            return
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers not installed")
        self._encoder = SentenceTransformer(self._model_name)
        self._template_embeddings = self._encoder.encode(SUSPICIOUS_TEMPLATES)

    def predict(self, text: str) -> float:
        """Score transcribed text for suspicious content.

        Returns score 0.0 – 1.0.
        """
        if not text or not text.strip():
            return 0.0

        # Stage 1: regex pre-filter (fast)
        max_regex_score = 0.0
        for pattern, weight in COMPILED_PATTERNS:
            if pattern.search(text):
                max_regex_score = max(max_regex_score, weight)

        # Stage 2: semantic comparison (only if regex triggered)
        if max_regex_score > 0 and self._encoder is not None:
            try:
                self._lazy_load()
            except RuntimeError:
                return max_regex_score  # fall back to regex-only

            if self._encoder is not None and self._template_embeddings is not None:
                emb = self._encoder.encode([text])
                sims = np.dot(emb, self._template_embeddings.T).flatten()
                max_sim = float(np.max(sims))
                # Blend regex + semantic
                return min(1.0, max_regex_score * 0.4 + max_sim * 0.6)

        return max_regex_score
