"""Автопредложение DIAG/DOCS/SUPPORT и pay link после оферты (bot_owned).

Стратегия: docs/marketing-sales/strategy-llm-tariffs-5000-8000.md
DIAG — после ИЛС+трудовая; DOCS — после выдачи диагностики;
SUPPORT — после DOCS paid + проект обращения.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.bot_owned import is_bot_owned
from sfrfr.integrations.max.intake import cabinet_url_for_case
from sfrfr.services.funnel_board import (
    classify_accomp_tariff,
    diagnosis_delivered_from_case,
    docs_package_ready_from_case,
    tariff_states,
)
from sfrfr.services.public_tariffs import public_tariff

logger = logging.getLogger(__name__)

_OFFERED: set[str] = set()
_OFFERED_DOCS: set[str] = set()
_OFFERED_SUPPORT: set[str] = set()

_CTA_DOCS = frozenset(
    {
        "готов к шагу 2",
        "готов к шагу2",
        "шаг 2",
        "подготовка документов",
        "хочу подготовку",
        "офер docs",
        "docs 5000",
        "5000",
    }
)
_CTA_APPEALS = frozenset(
    {
        "составьте обращения",
        "составить обращения",
        "да, составьте",
        "да составьте",
        "хочу обращения",
        "подготовьте обращения",
        "проекты обращений",
        "обращения в сфр",
    }
)
_CTA_SUPPORT = frozenset(
    {
        "сопровождение 8000",
        "сопровождение",
        "готов к шагу 3",
        "шаг 3",
        "хочу сопровождение",
        "support 8000",
        "8000",
    }
)
_CTA_SKIP = frozenset(
    {
        "сам по плану",
        "подам сам",
        "сам",
        "подумаю",
    }
)


def _has_open_or_paid_diag(orders: list[dict[str, Any]]) -> bool:
    st = tariff_states(orders)
    return st["DIAG"] in {"open", "paid"}


def _find_open_order(
    orders: list[dict[str, Any]],
    *,
    tariff: str,
) -> dict[str, Any] | None:
    tariff = tariff.upper()
    for o in orders or []:
        code = str(o.get("package_code") or "").upper()
        if tariff == "DIAG":
            if code != "DIAG":
                continue
        elif code != "ACCOMP":
            continue
        elif classify_accomp_tariff(o) != tariff:
            continue
        if str(o.get("status") or "") == "paid":
            return None
        if str(o.get("pay_url") or "").strip():
            return o
        if str(o.get("status") or "") in {"draft", "pending"} or str(
            o.get("invoice_status") or ""
        ) in {"draft", "invoice_ready", "invoice_sent"}:
            return o
    return None


def maybe_offer_diag_invoice(
    *,
    case_id: str,
    max_user_id: str,
    intake: Any | None = None,
) -> dict[str, Any] | None:
    """Черновик DIAG + сообщение с офертой в кабинет. Без pay URL."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    if not is_bot_owned(intake):
        return None
    cid = str(case_id or "").strip()
    mid = str(max_user_id or "").strip()
    if not cid or not mid:
        return None
    if cid in _OFFERED:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery
    from sfrfr.services.finance_automation import suggest_agreement_draft

    repo = CaseRepository()
    try:
        case = repo.get_case_row(cid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("diag offer case load failed: %s", exc)
        return None
    if not case:
        return None
    if not repo.has_consent(cid):
        return None
    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        orders = []
    if _has_open_or_paid_diag(orders):
        return None

    draft = suggest_agreement_draft(case, orders)
    if not draft or str(draft.get("package_code") or "").upper() != "DIAG":
        tariff = public_tariff("DIAG") or {}
        draft = {
            "package_code": "DIAG",
            "amount_rub": float(tariff.get("amount_rub") or 3000),
            "service_label": str(tariff.get("name") or "Диагностика"),
        }

    try:
        order = repo.create_order(
            cid,
            package_code="DIAG",
            amount_rub=float(draft["amount_rub"]),
            status_value="draft",
            actor_id="bot:max_owned",
            due_at=(datetime.now(UTC) + timedelta(days=3)).isoformat(),
            service_label=str(draft.get("service_label") or "Диагностика"),
            invoice_status="draft",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("diag draft create failed case=%s: %s", cid[:8], exc)
        return None

    amount = int(float(draft.get("amount_rub") or 3000))
    cab = cabinet_url_for_case(cid)
    body = (
        f"Для диагностики стоимость {amount} ₽. "
        "Чтобы выставить счёт, примите условия оказания услуг в кабинете на сайте — "
        f"после этого пришлём ссылку на оплату в этот чат.\n"
        f"Кабинет: {cab}"
    )
    enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=None,
    )
    _OFFERED.add(cid)
    return {"order": order, "offered": True, "tariff": "DIAG"}


def _gates_docs(
    *,
    case: dict[str, Any],
    orders: list[dict[str, Any]],
    intake: Any | None,
    require_bot_owned: bool,
) -> bool:
    if require_bot_owned and not is_bot_owned(intake):
        return False
    st = tariff_states(orders)
    if st["DIAG"] != "paid":
        return False
    if st["DOCS"] != "none" or st["SUPPORT"] != "none":
        return False
    if not diagnosis_delivered_from_case(case):
        return False
    return True


def _gates_support(
    *,
    case: dict[str, Any],
    orders: list[dict[str, Any]],
    intake: Any | None,
    require_bot_owned: bool,
) -> bool:
    if require_bot_owned and not is_bot_owned(intake):
        return False
    st = tariff_states(orders)
    if st["DOCS"] != "paid":
        return False
    if st["SUPPORT"] != "none":
        return False
    if not docs_package_ready_from_case(case):
        return False
    return True


def maybe_offer_docs_invoice(
    *,
    case_id: str,
    max_user_id: str | None = None,
    intake: Any | None = None,
    case: dict[str, Any] | None = None,
    require_cta: bool = False,
) -> dict[str, Any] | None:
    """Черновик DOCS 5000 после выдачи диагностики. Без pay URL."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    cid = str(case_id or "").strip()
    if not cid or cid in _OFFERED_DOCS:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery

    repo = CaseRepository()
    try:
        row = case or repo.get_case_row(cid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("docs offer case load failed: %s", exc)
        return None
    if not row:
        return None
    if not repo.has_consent(cid):
        return None
    clients = row.get("clients") or {}
    if isinstance(clients, list):
        clients = clients[0] if clients else {}
    mid = str(max_user_id or (clients or {}).get("max_user_id") or "").strip()
    if not mid:
        return None

    if intake is None:
        from sfrfr.integrations.max.intake import get_intake_store

        intake = get_intake_store().get_active(mid)

    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        orders = []

    # Авто после PDF и CTA «Готов к шагу 2»: ворота по фактам; bot_owned не обязателен
    # (диагностику часто ведёт сотрудник).
    if not _gates_docs(
        case=row, orders=orders, intake=intake, require_bot_owned=False
    ):
        return None

    tariff = public_tariff("DOCS") or {}
    amount = float(tariff.get("amount_rub") or 5000)
    label = str(tariff.get("name") or "Шаг 2. Подготовка документов")
    try:
        order = repo.create_order(
            cid,
            package_code="ACCOMP",
            amount_rub=amount,
            status_value="draft",
            actor_id="bot:max_owned",
            due_at=(datetime.now(UTC) + timedelta(days=3)).isoformat(),
            service_label=label,
            invoice_status="draft",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("docs draft create failed case=%s: %s", cid[:8], exc)
        return None

    cab = cabinet_url_for_case(cid)
    from sfrfr.services.max_post_diagnosis import build_docs_invoice_after_appeals_text

    body = build_docs_invoice_after_appeals_text(amount=int(amount), cabinet_url=cab)
    from sfrfr.integrations.max.client import inline_buttons_keyboard

    attachments = inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": "Позвать специалиста",
                    "payload": "intake:operator",
                }
            ],
        ]
    )

    enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=attachments,
    )
    _OFFERED_DOCS.add(cid)
    return {"order": order, "offered": True, "tariff": "DOCS"}


def maybe_offer_support_invoice(
    *,
    case_id: str,
    max_user_id: str | None = None,
    intake: Any | None = None,
    case: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Черновик SUPPORT 8000 после DOCS paid + проект обращения."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    cid = str(case_id or "").strip()
    if not cid or cid in _OFFERED_SUPPORT:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery

    repo = CaseRepository()
    try:
        row = case or repo.get_case_row(cid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("support offer case load failed: %s", exc)
        return None
    if not row:
        return None
    if not repo.has_consent(cid):
        return None
    clients = row.get("clients") or {}
    if isinstance(clients, list):
        clients = clients[0] if clients else {}
    mid = str(max_user_id or (clients or {}).get("max_user_id") or "").strip()
    if not mid:
        return None
    if intake is None:
        from sfrfr.integrations.max.intake import get_intake_store

        intake = get_intake_store().get_active(mid)
    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        orders = []
    if not _gates_support(
        case=row, orders=orders, intake=intake, require_bot_owned=False
    ):
        return None

    tariff = public_tariff("SUPPORT") or {}
    amount = float(tariff.get("amount_rub") or 8000)
    label = str(tariff.get("name") or "Шаг 3. Сопровождение до подачи")
    try:
        order = repo.create_order(
            cid,
            package_code="ACCOMP",
            amount_rub=amount,
            status_value="draft",
            actor_id="bot:max_owned",
            due_at=(datetime.now(UTC) + timedelta(days=3)).isoformat(),
            service_label=label,
            invoice_status="draft",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("support draft create failed case=%s: %s", cid[:8], exc)
        return None

    cab = cabinet_url_for_case(cid)
    body = (
        f"Шаг 3 — сопровождение до подачи, {int(amount)} ₽: "
        "доводим проект обращения и пошаговый план.\n"
        "Подачу через СФР / Госуслуги / МФЦ делаете вы; мы рядом с планом и ответами по шагам.\n"
        "Можно остаться на шаге 2, если хотите подать сами по уже готовому комплекту.\n"
        "Чтобы выставить счёт, примите условия в кабинете.\n"
        f"Кабинет: {cab}"
    )
    enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=None,
    )
    _OFFERED_SUPPORT.add(cid)
    return {"order": order, "offered": True, "tariff": "SUPPORT"}


def resolve_offer_cta(label: str) -> str | None:
    """offer:appeals | offer:docs | offer:support | offer:docs_skip | None."""
    low = " ".join(str(label or "").lower().split())
    if not low:
        return None
    if low in _CTA_SKIP or any(k in low for k in ("сам по плану", "подам сам")):
        return "offer:docs_skip"
    if low in _CTA_SUPPORT or "сопровожден" in low or "шаг 3" in low:
        return "offer:support"
    if low in _CTA_APPEALS or "обращени" in low or "составьт" in low:
        return "offer:appeals"
    if low in _CTA_DOCS or "шаг 2" in low or "подготовк" in low:
        return "offer:docs"
    return None


def _offer_docs_or_remind(
    *,
    case_id: str,
    max_user_id: str,
    intake: Any | None,
) -> dict[str, Any] | None:
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery

    repo = CaseRepository()
    try:
        orders = repo.list_orders(case_id)
    except Exception:  # noqa: BLE001
        orders = []
    existing = _find_open_order(orders, tariff="DOCS")
    if existing:
        cab = cabinet_url_for_case(case_id)
        enqueue_max_delivery(
            case_id=case_id,
            message_id=None,
            max_user_id=max_user_id,
            body=(
                "Счёт на подготовку документов и проектов обращений уже подготовлен. "
                f"Примите условия в кабинете, затем оплатите: {cab}"
            ),
            attachments=None,
        )
        return {"order": existing, "reminded": True, "tariff": "DOCS"}
    return maybe_offer_docs_invoice(
        case_id=case_id,
        max_user_id=max_user_id,
        intake=intake,
        require_cta=True,
    )


def handle_offer_callback(
    *,
    case_id: str,
    max_user_id: str,
    payload: str,
    intake: Any | None = None,
) -> dict[str, Any] | None:
    """Обработка offer:* — создание счёта по воротам или уважение отказа."""
    pl = str(payload or "").strip().lower()
    if pl == "offer:docs_skip":
        return {"skipped": True, "tariff": "DOCS"}
    if pl in {"offer:docs", "offer:appeals"}:
        return _offer_docs_or_remind(
            case_id=case_id, max_user_id=max_user_id, intake=intake
        )
    if pl == "offer:support":
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.services.case_chat_delivery import enqueue_max_delivery

        repo = CaseRepository()
        try:
            orders = repo.list_orders(case_id)
        except Exception:  # noqa: BLE001
            orders = []
        existing = _find_open_order(orders, tariff="SUPPORT")
        if existing:
            cab = cabinet_url_for_case(case_id)
            enqueue_max_delivery(
                case_id=case_id,
                message_id=None,
                max_user_id=max_user_id,
                body=(
                    "Счёт на сопровождение уже подготовлен. "
                    f"Примите условия в кабинете: {cab}"
                ),
                attachments=None,
            )
            return {"order": existing, "reminded": True, "tariff": "SUPPORT"}
        return maybe_offer_support_invoice(
            case_id=case_id,
            max_user_id=max_user_id,
            intake=intake,
        )
    return None


def maybe_send_pay_link_after_contract(
    *,
    repo: Any,
    case_id: str,
    actor_id: str | None,
) -> dict[str, Any] | None:
    """После contract_accepted: pay link в MAX для открытого DIAG/DOCS/SUPPORT."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled or not settings.max_bot_owned_pay_link:
        return None
    cid = str(case_id or "").strip()
    if not cid:
        return None
    try:
        case = repo.get_case_row(cid) if hasattr(repo, "get_case_row") else None
    except Exception:  # noqa: BLE001
        case = None
    if not case:
        return None
    clients = case.get("clients") or {}
    if isinstance(clients, list):
        clients = clients[0] if clients else {}
    max_uid = str((clients or {}).get("max_user_id") or "").strip()
    if not max_uid:
        return None

    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        return None

    target = None
    for tariff in ("SUPPORT", "DOCS", "DIAG"):
        target = _find_open_order(orders, tariff=tariff)
        if target:
            break
    if not target:
        return None

    from sfrfr.services.pay_link import PayLinkError, issue_and_deliver_pay_link

    try:
        return issue_and_deliver_pay_link(
            repo=repo,
            order=target,
            case=case,
            actor_id=actor_id,
            send_max=True,
            channel="max_bot_owned",
        )
    except PayLinkError as exc:
        logger.warning("bot_owned pay_link failed case=%s code=%s", cid[:8], exc.code)
        return None
    except Exception:  # noqa: BLE001
        logger.exception("bot_owned pay_link error case=%s", cid[:8])
        return None


def maybe_offer_after_diagnosis_delivered(*, case_id: str) -> dict[str, Any] | None:
    """Хук после link_issued: рекомендации + оффер отдельных обращений (без счёта)."""
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.max_post_diagnosis import maybe_send_post_diagnosis_next_steps

    cid = str(case_id or "").strip()
    if not cid:
        return None
    repo = CaseRepository()
    try:
        row = repo.get_case_row(cid) or {}
    except Exception:  # noqa: BLE001
        row = {}
    enriched = dict(row)
    enriched["diagnosis_delivered"] = True
    return maybe_send_post_diagnosis_next_steps(case_id=cid, case=enriched)


def reset_offer_cache() -> None:
    _OFFERED.clear()
    _OFFERED_DOCS.clear()
    _OFFERED_SUPPORT.clear()
    from sfrfr.services.max_post_diagnosis import reset_post_diagnosis_cache

    reset_post_diagnosis_cache()
