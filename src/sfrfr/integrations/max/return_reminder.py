"""Клиент вернулся в чат после паузы — напоминаем, на чём остановились и что делать сейчас."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import checklist_offer, questionnaire_flow
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store

Reply = Callable[[str, list[dict[str, Any]] | None], Any]

WELCOME_BACK = "С возвращением!"
NEED_DOCS_TEXT = (
    f"{WELCOME_BACK} Ваше дело создано. Сейчас нужно прислать документы: "
    "выписку из ИЛС (сведения о стаже) и трудовую книжку — фото или PDF прямо в этот чат. "
    "Если есть вопрос — напишите его, отвечу."
)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def touch(rec: MaxIntakeRecord, *, now: datetime | None = None) -> bool:
    """Отметить контакт. True — клиент вернулся после паузы дольше порога."""
    hours = int(get_settings().max_return_reminder_hours or 0)
    moment = now or datetime.now(UTC)
    previous = _parse(rec.last_seen_at)
    rec.last_seen_at = moment.isoformat()
    get_intake_store().save(rec)
    return bool(hours > 0 and previous and moment - previous >= timedelta(hours=hours))


def count_case_documents(case_id: str | None, *, fallback: int = 0) -> int:
    if not case_id or len(str(case_id)) < 32:
        return fallback
    try:
        from sfrfr.db.session import get_supabase_client

        res = (
            get_supabase_client()
            .table("documents")
            .select("id", count="exact")
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )
        return max(int(res.count or 0), fallback)
    except Exception:  # noqa: BLE001
        return fallback


def docs_text(count: int) -> str:
    return (
        f"{WELCOME_BACK} Документы получены: {count}. Специалист их изучает и напишет "
        "в этом чате. Если есть ещё документы или вопрос — пришлите их сюда."
    )


def remind(rec: MaxIntakeRecord, reply: Reply, *, text: str, docs_count: int) -> tuple[str, bool]:
    """Отправить напоминание. Вернуть (текст, остановить ли дальнейшую обработку)."""
    if q.is_active(rec):
        body = questionnaire_flow.send_current_question(
            rec, reply, prefix=f"{WELCOME_BACK} Продолжим анкету — осталось немного."
        )
        return body, True
    if checklist_offer.is_active(rec):
        if rec.lm_step == "email" and q.clean_email(text):
            return "", False
        hint = (
            checklist_offer.ASK_EMAIL_TEXT
            if rec.lm_step == "email"
            else checklist_offer.ASK_FORMAT_TEXT
        )
        body = f"{WELCOME_BACK} {hint}"
        reply(body, None)
        return body, True
    if docs_count > 0:
        body = docs_text(docs_count)
        reply(body, None)
        return body, True
    reply(NEED_DOCS_TEXT, q.menu_keyboard())
    return NEED_DOCS_TEXT, True
