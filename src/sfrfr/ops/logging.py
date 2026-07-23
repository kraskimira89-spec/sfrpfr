"""Безопасное логирование без ПДн (ТЗ-05)."""

from __future__ import annotations

import logging
import re

from sfrfr.utils.redact_pii import mask_snils, redact_fio

_TOKEN_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+)\S+"
    r"|(access_token=)[^&\s]+"
    r"|(token=)[^&\s]+"
    r"|(signedURL=)[^&\s]+"
    r"|(X-MAX-InitData:\s*)\S+"
)
_SNILS_RE = re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b")
_FIO_RE = re.compile(
    r"\b([А-ЯЁA-Z][а-яёa-z]+)\s+([А-ЯЁA-Z][а-яёa-z]+)(?:\s+([А-ЯЁA-Z][а-яёa-z]+))?\b"
)


def redact_log_text(text: str) -> str:
    """Убрать из текста логов СНИЛС, токены и типичные ФИО."""
    if not text:
        return text

    def _token_sub(match: re.Match[str]) -> str:
        for group in match.groups():
            if group is not None:
                return f"{group}***"
        return "***"

    out = _TOKEN_RE.sub(_token_sub, text)
    out = _SNILS_RE.sub(lambda m: mask_snils(m.group(0)), out)
    out = _FIO_RE.sub(lambda m: redact_fio(m.group(0)), out)
    return out


class RedactingFilter(logging.Filter):
    """Фильтр: маскирует ПДн и токены в сообщениях лога."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        record.msg = redact_log_text(msg)
        record.args = ()
        return True


def configure_logging(*, app_env: str, debug: bool) -> None:
    """Настроить логгеры с redaction (обязательно в production)."""
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    else:
        root.setLevel(level)

    redactor = RedactingFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "sfrfr"):
        logger = logging.getLogger(name) if name else root
        if not any(isinstance(f, RedactingFilter) for f in logger.filters):
            logger.addFilter(redactor)
    if app_env == "production":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
