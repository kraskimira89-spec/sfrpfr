"""Понятная карта дела для клиентского кабинета (без технических статусов)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

from sfrfr.services.public_tariffs import PUBLIC_TARIFFS, staff_package_label

ILS_HOWTO_URL = "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/"
OFFER_URL = "https://proverkastaza.ru/oferta/"

_STATUS = {
    "consent": (
        "Нужно согласие",
        "Подтвердите согласие на обработку персональных данных, чтобы загрузить файлы.",
    ),
    "waiting_docs": (
        "Ждём документы",
        "Нужна выписка ИЛС и трудовая книжка / сведения о работе",
    ),
    "docs_review": (
        "Документы на проверке",
        "Проверяем, всё ли читается и хватает ли файлов",
    ),
    "diagnosis": (
        "Проверка в работе",
        "Специалист сопоставляет предоставленные документы",
    ),
    "need_info": (
        "Нужны уточнения",
        "Нам нужен ещё один документ или более читаемый файл",
    ),
    "result_ready": (
        "Результат готов",
        "Откройте краткий итог и PDF-отчёт",
    ),
    "your_move": (
        "Ожидаем вашего действия",
        "Посмотрите план и выберите следующий шаг",
    ),
    "done": (
        "Завершено",
        "Результат выдан. Вы можете вернуться к нему в любое время",
    ),
}

_DOC_SLOTS: tuple[dict[str, Any], ...] = (
    {
        "key": "ils",
        "title": "Выписка ИЛС",
        "need": "required",
        "need_label": "Обязательно",
        "doc_type": "ils",
    },
    {
        "key": "labor",
        "title": "Трудовая книжка / сведения о трудовой деятельности",
        "need": "required",
        "need_label": "Обязательно",
        "doc_type": "workbook",
    },
    {
        "key": "passport",
        "title": "Паспорт",
        "need": "optional",
        "need_label": "При необходимости",
        "doc_type": "passport",
    },
    {
        "key": "sfr_size",
        "title": "Справка о размере пенсии",
        "need": "if_pension",
        "need_label": "Если пенсия уже назначена",
        "doc_type": "pension_size",
    },
    {
        "key": "sfr_pay",
        "title": "Справка о выплатах СФР за 12 месяцев",
        "need": "if_pension",
        "need_label": "Если пенсия уже назначена",
        "doc_type": "sfr_payments",
    },
    {
        "key": "bank",
        "title": "Дополнительный финансовый документ (только по запросу)",
        "need": "staff_requested",
        "need_label": "Только по запросу специалиста",
        "doc_type": "bank_statement",
    },
    {
        "key": "archive",
        "title": "Архивные справки с мест работы",
        "need": "optional",
        "need_label": "При наличии",
        "doc_type": "archive",
    },
    {
        "key": "extra",
        "title": "Договоры, приказы, ведомости",
        "need": "optional",
        "need_label": "При наличии",
        "doc_type": None,
    },
    {
        "key": "military",
        "title": "Военный билет",
        "need": "optional",
        "need_label": "При наличии",
        "doc_type": "military",
    },
    {
        "key": "children",
        "title": "Свидетельства о рождении детей / уход",
        "need": "optional",
        "need_label": "При наличии",
        "doc_type": "children",
    },
    {
        "key": "marriage",
        "title": "Свидетельство о браке (смена фамилии)",
        "need": "optional",
        "need_label": "При наличии",
        "doc_type": "marriage",
    },
    {
        "key": "education",
        "title": "Документы об образовании",
        "need": "optional",
        "need_label": "При необходимости",
        "doc_type": "education",
    },
    {
        "key": "north",
        "title": "Льготный, северный или вредный стаж",
        "need": "optional",
        "need_label": "При наличии",
        "doc_type": "north",
    },
    {
        "key": "sfr",
        "title": "Ответ или решение СФР",
        "need": "optional",
        "need_label": "Если уже есть",
        "doc_type": "sfr_decision",
    },
    {
        "key": "signed_application",
        "title": "Подписанное заявление в СФР",
        "need": "conditional",
        "need_label": "PDF или DOCX по ситуации",
        "doc_type": "client_signed_application",
    },
    {
        "key": "signed_appeal",
        "title": "Подписанное обращение / жалоба",
        "need": "conditional",
        "need_label": "PDF или DOCX по ситуации",
        "doc_type": "client_signed_appeal",
    },
)

_STATUS_LABEL = {
    "missing": "Нужно загрузить",
    "awaiting": "Загружен — ожидает проверки",
    "accepted": "Принят специалистом",
    "reupload": "Нужно загрузить повторно",
    "not_needed": "Не требуется сейчас",
}

_CLIENT_ORDER_STATUS = {
    "paid": "Оплата получена",
    "succeeded": "Оплата получена",
    "pending": "Ожидает оплаты",
    "awaiting_payment": "Ожидает оплаты",
    "pending_payment": "Ожидает оплаты",
    "invoice_ready": "Ожидает оплаты",
    "invoice_sent": "Ожидает оплаты",
    "draft": "Ожидает оплаты",
    "cancelled": "Отменено",
    "canceled": "Отменено",
    "refund": "Возврат",
}

_SKIP_DOC_TYPES = {"diagnosis_report", "payment_receipt"}
_MONTHS_RU = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
try:
    _MSK: tzinfo = ZoneInfo("Europe/Moscow")
except Exception:  # noqa: BLE001
    _MSK = timezone(timedelta(hours=3))


def _lower(value: object) -> str:
    return str(value or "").strip().lower()


def _doc_blob(doc: dict[str, Any]) -> str:
    return " ".join(
        _lower(doc.get(key))
        for key in ("doc_type", "doc_type_label", "filename", "inner_title", "storage_path")
    )


def _is_ils(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    return _lower(doc.get("doc_type")) == "ils" or "илс" in blob or "сзи" in blob


def _is_labor(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return (
        dtype in {"workbook", "labor"} or "труд" in blob or "книжк" in blob or "employment" in blob
    )


def _is_sfr(doc: dict[str, Any]) -> bool:
    return _lower(doc.get("doc_type")) == "sfr_decision" or "решени" in _doc_blob(doc)


def _is_passport(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    return _lower(doc.get("doc_type")) == "passport" or "паспорт" in blob


def _is_sfr_size(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return (
        dtype in {"pension_size", "sfr_size"} or "размер пенсии" in blob or "размере пенсии" in blob
    )


def _is_sfr_pay(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return dtype in {"sfr_payments", "sfr_payout"} or "выплат" in blob


def _is_bank(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return dtype in {"bank_statement", "bank"} or "банк" in blob


def _is_archive(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    return _lower(doc.get("doc_type")) == "archive" or "архив" in blob


def _is_military(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    return _lower(doc.get("doc_type")) == "military" or "военн" in blob


def _is_children(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return dtype in {"children", "birth"} or "рождении" in blob or "уход до" in blob


def _is_marriage(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    return _lower(doc.get("doc_type")) == "marriage" or "брак" in blob


def _is_education(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return dtype == "education" or "образован" in blob or "диплом" in blob or "аттестат" in blob


def _is_guardianship(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return dtype in {"guardianship", "adoption"} or "опек" in blob or "попечител" in blob


def _is_north(doc: dict[str, Any]) -> bool:
    blob = _doc_blob(doc)
    dtype = _lower(doc.get("doc_type"))
    return (
        dtype in {"north", "preferential"} or "северн" in blob or "льготн" in blob or "соут" in blob
    )


def _is_signed_application(doc: dict[str, Any]) -> bool:
    return _lower(doc.get("doc_type")) == "client_signed_application"


def _is_signed_appeal(doc: dict[str, Any]) -> bool:
    return _lower(doc.get("doc_type")) == "client_signed_appeal"


def _is_diagnosis(doc: dict[str, Any]) -> bool:
    return "diagnosis" in _lower(doc.get("doc_type"))


def _client_docs(docs: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in docs or []:
        if isinstance(item, dict) and _lower(item.get("doc_type")) not in _SKIP_DOC_TYPES:
            out.append(item)
    return out


def _checklist_for(items: list[Any], *needles: str) -> dict[str, Any] | None:
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = _lower(item.get("title"))
        if any(n in title for n in needles):
            return item
    return None


def _needs_reupload(item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    blob = f"{item.get('status')} {item.get('note')}"
    return any(w in _lower(blob) for w in ("повтор", "нечита", "reupload", "retry"))


def _slot_status(
    *,
    docs: list[dict[str, Any]],
    checklist: dict[str, Any] | None,
) -> str:
    if _needs_reupload(checklist):
        return "reupload"
    if checklist and _lower(checklist.get("status")) == "done":
        return "accepted"
    if docs:
        return "awaiting"
    return "missing"


def _format_added(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt = dt.astimezone(_MSK)
        return f"{dt.day} {_MONTHS_RU[dt.month]}, {dt:%H:%M}"
    except ValueError:
        return None


def _match_docs(docs: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    checks = {
        "ils": _is_ils,
        "labor": _is_labor,
        "sfr": _is_sfr,
        "passport": _is_passport,
        "sfr_size": _is_sfr_size,
        "sfr_pay": _is_sfr_pay,
        "bank": _is_bank,
        "archive": _is_archive,
        "military": _is_military,
        "children": _is_children,
        "marriage": _is_marriage,
        "education": _is_education,
        "north": _is_north,
        "guardianship": _is_guardianship,
        "signed_application": _is_signed_application,
        "signed_appeal": _is_signed_appeal,
    }
    check = checks.get(key)
    if check:
        return [d for d in docs if check(d)]
    claimed = checks.values()
    return [d for d in docs if not any(fn(d) for fn in claimed)]


def _slot_row(
    slot: dict[str, Any],
    *,
    matched: list[dict[str, Any]],
    checklist: dict[str, Any] | None,
    key_override: str | None = None,
    title_override: str | None = None,
) -> dict[str, Any]:
    latest = matched[0] if matched else None
    status = _slot_status(docs=matched, checklist=checklist)
    return {
        "key": key_override or str(slot["key"]),
        "title": title_override or slot["title"],
        "need": slot["need"],
        "need_label": slot["need_label"],
        "doc_type": slot["doc_type"],
        "status": status,
        "status_label": _STATUS_LABEL[status],
        "added_at": _format_added(latest.get("created_at") if latest else None),
        "document_id": str(latest["id"]) if latest and latest.get("id") else None,
        "can_replace": status in {"awaiting", "reupload"} and bool(latest),
        "can_delete": status in {"awaiting", "reupload"} and bool(latest),
    }


def document_slots(
    documents: list[Any] | None,
    checklist_items: list[Any] | None,
    *,
    scenario_rows: list[Any] | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    from sfrfr.services.document_requirements import (
        GUARDIANSHIP_SLOT,
        GUARDIANSHIP_SLOT_KEY,
        active_scenario_codes,
        slot_visible,
        staff_requested_codes,
    )

    active = active_scenario_codes(scenario_rows)
    staff_codes = staff_requested_codes(checklist_items)
    docs = _client_docs(list(documents or []))
    items = [i for i in (checklist_items or []) if isinstance(i, dict)]
    used: set[str] = set()
    typed: dict[str, list[dict[str, Any]]] = {}
    for slot in _DOC_SLOTS:
        key = str(slot["key"])
        if key == "extra":
            continue
        matched = [d for d in _match_docs(docs, key) if str(d.get("id")) not in used]
        for row in matched:
            used.add(str(row.get("id")))
        typed[key] = matched
    leftover = [d for d in docs if str(d.get("id")) not in used]
    leftover.sort(key=lambda d: str(d.get("created_at") or ""))
    for slot in _DOC_SLOTS:
        key = str(slot["key"])
        if slot["need"] == "required" and not typed.get(key) and leftover:
            taken = leftover.pop(0)
            typed[key] = [taken]
            used.add(str(taken.get("id")))
    extra_docs = leftover
    extra_slot = next(s for s in _DOC_SLOTS if s["key"] == "extra")
    slot_defs: list[dict[str, Any]] = list(_DOC_SLOTS)
    if GUARDIANSHIP_SLOT_KEY not in {str(s["key"]) for s in slot_defs}:
        slot_defs.insert(-1, GUARDIANSHIP_SLOT)
    rows: list[dict[str, Any]] = []
    for slot in slot_defs:
        key = str(slot["key"])
        if key == "extra":
            matched = extra_docs[:1]
            check = None
        elif key == "ils":
            matched = typed.get(key) or []
            check = _checklist_for(items, "илс", "сзи")
        elif key == "labor":
            matched = typed.get(key) or []
            check = _checklist_for(items, "труд", "стаж")
        elif key == GUARDIANSHIP_SLOT_KEY:
            matched = typed.get(key) or []
            check = None
        else:
            matched = typed.get(key) or []
            check = None
        if not slot_visible(
            key,
            active_scenarios=active,
            staff_codes=staff_codes,
            has_uploaded=bool(matched),
        ):
            continue
        rows.append(_slot_row(slot, matched=matched, checklist=check))
    for extra in extra_docs[1:]:
        rows.append(
            _slot_row(
                extra_slot,
                matched=[extra],
                checklist=None,
                key_override=f"file-{extra.get('id')}",
                title_override="Дополнительный документ",
            )
        )
    required = [r for r in rows if r["need"] == "required"]
    uploaded = sum(1 for r in required if r["status"] in {"awaiting", "accepted"})
    return rows, uploaded, len(required)


def _order_view(orders: list[Any] | None) -> dict[str, Any]:
    rows = [o for o in (orders or []) if isinstance(o, dict)]
    visible = [o for o in rows if not str(o.get("package_code") or "").upper().startswith("SF_")]
    if not visible:
        return {
            "state": "not_agreed",
            "title": "Диагностика сведений о стаже и пенсионных документах",
            "amount_rub": 3000,
            "status_label": "Услуга ещё не согласована",
            "can_pay": False,
            "order_id": None,
            "includes": [
                "сверка ИЛС, трудовой и предоставленных справок",
                "перечень возможных расхождений",
                "список недостающих документов",
                "понятный план дальнейших действий",
            ],
        }
    order = visible[0]
    code = str(order.get("package_code") or "DIAG").upper()
    tariff = next(
        (t for t in PUBLIC_TARIFFS if t.get("package_code") == code or t.get("code") == code), None
    )
    raw_status = _lower(order.get("status"))
    can_pay = raw_status in {
        "pending",
        "awaiting_payment",
        "pending_payment",
        "invoice_ready",
        "invoice_sent",
        "draft",
    }
    amount = order.get("amount_rub")
    try:
        amount_i = int(float(str(amount)))
    except (TypeError, ValueError):
        amount_i = int((tariff or {}).get("amount_rub") or 3000)
    includes_raw = str((tariff or {}).get("includes") or "")
    default_includes = [
        "сверка ИЛС, трудовой и предоставленных справок",
        "перечень возможных расхождений",
        "список недостающих документов",
        "понятный план дальнейших действий",
    ]
    includes = (
        default_includes
        if code == "DIAG"
        else ([p.strip() for p in includes_raw.split(";") if p.strip()] or default_includes)
    )
    return {
        "state": "paid"
        if raw_status in {"paid", "succeeded"}
        else ("pay" if can_pay else raw_status or "not_agreed"),
        "title": staff_package_label(code)
        if code != "DIAG"
        else "Диагностика сведений о стаже и пенсионных документах",
        "amount_rub": amount_i,
        "status_label": _CLIENT_ORDER_STATUS.get(raw_status, "Услуга ещё не согласована"),
        "can_pay": can_pay,
        "order_id": str(order["id"]) if order.get("id") else None,
        "includes": includes,
    }


def _stage_marks(
    *,
    consent: bool,
    required_ok: bool,
    status_key: str,
    result_ready: bool,
    done: bool,
) -> list[dict[str, Any]]:
    def mark(done_flag: bool, current: bool) -> str:
        if done_flag:
            return "done"
        if current:
            return "current"
        return "todo"

    s1 = consent
    s2 = required_ok
    s3 = status_key in {"diagnosis", "result_ready", "your_move", "done"}
    s4 = result_ready or done
    s5 = done
    if not s1:
        current_idx = 1
    elif not s2:
        current_idx = 2
    elif not s3:
        current_idx = 3
    elif not s4:
        current_idx = 4
    else:
        current_idx = 5
    titles = [
        (
            "1. Согласовали порядок работы",
            "Нужно согласие на обработку данных, затем можно загрузить файлы.",
        ),
        ("2. Собираем документы", "Нужны выписка ИЛС и трудовая книжка / сведения о стаже."),
        (
            "3. Специалист проверит документы",
            "Проверяем комплект: всё ли читается и хватает ли файлов.",
        ),
        (
            "4. Подготовим результат и план действий",
            "Специалист сопоставляет документы и готовит понятный итог.",
        ),
        (
            "5. Вы получите результат здесь и в MAX",
            "PDF и краткий итог появятся в кабинете. Решение по пенсии принимает СФР.",
        ),
    ]
    flags = [s1, s2, s3, s4, s5]
    out: list[dict[str, Any]] = []
    for i, ((title, hint), done_flag) in enumerate(zip(titles, flags, strict=True), start=1):
        out.append(
            {
                "n": i,
                "title": title,
                "hint": hint,
                "state": mark(done_flag, current_idx == i and not done_flag),
            }
        )
    return out


def build_client_work_map(
    *,
    pipeline_status: str | None,
    b2c_status: str | None,
    consent_accepted: bool,
    documents: list[Any] | None,
    checklist_items: list[Any] | None,
    orders: list[Any] | None = None,
    scenario_rows: list[Any] | None = None,
) -> dict[str, Any]:
    """Карта для клиента: статус, шаг, документы, заказ, результат."""
    pipeline = _lower(pipeline_status)
    b2c = _lower(b2c_status)
    docs = [d for d in (documents or []) if isinstance(d, dict)]
    slots, uploaded, required_total = document_slots(
        docs, checklist_items, scenario_rows=scenario_rows
    )
    required_ok = uploaded >= required_total and required_total > 0
    reupload = any(s["status"] == "reupload" for s in slots)
    diagnosis_docs = [d for d in docs if _is_diagnosis(d)]
    # PDF только если специалист выложил diagnosis_report
    result_published = bool(diagnosis_docs)
    done = pipeline == "completed" or b2c in {"closed", "package_delivered"}
    reviewing = required_ok and not result_published and pipeline not in {"intake", ""}
    if not consent_accepted:
        key = "consent"
    elif reupload or (required_ok is False and any(s["status"] == "reupload" for s in slots)):
        key = "need_info"
    elif not required_ok:
        key = "waiting_docs"
    elif result_published or done:
        key = "done" if done and result_published else "result_ready"
    elif reviewing or pipeline in {
        "documents_received",
        "ocr_done",
        "classified",
        "extracted",
        "human_review",
    }:
        key = "diagnosis" if pipeline not in {"intake", "documents_received"} else "docs_review"
    else:
        key = "docs_review"
    if key == "result_ready" and not result_published:
        key = "diagnosis"
    if done:
        key = "done"

    label, hint = _STATUS[key]
    missing_titles = [
        s["title"]
        for s in slots
        if s["need"] == "required" and s["status"] in {"missing", "reupload"}
    ]
    if key == "consent":
        now_need = "Подтвердить согласие на обработку персональных данных"
        cta_key, cta_label = "consent", "Даю согласие на обработку персональных данных"
    elif key in {"waiting_docs", "need_info"}:
        now_need = (
            "Загрузить " + " и ".join(missing_titles)
            if missing_titles
            else "Загрузить выписку ИЛС и трудовую книжку / сведения о стаже"
        )
        cta_key, cta_label = "upload", "Загрузить документы"
    elif key in {"docs_review", "diagnosis"}:
        now_need = "Сейчас от вас ничего не требуется"
        cta_key, cta_label = "wait", "Открыть чат MAX"
    elif key == "result_ready":
        now_need = "Открыть результат диагностики"
        cta_key, cta_label = "result", "Открыть результат"
    else:
        now_need = "Результат выдан. Можно вернуться к нему в любое время"
        cta_key, cta_label = "done", "Открыть результат"

    order = _order_view(orders)
    if order.get("can_pay") and required_ok and key in {"docs_review", "diagnosis", "waiting_docs"}:
        # Оплата не перебивает загрузку обязательных файлов
        if key != "waiting_docs":
            now_need = "Оплатить диагностику"
            cta_key, cta_label = "pay", "Оплатить безопасно"

    next_actions: list[str]
    if key == "consent":
        next_actions = [
            "Подтвердить согласие",
            "Загрузить выписку ИЛС",
            "Загрузить трудовую книжку или сведения о трудовой деятельности",
        ]
        sla_note = "После согласия можно загрузить документы в кабинете — не в чат."
    elif key in {"waiting_docs", "need_info"}:
        next_actions = [f"Загрузить: {t}" for t in missing_titles] or [
            "Загрузить выписку ИЛС",
            "Загрузить трудовую книжку или сведения о трудовой деятельности",
        ]
        next_actions.append("Дождаться подтверждения комплекта документов")
        sla_note = (
            "После загрузки мы проверим комплект и напишем вам в MAX. "
            "Срок проверки комплекта: до 1 рабочего дня."
        )
    elif key in {"docs_review", "diagnosis"}:
        next_actions = []
        sla_note = "Срок проверки комплекта: до 1 рабочего дня. Следующее сообщение придёт в MAX."
    elif key == "result_ready":
        next_actions = ["Открыть результат", "При необходимости задать вопрос в MAX"]
        sla_note = "Результат доступен в кабинете. Решение о пенсии принимает СФР."
    else:
        next_actions = ["Результат доступен в кабинете"]
        sla_note = "Результат доступен в кабинете. Решение о пенсии принимает СФР."

    return {
        "status_key": key,
        "status_label": label,
        "status_hint": hint,
        "now_need": now_need,
        "cta_key": cta_key,
        "cta_label": cta_label,
        "sla_note": sla_note,
        "required_uploaded": uploaded,
        "required_total": required_total,
        "consent_ok": bool(consent_accepted),
        "stages": _stage_marks(
            consent=bool(consent_accepted),
            required_ok=required_ok,
            status_key=key,
            result_ready=result_published,
            done=done,
        ),
        "documents": slots,
        "order": order,
        "result": {
            "ready": result_published,
            "document_id": str(diagnosis_docs[0]["id"])
            if diagnosis_docs and diagnosis_docs[0].get("id")
            else None,
            "added_at": _format_added(diagnosis_docs[0].get("created_at"))
            if diagnosis_docs
            else None,
        },
        "next_actions": next_actions,
        "ils_howto_url": ILS_HOWTO_URL,
        "offer_url": OFFER_URL,
    }
