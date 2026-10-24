"""Контракты callback precheck:* (MAX). Не создаёт заказ молча."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    "order": "Существующий DIAG-маршрут (каталог→draft→оферта→pay link) при gates",
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
    """Запись флагов; True только после read-back совпадения ключей patch.

    Отсутствие исключения / пустой data от клиента БД ≠ успех.
    """
    try:
        from sfrfr.db.case_repository import CaseRepository

        repo = CaseRepository()
        row = repo.get_case_row(case_id) or {}
        if not row:
            return False
        flags_raw = row.get("flags")
        flags = dict(flags_raw) if isinstance(flags_raw, dict) else {}
        flags.update(patch)
        resp = (
            repo.client.table("cases")
            .update({"flags": flags})
            .eq("id", case_id)
            .execute()
        )
        data = getattr(resp, "data", None)
        if isinstance(data, list) and len(data) == 0:
            return False
        # Подтверждение: перечитать строку и сверить patch.
        again = repo.get_case_row(case_id) or {}
        saved_raw = again.get("flags")
        saved = saved_raw if isinstance(saved_raw, dict) else {}
        for key, expected in patch.items():
            if saved.get(key) != expected:
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


def _link_attachments(*, text: str, url: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{"type": "link", "text": text, "url": url}]]
            },
        }
    ]


def _pending_question(primary: dict[str, Any]) -> str | None:
    rec = primary.get("recommendation")
    if isinstance(rec, dict):
        qs = rec.get("questions_to_resolve")
        if isinstance(qs, list) and qs:
            q0 = str(qs[0] or "").strip()
            if q0:
                return q0
    findings = primary.get("findings")
    if isinstance(findings, list):
        for f in findings:
            if isinstance(f, dict) and f.get("what"):
                return f"Уточните по находке «{f.get('code')}»: {f.get('what')}"
    return None


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


def _diag_catalog_snapshot() -> tuple[dict[str, Any] | None, str]:
    """Актуальные условия DIAG из публичного каталога (не из старого сообщения)."""
    try:
        from sfrfr.services.public_tariffs import public_tariff

        tariff = public_tariff("DIAG")
    except Exception:  # noqa: BLE001
        return None, "catalog_unavailable"
    if not isinstance(tariff, dict) or tariff.get("amount_rub") is None:
        return None, "catalog_unavailable"
    return tariff, "ok"


def _saved_offer_amount(rec: dict[str, Any]) -> int | None:
    raw = rec.get("amount_rub")
    if raw is None:
        raw = rec.get("catalog_price_reference")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _sandbox_diag_order(
    *,
    case_id: str,
    max_user_id: str,
    tariff: dict[str, Any],
) -> dict[str, Any]:
    """Синтетический DIAG-заказ без ЮKassa / реальных счетов клиентам."""
    from uuid import uuid4

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.max_bot_invoice import (
        _find_open_order,
        _has_open_or_paid_diag,
    )

    repo = CaseRepository()
    try:
        orders = repo.list_orders(case_id)
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "orders_load"}
    if _has_open_or_paid_diag(orders):
        open_diag = _find_open_order(orders, tariff="DIAG")
        if open_diag is None:
            return {"ok": True, "already_paid": True}
        pay_url = str(open_diag.get("pay_url") or "").strip()
        if not pay_url:
            pay_url = f"https://pay.sandbox.local/diag/{open_diag.get('id') or uuid4()}"
        return {
            "ok": True,
            "sandbox": True,
            "order": {**open_diag, "pay_url": pay_url},
            "pay": {"pay_url": pay_url, "sandbox": True},
            "reused": True,
        }
    amount = float(tariff.get("amount_rub") or 3000)
    label = str(tariff.get("name") or "Диагностика")
    try:
        order = repo.create_order(
            case_id,
            package_code="DIAG",
            amount_rub=amount,
            status_value="draft",
            actor_id=f"bot:precheck_sandbox:{max_user_id}"[:64],
            due_at=(datetime.now(UTC) + timedelta(days=3)).isoformat(),
            service_label=label,
            invoice_status="draft",
        )
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "create_order"}
    if not order or not order.get("id"):
        return {"ok": False, "reason": "create_order"}
    pay_url = f"https://pay.sandbox.local/diag/{order['id']}"
    return {
        "ok": True,
        "sandbox": True,
        "order": {**order, "pay_url": pay_url},
        "pay": {"pay_url": pay_url, "sandbox": True},
        "reused": False,
    }


def _execute_precheck_order(
    *,
    case_id: str,
    max_user_id: str,
    primary: dict[str, Any],
) -> PrecheckCallbackResult:
    """Явный precheck:order → существующий DIAG-маршрут (не вторая платёжка)."""
    import os

    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.diag_choice import fail_text_for_reason

    allowed, reason = live_offer_still_allowed(case_id=case_id, primary=primary)
    if not allowed:
        text, _ = sanitize_client_text(
            "Заказ анализа сейчас недоступен "
            f"({reason}). Счёт не создаём."
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_order_blocked",
            text=text,
            detail=reason,
        )

    tariff, cat_reason = _diag_catalog_snapshot()
    if tariff is None:
        text, _ = sanitize_client_text(
            "Каталог услуг сейчас недоступен — состав и цену не подтверждаем. "
            "Счёт не создаём. Попробуйте позже или напишите сотруднику."
        )
        return PrecheckCallbackResult(
            ok=False,
            action="precheck_order_catalog_unavailable",
            text=text,
            detail=cat_reason,
        )

    raw_rec = primary.get("recommendation")
    rec: dict[str, Any] = raw_rec if isinstance(raw_rec, dict) else {}
    catalog_amount = int(tariff["amount_rub"])
    saved_amount = _saved_offer_amount(rec)
    if saved_amount is not None and saved_amount != catalog_amount:
        text, _ = sanitize_client_text(
            f"С момента сообщения цена в каталоге изменилась: было {saved_amount} ₽, "
            f"сейчас {catalog_amount} ₽ ({tariff.get('name')}). "
            f"Состав: {tariff.get('includes') or 'см. каталог'}. "
            "Новый счёт не создаём по старой кнопке — откройте актуальное резюме "
            "и при согласии нажмите заказ снова."
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_order_price_changed",
            text=text,
            detail=f"{saved_amount}->{catalog_amount}",
        )

    scope = str(rec.get("service_scope") or rec.get("reason") or "").strip()
    composition = (
        f"{tariff.get('name')}: {tariff.get('includes') or 'диагностика документов'}. "
        f"Стоимость: {catalog_amount} ₽."
        + (f" Основание: {scope}." if scope else "")
    )

    settings = get_settings()
    sandbox = bool(settings.precheck_order_sandbox) or (
        os.environ.get("PRECHECK_ORDER_SANDBOX", "").strip() == "1"
    )

    result: dict[str, Any] | None
    if sandbox:
        result = _sandbox_diag_order(
            case_id=case_id, max_user_id=max_user_id, tariff=tariff
        )
    else:
        from sfrfr.services.max_bot_invoice import start_diag_payment_after_yes

        try:
            result = start_diag_payment_after_yes(
                case_id=case_id,
                max_user_id=max_user_id,
            )
        except Exception:  # noqa: BLE001
            text, _ = sanitize_client_text(
                "Не удалось завершить оформление: неизвестный исход создания заказа. "
                "Повторно счёт не выставляем автоматически. Напишите сотруднику."
            )
            return PrecheckCallbackResult(
                ok=False,
                action="precheck_order_unknown",
                text=text,
                detail="exception",
            )

    if not result:
        text, _ = sanitize_client_text(
            "Не удалось получить результат оформления. "
            "Повторно счёт не создаём. Напишите «Нужна проверка» или сотруднику."
        )
        return PrecheckCallbackResult(
            ok=False, action="precheck_order_unknown", text=text, detail="empty_result"
        )

    if result.get("already_paid"):
        text, _ = sanitize_client_text(
            "Диагностика по этому делу уже оплачена. Повторный счёт не создаём. "
            + composition
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_order_already_paid",
            text=text,
            detail="already_paid",
        )

    if not result.get("ok"):
        fail_reason = str(result.get("reason") or "unknown")
        # Честный текст из существующего diag_choice; без слепого повтора.
        body = fail_text_for_reason(fail_reason)
        text, _ = sanitize_client_text(body + " " + composition)
        return PrecheckCallbackResult(
            ok=False,
            action="precheck_order_failed",
            text=text,
            detail=fail_reason,
        )

    pay = result.get("pay") if isinstance(result.get("pay"), dict) else {}
    order = result.get("order") if isinstance(result.get("order"), dict) else {}
    pay_url = str(
        (pay or {}).get("pay_url") or (order or {}).get("pay_url") or ""
    ).strip()
    reused = bool(result.get("reused"))
    if not pay_url:
        text, _ = sanitize_client_text(
            "Заказ есть или создан, но ссылка на оплату ещё не подтверждена. "
            "Не обещаем оплату по отсутствующей ссылке. "
            + composition
            + " Напишите «Нужна проверка» — пришлём ссылку вручную."
        )
        return PrecheckCallbackResult(
            ok=False,
            action="precheck_order_no_pay_url",
            text=text,
            detail="pay_url_missing",
        )

    prefix = (
        "Повтор: возвращаем действующую ссылку на уже оформленный заказ. "
        if reused
        else "Заказ диагностики оформлен по вашему явному действию. "
    )
    sand = " (тестовый sandbox, не реальная оплата)." if result.get("sandbox") else ""
    text, _ = sanitize_client_text(prefix + composition + sand)
    return PrecheckCallbackResult(
        ok=True,
        action="precheck_order_pay_link",
        text=text,
        attachments=_link_attachments(text="Оплатить диагностику", url=pay_url),
        detail="sandbox" if result.get("sandbox") else "diag_route",
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
        from sfrfr.services.case_chat_delivery import documents_cabinet_url

        cab = documents_cabinet_url(case_id)
        text, _ = sanitize_client_text(
            "Нужны недостающие или более читаемые страницы. "
            "Действующий путь: 1) пришлите файл прямо в этот чат — он попадёт в дело; "
            "2) либо откройте раздел документов в кабинете по ссылке ниже. "
            "Отдельный одноразовый upload-token здесь не выдаём."
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_upload_route",
            text=text,
            attachments=_link_attachments(
                text="Открыть документы в кабинете", url=cab
            ),
            detail="chat_or_cabinet",
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
        return _execute_precheck_order(
            case_id=case_id, max_user_id=max_user_id, primary=primary
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
        question = _pending_question(primary)
        if not question:
            text, _ = sanitize_client_text(
                "По этой проверке нет сохранённого уточняющего вопроса. "
                "Напишите текстом в чат или нажмите «Задать вопрос сотруднику»."
            )
            return PrecheckCallbackResult(
                ok=True, action="precheck_answer_none", text=text, detail="no_question"
            )
        saved = _patch_case_flags(
            case_id,
            {
                "precheck_awaiting_answer": {
                    "check_id": current_id or requested_check_id,
                    "question": question[:500],
                    "asked_at": datetime.now(UTC).isoformat(),
                    "max_user_id": str(max_user_id or "")[:64],
                }
            },
        )
        if not saved:
            text, _ = sanitize_client_text(
                f"Вопрос: {question}\n\n"
                "Не удалось зафиксировать ожидание ответа в деле. "
                "Можете всё равно ответить текстом в чат — сотрудник увидит сообщение."
            )
            return PrecheckCallbackResult(
                ok=False,
                action="precheck_answer_flag_failed",
                text=text,
                detail="flag_not_saved",
            )
        text, _ = sanitize_client_text(
            f"Вопрос по проверке:\n{question}\n\n"
            "Напишите ответ следующим сообщением в этот чат — "
            "он будет связан с ожиданием ответа по этой проверке."
        )
        return PrecheckCallbackResult(
            ok=True, action="precheck_answer_awaiting", text=text, detail="awaiting_text"
        )

    text, _ = sanitize_client_text("Неизвестное действие проверки. Откройте актуальное резюме.")
    return PrecheckCallbackResult(
        ok=False, action="precheck_unknown", text=text, detail=sub
    )
