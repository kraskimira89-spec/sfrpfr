"""Короткий статус комплекта документов в MAX после ingest (без OCR-текста)."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.integrations.max.bot_owned import is_bot_owned
from sfrfr.integrations.max.intake import CALL_OPERATOR_LABEL

logger = logging.getLogger(__name__)

_ILS_CODES = frozenset({"ils", "ils_statement", "выписка илс"})
_LABOR_CODES = frozenset({"labor_book", "трудовая книжка", "трудовая"})

# Последний отправленный fingerprint комплекта: case_id → fingerprint
_LAST_KIT: dict[str, str] = {}


def _norm_type(value: str | None) -> str:
    return (value or "").strip().lower().replace("ё", "е")


def classify_doc_bucket(placement: dict[str, Any] | None, doc_type: str | None) -> str:
    """ils | labor | other — без содержимого OCR."""
    placement = placement or {}
    req = _norm_type(str(placement.get("requirement_code") or ""))
    label = _norm_type(str(placement.get("label") or ""))
    dtype = _norm_type(doc_type)
    blob = f"{req} {label} {dtype}"
    if req in _ILS_CODES or "илс" in blob or dtype == "ils":
        return "ils"
    if req in _LABOR_CODES or "трудов" in blob or dtype in {"labor_book", "labor"}:
        return "labor"
    return "other"


def kit_fingerprint(types: set[str]) -> str:
    return ",".join(sorted(types))


def build_kit_message(
    *,
    latest_bucket: str,
    have: set[str],
    pension_assigned: bool,
) -> str:
    labels = {"ils": "выписка ИЛС", "labor": "трудовая книжка", "other": "документ"}
    got = labels.get(latest_bucket, "документ")
    lines = [f"Похоже, это «{got}» — добавили к делу."]
    missing: list[str] = []
    if "ils" not in have:
        missing.append("выписка ИЛС")
    if "labor" not in have:
        missing.append("трудовая (скан или электронная)")
    if pension_assigned:
        lines.append(
            "Если пенсия уже назначена, позже пригодится справка СФР о размере/выплатах "
            "(это желательно, не обязательно для старта диагностики)."
        )
    if missing:
        lines.append("Для диагностики ещё нужно: " + "; ".join(missing) + ".")
        lines.append("Пришлите файлы сюда в чат или через «Мои документы» на сайте.")
    else:
        lines.append(
            "Базовый комплект для диагностики есть. "
            "Следующий шаг — диагностика 3 000 ₽: примите условия в кабинете на сайте, "
            "после этого пришлём ссылку на оплату в этот чат."
        )
    lines.append("Можно позвать специалиста кнопкой ниже.")
    return "\n".join(lines)


def collect_case_doc_buckets(documents: list[dict[str, Any]]) -> set[str]:
    have: set[str] = set()
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        placement = doc.get("placement_suggestion")
        if not isinstance(placement, dict):
            placement = {}
        bucket = classify_doc_bucket(placement, str(doc.get("doc_type") or ""))
        if bucket != "other":
            have.add(bucket)
    return have


def operator_keyboard() -> list[dict[str, Any]]:
    from sfrfr.integrations.max.client import inline_buttons_keyboard

    return inline_buttons_keyboard(
        [[{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}]]
    )


def notify_kit_status_after_ingest(
    *,
    case_id: str,
    placement_suggestion: dict[str, Any] | None,
    doc_type: str | None,
) -> bool:
    """Отправить клиенту статус комплекта; True если отправили."""
    cid = str(case_id or "").strip()
    if not cid:
        return False
    try:
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.integrations.max.intake import get_intake_store
        from sfrfr.services.case_chat_delivery import enqueue_max_delivery
    except Exception:  # noqa: BLE001
        return False

    max_uid = None
    try:
        max_uid = get_intake_store().find_max_user_id_by_case_id(cid)
    except Exception:  # noqa: BLE001
        max_uid = None
    if not max_uid:
        try:
            case = CaseRepository().get_case_row(cid)
            clients = (case or {}).get("clients") or {}
            if isinstance(clients, list):
                clients = clients[0] if clients else {}
            max_uid = str((clients or {}).get("max_user_id") or "").strip() or None
        except Exception:  # noqa: BLE001
            max_uid = None
    if not max_uid:
        return False

    intake = get_intake_store().get_active(str(max_uid))
    if not is_bot_owned(intake):
        return False

    latest = classify_doc_bucket(placement_suggestion, doc_type)
    try:
        docs = CaseRepository().list_documents(cid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("kit list_documents failed: %s", exc)
        docs = []
    have = collect_case_doc_buckets(list(docs or []))
    if latest != "other":
        have.add(latest)

    fp = kit_fingerprint(have)
    if _LAST_KIT.get(cid) == fp:
        return False
    pension_assigned = str(getattr(intake, "pension_status", "") or "") == "assigned"
    body = build_kit_message(
        latest_bucket=latest,
        have=have,
        pension_assigned=pension_assigned,
    )
    ok = enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=str(max_uid),
        body=body,
        attachments=operator_keyboard(),
    )
    if ok:
        _LAST_KIT[cid] = fp
        if "ils" in have and "labor" in have:
            try:
                from sfrfr.services.max_bot_invoice import maybe_offer_diag_invoice

                maybe_offer_diag_invoice(case_id=cid, max_user_id=str(max_uid), intake=intake)
            except Exception as exc:  # noqa: BLE001
                logger.debug("diag invoice offer skipped: %s", exc)
    return bool(ok)


def reset_kit_cache() -> None:
    _LAST_KIT.clear()
