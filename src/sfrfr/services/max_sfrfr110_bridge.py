"""Сквозной мост SFRFR-110 для MAX: факты операции → политика → исходящий пакет.

Первый срез: E05/F04 (неопределённость без фиктивного ограничения).
Не вызывает MAX API и не пишет в БД — вызывающий слой сохраняет/ставит в outbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from sfrfr.services.deception_client_reply_policy import (
    SAFE_INCOMPLETE_FACTS_FALLBACK,
    ConfirmedErrorReplyKind,
    client_facing_error_reply,
    persist_flag_is_trusted,
    reply_has_banned_internal_labels,
    reply_has_empty_placeholders,
)

POLICY_VERSION: Final = "sfrfr-110-e05-f04-v1"

CRITICAL_CLAIM_MARKERS: Final[tuple[str, ...]] = (
    "исправлено",
    "дата исправлена",
    "зарегистрирована",
    "зарегистрировано",
    "ответственный назначен",
    "использование ограничено",
    "отмечен как требующий проверки",
    "возврат выполнен",
    "проверка выполняется",
)


@dataclass(frozen=True)
class TrustedOpResult:
    """Результат реальной операции — не флаг модели."""

    case_id: str
    operation_id: str
    op_kind: str
    ok: bool
    source: str
    version: str | None = None
    detail: str | None = None

    def trusted_ok_for(self, *, case_id: str) -> bool:
        if str(self.case_id) != str(case_id):
            return False
        return persist_flag_is_trusted(source=self.source, value=self.ok)


@dataclass
class OutboundPackage:
    ok: bool
    text: str
    case_id: str
    operation_id: str
    policy_version: str
    kind: str
    evidence_refs: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False


def validate_outbound_client_text(text: str) -> dict[str, Any]:
    """Пост-проверка перед постановкой в outbox / send."""
    raw = text or ""
    if not raw.strip():
        return {"ok": False, "reason": "empty"}
    if reply_has_empty_placeholders(raw):
        return {"ok": False, "reason": "placeholder"}
    if reply_has_banned_internal_labels(raw):
        return {"ok": False, "reason": "internal_label"}
    if len(raw) > 4000:
        return {"ok": False, "reason": "too_long_before_truncate_policy"}
    return {"ok": True, "reason": "ok"}


def truncate_for_max(text: str, *, limit: int = 4000) -> str:
    """Обрезка как в enqueue; валидировать нужно уже усечённый текст."""
    return (text or "")[:limit]


def build_e05_f04_outbound(
    *,
    case_id: str,
    operation_id: str,
    confirmed_point: str,
    unknown_impact_area: str,
    limit_op: TrustedOpResult | None,
    invented_model_text: str | None = None,
) -> OutboundPackage:
    """E05/F04: ошибка подтверждена, последствия неизвестны.

    Если модель «придумала» текст с «ограничено» при неуспехе меры — блокируем.
    """
    cid = str(case_id).strip()
    op_id = str(operation_id).strip()
    if not cid or not op_id:
        return OutboundPackage(
            ok=False,
            text=SAFE_INCOMPLETE_FACTS_FALLBACK,
            case_id=cid,
            operation_id=op_id,
            policy_version=POLICY_VERSION,
            kind=ConfirmedErrorReplyKind.IMPACT_UNKNOWN.value,
            blocked_reason="missing_case_or_op",
            fallback=True,
        )

    limit_applied = False
    limit_source: str | None = None
    evidence: list[str] = []
    if limit_op is not None:
        evidence.append(f"op:{limit_op.operation_id}:{limit_op.op_kind}")
        if limit_op.trusted_ok_for(case_id=cid):
            limit_applied = True
            limit_source = limit_op.source
        else:
            # чужое дело / LLM-source / ok=False → не считаем меру применённой
            limit_applied = False
            limit_source = limit_op.source if limit_op.source else None

    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.IMPACT_UNKNOWN,
        facts={
            "confirmed_point": confirmed_point,
            "unknown_impact_area": unknown_impact_area,
            "provisional_limit_applied": limit_applied,
        },
        limit_source=limit_source if limit_applied else None,
    )
    # Критические ответы — из политики/фактов, не из свободной генерации.
    text = str(facing.get("text") or SAFE_INCOMPLETE_FACTS_FALLBACK)
    blocked: str | None = None
    if invented_model_text and not limit_applied:
        low_inv = invented_model_text.casefold()
        if (
            "использование ограничено" in low_inv
            or "отмечен как требующий проверки" in low_inv
            or "исправлено" in low_inv
        ):
            blocked = "model_invented_unconfirmed_claim"

    if not assert_no_limit_claim_without_measure(text, limit_applied=limit_applied):
        text = (
            f"Ошибка подтверждена в {confirmed_point}. Пока не установлено, "
            f"повлияла ли она на {unknown_impact_area}. "
            f"Не буду сообщать, что вопрос полностью исправлен, пока последствия "
            f"не проверены."
        )
        blocked = blocked or "stripped_limit_claim"

    truncated = truncate_for_max(text)
    check = validate_outbound_client_text(truncated)
    if not check["ok"]:
        return OutboundPackage(
            ok=True,
            text=SAFE_INCOMPLETE_FACTS_FALLBACK,
            case_id=cid,
            operation_id=op_id,
            policy_version=POLICY_VERSION,
            kind=ConfirmedErrorReplyKind.IMPACT_UNKNOWN.value,
            evidence_refs=evidence,
            blocked_reason=str(check["reason"]),
            fallback=True,
        )

    return OutboundPackage(
        ok=True,
        text=truncated,
        case_id=cid,
        operation_id=op_id,
        policy_version=POLICY_VERSION,
        kind=ConfirmedErrorReplyKind.IMPACT_UNKNOWN.value,
        evidence_refs=evidence,
        blocked_reason=blocked,
        fallback=bool(facing.get("fallback")),
    )

def assert_no_limit_claim_without_measure(text: str, *, limit_applied: bool) -> bool:
    if limit_applied:
        return True
    low = (text or "").casefold()
    return (
        "использование ограничено" not in low
        and "отмечен как требующий проверки" not in low
    )
