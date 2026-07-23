"""ЮKassa: создание платежа и webhook."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from sfrfr.core.config import get_settings
from sfrfr.db.case_repository import CaseRepository
from sfrfr.integrations.payments import YooKassaClient, parse_yookassa_event
from sfrfr.security.auth import Principal, get_current_principal

router = APIRouter()
webhook_router = APIRouter()

ReturnChannel = Literal["web_cabinet", "max_miniapp"]


class PayOrderRequest(BaseModel):
    return_channel: ReturnChannel = "web_cabinet"
    customer_email: str | None = Field(default=None, max_length=200)


def _repo() -> CaseRepository:
    return CaseRepository()


def _return_url(case_id: str, channel: ReturnChannel) -> str:
    settings = get_settings()
    if settings.yookassa_return_url:
        base = settings.yookassa_return_url.rstrip("/")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}case={case_id}&view=payments&paid=1"
    if channel == "max_miniapp":
        mini = settings.max_miniapp_url.rstrip("/") + "/"
        return f"{mini}?case={case_id}&view=payments&paid=1"
    cabinet = settings.cabinet_public_url.rstrip("/")
    return f"{cabinet}/?case={case_id}&view=payments&paid=1"


@router.post("/cases/{case_id}/orders/{order_id}/pay")
def start_order_payment(
    case_id: str,
    order_id: str,
    payload: PayOrderRequest | None = None,
    return_channel: ReturnChannel = Query(default="web_cabinet"),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Создать платёж ЮKassa и вернуть confirmation_url."""
    repo = _repo()
    repo.require_case(principal, case_id)
    order = repo.get_order(case_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    if order.get("status") == "paid":
        raise HTTPException(status_code=400, detail="order already paid")

    client = YooKassaClient()
    if not client.available:
        raise HTTPException(status_code=503, detail="payment provider not configured")

    body = payload or PayOrderRequest(return_channel=return_channel)
    channel = body.return_channel or return_channel
    email = body.customer_email or principal.email
    amount = float(order.get("amount_rub") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="order amount must be positive")

    result = client.create_payment(
        amount_rub=amount,
        description=f"SFRFR {order.get('package_code')} {order_id[:8]}",
        return_url=_return_url(case_id, channel),
        metadata={
            "order_id": order_id,
            "case_id": case_id,
            "package_code": str(order.get("package_code") or ""),
            "channel": channel,
        },
        customer_email=email,
    )
    if not result.get("ok") or not result.get("payment_id"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error") or result.get("reason") or "yookassa create failed",
        )

    payment_row = repo.create_payment_record(
        order_id=order_id,
        case_id=case_id,
        provider="yookassa",
        provider_payment_id=str(result["payment_id"]),
        status_value=str(result.get("status") or "pending"),
        actor_id=principal.audit_actor_id(),
    )
    return {
        "payment": payment_row,
        "confirmation_url": result.get("confirmation_url"),
        "provider_payment_id": result.get("payment_id"),
        "status": result.get("status"),
        "return_channel": channel,
        "warning": "Решение принимает СФР. Результат не гарантирован.",
    }


@webhook_router.post("/yookassa/webhook", status_code=status.HTTP_200_OK)
def yookassa_webhook(payload: dict[str, Any]) -> dict[str, str]:
    """Приём уведомлений ЮKassa (без ПДн в ответе)."""
    parsed = parse_yookassa_event(payload)
    provider_id = parsed.get("provider_payment_id")
    if not provider_id:
        raise HTTPException(status_code=400, detail="payment id missing")

    status_value = str(parsed.get("status") or "unknown")
    paid = bool(parsed.get("paid")) or status_value == "succeeded"
    try:
        _repo().apply_provider_payment(
            provider_payment_id=str(provider_id),
            status_value=status_value,
            order_id=str(parsed["order_id"]) if parsed.get("order_id") else None,
            paid=paid,
            fiscal_status="registered" if parsed.get("fiscal") else None,
            package_code=str(parsed["package_code"]) if parsed.get("package_code") else None,
            case_id=str(parsed["case_id"]) if parsed.get("case_id") else None,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return {"ok": "ignored"}
        raise
    return {"ok": "processed"}
