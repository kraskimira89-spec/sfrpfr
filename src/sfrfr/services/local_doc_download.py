"""Краткоживущие ссылки на локальные quarantine-файлы для staff."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

_lock = threading.RLock()
_TTL_SEC = 300.0


@dataclass
class _Entry:
    path: Path
    filename: str
    expires_at: float
    case_id: str
    document_id: str
    media_type: str | None = None
    as_attachment: bool = False


_tokens: dict[str, _Entry] = {}


def issue_local_download(
    *,
    path: Path,
    filename: str,
    case_id: str,
    document_id: str,
    ttl_sec: float = _TTL_SEC,
    media_type: str | None = None,
    as_attachment: bool = False,
) -> str:
    token = secrets.token_urlsafe(24)
    with _lock:
        _prune()
        _tokens[token] = _Entry(
            path=path,
            filename=filename,
            expires_at=time.time() + max(30.0, float(ttl_sec)),
            case_id=case_id,
            document_id=document_id,
            media_type=(media_type or "").strip() or None,
            as_attachment=bool(as_attachment),
        )
    return token


def take_local_download(token: str) -> _Entry | None:
    raw = (token or "").strip()
    if not raw:
        return None
    with _lock:
        _prune()
        entry = _tokens.get(raw)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            _tokens.pop(raw, None)
            return None
        return entry


def _prune() -> None:
    now = time.time()
    dead = [k for k, v in _tokens.items() if now > v.expires_at]
    for k in dead:
        _tokens.pop(k, None)


def reset_for_tests() -> None:
    with _lock:
        _tokens.clear()
