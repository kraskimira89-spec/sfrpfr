"""Анкета нового клиента в MAX (ТЗ-35 B1, §6): 8 вопросов после «Начать»."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.integrations.max.intake import MaxIntakeRecord

logger = logging.getLogger(__name__)

STEPS: tuple[str, ...] = (
    "last_name",
    "first_name",
    "middle_name",
    "birth_year",
    "experience",
    "phone",
    "email",
    "problem",
)

CALLBACK_PREFIX = "q:"
SKIP_MIDDLE_NAME = "q:skip:middle_name"
SKIP_EMAIL = "q:skip:email"
EXPERIENCE_PREFIX = "q:exp:"

EXPERIENCE_LABELS: dict[str, str] = {
    "lt5": "До 5 лет",
    "5_10": "5–10 лет",
    "10_20": "10–20 лет",
    "gt20": "Более 20 лет",
    "unknown": "Не знаю",
}

MENU_UPLOAD = "menu:upload"
MENU_DOCS = "menu:docs"
MENU_STATUS = "menu:status"
MENU_OPERATOR = "menu:operator"

PROBLEM_MAX_LEN = 2000
NAME_MAX_LEN = 60
MIN_AGE_YEARS = 14
MIN_BIRTH_YEAR = 1930

INTRO_TEXT = (
    "Спасибо! Чтобы завести дело, ответьте на 8 коротких вопросов. "
    "Файлы можно присылать в любой момент — анкета продолжится с того же места."
)

QUESTIONS: dict[str, str] = {
    "last_name": "1/8. Фамилия",
    "first_name": "2/8. Имя",
    "middle_name": "3/8. Отчество (если нет — нажмите кнопку)",
    "birth_year": "4/8. Год рождения — 4 цифры, например 1962",
    "experience": "5/8. Ориентировочный общий стаж",
    "phone": "6/8. Телефон для связи, например +7 900 123-45-67",
    "email": "7/8. E-mail (необязательно)",
    "problem": (
        "8/8. Коротко опишите проблему своими словами: например, «не учли стаж», "
        "«нет периода в ИЛС», «нужна архивная справка о стаже». До 2000 символов."
    ),
}

ERRORS: dict[str, str] = {
    "last_name": "Фамилию напишите буквами (можно дефис), до 60 символов.",
    "first_name": "Имя напишите буквами (можно дефис), до 60 символов.",
    "middle_name": "Отчество напишите буквами или нажмите «Нет отчества».",
    "birth_year": "Год рождения — 4 цифры, например 1962.",
    "experience": "Выберите вариант кнопкой ниже.",
    "phone": "Не получилось распознать номер. Пример: +7 900 123-45-67.",
    "email": "Похоже, в адресе ошибка. Пример: ivanova@yandex.ru — или нажмите «Пропустить».",
    "problem": "Опишите проблему хотя бы парой слов, не длиннее 2000 символов.",
}

COMPLETED_TEXT = (
    "Ваше дело создано. Дальше пришлите документы прямо в этот чат — фото или PDF. "
    "Мы готовим документы, проект обращения и план — расскажем по шагам, "
    "но подаёте через СФР или Госуслуги вы сами. Решение принимает СФР."
)

MENU_UPLOAD_TEXT = (
    "Пришлите документы прямо в этот чат: фото или PDF, можно по одному файлу. "
    "Сначала — выписку из ИЛС (сведения о стаже) с Госуслуг и трудовую книжку."
)

MENU_STATUS_FALLBACK_TEXT = (
    "Дело создано, ждём ваши документы. Как только пришлёте — специалист посмотрит "
    "и напишет вам в этом чате."
)

_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё]+(?:[ '\-][A-Za-zА-Яа-яЁё]+)*$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-zА-Яа-яЁё]{2,}$")
_SKIP_WORDS = {"нет", "пропустить", "-", "—"}


@dataclass
class AnswerResult:
    accepted: bool
    done: bool = False
    error: str | None = None


def is_active(rec: MaxIntakeRecord | None) -> bool:
    return rec is not None and rec.q_step in STEPS


def begin(rec: MaxIntakeRecord) -> None:
    rec.q_step = STEPS[0]
    rec.q_answers = {}
    rec.q_completed_at = None


def clean_name(raw: str) -> str | None:
    value = " ".join(str(raw or "").split())
    if not value or len(value) > NAME_MAX_LEN or not _NAME_RE.match(value):
        return None
    return "-".join(
        " ".join(w[:1].upper() + w[1:].lower() for w in part.split(" "))
        for part in value.split("-")
    )


def parse_birth_year(raw: str, *, now: datetime | None = None) -> int | None:
    value = str(raw or "").strip()
    if not re.fullmatch(r"\d{4}", value):
        return None
    year = int(value)
    current = (now or datetime.now(UTC)).year
    if year < MIN_BIRTH_YEAR or year > current - MIN_AGE_YEARS:
        return None
    return year


def normalize_phone(raw: str) -> str | None:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) == 11 and digits[0] in {"7", "8"}:
        return "+7" + digits[1:]
    return None


def clean_email(raw: str) -> str | None:
    value = str(raw or "").strip()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        return None
    return value.lower()


def question(step: str) -> tuple[str, list[dict[str, Any]] | None]:
    text = QUESTIONS[step]
    if step == "middle_name":
        return text, inline_buttons_keyboard(
            [[{"type": "callback", "text": "Нет отчества", "payload": SKIP_MIDDLE_NAME}]]
        )
    if step == "email":
        return text, inline_buttons_keyboard(
            [[{"type": "callback", "text": "Пропустить", "payload": SKIP_EMAIL}]]
        )
    if step == "experience":
        return text, inline_buttons_keyboard(
            [
                [{"type": "callback", "text": label, "payload": f"{EXPERIENCE_PREFIX}{key}"}]
                for key, label in EXPERIENCE_LABELS.items()
            ]
        )
    return text, None


def _parse(step: str, text: str, payload: str) -> str | None:
    """Нормализованный ответ или None, если ответ не подходит."""
    if step in {"last_name", "first_name"}:
        return clean_name(text)
    if step == "middle_name":
        if payload == SKIP_MIDDLE_NAME or text.strip().lower() in _SKIP_WORDS:
            return ""
        return clean_name(text)
    if step == "birth_year":
        year = parse_birth_year(text)
        return str(year) if year else None
    if step == "experience":
        key = payload[len(EXPERIENCE_PREFIX) :] if payload.startswith(EXPERIENCE_PREFIX) else ""
        return key if key in EXPERIENCE_LABELS else None
    if step == "phone":
        return normalize_phone(text)
    if step == "email":
        if payload == SKIP_EMAIL or text.strip().lower() in _SKIP_WORDS:
            return ""
        return clean_email(text)
    if step == "problem":
        value = str(text or "").strip()
        if len(value) < 3 or len(value) > PROBLEM_MAX_LEN:
            return None
        return value
    return None


def apply_answer(rec: MaxIntakeRecord, *, text: str, payload: str) -> AnswerResult:
    step = rec.q_step
    if step not in STEPS:
        return AnswerResult(accepted=False)
    value = _parse(step, text or "", payload or "")
    if value is None:
        return AnswerResult(accepted=False, error=ERRORS[step])
    answers = dict(rec.q_answers or {})
    answers[step] = value
    rec.q_answers = answers
    idx = STEPS.index(step)
    if idx + 1 < len(STEPS):
        rec.q_step = STEPS[idx + 1]
        return AnswerResult(accepted=True)
    rec.q_step = None
    rec.q_completed_at = datetime.now(UTC).isoformat()
    return AnswerResult(accepted=True, done=True)


def full_name(answers: dict[str, str]) -> str:
    parts = [answers.get("last_name"), answers.get("first_name"), answers.get("middle_name")]
    return " ".join(p for p in parts if p)


def summary_text(answers: dict[str, str]) -> str:
    exp = EXPERIENCE_LABELS.get(answers.get("experience") or "", "—")
    return "\n".join(
        [
            "Анкета клиента (MAX):",
            f"ФИО: {full_name(answers) or '—'}",
            f"Год рождения: {answers.get('birth_year') or '—'}",
            f"Стаж: {exp.lower()}",
            f"Телефон: {answers.get('phone') or '—'}",
            f"E-mail: {answers.get('email') or 'не указан'}",
            f"Проблема: {answers.get('problem') or '—'}",
        ]
    )


def menu_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "Загрузить документы", "payload": MENU_UPLOAD}],
            [{"type": "callback", "text": "Какие документы нужны", "payload": MENU_DOCS}],
            [{"type": "callback", "text": "Статус моего дела", "payload": MENU_STATUS}],
            [{"type": "callback", "text": "Связаться со специалистом", "payload": MENU_OPERATOR}],
        ]
    )


def save_questionnaire(
    *, answers: dict[str, str], client_id: str | None, case_id: str | None
) -> bool:
    """Записать анкету в clients/cases; без колонок B1 — только базовые поля."""
    try:
        from sfrfr.db.session import get_supabase_client

        sb = get_supabase_client()
    except Exception as exc:  # noqa: BLE001
        logger.warning("questionnaire save skipped: %s", exc)
        return False
    ok = True
    if client_id:
        base: dict[str, Any] = {"full_name": full_name(answers), "phone": answers.get("phone")}
        if answers.get("email"):
            base["email"] = answers["email"]
        extended = {
            **base,
            "last_name": answers.get("last_name"),
            "first_name": answers.get("first_name"),
            "middle_name": answers.get("middle_name") or None,
            "birth_year": int(answers["birth_year"]) if answers.get("birth_year") else None,
        }
        try:
            sb.table("clients").update(extended).eq("id", client_id).execute()
        except Exception:  # noqa: BLE001
            try:
                sb.table("clients").update(base).eq("id", client_id).execute()
            except Exception as exc:  # noqa: BLE001
                logger.warning("questionnaire client save failed: %s", exc)
                ok = False
    if case_id and len(str(case_id)) >= 32:
        try:
            sb.table("cases").update(
                {
                    "experience_bucket": answers.get("experience") or None,
                    "problem_text": answers.get("problem") or None,
                    "questionnaire_completed_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", case_id).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("questionnaire case save failed: %s", exc)
            ok = False
    return ok
