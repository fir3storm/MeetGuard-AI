"""Pydantic(-style) data models for the MeetGuard pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class AlertLevel(str, Enum):
    SAFE = "SAFE"
    MONITOR = "MONITOR"
    SUSPICIOUS = "SUSPICIOUS"
    CRITICAL = "CRITICAL"


@dataclass
class DetectorScores:
    face: float = 0.0       # deepfake face score 0-1
    voice: float = 0.0      # voice mismatch score 0-1
    lip: float = 0.0        # lip-sync drift score 0-1
    nlp: float = 0.0        # suspicious NLP score 0-1
    urgency: float = 0.0    # urgency language score 0-1


@dataclass
class DetectionResult:
    detector_name: str
    score: float             # 0.0 – 1.0  (higher = more suspicious)
    raw_value: Optional[float] = None  # e.g. cosine similarity, confidence
    details: str = ""


@dataclass
class FusionResult:
    timestamp: datetime = field(default_factory=datetime.now)
    scores: DetectorScores = field(default_factory=DetectorScores)
    total_risk: float = 0.0
    level: AlertLevel = AlertLevel.SAFE
    meeting_active: bool = False
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class VoiceprintRecord:
    name: str
    embedding_bytes: bytes   # serialised numpy array
    created_at: datetime = field(default_factory=datetime.now)
    threshold: float = 0.45


@dataclass
class SessionInfo:
    id: str
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    meeting_window: str = ""
    alert_count: int = 0
    max_risk: float = 0.0
    max_level: AlertLevel = AlertLevel.SAFE
