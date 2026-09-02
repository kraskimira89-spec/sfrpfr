"""Pay-link из единого чата + метрики «нудж → оплата»."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.core.config import get_settings

logger = logging.getLogger(__name__)

_PAY_INTENT = re.compile(
    r"(как\s+оплат|где\s+оплат|ссылк.*оплат|оплатить|сч[её]т|реквизит|"
    r"стоимость|сколько\s+стоит|3000|3\s*000|"
    r"оплат|перевод|ю\s*kassa|юкасса|"
    r"диагностик.*(₽|руб))",
    re.IGNORECASE,
)
_RESEND_INTENT = re.compile(
    r"(повтор|ещё\s+раз|еще\s+раз|снова|не\s+пришл).*(ссылк|сч[её]т|оплат|qr|к\s*у\s*ар)",
    re.IGNORECASE,
)
_BOT_PAY_NUDGE = re.compile(
    r"(оплат|сч[её]т|3000|3\s*000|раздел.*оплат|кабинет.*оплат)",
    re.IGNORECASE,
)

_NUDGE_COOLDOWN = timedelta(hours=24)


def payment_intent_detected(user_text: str) -> bool:
    text = (user_text or "").strip()
    if not text:
        return False
    return bool(_PAY_INTENT.search(text) or _RESEND_INTENT.search(text))


def resend_intent_detected(user_text: str) -> bool:
    return bool(_RESEND_INTENT.search((user_text or "").strip()))


def bot_reply_suggests_payment(reply: str) -> bool:
    return bool(_BOT_PAY_NUDGE.search((reply or "").strip()))


def _recent_nudge_exists(*, case_id: str, order_id: str) -> bool:
    try:
        from sfrfr.db.session import get_supabase_client

        since = (datetime.now(UTC) - _NUDGE_COOLDOWN).isoformat()
        rows = (
            get_supabase_client()
            .table("case_payment_nudges")
            .select("id")
            .eq("case_id", case_id)
            .eq("order_id", order_id)
            .gte("created_at", since)
            .limit(1)
            .execute()
            .data
            or []
        )
        return bool(rows)
    except Exception as exc:  # noqa: BLE001
        logger.debug("payment_nudge lookup skipped: %s", exc)
        return False


def record_payment_nudge(
    *,
    case_id: str,
    order_id: str,
    message_id: str | None,
    channel: str,
    source: str,
) -> str | None:
    try:
        from sfrfr.db.session import get_supabase_client

        inserted = (
            get_supabase_client()
            .table("case_payment_nudges")
            .insert(
                {
                    "case_id": case_id,
                    "order_id": order_id,
                    "message_id": message_id,
                    "channel": channel,
                    "source": source,
                }
            )
            .execute()
            .data
            or []
        )
        nudge_id = str((inserted[0] or {}).get("id") or "") if inserted else ""
        try:
            from sfrfr.ops.chat_bot_metrics import CHAT_PAYMENT_NUDGE

            CHAT_PAYMENT_NUDGE.labels(channel=channel, source=source).inc()
        except Exception:  # noqa: BLE001
            pass
        return nudge_id or None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "payment_nudge record failed case=%s order=%s: %s",
            case_id[:8],
            order_id[:8],
            exc,
        )
        return None


def mark_payment_nudge_converted(
    *,
    case_id: str,
    order_id: str,
    payment_id: str | None = None,
) -> int:
    """Отметить открытые нуджи по заказу как сконвертированные. Возвращает число строк."""
    if not case_id or not order_id:
        return 0
    try:
        from sfrfr.db.session import get_supabase_client

        client = get_supabase_client()
        open_rows = (
            client.table("case_payment_nudges")
            .select("id, channel, source")
            .eq("case_id", case_id)
            .eq("order_id", order_id)
            .is_("converted_at", "null")
            .execute()
            .data
            or []
        )
        if not open_rows:
            return 0
        now = datetime.now(UTC).isoformat()
        payload: dict[str, Any] = {"converted_at": now}
        if payment_id:
            payload["converted_payment_id"] = payment_id
        client.table("case_payment_nudges").update(payload).eq("case_id", case_id).eq(
            "order_id", order_id
        ).is_("converted_at", "null").execute()
        try:
            from sfrfr.ops.chat_bot_metrics import CHAT_PAYMENT_NUDGE_CONVERTED

            for row in open_rows:
                if not isinstance(row, dict):
                    continue
                CHAT_PAYMENT_NUDGE_CONVERTED.labels(
                    channel=str(row.get("channel") or "unified"),
                    source=str(row.get("source") or "chat_bot"),
                ).inc()
        except Exception:  # noqa: BLE001
            pass
        return len(open_rows)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "payment_nudge convert failed case=%s order=%s: %s",
            case_id[:8],
            order_id[:8],
            exc,
        )
        return 0


def _append_pay_link_case_message(
    *,
    case_id: str,
    text: str,
    max_user_id: str | None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    from sfrfr.db.session import get_supabase_client
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery, process_pending_outbox

    inserted = (
        get_supabase_client()
        .table("case_messages")
        .insert(
            {
                "case_id": case_id,
                "author_kind": "system",
                "author_user_id": None,
                "body": text,
                "channel_origin": "bot",
            }
        )
        .execute()
    )
    message_row = (inserted.data or [{}])[0]
    message_id = str(message_row.get("id") or "").strip() or None
    if max_user_id and message_id:
        enqueue_max_delivery(
            case_id=case_id,
            message_id=message_id,
            max_user_id=max_user_id,
            body=text,
            attachments=attachments or [],
        )
        process_pending_outbox(limit=5)
    return message_row if isinstance(message_row, dict) else None


def try_deliver_pay_link_from_chat(
    *,
    case: dict[str, Any],
    work: dict[str, Any],
    user_text: str,
    channel: str,
    source: str = "chat_bot",
    force: bool = False,
) -> dict[str, Any] | None:
    """Выставить счёт и отправить pay-link в единый чат, если счёт готов."""
    settings = get_settings()
    if not settings.case_chat_pay_link_enabled:
        return None

    case_id = str(case.get("id") or "").strip()
    order_view = work.get("order") if isinstance(work.get("order"), dict) else {}
    if not case_id or not order_view.get("can_pay"):
        return None
    order_id = str(order_view.get("order_id") or "").strip()
    if not order_id:
        return None

    intent = force or payment_intent_detected(user_text)
    if not intent:
        return None
    if not resend_intent_detected(user_text) and _recent_nudge_exists(
        case_id=case_id, order_id=order_id
    ):
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.integrations.max.client import inline_link_keyboard
    from sfrfr.services.pay_link import (
        PayLinkError,
        issue_and_deliver_pay_link,
        pay_message_text,
        public_qr_url,
    )
    from sfrfr.services.public_tariffs import staff_package_label

    repo = CaseRepository()
    order = repo.get_order_by_id(order_id)
    if not order or str(order.get("status") or "") == "paid":
        return None

    client_row = case.get("clients") or {}
    if isinstance(client_row, list):
        client_row = client_row[0] if client_row else {}
    max_uid = str((client_row or {}).get("max_user_id") or "").strip() or None

    service = staff_package_label(
        str(order.get("package_code") or ""), order.get("service_label")
    )
    amount = float(order.get("amount_rub") or order_view.get("amount_rub") or 0)

    try:
        if max_uid:
            result = issue_and_deliver_pay_link(
                repo=repo,
                order=order,
                case=case,
                actor_id=None,
                send_max=True,
                channel="chat_bot",
            )
            pay_url = str(result.get("pay_url") or "")
            from sfrfr.db.session import get_supabase_client

            rows = (
                get_supabase_client()
                .table("case_messages")
                .select("id, body")
                .eq("case_id", case_id)
                .eq("author_kind", "system")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            message_row = rows[0] if rows else None
        else:
            result = issue_and_deliver_pay_link(
                repo=repo,
                order=order,
                case=case,
                actor_id=None,
                send_max=False,
                channel="chat_bot",
            )
            pay_url = str(result.get("pay_url") or "")
            public_qr_url(order_id)
            text = pay_message_text(service=service, amount_rub=amount, pay_url=pay_url)
            attachments = list(inline_link_keyboard("Оплатить", pay_url))
            message_row = _append_pay_link_case_message(
                case_id=case_id,
                text=text,
                max_user_id=None,
                attachments=attachments,
            )
    except PayLinkError as exc:
        logger.info(
            "chat pay_link skipped case=%s code=%s",
            case_id[:8],
            exc.code,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat pay_link failed case=%s: %s", case_id[:8], exc)
        return None

    message_id = str((message_row or {}).get("id") or "") or None
    body = str((message_row or {}).get("body") or "") or pay_message_text(
        service=service, amount_rub=amount, pay_url=pay_url
    )
    record_payment_nudge(
        case_id=case_id,
        order_id=order_id,
        message_id=message_id,
        channel=channel,
        source=source,
    )
    logger.info(
        "chat pay_link sent case=%s order=%s channel=%s max=%s",
        case_id[:8],
        order_id[:8],
        channel,
        bool(max_uid),
    )
    return {
        "body": body,
        "pay_url": pay_url,
        "message_id": message_id,
        "order_id": order_id,
    }
