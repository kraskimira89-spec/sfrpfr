"""После выдачи диагностики: краткие рекомендации и оффер отдельных обращений в СФР.

Оплату (DOCS 5000) предлагаем только после согласия клиента.
Обращения не склеиваем в одно — по одному простому вопросу на обращение.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.intake import cabinet_url_for_case
from sfrfr.services.funnel_board import diagnosis_delivered_from_case, tariff_states

logger = logging.getLogger(__name__)

_OFFERED_NEXT: set[str] = set()

_PDN_RE = re.compile(
    r"(?i)(\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b|"
    r"снилс|паспорт|илс\s*№|сумма пенсии|прибавка)"
)

APPEALS_CTA_PAYLOAD = "offer:appeals"


def reset_post_diagnosis_cache() -> None:
    _OFFERED_NEXT.clear()


def sanitize_finding_line(text: str, *, max_len: int = 120) -> str:
    raw = " ".join(str(text or "").split())
    raw = _PDN_RE.sub("…", raw)
    if len(raw) > max_len:
        raw = raw[: max_len - 1].rstrip() + "…"
    return raw


def brief_recommendations_from_findings(
    findings: list[dict[str, Any]] | None,
    *,
    limit: int = 5,
) -> list[str]:
    """Короткие строки для MAX: проблемы / расхождения без ПДн и сумм пенсии."""
    out: list[str] = []
    for row in findings or []:
        if not isinstance(row, dict):
            continue
        severity = str(row.get("severity") or "").lower()
        ftype = str(row.get("type") or "").lower()
        detail = sanitize_finding_line(str(row.get("detail") or ""))
        if not detail:
            continue
        # приоритет расхождениям / вопросам
        interesting = (
            severity in {"warn", "warning", "error", "high", "critical", "red"}
            or any(
                k in ftype
                for k in ("discrep", "gap", "miss", "расхожд", "вопрос", "conflict")
            )
            or any(
                k in detail.lower()
                for k in ("расхожд", "не учт", "нет в илс", "не отраж", "вопрос", "уточн")
            )
        )
        if not interesting and severity in {"info", ""}:
            # всё равно берём, если мало строк
            if len(out) >= 2:
                continue
        out.append(detail)
        if len(out) >= limit:
            break
    return out


def build_post_diagnosis_next_steps_text(
    *,
    recommendations: list[str] | None = None,
) -> str:
    """Текст без цены: рекомендации + предложение составить отдельные обращения."""
    lines: list[str] = [
        "Кратко по итогам диагностики:",
    ]
    recs = [r for r in (recommendations or []) if r]
    if recs:
        for i, item in enumerate(recs, start=1):
            lines.append(f"{i}. {item}")
    else:
        lines.append(
            "в PDF отмечены вопросы и расхождения по периодам и документам — "
            "откройте результат в кабинете для полного плана."
        )
    lines.extend(
        [
            "",
            "Рекомендуем подготовить обращения в СФР по найденным вопросам.",
            "Важно: не склеивать всё в одно письмо — делаем несколько простых "
            "обращений (по одному вопросу), так проще отслеживать ответы СФР.",
            "",
            "Мы можем подготовить проекты таких обращений и комплекты приложений; "
            "подаёте через СФР / Госуслуги / МФЦ вы сами. Решение принимает только СФР.",
            "",
            "Составить обращения?",
        ]
    )
    return "\n".join(lines)


def build_docs_invoice_after_appeals_text(*, amount: int, cabinet_url: str) -> str:
    from sfrfr.core.copy import PAYMENT_LEGAL_ACCEPTANCE

    return (
        "Хорошо — подготовим проекты обращений в СФР: каждое обращение "
        "по одному вопросу или периоду, без «сборной» заявки.\n"
        f"Шаг 2 — подготовка документов и проектов обращений, {amount} ₽.\n"
        "Решение о пенсии принимает только СФР; мы готовим документы и план — "
        "подаёте вы сами.\n"
        "Чтобы выставить счёт, примите условия в кабинете — "
        f"после этого пришлём ссылку на оплату в этот чат.\n"
        f"{PAYMENT_LEGAL_ACCEPTANCE}\n"
        f"Кабинет: {cabinet_url}"
    )


def maybe_send_post_diagnosis_next_steps(
    *,
    case_id: str,
    case: dict[str, Any] | None = None,
    max_user_id: str | None = None,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """После выдачи PDF: рекомендации + CTA на обращения. Без счёта."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    cid = str(case_id or "").strip()
    if not cid or cid in _OFFERED_NEXT:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.integrations.max.client import inline_buttons_keyboard
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery

    repo = CaseRepository()
    try:
        row = case or repo.get_case_row(cid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("post-diagnosis case load failed: %s", exc)
        return None
    if not row:
        return None
    enriched = dict(row)
    if case and case.get("diagnosis_delivered"):
        enriched["diagnosis_delivered"] = True
    if not diagnosis_delivered_from_case(enriched):
        return None
    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        orders = []
    st = tariff_states(orders)
    if st["DIAG"] != "paid":
        return None
    if st["DOCS"] != "none" or st["SUPPORT"] != "none":
        return None
    if not repo.has_consent(cid):
        return None

    clients = enriched.get("clients") or {}
    if isinstance(clients, list):
        clients = clients[0] if clients else {}
    mid = str(max_user_id or (clients or {}).get("max_user_id") or "").strip()
    if not mid:
        return None

    loaded = findings
    if loaded is None:
        try:
            loaded = repo.get_pipeline_findings(cid)
        except Exception:  # noqa: BLE001
            loaded = []

    recs = brief_recommendations_from_findings(loaded)
    body = build_post_diagnosis_next_steps_text(recommendations=recs)
    attachments = inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": "Составьте обращения",
                    "payload": APPEALS_CTA_PAYLOAD,
                }
            ],
            [{"type": "callback", "text": "Сам по плану", "payload": "offer:docs_skip"}],
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
    _OFFERED_NEXT.add(cid)
    return {"sent": True, "recommendations": recs, "cabinet": cabinet_url_for_case(cid)}
