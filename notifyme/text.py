from __future__ import annotations


def html_escape(text: object) -> str:
    value = str(text)
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def truncate(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n... <truncated>"
