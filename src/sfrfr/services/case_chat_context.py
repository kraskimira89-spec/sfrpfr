"""Контекст единого чата для LLM: история переписки и стадия сделки без ПДн."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.ai.guardrails import redact_for_llm

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 20
MAX_BODY_CHARS = 400

_AUTHOR_LABELS: dict[str, str] = {
    "client": "Клиент",
    "representative": "Представитель",
    "staff": "Специалист",
    "system": "Бот",
    "bot": "Бот",
}


def author_label(author_kind: str | None) -> str:
    kind = str(author_kind or "unknown").strip().lower()
    return _AUTHOR_LABELS.get(kind, "Участник")


def fetch_recent_case_messages(
    case_id: str,
    *,
    limit: int = DEFAULT_HISTORY_LIMIT,
    exclude_message_id: str | None = None,
) -> list[dict[str, Any]]:
    """Последние реплики дела (хронологически), без текущего сообщения."""
    cid = (case_id or "").strip()
    if not cid:
        return []
    try:
        from sfrfr.db.session import get_supabase_client

        cap = max(1, min(int(limit), 40))
        rows = (
            get_supabase_client()
            .table("case_messages")
            .select("id, author_kind, body, created_at")
            .eq("case_id", cid)
            .order("created_at", desc=True)
            .limit(cap + (1 if exclude_message_id else 0))
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("case_chat_context fetch skipped case=%s: %s", cid[:8], exc)
        return []
    out: list[dict[str, Any]] = []
    ex = (exclude_message_id or "").strip()
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        if ex and str(row.get("id") or "") == ex:
            continue
        body = str(row.get("body") or "").strip()
        if not body:
            continue
        out.append(row)
        if len(out) >= cap:
            break
    return out


def format_thread_for_llm(
    messages: list[dict[str, Any]],
    *,
    max_body_chars: int = MAX_BODY_CHARS,
) -> str:
    """Лента «Кто: текст» для промпта (обезличено)."""
    lines: list[str] = []
    for row in messages:
        if not isinstance(row, dict):
            continue
        body = redact_for_llm(str(row.get("body") or "")).strip()
        if not body:
            continue
        label = author_label(str(row.get("author_kind") or ""))
        lines.append(f"{label}: {body[:max_body_chars]}")
    if not lines:
        return "(история пуста — это первое сообщение в теме)"
    return "\n".join(lines)


def format_deal_context(work: dict[str, Any] | None) -> str:
    """Стадия дела, CTA и оплата — для клиентского и staff LLM."""
    if not work:
        return "Стадия дела: неизвестна (дело ещё не создано или нет данных)."
    order = work.get("order") if isinstance(work.get("order"), dict) else {}
    parts = [
        f"Статус: {work.get('status_label') or '—'} ({work.get('status_key') or '—'})",
        f"Сейчас нужно от клиента: {work.get('now_need') or '—'}",
        (
            f"Документы (обязательные): "
            f"{work.get('required_uploaded', 0)}/{work.get('required_total', 0)}"
        ),
        f"Следующий шаг в кабинете (cta): {work.get('cta_key') or '—'} — "
        f"{work.get('cta_label') or '—'}",
        f"SLA: {work.get('sla_note') or '—'}",
    ]
    if order:
        parts.append(
            f"Услуга: {order.get('title') or '—'}; "
            f"сумма {order.get('amount_rub') or '—'} ₽; "
            f"статус счёта: {order.get('status_label') or order.get('state') or '—'}; "
            f"можно оплатить: {'да' if order.get('can_pay') else 'нет'}"
        )
    next_actions = work.get("next_actions") or []
    if isinstance(next_actions, list) and next_actions:
        parts.append("Плановые шаги: " + "; ".join(str(a) for a in next_actions[:4]))
    return "\n".join(parts)


def build_client_llm_user_prompt(
    *,
    channel: str,
    user_text: str,
    work: dict[str, Any] | None,
    history: list[dict[str, Any]] | None = None,
    intake_step: str | None = None,
    exclude_message_id: str | None = None,
) -> str:
    """Единый user-prompt для клиентского бота (MAX / кабинет)."""
    safe = redact_for_llm(user_text or "")[:1500]
    thread = format_thread_for_llm(history or [])
    deal = format_deal_context(work)
    header = {
        "cabinet": (
            "Клиент пишет из веб-кабинета (единый чат с MAX; "
            "документы — только в «Мои документы»)."
        ),
        "max": (
            "Клиент пишет в MAX (единый чат с кабинетом на сайте; "
            "документы — только в «Мои документы» кабинета)."
        ),
    }.get(channel, "Клиент пишет в единый чат по делу.")
    blocks = [header, "", "Контекст сделки:", deal]
    if intake_step:
        blocks.extend(
            [
                "",
                f"Шаг сценария intake (кнопки): {intake_step}",
                "Системные кнопки шага будут под ответом — дополни мягкими BUTTONS.",
            ]
        )
    blocks.extend(
        [
            "",
            "История переписки (хронологически, без ПДн):",
            thread,
            "",
            "Новое сообщение клиента (обезличено):",
            safe,
            "",
            "Учитывай всю историю: не повторяй уже данные инструкции, "
            "не задавай тот же вопрос дважды. "
            "Если can_pay=да — мягко предложи оплату в кабинете на сайте. "
            "Если клиент сомневается в цене — объясни ценность диагностики 3 000 ₽ "
            "без торга и без обещания суммы пенсии.",
        ]
    )
    return "\n".join(blocks)


def build_staff_llm_user_prompt(
    *,
    salutation: str,
    work: dict[str, Any] | None,
    messages: list[dict[str, Any]],
    pipeline_status: str | None = None,
    b2c_status: str | None = None,
) -> str:
    """User-prompt для подсказок ответов специалисту."""
    thread = format_thread_for_llm(messages, max_body_chars=500)
    deal = format_deal_context(work)
    return (
        f"Обращение к клиенту (обязательно в каждом варианте): {salutation}\n"
        f"Этап: pipeline={pipeline_status or '—'}, b2c={b2c_status or '—'}\n\n"
        f"Контекст сделки:\n{deal}\n\n"
        f"История переписки (хронологически):\n{thread}\n\n"
        "Предложи 3 варианта ответа с учётом последней реплики клиента и стадии сделки. "
        "Если клиент готов к оплате — один вариант может мягко напомнить про оплату в кабинете. "
        "Если клиент задаёт вопрос, на который бот уже отвечал — "
        "дай более точный ответ специалиста."
    )


def work_map_from_case(case: dict[str, Any]) -> dict[str, Any]:
    """Построить work_map для LLM из строки дела."""
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.client_work_map import build_client_work_map

    case_id = str(case.get("id") or "").strip()
    if not case_id:
        return {}
    repo = CaseRepository()
    try:
        scenarios = repo.list_case_scenarios(case_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("work_map scenarios skipped: %s", exc)
        scenarios = []
    return build_client_work_map(
        pipeline_status=str(case.get("pipeline_status") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        consent_accepted=repo.has_consent(case_id),
        documents=list(case.get("documents") or []),
        checklist_items=list(case.get("checklist_items") or []),
        orders=repo.list_orders(case_id) or list(case.get("orders") or []),
        scenario_rows=scenarios,
    )
