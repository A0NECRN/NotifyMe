from __future__ import annotations

import logging
from pathlib import Path


class SecretRedactionFilter(logging.Filter):
    def __init__(self, secrets: list[str]):
        super().__init__()
        self.secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "<redacted>")
        record.msg = message
        record.args = ()
        return True


def setup_logging(log_file: Path, secrets: list[str] | None = None) -> logging.Logger:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    redactor = SecretRedactionFilter(secrets or [])

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    stream.addFilter(redactor)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redactor)

    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logging.getLogger("notifyme")
