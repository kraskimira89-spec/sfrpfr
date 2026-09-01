"""Конвейер ingest: security → quality → OCR/classification → предложение размещения."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sfrfr.ai.agents.classifier import classify_document
from sfrfr.services.document_requirements import (
    BANK_REQUIREMENT_CODE,
    SCENARIO_BANK_LIMITED,
    SCENARIO_PAYOUT_RECONCILIATION,
)
from sfrfr.services.file_security import (
    MAX_PDF_PAGES,
    is_downloadable_status,
    validate_file_bytes,
)

logger = logging.getLogger(__name__)

DOC_TYPE_TO_REQUIREMENT: dict[str, str] = {
    "ils": "ils_statement",
    "labor": "labor_book",
    "labor_book": "labor_book",
    "workbook": "labor_book",
    "bank_statement": BANK_REQUIREMENT_CODE,
    "bank": BANK_REQUIREMENT_CODE,
    "children": "children_birth",
    "guardianship": "guardianship_docs",
    "marriage": "marriage_cert",
    "military": "military_docs",
    "north": "north_docs",
    "archive": "archive_docs",
    "sfr": "sfr_response",
    "sfr_response": "sfr_response",
    "client_signed_application": "client_signed_application",
    "client_signed_appeal": "client_signed_appeal",
}

SIGNED_DOC_TYPES = frozenset({"client_signed_application", "client_signed_appeal"})

CLIENT_STAGE_LABELS: dict[str, str] = {
    "uploading": "Загружаем файл",
    "security_check": "Проверяем файл",
    "quality_check": "Проверяем читаемость",
    "ocr_classification": "Определяем тип документа",
    "placement_suggestion": "Готовим предложение по размещению",
    "under_review": "Файл получен — специалист проверит",
    "accepted": "Документ принят",
    "needs_reupload": "Нужна повторная загрузка",
    "blocked_security": "Нужна повторная загрузка",
    "manual_review": "Нужна дополнительная проверка",
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _estimate_pdf_pages(data: bytes) -> int | None:
    try:
        count = len(re.findall(rb"/Type\s*/Page[^s]", data[:2_000_000]))
        return count or None
    except Exception:  # noqa: BLE001
        return None


def _quality_from_preview(preview: str) -> dict[str, Any]:
    text = (preview or "").strip()
    char_count = len(text)
    issues: list[str] = []
    score = 0.5
    if char_count < 40:
        issues.append("low_text")
        score = 0.25
        action = "reupload"
        message = "Текст плохо читается. Загрузите более чёткое фото или PDF."
    elif char_count < 120:
        issues.append("borderline_text")
        score = 0.55
        action = "manual_review"
        message = (
            "Файл принят на проверку. При необходимости специалист попросит более чёткую копию."
        )
    else:
        action = "continue"
        message = "Файл читается. Специалист проверит документ."
        score = 0.75
    return {
        "overall_score": score,
        "issues": issues,
        "recommended_action": action,
        "client_message": message,
        "char_count": char_count,
    }


def _suggest_requirement(
    *,
    doc_type_hint: str | None,
    classification_type: str | None,
    active_scenarios: set[str],
) -> dict[str, Any]:
    hint = (doc_type_hint or "").strip().lower()
    req = DOC_TYPE_TO_REQUIREMENT.get(hint)
    if req:
        confidence = 0.85
        label = hint
    elif classification_type:
        mapping = {
            "ils": ("ils_statement", 0.72, "Выписка ИЛС"),
            "labor_book": ("labor_book", 0.7, "Трудовая книжка"),
            "application": ("client_signed_application", 0.55, "Заявление"),
            "passport": ("passport", 0.5, "Паспорт"),
            "other": ("extra", 0.3, "Дополнительный документ"),
        }
        key = classification_type.replace("DocumentType.", "").lower()
        req, confidence, label = mapping.get(key, ("extra", 0.25, "Дополнительный документ"))
    else:
        req, confidence, label = "extra", 0.2, "Дополнительный документ"

    bank_allowed = (
        SCENARIO_BANK_LIMITED in active_scenarios
        or SCENARIO_PAYOUT_RECONCILIATION in active_scenarios
    )
    if req == BANK_REQUIREMENT_CODE and not bank_allowed:
        return {
            "requirement_code": None,
            "confidence": 0.0,
            "label": label,
            "blocked": True,
            "client_message": (
                "Банковская выписка не нужна для обычной проверки стажа. "
                "Загрузите её только если специалист запросил сверку выплат."
            ),
        }
    needs_confirmation = confidence < 0.65
    return {
        "requirement_code": req,
        "confidence": confidence,
        "label": label,
        "needs_confirmation": needs_confirmation,
        "client_message": (
            f"Похоже, это «{label}». Подтвердите размещение или выберите тип вручную."
            if needs_confirmation
            else f"Предварительно определён тип: «{label}». Специалист проверит документ."
        ),
    }


def _labor_timeline_rows(
    preview: str,
    *,
    document_id: str,
    group_id: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in (preview or "").splitlines():
        raw = line.strip()
        if len(raw) < 12:
            continue
        if not re.search(r"\d{2}\.\d{2}\.\d{4}", raw):
            continue
        rows.append(
            {
                "id": str(uuid4()),
                "document_id": document_id,
                "document_group_id": group_id,
                "employer": raw[:120],
                "event_type": "period",
                "source_page": 1,
                "confidence": 0.35,
                "status": "draft",
            }
        )
        if len(rows) >= 12:
            break
    return rows


def run_ingest_pipeline(
    *,
    data: bytes,
    filename: str,
    content_type: str | None,
    doc_type: str | None,
    preview_text: str,
    active_scenarios: set[str],
    duplicate_checksum: bool,
) -> dict[str, Any]:
    """Синхронный MVP-pipeline после загрузки в quarantine/verified storage."""
    allow_signed = (doc_type or "").strip().lower() in SIGNED_DOC_TYPES
    security = validate_file_bytes(
        data,
        filename=filename,
        declared_content_type=content_type,
        allow_signed=allow_signed,
    )
    if not security.ok:
        return {
            "ingest_status": "blocked_security",
            "progress_percent": 100,
            "current_stage": "blocked_security",
            "progress_message": security.client_message or "Нужна повторная загрузка.",
            "quality_report": None,
            "placement_suggestion": None,
            "mime_verified": security.detected_mime,
            "checksum_sha256": sha256_hex(data),
            "page_count": None,
            "duplicate": duplicate_checksum,
        }

    page_count = _estimate_pdf_pages(data) if security.detected_mime == "application/pdf" else 1
    if page_count and page_count > MAX_PDF_PAGES:
        return {
            "ingest_status": "blocked_security",
            "progress_percent": 100,
            "current_stage": "blocked_security",
            "progress_message": (
                "Слишком много страниц в PDF. Разделите файл или загрузите нужные страницы."
            ),
            "quality_report": None,
            "placement_suggestion": None,
            "mime_verified": security.detected_mime,
            "checksum_sha256": sha256_hex(data),
            "page_count": page_count,
            "duplicate": duplicate_checksum,
        }

    quality = _quality_from_preview(preview_text)
    classification = classify_document(preview_text[:4000])
    placement = _suggest_requirement(
        doc_type_hint=doc_type,
        classification_type=str(classification.document_type),
        active_scenarios=active_scenarios,
    )
    if placement.get("blocked"):
        return {
            "ingest_status": "blocked_security",
            "progress_percent": 100,
            "current_stage": "blocked_security",
            "progress_message": placement.get("client_message"),
            "quality_report": quality,
            "placement_suggestion": placement,
            "mime_verified": security.detected_mime,
            "checksum_sha256": sha256_hex(data),
            "page_count": page_count,
            "duplicate": duplicate_checksum,
        }

    if duplicate_checksum:
        status = "under_review"
        message = "Такой файл уже загружен. Специалист проверит, нужен ли дубликат."
    elif quality["recommended_action"] == "reupload":
        status = "needs_reupload"
        message = quality["client_message"]
    elif quality["recommended_action"] == "manual_review":
        status = "manual_review"
        message = quality["client_message"]
    else:
        status = "under_review"
        message = placement.get("client_message") or "Файл получен — специалист проверит."

    labor_codes = {"labor_book", "labor", "workbook"}
    req_code = placement.get("requirement_code")
    is_labor = (doc_type or "").strip().lower() in labor_codes or req_code in labor_codes

    return {
        "ingest_status": status,
        "progress_percent": 100,
        "current_stage": status,
        "progress_message": message,
        "quality_report": quality,
        "placement_suggestion": placement,
        "mime_verified": security.detected_mime,
        "checksum_sha256": sha256_hex(data),
        "page_count": page_count,
        "duplicate": duplicate_checksum,
        "classification": {
            "document_type": str(classification.document_type),
            "confidence": classification.confidence,
        },
        "labor_timeline_drafts": _labor_timeline_rows(
            preview_text,
            document_id="",
            group_id=None,
        )
        if is_labor
        else [],
    }


def client_progress_payload(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("ingest_status") or "under_review")
    return {
        "document_id": row.get("id"),
        "ingest_status": status,
        "status_label": CLIENT_STAGE_LABELS.get(status, "Файл получен — специалист проверит"),
        "progress_percent": int(row.get("progress_percent") or 0),
        "current_stage": row.get("current_stage"),
        "progress_message": row.get("progress_message"),
        "downloadable": is_downloadable_status(status),
        "placement_suggestion": row.get("placement_suggestion"),
        "updated_at": row.get("updated_at") or datetime.now(UTC).isoformat(),
    }


def parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None
