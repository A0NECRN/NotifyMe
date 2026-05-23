from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path


class ErrorRecorder:
    def __init__(self, path: Path, secrets: list[str] | None = None):
        self.path = path
        self.secrets = [s for s in secrets if s] if secrets else []
        self.lock = threading.Lock()
        self.log = logging.getLogger(__name__)

    def record(self, error_type: str, message: str, fixed: bool = False, fix_detail: str = "") -> None:
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": error_type,
            "message": self._redact(message),
            "fixed": fixed,
            "fix_detail": self._redact(fix_detail),
        }
        try:
            with self.lock:
                errors = self._read()
                errors.append(entry)
                self.path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            self.log.debug("Failed to write error record: %s", exc)

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _redact(self, text: str) -> str:
        value = str(text)
        for secret in self.secrets:
            value = value.replace(secret, "<redacted>")
        return value
