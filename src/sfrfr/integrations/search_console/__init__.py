"""Google Search Console: ops-проверка property (без ПДн)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.google_sa import access_token, load_service_account_info

_GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
_GSC_API = "https://www.googleapis.com/webmasters/v3"


class SearchConsoleClient:
    def __init__(self, *, credentials_json: str | None = None) -> None:
        settings = get_settings()
        raw = (
            credentials_json
            if credentials_json is not None
            else settings.google_search_console_credentials_json
        )
        self._credentials_raw = (raw or "").strip()

    @property
    def available(self) -> bool:
        return bool(self._credentials_raw)

    def list_sites(self) -> dict[str, Any]:
        if not self.available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no GOOGLE_SEARCH_CONSOLE_CREDENTIALS_JSON",
                "sites": [],
            }
        try:
            info = load_service_account_info(
                self._credentials_raw,
                env_name="GOOGLE_SEARCH_CONSOLE_CREDENTIALS_JSON",
            )
            token = access_token(info, scopes=[_GSC_SCOPE])
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    f"{_GSC_API}/sites",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "sites": [],
                    "sa_email": info.get("client_email"),
                }
            entries = (resp.json() or {}).get("siteEntry") or []
            sites = [
                {
                    "siteUrl": e.get("siteUrl"),
                    "permissionLevel": e.get("permissionLevel"),
                }
                for e in entries
            ]
            return {
                "ok": True,
                "sites": sites,
                "count": len(sites),
                "sa_email": info.get("client_email"),
                "hint": (
                    "Добавьте property в Search Console и выдайте доступ "
                    f"на {info.get('client_email')} (или подтвердите DNS)."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "sites": []}
