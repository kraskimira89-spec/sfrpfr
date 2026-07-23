"""Разбор вложений из апдейта MAX (url / file_bytes)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.integrations.max.ssl_context import max_ssl_verify


def iter_attachment_candidates(update: dict[str, Any]) -> list[dict[str, Any]]:
    """Собрать кандидатов вложений из разных форм payload MAX."""
    found: list[dict[str, Any]] = []
    message = update.get("message") or update.get("message_created") or {}
    if not isinstance(message, dict):
        message = {}
    body = message.get("body") if isinstance(message.get("body"), dict) else {}
    pools: list[Any] = [
        update.get("attachments"),
        message.get("attachments"),
        body.get("attachments") if isinstance(body, dict) else None,
        message.get("attaches"),
        body.get("attaches") if isinstance(body, dict) else None,
    ]
    for pool in pools:
        if isinstance(pool, list):
            for item in pool:
                if isinstance(item, dict):
                    found.append(item)
    return found


def extract_downloadable_files(update: dict[str, Any]) -> list[tuple[str, str]]:
    """Вернуть список (filename, url) для скачивания."""
    out: list[tuple[str, str]] = []
    for item in iter_attachment_candidates(update):
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
        url = (
            payload.get("url")
            or payload.get("fileUrl")
            or payload.get("file_url")
            or item.get("url")
            or item.get("fileUrl")
        )
        if not url or not isinstance(url, str):
            continue
        name = (
            payload.get("file_name")
            or payload.get("filename")
            or payload.get("name")
            or item.get("file_name")
            or item.get("filename")
            or item.get("name")
            or "document.bin"
        )
        out.append((str(name), url))
    return out


def download_file(url: str, *, max_bytes: int = 50 * 1024 * 1024) -> bytes:
    with httpx.Client(timeout=60.0, verify=max_ssl_verify(), follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.content
        if len(data) > max_bytes:
            raise ValueError("file too large")
        return data
