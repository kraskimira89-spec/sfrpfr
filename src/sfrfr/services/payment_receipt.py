"""Чек оплаты клиента: OCR, сверка реквизитов, подтверждение без webhook ЮKassa."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from sfrfr.ocr import extract_text_from_bytes
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET
from sfrfr.services.public_tariffs import PAYMENT_PURPOSE
from sfrfr.storage.local import safe_filename

logger = logging.getLogger("sfrfr.payment_receipt")

# ООО «ПОД ПРИСМОТРОМ» — docs/history/requisites-pod-prismotrom.md
ORG_INN = "8905066468"
ORG_RS = "40702810467400005864"
ORG_BIK = "047102651"
ORG_NAME = "под присмотром"
YOOKASSA_INN = "7750005725"
DOC_TYPE = "payment_receipt"
_PAID = {"paid", "succeeded"}
_CANCELLED = {"cancelled", "canceled", "refund", "refunded"}
_RECEIPT_HINTS = (
    "чек",
    "квитанц",
    "оплат",
    "перевод",
    "сбп",
    "qr",
    "юкасса",
    "yookassa",
    "юmoney",
    "юмани",
    "приход",
)


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _norm(text: str) -> str:
    return (text or "").lower().replace("ё", "е")


def looks_like_receipt(text: str) -> bool:
    if (text or "").startswith("[ocr_"):
        return False
    lowered = _norm(text)
    compact = digits_only(text)
    if ORG_INN in compact or ORG_RS in compact or YOOKASSA_INN in compact:
        return True
    if ORG_NAME in lowered:
        return True
    return any(hint in lowered for hint in _RECEIPT_HINTS)


def match_requisites(text: str) -> dict[str, Any]:
    lowered = _norm(text)
    compact = digits_only(text)
    inn = ORG_INN in compact
    account = ORG_RS in compact
    bik = ORG_BIK in compact
    name = ORG_NAME in lowered
    yookassa = YOOKASSA_INN in compact or any(
        token in lowered for token in ("юкасса", "yookassa", "юmoney", "юмани", "nko")
    )
    purpose = "информационн" in lowered or _norm(PAYMENT_PURPOSE[:40]) in lowered
    recipient_ok = inn or account or name or yookassa
    return {
        "recipient_ok": recipient_ok,
        "inn": inn,
        "account": account,
        "bik": bik,
        "name": name,
        "yookassa": yookassa,
        "purpose": purpose,
        "looks_like_receipt": looks_like_receipt(text),
    }


def amount_mentioned(text: str, amount_rub: float) -> bool:
    n = int(round(float(amount_rub)))
    compact = re.sub(r"[\s\u00a0]", "", text or "")
    variants = {str(n), f"{n}.00", f"{n},00", f"{n}.0"}
    return any(item in compact for item in variants)


def should_ask_for_receipt(orders: list[dict[str, Any]]) -> bool:
    return any(_is_unpaid(row) for row in orders)


def _is_unpaid(order: dict[str, Any]) -> bool:
    status = str(order.get("status") or "").lower()
    return status not in _PAID | _CANCELLED


def _unpaid_orders(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in orders if _is_unpaid(row)]


def _pick_order(
    orders: list[dict[str, Any]], text: str
) -> tuple[dict[str, Any] | None, bool]:
    """Вернуть (заказ, полная_сумма)."""
    unpaid = _unpaid_orders(orders)
    hits: list[tuple[dict[str, Any], bool]] = []
    for order in unpaid:
        expected = float(order.get("amount_rub") or 0)
        if expected <= 0 or not amount_mentioned(text, expected):
            continue
        hits.append((order, True))
    if hits:
        return hits[0][0], True
    if len(unpaid) == 1 and match_requisites(text)["recipient_ok"]:
        return unpaid[0], False
    return None, False


def evaluate_receipt_text(
    text: str, orders: list[dict[str, Any]]
) -> dict[str, Any]:
    req = match_requisites(text)
    unpaid = _unpaid_orders(orders)
    if not unpaid:
        return {
            "status": "already_paid",
            "ask_receipt": False,
            "requisites": req,
            "order": None,
            "client_message": (
                "Оплата уже получена, чек присылать не нужно. Спасибо, документ сохраним в деле."
            ),
        }
    if not req["looks_like_receipt"]:
        return {
            "status": "not_a_receipt",
            "ask_receipt": True,
            "requisites": req,
            "order": None,
            "client_message": None,
        }
    order, amount_ok = _pick_order(orders, text)
    if order and req["recipient_ok"] and amount_ok:
        return {
            "status": "confirmed",
            "ask_receipt": False,
            "requisites": req,
            "order": order,
            "client_message": (
                "Чек принят: реквизиты и сумма совпали. Оплата подтверждена, "
                "можно переходить к следующему шагу. Чек сохранён в деле."
            ),
        }
    if order and req["recipient_ok"] and not amount_ok:
        return {
            "status": "partial_or_amount",
            "ask_receipt": False,
            "requisites": req,
            "order": order,
            "client_message": (
                "Чек получили и сохранили. Сумма на чеке не совпала со счётом — "
                "специалист сверит вручную. Этап пока не открываем."
            ),
        }
    return {
        "status": "mismatch",
        "ask_receipt": True,
        "requisites": req,
        "order": None,
        "client_message": (
            "Чек сохранили в деле, но реквизиты получателя не совпали "
            "(нужны ООО «ПОД ПРИСМОТРОМ» или оплата через ЮKassa). "
            "Проверьте счёт или пришлите другой чек."
        ),
    }


def ocr_receipt_bytes(data: bytes, filename: str) -> str:
    return extract_text_from_bytes(data, filename)


def save_receipt_document(
    *,
    case_id: str,
    data: bytes,
    filename: str,
    actor_id: str | None,
    preview: str,
) -> str | None:
    from sfrfr.db.session import get_supabase_client

    document_id = str(uuid4())
    storage_path = f"{case_id}/{document_id}/{safe_filename(filename)}"
    client = get_supabase_client()
    content_type = "application/pdf" if filename.lower().endswith(".pdf") else "image/jpeg"
    try:
        client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
            storage_path,
            data,
            {"content-type": content_type, "x-upsert": "false"},
        )
        row: dict[str, Any] = {
            "id": document_id,
            "case_id": case_id,
            "storage_path": storage_path,
            "doc_type": DOC_TYPE,
            "uploaded_by": actor_id,
        }
        if preview:
            row["content_preview"] = preview[:280]
        client.table("documents").insert(row).execute()
        return document_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("save_receipt_document failed case=%s: %s", case_id[:8], exc)
        return None


def confirm_order_from_receipt(
    repo: Any,
    *,
    case_id: str,
    order: dict[str, Any],
    document_id: str | None,
    actor_id: str | None,
) -> dict[str, Any]:
    order_id = str(order.get("id") or "")
    if str(order.get("status") or "") in _PAID:
        return {"ok": True, "already": True}
    provider_payment_id = f"receipt:{document_id or order_id}"
    repo.create_payment_record(
        order_id=order_id,
        case_id=case_id,
        provider="receipt_ocr",
        provider_payment_id=provider_payment_id,
        status_value="pending",
        actor_id=actor_id,
    )
    applied = repo.apply_provider_payment(
        provider_payment_id=provider_payment_id,
        status_value="succeeded",
        order_id=order_id,
        paid=True,
        package_code=str(order.get("package_code") or ""),
        case_id=case_id,
    )
    try:
        repo.update_order_fields(
            order_id,
            case_id=case_id,
            actor_id=actor_id,
            action="receipt_confirmed",
            fields={"invoice_status": "paid"},
            audit_payload={"document_id": document_id, "source": "client_receipt"},
        )
    except Exception:  # noqa: BLE001
        pass
    return applied


def apply_receipt_decision(
    repo: Any,
    *,
    case_id: str,
    evaluation: dict[str, Any],
    document_id: str | None,
    actor_id: str | None,
    notify: bool = True,
) -> dict[str, Any]:
    status = str(evaluation.get("status") or "")
    order = evaluation.get("order")
    if status == "confirmed" and order:
        applied = confirm_order_from_receipt(
            repo,
            case_id=case_id,
            order=order,
            document_id=document_id,
            actor_id=actor_id,
        )
        evaluation["applied"] = applied
        if notify and applied.get("newly_paid"):
            try:
                from sfrfr.integrations.payments.notify import notify_payment_succeeded

                notify_payment_succeeded(
                    case_id=case_id,
                    package_code=str(order.get("package_code") or ""),
                    amount_value=str(order.get("amount_rub") or ""),
                    provider_payment_id=f"receipt:{document_id or ''}",
                    source="receipt",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("receipt notify failed: %s", exc)
        return evaluation
    if status in {"mismatch", "partial_or_amount"}:
        try:
            from sfrfr.services.finance_automation import ensure_staff_task

            ensure_staff_task(
                repo,
                case_id,
                title="Проверить чек оплаты",
                item_type="payment",
                due_at=None,
                actor_id=actor_id,
                note=status,
            )
        except Exception:  # noqa: BLE001
            pass
    return evaluation


def handle_uploaded_receipt(
    repo: Any,
    *,
    case_id: str,
    ocr_text: str,
    document_id: str | None,
    actor_id: str | None,
    doc_type: str | None = None,
) -> dict[str, Any] | None:
    orders = repo.list_orders(case_id)
    forced = (doc_type or "").lower() == DOC_TYPE
    if not forced and not looks_like_receipt(ocr_text) and not should_ask_for_receipt(orders):
        return None
    if not forced and not looks_like_receipt(ocr_text):
        return None
    evaluation = evaluate_receipt_text(ocr_text, orders)
    if evaluation["status"] == "not_a_receipt" and not forced:
        return None
    if evaluation["status"] == "not_a_receipt" and forced:
        evaluation["status"] = "mismatch"
        evaluation["client_message"] = (
            "Чек сохранили в деле. Текст не распознался — специалист сверит вручную."
        )
    return apply_receipt_decision(
        repo,
        case_id=case_id,
        evaluation=evaluation,
        document_id=document_id,
        actor_id=actor_id,
    )


def ingest_max_receipt(
    *,
    max_user_id: str,
    files: list[tuple[str, bytes]],
    actor_id: str | None = None,
) -> dict[str, Any] | None:
    """Если у клиента есть неоплаченный счёт и вложение — чек, обработать. Иначе None."""
    if not files:
        return None
    try:
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.db.session import get_supabase_client
    except Exception:  # noqa: BLE001
        return None
    try:
        sb = get_supabase_client()
        client_row = (
            sb.table("clients")
            .select("id")
            .eq("max_user_id", str(max_user_id))
            .limit(1)
            .execute()
            .data
            or []
        )
        if not client_row:
            return None
        cases = (
            sb.table("cases")
            .select("id")
            .eq("client_id", client_row[0]["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("ingest_max_receipt lookup skipped: %s", exc)
        return None
    repo = CaseRepository()
    for case in cases:
        case_id = str(case.get("id") or "")
        if not case_id:
            continue
        orders = repo.list_orders(case_id)
        if not should_ask_for_receipt(orders) and not any(
            str(o.get("status") or "") in _PAID for o in orders
        ):
            continue
        for filename, data in files:
            text = ocr_receipt_bytes(data, filename)
            if not looks_like_receipt(text) and should_ask_for_receipt(orders):
                continue
            if not looks_like_receipt(text):
                continue
            preview = " ".join(text.split())[:280]
            document_id = save_receipt_document(
                case_id=case_id,
                data=data,
                filename=filename,
                actor_id=actor_id or f"max:{max_user_id}",
                preview=preview,
            )
            result = handle_uploaded_receipt(
                repo,
                case_id=case_id,
                ocr_text=text,
                document_id=document_id,
                actor_id=actor_id or f"max:{max_user_id}",
                doc_type=DOC_TYPE,
            )
            if result:
                result["case_id"] = case_id
                result["document_id"] = document_id
                return result
    return None
