"""Контекст единого чата для LLM: история переписки и стадия сделки без ПДн."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.ai.guardrails import redact_for_llm

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 20
MAX_BODY_CHARS = 400
STAFF_ACTIVE_WINDOW = timedelta(minutes=30)

_AUTHOR_LABELS: dict[str, str] = {
    "client": "Клиент",
    "representative": "Представитель",
    "staff": "Специалист",
    "system": "Бот",
    "bot": "Бот",
}

_EXPERIENCE_LABELS: dict[str, str] = {
    "lt5": "до 5 лет",
    "5_10": "5–10 лет",
    "10_20": "10–20 лет",
    "gt20": "более 20 лет",
    "unknown": "не указан точно",
}


def author_label(author_kind: str | None) -> str:
    kind = str(author_kind or "unknown").strip().lower()
    return _AUTHOR_LABELS.get(kind, "Участник")


def fetch_recent_case_messages(
    case_id: str,
    *,
    limit: int = DEFAULT_HISTORY_LIMIT,
    exclude_message_id: str | None = None,
) -> list[dict[str, Any]]:
    """Последние реплики дела (хронологически), без текущего сообщения."""
    cid = (case_id or "").strip()
    if not cid:
        return []
    try:
        from sfrfr.db.session import get_supabase_client

        cap = max(1, min(int(limit), 40))
        rows = (
            get_supabase_client()
            .table("case_messages")
            .select("id, author_kind, body, created_at")
            .eq("case_id", cid)
            .order("created_at", desc=True)
            .limit(cap + (1 if exclude_message_id else 0))
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("case_chat_context fetch skipped case=%s: %s", cid[:8], exc)
        return []
    out: list[dict[str, Any]] = []
    ex = (exclude_message_id or "").strip()
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        if ex and str(row.get("id") or "") == ex:
            continue
        body = str(row.get("body") or "").strip()
        if not body:
            continue
        out.append(row)
        if len(out) >= cap:
            break
    return out


def format_thread_for_llm(
    messages: list[dict[str, Any]],
    *,
    max_body_chars: int = MAX_BODY_CHARS,
) -> str:
    """Лента «Кто: текст» для промпта (обезличено)."""
    lines: list[str] = []
    for row in messages:
        if not isinstance(row, dict):
            continue
        body = redact_for_llm(str(row.get("body") or "")).strip()
        if not body:
            continue
        label = author_label(str(row.get("author_kind") or ""))
        lines.append(f"{label}: {body[:max_body_chars]}")
    if not lines:
        return "(история пуста — это первое сообщение в теме)"
    return "\n".join(lines)


def format_deal_context(work: dict[str, Any] | None, *, staff_chat: bool = False) -> str:
    """Стадия дела, CTA и оплата — для клиентского и staff LLM."""
    if not work:
        return "Стадия дела: неизвестна (дело ещё не создано или нет данных)."
    order = work.get("order") if isinstance(work.get("order"), dict) else {}
    now_need = str(work.get("now_need") or "—")
    cta_key = str(work.get("cta_key") or "—")
    cta_label = str(work.get("cta_label") or "—")
    if staff_chat and (
        cta_key == "consent"
        or "соглас" in now_need.lower()
        or "соглас" in cta_label.lower()
    ):
        now_need = "Документы / следующий шаг по делу (согласие на ПДн уже получено в MAX)"
        cta_key = "docs_max"
        cta_label = "Прислать файлы в чат MAX"
    parts = [
        f"Статус: {work.get('status_label') or '—'} ({work.get('status_key') or '—'})",
        f"Сейчас нужно от клиента: {now_need}",
        (
            f"Документы (обязательные): "
            f"{work.get('required_uploaded', 0)}/{work.get('required_total', 0)}"
        ),
        f"Следующий шаг (cta): {cta_key} — {cta_label}",
        f"SLA: {work.get('sla_note') or '—'}",
    ]
    if order:
        parts.append(
            f"Услуга: {order.get('title') or '—'}; "
            f"сумма {order.get('amount_rub') or '—'} ₽; "
            f"статус счёта: {order.get('status_label') or order.get('state') or '—'}; "
            f"можно оплатить: {'да' if order.get('can_pay') else 'нет'}"
        )
    next_actions = work.get("next_actions") or []
    if isinstance(next_actions, list) and next_actions:
        cleaned = [str(a) for a in next_actions[:4]]
        if staff_chat:
            cleaned = [
                a
                for a in cleaned
                if "соглас" not in a.lower() and "кабинет" not in a.lower()
            ]
        if cleaned:
            parts.append("Плановые шаги: " + "; ".join(cleaned))
    return "\n".join(parts)


def _confirmed_from_intake(intake: Any | None) -> list[str]:
    """Уже известные факты анкеты/FSM без сырых ПДн (телефон/email только флаг)."""
    if intake is None:
        return []
    out: list[str] = []
    answers = getattr(intake, "q_answers", None) or {}
    if isinstance(answers, dict):
        exp = str(answers.get("experience") or "").strip()
        if exp:
            out.append(f"стаж: {_EXPERIENCE_LABELS.get(exp, exp)}")
        if str(answers.get("phone") or "").strip():
            out.append("телефон: указан")
        if str(answers.get("email") or "").strip():
            out.append("email: указан")
        problem = redact_for_llm(str(answers.get("problem") or "")).strip()
        if problem:
            out.append(f"проблема своими словами: {problem[:180]}")
        if getattr(intake, "q_completed_at", None):
            out.append("короткая анкета: завершена")
    for_whom = getattr(intake, "for_whom", None)
    if for_whom:
        out.append(f"для кого: {for_whom}")
    pension = getattr(intake, "pension_status", None)
    if pension:
        out.append(f"пенсия: {pension}")
    goal = getattr(intake, "goal", None)
    if goal:
        out.append(f"цель (goal): {goal}")
    problem_type = getattr(intake, "problem_type", None)
    if problem_type:
        out.append(f"тип проблемы: {problem_type}")
    ils = getattr(intake, "ils_available", None)
    if ils:
        out.append(f"ИЛС: {ils}")
    emp = getattr(intake, "employment_records_available", None)
    if emp:
        out.append(f"трудовая/записи: {emp}")
    return out


def _document_buckets(
    *,
    work: dict[str, Any] | None,
    documents: list[dict[str, Any]] | None,
    max_user_id: str | None,
) -> dict[str, list[str]]:
    available: list[str] = []
    pending: list[str] = []
    failed: list[str] = []
    for doc in documents or []:
        if not isinstance(doc, dict):
            continue
        name = str(doc.get("doc_type") or doc.get("filename") or "файл")[:40]
        status = str(doc.get("ingest_status") or "").lower()
        cloud = str(doc.get("cloud_status") or "").lower()
        if status in {"blocked_security", "failed"} or cloud == "failed":
            failed.append(name)
        elif status in {"needs_reupload", "uploading", "security_check"} or cloud == "pending":
            pending.append(f"{name} (ожидает)")
        elif doc.get("id"):
            # Только факт вложения — без «изучено»
            available.append(f"{name} (файл в деле, содержание не передано модели)")
    if work:
        req_u = int(work.get("required_uploaded") or 0)
        req_t = int(work.get("required_total") or 0)
        if req_t:
            available.append(f"обязательных слотов: {req_u}/{req_t}")
    uid = str(max_user_id or "").strip()
    if uid:
        try:
            from sfrfr.integrations.max import attachment_lifecycle as life

            for job in life.list_jobs():
                if str(job.get("user_id") or "") != uid:
                    continue
                stage = str(job.get("stage") or "")
                hint = str(job.get("filename") or "вложение")[:40]
                if stage in {"awaiting_bytes", "discovered", "saved"}:
                    pending.append(f"{hint} (скачивание)")
                elif stage == "failed":
                    failed.append(f"{hint} (не получено)")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context pack attach jobs skipped: %s", exc)
    return {
        "available": available[:12],
        "pending": pending[:12],
        "failed": failed[:12],
    }


def staff_dialog_active(history: list[dict[str, Any]] | None) -> bool:
    if not history:
        return False
    cutoff = datetime.now(UTC) - STAFF_ACTIVE_WINDOW
    for row in reversed(history):
        if not isinstance(row, dict):
            continue
        if str(row.get("author_kind") or "").lower() != "staff":
            continue
        raw = str(row.get("created_at") or "").strip()
        if not raw:
            return True
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            return ts >= cutoff
        except ValueError:
            return True
    return False


def _conversation_stage(
    *,
    work: dict[str, Any] | None,
    intake: Any | None,
    consent_ok: bool,
) -> str:
    if not consent_ok:
        return "consent"
    if intake is not None and getattr(intake, "q_step", None) and not getattr(
        intake, "q_completed_at", None
    ):
        return "intake"
    cta = str((work or {}).get("cta_key") or "").strip().lower()
    if cta in {"pay", "pay_link"}:
        return "offer_analysis"
    if cta in {"docs", "docs_max", "upload"}:
        return "collecting_documents"
    status = str((work or {}).get("status_key") or "").strip().lower()
    if "review" in status or "diagn" in status:
        return "preliminary_review"
    if intake is not None and intake.step() not in {"summary", "whom"}:
        return f"intake:{intake.step()}"
    return "collecting_documents" if consent_ok else "consent"


def build_client_context_pack(
    *,
    channel: str,
    user_text: str,
    work: dict[str, Any] | None,
    history: list[dict[str, Any]] | None = None,
    intake: Any | None = None,
    intake_step: str | None = None,
    documents: list[dict[str, Any]] | None = None,
    max_user_id: str | None = None,
    consent_accepted: bool | None = None,
) -> dict[str, Any]:
    """Серверный ContextPack для клиентского LLM (без сырых ПДн и без текста сканов)."""
    consent_ok = bool(consent_accepted) if consent_accepted is not None else True
    if work and "consent" in str(work.get("cta_key") or "").lower():
        consent_ok = False
    docs = _document_buckets(work=work, documents=documents, max_user_id=max_user_id)
    confirmed = _confirmed_from_intake(intake)
    staff_active = staff_dialog_active(history)
    order = work.get("order") if isinstance((work or {}).get("order"), dict) else {}
    payment_status = str(
        (order or {}).get("status_label")
        or (order or {}).get("state")
        or "нет заказа"
    )
    next_step = str((work or {}).get("now_need") or (work or {}).get("cta_label") or "—")
    stage = _conversation_stage(work=work, intake=intake, consent_ok=consent_ok)
    return {
        "channel": channel,
        "conversation_stage": stage,
        "consent_status": "accepted" if consent_ok else "needed",
        "confirmed_fields": confirmed,
        "client_goal": str(getattr(intake, "goal", None) or (work or {}).get("cta_label") or "—"),
        "intake_step": intake_step or (intake.step() if intake is not None else None),
        "documents": docs,
        "document_content_available_to_model": False,
        "payment_status_trusted": payment_status,
        "can_pay": bool((order or {}).get("can_pay")),
        "next_allowed_step": next_step,
        "staff_dialog_active": staff_active,
        "user_text_redacted": redact_for_llm(user_text or "")[:1500],
        "history": history or [],
        "work": work,
    }


def format_context_pack_for_prompt(pack: dict[str, Any]) -> str:
    """Текстовый блок ContextPack для user-prompt."""
    docs = pack.get("documents") if isinstance(pack.get("documents"), dict) else {}
    confirmed = pack.get("confirmed_fields") or []
    lines = [
        f"Стадия диалога: {pack.get('conversation_stage')}",
        f"Согласие ПДн: {pack.get('consent_status')}",
        f"Цель клиента: {pack.get('client_goal')}",
        f"Следующий разрешённый шаг: {pack.get('next_allowed_step')}",
        f"Оплата (только доверенный статус сервера): {pack.get('payment_status_trusted')}; "
        f"can_pay={'да' if pack.get('can_pay') else 'нет'}",
        f"Активный диалог со специалистом: "
        f"{'да — не дублируй специалиста' if pack.get('staff_dialog_active') else 'нет'}",
        "Содержание документов модели НЕ передано "
        "(есть только факт вложения / тип / статус).",
    ]
    if pack.get("intake_step"):
        lines.append(f"Шаг кнопок intake: {pack.get('intake_step')}")
    if confirmed:
        lines.append("Уже известно (не спрашивай повторно): " + "; ".join(confirmed))
    else:
        lines.append("Уже известно: (пока пусто)")
    lines.append(
        "Документы available: "
        + (", ".join(docs.get("available") or []) or "—")
    )
    lines.append(
        "Документы pending: " + (", ".join(docs.get("pending") or []) or "—")
    )
    lines.append(
        "Документы failed: " + (", ".join(docs.get("failed") or []) or "—")
    )
    return "\n".join(lines)


def build_client_llm_user_prompt(
    *,
    channel: str,
    user_text: str,
    work: dict[str, Any] | None,
    history: list[dict[str, Any]] | None = None,
    intake_step: str | None = None,
    exclude_message_id: str | None = None,
    intake: Any | None = None,
    documents: list[dict[str, Any]] | None = None,
    max_user_id: str | None = None,
    consent_accepted: bool | None = None,
    context_pack: dict[str, Any] | None = None,
) -> str:
    """Единый user-prompt для клиентского бота (MAX / кабинет)."""
    del exclude_message_id  # история уже отфильтрована вызывающим
    pack = context_pack or build_client_context_pack(
        channel=channel,
        user_text=user_text,
        work=work,
        history=history,
        intake=intake,
        intake_step=intake_step,
        documents=documents,
        max_user_id=max_user_id,
        consent_accepted=consent_accepted,
    )
    safe = str(pack.get("user_text_redacted") or redact_for_llm(user_text or "")[:1500])
    thread = format_thread_for_llm(history or [])
    deal = format_deal_context(work)
    header = {
        "cabinet": (
            "Клиент пишет из веб-кабинета (единый чат с MAX; "
            "файлы — в чат MAX или в личном кабинете на сайте)."
        ),
        "max": (
            "Клиент пишет в MAX (уже в чате бота — не предлагай уходить "
            "в веб-кабинет для переписки; документы можно прислать сюда; "
            "кабинет — альтернатива для файлов / оплата / согласие)."
        ),
    }.get(channel, "Клиент пишет в единый чат по делу.")
    blocks = [
        header,
        "",
        "ContextPack (сервер, источник истины):",
        format_context_pack_for_prompt(pack),
        "",
        "Контекст сделки:",
        deal,
    ]
    if pack.get("intake_step"):
        blocks.extend(
            [
                "",
                f"Шаг сценария intake (кнопки): {pack.get('intake_step')}",
                "Системные кнопки шага будут под ответом — дополни мягкими BUTTONS.",
            ]
        )
    blocks.extend(
        [
            "",
            "История переписки (хронологически, без ПДн):",
            thread,
            "",
            "Новое сообщение клиента (обезличено):",
            safe,
            "",
            "Правила ответа:",
            "- Один вопрос или одно действие за сообщение.",
            "- Не спрашивай повторно то, что в «Уже известно».",
            "- Не говори «документ изучен/разобран», если содержание не передано.",
            "- Не говори «получили файл», если он в pending/failed.",
            "- Не обещай перерасчёт, сумму пенсии, подачу вместо клиента.",
            "- Если staff_dialog_active=да — кратко поддержи и не перехватывай диалог.",
            "- Если can_pay=да — мягко предложи оплату ссылкой/QR в этот чат "
            "(не выдумывай URL); ценность диагностики 3 000 ₽ без торга.",
        ]
    )
    return "\n".join(blocks)


def build_staff_llm_user_prompt(
    *,
    salutation: str,
    work: dict[str, Any] | None,
    messages: list[dict[str, Any]],
    pipeline_status: str | None = None,
    b2c_status: str | None = None,
) -> str:
    """User-prompt для подсказок ответов специалисту."""
    thread = format_thread_for_llm(messages, max_body_chars=500)
    deal = format_deal_context(work, staff_chat=True)
    return (
        f"Обращение к клиенту (обязательно в каждом варианте): {salutation}\n"
        f"Этап: pipeline={pipeline_status or '—'}, b2c={b2c_status or '—'}\n\n"
        f"Контекст сделки:\n{deal}\n\n"
        f"История переписки (хронологически):\n{thread}\n\n"
        "Предложи 3 варианта ответа с учётом последней реплики клиента и стадии сделки. "
        "Не упоминай согласие на ПДн и личный кабинет на сайте — согласие уже получено "
        "при входе в MAX до «Начать»; документы — в этот чат MAX. "
        "Если клиент задаёт вопрос, на который бот уже отвечал — "
        "дай более точный ответ специалиста."
    )


def work_map_from_case(case: dict[str, Any]) -> dict[str, Any]:
    """Построить work_map для LLM из строки дела."""
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.client_work_map import build_client_work_map

    case_id = str(case.get("id") or "").strip()
    if not case_id:
        return {}
    repo = CaseRepository()
    try:
        scenarios = repo.list_case_scenarios(case_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("work_map scenarios skipped: %s", exc)
        scenarios = []
    return build_client_work_map(
        pipeline_status=str(case.get("pipeline_status") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        consent_accepted=repo.has_consent(case_id),
        documents=list(case.get("documents") or []),
        checklist_items=list(case.get("checklist_items") or []),
        orders=repo.list_orders(case_id) or list(case.get("orders") or []),
        scenario_rows=scenarios,
    )
