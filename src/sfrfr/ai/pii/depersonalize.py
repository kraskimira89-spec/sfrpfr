"""Обезличивание текста перед RAG / импортом / другим AI."""

from __future__ import annotations

import re

from sfrfr.utils.redact_pii import mask_snils, redact_fio

_SNILS_RE = re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b")
_PASSPORT_RE = re.compile(r"\b\d{4}\s?\d{6}\b")
_PHONE_RE = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_BIRTH_RE = re.compile(
    r"\b(?:0[1-9]|[12]\d|3[01])[./](?:0[1-9]|1[0-2])[./](?:19|20)\d{2}\b"
)
_PAYMENT_CASE_RE = re.compile(
    r"\b(?:выплатн\w*\s*дел\w*|№\s*дела)[:\s№]*[\d\-A-Za-z/]{5,}\b",
    re.IGNORECASE,
)
# ФИО: три слова с заглавной (кириллица), грубая эвристика.
_FIO_RE = re.compile(
    r"\b([А-ЯЁ][а-яё]{1,30})\s+([А-ЯЁ][а-яё]{1,30})\s+([А-ЯЁ][а-яё]{1,30})\b"
)


def depersonalize_text(text: str, *, client_name: str | None = None) -> str:
    """Удаляет/заменяет ПДн перед загрузкой в RAG или другой AI."""
    out = text
    out = _SNILS_RE.sub(lambda m: mask_snils(m.group(0)), out)
    out = _PASSPORT_RE.sub("[ПАСПОРТ]", out)
    out = _PHONE_RE.sub("[ТЕЛЕФОН]", out)
    out = _EMAIL_RE.sub("[EMAIL]", out)
    out = _URL_RE.sub("[ССЫЛКА]", out)
    out = _BIRTH_RE.sub("[ДАТА]", out)
    out = _PAYMENT_CASE_RE.sub("[№ДЕЛА]", out)
    out = _FIO_RE.sub(lambda m: redact_fio(m.group(0)), out)
    if client_name and client_name.strip():
        out = out.replace(client_name, redact_fio(client_name))
    return out
