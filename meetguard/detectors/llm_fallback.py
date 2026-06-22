"""LLM fallback for ambiguous suspicious NLP detections.

Calls a local Ollama instance (or falls back to HuggingFace transformers)
to disambiguate borderline cases.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

try:
    from transformers import pipeline as hf_pipeline
except ImportError:
    hf_pipeline = None  # type: ignore[assignment]


CLASSIFICATION_PROMPT = """You are a financial fraud detection assistant. Analyze the following meeting transcript and determine if it contains a suspicious instruction that could indicate CEO fraud, vendor payment fraud, or social engineering.

Transcript: "{text}"

Output one of:
- SUSPICIOUS (0-1) — where 0 is probably normal and 1 is definitely fraudulent
- NORMAL

Only output your classification, nothing else."""


class LLMAnalyzer:
    """Analyze transcript text using a local LLM (Ollama) or HuggingFace."""

    def __init__(self, provider: str = "ollama", model: str = "mistral:7b",
                 api_url: str = "http://localhost:11434"):
        self.provider = provider
        self.model = model
        self.api_url = api_url.rstrip("/")
        self._hf_pipe: Any = None

    def analyze(self, text: str) -> float:
        """Return suspicious score 0.0–1.0 from LLM analysis.

        0.0 = normal, 1.0 = definitely suspicious.
        """
        if self.provider == "ollama":
            return self._analyze_ollama(text)
        elif self.provider == "huggingface":
            return self._analyze_hf(text)
        return 0.5

    def _analyze_ollama(self, text: str) -> float:
        if requests is None:
            return 0.5
        try:
            resp = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": CLASSIFICATION_PROMPT.format(text=text[:2000]),
                    "stream": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip().lower()
            return self._parse_response(raw)
        except Exception:
            return 0.5

    def _analyze_hf(self, text: str) -> float:
        if hf_pipeline is None:
            return 0.5
        if self._hf_pipe is None:
            self._hf_pipe = hf_pipeline(
                "text-classification",
                model="microsoft/deberta-v3-base",
                tokenizer="microsoft/deberta-v3-base",
            )
        result = self._hf_pipe(text[:512])[0]
        label = result["label"].lower()
        score = result["score"]
        if "suspicious" in label or "fraud" in label:
            return float(score)
        return 1.0 - float(score)

    @staticmethod
    def _parse_response(raw: str) -> float:
        """Extract score from LLM response like 'SUSPICIOUS (0.85)' or 'NORMAL'."""
        if "suspicious" in raw:
            import re
            match = re.search(r"\(([0-9.]+)\)", raw)
            if match:
                return min(1.0, max(0.0, float(match.group(1))))
            return 0.7  # suspicious without score → moderately suspicious
        return 0.0  # NORMAL
