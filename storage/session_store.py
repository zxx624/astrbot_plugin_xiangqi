from __future__ import annotations

import json
from pathlib import Path

from ..engine.board import Board


class SessionStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.path = data_dir / "sessions.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load(self, session_id: str) -> Board | None:
        payload = self._read_all()
        state = payload.get(session_id)
        if state is None:
            return None
        return Board.from_dict(state)

    def save(self, session_id: str, board: Board) -> None:
        payload = self._read_all()
        payload[session_id] = board.to_dict()
        self._write_all(payload)

    def delete(self, session_id: str) -> None:
        payload = self._read_all()
        if session_id in payload:
            payload.pop(session_id)
            self._write_all(payload)

    def _read_all(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_all(self, payload: dict) -> None:
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)
