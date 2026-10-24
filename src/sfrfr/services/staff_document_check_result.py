"""Чистый результат staff docs-check: fingerprint, счётчики, next action."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

JOB_TYPE = "staff_docs_check"
ACTIVE_STATUSES = ("queued", "running")
STATUS_LABELS_RU = {
    "queued": "ожидает",
    "running": "выполняется",
    "completed": "готово",
    "needs_action": "требуется действие",
    "failed": "ошибка",
}

_OCR_MARKERS = ("[ocr_error]", "[ocr_empty]")


def is_embedded_text(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    low = text.lower()
    return not any(marker in low for marker in _OCR_MARKERS)


def documents_fingerprint(documents: list[dict[str, Any]]) -> str:
    """Стабильный отпечаток набора: id + checksum (порядок не важен)."""
    parts: list[str] = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        doc_id = str(doc.get("id") or "").strip()
        if not doc_id:
            continue
        checksum = str(doc.get("checksum_sha256") or "").strip() or "-"
        parts.append(f"{doc_id}:{checksum}")
    blob = "|".join(sorted(parts))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def next_staff_action(
    *,
    originals_missing: int,
    needs_ocr: int,
    missing_kit: list[str],
    needs_manual: int,
) -> str:
    if originals_missing > 0:
        return (
            f"Восстановите доступ к оригиналам ({originals_missing}) "
            "или попросите клиента прислать файлы снова."
        )
    if needs_ocr > 0:
        return (
            f"Запустите распознавание для {needs_ocr} файл(ов) со сканами "
            "или отметьте тип вручную."
        )
    if missing_kit:
        return "Запросите у клиента: " + "; ".join(missing_kit) + "."
    if needs_manual > 0:
        return (
            f"Проверьте вручную {needs_manual} документ(ов) с неясным типом "
            "или сомнительным текстом."
        )
    return "Комплект для диагностики собран — проверьте текст и перейдите к диагностике."


def build_check_result(
    *,
    documents: list[dict[str, Any]],
    missing_for_task: list[str],
    ocr_allowed: bool,
) -> dict[str, Any]:
    checked = len(documents)
    originals = sum(1 for d in documents if d.get("original_available"))
    text_ok = sum(1 for d in documents if d.get("text_extracted"))
    needs_ocr = sum(1 for d in documents if d.get("needs_ocr"))
    needs_manual = sum(1 for d in documents if d.get("needs_manual"))
    types = sorted(
        {
            str(d.get("guessed_type") or d.get("doc_type") or "other")
            for d in documents
            if d.get("guessed_type") or d.get("doc_type")
        }
    )
    checksums = [
        str(d.get("checksum_sha256") or "")
        for d in documents
        if str(d.get("checksum_sha256") or "").strip()
    ]
    dup_groups = sum(1 for _c, n in Counter(checksums).items() if n > 1)
    missing_explanations = [
        f"Не хватает «{item}» для текущей задачи клиента (базовый комплект диагностики)."
        for item in missing_for_task
    ]
    originals_missing = checked - originals
    next_action = next_staff_action(
        originals_missing=originals_missing,
        needs_ocr=needs_ocr,
        missing_kit=list(missing_for_task),
        needs_manual=needs_manual,
    )
    if originals_missing or needs_ocr or missing_for_task or needs_manual:
        status = "needs_action"
    else:
        status = "completed"
    out: dict[str, Any] = {
        "documents_checked": checked,
        "originals_available": originals,
        "text_extracted": text_ok,
        "needs_recognition": needs_ocr,
        "needs_manual_review": needs_manual,
        "types_found": types,
        "exact_duplicate_groups": dup_groups,
        "missing_for_task": list(missing_for_task),
        "missing_explanations": missing_explanations,
        "next_action": next_action,
        "ocr_allowed": bool(ocr_allowed),
        "legal_analysis_ran": False,
        "status": status,
        "documents": [
            {
                "id": d.get("id"),
                "filename": d.get("filename"),
                "guessed_type": d.get("guessed_type"),
                "original_available": bool(d.get("original_available")),
                "text_extracted": bool(d.get("text_extracted")),
                "needs_ocr": bool(d.get("needs_ocr")),
                "needs_manual": bool(d.get("needs_manual")),
                "checksum_sha256": d.get("checksum_sha256"),
            }
            for d in documents
        ],
    }
    return out


def attach_honest_brief(
    result: dict[str, Any],
    *,
    brief: dict[str, Any] | None,
) -> dict[str, Any]:
    """Добавить честное резюме по разделам (без выдуманного «анализ идёт»)."""
    if not brief:
        return result
    merged = dict(result)
    merged["honest_brief"] = brief
    if brief.get("offer_diag_allowed"):
        merged["diag_offer"] = {
            "allowed": True,
            "amount_rub": int(brief.get("offer_amount_rub") or 3000),
            "label": "Подробная диагностика — 3 000 ₽",
            "note": (
                "Офер только при подтверждённом основании "
                "(документы / требует проверки). Анкета ≠ доказательство."
            ),
        }
    else:
        merged["diag_offer"] = {
            "allowed": False,
            "amount_rub": 0,
            "label": "",
            "note": str(brief.get("next_step") or ""),
        }
    return merged


def summarize_for_staff(result: dict[str, Any]) -> dict[str, Any]:
    """Карточка для UI: без findings/analysis_notes/draft пайплайна."""
    primary = result.get("primary_precheck")
    primary_dict = primary if isinstance(primary, dict) else None
    rec = (
        primary_dict.get("recommendation")
        if isinstance(primary_dict, dict)
        else None
    )
    # Срез 1: не поднимать платный офер в staff UI из brief/rec.
    diag_offer = {
        "allowed": False,
        "amount_rub": 0,
        "label": "",
        "note": (
            str(rec.get("reason") or "")
            if isinstance(rec, dict)
            else "Офер клиенту — следующий срез."
        ),
    }
    return {
        "documents_checked": int(result.get("documents_checked") or 0),
        "originals_available": int(result.get("originals_available") or 0),
        "text_extracted": int(result.get("text_extracted") or 0),
        "needs_recognition": int(result.get("needs_recognition") or 0),
        "needs_manual_review": int(result.get("needs_manual_review") or 0),
        "types_found": list(result.get("types_found") or []),
        "exact_duplicate_groups": int(result.get("exact_duplicate_groups") or 0),
        "missing_for_task": list(result.get("missing_for_task") or []),
        "missing_explanations": list(result.get("missing_explanations") or []),
        "next_action": str(result.get("next_action") or ""),
        "ocr_allowed": bool(result.get("ocr_allowed")),
        "legal_analysis_ran": False,
        "status": str(result.get("status") or ""),
        "honest_brief": result.get("honest_brief"),
        "diag_offer": diag_offer,
        "precheck_outcome": result.get("precheck_outcome")
        or (primary_dict.get("outcome") if primary_dict else None),
        "client_summary": result.get("client_summary")
        or (primary_dict.get("client_summary") if primary_dict else None),
        "primary_precheck": primary_dict,
        "checked_scope": list(result.get("checked_scope") or [])
        or (
            list(primary_dict.get("areas_checked") or []) if primary_dict else []
        ),
        "document_set_revision": str(result.get("document_set_revision") or ""),
        "processor_version": str(result.get("processor_version") or "")
        or (
            str(primary_dict.get("rules_version") or "") if primary_dict else ""
        ),
        "execution_status": (
            primary_dict.get("execution_status") if primary_dict else None
        ),
        "data_status": primary_dict.get("data_status") if primary_dict else None,
        "comparison_status": (
            primary_dict.get("comparison_status") if primary_dict else None
        ),
        "limitations": list(
            (primary_dict.get("limitations") if primary_dict else None)
            or result.get("limitations")
            or []
        ),
        "findings": list(
            (primary_dict.get("findings") if primary_dict else None) or []
        ),
    }
