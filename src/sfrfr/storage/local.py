"""Локальное сохранение загрузок (storage/uploads)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from sfrfr.core.config import get_settings

_SAFE_NAME = re.compile(r"[^\w.\-]+", re.UNICODE)


def uploads_root() -> Path:
    root = Path(get_settings().storage_local_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def case_dir(case_id: str) -> Path:
    path = uploads_root() / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", name).strip("._") or "file"
    return cleaned[:180]


def save_upload(case_id: str, filename: str, data: bytes) -> Path:
    """Сохранить файл в storage/uploads/<case_id>/."""
    dest = case_dir(case_id) / f"{uuid.uuid4().hex[:8]}_{safe_filename(filename)}"
    dest.write_bytes(data)
    return dest
