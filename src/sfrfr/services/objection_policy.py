"""Политика возражений клиента: классификация сигнала, не «продавец».

Возражение = сомнение / ограничение / отказ, а не препятствие для слома.
Претензии и stop — отдельные маршруты (не коммерческий цикл).
Цены и состав услуги сюда не хардкодить — только класс сигнала и запреты.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final


class ClientSignalKind(StrEnum):
    """Логические состояния сигнала (не обязательно отдельные поля БД)."""

    PRICE_OBJECTION = "price_objection"
    NO_MONEY = "no_money"
    GUARANTEE_ASK = "guarantee_ask"
    SELF_SERVICE = "self_service"
    SFR_ALREADY_CHECKED = "sfr_already_checked"
    SFR_REFUSED = "sfr_refused"
    TRUST = "trust"
    FEAR_DOCS = "fear_docs"
    NO_DOCS = "no_docs"
    CANT_UPLOAD = "cant_upload"
    ALREADY_SENT = "already_sent"
    THINKING = "thinking"
    CONSULT_OTHERS = "consult_others"
    HARD_REFUSE = "hard_refuse"
    STOP_MESSAGES = "stop_messages"
    CLAIM = "claim"
    ASK_SPECIALIST = "ask_specialist"
    CONDITIONS_QUESTION = "conditions_question"
    OTHER = "other"


# Претензии / сервис — не продажный цикл.
_CLAIM_RE: Final = re.compile(
    r"("
    r"оплатил.{0,40}результат\w*\s+нет|"
    r"оплатил.{0,40}нет\s+результат|"
    r"списал(и|о).{0,20}дважды|"
    r"верните\s+деньг|"
    r"потерял(и|а)\s+документ|"
    r"удалите\s+(мои\s+)?данн|"
    r"на\s+меня\s+дав(ят|ление)|"
    r"хочу\s+пожаловаться|"
    r"жалоба|"
    r"возврат\s+денег"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_PATTERNS: Final[tuple[tuple[ClientSignalKind, re.Pattern[str]], ...]] = (
    (ClientSignalKind.STOP_MESSAGES, re.compile(
        r"^(стоп|stop|отписаться|unsubscribe|/stop)$|"
        r"не\s+пишите\s+(мне|больше)|отключите\s+уведомлен",
        re.I,
    )),
    (ClientSignalKind.CLAIM, _CLAIM_RE),
    (ClientSignalKind.ASK_SPECIALIST, re.compile(
        r"специалист|человек|оператор|живого\s+собеседник|"
        r"позвать\s+(человека|специалиста)",
        re.I,
    )),
    (ClientSignalKind.GUARANTEE_ASK, re.compile(
        r"гарант|обязательно\s+добь|точно\s+добав|"
        r"обещаете\s+перерасч|гарантируете",
        re.I,
    )),
    (ClientSignalKind.NO_MONEY, re.compile(
        r"нет\s+денег|не\s+на\s+что|сейчас\s+не\s+потянуть|"
        r"не\s+могу\s+оплатить",
        re.I,
    )),
    (ClientSignalKind.PRICE_OBJECTION, re.compile(
        r"дорого|дороговато|слишком\s+доро|цена\s+высок|"
        r"не\s+по\s+карману",
        re.I,
    )),
    (ClientSignalKind.SELF_SERVICE, re.compile(
        r"сам(а|и)?\s+(обращ|подам|сделаю)|могу\s+сам|"
        r"сам\s+в\s+сфр|без\s+вас",
        re.I,
    )),
    (ClientSignalKind.SFR_REFUSED, re.compile(
        r"уже\s+отказ|мне\s+отказал|отказ\s+сфр|получил(а|и)?\s+отказ",
        re.I,
    )),
    (ClientSignalKind.SFR_ALREADY_CHECKED, re.compile(
        r"сфр\s+уже\s+(вс[её]|проверил)|уже\s+вс[её]\s+проверил|"
        r"вс[её]\s+учтено",
        re.I,
    )),
    (ClientSignalKind.TRUST, re.compile(
        r"не\s+довер|обман|развод|мошен",
        re.I,
    )),
    (ClientSignalKind.FEAR_DOCS, re.compile(
        r"боюсь\s+(отправ|загруз|передать)|страшно\s+слать\s+документ|"
        r"небезопасно",
        re.I,
    )),
    (ClientSignalKind.NO_DOCS, re.compile(
        r"нет\s+документ|документов\s+нет|нету\s+(илс|трудов)",
        re.I,
    )),
    (ClientSignalKind.CANT_UPLOAD, re.compile(
        r"не\s+умею\s+загру[зж]|не\s+умею\s+отправ|как\s+загру[зж]|"
        r"не\s+получается\s+загру[зж]",
        re.I,
    )),
    (ClientSignalKind.ALREADY_SENT, re.compile(
        r"уже\s+(вс[её]\s+)?(отправ|загруз|присылал)|я\s+уже\s+вс[её]\s+слал",
        re.I,
    )),
    (ClientSignalKind.CONSULT_OTHERS, re.compile(
        r"посоветоваться|с\s+(женой|мужем|детьми|семь[её]й)|"
        r"обсуд(ить|им)\s+с",
        re.I,
    )),
    (ClientSignalKind.THINKING, re.compile(
        r"подумаю|надо\s+подумать|не\s+сейчас|позже\s+решу",
        re.I,
    )),
    (ClientSignalKind.HARD_REFUSE, re.compile(
        r"не\s+хочу|не\s+надо|не\s+нужно|отказываюсь|"
        r"не\s+буду\s+(платить|оформ)|хватит\s+предлагать",
        re.I,
    )),
    (ClientSignalKind.CONDITIONS_QUESTION, re.compile(
        r"что\s+входит|сколько\s+стоит|какие\s+условия|оферта",
        re.I,
    )),
)

# Фразы, которые нельзя генерировать в ответе на возражение (подстроки).
BANNED_OBJECTION_REPLY_MARKERS: Final[tuple[str, ...]] = (
    "теряете деньги каждый день",
    "окупится за счёт прибавки",
    "оформите кредит",
    "займите",
    "успейте сегодня",
    "осталось мало мест",
    "скидка только сегодня",
    "вам всё равно придётся платить",
    "гарантируем перерасчёт",
    "точно добьёмся",
    "недоплачивают",
)


def classify_client_signal(text: str) -> ClientSignalKind:
    """Классифицировать клиентский сигнал (порядок: претензия/stop раньше продажи)."""
    raw = (text or "").strip()
    if not raw:
        return ClientSignalKind.OTHER
    for kind, pattern in _PATTERNS:
        if pattern.search(raw):
            return kind
    return ClientSignalKind.OTHER


def is_claim_or_stop(kind: ClientSignalKind) -> bool:
    return kind in {ClientSignalKind.CLAIM, ClientSignalKind.STOP_MESSAGES}


def may_reoffer_after_signal(kind: ClientSignalKind) -> bool:
    """Можно ли в том же ходе снова показывать коммерческий offer."""
    if kind in {
        ClientSignalKind.HARD_REFUSE,
        ClientSignalKind.THINKING,
        ClientSignalKind.NO_MONEY,
        ClientSignalKind.CLAIM,
        ClientSignalKind.STOP_MESSAGES,
        ClientSignalKind.CONSULT_OTHERS,
    }:
        return False
    return True


def reply_has_banned_objection_pressure(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_OBJECTION_REPLY_MARKERS)


# Отказ от оплаты ≠ удаление данных / полный stop / «проблемы со стажем нет».
PAYMENT_REFUSAL_IS_NOT: Final[frozenset[str]] = frozenset(
    {
        "data_delete",
        "all_messages_stop",
        "no_stazh_problem",
    }
)
