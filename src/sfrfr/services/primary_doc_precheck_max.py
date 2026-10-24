"""Слой 3: ветки MAX + запрещённые формулировки.

Не меняет comparison_status и findings.
"""

from __future__ import annotations

import re
from typing import Any

_BANNED = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"нашли недоплат",
        r"точно положен[аоы] прибавк",
        r"вернум потерянн",
        r"анализ окупит",
        r"срочно оплат",
        r"ошибок нет,? но анализ обязателен",
        r"пенсия точно занижен",
        r"недоплачивают",
        r"сколько вам добавят",
        r"гарантир\w* прибав",
    )
]

_SAFE_FALLBACK = (
    "Первичная проверка завершена. Подробности — в резюме. "
    "Мы не подтверждаем и не опровергаем размер пенсии на этом шаге."
)


def sanitize_client_text(text: str) -> tuple[str, bool]:
    """Вернуть (текст, blocked). Запрещённые обещания не отправляются."""
    raw = (text or "").strip()
    if not raw:
        return _SAFE_FALLBACK, True
    for pat in _BANNED:
        if pat.search(raw):
            return _SAFE_FALLBACK, True
    return raw, False


def select_max_branch(primary: dict[str, Any]) -> str:
    """Приоритет веток ТЗ §2.1."""
    if str(primary.get("data_status") or "") == "identity_conflict":
        return "staff"
    if str(primary.get("execution_status") or "") == "failed":
        return "recover"
    next_action = str(primary.get("next_action") or "")
    if next_action == "upload_documents":
        return "need_docs"
    if next_action == "answer_question":
        return "need_answer"
    if str(primary.get("comparison_status") or "") == "discrepancies_found":
        return "discrepancy"
    if next_action == "staff_review":
        return "staff"
    if str(primary.get("comparison_status") or "") == "no_discrepancies_found":
        return "clear"
    outcome = str(primary.get("outcome") or "")
    mapping = {
        "failed": "recover",
        "insufficient_documents": "need_docs",
        "needs_clarification": "need_answer",
        "discrepancies_found": "discrepancy",
        "manual_review_required": "staff",
        "no_discrepancies_found": "clear",
    }
    return mapping.get(outcome, "staff")


def resolve_stale_callback(
    *,
    requested_check_id: str,
    current_check_id: str,
    current_primary: dict[str, Any],
) -> dict[str, Any]:
    """Старый callback не запускает заказ по устаревшему результату."""
    req = (requested_check_id or "").strip()
    cur = (current_check_id or "").strip()
    if req and cur and req != cur:
        return {
            "stale": True,
            "action": "show_current",
            "check_id": cur,
            "primary": current_primary,
            "message": (
                "Результат проверки обновился. Показываем актуальное состояние."
            ),
        }
    return {
        "stale": False,
        "action": "proceed",
        "check_id": cur or req,
        "primary": current_primary,
    }


def answer_faq(question: str, primary: dict[str, Any]) -> str:
    q = (question or "").casefold()
    rec = primary.get("recommendation") if isinstance(primary.get("recommendation"), dict) else {}
    if "недоплач" in q or ("точно" in q and "пенс" in q):
        return (
            "Различие документов само по себе не подтверждает недоплату. "
            "Нужна проверка оснований учёта периода — это уже не первичное сравнение."
        )
    if "сколько" in q and ("добав" in q or "прибав" in q):
        return (
            "По разнице дат мы не рассчитываем прибавку. "
            "Первичная проверка только сопоставляет представленные сведения."
        )
    if "почему" in q and ("плат" in q or "анализ" in q):
        if rec.get("offer_paid_analysis"):
            return (
                "Подробный анализ нужен, чтобы проверить конкретный вопрос по периоду "
                "и подготовить обоснованный следующий шаг. Заказ добровольный."
            )
        return "Сейчас нет оснований предлагать платный анализ по этой проверке."
    if "оплатил" in q or "уже заплат" in q:
        return (
            "Если заказ уже подтверждён, повторно покупать услугу не нужно. "
            "Статус заказа смотрит сотрудник."
        )
    if "дослал" in q or "загрузил" in q:
        return (
            "Если файл уже в деле, можно запустить проверку снова по новой версии комплекта."
        )
    if "не хочу" in q or "отказ" in q:
        return "Хорошо, предложение убираем. Резюме проверки остаётся доступным."
    if "человек" in q or "сотрудник" in q or "специалист" in q:
        return (
            "Можно передать вопрос сотруднику. "
            "Сообщение «специалист подключён» появится только после реальной передачи."
        )
    text = str(primary.get("client_summary") or _SAFE_FALLBACK)
    safe, _ = sanitize_client_text(text)
    return safe
