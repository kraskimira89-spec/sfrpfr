"""Короткая ссылка и QR на оплату ЮKassa → доставка клиенту в MAX.

Каналы доставки (канон):
1. Staff «В MAX» / API pay-link send_max=true — текст + кнопка «Оплатить» + QR PNG.
2. Staff «Ссылка» — только pay_url в админке (копипаст), без MAX.
3. Клиент сам: кабинет на сайте → confirmation_url (без QR в чат).
4. Опционально MAX_PAY_LINK_AUTO_SEND=1 — после черновика счёта, если есть max_user_id.

SMS/email ЮKassa не используем. Secure action link для оплаты не нужен:
страница оплаты на стороне ЮKassa; QR — наш signed /api/public/pay/{id}/qr.png.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from urllib.parse import urlencode

import segno

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.client import MaxBotClient, inline_link_keyboard
from sfrfr.integrations.payments import YooKassaClient
from sfrfr.services.public_tariffs import PAYMENT_PURPOSE, staff_package_label
from sfrfr.services.staff_finance import parse_dt

logger = logging.getLogger(__name__)

_YOOKASSA_HOSTS = ("yookassa.ru", "yoomoney.ru")


def is_yookassa_pay_url(url: str | None) -> bool:
    value = (url or "").lower()
    return any(host in value for host in _YOOKASSA_HOSTS)


def pay_qr_signature(order_id: str) -> str:
    secret = get_settings().app_secret_key.encode("utf-8")
    digest = hmac.new(secret, f"pay-qr:{order_id}".encode(), hashlib.sha256).hexdigest()
    return digest[:16]


def public_qr_url(order_id: str) -> str:
    base = get_settings().public_base_url.rstrip("/")
    query = urlencode({"s": pay_qr_signature(order_id)})
    return f"{base}/api/public/pay/{order_id}/qr.png?{query}"


def qr_png_bytes(pay_url: str, *, scale: int = 6) -> bytes:
    qr = segno.make(pay_url, error="m")
    buf = BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


def _expires_iso(due_at: str | None) -> str:
    due = parse_dt(due_at)
    now = datetime.now(UTC)
    if due is None or due < now + timedelta(hours=2):
        due = now + timedelta(days=3)
    return due.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ensure_yookassa_pay_url(
    *,
    client: YooKassaClient,
    order: dict[str, Any],
    case: dict[str, Any],
    return_url: str,
    channel: str,
) -> dict[str, Any]:
    """Счёт ЮKassa (короткая ссылка) или fallback на redirect-платёж."""
    existing = str(order.get("pay_url") or "")
    if is_yookassa_pay_url(existing):
        return {"ok": True, "pay_url": existing, "kind": "reuse"}
    if not client.available:
        return {"ok": False, "pay_url": existing, "kind": "unconfigured"}
    amount = float(order.get("amount_rub") or 0)
    if amount <= 0:
        return {"ok": False, "pay_url": existing, "kind": "bad_amount"}
    service = staff_package_label(str(order.get("package_code") or ""), order.get("service_label"))
    description = (service or PAYMENT_PURPOSE)[:128]
    client_row = case.get("clients") or {}
    email = str(client_row.get("email") or "").strip() or None
    meta = {
        "order_id": str(order.get("id") or ""),
        "case_id": str(order.get("case_id") or ""),
        "package_code": str(order.get("package_code") or ""),
        "channel": channel,
    }
    invoice = client.create_invoice(
        amount_rub=amount,
        description=description,
        metadata=meta,
        expires_at=_expires_iso(str(order.get("due_at") or "") or None),
        customer_email=email,
    )
    if invoice.get("ok") and invoice.get("pay_url"):
        return {
            "ok": True,
            "pay_url": str(invoice["pay_url"]),
            "kind": "invoice",
            "invoice_id": invoice.get("invoice_id"),
            "payment_id": None,
        }
    payment = client.create_payment(
        amount_rub=amount,
        description=PAYMENT_PURPOSE,
        return_url=return_url,
        metadata=meta,
        customer_email=email,
    )
    if payment.get("ok") and payment.get("confirmation_url"):
        return {
            "ok": True,
            "pay_url": str(payment["confirmation_url"]),
            "kind": "payment",
            "invoice_id": None,
            "payment_id": payment.get("payment_id"),
            "status": payment.get("status"),
        }
    return {
        "ok": False,
        "pay_url": existing,
        "kind": "failed",
        "error": invoice.get("error") or payment.get("error"),
    }


def pay_message_text(*, service: str, amount_rub: float, pay_url: str) -> str:
    return (
        "Здравствуйте! Счёт на оплату информационно-документарной поддержки "
        f"({service}, {int(amount_rub)} ₽).\n"
        f"{pay_url}\n"
        "Можно открыть ссылку или отсканировать QR. "
        "Если оплатите переводом — пришлите фото чека в этот чат или в кабинет (Оплаты). "
        "Если оплата пройдёт по ссылке ЮKassa, чек присылать не нужно. "
        "Решение о пенсии и перерасчёте принимает СФР, результат не гарантирован."
    )


def send_pay_link_max(
    *,
    max_user_id: str,
    service: str,
    amount_rub: float,
    pay_url: str,
    qr_url: str | None = None,
    case_id: str | None = None,
) -> None:
    """Текст + (опц.) картинка QR + кнопка «Оплатить» в личный чат MAX.

    Дублирует текст в case_messages, чтобы сотрудник видел счёт в ленте дела.
    """
    bot = MaxBotClient()
    if not bot.available:
        raise RuntimeError("max_bot_not_configured")
    text = pay_message_text(service=service, amount_rub=amount_rub, pay_url=pay_url)
    attachments: list[dict[str, Any]] = []
    if qr_url:
        attachments.append({"type": "image", "payload": {"url": qr_url}})
    attachments.extend(inline_link_keyboard("Оплатить", pay_url))
    bot.send_message(text=text, user_id=max_user_id, attachments=attachments)
    if case_id:
        try:
            from sfrfr.integrations.max.case_chat_log import append_bot_case_message

            chat_body = text
            if qr_url:
                chat_body = f"{text}\nQR: {qr_url}"
            append_bot_case_message(
                case_id=case_id,
                text=chat_body,
                attachments=attachments,
                max_user_id=max_user_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "pay_link_case_message_failed case=%s",
                str(case_id)[:8],
            )


class PayLinkError(Exception):
    """Ошибка выдачи/доставки pay-link (код в .code)."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def issue_and_deliver_pay_link(
    *,
    repo: Any,
    order: dict[str, Any],
    case: dict[str, Any],
    actor_id: str | None,
    send_max: bool,
    channel: str | None = None,
    return_url: str | None = None,
    yookassa: YooKassaClient | None = None,
) -> dict[str, Any]:
    """Создать/reuse счёт ЮKassa, сохранить pay_url, опционально отправить в MAX.

    Возвращает: pay_url, qr_url, sent, kind, order (после update), payment_id.
    Не логирует полный pay_url и ПДн.
    """
    order_id = str(order.get("id") or "")
    case_id = str(order.get("case_id") or case.get("id") or "")
    if not order_id or not case_id:
        raise PayLinkError("missing_ids")
    if order.get("status") == "paid":
        raise PayLinkError("order_already_paid")

    settings = get_settings()
    resolved_channel = channel or ("max" if send_max else "web_cabinet")
    if return_url is None:
        cabinet = settings.cabinet_public_url.rstrip("/")
        return_url = f"{cabinet}/cases/{case_id}?view=payments&paid=1"

    created = ensure_yookassa_pay_url(
        client=yookassa or YooKassaClient(),
        order=order,
        case=case,
        return_url=return_url,
        channel=resolved_channel,
    )
    pay_url = str(created.get("pay_url") or "")
    payment_id = str(created.get("payment_id") or "")
    if payment_id and hasattr(repo, "create_payment_record"):
        repo.create_payment_record(
            order_id=order_id,
            case_id=case_id,
            provider="yookassa",
            provider_payment_id=payment_id,
            status_value=str(created.get("status") or "pending"),
            actor_id=actor_id,
        )
    if not pay_url:
        cabinet = settings.cabinet_public_url.rstrip("/")
        pay_url = f"{cabinet}/cases/{case_id}?view=payments"

    updated = repo.update_order_fields(
        order_id,
        case_id=case_id,
        actor_id=actor_id,
        action="invoice_sent",
        fields={
            "pay_url": pay_url,
            "sent_channel": resolved_channel,
            "sent_at": datetime.now(UTC).isoformat(),
            "invoice_status": "invoice_sent",
            "status": "pending" if order.get("status") == "draft" else order.get("status"),
        },
        audit_payload={
            "channel": resolved_channel,
            "kind": created.get("kind"),
            "invoice_id": created.get("invoice_id"),
            "sent_max": False,
        },
    )

    qr = public_qr_url(order_id)
    sent = False
    if send_max:
        client_row = case.get("clients") or {}
        max_uid = str(client_row.get("max_user_id") or "").strip()
        if not max_uid:
            raise PayLinkError("client_has_no_max_user_id")
        service = staff_package_label(
            str(order.get("package_code") or ""), order.get("service_label")
        )
        try:
            send_pay_link_max(
                max_user_id=max_uid,
                service=service,
                amount_rub=float(order.get("amount_rub") or 0),
                pay_url=pay_url,
                qr_url=qr,
                case_id=case_id,
            )
            sent = True
        except PayLinkError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PayLinkError("max_send_failed", str(exc)) from exc
        if hasattr(repo, "append_finance_audit"):
            repo.append_finance_audit(
                order_id=order_id,
                case_id=case_id,
                actor_id=actor_id,
                action="pay_link_max",
                payload={"sent": True},
            )
        logger.info(
            "pay_link_max_sent order=%s case=%s kind=%s",
            order_id[:8],
            case_id[:8],
            created.get("kind"),
        )

    return {
        "pay_url": pay_url,
        "qr_url": qr,
        "sent": sent,
        "kind": created.get("kind"),
        "payment_id": payment_id or None,
        "order": updated,
    }


def maybe_auto_send_pay_link_after_draft(
    *,
    repo: Any,
    order: dict[str, Any],
    case: dict[str, Any],
    actor_id: str | None,
) -> dict[str, Any] | None:
    """Если MAX_PAY_LINK_AUTO_SEND=1 и у клиента есть max_user_id — выставить и отправить."""
    settings = get_settings()
    if not settings.max_pay_link_auto_send:
        return None
    client_row = case.get("clients") or {}
    if not str(client_row.get("max_user_id") or "").strip():
        logger.info(
            "pay_link_auto_skip_no_max order=%s case=%s",
            str(order.get("id") or "")[:8],
            str(case.get("id") or "")[:8],
        )
        return None
    try:
        return issue_and_deliver_pay_link(
            repo=repo,
            order=order,
            case=case,
            actor_id=actor_id,
            send_max=True,
            channel="max_auto",
        )
    except PayLinkError as exc:
        logger.warning(
            "pay_link_auto_failed order=%s code=%s",
            str(order.get("id") or "")[:8],
            exc.code,
        )
        return None
    except Exception:  # noqa: BLE001
        logger.exception(
            "pay_link_auto_error order=%s",
            str(order.get("id") or "")[:8],
        )
        return None
