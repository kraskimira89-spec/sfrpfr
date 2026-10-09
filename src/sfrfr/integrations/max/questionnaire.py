"""Анкета нового клиента в MAX (ТЗ-35 B1): короткие вопросы после «Начать».

ФИО и год рождения не спрашиваем — берём из выписок/документов.
Обращение в чате — по имени из профиля MAX (имя или имя+отчество, без фамилии).
"""

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
    "experience",
    "phone",
    "email",
    "problem",
)

CALLBACK_PREFIX = "q:"
SKIP_MIDDLE_NAME = "q:skip:middle_name"  # совместимость со старыми кнопками
SKIP_EMAIL = "q:skip:email"
FIX_NAME = "q:fix_name"  # совместимость: игнорируем
NAME_SOURCE_KEY = "name_source"
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
    "Спасибо! Чтобы завести дело, ответьте на несколько коротких вопросов. "
    "Фамилию, имя, отчество и год рождения не спрашиваем — "
    "это берём из выписок и документов, которые вы пришлёте. "
    "Обращаемся по имени из вашего профиля MAX. "
    "Файлы можно присылать в любой момент — анкета продолжится с того же места."
)

QUESTIONS: dict[str, str] = {
    "experience": "Ориентировочный общий стаж",
    "phone": "Телефон для связи, например +7 900 123-45-67",
    "email": "E-mail (необязательно)",
    "problem": (
        "Коротко опишите проблему своими словами: например, «не учли стаж», "
        "«нет периода в ИЛС», «нужна архивная справка о стаже». До 2000 символов."
    ),
}

ERRORS: dict[str, str] = {
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


def _next_step(answers: dict[str, str], after: int = -1) -> str | None:
    for step in STEPS[after + 1 :]:
        if step not in answers:
            return step
    return None


def begin(rec: MaxIntakeRecord) -> None:
    """Имя из MAX сохраняем для обращения; вопросы ФИО/года рождения не задаём."""
    answers: dict[str, str] = {}
    first = clean_name(rec.max_first_name or "")
    last = clean_name(rec.max_last_name or "")
    if first:
        answers["first_name"] = first
        answers[NAME_SOURCE_KEY] = "max"
    if last:
        # Только для карточки/CRM; в обращении к клиенту не используем.
        answers["last_name"] = last
        answers.setdefault(NAME_SOURCE_KEY, "max")
    rec.q_answers = answers
    rec.q_step = _next_step(answers)
    rec.q_completed_at = None


def max_salutation(answers: dict[str, str] | None = None, *, first_name: str | None = None) -> str:
    """Обращение: имя или имя+отчество из профиля MAX. Без фамилии и без угадывания пола."""
    from sfrfr.utils.person_name import client_salutation, welcome_salutation

    source = (first_name or "").strip() or str((answers or {}).get("first_name") or "").strip()
    if not source:
        return ""
    # Только first_name профиля — фамилию из answers не подмешиваем.
    welcome = welcome_salutation(source)
    if welcome:
        return welcome
    sal = client_salutation(source)
    return "" if sal == "Клиент" else sal


def prefilled_name(answers: dict[str, str]) -> str:
    """Имя для интро: только обращение, не «Фамилия Имя»."""
    if answers.get(NAME_SOURCE_KEY) != "max":
        return ""
    return max_salutation(answers)


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


def question(
    step: str, answers: dict[str, str] | None = None
) -> tuple[str, list[dict[str, Any]] | None]:
    from sfrfr.utils.ru_question_progress import with_question_progress

    del answers  # имя больше не правим кнопкой в анкете
    body = QUESTIONS[step]
    n = STEPS.index(step) + 1
    text = with_question_progress(body, n=n, total=len(STEPS))
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
    if payload == FIX_NAME:
        # Старая кнопка: ФИО больше не спрашиваем — просто повторяем текущий шаг.
        return AnswerResult(accepted=True)
    value = _parse(step, text or "", payload or "")
    if value is None:
        return AnswerResult(accepted=False, error=ERRORS[step])
    answers = dict(rec.q_answers or {})
    answers[step] = value
    rec.q_answers = answers
    nxt = _next_step(answers, STEPS.index(step))
    if nxt is not None:
        rec.q_step = nxt
        return AnswerResult(accepted=True)
    rec.q_step = None
    rec.q_completed_at = datetime.now(UTC).isoformat()
    return AnswerResult(accepted=True, done=True)


def full_name(answers: dict[str, str]) -> str:
    """Для карточки: если есть только имя из MAX — его; полные ФИО ждут из документов."""
    first = (answers.get("first_name") or "").strip()
    last = (answers.get("last_name") or "").strip()
    if first and last:
        # Порядок РФ для папки: Фамилия Имя (без выдуманного отчества).
        return f"{last} {first}".strip()
    return first or last


def summary_text(answers: dict[str, str]) -> str:
    exp = EXPERIENCE_LABELS.get(answers.get("experience") or "", "—")
    salutation = max_salutation(answers) or full_name(answers) or "—"
    return "\n".join(
        [
            "Анкета клиента (MAX):",
            f"Обращение (MAX): {salutation}",
            f"Стаж: {exp.lower()}",
            f"Телефон: {answers.get('phone') or '—'}",
            f"E-mail: {answers.get('email') or 'не указан'}",
            f"Проблема: {answers.get('problem') or '—'}",
            "ФИО и год рождения — из документов клиента.",
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
    """Записать анкету в clients/cases; ФИО полное — позже из документов."""
    try:
        from sfrfr.db.session import get_supabase_client

        sb = get_supabase_client()
    except Exception as exc:  # noqa: BLE001
        logger.warning("questionnaire save skipped: %s", exc)
        return False
    ok = True
    if client_id:
        name = full_name(answers)
        base: dict[str, Any] = {"phone": answers.get("phone")}
        if name:
            base["full_name"] = name
        if answers.get("email"):
            base["email"] = answers["email"]
        extended = {
            **base,
            "last_name": answers.get("last_name") or None,
            "first_name": answers.get("first_name") or None,
            "middle_name": None,
            "birth_year": None,
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
