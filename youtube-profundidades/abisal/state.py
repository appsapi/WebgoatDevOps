"""Historial de vídeos publicados, para no repetir temas."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT

HISTORY_PATH = ROOT / "state" / "history.json"


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def append_history(entry: dict) -> None:
    history = load_history()
    entry = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    history.append(entry)
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
