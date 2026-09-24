"""OCR source resolver: local hash → Яндекс.Диск (temp) → Storage fallback.

Phase 1 (ТЗ-13a §4 / ТЗ-13 §3.7, §16). YDB не используется.

Порядок:
1) local ``storage/uploads/{case_id}/`` (по sha256, не по имени)
2) Яндекс.Диск по известному ``yandex_disk_path`` → temp (caller/ctx удаляет)
3) Supabase Storage — только если ``INGEST_OCR_STORAGE_FALLBACK`` /
   ``SUPABASE_STORAGE_OCR_FALLBACK`` true

Default fallback = True на переходный период: текущие jobs имеют только
``storage_path`` (local/disk paths ещё не заполнены Phase 2). Resolver всё
равно предпочитает local → disk, когда они есть.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sfrfr.core.config import get_settings
from sfrfr.storage.local import uploads_root

logger = logging.getLogger(__name__)

SourceUsed = Literal["local_storage", "yandex_disk", "supabase_storage"]


class OcrSourceUnresolved(Exception):
    """Не удалось получить байты оригинала для OCR (fail safe)."""

    def __init__(self, message: str, *, trace: list[str] | None = None) -> None:
        super().__init__(message)
        self.trace = list(trace or [])


@dataclass(frozen=True)
class ResolvedBytes:
    data: bytes
    sha256: str
    size_bytes: int
    source_used: SourceUsed
    local_path: str | None = None
    yandex_disk_path: str | None = None
    storage_path: str | None = None
    document_version: int | None = None
    temp_path: Path | None = None


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _storage_fallback_enabled(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    settings = get_settings()
    if bool(settings.ingest_ocr_storage_fallback):
        return True
    # Алиас env без отдельного поля Settings (MVP).
    raw = (os.getenv("SUPABASE_STORAGE_OCR_FALLBACK") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _matches_expected(
    data: bytes,
    *,
    expected_hash: str | None,
    expected_size: int | None,
) -> bool:
    if expected_size is not None and len(data) != expected_size:
        return False
    if expected_hash and _sha256_hex(data) != expected_hash.lower():
        return False
    return True


def _is_under_uploads_root(path: Path) -> bool:
    """``local_path`` разрешён только внутри ``uploads_root()``."""
    try:
        resolved = path.expanduser().resolve(strict=False)
        root = uploads_root().expanduser().resolve(strict=False)
        resolved.relative_to(root)
        return True
    except (OSError, ValueError):
        return False


def _try_local_path(
    path: Path,
    *,
    expected_hash: str | None,
    expected_size: int | None,
) -> ResolvedBytes | None:
    if not path.is_file():
        return None
    data = path.read_bytes()
    if not _matches_expected(data, expected_hash=expected_hash, expected_size=expected_size):
        return None
    return ResolvedBytes(
        data=data,
        sha256=_sha256_hex(data),
        size_bytes=len(data),
        source_used="local_storage",
        local_path=str(path),
    )


def _scan_local_by_hash(
    case_id: str,
    *,
    expected_hash: str | None,
    expected_size: int | None,
) -> ResolvedBytes | None:
    if not expected_hash:
        return None
    root = uploads_root() / case_id
    if not root.is_dir():
        return None
    want = expected_hash.lower()
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if _sha256_hex(data) != want:
            continue
        if expected_size is not None and len(data) != expected_size:
            continue
        return ResolvedBytes(
            data=data,
            sha256=want,
            size_bytes=len(data),
            source_used="local_storage",
            local_path=str(path),
        )
    return None


def _default_disk_download_to_temp(path: str) -> Path:
    from sfrfr.integrations.yandex_workspace.disk import download_case_file_to_temp

    result = download_case_file_to_temp(path)
    if not result.get("ok"):
        raise OcrSourceUnresolved(
            "yandex_disk_download_failed",
            trace=[f"disk:{result.get('error') or result.get('reason') or 'failed'}"],
        )
    return Path(str(result["temp_path"]))


def _default_storage_download(storage_path: str) -> bytes:
    from sfrfr.db.session import get_supabase_client
    from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

    client = get_supabase_client()
    return client.storage.from_(PRIVATE_STORAGE_BUCKET).download(storage_path)


def resolve_ocr_bytes(
    document: dict[str, Any],
    *,
    case_id: str,
    storage_download: Callable[[str], bytes] | None = None,
    disk_download_to_temp: Callable[[str], Path] | None = None,
    storage_fallback: bool | None = None,
) -> ResolvedBytes:
    """Resolve original bytes for OCR. Does not look up Disk paths by FIO."""
    trace: list[str] = []
    expected_hash = str(document.get("checksum_sha256") or "").strip() or None
    if expected_hash:
        expected_hash = expected_hash.lower()
    size_raw = document.get("size_bytes")
    expected_size: int | None
    try:
        expected_size = int(size_raw) if size_raw is not None and str(size_raw) != "" else None
    except (TypeError, ValueError):
        expected_size = None
    version_raw = document.get("document_version")
    try:
        document_version = int(version_raw) if version_raw is not None else None
    except (TypeError, ValueError):
        document_version = None

    storage_path = str(document.get("storage_path") or "").strip() or None
    yandex_disk_path = str(document.get("yandex_disk_path") or "").strip() or None
    local_path_raw = str(document.get("local_path") or "").strip() or None

    # 1) LOCAL — explicit path (только внутри uploads_root)
    if local_path_raw:
        candidate = Path(local_path_raw)
        if not _is_under_uploads_root(candidate):
            trace.append("local_path_outside_uploads_root")
        else:
            found = _try_local_path(
                candidate,
                expected_hash=expected_hash,
                expected_size=expected_size,
            )
            if found:
                return ResolvedBytes(
                    data=found.data,
                    sha256=found.sha256,
                    size_bytes=found.size_bytes,
                    source_used="local_storage",
                    local_path=found.local_path,
                    yandex_disk_path=yandex_disk_path,
                    storage_path=storage_path,
                    document_version=document_version,
                )
            trace.append("local_path_miss_or_hash_mismatch")

    # 1b) LOCAL — scan uploads/{case_id}/ by sha256
    scanned = _scan_local_by_hash(
        case_id, expected_hash=expected_hash, expected_size=expected_size
    )
    if scanned:
        return ResolvedBytes(
            data=scanned.data,
            sha256=scanned.sha256,
            size_bytes=scanned.size_bytes,
            source_used="local_storage",
            local_path=scanned.local_path,
            yandex_disk_path=yandex_disk_path,
            storage_path=storage_path,
            document_version=document_version,
        )
    if expected_hash:
        trace.append("local_scan_no_hash_match")
    else:
        trace.append("local_scan_skipped_no_hash")

    # 2) YANDEX_DISK — only known path (no FIO lookup)
    if yandex_disk_path:
        downloader = disk_download_to_temp or _default_disk_download_to_temp
        temp_path: Path | None = None
        try:
            temp_path = downloader(yandex_disk_path)
            data = temp_path.read_bytes()
            if _matches_expected(data, expected_hash=expected_hash, expected_size=expected_size):
                return ResolvedBytes(
                    data=data,
                    sha256=_sha256_hex(data),
                    size_bytes=len(data),
                    source_used="yandex_disk",
                    local_path=local_path_raw,
                    yandex_disk_path=yandex_disk_path,
                    storage_path=storage_path,
                    document_version=document_version,
                    temp_path=temp_path,
                )
            trace.append("yandex_disk_hash_or_size_mismatch")
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
                temp_path = None
        except OcrSourceUnresolved as exc:
            trace.extend(exc.trace or [str(exc)])
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            trace.append(f"yandex_disk_error:{type(exc).__name__}")
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    else:
        trace.append("yandex_disk_path_absent")

    # 3) STORAGE FALLBACK
    fallback_on = _storage_fallback_enabled(storage_fallback)
    if fallback_on and storage_path:
        downloader_s = storage_download or _default_storage_download
        try:
            data = downloader_s(storage_path)
            if _matches_expected(data, expected_hash=expected_hash, expected_size=expected_size):
                logger.warning(
                    "ocr_source_fallback=storage reason=no_verified_local_or_disk_source"
                )
                return ResolvedBytes(
                    data=data,
                    sha256=_sha256_hex(data),
                    size_bytes=len(data),
                    source_used="supabase_storage",
                    local_path=local_path_raw,
                    yandex_disk_path=yandex_disk_path,
                    storage_path=storage_path,
                    document_version=document_version,
                )
            trace.append("supabase_storage_hash_or_size_mismatch")
        except Exception as exc:  # noqa: BLE001
            trace.append(f"supabase_storage_error:{type(exc).__name__}")
    elif not fallback_on:
        trace.append("supabase_storage_fallback_disabled")
    else:
        trace.append("supabase_storage_path_absent")

    raise OcrSourceUnresolved(
        "ocr_source_unresolved",
        trace=trace,
    )


@contextmanager
def resolve_ocr_bytes_ctx(
    document: dict[str, Any],
    *,
    case_id: str,
    storage_download: Callable[[str], bytes] | None = None,
    disk_download_to_temp: Callable[[str], Path] | None = None,
    storage_fallback: bool | None = None,
) -> Iterator[ResolvedBytes]:
    """Как ``resolve_ocr_bytes``, плюс удаление temp с Диска в finally."""
    resolved = resolve_ocr_bytes(
        document,
        case_id=case_id,
        storage_download=storage_download,
        disk_download_to_temp=disk_download_to_temp,
        storage_fallback=storage_fallback,
    )
    try:
        yield resolved
    finally:
        if resolved.temp_path is not None:
            resolved.temp_path.unlink(missing_ok=True)
