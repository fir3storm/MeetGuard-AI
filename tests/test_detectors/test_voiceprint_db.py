"""Tests for voiceprint storage with encryption."""

import pytest

from meetguard.storage.voiceprint_db import VoiceprintDB
from meetguard.utils.models import VoiceprintRecord


def test_save_and_list(tmp_path):
    db_path = tmp_path / "test_vp.db"
    db = VoiceprintDB(db_path, encrypt=False)
    record = VoiceprintRecord(name="CEO", embedding_bytes=b"\x00\x01\x02" * 100)
    db.save(record)
    records = db.list_all()
    assert len(records) == 1
    assert records[0].name == "CEO"
    assert records[0].embedding_bytes == b"\x00\x01\x02" * 100


def test_delete(tmp_path):
    db_path = tmp_path / "test_vp.db"
    db = VoiceprintDB(db_path, encrypt=False)
    db.save(VoiceprintRecord(name="CEO", embedding_bytes=b"\x00" * 100))
    db.save(VoiceprintRecord(name="CFO", embedding_bytes=b"\x01" * 100))
    db.delete("CEO")
    assert len(db.list_all()) == 1
    assert db.list_all()[0].name == "CFO"


def test_empty_db(tmp_path):
    db = VoiceprintDB(tmp_path / "empty.db", encrypt=False)
    assert db.list_all() == []


def test_multiple_enrollments(tmp_path):
    db = VoiceprintDB(tmp_path / "multi.db", encrypt=False)
    db.save(VoiceprintRecord(name="CEO", embedding_bytes=b"\x00" * 100))
    db.save(VoiceprintRecord(name="CFO", embedding_bytes=b"\x01" * 100))
    db.save(VoiceprintRecord(name="CTO", embedding_bytes=b"\x02" * 100))
    assert len(db.list_all()) == 3
