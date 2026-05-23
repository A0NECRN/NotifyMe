from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    app_dir: Path
    telegram_token: str
    telegram_chat_id: str
    screenshot_quality: int = 75
    screenshot_max_width: int = 1920
    check_interval: int = 3
    cpu_threshold: float = 15.0
    cpu_idle_duration: int = 30
    gpu_threshold: float = 10.0
    gpu_idle_duration: int = 30
    verify_ssl: bool = True
    updates_timeout: int = 30

    @property
    def errors_file(self) -> Path:
        return self.app_dir / "errors.json"

    @property
    def log_file(self) -> Path:
        return self.app_dir / "task_monitor.log"

    @property
    def offset_file(self) -> Path:
        return self.app_dir / "task_monitor_offset.txt"

    @property
    def database_file(self) -> Path:
        return self.app_dir / "notifyme.db"


def load_config(app_dir: Path | None = None) -> AppConfig:
    root = app_dir or Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    return AppConfig(
        app_dir=root,
        telegram_token=os.getenv("TELEGRAM_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        screenshot_quality=_int_env("SCREENSHOT_QUALITY", 75),
        screenshot_max_width=_int_env("SCREENSHOT_MAX_WIDTH", 1920),
        check_interval=_int_env("CHECK_INTERVAL", 3),
        cpu_threshold=_float_env("CPU_THRESHOLD", 15.0),
        cpu_idle_duration=_int_env("CPU_IDLE_DURATION", 30),
        gpu_threshold=_float_env("GPU_THRESHOLD", 10.0),
        gpu_idle_duration=_int_env("GPU_IDLE_DURATION", 30),
        verify_ssl=_bool_env("VERIFY_SSL", True),
        updates_timeout=_int_env("UPDATES_TIMEOUT", 30),
    )


def validate_config(config: AppConfig) -> list[str]:
    errors: list[str] = []
    if not config.telegram_token:
        errors.append("TELEGRAM_TOKEN is not set in .env")
    if not config.telegram_chat_id:
        errors.append("TELEGRAM_CHAT_ID is not set in .env")
    if not 1 <= config.screenshot_quality <= 100:
        errors.append("SCREENSHOT_QUALITY must be between 1 and 100")
    if config.screenshot_max_width < 320:
        errors.append("SCREENSHOT_MAX_WIDTH must be at least 320")
    if config.check_interval < 1:
        errors.append("CHECK_INTERVAL must be at least 1")
    return errors


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name, "")
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
