"""Публичные URL для полей сделки amo (admin, MAX)."""

from __future__ import annotations

from sfrfr.core.config import get_settings


def admin_case_url(case_id: str | None) -> str | None:
    cid = (case_id or "").strip()
    if not cid:
        return None
    base = (get_settings().admin_public_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/?case={cid}"


def max_dialog_url() -> str | None:
    """Ссылка на личный чат бота — оператор продолжает диалог в MAX Business."""
    url = (get_settings().max_chat_url or get_settings().max_public_bot_url or "").strip()
    if not url:
        return None
    # Без ?startapp — открыть чат, не mini-app.
    if "?" in url:
        url = url.split("?", 1)[0]
    return url
