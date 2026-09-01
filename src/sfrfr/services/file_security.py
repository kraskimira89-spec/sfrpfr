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

STANDARD_SUFFIXES = frozenset({".pdf", ".jpg", ".jpeg", ".png"})
SIGNED_SUFFIXES = frozenset({".pdf", ".docx"})


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
    if len(data) >= 5 and data[:5] == b"%PDF-":
        return "application/pdf"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 4 and data[:4] == b"PK\x03\x04":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return None


def validate_upload_filename(filename: str, *, allow_signed: bool = False) -> FileSecurityResult:
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
            client_message="Этот формат файла не принимается. Загрузите PDF или фото.",
            internal_reason=f"blocked_suffix:{suffix}",
        )
    allowed = SIGNED_SUFFIXES if allow_signed else STANDARD_SUFFIXES
    if suffix not in allowed:
        return FileSecurityResult(
            ok=False,
            client_message="Допустимы PDF, JPG и PNG."
            if not allow_signed
            else "Для подписанного заявления допустимы PDF или DOCX.",
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
    name_check = validate_upload_filename(filename, allow_signed=allow_signed)
    if not name_check.ok:
        return name_check
    if not data:
        return FileSecurityResult(
            ok=False,
            client_message="Файл пустой.",
            internal_reason="empty_file",
        )
    if len(data) > MAX_FILE_BYTES:
        return FileSecurityResult(
            ok=False,
            client_message="Файл слишком большой. Максимум 20 МБ.",
            internal_reason="file_too_large",
        )
    detected = _detect_magic(data)
    if not detected:
        return FileSecurityResult(
            ok=False,
            client_message="Не удалось распознать формат файла. Загрузите PDF или фото.",
            internal_reason="magic_bytes_failed",
        )
    suffix = Path(filename).suffix.lower()
    if detected == "application/pdf" and suffix != ".pdf":
        return FileSecurityResult(
            ok=False,
            client_message="Расширение файла не совпадает с содержимым.",
            internal_reason="mime_mismatch",
        )
    if detected == "image/jpeg" and suffix not in {".jpg", ".jpeg"}:
        return FileSecurityResult(
            ok=False,
            client_message="Расширение файла не совпадает с содержимым.",
            internal_reason="mime_mismatch",
        )
    if detected == "image/png" and suffix != ".png":
        return FileSecurityResult(
            ok=False,
            client_message="Расширение файла не совпадает с содержимым.",
            internal_reason="mime_mismatch",
        )
    if detected.endswith("wordprocessingml.document") and suffix != ".docx":
        return FileSecurityResult(
            ok=False,
            client_message="Для Word загрузите файл .docx без макросов.",
            internal_reason="mime_mismatch",
        )
    if declared_content_type:
        declared = declared_content_type.split(";")[0].strip().lower()
        if declared and declared not in {detected, "application/octet-stream"}:
            if not (declared == "image/jpg" and detected == "image/jpeg"):
                return FileSecurityResult(
                    ok=False,
                    client_message="Тип файла не совпадает с содержимым.",
                    internal_reason="content_type_mismatch",
                )
    if allow_signed and detected.endswith("wordprocessingml.document"):
        if _docx_has_macros(data):
            return FileSecurityResult(
                ok=False,
                client_message="Файлы с макросами не принимаются.",
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
