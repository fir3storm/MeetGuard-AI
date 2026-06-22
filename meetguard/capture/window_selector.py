"""Match a running meeting window by title pattern."""

from __future__ import annotations

import re
import sys
from typing import Optional


def list_windows() -> list[dict]:
    """Return list of visible windows with title and pid (cross-platform)."""
    windows: list[dict] = []

    if sys.platform == "win32":
        try:
            import win32gui  # type: ignore[import-untyped]
            import win32process  # type: ignore[import-untyped]

            def enum_cb(hwnd: int, _lparam: object) -> None:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                windows.append({"title": title, "hwnd": hwnd, "pid": pid})

            win32gui.EnumWindows(enum_cb, None)  # type: ignore[arg-type]
        except ImportError:
            pass
    elif sys.platform == "darwin":
        try:
            import subprocess
            out = subprocess.check_output(
                ["osascript", "-e",
                 'tell app "System Events" to get name of every process whose visible is true']
            ).decode()
            for name in out.strip().split(", "):
                windows.append({"title": name, "pid": 0})
        except Exception:
            pass
    else:  # Linux (X11)
        try:
            import subprocess
            out = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--name", ".*"],
                                          stderr=subprocess.DEVNULL).decode().strip()
            for wid in out.split("\n"):
                if not wid:
                    continue
                name = subprocess.check_output(["xdotool", "getwindowname", wid],
                                               stderr=subprocess.DEVNULL).decode().strip()
                windows.append({"title": name, "id": wid, "pid": 0})
        except Exception:
            pass

    return windows


def find_meeting_window(patterns: list[str] | None = None) -> Optional[str]:
    """Return the title of the first meeting window found, or None."""
    patterns = patterns or [
        "Zoom*", "Google Meet*", "Microsoft Teams*", "*Meet*",
    ]
    # Convert glob-like patterns to regex
    regexes = [re.escape(p).replace(r"\*", ".*") + "$" for p in patterns]
    compiled = [re.compile(r, re.IGNORECASE) for r in regexes]

    for win in list_windows():
        title = win.get("title", "")
        for cr in compiled:
            if cr.match(title):
                return title
    return None
