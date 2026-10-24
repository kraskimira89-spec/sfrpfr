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

# subcode → краткое описание контракта (для матрицы доказательств).
CALLBACK_CONTRACTS: dict[str, str] = {
    "summary": "Открыть резюме актуальной проверки",
    "explain": "Объяснить расхождение по сохранённой находке",
    "need_docs": "Что загрузить / зачем",
    "upload": "Маршрут досылки документов",
    "offer_info": "Состав/цена из каталога в recommendation, без заказа",
    "order": "Явный заказ через существующий маршрут (не по stale)",
    "decline": "Отказ от оффера; прекратить авто-повтор",
    "ask_staff": "Зарегистрировать передачу сотруднику",
    "status": "Статус незавершённой/актуальной проверки",
    "answer": "Ответ на уточняющий вопрос",
}


@dataclass
class PrecheckCallbackResult:
    ok: bool
    action: str
    text: str
    attachments: list[dict[str, Any]] | None = None
    detail: str | None = None


def parse_precheck_callback(payload: str) -> str | None:
    raw = (payload or "").strip()
    if not raw.startswith(PRECHECK_PREFIX):
        return None
    return raw[len(PRECHECK_PREFIX) :].strip() or None


def _load_latest_check(case_id: str) -> dict[str, Any] | None:
    from sfrfr.services.staff_document_check import get_case_document_check

    return get_case_document_check(case_id)


def _primary_from_check(check: dict[str, Any] | None) -> dict[str, Any]:
    if not check:
        return {}
    result = check.get("result") if isinstance(check.get("result"), dict) else {}
    primary = result.get("primary_precheck") if isinstance(result, dict) else None
    if isinstance(primary, dict):
        return primary
    # fallback: поля summarize
    return {
        "outcome": result.get("precheck_outcome") or check.get("status"),
        "client_summary": result.get("client_summary"),
        "comparison_status": result.get("comparison_status"),
        "recommendation": (
            {"offer_paid_analysis": bool((result.get("diag_offer") or {}).get("allowed"))}
            if isinstance(result, dict)
            else {}
        ),
        "findings": result.get("findings") or [],
        "limitations": result.get("limitations") or [],
    }


def _patch_case_flags(case_id: str, patch: dict[str, Any]) -> bool:
    """Best-effort запись флагов дела (decline / ask_staff)."""
    try:
        from sfrfr.db.case_repository import CaseRepository

        repo = CaseRepository()
        row = repo.get_case_row(case_id) or {}
        flags = dict(row.get("flags") or {}) if isinstance(row.get("flags"), dict) else {}
        flags.update(patch)
        repo.client.table("cases").update({"flags": flags}).eq("id", case_id).execute()
        return True
    except Exception:  # noqa: BLE001
        return False


def _mark_declined(case_id: str) -> None:
    _patch_case_flags(case_id, {"precheck_offer_declined": True})


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


def handle_precheck_callback(
    *,
    payload: str,
    case_id: str,
    max_user_id: str,
    requested_check_id: str | None = None,
) -> PrecheckCallbackResult | None:
    """Обработать precheck:*. None — не наш callback."""
    sub = parse_precheck_callback(payload)
    if sub is None:
        return None

    check = _load_latest_check(case_id)
    current_id = str((check or {}).get("job_id") or "")
    primary = _primary_from_check(check)
    if requested_check_id:
        stale = resolve_stale_callback(
            requested_check_id=requested_check_id,
            current_check_id=current_id,
            current_primary=primary,
        )
        if stale.get("stale"):
            text, atts = build_precheck_max_message(primary)
            text, _ = sanitize_client_text(
                str(stale.get("message") or "") + "\n\n" + text
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

    if sub in {"summary", "status"}:
        text, atts = build_precheck_max_message(primary)
        text, _ = sanitize_client_text(text)
        return PrecheckCallbackResult(
            ok=True, action=f"precheck_{sub}", text=text, attachments=atts
        )

    if sub == "explain":
        findings = primary.get("findings") if isinstance(primary.get("findings"), list) else []
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
            lim = primary.get("limitations") if isinstance(primary.get("limitations"), list) else []
            if lim:
                body += " Ограничения: " + "; ".join(str(x) for x in lim[:3])
        else:
            body = answer_faq("что означает расхождение", primary)
        text, _ = sanitize_client_text(body)
        return PrecheckCallbackResult(ok=True, action="precheck_explain", text=text)

    if sub in {"need_docs", "upload"}:
        text, _ = sanitize_client_text(
            "Нужны недостающие или более читаемые страницы для сопоставления. "
            "Загрузите файлы в чат или кабинет — после поступления можно повторить проверку."
        )
        return PrecheckCallbackResult(ok=True, action="precheck_need_docs", text=text)

    def _rec() -> dict[str, Any]:
        raw = primary.get("recommendation")
        return raw if isinstance(raw, dict) else {}

    if sub == "offer_info":
        rec = _rec()
        if not rec.get("offer_paid_analysis"):
            text, _ = sanitize_client_text(
                "Сейчас нет оснований предлагать платный анализ по этой проверке."
            )
            return PrecheckCallbackResult(ok=True, action="precheck_offer_blocked", text=text)
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
        rec = _rec()
        if not rec.get("offer_paid_analysis"):
            text, _ = sanitize_client_text(
                "Заказ анализа сейчас недоступен (нет актуального основания, "
                "отказ, оплата или неясный статус заказа)."
            )
            return PrecheckCallbackResult(
                ok=True,
                action="precheck_order_blocked",
                text=text,
                detail="offer_not_allowed",
            )
        # Не создаём заказ здесь — только направляем на существующий маршрут.
        text, _ = sanitize_client_text(
            "Чтобы заказать подробный анализ, подтвердите в кабинете или "
            "через кнопку оплаты, которую пришлёт сотрудник. "
            "Этот callback сам заказ не создаёт."
        )
        return PrecheckCallbackResult(
            ok=True, action="precheck_order_handoff", text=text, detail="explicit_route_required"
        )

    if sub == "decline":
        _mark_declined(case_id)
        text, _ = sanitize_client_text(
            "Хорошо, предложение убираем. Резюме проверки остаётся доступным."
        )
        return PrecheckCallbackResult(ok=True, action="precheck_declined", text=text)

    if sub == "ask_staff":
        registered = _mark_ask_staff(case_id, max_user_id)
        text, _ = sanitize_client_text(
            (
                "Запрос сотруднику зарегистрирован. "
                if registered
                else "Запрос сотруднику принят (сохранение флага отложено). "
            )
            + "Сообщение «специалист подключён» появится только после реальной передачи."
        )
        return PrecheckCallbackResult(
            ok=True,
            action="precheck_ask_staff",
            text=text,
            detail="registered" if registered else "register_deferred",
        )

    if sub == "answer":
        text, _ = sanitize_client_text(
            answer_faq("нужно уточнение", primary)
        )
        return PrecheckCallbackResult(ok=True, action="precheck_answer", text=text)

    text, _ = sanitize_client_text("Неизвестное действие проверки. Откройте актуальное резюме.")
    return PrecheckCallbackResult(
        ok=False, action="precheck_unknown", text=text, detail=sub
    )
