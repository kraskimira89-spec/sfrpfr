"""Явные отказы secure action links (не silent pass)."""

from __future__ import annotations


class SecureLinksDisabled(Exception):
    """SECURE_ACTION_LINKS_ENABLED=false — create/verify запрещены."""

    def __init__(self, message: str = "secure_action_links_disabled") -> None:
        super().__init__(message)
        self.reason = "disabled"


class SecureLinkDenied(Exception):
    """Токен недействителен: TTL / revoke / max_uses / purpose / status."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
