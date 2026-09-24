"""Локальное сохранение загрузок (storage/uploads)."""

from __future__ import annotations

import hashlib
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


def save_quarantine_upload(
    case_id: str,
    *,
    document_id: str,
    filename: str,
    data: bytes,
) -> Path:
    """Локальная карантинная копия до security gate worker.

    Путь: ``uploads/quarantine/{case_id}/{doc8}_{safe_name}``.
    """
    cid = (case_id or "").strip()
    did = (document_id or "").strip()
    if not cid or not did:
        raise ValueError("case_id and document_id required")
    folder = uploads_root() / "quarantine" / cid
    folder.mkdir(parents=True, exist_ok=True)
    prefix = did.replace("-", "")[:8] or uuid.uuid4().hex[:8]
    dest = folder / f"{prefix}_{safe_filename(filename)}"
    dest.write_bytes(data)
    return dest


def relative_to_uploads(path: Path) -> str | None:
    """Относительный путь от uploads_root без leading slash; None если вне root."""
    try:
        root = uploads_root().expanduser().resolve(strict=False)
        resolved = path.expanduser().resolve(strict=False)
        rel = resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    text = rel.as_posix().lstrip("/")
    if not text or ".." in Path(text).parts:
        return None
    return text


def path_from_uploads_relative(stored: str) -> Path | None:
    """``uploads_root() / relative``; отклоняет ``..``, abs и выход за root."""
    raw = (stored or "").strip().replace("\\", "/").lstrip("/")
    if not raw or raw.startswith("/") or ".." in Path(raw).parts:
        return None
    candidate = (uploads_root() / raw).expanduser()
    try:
        resolved = candidate.resolve(strict=False)
        root = uploads_root().expanduser().resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved


def confirm_local_file(
    path: Path,
    *,
    expected_sha256: str,
    expected_size: int | None = None,
) -> str | None:
    """Если файл существует и hash(+size) совпадают — relative path для БД."""
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if expected_size is not None and len(data) != expected_size:
        return None
    digest = hashlib.sha256(data).hexdigest().lower()
    if digest != (expected_sha256 or "").strip().lower():
        return None
    return relative_to_uploads(path)
