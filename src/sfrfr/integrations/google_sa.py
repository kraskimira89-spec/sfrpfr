"""Общая загрузка Google service account JSON (без печати ключей)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_service_account_info(raw: str, *, env_name: str = "GOOGLE_*_CREDENTIALS_JSON") -> dict[str, Any]:
    text = raw.strip().strip('"').strip("'")
    if not text:
        raise ValueError(f"{env_name} пуст")

    candidates = [Path(text)]
    if not Path(text).is_absolute():
        candidates.append(repo_root() / text)
        candidates.append(Path.cwd() / text)

    for path in candidates:
        if path.is_file():
            payload = path.read_text(encoding="utf-8").strip()
            if not payload:
                raise ValueError(f"пустой файл ключа: {path}")
            return json.loads(payload)

    if text.startswith("{"):
        return json.loads(text)

    raise FileNotFoundError(
        f"JSON ключ Google SA не найден ({env_name}={text!r}; "
        f"искали: {', '.join(str(p) for p in candidates)})"
    )


def access_token(credentials_info: dict[str, Any], *, scopes: list[str]) -> str:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Установите google-auth: pip install 'google-auth>=2.35.0'"
        ) from exc

    creds = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=scopes,
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Google SA: empty access token")
    return str(creds.token)
