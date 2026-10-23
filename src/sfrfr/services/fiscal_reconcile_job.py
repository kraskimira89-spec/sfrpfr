"""SFRFR-93: тик fiscal reconcile (lease → gate → POST /receipts).

ENABLED=0 и DRY_RUN=1 по умолчанию. Алерты не шлются в dry-run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sfrfr.integrations.payments import (
    YooKassaClient,
    payment_receipt_retry_gate,
    should_auto_retry_fiscal_receipt,
)
from sfrfr.services.fiscal_reconcile import (
    LEASE_SECS,
    MAX_RECONCILE_ATTEMPTS,
    attempts_block_new_post,
    classify_create_receipt_result,
    is_unknown_outcome,
    reconcile_idempotence_key,
    should_alert_attempts,
    should_alert_streak,
    stable_receipt_snapshot,
)

logger = logging.getLogger(__name__)

AlertSend = Callable[[str, dict[str, Any]], bool]


def _parse_alert_since(raw: str | None) -> datetime | None:
    """ISO timestamptz. None = пусто или мусор (нельзя включать ENABLED)."""
    text = (raw or "").strip().strip("'\"")
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    # отсечь мусор вроде «abc», который fromisoformat мог бы не принять,
    # и значения без даты (чистое число и т.п.)
    if not hasattr(dt, "year") or dt.year < 2020:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _build_receipt_body(
    client: YooKassaClient,
    *,
    payment: dict[str, Any],
    customer_email: str | None,
    customer_phone: str | None,
    amount_rub: float | None,
) -> dict[str, Any] | None:
    raw_amount = payment.get("amount")
    amount: dict[str, Any] = raw_amount if isinstance(raw_amount, dict) else {}
    try:
        value = float(amount_rub if amount_rub is not None else amount.get("value") or 0)
    except (TypeError, ValueError):
        value = 0.0
    if value <= 0:
        return None
    desc = str(payment.get("description") or "").strip() or "Оплата услуг"
    receipt = client._receipt(
        amount_rub=value,
        description=desc,
        customer_email=customer_email,
        customer_phone=customer_phone,
    )
    if not receipt:
        return None
    return stable_receipt_snapshot(
        {
            "type": "payment",
            "payment_id": str(payment.get("id") or "").strip(),
            "send": True,
            "customer": receipt["customer"],
            "items": receipt["items"],
            "internet": True,
            "settlements": [
                {
                    "type": "cashless",
                    "amount": {"value": f"{value:.2f}", "currency": "RUB"},
                }
            ],
        }
    )


def _default_alert_send(reason: str, payment: dict[str, Any]) -> bool:
    """Лог + попытка пинга ops MAX (без ПДн в тексте)."""
    yk = str(payment.get("provider_payment_id") or "")[:13]
    pid = str(payment.get("id") or "")[:8]
    text = (
        f"fiscal_reconcile alert reason={reason} payment={pid} yk={yk} "
        f"attempts={payment.get('reconcile_attempts')} "
        f"streak={payment.get('reconcile_pre_error_streak')} "
        f"outcome={payment.get('reconcile_last_outcome')}"
    )
    logger.error("%s", text)
    try:
        from sfrfr.core.config import get_settings
        from sfrfr.integrations.max.client import MaxBotClient

        settings = get_settings()
        chat = (settings.max_specialists_channel_chat_id or "").strip()
        if not chat:
            # False: claim уже мог проставить alerted_at — не маскировать как успех.
            logger.error(
                "fiscal_reconcile_alert_send_failed payment=%s reason=no_chat_id",
                pid,
            )
            return False
        MaxBotClient().send_message(chat_id=chat, text=text[:3500])
        return True
    except Exception:  # noqa: BLE001
        logger.exception("fiscal_reconcile_alert_send_failed payment=%s", pid)
        return False


def _resolve_contacts(repo: Any, payment: dict[str, Any]) -> tuple[str | None, str | None]:
    orders = payment.get("orders") or {}
    case_id = str(orders.get("case_id") or "")
    if not case_id:
        return None, None
    getter = getattr(repo, "get_case_row", None) or getattr(repo, "_case", None)
    if getter is None:
        return None, None
    try:
        case = getter(case_id) or {}
    except Exception:  # noqa: BLE001
        return None, None
    if not isinstance(case, dict):
        return None, None
    raw_clients = case.get("clients")
    clients: dict[str, Any] = raw_clients if isinstance(raw_clients, dict) else {}
    email = (str(clients.get("email") or case.get("email") or "")).strip() or None
    phone = (str(clients.get("phone") or case.get("phone") or "")).strip() or None
    return email, phone


def process_payment_reconcile(
    repo: Any,
    payment: dict[str, Any],
    *,
    client: YooKassaClient | None = None,
    dry_run: bool = True,
    bypass_attempt_limit: bool = False,
    customer_email: str | None = None,
    customer_phone: str | None = None,
    alert_send: AlertSend | None = None,
) -> dict[str, Any]:
    """Один кандидат: lease → fetch → gate → skip | POST.

    bypass_attempt_limit — CLI: лимит 3 с WARNING, не блокирует.
    """
    yk_client = client or YooKassaClient()
    send_alert = alert_send or _default_alert_send
    payment_id = str(payment.get("id") or "")
    yk_id = str(payment.get("provider_payment_id") or "").strip()
    out: dict[str, Any] = {
        "payment_id": payment_id,
        "provider_payment_id": yk_id,
        "action": "none",
    }
    if not payment_id or not yk_id:
        out["action"] = "skip_bad_row"
        return out

    leased = repo.try_fiscal_reconcile_lease(payment_id, lease_secs=LEASE_SECS)
    if leased is None:
        out["action"] = "lease_busy"
        return out
    payment = {**payment, **leased}

    if dry_run:
        logger.info(
            "fiscal_reconcile dry-run: создал бы для payment_id=%s yk=%s",
            payment_id[:8],
            yk_id[:13],
        )
        out["action"] = "dry_run"
        return out

    fetched = yk_client.fetch_payment(yk_id)
    if not fetched.get("ok"):
        streak = int(payment.get("reconcile_pre_error_streak") or 0) + 1
        repo.update_payment_reconcile_fields(
            payment_id,
            {
                "reconcile_last_outcome": "error_before_post",
                "reconcile_pre_error_streak": streak,
            },
        )
        out["action"] = "error_before_post"
        out["error"] = fetched.get("error")
        payment["reconcile_pre_error_streak"] = streak
        payment["reconcile_last_outcome"] = "error_before_post"
        _maybe_alert(repo, payment, send_alert, reason="sticky_pre_error")
        return out

    raw_payment = fetched.get("payment")
    yk_payment: dict[str, Any] = raw_payment if isinstance(raw_payment, dict) else {}
    reg = str(yk_payment.get("receipt_registration") or "")
    if not should_auto_retry_fiscal_receipt(reg):
        reg_l = reg.strip().lower()
        outcome = "skip_pending" if reg_l == "pending" else "skip_reg"
        repo.update_payment_reconcile_fields(
            payment_id,
            {
                "reconcile_last_outcome": outcome,
                "reconcile_pre_error_streak": 0,
            },
        )
        out["action"] = outcome
        return out

    listed = yk_client.list_receipts(yk_id)
    if not listed.get("ok"):
        streak = int(payment.get("reconcile_pre_error_streak") or 0) + 1
        # На ветке unknown/post_started outcome не меняем (дизайн).
        fields: dict[str, Any] = {"reconcile_pre_error_streak": streak}
        if not is_unknown_outcome(str(payment.get("reconcile_last_outcome") or "")):
            fields["reconcile_last_outcome"] = "error_before_post"
        repo.update_payment_reconcile_fields(payment_id, fields)
        out["action"] = "gate_list_failed"
        out["error"] = listed.get("error")
        payment["reconcile_pre_error_streak"] = streak
        _maybe_alert(repo, payment, send_alert, reason="sticky_pre_error")
        return out

    # Полный fetch+list OK → streak сброс (даже если gate skip).
    repo.update_payment_reconcile_fields(
        payment_id, {"reconcile_pre_error_streak": 0}
    )
    payment["reconcile_pre_error_streak"] = 0

    gate = payment_receipt_retry_gate(listed.get("items") or [])
    if gate.get("skip"):
        reason = str(gate.get("reason") or "receipt_exists")
        outcome = (
            "succeeded"
            if "succeeded" in reason
            else "pending"
            if "pending" in reason
            else "succeeded"
        )
        fields = {
            "reconcile_last_outcome": outcome,
            "reconcile_post_payload": None,
        }
        if outcome == "succeeded":
            fields["fiscal_status"] = "registered"
        repo.update_payment_reconcile_fields(payment_id, fields)
        out["action"] = f"gate_{outcome}"
        return out

    attempts = int(payment.get("reconcile_attempts") or 0)
    outcome_prev = str(payment.get("reconcile_last_outcome") or "") or None
    ttl_alive = bool(repo.fiscal_reconcile_ttl_alive(payment_id))
    if is_unknown_outcome(outcome_prev) and payment.get("reconcile_post_at") is None:
        logger.warning(
            "fiscal_reconcile_post_at_missing payment=%s — путь TTL истёк",
            payment_id[:8],
        )
        ttl_alive = False

    same_key_retry = is_unknown_outcome(outcome_prev) and ttl_alive
    if (
        attempts_block_new_post(
            attempts=attempts,
            outcome=outcome_prev,
            ttl_alive=ttl_alive,
            bypass_limit=bypass_attempt_limit,
        )
        and not same_key_retry
    ):
        out["action"] = "attempts_exhausted"
        if bypass_attempt_limit:
            logger.warning(
                "fiscal_reconcile CLI bypass attempt limit payment=%s attempts=%s",
                payment_id[:8],
                attempts,
            )
        else:
            _maybe_alert(repo, payment, send_alert, reason="attempts")
            return out

    email, phone = _resolve_contacts(repo, payment)
    if customer_email:
        email = customer_email
    if customer_phone:
        phone = customer_phone
    body: dict[str, Any] | None = None
    attempt_for_key = attempts

    if same_key_retry:
        stored = repo.get_payment_reconcile_payload(payment_id) or {}
        raw_payload = stored.get("reconcile_post_payload")
        if isinstance(raw_payload, dict):
            body = stable_receipt_snapshot(raw_payload)
        attempt_for_key = attempts  # без +1
        if body is None:
            logger.warning(
                "fiscal_reconcile same-key без payload payment=%s — пересборка",
                payment_id[:8],
            )
            same_key_retry = False

    if not same_key_retry:
        if bypass_attempt_limit and attempts >= MAX_RECONCILE_ATTEMPTS:
            logger.warning(
                "fiscal_reconcile CLI: attempts>=3, всё равно +1 payment=%s",
                payment_id[:8],
            )
        body = _build_receipt_body(
            yk_client,
            payment=yk_payment,
            customer_email=email,
            customer_phone=phone,
            amount_rub=None,
        )
        if body is None:
            streak = int(payment.get("reconcile_pre_error_streak") or 0) + 1
            repo.update_payment_reconcile_fields(
                payment_id,
                {
                    "reconcile_last_outcome": "error_before_post",
                    "reconcile_pre_error_streak": streak,
                },
            )
            out["action"] = "error_before_post"
            out["error"] = "cannot_build_receipt_body"
            return out
        attempt_for_key = attempts + 1
        key = reconcile_idempotence_key(yk_id, attempt_for_key)
        if len(key) > 64:
            logger.error("fiscal_reconcile key>64 payment=%s", payment_id[:8])
            out["action"] = "key_too_long"
            return out
        marked = repo.mark_fiscal_reconcile_post_started(
            payment_id, attempts=attempt_for_key, payload=body
        )
        if marked is None:
            out["action"] = "mark_post_failed"
            return out
        payment = {**payment, **marked}
    else:
        key = reconcile_idempotence_key(yk_id, attempt_for_key)
        if len(key) > 64:
            out["action"] = "key_too_long"
            return out

    assert body is not None
    result = yk_client.create_receipt(
        payment_id=yk_id,
        amount_rub=0.0,
        description="",
        idempotence_key=key,
        body_snapshot=body,
    )
    new_outcome = classify_create_receipt_result(result)
    fields_after: dict[str, Any] = {"reconcile_last_outcome": new_outcome}
    if new_outcome == "succeeded":
        fields_after["fiscal_status"] = "registered"
        fields_after["reconcile_post_payload"] = None
    elif new_outcome == "pending":
        pass
    elif new_outcome == "error_before_post":
        # pre_post после mark — редкость (ключ); не жжём attempts повторно
        fields_after["reconcile_pre_error_streak"] = (
            int(payment.get("reconcile_pre_error_streak") or 0) + 1
        )
    repo.update_payment_reconcile_fields(payment_id, fields_after)
    payment["reconcile_last_outcome"] = new_outcome
    payment["reconcile_attempts"] = attempt_for_key
    out["action"] = new_outcome
    out["phase"] = result.get("phase")
    out["status_code"] = result.get("status_code")
    # Не кладём result целиком — там может быть receipt с ПДн.
    if not result.get("ok"):
        out["error"] = result.get("error")
    _maybe_alert(repo, payment, send_alert, reason="attempts")
    return out


def _maybe_alert(
    repo: Any,
    payment: dict[str, Any],
    send_alert: AlertSend,
    *,
    reason: str,
) -> None:
    payment_id = str(payment.get("id") or "")
    if not payment_id or payment.get("reconcile_alerted_at") is not None:
        return
    attempts = int(payment.get("reconcile_attempts") or 0)
    streak = int(payment.get("reconcile_pre_error_streak") or 0)
    outcome = str(payment.get("reconcile_last_outcome") or "") or None
    ttl_alive = False
    try:
        ttl_alive = bool(repo.fiscal_reconcile_ttl_alive(payment_id))
    except Exception:  # noqa: BLE001
        ttl_alive = False
    fire = False
    alert_reason = reason
    if reason == "sticky_pre_error" and should_alert_streak(streak):
        fire = True
        alert_reason = "pre_error_streak"
    elif reason == "attempts" and should_alert_attempts(
        attempts=attempts, outcome=outcome, ttl_alive=ttl_alive
    ):
        fire = True
        alert_reason = "attempts"
    elif reason == "stale_48h":
        fire = True
        alert_reason = "stale_48h"
    if not fire:
        return
    claimed = repo.claim_fiscal_reconcile_alert(payment_id)
    if claimed is None:
        return
    # Claim до send: лучше потерять повтор, чем спамить. False → ERROR (без отката).
    ok = send_alert(alert_reason, {**payment, **claimed})
    if not ok:
        logger.error(
            "fiscal_reconcile_alert_claimed_but_not_delivered payment=%s reason=%s",
            payment_id[:8],
            alert_reason,
        )


def run_fiscal_reconcile_tick(
    repo: Any,
    *,
    enabled: bool,
    dry_run: bool,
    alert_since_raw: str | None,
    client: YooKassaClient | None = None,
    limit: int = 50,
    alert_send: AlertSend | None = None,
) -> dict[str, Any]:
    """Точка входа CLI / systemd."""
    stats: dict[str, Any] = {
        "enabled": enabled,
        "dry_run": dry_run,
        "candidates": 0,
        "stale_alerts": 0,
        "results": [],
    }
    if not enabled:
        stats["skipped"] = "FISCAL_RECONCILE_ENABLED=0"
        return stats
    raw = (alert_since_raw or "").strip()
    if not raw:
        stats["error"] = (
            "FISCAL_RECONCILE_ALERT_SINCE required when ENABLED=1 "
            "(ISO timestamptz, e.g. 2026-10-23T00:00:00+00:00)"
        )
        logger.error("%s", stats["error"])
        return stats
    alert_since = _parse_alert_since(raw)
    if alert_since is None:
        stats["error"] = (
            f"FISCAL_RECONCILE_ALERT_SINCE invalid ISO: {raw[:40]!r} "
            "(fix .env; timer will keep failing until corrected)"
        )
        logger.error("%s", stats["error"])
        return stats

    yk = client or YooKassaClient()
    send = alert_send or _default_alert_send
    candidates = repo.list_succeeded_payments_for_reconcile(limit=limit)
    stats["candidates"] = len(candidates)
    for row in candidates:
        stats["results"].append(
            process_payment_reconcile(
                repo,
                row,
                client=yk,
                dry_run=dry_run,
                bypass_attempt_limit=False,
                alert_send=send,
            )
        )

    if not dry_run:
        stale = repo.list_payments_for_stale_fiscal_alert(
            alert_since=alert_since, limit=limit
        )
        stats["stale_alerts"] = len(stale)
        for row in stale:
            _maybe_alert(repo, row, send, reason="stale_48h")

    return stats
