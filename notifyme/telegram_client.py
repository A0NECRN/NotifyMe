from __future__ import annotations

import logging

import requests

from .config import AppConfig
from .errors import ErrorRecorder
from .retry import retry


class TelegramClient:
    def __init__(self, config: AppConfig, errors: ErrorRecorder):
        self.config = config
        self.errors = errors
        self.session = requests.Session()
        self.log = logging.getLogger(__name__)

    def send_message(self, text: str, reply_markup: dict | None = None) -> bool:
        @retry(self.errors)
        def send() -> bool:
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            self._request("POST", "sendMessage", json=payload, timeout=15)
            return True

        return send()

    def send_photo(self, image_bytes: bytes, caption: str) -> bool:
        @retry(self.errors)
        def send() -> bool:
            self._request(
                "POST",
                "sendPhoto",
                data={"chat_id": self.config.telegram_chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": ("screenshot.jpg", image_bytes, "image/jpeg")},
                timeout=30,
            )
            return True

        return send()

    def send_document(self, image_bytes: bytes, caption: str) -> bool:
        @retry(self.errors)
        def send() -> bool:
            self._request(
                "POST",
                "sendDocument",
                data={"chat_id": self.config.telegram_chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"document": ("screenshot.jpg", image_bytes, "image/jpeg")},
                timeout=30,
            )
            return True

        return send()

    def get_updates(self, offset: int) -> list[dict]:
        response = self._request(
            "GET",
            "getUpdates",
            params={"timeout": self.config.updates_timeout, "offset": offset},
            timeout=self.config.updates_timeout + 10,
        )
        data = response.json()
        if not data.get("ok"):
            self.log.warning("Telegram getUpdates returned ok=false")
            return []
        result = data.get("result", [])
        return result if isinstance(result, list) else []

    def _request(self, method: str, api_method: str, **kwargs) -> requests.Response:
        kwargs.setdefault("verify", self.config.verify_ssl)
        try:
            response = self.session.request(method, self._url(api_method), **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError:
            if self.config.verify_ssl:
                self.log.warning("SSL verification failed for Telegram %s; retrying without verification", api_method)
                kwargs["verify"] = False
                response = self.session.request(method, self._url(api_method), **kwargs)
                response.raise_for_status()
                return response
            raise

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.config.telegram_token}/{method}"
