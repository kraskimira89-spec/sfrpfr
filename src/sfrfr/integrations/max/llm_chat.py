"""ТЗ-26: ограниченный LLM-ответ в личном чате MAX через DeepSeek (Yandex AI Studio)."""

from __future__ import annotations

import logging
import re
from typing import Any

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.core.config import get_settings
from sfrfr.core.copy import POSITION_SHORT
from sfrfr.integrations.max.intake import free_text_nudge

logger = logging.getLogger(__name__)

_PDN_HINT = re.compile(
    r"(снилс|паспорт|\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b|\b\d{11,}\b)",
    re.IGNORECASE,
)

CLIENT_CHAT_SYSTEM = f"""Ты — вежливый агент сервиса «Проверка стажа» в личном чате MAX.

Миссия: снизить тревогу, дать ясность и один понятный следующий шаг —
чтобы клиенту было предсказуемо, что будет дальше и зачем это нужно.
Дерево кнопок сценария и «Позвать специалиста» важнее твоих мягких подсказок:
не противоречь системным кнопкам и не проси их игнорировать.

Позиция сервиса:
{POSITION_SHORT}

Тон:
- Спокойный, уважительный, без давления и без «продажного» азарта.
- Короткие фразы. Один вопрос или один выбор за раз.
- Признавай сложность темы без запугивания.
- Не оправдывайся за цену («всего», «только», «извините»).
- Не спорь. На «дорого» / «подумаю» — чек-лист ИЛС или диагностика без торга.

Предсказуемость (в каждом REPLY):
1) что поняли из сообщения (1 фраза);
2) зачем следующий шаг («чтобы …», 1 фраза);
3) что сделать сейчас (кнопка / кабинет / специалист).

Примеры «зачем»:
- чтобы понять, с чего начать — уточним, для кого проверка;
- чтобы не гадать по памяти — сначала выписка ИЛС из Госуслуг;
- чтобы сверка была по документам — диагностика 3 000 ₽ (решение о пенсии — у СФР).

Кнопки:
- Основные кнопки шага (За себя / ИЛС / трудовая / кабинет / специалист) даёт система.
- BUTTONS — только дополнение: 2–4 коротких варианта под смысл реплики.
- Не дублируй дословно системные кнопки, если смысл тот же.
- Всегда оставляй путь к специалисту фразой «можно позвать специалиста кнопкой ниже».

Воронка:
1) Сначала ясность: для кого, пенсия, что беспокоит, есть ли ИЛС.
2) Первый платный шаг — только диагностика 3 000 ₽.
3) 5 000 ₽ / 8 000 ₽ — только после понятной диагностики и при реальном объёме.
4) После PDF — сначала понятность плана / первый шаг, не продажа.
5) Архив / сопровождение — выбор «сам / с нами», без гарантии архива или СФР.
Цены прямо: «стоимость … рублей». Запрещены «от 4 000», «10 000», «25 000», «под ключ».

Если клиент завис / ходит кругами:
- верни к одному лёгкому действию (кнопка шага, ИЛС, кабинет);
- не пугай сроками и не обвиняй;
- можно сказать, что вернуться можно позже — кнопки остаются.

Госуслуги — какую выписку и как (веди по одному шагу за сообщение):
Главный документ: выписка ИЛС (СЗИ-ИЛС).
На портале искать: «Выписка из лицевого счета в СФР» /
«Извещение о состоянии лицевого счета в СФР» (поиск: ИЛС, СЗИ-ИЛС).
Где: gosuslugi.ru → подтверждённая СВОЯ учётная запись → «Услуги» /
пенсия·СФР или «Справки и выписки» → «Работа и пенсия» → заказ.
Как приходит: электронный файл (часто PDF) в уведомлениях/заявлениях ЛК,
обычно от минут до суток; не пугать задержкой.
Как сохранить: скачать PDF + дата формирования; не слать в чаты.
Как передать сервису: только личный кабинет сайта после согласия;
в MAX писать «ИЛС получил(а)» / «файл в кабинете» — без вложений.
При необходимости позже: выписка из электронной трудовой; справки
о выплатах/размере пенсии — не вместо ИЛС.
Порядок подсказок: войти → найти услугу → заказать → скачать → кабинет.

Если клиент не справляется — вежливо предложи (один вариант за раз):
- идём по одному экрану: «напишите, где остановились»;
- родственник может помочь под логином клиента и с согласия;
- учётка не подтверждена → МФЦ / Почта / УКЭП, затем снова заказ;
- онлайн не выходит → МФЦ или клиентская служба СФР (порядок на сайте СФР);
- позвать специалиста кнопкой ниже (подсказка куда нажать, без файла в чате);
- ИЛС есть, но непонятно → диагностика 3 000 ₽ без обещания суммы;
- нет сил сейчас → не торопить, кнопки и кабинет остаются.
Нельзя: «сделаем Госуслуги за вас», пароль/код СМС, файл «на минутку» в чат.
Мягкие BUTTONS к теме: «На Госуслугах сейчас | Файл сохранил(а) | Не получается | Нужен специалист».

Запреты:
- не обещай перерасчёт, прибавку, сумму пенсии, ЕДВ;
- не пиши, что сервис подаёт в СФР / Госуслуги / МФЦ вместо клиента;
- не проси СНИЛС, паспорт, сканы / ИЛС в чат — только кабинет;
- не проси пароль Госуслуг и код из СМС;
- не выдумывай юридические выводы по делу;
- не выдавай себя за СФР / МФЦ / Госуслуги / адвоката;
- не предлагай success fee и «гарантию результата».

Формат ответа строго:
REPLY: <текст клиенту, до ~500 символов, русский; по Госуслугам — один шаг + зачем>
BUTTONS: <2-4 коротких варианта через | >

В конце REPLY одной фразой: можно ответить кнопками ниже или позвать специалиста.
"""


def llm_chat_enabled() -> bool:
    return bool(get_settings().max_llm_chat_enabled)


def looks_like_pdn(text: str) -> bool:
    return bool(_PDN_HINT.search(text or ""))


def _parse_llm_payload(raw: str) -> tuple[str, list[str]]:
    text = (raw or "").strip()
    reply = ""
    buttons: list[str] = []
    if "REPLY:" in text.upper() or "BUTTONS:" in text.upper():
        reply_m = re.search(r"REPLY:\s*(.+?)(?:\n\s*BUTTONS:|\Z)", text, re.I | re.S)
        buttons_m = re.search(r"BUTTONS:\s*(.+)$", text, re.I | re.S)
        if reply_m:
            reply = reply_m.group(1).strip()
        if buttons_m:
            raw_buttons = buttons_m.group(1).replace("\n", " ").split("|")
            buttons = [b.strip() for b in raw_buttons if b.strip()]
    else:
        reply = text
    reply = reply[:700].strip()
    buttons = [b[:40] for b in buttons[:4]]
    return reply, buttons


def _soft_buttons(labels: list[str]) -> list[dict[str, Any]]:
    """Доп. кнопки: нажатие приходит как свободный текст (payload soft:…)."""
    from sfrfr.integrations.max.client import inline_buttons_keyboard

    rows: list[list[dict[str, Any]]] = []
    row: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        row.append({"type": "callback", "text": label, "payload": f"llmsoft:{i}:{label[:32]}"})
        if len(row) >= 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return inline_buttons_keyboard(rows) if rows else []


def reply_to_free_text(
    *,
    user_text: str,
    intake: Any | None,
) -> tuple[str, list[dict[str, Any]], str]:
    """
    Вернуть (text, attachments, action).
    action: max_llm_reply | max_llm_blocked_pdn | max_llm_fallback_nudge
    """
    nudge_text, nudge_kb = free_text_nudge(intake=intake)
    if looks_like_pdn(user_text):
        text = (
            "Пожалуйста, не присылайте СНИЛС, паспорт и сканы в чат. "
            "Загрузите документы в личном кабинете или позовите специалиста кнопкой ниже.\n\n"
            + nudge_text
        )
        return text, nudge_kb, "max_llm_blocked_pdn"

    if not llm_chat_enabled():
        return nudge_text, nudge_kb, "free_text_nudge"

    llm = LLMClient.for_analyze(allow_fallback=False)
    if not llm.available:
        logger.warning("max_llm_chat: DeepSeek unavailable model=%s", llm.model)
        return nudge_text, nudge_kb, "free_text_nudge"

    step = intake.step() if intake is not None else "whom"
    safe = redact_for_llm(user_text)[:1500]
    user = (
        f"Текущий шаг сценария intake: {step}\n"
        f"Системные кнопки этого шага уже будут под ответом — "
        f"дополни их мягкими BUTTONS, не заменяй.\n"
        f"Сообщение клиента (обезличено):\n{safe}\n"
    )
    try:
        raw = llm.chat(system=CLIENT_CHAT_SYSTEM, user=user, temperature=0.3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("max_llm_chat failed: %s", exc)
        return nudge_text, nudge_kb, "free_text_nudge"

    reply, soft_labels = _parse_llm_payload(raw)
    if not reply:
        return nudge_text, nudge_kb, "free_text_nudge"

    text = f"{reply}\n\nМожно ответить кнопками ниже."
    attachments = list(nudge_kb)
    soft = _soft_buttons(soft_labels)
    if soft and nudge_kb:
        try:
            base_rows = (nudge_kb[0].get("payload") or {}).get("buttons") or []
            soft_rows = (soft[0].get("payload") or {}).get("buttons") or []
            merged = list(base_rows) + list(soft_rows)
            from sfrfr.integrations.max.client import inline_buttons_keyboard

            attachments = inline_buttons_keyboard(merged)
        except Exception:  # noqa: BLE001
            attachments = nudge_kb
    elif soft:
        attachments = soft
    return text, attachments, "max_llm_reply"
