"""Audible alert on critical detections."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


def play_alert(sound_path: str | Path | None = None) -> None:
    """Play an alert sound.

    Uses the platform-native method.
    A default beep is used if no sound_path is given.
    """
    if sound_path and Path(sound_path).exists():
        _play_file(sound_path)
    else:
        _beep()


def _beep() -> None:
    """System beep."""
    if sys.platform == "win32":
        import winsound  # type: ignore[import-untyped]
        winsound.MessageBeep(winsound.MB_ICONHAND)  # type: ignore[attr-defined]
    else:
        print("\a", end="", flush=True)


def _play_file(path: str | Path) -> None:
    """Play a sound file using the OS default."""
    try:
        if sys.platform == "win32":
            import winsound  # type: ignore[import-untyped]
            winsound.PlaySound(str(path), winsound.SND_FILENAME)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["afplay", str(path)], check=False)
        else:
            subprocess.run(["aplay", str(path)], check=False)
    except Exception:
        _beep()
