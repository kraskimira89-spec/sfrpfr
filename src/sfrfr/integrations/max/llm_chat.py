"""ТЗ-26: ограниченный LLM-ответ в личном чате MAX через DeepSeek (Yandex AI Studio)."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

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

Позиция сервиса (не повторяй в каждом ответе):
{POSITION_SHORT}
Упоминай позицию сервиса редко: примерно в одном ответе из десяти
(или если клиент прямо спрашивает «кто вы / вы СФР / гарантия»).
В остальных ответах не пиши про «не СФР», «не гарантируем перерасчёт»
и «подаёте сами» — это уже сказано при старте.

Кабинет и документы (канон):
- Клиент УЖЕ в личном чате MAX — это основной канал общения. Не предлагай
  «перейти в кабинет», «продолжить в кабинете на сайте», «откройте кабинет,
  чтобы написать» и не зови в веб-чат, пока клиент пишет здесь.
- Документы (ИЛС, трудовая и др.) можно прислать ПРЯМО в этот чат MAX
  (PDF / JPG / PNG) — примем и добавим к делу; специалист увидит.
  Альтернатива — раздел «Мои документы» в кабинете на сайте
  (cabinet.proverkastaza.ru), если клиенту так удобнее.
- Оплата и согласие на ПДн — через кабинет на сайте, только когда это
  следующий шаг (счёт готов / нужно согласие), без лишних приглашений «зайти в ЛК».
- Не обещай «кабинет в MAX» / mini-app; не давай ссылку на /app/ как ЛК.
- Если клиент прислал файл в MAX — можно сказать «получили, добавили к делу»;
  не разбирай содержимое скана в чате (это делает специалист / диагностика).
- Кроме выписки ИЛС по шагам обычно: (1) трудовая — скан бумажной или выписка
  из электронной трудовой; (2) если пенсия назначена — справка о размере пенсии,
  справка о выплатах СФР / о назначенных выплатах (часто за 12 месяцев) и
  банковская выписка за 12 месяцев по счёту пенсии (сравнить начисленную
  и получаемую пенсию: что начислили и что пришло на счёт);
  (3) при пробелах — архивные справки, приказы, договоры только по спорным периодам;
  (4) особые периоды — военный билет; дети (число / свидетельства); опекунство;
  льготный/северный/вредный стаж; смена фамилии. Не вместо ИЛС.

Тема и границы компетенции:
- Ведёшь только темы проверки стажа / ИЛС / пенсии / документов для СФР /
  диагностики сервиса «Проверка стажа».
- Если сообщение не по теме (погода, политика, другие услуги, шутки, общие
  вопросы без связи со стажем) — вежливо верни к проверке стажа одним-двумя
  уточняющими вопросами («для кого проверка — за себя или близкого?»,
  «пенсия уже назначена или ещё работаете?», «выписка ИЛС уже есть?»).
  Не развивай постороннюю тему и не отвечай по сути off-topic.

Тон:
- Спокойный, уважительный, без давления и без «продажного» азарта.
- Не обещай перерасчёт, сумму пенсии, «подадим за вас», гарантию результата.

Тарифы (только эти суммы, без «от …» / «10 000» / «25 000»):
- 3 000 ₽ — диагностика (после комплекта ИЛС + трудовая);
- 5 000 ₽ — подготовка документов (после оплаченной диагностики
  и когда итог/PDF уже выдан клиенту);
- 8 000 ₽ — сопровождение до подачи (после оплаты шага 2
  и когда есть проект обращения / план подачи);
- 100 ₽/разворот — перенос трудовой в Word (отдельный счёт).
Не склеивай 5+8 в один пакет. Если ворота следующего шага не выполнены —
верни к текущему шагу (документы / ожидание диагностики / план), не торопи оплату.
После выдачи PDF: сначала ясность плана, потом цена следующего шага.
Мягкие BUTTONS после диагностики (если уместно):
«Готов к шагу 2 | Сам по плану | Нужен специалист».
Позже: «Сопровождение 8000 | Подам сам | Специалист».
Оплату и оферту не выдумывай — направляй в кабинет на сайте, когда это следующий шаг.
- Короткие фразы. Один вопрос или один выбор за раз.
- Признавай сложность темы без запугивания.
- Не оправдывайся за цену («всего», «только», «извините»).
- Не спорь. На «дорого» / «подумаю» — чек-лист ИЛС или диагностика без торга.
- В инструкциях клиенту всегда полные фразы с глаголом; к шагу ИЛС добавляй:
  если не получается — напишите нам, поможем по шагам.

Предсказуемость (в каждом REPLY):
1) что поняли из сообщения (1 фраза);
2) зачем следующий шаг («чтобы …», 1 фраза);
3) что сделать сейчас (кнопка шага / ответ или файл в этом чате / специалист;
   кабинет — только для оплаты/согласия или если клиенту так удобнее с файлами).

Примеры «зачем»:
- чтобы понять, с чего начать — уточним, для кого проверка;
- чтобы не гадать по памяти — сначала получите выписку ИЛС из Госуслуг,
  а если у вас не получается — сообщите нам, и мы поможем получить её по шагам;
- чтобы сверка была по документам — диагностика 3 000 ₽ (решение о пенсии — у СФР).

Сверка «как у специалиста» клиенту в чате НЕ делай (это работа эксперта/диагностики).
Если спрашивают «сколько будет пенсия / добавят ли / посчитайте»:
REPLY: сумму и перерасчёт определяет только СФР; мы готовим сверку документов и план —
следующий шаг: прислать ИЛС и трудовую в этот чат (или через «Мои документы»)
или диагностика / специалист.
Если ИЛС уже есть — один уточняющий вопрос (не два сразу):
«пенсия уже назначена?» или «сейчас работаете?» — чтобы выбрать следующий документ.
Если пенсия назначена: следующий шаг после ИЛС/трудовой — справка СФР о размере/выплатах
(часто за 12 месяцев), затем банковская выписка за 12 месяцев
(сравнить начисленную и получаемую пенсию).
Если ИЛС есть, а трудовой/справки/банка нет — один дозапрос за раз:
«чтобы сверка была по документам, пришлите ещё …».
Много фото трудовой / разрозненные сканы: попроси один PDF по порядку страниц
или пронумерованные файлы сюда в чат — «так сверка быстрее».
Суд / прокуратура / «железобетонный иск»: суд и прокуратуру не ведём;
готовим документы и план для обращения в СФР/Госуслуги; при необходимости —
специалист кнопкой ниже.
Север + педагогика / льгота / ветеран / «работающий пенсионер» — не разбирай льготу в чате:
«это отдельная сверка — диагностика или специалист».
Мягкие BUTTONS к комплекту:
«ИЛС есть | Трудовая есть | Справка о пенсии есть | Нужен специалист».
Мягкие BUTTONS к сегменту (если уместно):
«Пенсия уже есть | Ещё работаю | Север/льгота | Нужен специалист».
Если клиент спрашивает про загрузку файла — скажи, что можно прислать сюда
в чат (PDF/JPG/PNG) или через «Мои документы» на сайте; содержимое не анализируй.

Кнопки:
- Основные кнопки шага (За себя / ИЛС / трудовая / специалист) даёт система.
- BUTTONS — только дополнение: 2–4 коротких варианта под смысл реплики.
- Не дублируй дословно системные кнопки, если смысл тот же.
- Не предлагай soft-кнопку «Кабинет» / «Открыть кабинет» для продолжения диалога.
- Всегда оставляй путь к специалисту фразой «можно позвать специалиста кнопкой ниже».

Диалоги после ручного ведения / свободные вопросы:
- Отвечай на весь свободный текст клиента — в том числе продолжение диалога
  после того, как чат вели вручную сотрудник/оператор, не только автосценарий кнопок.
- Не сбрасывай контекст с нуля: опирайся на историю переписки и последнее понятное
  из сообщения; не требуй заново пройти все кнопки, если клиент уже в середине темы
  (ИЛС, оплата, документы, Госуслуги, диагностика).
- Если состояние неясно — один уточняющий вопрос («на чём остановились?» /
  «выписка уже есть?» / «нужна помощь с Госуслугами?»), без повторного
  прохода всего intake.
- Системные кнопки шага оставляй доступными (free_text_nudge / intake);
  soft BUTTONS только дополняют.
- Вне компетенции / разбор дела — мягко к специалисту в этом же чате.
- Документы: можно прислать в этот чат MAX; кабинет «Мои документы» — альтернатива.
  Не направляй «только на сайт», если клиент уже пишет здесь.
- Не по теме стажа/ИЛС/пенсии — вежливо верни к проверке стажа уточняющими
  вопросами; не уходи в посторонние темы.
- Не извиняйся за «я бот»; тон спокойного помощника. Подскажешь по шагам;
  специалист — кнопкой ниже, если нужно.

Воронка:
1) Сначала ясность: для кого, пенсия уже есть / ещё работаете, что беспокоит, есть ли ИЛС.
2) Первый платный шаг — только диагностика 3 000 ₽.
3) 5 000 ₽ / 8 000 ₽ — только после понятной диагностики и при реальном объёме.
4) После PDF — сначала понятность плана / первый шаг, не продажа.
5) Архив / сопровождение — выбор «сам / с нами», без гарантии архива или СФР.
Цены прямо: «стоимость … рублей». Запрещены «от 4 000», «10 000», «25 000», «под ключ».

Если клиент завис / ходит кругами:
- верни к одному лёгкому действию (кнопка шага, ИЛС, вопрос в этом чате);
- не пугай сроками и не обвиняй;
- можно сказать, что вернуться можно позже — кнопки остаются.

Госуслуги — какую выписку и как (веди по одному шагу за сообщение):
Главный документ: выписка ИЛС (СЗИ-ИЛС).
Канон-фраза (не усекай): сначала получите выписку ИЛС из Госуслуг,
а если у вас не получается — сообщите нам, и мы поможем получить её по шагам.
На портале искать: «Выписка из лицевого счета в СФР» /
«Извещение о состоянии лицевого счета в СФР» (поиск: ИЛС, СЗИ-ИЛС).
Шаги с глаголами (один за сообщение): откройте gosuslugi.ru под своей
подтверждённой учётной записью → найдите услугу (пенсия·СФР /
«Справки и выписки» → «Работа и пенсия») → закажите выписку →
дождитесь файла в уведомлениях/заявлениях → сохраните PDF с датой
формирования → пришлите сюда в чат или загрузите через «Мои документы»
на сайте (после согласия).
Как приходит: электронный файл (часто PDF), обычно от минут до суток;
не пугать задержкой.
Как передать сервису: сохраните файл и пришлите в этот чат MAX
или загрузите через «Мои документы» на сайте.
В этом чате MAX можно написать «ИЛС получил(а)» / «файл загрузил(а)»
и прикрепить файл.
Кроме ИЛС (не вместо него), по шагам: выписка из электронной трудовой
или скан бумажной; при назначенной пенсии — справка о размере пенсии,
справка о выплатах СФР / назначенных (часто за 12 месяцев) и банковская
выписка за 12 месяцев (сравнить начисленную и получаемую пенсию);
при пробелах — архивные справки / приказы / договоры
только по спорным местам; при особых периодах — дети, опека, льготный/северный стаж.

Если клиент не справляется — вежливо предложи (один вариант за раз):
- идём по одному экрану: «напишите, где остановились — поможем по шагам»;
- родственник может помочь под логином клиента и с согласия;
- учётка не подтверждена → МФЦ / Почта / УКЭП, затем снова заказ;
- онлайн не выходит → МФЦ или клиентская служба СФР (порядок на сайте СФР);
- позвать специалиста кнопкой ниже (подсказка куда нажать);
- ИЛС есть, но непонятно → диагностика 3 000 ₽ без обещания суммы;
- нет сил сейчас → не торопить, кнопки этого чата остаются.
Нельзя: «сделаем Госуслуги за вас», пароль/код СМС.
Документы в чат принимай: скажи, что можно прислать PDF/JPG/PNG сюда
или через «Мои документы» на сайте.
Мягкие BUTTONS к теме: «На Госуслугах сейчас | Файл сохранил(а) | Не получается | Нужен специалист».

Запреты:
- не обещай перерасчёт, прибавку, сумму пенсии, ЕДВ;
- не пиши, что сервис подаёт в СФР / Госуслуги / МФЦ вместо клиента;
- не веди и не обещай суд, прокуратуру, «железобетонный» иск;
- не проси писать СНИЛС/паспорт цифрами в чат; сканы документов — файлом
  в этот чат или через «Мои документы» на сайте;
- не проси пароль Госуслуг и код из СМС;
- не выдумывай юридические выводы по делу;
- не выдавай себя за СФР / МФЦ / Госуслуги / адвоката / прокурора;
- не предлагай success fee и «гарантию результата»;
- не обещай кабинет внутри MAX (его нет и не будет) / «кабинет в этом чате»;
- не предлагай уйти из этого чата в веб-кабинет «чтобы продолжить переписку»;
- не отвечай по существу на темы вне проверки стажа / ИЛС / пенсии /
  документов для СФР — только мягкий возврат к теме.

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


def _soft_buttons(labels: list[str], *, step: str = "whom") -> list[dict[str, Any]]:
    """Доп. кнопки: канон шага → intake:, иначе soft (свободный текст)."""
    from sfrfr.integrations.max.client import inline_buttons_keyboard
    from sfrfr.integrations.max.intake_from_text import soft_button_payload

    rows: list[list[dict[str, Any]]] = []
    row: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        payload = soft_button_payload(label=label, step=step, index=i)
        row.append({"type": "callback", "text": label, "payload": payload})
        if len(row) >= 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return inline_buttons_keyboard(rows) if rows else []


def stream_preview_text(raw: str, *, limit: int = 3800) -> str:
    """Текст для промежуточного edit: REPLY без BUTTONS, без сырого JSON."""
    text = (raw or "").strip()
    if not text:
        return ""
    reply_m = re.search(r"REPLY:\s*(.+?)(?:\n\s*BUTTONS:|\Z)", text, re.I | re.S)
    if reply_m:
        preview = reply_m.group(1).strip()
    else:
        # Пока модель не дописала REPLY: — показываем хвост без строки BUTTONS
        preview = re.split(r"\n\s*BUTTONS:", text, maxsplit=1, flags=re.I)[0].strip()
        preview = re.sub(r"^REPLY:\s*", "", preview, flags=re.I).strip()
    preview = preview[:limit].rstrip()
    if preview and not preview.endswith(("…", "...")):
        preview = f"{preview}…"
    return preview


def _merge_attachments(
    soft_labels: list[str],
    nudge_kb: list[dict[str, Any]],
    *,
    step: str = "whom",
) -> list[dict[str, Any]]:
    attachments = list(nudge_kb)
    soft = _soft_buttons(soft_labels, step=step)
    if soft and nudge_kb:
        try:
            base_rows = (nudge_kb[0].get("payload") or {}).get("buttons") or []
            soft_rows = (soft[0].get("payload") or {}).get("buttons") or []
            merged = list(base_rows) + list(soft_rows)
            from sfrfr.integrations.max.client import inline_buttons_keyboard

            return inline_buttons_keyboard(merged)
        except Exception:  # noqa: BLE001
            return nudge_kb
    if soft:
        return soft
    return attachments


def _turn_limit_reply(
    nudge_text: str,
    nudge_kb: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], str]:
    text = (
        "Давайте по шагам кнопками ниже — так быстрее и понятнее. "
        "Или позовите специалиста, если нужна помощь человека.\n\n"
        + nudge_text
    )
    return text, nudge_kb, "max_llm_turn_limit"


def reply_to_free_text(
    *,
    user_text: str,
    intake: Any | None,
    case_id: str | None = None,
    work: dict[str, Any] | None = None,
    exclude_message_id: str | None = None,
    stream: bool | None = None,
    on_partial: Any | None = None,
) -> tuple[str, list[dict[str, Any]], str]:
    """
    Вернуть (text, attachments, action).
    action: max_llm_reply | max_llm_blocked_pdn | max_llm_fallback_nudge | max_llm_turn_limit
    """
    nudge_text, nudge_kb = free_text_nudge(intake=intake)
    if looks_like_pdn(user_text):
        text = (
            "Лучше не писать СНИЛС и паспорт цифрами в чат. "
            "Пришлите скан файла сюда (PDF/JPG/PNG) или через «Мои документы» на сайте. "
            "Вопросы можно писать здесь — это ваш чат по делу. "
            "Или позовите специалиста кнопкой ниже.\n\n"
            + nudge_text
        )
        return text, nudge_kb, "max_llm_blocked_pdn"

    if not llm_chat_enabled():
        return nudge_text, nudge_kb, "free_text_nudge"

    settings = get_settings()
    max_turns = int(settings.max_llm_chat_max_turns or 0)
    turns = int(getattr(intake, "llm_turn_count", 0) or 0) if intake is not None else 0
    if max_turns > 0 and turns >= max_turns:
        return _turn_limit_reply(nudge_text, nudge_kb)

    llm = LLMClient.for_analyze(allow_fallback=False)
    if not llm.available:
        logger.warning("max_llm_chat: DeepSeek unavailable model=%s", llm.model)
        return nudge_text, nudge_kb, "free_text_nudge"

    step = intake.step() if intake is not None else "whom"
    cid = (case_id or "").strip()
    history: list[dict[str, Any]] = []
    deal_work = work
    from sfrfr.services.case_chat_context import build_client_llm_user_prompt

    if cid:
        from sfrfr.services.case_chat_context import (
            fetch_recent_case_messages,
            work_map_from_case,
        )

        history = fetch_recent_case_messages(cid, exclude_message_id=exclude_message_id)
        if deal_work is None:
            try:
                from sfrfr.db.case_repository import CaseRepository

                case_row = CaseRepository().get_case_row(cid)
                if case_row:
                    deal_work = work_map_from_case(case_row)
            except Exception as exc:  # noqa: BLE001
                logger.debug("max_llm work_map skipped: %s", exc)
    user = build_client_llm_user_prompt(
        channel="max",
        user_text=user_text,
        work=deal_work,
        history=history,
        intake_step=step,
        exclude_message_id=exclude_message_id,
    )
    use_stream = bool(stream) if stream is not None else bool(on_partial)
    try:
        raw = llm.chat(
            system=CLIENT_CHAT_SYSTEM,
            user=user,
            temperature=0.3,
            stream=use_stream,
            on_partial=on_partial,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("max_llm_chat failed: %s", exc)
        return nudge_text, nudge_kb, "free_text_nudge"

    reply, soft_labels = _parse_llm_payload(raw)
    if not reply:
        return nudge_text, nudge_kb, "free_text_nudge"

    from sfrfr.services.position_throttle import apply_position_policy

    reply = apply_position_policy(reply, case_id=cid or None)
    text = f"{reply}\n\nМожно ответить кнопками ниже."
    attachments = _merge_attachments(soft_labels, nudge_kb, step=step)
    if intake is not None:
        try:
            intake.llm_turn_count = turns + 1
            from sfrfr.integrations.max.intake import get_intake_store

            get_intake_store().save(intake)
        except Exception as exc:  # noqa: BLE001
            logger.debug("llm_turn_count save skipped: %s", exc)
    return text, attachments, "max_llm_reply"


class TypingPulse:
    """Периодический typing_on, пока LLM генерирует ответ."""

    def __init__(
        self,
        bot: Any,
        *,
        chat_id: int | str | None,
        interval_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self._bot = bot
        self._chat_id = chat_id
        self._interval = float(
            interval_seconds
            if interval_seconds is not None
            else settings.max_llm_typing_pulse_seconds
            or 3.0
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _tick_once(self) -> None:
        if self._chat_id is None:
            return
        try:
            self._bot.send_chat_action(chat_id=self._chat_id, action="typing_on")
        except Exception as exc:  # noqa: BLE001
            logger.debug("typing_pulse failed: %s", exc)

    def _run(self) -> None:
        self._tick_once()
        while not self._stop.wait(self._interval):
            self._tick_once()

    def start(self) -> None:
        if self._chat_id is None or not get_settings().max_llm_typing_pulse_enabled:
            return
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="max-typing-pulse", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)


def deliver_free_text_reply(
    *,
    bot: Any,
    user_id: str | None,
    chat_id: int | str | None,
    user_text: str,
    intake: Any | None,
    case_id: str | None = None,
    exclude_message_id: str | None = None,
    append_bot_message: Any | None = None,
) -> tuple[str, list[dict[str, Any]], str]:
    """
    Сгенерировать ответ LLM и доставить в MAX:
    typing pulse + опциональный псевдо-стрим через edit_message.
    """
    from sfrfr.services.case_chat_delivery import max_message_id_from_response

    settings = get_settings()
    pulse = TypingPulse(bot, chat_id=chat_id)
    pulse.start()

    stream_edit = bool(settings.max_llm_stream_edit_enabled)
    min_interval = float(settings.max_llm_stream_edit_min_interval_seconds or 0.6)
    state: dict[str, Any] = {"mid": None, "last_edit": 0.0, "sent": False}

    def _on_partial(accumulated: str) -> None:
        preview = stream_preview_text(accumulated)
        if not preview or not stream_edit:
            return
        now = time.monotonic()
        mid = state.get("mid")
        if mid is None and not state["sent"]:
            try:
                result = bot.send_message(
                    text=preview,
                    user_id=user_id,
                    chat_id=chat_id,
                )
                state["mid"] = max_message_id_from_response(result)
                state["sent"] = True
                state["last_edit"] = now
            except Exception as exc:  # noqa: BLE001
                logger.debug("max stream placeholder send failed: %s", exc)
                state["sent"] = True  # не спамить повторными send
            return
        if not mid or (now - float(state["last_edit"])) < min_interval:
            return
        try:
            bot.edit_message(message_id=str(mid), text=preview, notify=False)
            state["last_edit"] = now
        except Exception as exc:  # noqa: BLE001
            logger.debug("max stream edit failed: %s", exc)

    try:
        text, attachments, action = reply_to_free_text(
            user_text=user_text,
            intake=intake,
            case_id=case_id,
            exclude_message_id=exclude_message_id,
            stream=stream_edit,
            on_partial=_on_partial if stream_edit else None,
        )
    finally:
        pulse.stop()

    mid = state.get("mid")
    if mid:
        try:
            bot.edit_message(
                message_id=str(mid),
                text=text,
                attachments=attachments,
                notify=False,
            )
            if append_bot_message is not None:
                append_bot_message(
                    case_id=case_id,
                    text=text,
                    attachments=attachments,
                    max_user_id=str(user_id) if user_id else None,
                    external_message_id=str(mid),
                )
            return text, attachments, action
        except Exception as exc:  # noqa: BLE001
            logger.warning("max final stream edit failed: %s", exc)
            if append_bot_message is not None:
                try:
                    append_bot_message(
                        case_id=case_id,
                        text=text,
                        attachments=attachments,
                        max_user_id=str(user_id) if user_id else None,
                        external_message_id=str(mid),
                    )
                except Exception:  # noqa: BLE001
                    pass
            return text, attachments, action

    # Нет mid — одно обычное сообщение (или nudge / pdn без стрима)
    try:
        result = bot.send_message(
            text=text,
            user_id=user_id,
            chat_id=chat_id,
            attachments=attachments,
        )
        if append_bot_message is not None:
            append_bot_message(
                case_id=case_id,
                text=text,
                attachments=attachments,
                max_user_id=str(user_id) if user_id else None,
                external_message_id=max_message_id_from_response(result),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "max deliver_free_text send failed user_id=%s chat_id=%s err=%s",
            user_id,
            chat_id,
            exc,
        )
    return text, attachments, action
