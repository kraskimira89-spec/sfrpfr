"""Серверная проверка типов файлов: magic bytes, блокировка опасных расширений."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sfrfr.core.config import get_settings

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_IMAGE_PIXELS = 25_000_000
MAX_FILES_PER_BATCH = 20

BLOCKED_SUFFIXES = frozenset(
    {
        ".zip",
        ".rar",
        ".7z",
        ".doc",
        ".docm",
        ".xls",
        ".xlsx",
        ".exe",
        ".msi",
        ".dll",
        ".html",
        ".htm",
        ".svg",
        ".js",
        ".php",
        ".py",
        ".bat",
        ".cmd",
        ".eml",
        ".msg",
    }
)

STANDARD_SUFFIXES = frozenset({".pdf", ".docx", ".jpg", ".jpeg", ".png"})
SIGNED_SUFFIXES = frozenset({".pdf", ".docx"})
_HEIC_SUFFIXES = frozenset({".heic", ".heif"})

# Клиенту — без латиницы форматов (старшее поколение; формат знать не обязательно).
_CLIENT_REJECT = (
    "Этот файл не получается принять. "
    "Пришлите его ещё раз фотографией или документом из телефона."
)
_CLIENT_UNRECOGNIZED = (
    "Не получилось понять, что за файл. "
    "Пришлите его ещё раз фотографией или документом из телефона."
)
_CLIENT_HEIC = (
    "Фото в этом формате телефона не принимается. "
    "Пришлите обычную фотографию или документ ещё раз."
)
_CLIENT_EMPTY = "Файл пустой — пришлите его ещё раз."
_CLIENT_TOO_LARGE = "Файл слишком большой. Пришлите файл поменьше (до 20 МБ)."
_CLIENT_MACROS = "Файлы Word с макросами не принимаются. Пришлите обычный документ без макросов."
_CLIENT_SIGNED_ONLY = (
    "Для подписанного заявления пришлите обычный документ без макросов."
)

_PDF_MIME = "application/pdf"
_JPEG_MIME = "image/jpeg"
_PNG_MIME = "image/png"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class FileSecurityResult:
    ok: bool
    detected_mime: str | None = None
    client_message: str | None = None
    internal_reason: str | None = None


@dataclass(frozen=True)
class AntivirusResult:
    status: Literal["clean", "infected", "not_configured", "error"]
    reason: str | None = None


def scan_file_bytes(data: bytes, filename: str) -> AntivirusResult:
    """Проверить байты ClamAV, если сканер установлен на worker/VPS."""
    if b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*" in data:
        return AntivirusResult("infected", "eicar_test_signature")
    executable = shutil.which(os.getenv("DOCUMENT_AV_SCANNER", "clamdscan"))
    if not executable:
        executable = shutil.which("clamscan")
    if not executable:
        return AntivirusResult("not_configured", "scanner_not_found")

    suffix = Path(filename or "document.bin").suffix or ".bin"
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary_path = temporary.name
            temporary.write(data)
            temporary.flush()
        result = subprocess.run(
            [executable, "--no-summary", temporary_path],
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return AntivirusResult("error", type(exc).__name__)
    finally:
        if temporary_path:
            try:
                Path(temporary_path).unlink(missing_ok=True)
            except OSError:
                pass
    if result.returncode == 0:
        return AntivirusResult("clean")
    if result.returncode == 1:
        return AntivirusResult("infected", "scanner_detected_threat")
    return AntivirusResult("error", f"scanner_exit:{result.returncode}")


def antivirus_allows(result: AntivirusResult) -> bool:
    """Разрешить обработку только после clean; local auto допускает отсутствие ClamAV."""
    mode = (
        os.getenv("DOCUMENT_AV_MODE") or get_settings().document_av_mode or "auto"
    ).strip().lower()
    if mode == "disabled":
        return True
    if result.status == "clean":
        return True
    if (
        result.status == "not_configured"
        and mode in {"auto", "observe"}
        and get_settings().app_env.lower() not in {"production", "prod"}
    ):
        return True
    return False


def _detect_magic(data: bytes) -> str | None:
    # ISO 32000: допускается преамбула до маркера %PDF- (часто с телефона).
    if b"%PDF-" in data[:1024]:
        return _PDF_MIME
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return _JPEG_MIME
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return _PNG_MIME
    if len(data) >= 4 and data[:4] == b"PK\x03\x04":
        return _DOCX_MIME
    return None


def _looks_like_heic(data: bytes) -> bool:
    if len(data) < 12 or data[4:8] != b"ftyp":
        return False
    brand = data[8:12].lower()
    return brand in {b"heic", b"heif", b"mif1", b"msf1", b"heix", b"hevc"}


def _allowed_mimes(*, allow_signed: bool) -> frozenset[str]:
    if allow_signed:
        return frozenset({_PDF_MIME, _DOCX_MIME})
    return frozenset({_PDF_MIME, _JPEG_MIME, _PNG_MIME, _DOCX_MIME})


def validate_upload_filename(filename: str, *, allow_signed: bool = False) -> FileSecurityResult:
    name = Path(filename or "document").name
    if ".." in name or name.startswith("."):
        return FileSecurityResult(
            ok=False,
            client_message="Некорректное имя файла.",
            internal_reason="path_traversal",
        )
    suffix = Path(name).suffix.lower()
    if suffix in BLOCKED_SUFFIXES or suffix in _HEIC_SUFFIXES:
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_HEIC if suffix in _HEIC_SUFFIXES else _CLIENT_REJECT,
            internal_reason=(
                "heic_unsupported" if suffix in _HEIC_SUFFIXES else f"blocked_suffix:{suffix}"
            ),
        )
    allowed = SIGNED_SUFFIXES if allow_signed else STANDARD_SUFFIXES
    if suffix not in allowed:
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_SIGNED_ONLY if allow_signed else _CLIENT_REJECT,
            internal_reason=f"disallowed_suffix:{suffix}",
        )
    return FileSecurityResult(ok=True)


def validate_file_bytes(
    data: bytes,
    *,
    filename: str,
    declared_content_type: str | None = None,
    allow_signed: bool = False,
) -> FileSecurityResult:
    """Проверка по содержимому (magic). Имя/mime с телефона могут врать — доверяем байтам."""
    del declared_content_type  # телефоны часто шлют пустой/чужой mime; не режем из‑за него
    name = Path(filename or "document").name
    if ".." in name or name.startswith("."):
        return FileSecurityResult(
            ok=False,
            client_message="Некорректное имя файла.",
            internal_reason="path_traversal",
        )
    suffix = Path(name).suffix.lower()
    if suffix in BLOCKED_SUFFIXES:
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_REJECT,
            internal_reason=f"blocked_suffix:{suffix}",
        )
    if not data:
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_EMPTY,
            internal_reason="empty_file",
        )
    if len(data) > MAX_FILE_BYTES:
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_TOO_LARGE,
            internal_reason="file_too_large",
        )
    if suffix in _HEIC_SUFFIXES or _looks_like_heic(data):
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_HEIC,
            internal_reason="heic_unsupported",
        )
    detected = _detect_magic(data)
    if not detected:
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_UNRECOGNIZED,
            internal_reason="magic_bytes_failed",
        )
    if detected not in _allowed_mimes(allow_signed=allow_signed):
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_SIGNED_ONLY if allow_signed else _CLIENT_REJECT,
            internal_reason=f"mime_not_allowed:{detected}",
        )
    if detected == _DOCX_MIME and _docx_has_macros(data):
        return FileSecurityResult(
            ok=False,
            client_message=_CLIENT_MACROS,
            internal_reason="docx_macros",
        )
    return FileSecurityResult(ok=True, detected_mime=detected)


def _docx_has_macros(data: bytes) -> bool:
    """Грубая проверка OOXML: vbaProject.bin внутри zip."""
    return bool(re.search(rb"vbaProject\.bin", data[:512_000]))


def is_quarantine_status(status: str | None) -> bool:
    return str(status or "") in {
        "uploading",
        "security_check",
        "blocked_security",
        "quarantine",
    }


def is_downloadable_status(
    status: str | None,
    *,
    antivirus_status: str | None = None,
) -> bool:
    blocked = {
        "uploading",
        "security_check",
        "blocked_security",
        "quarantine",
        "needs_reupload",
    }
    av = str(antivirus_status or "").strip().lower()
    if av and av not in {"clean", "not_configured", "disabled"}:
        return False
    return str(status or "uploaded") not in blocked
