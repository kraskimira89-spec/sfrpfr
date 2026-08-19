"""Публичные URL и подсказки для полей amo (admin, MAX)."""

from __future__ import annotations

from sfrfr.core.config import get_settings


def admin_case_url(case_id: str | None) -> str | None:
    cid = (case_id or "").strip()
    if not cid:
        return None
    base = (get_settings().admin_public_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/?case={cid}"


def max_operator_reply_hint(max_user_id: str | None) -> str | None:
    """
    Прямой URL на чат клиента в MAX не существует.
    Ссылка на бота открывает личный диалог оператора с ботом, не переписку клиента.
    """
    uid = (max_user_id or "").strip()
    if not uid:
        return (
            "Ответ в MAX: кабинет admin → дело → «Написать клиенту в MAX». "
            "Не открывать ссылку на бота — это ваш чат с ботом."
        )
    return (
        f"Клиент MAX user_id={uid}. Ответ: admin → дело → «Написать в MAX». "
        f"Или MAX Business → бот «Стаж и пенсия» → диалоги → ID {uid}."
    )
