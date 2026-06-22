"""Settings persistence for the MeetGuard app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SettingsStore:
    """Persist UI settings and preferences as JSON."""

    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = Path.home() / ".meetguard" / "settings.json"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()
