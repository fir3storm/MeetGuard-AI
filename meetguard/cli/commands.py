"""CLI subcommands: status, alerts, report.

All read SQLite directly — no engine needed, works offline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from meetguard.storage.session_log import SessionLog


def cmd_status() -> None:
    """meetguard status — show engine status and last session summary."""
    pid_file = Path.home() / ".meetguard" / "engine.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        print(f"🟢 Engine running (PID: {pid})")
    else:
        print("⚪ Engine not running")

    log = SessionLog()
    sessions = log.get_sessions(limit=1)
    if sessions:
        s = sessions[0]
        print(f"  Last session: {s['id']}")
        print(f"  Started:      {s['started_at']}")
        print(f"  Ended:        {s['ended_at']}")
        print(f"  Meeting:      {s['meeting_window'] or 'Unknown'}")
        print(f"  Alerts:       {s['alert_count']}  Max risk: {s['max_risk']:.2f}  Level: {s['max_level']}")
    else:
        print("  No sessions recorded.")
    log.close()


def cmd_alerts(limit: int = 10, json_output: bool = False) -> None:
    """meetguard alerts — list recent alerts."""
    log = SessionLog()
    alerts = log.get_recent_alerts(limit=limit)
    log.close()

    if not alerts:
        print("No alerts recorded.")
        return

    if json_output:
        json.dump(alerts, sys.stdout, indent=2)
        print()
        return

    print(f"{'Time':<22} {'Level':<12} {'Risk':<6} {'Session':<14}")
    print("-" * 60)
    for a in alerts:
        print(f"{a['timestamp']:<22} {a['level']:<12} {a['total_risk']:<6.2f} {a['session_id']:<14}")


def cmd_report(session_id: str | None = None, output: str | None = None) -> None:
    """meetguard report — generate session summary (stdout or JSON file)."""
    log = SessionLog()
    sessions = log.get_sessions(limit=50)

    if session_id:
        sessions = [s for s in sessions if s["id"] == session_id]
    elif sessions:
        sessions = [sessions[0]]

    if not sessions:
        print("No sessions found.")
        log.close()
        return

    s = sessions[0]
    all_alerts = log.get_recent_alerts(limit=1000)
    session_alerts = [a for a in all_alerts if a["session_id"] == s["id"]]
    log.close()

    report = {
        "session_id": s["id"],
        "started_at": s["started_at"],
        "ended_at": s["ended_at"],
        "meeting_window": s["meeting_window"],
        "alert_count": s["alert_count"],
        "max_risk": s["max_risk"],
        "max_level": s["max_level"],
        "alerts": session_alerts,
    }

    if output:
        Path(output).write_text(json.dumps(report, indent=2))
        print(f"Report written to {output}")
    else:
        print(f"Session Report: {s['id']}")
        print(f"  Meeting: {s['meeting_window'] or 'Unknown'}")
        print(f"  Started: {s['started_at']}")
        print(f"  Ended:   {s['ended_at']}")
        print(f"  Alerts:  {s['alert_count']} (peak risk: {s['max_risk']:.2f} — {s['max_level']})")
        print()
        if session_alerts:
            print(f"  Alert Timeline ({len(session_alerts)} total, last 10 shown):")
            for a in session_alerts[-10:]:
                print(f"    {a['timestamp']}  [{a['level']:<10}] risk={a['total_risk']:.2f}")
        else:
            print("  No alerts during this session.")
