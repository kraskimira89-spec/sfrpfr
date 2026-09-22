"""Яндекс Wiki: ensure страницы-индекса (отдельный API host)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_tracker import _maybe_load_tracker_secrets_file

logger = logging.getLogger(__name__)

WIKI_API_BASE = "https://api.wiki.yandex.net/v1"


def _wiki_headers() -> dict[str, str]:
    _maybe_load_tracker_secrets_file()
    settings = get_settings()
    token = (
        (os.environ.get("WIKI_TOKEN") or "").strip()
        or (settings.tracker_oauth_token or settings.tracker_token or "").strip()
    )
    if not token:
        raise RuntimeError("WIKI_TOKEN / TRACKER_TOKEN not configured")
    headers = {
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json",
    }
    cloud = (settings.tracker_cloud_org_id or "").strip()
    org = (settings.tracker_org_id or "").strip()
    if cloud:
        headers["X-Cloud-Org-Id"] = cloud
    elif org:
        headers["X-Org-Id"] = org
    else:
        raise RuntimeError("TRACKER_ORG_ID or TRACKER_CLOUD_ORG_ID required")
    return headers


def wiki_page_url(slug: str) -> str:
    return f"https://wiki.yandex.ru/{slug.lstrip('/')}"


def get_page_by_slug(slug: str) -> dict[str, Any] | None:
    s = (slug or "").strip().strip("/")
    if not s:
        return None
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(
                f"{WIKI_API_BASE}/pages",
                headers=_wiki_headers(),
                params={"slug": s, "fields": "slug,title,id"},
            )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            logger.warning("wiki_get_failed status=%s slug=%s", resp.status_code, s)
            return None
        data = resp.json() if resp.content else {}
        return data if isinstance(data, dict) and data.get("id") is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("wiki_get_failed err=%s", type(exc).__name__)
        return None


def create_page(
    *,
    slug: str,
    title: str,
    content: str,
    page_type: str = "wysiwyg",
) -> dict[str, Any]:
    body = {
        "slug": slug.strip().strip("/"),
        "title": title[:255],
        "content": content[:50000],
        "page_type": page_type,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{WIKI_API_BASE}/pages",
                headers=_wiki_headers(),
                json=body,
                params={"is_silent": "true"},
            )
        data: Any
        try:
            data = resp.json() if resp.content else {}
        except Exception:  # noqa: BLE001
            data = {"text": (resp.text or "")[:200]}
        if resp.status_code in (200, 201) and isinstance(data, dict) and data.get("id") is not None:
            slug_out = str(data.get("slug") or body["slug"])
            return {
                "ok": True,
                "id": data["id"],
                "slug": slug_out,
                "url": wiki_page_url(slug_out),
            }
        # 401/403 — нет wiki:write; вызывающий делает soft-skip
        return {
            "ok": False,
            "status_code": resp.status_code,
            "error": str(
                (data.get("message") if isinstance(data, dict) else None)
                or (data.get("error") if isinstance(data, dict) else None)
                or data
            )[:300],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}
