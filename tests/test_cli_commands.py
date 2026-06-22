"""Tests for CLI subcommands."""

import json
from pathlib import Path

from meetguard.cli.commands import cmd_status, cmd_alerts, cmd_report
from meetguard.storage.session_log import SessionLog


def test_status_no_engine(tmp_path, monkeypatch):
    """status should not crash when engine not running and no sessions."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cmd_status()  # should not raise


def test_alerts_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cmd_alerts(limit=5)  # should print "No alerts" without crashing


def test_alerts_json(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Create a session + alert so there's data
    log = SessionLog()
    sid = log.create_session("Test Meeting")
    from meetguard.utils.models import FusionResult, DetectorScores, AlertLevel
    result = FusionResult(session_id=sid, total_risk=0.8,
                          scores=DetectorScores(face=0.9), level=AlertLevel.CRITICAL)
    log.save_alert(result)
    log.close()

    import sys, io
    captured = io.StringIO()
    sys.stdout = captured
    cmd_alerts(limit=5, json_output=True)
    sys.stdout = sys.__stdout__
    output = captured.getvalue()
    data = json.loads(output)
    assert len(data) >= 1
    assert data[0]["level"] == "CRITICAL"


def test_report_with_data(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    log = SessionLog()
    sid = log.create_session("Board Meeting")
    from meetguard.utils.models import FusionResult, DetectorScores, AlertLevel
    log.save_alert(FusionResult(session_id=sid, total_risk=0.8,
                                 scores=DetectorScores(face=0.9), level=AlertLevel.CRITICAL))
    log.close()

    report_path = tmp_path / "report.json"
    cmd_report(session_id=sid, output=str(report_path))
    assert report_path.exists()
    data = json.loads(report_path.read_text())
    assert data["session_id"] == sid
    assert data["alert_count"] >= 1
