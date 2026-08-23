"""MAX: опрос понятности PDF — кнопки с одноразовыми токенами (ТЗ-29)."""

from __future__ import annotations

from typing import Any

from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.services.diagnosis_survey import CLARITY_ANSWERS, DiagnosisSurveyService

CALLBACK_PREFIX = "svy:"


def clarity_keyboard(tokens: dict[str, str]) -> list[dict[str, Any]]:
    """tokens: answer_code → raw token."""
    rows: list[list[dict[str, Any]]] = []
    for code, label in CLARITY_ANSWERS.items():
        raw = tokens.get(code)
        if not raw:
            continue
        rows.append(
            [
                {
                    "type": "callback",
                    "text": label[:64],
                    "payload": f"{CALLBACK_PREFIX}{raw}",
                }
            ]
        )
    return inline_buttons_keyboard(rows)


def handle_survey_callback(*, user_id: str, payload: str) -> dict[str, Any] | None:
    """Обработать svy:*; вернуть {text, attachments} или None."""
    _ = user_id
    if not payload.startswith(CALLBACK_PREFIX):
        return None
    raw = payload[len(CALLBACK_PREFIX) :].strip()
    if len(raw) < 10:
        return {"text": "Ссылка устарела. Напишите нам в чат — подскажем.", "attachments": None}
    try:
        out = DiagnosisSurveyService().handle_action_token(raw)
    except LookupError:
        return {
            "text": "Этот вариант уже не действует. Напишите в чат, если нужна помощь.",
            "attachments": None,
        }
    except PermissionError:
        return {"text": "Срок ответа истёк. Напишите в чат — поможем.", "attachments": None}
    return {"text": str(out.get("text") or "Ответ принят."), "attachments": None}
