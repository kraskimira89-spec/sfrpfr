"""Kanban этапов воронки 3/5/8 тыс. (ТЗ-33).

Колонку считает код по заказам/оплате/выдаче диагностики — не LLM.
"""

from __future__ import annotations

from typing import Any

# id → заголовок UI
FUNNEL_BOARD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("new", "Новый лид"),
    ("qualify", "Квалификация"),
    ("docs_collect", "Сбор документов"),
    ("pay_diag", "Оплата 3 000"),
    ("diag_work", "Диагностика"),
    ("diag_done", "Результат выдан"),
    ("pay_docs", "Оплата 5 000"),
    ("docs_work", "Подготовка документов"),
    ("pay_support", "Оплата 8 000"),
    ("support", "Сопровождение"),
    ("delivery", "Подача клиентом"),
    ("closed", "Закрыто"),
    ("lost", "Отказ"),
)

FUNNEL_COLUMN_IDS: frozenset[str] = frozenset(c[0] for c in FUNNEL_BOARD_COLUMNS)

_OPEN = frozenset({"draft", "pending", "awaiting_payment"})
_OPEN_INV = _OPEN | frozenset({"invoice_ready", "invoice_sent", "overdue"})
_DELIVERED_RESULT = frozenset(
    {"link_issued", "delivered", "opened", "feedback_pending"}
)

# Порог суммы: DOCS ≈ 5000, SUPPORT ≈ 8000 (оба package_code=ACCOMP).
_DOCS_AMOUNT_MAX = 6500.0
_SUPPORT_AMOUNT_MIN = 7000.0


def classify_accomp_tariff(order: dict[str, Any]) -> str | None:
    """DOCS | SUPPORT | None для заказа ACCOMP."""
    code = str(order.get("package_code") or "").upper()
    if code != "ACCOMP":
        return None
    label = str(order.get("service_label") or "").lower()
    if "сопровожд" in label or "шаг 3" in label or "support" in label:
        return "SUPPORT"
    if "подготов" in label or "шаг 2" in label or "документ" in label:
        # «документов» overlapping — amount breaks ties
        pass
    try:
        amount = float(order.get("amount_rub") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount >= _SUPPORT_AMOUNT_MIN:
        return "SUPPORT"
    if 0 < amount <= _DOCS_AMOUNT_MAX:
        return "DOCS"
    if "сопровожд" in label:
        return "SUPPORT"
    return "DOCS"


def _order_open(order: dict[str, Any]) -> bool:
    status = str(order.get("status") or "").lower()
    inv = str(order.get("invoice_status") or "").lower()
    if status == "paid":
        return False
    if status in _OPEN:
        return True
    if inv in _OPEN_INV:
        return True
    return False


def _order_paid(order: dict[str, Any]) -> bool:
    return str(order.get("status") or "").lower() == "paid"


def tariff_states(orders: list[dict[str, Any]] | None) -> dict[str, str]:
    """DIAG/DOCS/SUPPORT → paid | open | none."""
    out = {"DIAG": "none", "DOCS": "none", "SUPPORT": "none"}
    for o in orders or []:
        code = str(o.get("package_code") or "").upper()
        if code == "DIAG":
            key = "DIAG"
        elif code == "ACCOMP":
            key = classify_accomp_tariff(o) or "DOCS"
        else:
            continue
        if _order_paid(o):
            out[key] = "paid"
        elif _order_open(o) and out[key] != "paid":
            out[key] = "open"
    return out


def active_tariff_badge(orders: list[dict[str, Any]] | None) -> str | None:
    """Бейдж на карточке: DIAG / DOCS / SUPPORT."""
    states = tariff_states(orders)
    for key in ("SUPPORT", "DOCS", "DIAG"):
        if states[key] in {"paid", "open"}:
            return key
    return None


def order_summary_for_board(orders: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Кратко по открытому счёту для pay_*."""
    best: dict[str, Any] | None = None
    best_prio = -1
    prio = {"SUPPORT": 3, "DOCS": 2, "DIAG": 1}
    for o in orders or []:
        if not _order_open(o):
            continue
        code = str(o.get("package_code") or "").upper()
        if code == "DIAG":
            tariff = "DIAG"
        elif code == "ACCOMP":
            tariff = classify_accomp_tariff(o) or "DOCS"
        else:
            continue
        rank = prio.get(tariff, 0)
        if rank > best_prio:
            best_prio = rank
            try:
                amount = float(o.get("amount_rub") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            best = {
                "tariff": tariff,
                "amount_rub": amount,
                "status": str(o.get("status") or ""),
                "invoice_status": str(o.get("invoice_status") or ""),
            }
    return best


def diagnosis_delivered_from_case(case: dict[str, Any] | None) -> bool:
    """Выдан клиенту PDF/ссылка (ТЗ-30), не сырой OCR."""
    if not case:
        return False
    if case.get("diagnosis_delivered") is True:
        return True
    results = case.get("diagnostic_results")
    if isinstance(results, dict):
        results = [results]
    for row in results or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").lower() in _DELIVERED_RESULT:
            return True
    feedback = case.get("diagnosis_feedback")
    if isinstance(feedback, list):
        feedback = feedback[0] if feedback else None
    if isinstance(feedback, dict):
        if feedback.get("pdf_issued_at"):
            return True
        if str(feedback.get("feedback_status") or "") in {
            "nav_sent",
            "understood",
            "need_help",
            "has_question",
            "survey_done",
        }:
            return True
    return False


def docs_package_ready_from_case(case: dict[str, Any] | None) -> bool:
    """Есть артефакт проекта обращения / план подачи (ворота SUPPORT)."""
    if not case:
        return False
    if case.get("docs_package_ready") is True:
        return True
    p = str(case.get("pipeline_status") or "").lower()
    if p in {"draft_ready", "human_review", "audited"}:
        return True
    for item in case.get("checklist_items") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "") != "done":
            continue
        title = str(item.get("title") or "").lower()
        if "проект обращения" in title or "план подачи" in title:
            return True
    return False


def compute_funnel_column(
    case: dict[str, Any] | None,
    orders: list[dict[str, Any]] | None = None,
    *,
    diagnosis_delivered: bool | None = None,
    docs_package_ready: bool | None = None,
    waiting_on: str | None = None,
    finance_attention: str | None = None,
) -> str:
    """Ключ колонки kanban. Ручной override — case.funnel_column_manual."""
    case = case or {}
    manual = str(case.get("funnel_column_manual") or "").strip()
    if manual in FUNNEL_COLUMN_IDS:
        return manual

    p = str(case.get("pipeline_status") or "").strip().lower()
    b = str(case.get("b2c_status") or "").strip().lower()
    w = (waiting_on if waiting_on is not None else case.get("waiting_on") or "")
    w = str(w).strip().lower()
    fin = (finance_attention if finance_attention is not None else "")
    fin = str(fin).strip().lower()
    loss = str(case.get("loss_reason") or "").strip()

    order_rows = orders if orders is not None else (case.get("orders") or [])
    states = tariff_states(order_rows)
    delivered = (
        diagnosis_delivered
        if diagnosis_delivered is not None
        else diagnosis_delivered_from_case(case)
    )
    docs_ready = (
        docs_package_ready
        if docs_package_ready is not None
        else docs_package_ready_from_case(case)
    )

    if b == "closed" or p in {"completed", "failed"}:
        return "lost" if loss else "closed"

    if b == "awaiting_client_submission" or w == "sfr":
        return "delivery"

    if states["SUPPORT"] == "paid":
        if w == "sfr" or b == "awaiting_client_submission":
            return "delivery"
        return "support"
    if states["SUPPORT"] == "open":
        return "pay_support"

    if states["DOCS"] == "paid":
        if docs_ready and states["SUPPORT"] == "none" and w == "payment":
            # счёт ещё не создан, но ждём оплату следующего — редкий кейс
            pass
        return "docs_work"
    if states["DOCS"] == "open":
        return "pay_docs"

    if delivered and states["DIAG"] == "paid":
        return "diag_done"
    if states["DIAG"] == "paid":
        return "diag_work"
    if states["DIAG"] == "open":
        return "pay_diag"

    if fin in {"payable", "awaiting_invoice"} or w == "payment" or b == "success_fee_due":
        # без детализации заказа — оплата диагностики как типичный первый счёт
        return "pay_diag"

    if w in {"client", "archive"} or p == "documents_received":
        return "docs_collect"

    if p == "intake" or b in {"lead", ""}:
        return "new"

    if b in {"consent_accepted", "contract_accepted"} or p:
        return "qualify"

    return "qualify"


def funnel_columns_meta() -> list[dict[str, str]]:
    return [{"id": cid, "label": label} for cid, label in FUNNEL_BOARD_COLUMNS]
