"""Черновик отзыва по ответам анкеты (ТЗ-19): ИИ или шаблон, без ПДн и без автопубликации."""

from __future__ import annotations

from typing import Any

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient

REVIEW_PUBLISH_URL = "https://proverkastaza.ru/otzyv/"
REVIEW_ANKETA_URL = "https://proverkastaza.ru/anketa-otzyv/"

REVIEW_DRAFT_SYSTEM = (
    "Ты помогаешь клиенту сервиса «Проверка стажа» сформулировать короткий отзыв "
    "для публикации на Яндекс Картах. "
    "Пиши от первого лица по ответам клиента. Не выдумывай факты. "
    "Запрещено: СНИЛС, паспорт, ФИО третьих лиц, суммы пенсии, обещание перерасчёта, "
    "фразы «поставьте 5» / «обязательно 5 звёзд», упоминание что сервис — это СФР. "
    "Можно кратко: готовили документы/план, подаёт клиент сам, решение принимает СФР — "
    "только если это следует из ответов. "
    "Верни только текст отзыва (2–5 предложений), без заголовка и кавычек."
)

# id → (question label, options: id → label)
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "helped",
        "label": "Чем мы помогли?",
        "options": {
            "ils_labor": "Сверили трудовую с выпиской ИЛС",
            "plan": "Подготовили план / проект обращения",
            "word": "Перенесли трудовую в таблицу",
            "docs": "Помогли разобраться с документами",
            "other": "Другое",
        },
    },
    {
        "id": "clarity",
        "label": "Было ли понятно и спокойно общаться?",
        "options": {
            "yes": "Да",
            "mostly": "В целом да",
            "hard": "Местами сложно",
        },
    },
    {
        "id": "convenient",
        "label": "Что было удобнее всего?",
        "options": {
            "max": "Личный чат MAX",
            "cabinet": "Личный кабинет",
            "speed": "Сроки ответа",
            "steps": "Понятные шаги",
            "none": "Пока ничего из этого",
        },
    },
]


def question_catalog() -> list[dict[str, Any]]:
    """Публичный каталог вопросов для сайта / кабинета."""
    out: list[dict[str, Any]] = []
    for q in QUESTIONS:
        out.append(
            {
                "id": q["id"],
                "label": q["label"],
                "options": [
                    {"id": oid, "label": olabel}
                    for oid, olabel in (q["options"] or {}).items()
                ],
            }
        )
    return out


def _resolve_answers(raw: dict[str, str]) -> list[tuple[str, str]]:
    resolved: list[tuple[str, str]] = []
    for q in QUESTIONS:
        qid = str(q["id"])
        choice = (raw.get(qid) or "").strip()
        options: dict[str, str] = q["options"]
        label = options.get(choice) or choice
        if not label:
            continue
        resolved.append((str(q["label"]), label[:200]))
    return resolved


def template_draft(answers: dict[str, str]) -> str:
    """Детерминированный черновик без LLM (fallback)."""
    resolved = dict(_resolve_answers(answers))
    helped = resolved.get("Чем мы помогли?", "разобраться с документами по стажу")
    clarity = resolved.get("Было ли понятно и спокойно общаться?", "в целом понятно")
    convenient = resolved.get("Что было удобнее всего?", "")

    parts = [
        f"Обращался(ась) в сервис «Проверка стажа». Помогли так: {helped.lower()}.",
    ]
    if clarity.lower().startswith("да"):
        parts.append("Общение было понятное и спокойное.")
    elif "сложн" in clarity.lower():
        parts.append("В целом помогли, хотя местами было сложновато разобраться.")
    else:
        parts.append("В целом общение было понятным.")
    if convenient and "ничего" not in convenient.lower():
        parts.append(f"Удобнее всего оказалось: {convenient.lower()}.")
    parts.append(
        "Понятно, что документы и план готовят в сервисе, а обращение в СФР подаю сам(а)."
    )
    return " ".join(parts)


def build_review_draft(
    answers: dict[str, str],
    *,
    improve: str | None = None,
) -> dict[str, Any]:
    """
    Собрать черновик отзыва.
    Возвращает: draft, source (llm|template), publish_url.
    """
    resolved = _resolve_answers(answers)
    if len(resolved) < 2:
        return {
            "ok": False,
            "error": "need_at_least_two_answers",
            "draft": "",
            "source": "none",
            "publish_url": REVIEW_PUBLISH_URL,
        }

    lines = [f"— {label}: {value}" for label, value in resolved]
    extra = (improve or "").strip()[:400]
    if extra:
        lines.append(f"— Что улучшить (если указали): {extra}")

    user_blob = "Ответы клиента:\n" + "\n".join(lines)
    draft = ""
    source = "template"

    llm = LLMClient.for_draft()
    if llm.available:
        try:
            draft = (
                llm.chat(system=REVIEW_DRAFT_SYSTEM, user=redact_for_llm(user_blob)) or ""
            ).strip()
            if draft:
                source = "llm"
        except Exception:  # noqa: BLE001
            draft = ""

    if not draft:
        draft = template_draft(answers)
        source = "template"

    # Жёсткая подчистка типичных запретов
    banned = ("поставьте 5", "ставьте пять", "гарантируем перерасчёт", "снилс")
    lower = draft.lower()
    if any(b in lower for b in banned):
        draft = template_draft(answers)
        source = "template"

    return {
        "ok": True,
        "draft": draft[:1200],
        "source": source,
        "publish_url": REVIEW_PUBLISH_URL,
        "anketa_url": REVIEW_ANKETA_URL,
    }
