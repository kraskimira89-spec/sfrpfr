"""Запись разбора ответа СФР (ступень 11)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sfrfr.db.case_repository import CaseRepository
from sfrfr.services.response_review import (
    ResponseReviewError,
    build_review_row,
    generate_response_review_draft,
    serialize_review,
    validate_outcome,
    validate_register_payload,
)


def register_response_review(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = dict(payload or {})
    idem = str(body.get("idempotency_key") or "").strip() or (
        f"{case_id}:register:{body.get('document_id')}:{uuid4()}"[:200]
    )
    existing = repo.get_response_review_by_idempotency(idem)
    if existing:
        return {
            "ok": True,
            "replayed": True,
            "action": "response_review_registered",
            "review": serialize_review(existing),
        }

    validated = validate_register_payload(body)
    # Документ должен принадлежать делу.
    docs = {str(d.get("id")): d for d in (repo.list_documents(case_id) or [])}
    if validated["document_id"] not in docs:
        raise ResponseReviewError("document_id not found on case")

    row = build_review_row(
        case_id=case_id,
        actor_id=actor_id,
        validated=validated,
        idempotency_key=idem,
        status="received",
    )
    inserted = repo.insert_response_review(row)
    is_new = str(inserted.get("id")) == str(row["id"])
    if is_new:
        repo.audit(case_id, actor_id, "response_review_registered")
        # Передача из ступени 10 открывает работу, но не «разобрано».
        repo.update_next_action(
            case_id,
            actor_id,
            next_action="Разбор ответа СФР (ступень 11)",
            waiting_on="staff",
        )
    return {
        "ok": True,
        "replayed": not is_new,
        "action": "response_review_registered",
        "review": serialize_review(inserted),
    }


def generate_and_store_ai_draft(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    review_id: str,
    response_text: str | None = None,
    package_summary: str | None = None,
    prior_analysis: str | None = None,
) -> dict[str, Any]:
    review = repo.get_response_review(review_id)
    if not review or str(review.get("case_id")) != case_id:
        raise ResponseReviewError("review not found")

    case = repo.get_case_row(case_id) or {}
    case_ref = str(case.get("public_id") or case.get("case_number") or case_id[:8])
    completeness = str(review.get("completeness") or "unknown")

    # OCR / текст ответа: payload или сниппеты пайплайна по document_id.
    text = (response_text or "").strip()
    if not text:
        text = _ocr_for_document(repo, case_id, str(review.get("document_id") or ""))

    if package_summary is None:
        package_summary = _package_summary(repo, case_id)
    if prior_analysis is None:
        prior_analysis = _prior_analysis(case_id)

    out = generate_response_review_draft(
        case_ref=case_ref,
        response_text=text,
        package_summary=package_summary,
        prior_analysis=prior_analysis,
        completeness=completeness,
    )
    draft = str(out.get("text") or "")
    updated = repo.update_response_review(
        review_id,
        {
            "ai_draft_md": draft,
            "staff_draft_md": draft,
            "status": "reviewing",
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    repo.audit(case_id, actor_id, "response_review_ai_draft")
    return {
        "ok": True,
        "source": out.get("source"),
        "reason": out.get("reason"),
        "llm_provider": out.get("llm_provider"),
        "review": serialize_review(updated or review),
        "text": draft,
    }


def save_staff_draft(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    review_id: str,
    staff_draft_md: str,
) -> dict[str, Any]:
    review = repo.get_response_review(review_id)
    if not review or str(review.get("case_id")) != case_id:
        raise ResponseReviewError("review not found")
    updated = repo.update_response_review(
        review_id,
        {
            "staff_draft_md": staff_draft_md,
            "status": "reviewing"
            if str(review.get("status")) == "received"
            else review.get("status"),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    repo.audit(case_id, actor_id, "response_review_staff_saved")
    return {"ok": True, "review": serialize_review(updated or review)}


def mark_reviewed(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    review_id: str,
    staff_draft_md: str | None = None,
) -> dict[str, Any]:
    review = repo.get_response_review(review_id)
    if not review or str(review.get("case_id")) != case_id:
        raise ResponseReviewError("review not found")
    now = datetime.now(UTC).isoformat()
    patch: dict[str, Any] = {
        "status": "reviewed",
        "reviewed_at": now,
        "updated_at": now,
    }
    if staff_draft_md is not None:
        patch["staff_draft_md"] = staff_draft_md
    text = str(
        patch.get("staff_draft_md")
        or review.get("staff_draft_md")
        or review.get("ai_draft_md")
        or ""
    ).strip()
    if not text:
        raise ResponseReviewError("draft is empty — нельзя отметить проверенным")
    updated = repo.update_response_review(review_id, patch)
    repo.audit(case_id, actor_id, "response_review_reviewed")
    return {"ok": True, "review": serialize_review(updated or review)}


def set_outcome(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    review_id: str,
    outcome: str,
    case_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Выбор пути: документы / эскалация (12) / закрытие (13) / ожидание клиента.

    Не создаёт счёт 8 000 ₽. Не закрывает дело автоматически при wait_client.
    """
    o = validate_outcome(outcome)
    review = repo.get_response_review(review_id)
    if not review or str(review.get("case_id")) != case_id:
        raise ResponseReviewError("review not found")
    if str(review.get("status")) != "reviewed":
        raise ResponseReviewError("review must be reviewed before outcome")

    now = datetime.now(UTC).isoformat()
    updated = repo.update_response_review(
        review_id,
        {
            "outcome": o,
            "outcome_at": now,
            "outcome_actor_id": actor_id,
            "updated_at": now,
        },
    )
    action = f"response_review_outcome:{o}"
    repo.audit(case_id, actor_id, action)

    waiting = {
        "need_docs": "client",
        "offer_escalation": "client",
        "close": "staff",
        "wait_client": "client",
    }[o]
    next_text = {
        "need_docs": "Запросить документы/пояснения по ответу СФР",
        "offer_escalation": "Предложить доп. обращения (ступень 12) — без автосчёта",
        "close": "Передать на завершение (ступень 13)",
        "wait_client": "Ожидание решения клиента (дело не закрывать автоматически)",
    }[o]
    # Дату контроля не трогаем — только текст/waiting (срок через ступень 10).
    _ = case_row  # сохраняем сигнатуру для вызывающих
    repo.update_next_action(
        case_id,
        actor_id,
        next_action=next_text,
        waiting_on=waiting,
    )
    return {
        "ok": True,
        "action": action,
        "outcome": o,
        "review": serialize_review(updated or review),
        # Явно: эскалация = предложение, не счёт.
        "invoice_created": False,
        "note": (
            "Переход к ступени 12 не создаёт счёт 8 000 ₽ автоматически."
            if o == "offer_escalation"
            else None
        ),
    }


def apply_deadline_to_control(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    review_id: str,
    control_at: str,
    case_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Цитата срока из ответа → контроль через механизм ступени 10 (next_action_at)."""
    from sfrfr.services.follow_up_record import record_follow_up_control

    review = repo.get_response_review(review_id)
    if not review or str(review.get("case_id")) != case_id:
        raise ResponseReviewError("review not found")
    quote = str(review.get("deadline_quote") or "").strip()
    if not quote:
        raise ResponseReviewError("deadline_quote is empty — укажите точный текст из ответа")
    source = str(review.get("deadline_quote_source") or "").strip()
    page = str(review.get("deadline_quote_page") or "").strip()
    reason = f"Срок из ответа СФР: «{quote[:400]}»"
    if source:
        reason += f" · источник: {source}"
    if page:
        reason += f" · стр./п. {page}"
    return record_follow_up_control(
        repo,
        case_id=case_id,
        actor_id=actor_id,
        payload={
            "kind": "assign_control",
            "control_at": control_at,
            "next_action_text": "Срок из ответа СФР (проверка сотрудником)",
            "reason": reason,
            "waiting_on": "client",
            "idempotency_key": f"deadline:{review_id}:{control_at}"[:200],
        },
        case_row=case_row,
    )


def _ocr_for_document(repo: CaseRepository, case_id: str, document_id: str) -> str:
    if not document_id:
        return ""
    try:
        pipeline = repo.get_pipeline_row(case_id) or {}
        chunks: list[str] = []
        for row in list(pipeline.get("ocr_texts") or []):
            if not isinstance(row, dict):
                continue
            did = str(row.get("document_id") or row.get("doc_id") or "")
            if did and did != document_id:
                continue
            sample = str(row.get("text") or row.get("content") or "").strip()
            if sample:
                chunks.append(sample[:4000])
        return "\n\n".join(chunks)[:8000]
    except Exception:  # noqa: BLE001
        return ""


def _package_summary(repo: CaseRepository, case_id: str) -> str:
    try:
        parts: list[str] = []
        draft = repo.get_pipeline_draft(case_id) or {}
        title = str(draft.get("title") or "").strip()
        body = str(draft.get("body") or "").strip()
        if title:
            parts.append(title)
        if body:
            parts.append(body[:1500])
        reports = repo.list_submission_reports(case_id) or []
        if reports:
            r0 = reports[0]
            bits = [
                str(r0.get("submitted_what") or "").strip(),
                str(r0.get("method") or "").strip(),
                str(r0.get("submitted_on") or "").strip(),
            ]
            line = " · ".join(b for b in bits if b)
            if line:
                parts.append(f"Подача: {line}")
        return "\n".join(parts) if parts else "—"
    except Exception:  # noqa: BLE001
        return "—"


def _prior_analysis(case_id: str) -> str:
    try:
        from sfrfr.services.full_analysis_workflow import FullAnalysisWorkflow

        state = FullAnalysisWorkflow().get_state(case_id)
        current = (state or {}).get("current") or {}
        return str(current.get("markdown") or "")[:4000]
    except Exception:  # noqa: BLE001
        return ""


__all__ = [
    "ResponseReviewError",
    "register_response_review",
    "generate_and_store_ai_draft",
    "save_staff_draft",
    "mark_reviewed",
    "set_outcome",
    "apply_deadline_to_control",
]
