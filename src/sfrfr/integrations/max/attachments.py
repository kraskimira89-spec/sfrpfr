"""Разбор вложений из апдейта MAX (url / file_bytes)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.integrations.max.ssl_context import max_ssl_verify

_MEDIA_TYPES = frozenset({"file", "image", "video", "audio", "photo"})


def message_mid(update: dict[str, Any]) -> str | None:
    message = update.get("message") or update.get("message_created") or {}
    if isinstance(message, dict):
        body = message.get("body") if isinstance(message.get("body"), dict) else {}
        for key in ("mid", "message_id", "id"):
            for src in (body, message, update):
                if isinstance(src, dict):
                    raw = src.get(key)
                    if raw is not None and str(raw).strip():
                        return str(raw).strip()
    return None


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


def _payload_of(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("payload")
    return raw if isinstance(raw, dict) else item


def _first_url(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
        if isinstance(value, dict):
            nested = _first_url(
                value.get("url"),
                value.get("fileUrl"),
                value.get("file_url"),
                value.get("href"),
            )
            if nested:
                return nested
        if isinstance(value, list):
            for entry in value:
                nested = _first_url(entry)
                if nested:
                    return nested
    return None


def attachment_debug_meta(update: dict[str, Any]) -> list[dict[str, Any]]:
    """Ключи вложений без URL/токенов — для диагностики."""
    meta: list[dict[str, Any]] = []
    for item in iter_attachment_candidates(update):
        payload = _payload_of(item)
        meta.append(
            {
                "type": str(item.get("type") or payload.get("type") or ""),
                "item_keys": sorted(str(k) for k in item.keys()),
                "payload_keys": sorted(str(k) for k in payload.keys()),
                "has_url": bool(
                    _first_url(
                        payload.get("url"),
                        payload.get("fileUrl"),
                        payload.get("file_url"),
                        item.get("url"),
                    )
                ),
            }
        )
    return meta


def has_media_attachments(update: dict[str, Any]) -> bool:
    """Есть ли в апдейте медиа (даже без скачиваемого url)."""
    for item in iter_attachment_candidates(update):
        payload = _payload_of(item)
        kind = str(item.get("type") or payload.get("type") or "").strip().lower()
        if kind in _MEDIA_TYPES:
            return True
        if _first_url(
            payload.get("url"),
            payload.get("fileUrl"),
            payload.get("file_url"),
            item.get("url"),
            payload.get("photos"),
            payload.get("thumbnail"),
        ):
            return True
        if any(
            payload.get(key) or item.get(key)
            for key in ("token", "fileId", "file_id", "photoId", "photo_id", "id")
        ):
            return True
    return False


def _attachment_filename(item: dict[str, Any], payload: dict[str, Any]) -> str:
    return str(
        payload.get("file_name")
        or payload.get("filename")
        or payload.get("name")
        or item.get("file_name")
        or item.get("filename")
        or item.get("name")
        or "document"
    )


def extract_attachment_specs(update: dict[str, Any]) -> list[dict[str, Any]]:
    """Спеки вложений: filename, url|None, attach_key (без сырого token в ключе)."""
    from sfrfr.integrations.max.attachment_lifecycle import attach_key_from_parts

    out: list[dict[str, Any]] = []
    for index, item in enumerate(iter_attachment_candidates(update)):
        payload = _payload_of(item)
        url = _first_url(
            payload.get("url"),
            payload.get("fileUrl"),
            payload.get("file_url"),
            payload.get("href"),
            item.get("url"),
            item.get("fileUrl"),
            payload.get("photos"),
            payload.get("thumbnail"),
            payload.get("imageUrl"),
        )
        name = _attachment_filename(item, payload)
        token = payload.get("token") or item.get("token")
        file_id = (
            payload.get("fileId")
            or payload.get("file_id")
            or item.get("fileId")
            or item.get("file_id")
            or payload.get("photoId")
            or payload.get("photo_id")
            or item.get("id")
        )
        key = attach_key_from_parts(
            token=str(token) if token else None,
            file_id=str(file_id) if file_id else None,
            url=url,
            filename=name,
            index=index,
        )
        out.append(
            {
                "filename": name,
                "url": url,
                "attach_key": key,
                "index": index,
            }
        )
    return out


def extract_downloadable_files(update: dict[str, Any]) -> list[tuple[str, str]]:
    """Вернуть список (filename, url) для скачивания."""
    out: list[tuple[str, str]] = []
    for spec in extract_attachment_specs(update):
        url = spec.get("url")
        if not url:
            continue
        out.append((str(spec["filename"]), str(url)))
    return out


def download_file(url: str, *, max_bytes: int = 50 * 1024 * 1024) -> bytes:
    with httpx.Client(timeout=60.0, verify=max_ssl_verify(), follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.content
        if len(data) > max_bytes:
            raise ValueError("file too large")
        return data
