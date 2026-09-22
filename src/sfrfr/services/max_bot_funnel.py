"""Bot-owned воронка MAX: документы → анализ → счёт → оплата/чек → план со специалистом.

Канон шагов (единый чат MAX ↔ кабинет по case_id):

1. Принять документы (чат или кабинет).
2. Если комплект неполный — запросить недостающее (без OCR-текста клиенту).
3. Согласие ПДн / оферта → счёт DIAG → pay link или чек.
4. Подтвердить оплату.
5. После сверки — расхождения пунктами; иначе дозапрос документов.
6. Согласовать план со специалистом (задача staff + ответ клиенту).

LLM не двигает деньги; счета и статусы — детерминированный код.
"""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.bot_owned import is_bot_owned
from sfrfr.integrations.max.intake import CALL_OPERATOR_LABEL, cabinet_url_for_case
from sfrfr.services.max_post_diagnosis import (
    brief_recommendations_from_findings,
    sanitize_finding_line,
)

logger = logging.getLogger(__name__)

AGREE_PLAN_PAYLOAD = "funnel:agree_plan"
AGREE_PLAN_LABEL = "Согласовать план со специалистом"

_FINDINGS_SENT: dict[str, str] = {}
_PAID_FUNNEL: set[str] = set()
_PLAN_AGREED: set[str] = set()


def reset_funnel_cache() -> None:
    _FINDINGS_SENT.clear()
    _PAID_FUNNEL.clear()
    _PLAN_AGREED.clear()


def _max_uid_from_case(case: dict[str, Any] | None) -> str | None:
    if not case:
        return None
    clients = case.get("clients") or {}
    if isinstance(clients, list):
        clients = clients[0] if clients else {}
    mid = str((clients or {}).get("max_user_id") or "").strip()
    return mid or None


def _intake_for(max_user_id: str | None) -> Any | None:
    if not max_user_id:
        return None
    try:
        from sfrfr.integrations.max.intake import get_intake_store

        return get_intake_store().get_active(str(max_user_id))
    except Exception:  # noqa: BLE001
        return None


def funnel_keyboard(*, include_agree_plan: bool = True) -> list[dict[str, Any]]:
    from sfrfr.integrations.max.client import inline_buttons_keyboard

    rows: list[list[dict[str, Any]]] = []
    if include_agree_plan:
        rows.append(
            [{"type": "callback", "text": AGREE_PLAN_LABEL, "payload": AGREE_PLAN_PAYLOAD}]
        )
    rows.append(
        [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}]
    )
    return inline_buttons_keyboard(rows)


def build_consent_nudge_text(*, case_id: str) -> str:
    cab = cabinet_url_for_case(case_id)
    return (
        "Базовый комплект документов есть. "
        "Чтобы выставить счёт на диагностику (3 000 ₽) и продолжить сверку, "
        "нужно согласие на обработку данных и принятие условий в кабинете на сайте.\n"
        f"Кабинет: {cab}\n"
        "После этого пришлём ссылку на оплату в этот чат. "
        "Файлы можно присылать сюда или загружать в «Мои документы»."
    )


def nudge_consent_before_invoice(
    *,
    case_id: str,
    max_user_id: str,
    intake: Any | None = None,
) -> dict[str, Any] | None:
    """Если комплект готов, но нет согласия — напомнить про кабинет (не молчать)."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    if intake is None:
        intake = _intake_for(max_user_id)
    if not is_bot_owned(intake):
        return None
    cid = str(case_id or "").strip()
    mid = str(max_user_id or "").strip()
    if not cid or not mid:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery

    repo = CaseRepository()
    if repo.has_consent(cid):
        return None
    body = build_consent_nudge_text(case_id=cid)
    ok = enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=funnel_keyboard(include_agree_plan=False),
    )
    return {"ok": bool(ok), "nudged": "consent"}


def build_findings_message(
    *,
    findings: list[dict[str, Any]] | None,
    missing_docs: list[str] | None = None,
) -> str:
    """Пункты расхождений или дозапрос документов (без ПДн и сумм пенсии)."""
    lines = ["По сверке документов:"]
    bullets = brief_recommendations_from_findings(findings, limit=6)
    if not bullets and findings:
        for row in findings[:6]:
            if not isinstance(row, dict):
                continue
            detail = sanitize_finding_line(str(row.get("detail") or row.get("type") or ""))
            if detail:
                bullets.append(detail)
    if bullets:
        for i, item in enumerate(bullets, start=1):
            lines.append(f"{i}. {item}")
    else:
        lines.append(
            "явных расхождений в автоматической сверке пока нет — "
            "специалист уточнит нюансы по комплекту."
        )
    missing = [m for m in (missing_docs or []) if m]
    if missing:
        lines.append("")
        lines.append("Ещё желательно прислать:")
        for m in missing:
            lines.append(f"• {m}")
        lines.append("Можно сюда в чат или через «Мои документы» на сайте.")
    lines.extend(
        [
            "",
            "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
            "Решение принимает только СФР.",
            "",
            "Можно согласовать план работы со специалистом кнопкой ниже.",
        ]
    )
    return "\n".join(lines)


def _missing_docs_hints(
    *,
    findings: list[dict[str, Any]] | None,
    have_buckets: set[str] | None = None,
) -> list[str]:
    missing: list[str] = []
    have = have_buckets or set()
    if "ils" not in have:
        missing.append("выписка ИЛС")
    if "labor" not in have:
        missing.append("трудовая книжка (скан или электронная)")
    blob = " ".join(
        str((f or {}).get("detail") or (f or {}).get("type") or "").lower()
        for f in (findings or [])
        if isinstance(f, dict)
    )
    if "архив" in blob or "справк" in blob:
        missing.append("архивная справка по спорному периоду (если есть)")
    if "север" in blob:
        missing.append("документы, подтверждающие северный стаж (если есть)")
    # уникальные, порядок сохраняем
    seen: set[str] = set()
    out: list[str] = []
    for item in missing:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def notify_analysis_findings(
    *,
    case_id: str,
    findings: list[dict[str, Any]] | None = None,
    max_user_id: str | None = None,
    force: bool = False,
) -> dict[str, Any] | None:
    """После audited / snapshot: пункты расхождений или дозапрос в MAX (bot_owned)."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    cid = str(case_id or "").strip()
    if not cid:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery
    from sfrfr.services.funnel_board import tariff_states
    from sfrfr.services.max_kit_status import collect_case_doc_buckets

    repo = CaseRepository()
    try:
        case = repo.get_case_row(cid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("funnel findings case load failed: %s", exc)
        return None
    mid = str(max_user_id or _max_uid_from_case(case) or "").strip()
    if not mid:
        return None
    intake = _intake_for(mid)
    if not is_bot_owned(intake):
        return None

    try:
        orders = repo.list_orders(cid)
    except Exception:  # noqa: BLE001
        orders = []
    # Полный разбор клиенту — после оплаты диагностики (или force для тестов)
    if not force and tariff_states(orders).get("DIAG") != "paid":
        return None

    rows = findings
    if rows is None:
        try:
            rows = repo.get_pipeline_findings(cid)
        except Exception:  # noqa: BLE001
            rows = []
    rows = list(rows or [])
    try:
        docs = repo.list_documents(cid)
    except Exception:  # noqa: BLE001
        docs = []
    have = collect_case_doc_buckets(list(docs or []))
    missing = _missing_docs_hints(findings=rows, have_buckets=have)

    fp = f"{len(rows)}:{'|'.join(sanitize_finding_line(str(r.get('detail') or ''), max_len=40) for r in rows[:5] if isinstance(r, dict))}"
    if not force and _FINDINGS_SENT.get(cid) == fp:
        return None

    body = build_findings_message(findings=rows, missing_docs=missing)
    ok = enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=funnel_keyboard(include_agree_plan=True),
    )
    if ok:
        _FINDINGS_SENT[cid] = fp
    return {"ok": bool(ok), "findings": len(rows), "missing": missing}


def after_payment_confirmed(
    *,
    case_id: str,
    package_code: str | None = None,
    source: str = "yookassa",
) -> dict[str, Any] | None:
    """После оплаты/чека: подтверждение + старт сверки + задача специалисту."""
    settings = get_settings()
    if not settings.max_bot_owned_enabled:
        return None
    cid = str(case_id or "").strip()
    if not cid or cid in _PAID_FUNNEL:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery
    from sfrfr.services.finance_automation import ensure_staff_task

    repo = CaseRepository()
    try:
        case = repo.get_case_row(cid)
    except Exception:  # noqa: BLE001
        case = None
    mid = _max_uid_from_case(case)
    intake = _intake_for(mid)
    if not is_bot_owned(intake):
        return None

    code = (package_code or "").upper()
    # Подтверждение оплаты уже шлёт notify_payment_succeeded — здесь только следующий шаг.
    lines: list[str] = []
    if code == "DIAG":
        lines.extend(
            [
                "Следующий шаг: сверим ИЛС и трудовую.",
                "Пришлём найденные расхождения по пунктам или запросим недостающие документы.",
                "После сверки можно согласовать план работы со специалистом.",
            ]
        )
        try:
            ensure_staff_task(
                repo,
                cid,
                title="Провести диагностику (bot_owned)",
                item_type="action",
                due_at=None,
                actor_id="bot:max_funnel",
                note="После оплаты DIAG — сверка и план",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("funnel staff after pay skipped: %s", exc)
    elif code == "ACCOMP":
        lines.append(
            "Следующий шаг: подготовка документов и проектов обращений. "
            "Можно согласовать план со специалистом кнопкой ниже."
        )
        try:
            ensure_staff_task(
                repo,
                cid,
                title="Согласовать план после оплаты ACCOMP",
                item_type="action",
                due_at=None,
                actor_id="bot:max_funnel",
            )
        except Exception:  # noqa: BLE001
            pass
    else:
        lines.append("Специалист продолжит работу по делу в этом чате.")

    if lines and mid:
        lines.extend(
            [
                "",
                "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
                "Решение принимает СФР.",
            ]
        )
        enqueue_max_delivery(
            case_id=cid,
            message_id=None,
            max_user_id=mid,
            body="\n".join(lines),
            attachments=funnel_keyboard(include_agree_plan=True),
        )
    _PAID_FUNNEL.add(cid)
    return {"ok": True, "case_id": cid, "package_code": code, "source": source}


def agree_plan_with_specialist(
    *,
    case_id: str,
    max_user_id: str,
    intake: Any | None = None,
) -> dict[str, Any]:
    """Клиент просит согласовать план: задача staff + ответ в чат."""
    cid = str(case_id or "").strip()
    mid = str(max_user_id or "").strip()
    if not cid or not mid:
        return {"ok": False, "reason": "missing ids"}

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery
    from sfrfr.services.finance_automation import ensure_staff_task

    if intake is None:
        intake = _intake_for(mid)

    repo = CaseRepository()
    created = False
    try:
        created = ensure_staff_task(
            repo,
            cid,
            title="Согласовать план работы с клиентом",
            item_type="action",
            due_at=None,
            actor_id="bot:max_funnel",
            note="Клиент нажал «Согласовать план» в MAX",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("agree_plan staff task failed: %s", exc)

    try:
        repo.update_next_action(
            cid,
            "bot:max_funnel",
            next_action="Согласовать план с клиентом",
            waiting_on="staff",
        )
    except Exception:  # noqa: BLE001
        pass

    # Передаём специалисту (как operator), но оставляем понятный ответ клиенту
    try:
        from sfrfr.integrations.max.intake import get_intake_store

        store = get_intake_store()
        rec = intake or store.get_active(mid)
        if rec is not None and str(getattr(rec, "status", "") or "") != "handed_to_operator":
            rec.status = "handed_to_operator"
            store.save(rec)
    except Exception:  # noqa: BLE001
        pass

    body = (
        "Передали запрос специалисту: согласуем план работы по вашему делу в этом чате. "
        "Пока можно дослать недостающие файлы сюда или в кабинет на сайте."
    )
    enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=None,
    )
    _PLAN_AGREED.add(cid)
    return {"ok": True, "task_created": created, "handed_to_operator": True}


def handle_funnel_callback(
    *,
    case_id: str,
    max_user_id: str,
    payload: str,
    intake: Any | None = None,
) -> dict[str, Any] | None:
    pl = str(payload or "").strip().lower()
    if pl == AGREE_PLAN_PAYLOAD or pl == "intake:agree_plan":
        return agree_plan_with_specialist(
            case_id=case_id, max_user_id=max_user_id, intake=intake
        )
    return None
