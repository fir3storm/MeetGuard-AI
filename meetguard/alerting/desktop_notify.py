"""Desktop notifications via plyer."""

from __future__ import annotations

from typing import Optional

from meetguard.utils.models import AlertLevel

try:
    from plyer import notification as plyer_notification
except ImportError:
    plyer_notification = None  # type: ignore[assignment]


def notify(level: AlertLevel, title: str, message: str, timeout: int = 5) -> None:
    """Show a desktop notification.

    Falls back to print() if plyer is not available.
    """
    if plyer_notification is not None:
        try:
            plyer_notification.notify(
                title=f"MeetGuard: {level.value} — {title}",
                message=message,
                timeout=timeout,
            )
            return
        except Exception:
            pass

    # Fallback
    print(f"[MeetGuard] {level.value} | {title}: {message}")
