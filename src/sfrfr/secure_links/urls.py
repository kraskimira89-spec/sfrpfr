"""Публичные URL secure action pages (без case_id / ПДн в path)."""

from __future__ import annotations

from sfrfr.core.config import get_settings


def public_secure_action_url(raw_token: str) -> str:
    """Страница действия: HTML на API (Sprint 2)."""
    api = (get_settings().public_base_url or "").rstrip("/")
    return f"{api}/api/portal/secure/{raw_token}"


def public_secure_pdf_url(raw_token: str) -> str:
    api = (get_settings().public_base_url or "").rstrip("/")
    return f"{api}/api/portal/secure/{raw_token}/pdf"
