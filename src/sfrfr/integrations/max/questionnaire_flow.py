"""Ход анкеты B1 в диалоге MAX: вопросы, повтор, итог и меню (без зависимостей от handler)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store

Reply = Callable[[str, list[dict[str, Any]] | None], Any]


def send_current_question(rec: MaxIntakeRecord, reply: Reply, *, prefix: str = "") -> str:
    text, keyboard = q.question(str(rec.q_step))
    full = f"{prefix}\n\n{text}" if prefix else text
    reply(full, keyboard)
    return full


def start(rec: MaxIntakeRecord, reply: Reply) -> str:
    q.begin(rec)
    get_intake_store().save(rec)
    reply(q.INTRO_TEXT, None)
    return send_current_question(rec, reply)


def handle_answer(
    rec: MaxIntakeRecord,
    reply: Reply,
    *,
    text: str,
    payload: str,
    client_id: str | None,
    case_id: str | None,
    log_summary: Callable[[str], Any],
) -> tuple[str, str]:
    """Вернуть (action, текст ответа клиенту)."""
    res = q.apply_answer(rec, text=text, payload=payload)
    if not res.accepted:
        return "max_questionnaire_invalid", send_current_question(
            rec, reply, prefix=res.error or ""
        )
    get_intake_store().save(rec)
    if not res.done:
        return "max_questionnaire_step", send_current_question(rec, reply)
    answers = dict(rec.q_answers or {})
    q.save_questionnaire(answers=answers, client_id=client_id, case_id=case_id)
    log_summary(q.summary_text(answers))
    reply(q.COMPLETED_TEXT, q.menu_keyboard())
    from sfrfr.integrations.max import checklist_offer

    reply(checklist_offer.OFFER_TEXT, checklist_offer.offer_keyboard())
    return "max_questionnaire_completed", q.COMPLETED_TEXT
