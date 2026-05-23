from __future__ import annotations

import io
import logging
import os
import platform
import subprocess

from PIL import Image

from .config import AppConfig
from .errors import ErrorRecorder


class Screenshotter:
    def __init__(self, config: AppConfig, errors: ErrorRecorder):
        self.config = config
        self.errors = errors
        self.log = logging.getLogger(__name__)

    def capture_jpeg(self) -> bytes | None:
        try:
            image = self._capture_image()
            if image.width > self.config.screenshot_max_width:
                ratio = self.config.screenshot_max_width / image.width
                image = image.resize(
                    (self.config.screenshot_max_width, int(image.height * ratio)),
                    Image.LANCZOS,
                )
            image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=self.config.screenshot_quality, optimize=True)
            return buffer.getvalue()
        except Exception as exc:
            self.log.error("Screenshot failed: %s", exc)
            self.errors.record("SCREENSHOT", str(exc))
            return None

    def _capture_image(self) -> Image.Image:
        system = platform.system()
        if system == "Darwin":
            return self._capture_with_command(["screencapture", "-x"])
        if system == "Linux":
            try:
                import pyautogui

                return pyautogui.screenshot()
            except Exception:
                return self._capture_with_command(["scrot"])

        import pyautogui

        return pyautogui.screenshot()

    def _capture_with_command(self, command: list[str]) -> Image.Image:
        tmp = "/tmp/task_monitor_shot.png"
        subprocess.run([*command, tmp], check=True)
        try:
            return Image.open(tmp).copy()
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
