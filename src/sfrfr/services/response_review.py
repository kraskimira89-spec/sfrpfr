"""Ступень 11: разбор ответа СФР (валидация + AI-черновик)."""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from typing import Any, Literal, Protocol
from uuid import uuid4

from sfrfr.ai.guardrails import redact_for_llm

logger = logging.getLogger(__name__)

SOURCES = frozenset({"cabinet", "chat", "mail", "staff"})
COMPLETENESS = frozenset({"all_pages", "need_more_pages", "unknown"})
STATUSES = frozenset({"received", "reviewing", "reviewed"})
OUTCOMES = frozenset({"need_docs", "offer_escalation", "close", "wait_client"})

_POSITION = (
    "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
    "Решение принимает СФР."
)

SYSTEM = """Ты помощник сотрудника сервиса проверки стажа.
Готовишь проект РАЗБОРА ответа СФР для проверки специалистом.

Правила:
- опирайся только на текст ответа СФР и известный пакет обращений;
- не выдумывай решения, суммы, перерасчёт, номера дел;
- если документ нечитаемый или неполный — напиши, что нужно уточнение, а не уверенный вывод;
- каждый существенный вывод снабжай пометкой источника (страница/пункт/цитата), если есть;
- структура Markdown:
  ## Что сообщил СФР
  ## Какие вопросы рассмотрены
  ## Что подтверждено (с источником)
  ## Что осталось неясным
  ## Следующее действие
  ## Срок из ответа (если есть точная цитата; иначе «в ответе срок не указан»)
- в конце позиция сервиса (подаёт клиент, решение — СФР)
- тон спокойный, без обещаний выплаты.
"""


class ResponseReviewError(ValueError):
    """Некорректные поля разбора ответа."""


class _LLM(Protocol):
    @property
    def available(self) -> bool: ...

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str: ...


def _parse_date(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as exc:
        raise ResponseReviewError("doc_date must be YYYY-MM-DD") from exc


def validate_register_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("document_id") or "").strip()
    if not doc_id:
        raise ResponseReviewError("document_id is required")
    source = str(payload.get("source") or "staff").strip().lower()
    if source not in SOURCES:
        raise ResponseReviewError("source must be cabinet|chat|mail|staff")
    completeness = str(payload.get("completeness") or "unknown").strip().lower()
    if completeness not in COMPLETENESS:
        raise ResponseReviewError(
            "completeness must be all_pages|need_more_pages|unknown"
        )
    submission_report_id = (
        str(payload.get("submission_report_id") or "").strip() or None
    )
    return {
        "document_id": doc_id,
        "submission_report_id": submission_report_id,
        "doc_date": _parse_date(payload.get("doc_date")),
        "doc_number": (str(payload.get("doc_number") or "").strip()[:120] or None),
        "received_at": (str(payload.get("received_at") or "").strip() or None)
        or datetime.now(UTC).isoformat(),
        "source": source,
        "completeness": completeness,
        "deadline_quote": (str(payload.get("deadline_quote") or "").strip()[:2000] or None),
        "deadline_quote_source": (
            str(payload.get("deadline_quote_source") or "").strip()[:400] or None
        ),
        "deadline_quote_page": (
            str(payload.get("deadline_quote_page") or "").strip()[:80] or None
        ),
    }


def validate_outcome(outcome: str) -> str:
    o = str(outcome or "").strip().lower()
    if o not in OUTCOMES:
        raise ResponseReviewError(
            "outcome must be need_docs|offer_escalation|close|wait_client"
        )
    return o


def build_review_row(
    *,
    case_id: str,
    actor_id: str | None,
    validated: dict[str, Any],
    idempotency_key: str,
    status: str = "received",
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "case_id": case_id,
        "actor_id": actor_id,
        "document_id": validated["document_id"],
        "submission_report_id": validated.get("submission_report_id"),
        "doc_date": validated.get("doc_date"),
        "doc_number": validated.get("doc_number"),
        "received_at": validated.get("received_at"),
        "source": validated.get("source"),
        "completeness": validated.get("completeness") or "unknown",
        "status": status if status in STATUSES else "received",
        "deadline_quote": validated.get("deadline_quote"),
        "deadline_quote_source": validated.get("deadline_quote_source"),
        "deadline_quote_page": validated.get("deadline_quote_page"),
        "idempotency_key": idempotency_key[:200],
    }


def serialize_review(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "case_id": str(row.get("case_id") or ""),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "document_id": row.get("document_id"),
        "submission_report_id": row.get("submission_report_id"),
        "doc_date": row.get("doc_date"),
        "doc_number": row.get("doc_number"),
        "received_at": row.get("received_at"),
        "source": row.get("source"),
        "completeness": row.get("completeness"),
        "status": row.get("status"),
        "deadline_quote": row.get("deadline_quote"),
        "deadline_quote_source": row.get("deadline_quote_source"),
        "deadline_quote_page": row.get("deadline_quote_page"),
        "ai_draft_md": row.get("ai_draft_md"),
        "staff_draft_md": row.get("staff_draft_md"),
        "reviewed_at": row.get("reviewed_at"),
        "sent_at": row.get("sent_at"),
        "sent_channel": row.get("sent_channel"),
        "outcome": row.get("outcome"),
        "outcome_at": row.get("outcome_at"),
    }


def _template_draft(*, incomplete: bool) -> str:
    unclear = (
        "Документ отмечен как неполный / нечитаемый — запросите дополнительные страницы "
        "или более качественную копию. Уверенный разбор не сформирован."
        if incomplete
        else "Недостаточно данных для уверенных выводов — проверьте текст ответа."
    )
    return (
        "## Что сообщил СФР\n"
        "Требуется проверка специалистом по исходному файлу.\n\n"
        "## Какие вопросы рассмотрены\n"
        "—\n\n"
        "## Что подтверждено (с источником)\n"
        "—\n\n"
        f"## Что осталось неясным\n{unclear}\n\n"
        "## Следующее действие\n"
        "Проверить ответ вручную и при необходимости запросить уточнение у клиента.\n\n"
        "## Срок из ответа\n"
        "в ответе срок не указан (или не извлечён автоматически)\n\n"
        f"{_POSITION}\n"
    )


def generate_response_review_draft(
    *,
    case_ref: str,
    response_text: str | None,
    package_summary: str | None,
    prior_analysis: str | None,
    completeness: str = "unknown",
    llm: _LLM | Literal["auto"] | None = "auto",
) -> dict[str, Any]:
    incomplete = completeness == "need_more_pages" or not (response_text or "").strip()
    template = _template_draft(incomplete=incomplete)
    if incomplete and completeness == "need_more_pages":
        return {"text": template, "source": "template", "reason": "incomplete_document"}

    client: _LLM | None
    if llm == "auto":
        from sfrfr.ai.llm import LLMClient

        client = LLMClient.for_analyze(allow_fallback=True, foreign_ok=True)
    else:
        client = llm  # type: ignore[assignment]

    if client is None or not getattr(client, "available", False):
        return {"text": template, "source": "template", "reason": "llm_unavailable"}

    user = (
        f"Дело (без ПДн): {redact_for_llm(case_ref)}\n\n"
        f"Поданный пакет (кратко):\n{redact_for_llm(package_summary or '—')[:3000]}\n\n"
        f"Предыдущий подробный разбор (фрагмент):\n"
        f"{redact_for_llm(prior_analysis or '—')[:4000]}\n\n"
        f"Текст / OCR ответа СФР:\n{redact_for_llm(response_text or '—')[:8000]}\n\n"
        "Составь проект разбора по правилам system."
    )
    try:
        raw = client.chat(system=SYSTEM, user=user, temperature=0.2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("response_review draft llm_error %s", type(exc).__name__)
        return {"text": template, "source": "template", "reason": "llm_error"}

    text = re.sub(r"\n{3,}", "\n\n", str(raw or "").strip())
    if not text or len(text) < 80:
        return {"text": template, "source": "template", "reason": "llm_empty"}
    lower = text.lower()
    if "решение принимает сфр" not in lower and "подаёте через сфр" not in lower:
        text = f"{text.rstrip()}\n\n{_POSITION}"
    return {
        "text": text,
        "source": "ai",
        "llm_provider": getattr(client, "last_provider_used", None)
        or getattr(client, "provider", None),
    }
