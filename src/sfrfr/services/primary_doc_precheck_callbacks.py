"""Контракты callback precheck:* (MAX). Не создаёт заказ молча."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sfrfr.services.primary_doc_precheck_max import (
    answer_faq,
    resolve_stale_callback,
    sanitize_client_text,
)
from sfrfr.services.primary_doc_precheck_notify import build_precheck_max_message

PRECHECK_PREFIX = "precheck:"

# Действия, меняющие коммерческое/операционное состояние — нужен check_id.
MUTATING_SUBCODES = frozenset({"decline", "order", "ask_staff", "offer_info"})

# subcode → краткое описание контракта (для матрицы доказательств).
CALLBACK_CONTRACTS: dict[str, str] = {
    "summary": "Открыть резюме актуальной проверки",
    "explain": "Объяснить расхождение по сохранённой находке",
    "need_docs": "Что загрузить / зачем",
    "upload": "Маршрут досылки документов (промежуточный)",
    "offer_info": "Состав/цена при актуальных gates, без заказа",
    "order": "Handoff на существующий маршрут при актуальных gates",
    "decline": "Отказ от оффера; только после подтверждённой записи",
    "ask_staff": "Зарегистрировать передачу сотруднику",
    "status": "Статус незавершённой/актуальной проверки",
    "answer": "Уточнение (промежуточный FAQ)",
}


@dataclass
class PrecheckCallbackResult:
    ok: bool
    action: str
    text: str
    attachments: list[dict[str, Any]] | None = None
    detail: str | None = None


def parse_precheck_callback(payload: str) -> str | None:
    """Вернуть subcode (`summary`, `order`, …) или None."""
    parsed = parse_precheck_payload(payload)
    return parsed[0] if parsed else None


def parse_precheck_payload(payload: str) -> tuple[str, str | None] | None:
    """Разобрать `precheck:<sub>` или `precheck:<sub>:<check_id>`."""
    raw = (payload or "").strip()
    if not raw.startswith(PRECHECK_PREFIX):
        return None
    rest = raw[len(PRECHECK_PREFIX) :].strip()
    if not rest:
        return None
    if ":" in rest:
        sub, _, check = rest.partition(":")
        sub = sub.strip()
        check_id = check.strip() or None
        return (sub, check_id) if sub else None
    return rest, None


def _load_latest_check(case_id: str) -> dict[str, Any] | None:
    from sfrfr.services.staff_document_check import get_case_document_check

    return get_case_document_check(case_id)


def _job_belongs_to_case(check_id: str, case_id: str) -> bool:
    """Проверить, что check_id из payload принадлежит разрешённому делу."""
    cid = (check_id or "").strip()
    case = (case_id or "").strip()
    if not cid or not case:
        return False
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("staff_document_check_jobs")
            .select("id, case_id")
            .eq("id", cid)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return False
        return str(rows[0].get("case_id") or "") == case
    except Exception:  # noqa: BLE001
        # Недоступность БД ≠ «принадлежит»: блокируем мутации.
        return False


def _primary_from_check(check: dict[str, Any] | None) -> dict[str, Any]:
    if not check:
        return {}
    result_raw = check.get("result")
    result: dict[str, Any] = result_raw if isinstance(result_raw, dict) else {}
    primary = result.get("primary_precheck")
    if isinstance(primary, dict):
        return primary
    diag = result.get("diag_offer")
    diag_d = diag if isinstance(diag, dict) else {}
    return {
        "outcome": result.get("precheck_outcome") or check.get("status"),
        "client_summary": result.get("client_summary"),
        "comparison_status": result.get("comparison_status"),
        "recommendation": {
            "offer_paid_analysis": bool(diag_d.get("allowed")),
        },
        "findings": result.get("findings") or [],
        "limitations": result.get("limitations") or [],
    }


def _patch_case_flags(case_id: str, patch: dict[str, Any]) -> bool:
    """Запись флагов дела; True только если update затронул строку."""
    try:
        from sfrfr.db.case_repository import CaseRepository

        repo = CaseRepository()
        row = repo.get_case_row(case_id) or {}
        if not row:
            return False
        flags = dict(row.get("flags") or {}) if isinstance(row.get("flags"), dict) else {}
        flags.update(patch)
        resp = (
            repo.client.table("cases")
            .update({"flags": flags})
            .eq("id", case_id)
            .execute()
        )
        data = getattr(resp, "data", None)
        if data is None:
            # некоторые клиенты не возвращают data — считаем ok только без исключения
            # после явной проверки существования строки выше
            return True
        if isinstance(data, list):
            return len(data) > 0
        return bool(data)
    except Exception:  # noqa: BLE001
        return False


def _mark_declined(case_id: str) -> bool:
    return _patch_case_flags(case_id, {"precheck_offer_declined": True})


def _mark_ask_staff(case_id: str, max_user_id: str) -> bool:
    """Зарегистрировать запрос сотрудника без ложного «подключён»."""
    return _patch_case_flags(
        case_id,
        {
            "precheck_ask_staff_requested": True,
            "precheck_ask_staff_at": datetime.now(UTC).isoformat(),
            "precheck_ask_staff_max_user": str(max_user_id or "")[:64],
            "precheck_ask_staff_confirmed": False,
        },
    )


def live_offer_still_allowed(*, case_id: str, primary: dict[str, Any]) -> tuple[bool, str]:
    """Повторная проверка gates на момент callback (не доверять сохранённой карточке)."""
    raw_rec = primary.get("recommendation")
    rec: dict[str, Any] = raw_rec if isinstance(raw_rec, dict) else {}
    if not rec.get("offer_paid_analysis"):
        return False, "saved_offer_false"
    try:
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.services.staff_document_check import (
            _client_declined_precheck_offer,
            _orders_offer_gate,
        )

        repo = CaseRepository()
        if _client_declined_precheck_offer(repo, case_id):
            return False, "client_declined"
        block, unknown = _orders_offer_gate(repo, case_id)
        if unknown:
            return False, "order_status_unknown"
        if block:
            return False, "already_ordered_or_paid"
    except Exception:  # noqa: BLE001
        return False, "gate_unavailable"
    return True, "allowed"


def _status_text(check: dict[str, Any] | None, primary: dict[str, Any]) -> str:
    if not check:
        return (
            "Результат первичной проверки по этому делу ещё не сохранён. "
            "Когда сотрудник запустит проверку и она завершится — придёт уведомление."
        )
    status = str(check.get("status") or "").lower()
    if status in {"queued", "pending"}:
        return "Проверка документов поставлена в очередь. Результата ещё нет."
    if status == "running":
        return "Проверка документов выполняется. Результата ещё нет — подождите."
    if status == "failed":
        err = str(check.get("last_error") or "").strip()
        base = "Проверка не завершилась из‑за технической ошибки. Выводов пока нет."
        return f"{base} ({err})" if err else base
    if not primary or not (
        primary.get("client_summary") or primary.get("outcome") or primary.get("findings")
    ):
        return (
            "Сохранённой карточки результата пока нет. "
            "Нельзя считать проверку завершённой."
        )
    return str(primary.get("client_summary") or "Есть сохранённый результат проверки.")


def _summary_message(
    check: dict[str, Any] | None,
    primary: dict[str, Any],
    current_id: str,
) -> PrecheckCallbackResult:
    status = str((check or {}).get("status") or "").lower()
    if status in {"queued", "running", "pending", "failed"} or not primary:
        text, _ = sanitize_client_text(_status_text(check, primary))
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_status",
            text=text,
            detail=status or "no_primary",
        )
    # Не подставлять дефолт «завершена» без outcome.
    text, atts = build_precheck_max_message(primary, check_id=current_id or None)
    if not str(primary.get("client_summary") or "").strip():
        text, _ = sanitize_client_text(_status_text(check, primary))
    else:
        text, _ = sanitize_client_text(text)
    return PrecheckCallbackResult(
        ok=True, action="precheck_summary", text=text, attachments=atts
    )


def handle_precheck_callback(
    *,
    payload: str,
    case_id: str,
    max_user_id: str,
    requested_check_id: str | None = None,
) -> PrecheckCallbackResult | None:
    """Обработать precheck:*. None — не наш callback."""
    parsed = parse_precheck_payload(payload)
    if parsed is None:
        return None
    sub, payload_check_id = parsed
    if requested_check_id is None and payload_check_id:
        requested_check_id = payload_check_id

    # Неизвестный / повреждённый subcode
    if sub not in CALLBACK_CONTRACTS:
        text, _ = sanitize_client_text(
            "Неизвестное или повреждённое действие проверки. "
            "Откройте актуальное резюме или напишите сотруднику."
        )
        return PrecheckCallbackResult(
            ok=False, action="precheck_unknown", text=text, detail=sub
        )

    check = _load_latest_check(case_id)
    current_id = str((check or {}).get("job_id") or (check or {}).get("id") or "")
    primary = _primary_from_check(check)

    # Мутации без check_id (старые кнопки) — не выполнять, показать актуальное.
    if sub in MUTATING_SUBCODES and not requested_check_id:
        text, atts = build_precheck_max_message(primary, check_id=current_id or None)
        note, _ = sanitize_client_text(
            "Эта кнопка без версии проверки устарела. "
            "Ниже — актуальное состояние; коммерческое действие не выполнено.\n\n"
            + (text if primary else _status_text(check, primary))
        )
        return PrecheckCallbackResult(
            ok=True,
            action="stale_missing_check_id",
            text=note,
            attachments=atts if primary else None,
            detail="legacy_payload",
        )

    if requested_check_id:
        if not _job_belongs_to_case(requested_check_id, case_id):
            text, _ = sanitize_client_text(
                "Эта кнопка относится к другой проверке или делу. "
                "Результат не раскрываем. Напишите сотруднику, если нужна помощь."
            )
            return PrecheckCallbackResult(
                ok=False,
                action="precheck_forbidden_check",
                text=text,
                detail="check_not_on_case",
            )
        stale = resolve_stale_callback(
            requested_check_id=requested_check_id,
            current_check_id=current_id,
            current_primary=primary,
        )
        if stale.get("stale"):
            # Старое коммерческое действие не выполняем.
            text, atts = build_precheck_max_message(primary, check_id=current_id or None)
            text, _ = sanitize_client_text(
                str(stale.get("message") or "")
                + " Предыдущее действие не применено.\n\n"
                + text
            )
            return PrecheckCallbackResult(
                ok=True,
                action="stale_show_current",
                text=text,
                attachments=atts,
                detail="stale_callback",
            )

    if check and check.get("stale"):
        text, _ = sanitize_client_text(
            "Результат устарел: набор документов изменился. "
            "Сотрудник может запустить проверку снова."
        )
        return PrecheckCallbackResult(
            ok=True, action="stale_docs", text=text, detail="document_set_changed"
        )

    if sub == "status":
        text, _ = sanitize_client_text(_status_text(check, primary))
        return PrecheckCallbackResult(ok=True, action="precheck_status", text=text)

    if sub == "summary":
        return _summary_message(check, primary, current_id)

    if sub == "explain":
        if not primary:
            text, _ = sanitize_client_text(_status_text(check, primary))
            return PrecheckCallbackResult(ok=True, action="precheck_status", text=text)
        findings_raw = primary.get("findings")
        findings: list[Any] = findings_raw if isinstance(findings_raw, list) else []
        hard = [
            f
            for f in findings
            if isinstance(f, dict)
            and str(f.get("code") or "")
            in {"DATE_DIFFERENCE", "NOT_LOCATED_IN_ILS", "SOURCE_CONFLICT"}
        ]
        if hard:
            sample = hard[0]
            body = (
                f"По сохранённой находке «{sample.get('code')}»: {sample.get('what')}. "
                "Это различие между представленными документами, "
                "а не доказанная недоплата пенсии."
            )
            lim_raw = primary.get("limitations")
            lim: list[Any] = lim_raw if isinstance(lim_raw, list) else []
            if lim:
                body += " Ограничения: " + "; ".join(str(x) for x in lim[:3])
        else:
            body = answer_faq("что означает расхождение", primary)
        text, _ = sanitize_client_text(body)
        return PrecheckCallbackResult(ok=True, action="precheck_explain", text=text)

    if sub in {"need_docs", "upload"}:
        text, _ = sanitize_client_text(
            "Нужны недостающие или более читаемые страницы. "
            "Сейчас доступна загрузка в этот чат MAX или через кабинет "
            "(защищённая ссылка «открыть кабинет» в меню бота). "
            "Отдельный one-shot upload-token из этой кнопки пока не выдаётся."
        )
        return PrecheckCallbackResult(
            ok=True, action="precheck_need_docs", text=text, detail="route_instruction"
        )

    if sub == "offer_info":
        allowed, reason = live_offer_still_allowed(case_id=case_id, primary=primary)
        if not allowed:
            text, _ = sanitize_client_text(
                "Сейчас нет оснований предлагать платный анализ "
                f"(проверка: {reason})."
            )
            return PrecheckCallbackResult(
                ok=True, action="precheck_offer_blocked", text=text, detail=reason
            )
        raw_rec = primary.get("recommendation")
        rec = raw_rec if isinstance(raw_rec, dict) else {}
        price = rec.get("amount_rub") or rec.get("catalog_price_reference")
        scope = str(rec.get("service_scope") or rec.get("reason") or "")
        price_part = (
            f" Стоимость по каталогу: {price} ₽." if price else " Цену уточнит каталог."
        )
        text, _ = sanitize_client_text(
            "Подробный анализ проверяет основания учёта периода и готовит план. "
            + scope
            + price_part
            + " Заказ создаётся только по вашему явному действию."
        )
        return PrecheckCallbackResult(ok=True, action="precheck_offer_info", text=text)

    if sub == "order":
        allowed, reason = live_offer_still_allowed(case_id=case_id, primary=primary)
        if not allowed:
            text, _ = sanitize_client_text(
                "Заказ анализа сейчас недоступен "
                f"({reason}). Это не создание счёта."
            )
            return PrecheckCallbackResult(
                ok=True,
                action="precheck_order_blocked",
                text=text,
                detail=reason,
            )
        text, _ = sanitize_client_text(
            "Переход к оплате из этой кнопки пока не подключён к платёжному маршруту. "
            "Счёт и ссылка на оплату создаются только через кабинет или сообщение "
            "сотрудника. Этот callback заказ и платёж не создаёт."
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_order_handoff",
            text=text,
            detail="explicit_route_unavailable",
        )

    if sub == "decline":
        saved = _mark_declined(case_id)
        if not saved:
            text, _ = sanitize_client_text(
                "Не удалось сохранить отказ от предложения. "
                "Попробуйте ещё раз или напишите сотруднику — "
                "предложение пока может снова отображаться."
            )
            return PrecheckCallbackResult(
                ok=False,
                action="precheck_decline_failed",
                text=text,
                detail="flag_not_saved",
            )
        # Актуальные кнопки без оффера
        primary_no_offer = dict(primary)
        raw_rec = primary.get("recommendation")
        rec = dict(raw_rec) if isinstance(raw_rec, dict) else {}
        rec["offer_paid_analysis"] = False
        rec["offer_status"] = "declined"
        primary_no_offer["recommendation"] = rec
        text, atts = build_precheck_max_message(
            primary_no_offer, check_id=current_id or None
        )
        note, _ = sanitize_client_text(
            "Хорошо, отказ сохранён — предложение убираем. "
            "Резюме проверки остаётся доступным.\n\n" + text
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_declined",
            text=note,
            attachments=atts,
            detail="flag_saved",
        )

    if sub == "ask_staff":
        registered = _mark_ask_staff(case_id, max_user_id)
        if not registered:
            text, _ = sanitize_client_text(
                "Не удалось зарегистрировать запрос сотруднику. "
                "Напишите сообщение в чат текстом или повторите позже. "
                "Специалист автоматически не подключён."
            )
            return PrecheckCallbackResult(
                ok=False,
                action="precheck_ask_staff_failed",
                text=text,
                detail="flag_not_saved",
            )
        text, _ = sanitize_client_text(
            "Запрос сотруднику зарегистрирован. "
            "Сообщение «специалист подключён» появится только после реальной передачи."
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_ask_staff",
            text=text,
            detail="registered",
        )

    if sub == "answer":
        text, _ = sanitize_client_text(
            "Конкретный уточняющий вопрос по этой проверке пока не зафиксирован "
            "в ожидании ответа. Кратко: "
            + answer_faq("нужно уточнение", primary)
            + " Чтобы задать свой вопрос — напишите текстом в чат или нажмите "
            "«Задать вопрос сотруднику»."
        )
        return PrecheckCallbackResult(
            ok=True, action="precheck_answer", text=text, detail="faq_stub"
        )

    text, _ = sanitize_client_text("Неизвестное действие проверки. Откройте актуальное резюме.")
    return PrecheckCallbackResult(
        ok=False, action="precheck_unknown", text=text, detail=sub
    )
