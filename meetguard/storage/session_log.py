"""SQLite session log for alert history — with session lifecycle."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from meetguard.utils.models import AlertLevel, FusionResult


class SessionLog:
    """Persist meeting session alerts and risk history."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".meetguard" / "sessions.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional = None

    def _connect(self):
        import sqlite3
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "  id TEXT PRIMARY KEY,"
                "  started_at REAL, ended_at REAL,"
                "  meeting_window TEXT,"
                "  alert_count INTEGER, max_risk REAL, max_level TEXT"
                ")"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS alerts ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  session_id TEXT,"
                "  timestamp REAL,"
                "  total_risk REAL,"
                "  level TEXT,"
                "  scores TEXT,"
                "  FOREIGN KEY(session_id) REFERENCES sessions(id)"
                ")"
            )
        return self._conn

    def create_session(self, meeting_window: str = "") -> str:
        """Create a new session and return its ID."""
        conn = self._connect()
        session_id = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO sessions (id, started_at, meeting_window, alert_count, max_risk, max_level) "
            "VALUES (?, ?, ?, 0, 0.0, ?)",
            (session_id, time.time(), meeting_window, AlertLevel.SAFE.value),
        )
        conn.commit()
        return session_id

    def end_session(self, session_id: str) -> None:
        """Mark a session as ended."""
        conn = self._connect()
        conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (time.time(), session_id))
        conn.commit()

    def save_alert(self, result: FusionResult) -> None:
        conn = self._connect()
        scores_json = json.dumps({
            "face": result.scores.face,
            "voice": result.scores.voice,
            "lip": result.scores.lip,
            "nlp": result.scores.nlp,
            "urgency": result.scores.urgency,
        })
        conn.execute(
            "INSERT INTO alerts (session_id, timestamp, total_risk, level, scores) "
            "VALUES (?, ?, ?, ?, ?)",
            (result.session_id, time.time(), result.total_risk, result.level.value, scores_json),
        )
        # Update session max_risk / max_level
        conn.execute(
            "UPDATE sessions SET alert_count = alert_count + 1, "
            "max_risk = MAX(max_risk, ?), "
            "max_level = CASE WHEN ? = 'CRITICAL' THEN 'CRITICAL' "
            "  WHEN ? = 'SUSPICIOUS' AND max_level != 'CRITICAL' THEN 'SUSPICIOUS' "
            "  ELSE max_level END "
            "WHERE id = ?",
            (result.total_risk, result.level.value, result.level.value, result.session_id),
        )
        conn.commit()

    def get_recent_alerts(self, limit: int = 50) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT timestamp, total_risk, level, scores, session_id "
            "FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {
                "timestamp": datetime.fromtimestamp(r[0]).isoformat(),
                "total_risk": r[1],
                "level": r[2],
                "scores": json.loads(r[3]),
                "session_id": r[4],
            }
            for r in rows
        ]

    def get_sessions(self, limit: int = 20) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, started_at, ended_at, meeting_window, alert_count, max_risk, max_level "
            "FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {
                "id": r[0],
                "started_at": datetime.fromtimestamp(r[1]).isoformat() if r[1] else "",
                "ended_at": datetime.fromtimestamp(r[2]).isoformat() if r[2] else "ongoing",
                "meeting_window": r[3],
                "alert_count": r[4],
                "max_risk": r[5],
                "max_level": r[6],
            }
            for r in rows
        ]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
