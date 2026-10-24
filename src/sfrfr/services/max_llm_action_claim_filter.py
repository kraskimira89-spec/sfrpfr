"""Постфильтр max_llm_reply: утверждения о выполненных действиях.

Первый срез — ограниченный набор completed-action claims.
Не универсальная проверка истинности всех ответов.
Не пишет даты и не создаёт TrustedOpResult.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final

from sfrfr.services.deception_client_reply_policy import SAFE_INCOMPLETE_FACTS_FALLBACK
from sfrfr.services.max_trusted_error_context import (
    TrustedErrorContextPort,
    get_trusted_error_context_adapter,
)

logger = logging.getLogger(__name__)

FILTER_VERSION: Final = "sfrfr-110-llm-action-claim-v1"

# Безопасная замена при блоке (совпадает по смыслу с incomplete facts).
ACTION_CLAIM_SAFE_FALLBACK: Final = SAFE_INCOMPLETE_FACTS_FALLBACK

# Срез 1: только эти completed-action маркеры (не offers / цитаты / отрицания).
_COMPLETED_ACTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"дата\s+исправлена",
        r"вс[её]\s+исправлено",
        r"(?<![А-Яа-яA-Za-z])исправлено(?![А-Яа-яA-Za-z])",
        r"результат\s+ограничен",
        r"использование\s+ограничено",
        r"отмечен(?:а|о)?\s+как\s+требующ\w*\s+проверк",
        r"претензия\s+зарегистрирована",
        r"возврат\s+выполнен",
        r"ответственный\s+назначен",
    )
)

_OFFER_HINTS: Final[tuple[str, ...]] = (
    "могу помочь",
    "можем помочь",
    "можем проверить",
    "можем уточнить",
    "давайте проверим",
    "помогу проверить",
    "помогу уточнить",
    "предложу проверить",
)

_QUOTE_HINTS: Final[tuple[str, ...]] = (
    "вы написали",
    "вы сказали",
    "вы пишете",
    "цитат",
)

_NEGATION_OR_UNCERTAINTY: Final[tuple[str, ...]] = (
    "не буду сообщать, что исправление",
    "не исправлено",
    "пока не установлено",
    "не подтверждено",
    "данных пока недостаточно",
    "не считаю подтверждённым",
    "не подтверждает",
)


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


def _looks_like_offer_or_quote_or_negation(text: str) -> bool:
    low = (text or "").casefold()
    if any(h in low for h in _NEGATION_OR_UNCERTAINTY):
        # Если весь ответ — uncertainty/negation вокруг маркера — не блок.
        # Блокируем только если есть голый completed-claim вне отрицания.
        return True
    if any(h in low for h in _OFFER_HINTS):
        return True
    if any(h in low for h in _QUOTE_HINTS):
        return True
    # Кавычки вокруг «…исправ…» / "…исправ…"
    if re.search(r"[«\"].{0,40}исправ.{0,40}[»\"]", text or "", re.IGNORECASE):
        return True
    return False


def _scan_completed_action_claims(text: str) -> list[str]:
    """Найти маркеры заявления о завершённом действии (не offer/quote/negation)."""
    raw = text or ""
    if not raw.strip():
        return []
    if _looks_like_offer_or_quote_or_negation(raw):
        # Особый случай: «Вы написали: …» — пропускаем целиком.
        # Если uncertainty + отдельное голое утверждение — всё равно осторожно:
        # для среза 1: при любом negation/uncertainty hint не блокируем весь текст,
        # если нет «голой» фразы вне отрицательной рамки.
        # Упрощение среза: negation/quote/offer → не completed-claim scan.
        return []
    found: list[str] = []
    for pat in _COMPLETED_ACTION_PATTERNS:
        m = pat.search(raw)
        if m:
            found.append(m.group(0))
    return found


def _limit_claim_trusted(
    *,
    case_id: str,
    adapter: TrustedErrorContextPort,
    current_result_version: str | None,
) -> bool:
    """Разрешить «ограничено» только при trusted success меры на этом деле/версии."""
    ctx = adapter.load_for_case(case_id, current_result_version=current_result_version)
    if ctx is None or not ctx.belongs_to(case_id):
        return False
    return ctx.limit_outcome() == "success"


def _date_fix_claim_trusted(
    *,
    case_id: str,
    adapter: TrustedErrorContextPort,
    current_result_version: str | None,
) -> bool:
    """Срез 1: подтверждённого persist даты в адаптере ещё нет → никогда True.

    Оставляем хук для будущего TrustedOpResult date_persist; не синтезировать.
    """
    _ = case_id, adapter, current_result_version
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

        # Разрешить только если для конкретного типа claim есть trusted факт.
        allow = False
        low_joined = " ".join(claims).casefold()
        if any(
            x in low_joined
            for x in ("ограничен", "отмечен")
        ):
            allow = bool(cid) and _limit_claim_trusted(
                case_id=cid,
                adapter=port,
                current_result_version=current_result_version,
            )
        elif any(x in low_joined for x in ("исправл",)):
            allow = bool(cid) and _date_fix_claim_trusted(
                case_id=cid,
                adapter=port,
                current_result_version=current_result_version,
            )
        # Прочие маркеры (зарегистрирована, возврат, назначен) — в срезе 1 без ack → блок.

        if allow:
            return FilteredLlmReply(text=text, attachments=atts, blocked=False)

        return FilteredLlmReply(
            text=ACTION_CLAIM_SAFE_FALLBACK,
            attachments=_strip_keyboards(atts),
            blocked=True,
            reason="unconfirmed_action_claim:" + ",".join(claims[:3]),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm action claim filter failed: %s", exc)
        return FilteredLlmReply(
            text=ACTION_CLAIM_SAFE_FALLBACK,
            attachments=[],
            blocked=True,
            reason="filter_error",
        )
