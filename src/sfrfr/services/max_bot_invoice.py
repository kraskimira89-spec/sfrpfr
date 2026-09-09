"""Автопредложение диагностики 3000 ₽ и pay link после оферты (bot_owned)."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.bot_owned import is_bot_owned
from sfrfr.integrations.max.intake import cabinet_url_for_case

logger = logging.getLogger(__name__)

_OFFERED: set[str] = set()


def _has_open_diag(orders: list[dict[str, Any]]) -> bool:
    for o in orders or []:
        code = str(o.get("package_code") or "").upper()
        if code != "DIAG":
            continue
        status = str(o.get("status") or "").lower()
        inv = str(o.get("invoice_status") or "").lower()
        if status in {"paid"}:
            return True
        if status in {"draft", "pending", "awaiting_payment"} or inv in {
            "draft",
            "invoice_ready",
            "invoice_sent",
        }:
            return True
    return False


def maybe_offer_diag_invoice(
    *,
    case_id: str,
    max_user_id: str,
    intake: Any | None = None,
) -> dict[str, Any] | None:
    """Черновик DIAG + сообщение с офертой в кабинет. Без pay URL."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    if not is_bot_owned(intake):
        return None
    cid = str(case_id or "").strip()
    mid = str(max_user_id or "").strip()
    if not cid or not mid:
        return None
    if cid in _OFFERED:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery
    from sfrfr.services.finance_automation import suggest_agreement_draft
    from sfrfr.services.public_tariffs import public_tariff

    repo = CaseRepository()
    try:
        case = repo.get_case_row(cid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("diag offer case load failed: %s", exc)
        return None
    if not case:
        return None
    if not repo.has_consent(cid):
        return None
    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        orders = []
    if _has_open_diag(orders):
        return None

    draft = suggest_agreement_draft(case, orders)
    if not draft or str(draft.get("package_code") or "").upper() != "DIAG":
        # Если b2c ещё lead — всё равно предложим DIAG 3000
        tariff = public_tariff("DIAG") or {}
        draft = {
            "package_code": "DIAG",
            "amount_rub": float(tariff.get("amount_rub") or 3000),
            "service_label": str(tariff.get("name") or "Диагностика"),
        }

    try:
        from datetime import UTC, datetime, timedelta

        order = repo.create_order(
            cid,
            package_code="DIAG",
            amount_rub=float(draft["amount_rub"]),
            status_value="draft",
            actor_id="bot:max_owned",
            due_at=(datetime.now(UTC) + timedelta(days=3)).isoformat(),
            service_label=str(draft.get("service_label") or "Диагностика"),
            invoice_status="draft",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("diag draft create failed case=%s: %s", cid[:8], exc)
        return None

    amount = int(float(draft.get("amount_rub") or 3000))
    cab = cabinet_url_for_case(cid)
    body = (
        f"Для диагностики стоимость {amount} ₽. "
        "Чтобы выставить счёт, примите условия оказания услуг в кабинете на сайте — "
        f"после этого пришлём ссылку на оплату в этот чат.\n"
        f"Кабинет: {cab}"
    )
    enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=None,
    )
    _OFFERED.add(cid)
    return {"order": order, "offered": True}


def maybe_send_pay_link_after_contract(
    *,
    repo: Any,
    case_id: str,
    actor_id: str | None,
) -> dict[str, Any] | None:
    """После contract_accepted: если bot_owned и есть draft DIAG — pay link в MAX."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled or not settings.max_bot_owned_pay_link:
        return None
    cid = str(case_id or "").strip()
    if not cid:
        return None
    try:
        case = repo.get_case_row(cid) if hasattr(repo, "get_case_row") else None
    except Exception:  # noqa: BLE001
        case = None
    if not case:
        return None
    clients = case.get("clients") or {}
    if isinstance(clients, list):
        clients = clients[0] if clients else {}
    max_uid = str((clients or {}).get("max_user_id") or "").strip()
    if not max_uid:
        return None
    from sfrfr.integrations.max.intake import get_intake_store

    intake = get_intake_store().get_active(max_uid)
    if not is_bot_owned(intake):
        # После оферты клиент ещё в bot_owned обычно; если уже specialist — тоже можно слать
        # если был черновик от бота. Разрешаем при любом статусе, если есть draft DIAG.
        pass

    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        return None
    diag = None
    for o in orders or []:
        if str(o.get("package_code") or "").upper() != "DIAG":
            continue
        if str(o.get("status") or "") == "paid":
            return None
        if str(o.get("pay_url") or "").strip():
            # уже есть ссылка — доотправим если нужно
            diag = o
            break
        if str(o.get("status") or "") in {"draft", "pending"} or str(
            o.get("invoice_status") or ""
        ) in {"draft", "invoice_ready", "invoice_sent"}:
            diag = o
            break
    if not diag:
        return None

    from sfrfr.services.pay_link import PayLinkError, issue_and_deliver_pay_link

    try:
        return issue_and_deliver_pay_link(
            repo=repo,
            order=diag,
            case=case,
            actor_id=actor_id,
            send_max=True,
            channel="max_bot_owned",
        )
    except PayLinkError as exc:
        logger.warning("bot_owned pay_link failed case=%s code=%s", cid[:8], exc.code)
        return None
    except Exception:  # noqa: BLE001
        logger.exception("bot_owned pay_link error case=%s", cid[:8])
        return None


def reset_offer_cache() -> None:
    _OFFERED.clear()
