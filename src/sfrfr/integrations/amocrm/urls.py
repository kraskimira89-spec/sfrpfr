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


def admin_case_max_reply_url(case_id: str | None) -> str | None:
    """Кабинет сотрудника → дело → блок «Написать клиенту в MAX»."""
    base = admin_case_url(case_id)
    if not base:
        return None
    return f"{base}#max-reply"


def max_dialog_url(case_id: str | None = None) -> str | None:
    """Кликабельная ссылка для amo: ответ клиенту через кабинет (не бот)."""
    return admin_case_max_reply_url(case_id)


def staff_max_login_url() -> str:
    """Ops-бот для входа сотрудника в веб-кабинет (ТЗ-25)."""
    settings = get_settings()
    return (settings.max_ops_chat_url or settings.max_chat_url or "").strip()


def max_business_dialogs_url() -> str:
    """Раздел диалогов бота в MAX Business (ручной поиск по user_id)."""
    settings = get_settings()
    default = "https://business.max.ru/self"
    return (settings.max_business_dialogs_url or default).strip().rstrip("/")


def max_operator_reply_hint(max_user_id: str | None) -> str | None:
    """
    Прямого URL на переписку клиента с ботом у MAX нет.
    Для amo — короткая подсказка; основная ссылка — MAX_DIALOG_URL (кабинет).
    """
    uid = (max_user_id or "").strip()
    if not uid:
        return "Ответ: кабинет сотрудника → дело → «Написать клиенту в MAX»."
    biz = max_business_dialogs_url()
    return (
        f"MAX user_id {uid}. Быстрый ответ — ссылка «Диалог MAX» выше. "
        f"Или MAX Business ({biz}) → бот «Стаж и пенсия» → Диалоги → {uid}."
    )
