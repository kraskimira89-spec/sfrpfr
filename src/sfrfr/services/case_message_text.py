"""Текст case_messages: internal-префикс для заметок сотрудника."""

from __future__ import annotations

INTERNAL_STAFF_PREFIX = "[[internal]] "


def is_internal_staff_body(body: str) -> bool:
    return (body or "").lstrip().startswith("[[internal]]")


def strip_internal_staff_prefix(body: str) -> str:
    text = body or ""
    if text.startswith(INTERNAL_STAFF_PREFIX):
        return text[len(INTERNAL_STAFF_PREFIX) :]
    if text.startswith("[[internal]]"):
        rest = text[len("[[internal]]") :]
        return rest.lstrip(" \t")
    return text


def mark_internal_staff_body(body: str) -> str:
    text = (body or "").strip()
    if not text or is_internal_staff_body(text):
        return text
    return f"{INTERNAL_STAFF_PREFIX}{text}"
