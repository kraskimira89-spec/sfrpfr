"""Один MAX reply-path для E05/F04: адаптер → политика → outbox.

Не реализует бизнес-установку ограничения: получает TrustedOpResult или отсутствие.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sfrfr.services.max_sfrfr110_bridge import (
    OutboundPackage,
    build_e05_f04_outbound,
)
from sfrfr.services.max_trusted_error_context import (
    ERROR_NOT_CONFIRMED_TEMPLATE,
    F04_UNCERTAINTY_TEMPLATE,
    TrustedErrorContext,
    TrustedErrorContextPort,
    get_trusted_error_context_adapter,
)

logger = logging.getLogger(__name__)

ACTION_E05_F04 = "max_e05_f04_policy"

# Исходы для вызывающего кода — не смешивать.
OUTCOME_NO_TRUSTED_CONTEXT = "no_trusted_context"  # не мой сценарий / Null
OUTCOME_INSUFFICIENT_FACTS = "insufficient_facts"  # контекст есть, ошибка не подтверждена
OUTCOME_POLICY_PREPARED = "policy_prepared"  # ответ сформирован политикой
OUTCOME_DELIVERY_UNCONFIRMED = "delivery_unconfirmed"  # prepared, транспорт/persist не подтверждён


@dataclass
class PolicyReply:
    text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    action: str = ACTION_E05_F04
    package: OutboundPackage | None = None
    used_fallback: bool = False
    outcome: str = OUTCOME_POLICY_PREPARED


def _strip_incompatible_attachments(
    attachments: list[dict[str, Any]] | None,
    *,
    fallback: bool,
) -> list[dict[str, Any]]:
    if fallback or not attachments:
        return []
    # Коммерческие inline-кнопки не тащим к policy/fallback ответу.
    safe: list[dict[str, Any]] = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        t = str(item.get("type") or "")
        if t in {"inline_keyboard", "keyboard"}:
            continue
        safe.append(item)
    return safe


def try_policy_reply_for_case(
    *,
    case_id: str | None,
    invented_model_text: str | None = None,
    current_result_version: str | None = None,
    adapter: TrustedErrorContextPort | None = None,
    prior_attachments: list[dict[str, Any]] | None = None,
) -> PolicyReply | None:
    """Если есть доверенный контекст E05 — вернуть контролируемый текст.

    None = перехват не применяется (обычный LLM/иной путь).
    """
    cid = str(case_id or "").strip()
    if not cid:
        return None
    port = adapter or get_trusted_error_context_adapter()
    ctx = port.load_for_case(cid, current_result_version=current_result_version)
    if ctx is None:
        return None
    if not ctx.belongs_to(cid):
        return None

    if not ctx.error_confirmed:
        text = ERROR_NOT_CONFIRMED_TEMPLATE
        return PolicyReply(
            text=text,
            attachments=_strip_incompatible_attachments(prior_attachments, fallback=True),
            used_fallback=True,
            outcome=OUTCOME_INSUFFICIENT_FACTS,
        )

    desc = (ctx.error_description or "").strip() or "указанном фрагменте"
    impact = (ctx.unknown_impact_area or "").strip() or "результат проверки"
    op_id = ctx.operation_id or f"e05-{uuid.uuid4().hex[:12]}"

    pkg = build_e05_f04_outbound(
        case_id=cid,
        operation_id=op_id,
        confirmed_point=desc,
        unknown_impact_area=impact,
        limit_op=ctx.limit_op,
        invented_model_text=invented_model_text,
    )
    # Мера применена только при trusted success; unknown ≠ confirmed_failure.
    limit_outcome = ctx.limit_outcome()
    limit_ok = limit_outcome == "success"
    if not limit_ok:
        text = F04_UNCERTAINTY_TEMPLATE.format(
            error_description=desc,
            impact_area=impact,
        )
        evidence = list(pkg.evidence_refs)
        evidence.append(f"limit_outcome:{limit_outcome}")
        pkg = OutboundPackage(
            ok=True,
            text=text,
            case_id=cid,
            operation_id=op_id,
            policy_version=pkg.policy_version,
            kind=pkg.kind,
            evidence_refs=evidence,
            blocked_reason=pkg.blocked_reason,
            attachments=[],
            fallback=bool(pkg.fallback or pkg.blocked_reason),
        )
    else:
        text = pkg.text

    atts = _strip_incompatible_attachments(
        prior_attachments if not pkg.fallback else None,
        fallback=bool(pkg.fallback or not limit_ok),
    )
    return PolicyReply(
        text=text,
        attachments=atts,
        action=ACTION_E05_F04,
        package=pkg,
        used_fallback=bool(pkg.fallback or not limit_ok),
        outcome=OUTCOME_POLICY_PREPARED,
    )


def deliver_policy_reply_via_outbox(
    *,
    case_id: str,
    max_user_id: str,
    reply: PolicyReply,
    message_id: str | None = None,
    process_now: bool = False,
    bot: Any | None = None,
) -> dict[str, Any]:
    """Сохранить постановку в существующий outbox; опционально process с mock/bot.

    Успешный enqueue ≠ отправка ≠ прочтение.
    """
    from sfrfr.services.case_chat_delivery import (
        enqueue_max_delivery,
        process_pending_outbox,
    )

    mid = str(max_user_id or "").strip()
    cid = str(case_id or "").strip()
    text = (reply.text or "").strip()
    if not mid or not cid or not text:
        return {
            "enqueued": False,
            "sent": False,
            "reason": "missing_recipient_or_text",
        }

    ok = enqueue_max_delivery(
        case_id=cid,
        message_id=message_id,
        max_user_id=mid,
        body=text,
        attachments=list(reply.attachments or []),
    )
    result: dict[str, Any] = {
        "enqueued": bool(ok),
        "sent": False,
        "action": reply.action,
        "transport": None,
        "stages": {
            "prepared": True,
            "enqueued": bool(ok),
            "transport_accepted": False,
            "outbox_marked_sent": False,
            "delivered_to_user": False,
            "read": False,
        },
    }
    if not ok:
        result["reason"] = "enqueue_failed"
        result["caller_outcome"] = OUTCOME_DELIVERY_UNCONFIRMED
        return result
    if not process_now:
        result["reason"] = "enqueued_pending"
        result["caller_outcome"] = OUTCOME_DELIVERY_UNCONFIRMED
        return result

    # Изолированные тесты подменяют process_pending_outbox / bot.
    if bot is not None:
        try:
            transport = bot.send_message(text=text, user_id=mid)
            accepted = not (
                isinstance(transport, dict)
                and (transport.get("skipped") or transport.get("ok") is False)
            )
            result["sent"] = accepted
            result["transport"] = transport
            result["stages"]["transport_accepted"] = accepted
            # Mock/direct path не пишет status=sent в БД — не утверждать persist.
            result["stages"]["outbox_marked_sent"] = False
            result["reason"] = "mock_or_direct_after_enqueue"
            result["caller_outcome"] = (
                OUTCOME_POLICY_PREPARED if accepted else OUTCOME_DELIVERY_UNCONFIRMED
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("e05_f04 transport after enqueue failed: %s", exc)
            result["reason"] = "transport_failed"
            result["sent"] = False
            result["caller_outcome"] = OUTCOME_DELIVERY_UNCONFIRMED
        return result

    sent_n = process_pending_outbox(limit=1, message_id=message_id)
    result["sent"] = sent_n > 0
    result["stages"]["transport_accepted"] = sent_n > 0
    result["stages"]["outbox_marked_sent"] = sent_n > 0
    result["reason"] = "processed_outbox" if sent_n else "enqueued_not_sent"
    result["caller_outcome"] = (
        OUTCOME_POLICY_PREPARED if sent_n > 0 else OUTCOME_DELIVERY_UNCONFIRMED
    )
    return result


def context_from_fixture(ctx: TrustedErrorContext) -> TrustedErrorContext:
    """Явный helper тестов — не для production import side effects."""
    return ctx
