"""Автоответ бота в едином чате кабинет ↔ MAX по контексту дела."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_RESULT_QUESTION = re.compile(
    r"(когда\s+(будет|ждать|ждём|получу|готов|готова|появится|выш)"
    r"|срок\s+(проверк|результат|ожидан)"
    r"|когда\s+.*\s+результат"
    r"|результат\s+.*\s+когда)",
    re.IGNORECASE,
)

_DOC_QUESTION = re.compile(
    r"(какой\s+документ|что\s+загруз|какие\s+документ|что\s+нужно\s+загруз)",
    re.IGNORECASE,
)

_REPLACE_QUESTION = re.compile(
    r"(заменить|перезагруз|другой\s+файл).*(файл|документ|скан)"
    r"|(файл|документ).*(заменить|перезагруз)",
    re.IGNORECASE,
)


def _work_map_for_case(case: dict[str, Any]) -> dict[str, Any]:
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.client_work_map import build_client_work_map

    case_id = str(case["id"])
    repo = CaseRepository()
    try:
        scenarios = repo.list_case_scenarios(case_id)
    except Exception as exc:  # noqa: BLE001
        logger.info("case_scenarios skipped: %s", exc)
        scenarios = []
    return build_client_work_map(
        pipeline_status=str(case.get("pipeline_status") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        consent_accepted=repo.has_consent(case_id),
        documents=list(case.get("documents") or []),
        checklist_items=list(case.get("checklist_items") or []),
        orders=repo.list_orders(case_id),
        scenario_rows=scenarios,
    )


def rule_based_reply(user_text: str, work: dict[str, Any]) -> str | None:
    """Быстрые ответы по статусу дела без LLM."""
    text = (user_text or "").strip()
    if not text:
        return None
    status_key = str(work.get("status_key") or "")
    now_need = str(work.get("now_need") or "").strip()
    sla = str(work.get("sla_note") or "").strip()

    if _RESULT_QUESTION.search(text):
        if status_key in {"result_ready", "done"}:
            return (
                "Итог проверки уже готов — откройте блок «Итог первичной проверки» "
                "на этой странице или скачайте PDF. Решение о пенсии принимает только СФР."
            )
        if status_key in {"docs_review", "diagnosis"}:
            return (
                "Сейчас специалист проверяет комплект документов — обычно до 1 рабочего дня. "
                "Когда итог будет готов, он появится здесь в чате "
                "и в разделе «Итог первичной проверки»."
            )
        if status_key in {"waiting_docs", "need_info"}:
            need = now_need or "загрузить обязательные документы"
            return (
                f"Сначала нужно: {need}. Файлы — в разделе «Мои документы» на этой странице. "
                "После загрузки комплекта проверка обычно занимает до 1 рабочего дня."
            )
        if status_key == "consent":
            return (
                "Сначала подтвердите согласие на обработку персональных данных — "
                "тогда можно загрузить документы и начнётся проверка."
            )
        return sla or (
            "Мы сообщим в этом чате, когда будет следующий шаг. "
            "Срок зависит от этапа — обычно до 1 рабочего дня после загрузки комплекта."
        )

    if _DOC_QUESTION.search(text):
        if now_need:
            return (
                f"Сейчас нужно: {now_need}. "
                "Загрузите файлы в разделе «Мои документы» на этой странице — не в чат."
            )
        return (
            "Обязательный минимум — выписка ИЛС и трудовая книжка / сведения о стаже. "
            "Загрузите их в «Мои документы»."
        )

    if _REPLACE_QUESTION.search(text):
        return (
            "Да — в «Мои документы» нажмите «Заменить файл» у нужного документа, "
            "пока специалист не принял файл. Документы в чат не отправляйте."
        )

    return None


def _llm_reply(user_text: str, work: dict[str, Any]) -> str | None:
    from sfrfr.ai.guardrails import redact_for_llm
    from sfrfr.ai.llm import LLMClient
    from sfrfr.integrations.max.llm_chat import (
        CLIENT_CHAT_SYSTEM,
        _parse_llm_payload,
        llm_chat_enabled,
        looks_like_pdn,
    )

    if looks_like_pdn(user_text):
        return (
            "Лучше не писать СНИЛС и паспорт цифрами в чат. "
            "Документы загружайте только в «Мои документы» на этой странице."
        )
    if not llm_chat_enabled():
        return None
    llm = LLMClient.for_analyze(allow_fallback=False)
    if not llm.available:
        return None
    safe = redact_for_llm(user_text)[:1500]
    user = (
        "Клиент пишет из веб-кабинета (тот же чат, что MAX; "
        "документы — только в «Мои документы»).\n"
        f"Статус дела: {work.get('status_label')}\n"
        f"Сейчас нужно от клиента: {work.get('now_need')}\n"
        f"Документы загружено: {work.get('required_uploaded')}/{work.get('required_total')}\n"
        f"Подсказка SLA: {work.get('sla_note')}\n"
        f"Сообщение клиента (обезличено):\n{safe}\n"
    )
    try:
        raw = llm.chat(system=CLIENT_CHAT_SYSTEM, user=user, temperature=0.3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cabinet case chat llm failed: %s", exc)
        return None
    reply, _buttons = _parse_llm_payload(raw)
    return reply[:700].strip() if reply else None


def _fallback_reply(work: dict[str, Any]) -> str:
    status = str(work.get("status_label") or "дело в работе")
    now_need = str(work.get("now_need") or "").strip()
    parts = [f"Понял ваш вопрос. Сейчас статус: {status}."]
    if now_need and "ничего не требуется" not in now_need.lower():
        parts.append(f"От вас сейчас: {now_need}.")
    sla = str(work.get("sla_note") or "").strip()
    if sla:
        parts.append(sla)
    parts.append("Если нужен разбор — напишите подробнее, специалист увидит сообщение в этом чате.")
    return " ".join(parts)


def _max_user_id(case: dict[str, Any]) -> str:
    client_row = case.get("clients") or {}
    if isinstance(client_row, list):
        client_row = client_row[0] if client_row else {}
    return str((client_row or {}).get("max_user_id") or "").strip()


def try_immediate_rule_reply(*, case: dict[str, Any], user_text: str) -> dict[str, Any] | None:
    """Быстрый ответ по правилам без LLM — чтобы POST /messages не зависал."""
    body = (user_text or "").strip()
    case_id = str(case.get("id") or "").strip()
    if not body or not case_id:
        return None
    try:
        work = _work_map_for_case(case)
    except Exception as exc:  # noqa: BLE001
        logger.warning("case chat bot work_map failed case=%s: %s", case_id[:8], exc)
        return None
    reply = rule_based_reply(body, work)
    if not reply:
        return None
    return _append_bot_reply(case=case, case_id=case_id, reply=reply)


def _append_bot_reply(*, case: dict[str, Any], case_id: str, reply: str) -> dict[str, Any] | None:
    from sfrfr.integrations.max.case_chat_log import append_bot_case_message

    max_uid = _max_user_id(case)
    message = append_bot_case_message(
        case_id=case_id,
        max_user_id=max_uid or None,
        text=reply,
        channel_origin="cabinet",
    )
    if max_uid and message:
        try:
            from sfrfr.services.case_chat_delivery import enqueue_max_delivery

            enqueue_max_delivery(
                case_id=case_id,
                message_id=str(message.get("id") or "") or None,
                max_user_id=max_uid,
                body=reply,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("case chat bot MAX mirror failed: %s", exc)
    return message


def auto_reply_to_client_message(*, case: dict[str, Any], user_text: str) -> dict[str, Any] | None:
    """Ответ бота в ленту дела (author_kind=system) и в MAX при связке."""
    body = (user_text or "").strip()
    case_id = str(case.get("id") or "").strip()
    if not body or not case_id:
        return None
    try:
        work = _work_map_for_case(case)
    except Exception as exc:  # noqa: BLE001
        logger.warning("case chat bot work_map failed case=%s: %s", case_id[:8], exc)
        work = {}

    reply = rule_based_reply(body, work)
    if not reply:
        reply = _llm_reply(body, work)
    if not reply:
        reply = _fallback_reply(work) if work else (
            "Понял ваш вопрос. Специалист увидит сообщение в этом чате и ответит здесь."
        )
    return _append_bot_reply(case=case, case_id=case_id, reply=reply)
