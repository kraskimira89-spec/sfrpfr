"""Постфильтр max_llm_reply: утверждения о выполненных действиях.

Первый срез — ограниченный набор completed-action claims.
Цитата / отрицание / неопределённость в одной части сообщения
не разрешают неподтверждённое действие в другой.
Не универсальная проверка истинности всех ответов.
Не пишет даты и не создаёт TrustedOpResult.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

from sfrfr.services.deception_client_reply_policy import SAFE_INCOMPLETE_FACTS_FALLBACK
from sfrfr.services.max_trusted_error_context import (
    TrustedErrorContextPort,
    get_trusted_error_context_adapter,
)

logger = logging.getLogger(__name__)

FILTER_VERSION: Final = "sfrfr-110-llm-action-claim-v1.1"

ACTION_CLAIM_SAFE_FALLBACK: Final = SAFE_INCOMPLETE_FACTS_FALLBACK

# Явно: срез 1 блокирует перечисленные claims; разрешающий ack только для limit
# (TrustedErrorContext.limit_outcome == success на том же деле/версии).
# Ack регистрации / доставки / date_persist в этом срезе НЕ реализованы и НЕ
# превращаются в универсальное разрешение.


class ClaimKind(StrEnum):
    DATE_FIXED = "date_fixed"
    LIMIT_APPLIED = "limit_applied"
    CLAIM_REGISTERED = "claim_registered"
    REFUND_DONE = "refund_done"
    ASSIGNEE_SET = "assignee_set"


_CLAIM_SPECS: Final[tuple[tuple[ClaimKind, re.Pattern[str]], ...]] = tuple(
    (kind, re.compile(pat, re.IGNORECASE | re.UNICODE))
    for kind, pat in (
        (ClaimKind.DATE_FIXED, r"дата\s+исправлена"),
        (ClaimKind.DATE_FIXED, r"вс[её]\s+исправлено"),
        (ClaimKind.DATE_FIXED, r"(?<![\w])исправлено(?![\w])"),
        (ClaimKind.LIMIT_APPLIED, r"результат\s+(?:\S+\s+){0,3}ограничен"),
        (ClaimKind.LIMIT_APPLIED, r"использование\s+ограничено"),
        (ClaimKind.LIMIT_APPLIED, r"отмечен(?:а|о)?\s+как\s+требующ\w*\s+проверк"),
        (ClaimKind.CLAIM_REGISTERED, r"претензия\s+зарегистрирована"),
        (ClaimKind.REFUND_DONE, r"возврат\s+выполнен"),
        (ClaimKind.ASSIGNEE_SET, r"ответственный\s+назначен"),
    )
)

@dataclass(frozen=True)
class _FoundClaim:
    kind: ClaimKind
    matched: str
    start: int
    end: int


@dataclass
class FilteredLlmReply:
    text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    blocked: bool = False
    reason: str | None = None
    filter_version: str = FILTER_VERSION


def _strip_keyboards(attachments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not attachments:
        return []
    safe: list[dict[str, Any]] = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") in {"inline_keyboard", "keyboard"}:
            continue
        safe.append(item)
    return safe


def _mask_quoted_spans(text: str) -> str:
    """Заменить содержимое кавычек пробелами — цитата не считается нашим утверждением."""
    masked = text or ""
    for pat in (r"«[^»]*»", r"\"[^\"]*\"", r"'[^']*'"):
        masked = re.sub(pat, lambda m: " " * len(m.group(0)), masked)
    return masked


def _is_locally_negated(text: str, start: int) -> bool:
    """Отрицание непосредственно перед маркером (не «где-то в сообщении»)."""
    window = (text or "")[max(0, start - 56) : start]
    low = window.casefold()
    if re.search(r"(?:^|[\s,;:—-])не\s+$", low):
        return True
    if re.search(r"(?:ещё|еще|пока)\s+не\s+$", low):
        return True
    if "не буду сообщать" in low:
        return True
    return False


def _scan_completed_action_claims(text: str) -> list[_FoundClaim]:
    """Маркеры completed-action вне цитат и вне локального отрицания."""
    raw = text or ""
    if not raw.strip():
        return []
    masked = _mask_quoted_spans(raw)
    found: list[_FoundClaim] = []
    for kind, pat in _CLAIM_SPECS:
        for m in pat.finditer(masked):
            if _is_locally_negated(raw, m.start()):
                continue
            found.append(
                _FoundClaim(
                    kind=kind,
                    matched=m.group(0),
                    start=m.start(),
                    end=m.end(),
                )
            )
    return found


def _claim_trusted(
    kind: ClaimKind,
    *,
    case_id: str,
    adapter: TrustedErrorContextPort,
    current_result_version: str | None,
) -> bool:
    """Разрешение строго по виду операции. Чужой ack не универсален."""
    if not case_id:
        return False
    if kind == ClaimKind.LIMIT_APPLIED:
        ctx = adapter.load_for_case(
            case_id, current_result_version=current_result_version
        )
        if ctx is None or not ctx.belongs_to(case_id):
            return False
        return ctx.limit_outcome() == "success"
    # DATE_FIXED / CLAIM_REGISTERED / REFUND_DONE / ASSIGNEE_SET:
    # в срезе 1 нет отдельного trusted ack → всегда False (не синтезировать).
    _ = adapter, current_result_version
    return False


def filter_llm_action_claims(
    *,
    text: str,
    attachments: list[dict[str, Any]] | None = None,
    case_id: str | None = None,
    adapter: TrustedErrorContextPort | None = None,
    current_result_version: str | None = None,
) -> FilteredLlmReply:
    """Проверить LLM-текст на неподтверждённые completed-action claims."""
    cid = str(case_id or "").strip()
    port = adapter or get_trusted_error_context_adapter()
    atts = list(attachments or [])
    try:
        claims = _scan_completed_action_claims(text)
        if not claims:
            return FilteredLlmReply(text=text, attachments=atts, blocked=False)

        untrusted: list[_FoundClaim] = []
        for claim in claims:
            if not _claim_trusted(
                claim.kind,
                case_id=cid,
                adapter=port,
                current_result_version=current_result_version,
            ):
                untrusted.append(claim)

        if not untrusted:
            return FilteredLlmReply(text=text, attachments=atts, blocked=False)

        # Любой неподтверждённый claim → весь ответ заменяется (не частичный patch).
        labels = [f"{c.kind.value}:{c.matched}" for c in untrusted[:3]]
        return FilteredLlmReply(
            text=ACTION_CLAIM_SAFE_FALLBACK,
            attachments=_strip_keyboards(atts),
            blocked=True,
            reason="unconfirmed_action_claim:" + ",".join(labels),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm action claim filter failed: %s", exc)
        return FilteredLlmReply(
            text=ACTION_CLAIM_SAFE_FALLBACK,
            attachments=[],
            blocked=True,
            reason="filter_error",
        )
