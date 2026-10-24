"""Агрессия / претензия / жалоба: содержание требования важнее тона (§20.21).

Расширение 20.15: тон ≠ метка «оскорбление», не отменяет статус/возврат/претензию.
Угроза жалобой ≠ угроза вреда. Без миграции — логическая карточка обращения.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final


class ComplaintVariant(StrEnum):
    DELAY_ANGER = "delay_anger"  # А
    THREATEN_REVIEW = "threaten_review"  # Б
    FORMAL_CLAIM = "formal_claim"  # В
    IMMEDIATE_REFUND = "immediate_refund"  # Г
    FRAUD_ACCUSATION = "fraud_accusation"  # Д
    INSULT = "insult"  # Е
    HARM_THREAT = "harm_threat"  # Ж
    MULTI_CHANNEL = "multi_channel"  # З
    AI_ERROR_CLAIM = "ai_error_claim"  # И
    WRONG_CLIENT_ASSERTION = "wrong_client_assertion"  # К


class RequirementKind(StrEnum):
    STATUS = "status"
    SERVICE_QUALITY = "service_quality"
    REFUND = "refund"
    FORMAL_CLAIM = "formal_claim"
    DELETE_DATA = "delete_data"
    REVIEW_COMPLAINT = "review_complaint"
    OTHER = "other"


class ToneKind(StrEnum):
    NEUTRAL = "neutral"
    SHARP = "sharp"
    INSULTING = "insulting"
    COMPLAINT_THREAT = "complaint_threat"
    HARM_THREAT = "harm_threat"


_HARM_THREAT_RE: Final = re.compile(
    r"приеду\s+и\s+причин|"
    r"причин(ю|ить)\s+(вашему\s+)?сотрудник|"
    r"угрожа(ю|ем)\s+физич|"
    r"разобью\s+(вам|тебе)|"
    r"убить\s+(вас|сотрудник)",
    re.I,
)
_FORMAL_CLAIM_RE: Final = re.compile(
    r"зарегистрируйте\s+претензи|"
    r"официальн(ую|ая)\s+претензи|"
    r"мне\s+не\s+нужен\s+разговор\s+с\s+ботом",
    re.I,
)
_REFUND_RE: Final = re.compile(
    r"верните\s+(деньг|оплат)|"
    r"возврат|"
    r"деньги\s+прямо\s+сейчас|"
    r"больше\s+с\s+вами\s+работать\s+не\s+хочу",
    re.I,
)
_REVIEW_THREAT_RE: Final = re.compile(
    r"напишу\s+на\s+вас\s+жалоб|"
    r"отзыв\s+везде|"
    r"оставлю\s+отзыв|"
    r"пожалуюсь\s+(в|на)|"
    r"подам\s+в\s+суд",
    re.I,
)
_FRAUD_RE: Final = re.compile(
    r"мошенник|ничего\s+не\s+проверяли|"
    r"развод\s+на\s+деньг",
    re.I,
)
_AI_ERROR_CLAIM_RE: Final = re.compile(
    r"бот\s+сказал.{0,40}прибав|"
    r"отказываетесь\s+от\s+слов|"
    r"оплатил.{0,40}отказываетесь",
    re.I | re.DOTALL,
)
_MULTI_CHANNEL_RE: Final = re.compile(
    r"уже\s+писал.{0,30}(кабинет|max)|"
    r"в\s+кабинете\s+и\s+в\s+max|"
    r"никто\s+не\s+отвечает",
    re.I | re.DOTALL,
)
_DELAY_RE: Final = re.compile(
    r"сколько\s+можно\s+ждать|"
    r"только\s+деньги\s+брать|"
    r"где\s+мой\s+отч[её]т|"
    r"вы\s+вообще\s+ничего\s+не\s+делаете",
    re.I,
)
_INSULT_RE: Final = re.compile(
    r"безграмотн|дебил|идиот|туп(ые|ой)|"
    r"делайте\s+что\s+я\s+сказал",
    re.I,
)
_WRONG_SEND_RE: Final = re.compile(
    r"ничего\s+мне\s+не\s+отправляли|"
    r"вы\s+вообще\s+ничего\s+мне\s+не\s+отправляли",
    re.I,
)
_DELETE_DATA_RE: Final = re.compile(
    r"удалите\s+(мои\s+)?данн|удалить\s+данн",
    re.I,
)

BANNED_COMPLAINT_REPLY: Final[tuple[str, ...]] = (
    "мы всегда всё делаем вовремя",
    "деньги вернули",
    "вопрос решён",
    "удалите отзыв",
    "скидка за отзыв",
    "откажитесь от жалобы",
    "неадекватный",
    "шантажист",
    "проблемный клиент",
    "вы врёте",
    "помощь уже вызвана",
    "купите вместо возврата",
)

FORBIDDEN_INTERNAL_LABELS: Final[tuple[str, ...]] = (
    "неадекватный",
    "шантажист",
    "проблемный клиент",
    "угроза",  # не называть жалобу «угрозой» клиенту
)


def classify_complaint_signal(text: str) -> ComplaintVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _HARM_THREAT_RE.search(raw):
        return ComplaintVariant.HARM_THREAT
    if _AI_ERROR_CLAIM_RE.search(raw):
        return ComplaintVariant.AI_ERROR_CLAIM
    if _FORMAL_CLAIM_RE.search(raw):
        return ComplaintVariant.FORMAL_CLAIM
    if _WRONG_SEND_RE.search(raw):
        return ComplaintVariant.WRONG_CLIENT_ASSERTION
    if _MULTI_CHANNEL_RE.search(raw):
        return ComplaintVariant.MULTI_CHANNEL
    if _FRAUD_RE.search(raw):
        return ComplaintVariant.FRAUD_ACCUSATION
    if _REFUND_RE.search(raw):
        # Возврат важнее тона задержки / жалобы в том же сообщении
        return ComplaintVariant.IMMEDIATE_REFUND
    if _REVIEW_THREAT_RE.search(raw):
        return ComplaintVariant.THREATEN_REVIEW
    if _DELAY_RE.search(raw):
        return ComplaintVariant.DELAY_ANGER
    if _INSULT_RE.search(raw):
        return ComplaintVariant.INSULT
    return None


def extract_message_layers(text: str) -> dict[str, Any]:
    """Тон и содержание — отдельно (§31)."""
    raw = text or ""
    low = raw.casefold()
    requirements: list[str] = []
    if re.search(r"где\s+мой|статус|отч[её]т|результат|сколько\s+можно", low):
        requirements.append(RequirementKind.STATUS.value)
    if re.search(r"верните|возврат", low):
        requirements.append(RequirementKind.REFUND.value)
    if re.search(r"претензи|зарегистрируйте", low):
        requirements.append(RequirementKind.FORMAL_CLAIM.value)
    if _DELETE_DATA_RE.search(raw):
        requirements.append(RequirementKind.DELETE_DATA.value)
    if re.search(r"жалоб|отзыв|суд", low):
        requirements.append(RequirementKind.REVIEW_COMPLAINT.value)
    if re.search(r"ничего\s+не\s+дела|не\s+проверял|качество", low):
        requirements.append(RequirementKind.SERVICE_QUALITY.value)
    if not requirements:
        requirements.append(RequirementKind.OTHER.value)

    tone = ToneKind.NEUTRAL.value
    if _HARM_THREAT_RE.search(raw):
        tone = ToneKind.HARM_THREAT.value
    elif _REVIEW_THREAT_RE.search(raw):
        tone = ToneKind.COMPLAINT_THREAT.value
    elif _INSULT_RE.search(raw) or "мошенник" in low:
        tone = ToneKind.INSULTING.value
    elif re.search(r"только\s+деньги|сколько\s+можно|вообще\s+ничего", low):
        tone = ToneKind.SHARP.value

    return {
        "requirements": requirements,
        "tone": tone,
        "reduce_to_insult_only": False,
        "content_still_processed": True,
    }


def is_complaint_threat_not_harm(text: str) -> bool:
    """«Подам жалобу / суд / отзыв» ≠ физическая опасность."""
    raw = text or ""
    if _HARM_THREAT_RE.search(raw):
        return False
    return bool(_REVIEW_THREAT_RE.search(raw))


def may_discourage_complaint() -> bool:
    return False


def may_trade_help_for_no_complaint() -> bool:
    return False


def may_promise_refund_without_authority() -> bool:
    return False


def may_say_resolved_when_only_task_created() -> bool:
    return False


def may_invent_sla_deadline() -> bool:
    return False


def may_offer_upsell_instead_of_claim() -> bool:
    return False


def may_close_claim_for_tone() -> bool:
    return False


def may_accuse_client_of_lying() -> bool:
    return False


def may_claim_registration_without_success() -> bool:
    return False


def may_apply_harm_route_to_review_threat() -> bool:
    return False


def complaint_case_record(
    *,
    channel: str,
    subject: str,
    requirements: list[str],
    client_position: str,
    case_linked: bool = False,
    registered: bool = False,
    ticket_id: str | None = None,
    deadline: str | None = None,
    deadline_source: str | None = None,
) -> dict[str, Any]:
    """Логическая карточка §32 — без новой схемы «для бота»."""
    return {
        "channel": channel,
        "subject": subject,
        "requirements": list(requirements),
        "case_linked": case_linked,
        "facts": [],
        "client_position": client_position,
        "client_label": None,
        "evidence": [],
        "assignee": None,
        "deadline": deadline if deadline_source else None,
        "deadline_source": deadline_source,
        "actions_planned": [],
        "actions_done": [],
        "outcome": None,
        "disagreement": None,
        "registered": registered,
        "ticket_id": ticket_id if registered else None,
        "task_created_is_not_resolution": True,
        "reply_sent_is_not_refund": True,
    }


def registration_reply(*, succeeded: bool, ticket_id: str | None = None) -> dict[str, Any]:
    if succeeded and ticket_id:
        return {
            "announce_accepted": True,
            "ticket_id": ticket_id,
            "text_ok": True,
        }
    return {
        "announce_accepted": False,
        "ticket_id": None,
        "must_say_failed": True,
    }


def send_vs_delivery_status(
    *,
    prepared: bool,
    sent: bool,
    delivered: bool,
    opened: bool,
) -> dict[str, Any]:
    """Подготовка ≠ отправка ≠ доставка ≠ открытие."""
    return {
        "prepared": prepared,
        "sent": sent,
        "delivered": delivered,
        "opened": opened,
        "may_blame_client": False,
        "prove_received": delivered and opened,
    }


def harm_threat_response() -> dict[str, Any]:
    return {
        "pause_provocation": True,
        "no_plan_details_asked": True,
        "claim_emergency_dispatched": False,
        "keep_service_request": True,
        "separate_from_review_threat": True,
        "template_core": (
            "Я могу помочь только с решением вопроса по делу. "
            "Сообщение с угрозой требует отдельной обработки по правилам безопасности. "
            "Само обращение по услуге будет сохранено."
        ),
    }


def reply_has_banned_complaint_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    # «угроза» в клиентском ответе о жалобе — бан; про безопасность Ж — ок в template.
    if "угроз" in low and "безопасност" not in low and "жалоб" in low:
        return True
    return any(m in low for m in BANNED_COMPLAINT_REPLY)


def reply_has_forbidden_complaint_label(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(
        m in low
        for m in ("неадекватный", "шантажист", "проблемный клиент")
    )
