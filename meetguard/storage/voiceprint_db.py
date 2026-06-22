"""SQLite-backed voiceprint storage with optional encryption.

Uses Fernet symmetric encryption for biometric data at rest.
The encryption key is stored at ~/.meetguard/.voiceprint_key.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from meetguard.utils.models import VoiceprintRecord

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]


def _get_or_create_key(key_path: Path) -> bytes:
    """Get existing key or generate a new one."""
    if key_path.exists():
        return key_path.read_bytes()
    if Fernet is None:
        raise RuntimeError("cryptography not installed: pip install cryptography")
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    return key


class VoiceprintDB:
    """Persist and load enrolled voiceprints with optional encryption."""

    def __init__(self, db_path: str | Path | None = None, encrypt: bool = True):
        if db_path is None:
            db_path = Path.home() / ".meetguard" / "voiceprints.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._encrypt = encrypt and Fernet is not None
        self._fernet: Optional[Fernet] = None
        if self._encrypt:
            key_path = Path.home() / ".meetguard" / ".voiceprint_key"
            key = _get_or_create_key(key_path)
            self._fernet = Fernet(key)
        self._conn: Optional[sqlite3.Connection] = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS voiceprints ("
                "  name TEXT PRIMARY KEY,"
                "  embedding BLOB NOT NULL,"
                "  created_at REAL NOT NULL,"
                "  threshold REAL NOT NULL DEFAULT 0.45"
                ")"
            )
        return self._conn

    def _encrypt_blob(self, data: bytes) -> bytes:
        if self._fernet is not None:
            return self._fernet.encrypt(data)
        return data

    def _decrypt_blob(self, data: bytes) -> bytes:
        if self._fernet is not None:
            try:
                return self._fernet.decrypt(data)
            except Exception:
                return data  # fallback: return as-is (migration path)
        return data

    def save(self, record: VoiceprintRecord) -> None:
        conn = self._connect()
        encrypted = self._encrypt_blob(record.embedding_bytes)
        conn.execute(
            "INSERT OR REPLACE INTO voiceprints (name, embedding, created_at, threshold) "
            "VALUES (?, ?, ?, ?)",
            (record.name, encrypted, time.time(), record.threshold),
        )
        conn.commit()

    def list_all(self) -> list[VoiceprintRecord]:
        conn = self._connect()
        rows = conn.execute("SELECT name, embedding, created_at, threshold FROM voiceprints").fetchall()
        return [
            VoiceprintRecord(
                name=row[0],
                embedding_bytes=self._decrypt_blob(row[1]),
                created_at=__import__("datetime").datetime.fromtimestamp(row[2]),
                threshold=row[3],
            )
            for row in rows
        ]

    def delete(self, name: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM voiceprints WHERE name = ?", (name,))
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
