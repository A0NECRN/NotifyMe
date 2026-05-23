from __future__ import annotations

import logging
import platform
from datetime import datetime

from .screenshot import Screenshotter
from .telegram_client import TelegramClient
from .text import html_escape, truncate


class Notifier:
    def __init__(self, telegram: TelegramClient, screenshotter: Screenshotter):
        self.telegram = telegram
        self.screenshotter = screenshotter
        self.log = logging.getLogger(__name__)

    def task_done(self, task_name: str, detail: str = "", success: bool = True, metrics: dict | None = None) -> None:
        status = "Done" if success else "Failed"
        caption = self._caption(status, task_name, detail, metrics or {})
        self.log.info("Task finished: %s (%s)", task_name, status)
        self.telegram.send_message(caption)

        image = self.screenshotter.capture_jpeg()
        if not image:
            self.telegram.send_message("Screenshot failed.")
            return
        if len(image) < 10 * 1024 * 1024:
            self.telegram.send_photo(image, caption)
        else:
            self.telegram.send_document(image, caption)

    def screenshot_now(self) -> None:
        self.telegram.send_message("Taking screenshot...")
        image = self.screenshotter.capture_jpeg()
        if not image:
            self.telegram.send_message("Screenshot failed.")
            return
        caption = (
            "<b>Screenshot</b>\n"
            f"<b>Host:</b> {html_escape(platform.node())}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if len(image) < 10 * 1024 * 1024:
            self.telegram.send_photo(image, caption)
        else:
            self.telegram.send_document(image, caption)

    def _caption(self, status: str, task_name: str, detail: str = "", metrics: dict | None = None) -> str:
        metrics = metrics or {}
        message = (
            f"<b>Task {status}</b>\n\n"
            f"<b>Task:</b> {html_escape(task_name)}\n"
            f"<b>Host:</b> {html_escape(platform.node())}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if metrics:
            duration = float(metrics.get("duration", 0))
            message += (
                f"\n<b>Duration:</b> {duration:.1f}s"
                f"\n<b>Peak:</b> CPU {metrics.get('max_cpu', 0)}%, "
                f"RAM {metrics.get('max_memory', 0)}%, GPU {metrics.get('max_gpu', 0)}%"
            )
        if detail:
            message += f"\n<b>Detail:</b> {html_escape(truncate(detail, 1200))}"
        return message
