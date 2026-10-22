"""Краткий бесплатный разбор после полного комплекта (ТЗ-35 §11 / 35a).

Без нового OCR-провайдера и без сырого скана в LLM по умолчанию:
опора на типы документов, content_preview (уже в деле), анкету и
pipeline findings при наличии. Платный оффер 3 000 ₽ — только через
diag_offer_gate после согласия на подробный разбор.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.services.max_post_diagnosis import sanitize_finding_line

logger = logging.getLogger(__name__)

STATUS_KEY = "_brief_status"
OK_KEY = "_brief_ok"
CURRENT_KEY = "_brief_current"
DISCREPANCY_KEY = "_brief_discrepancy"
SUMMARY_KEY = "_brief_summary"
FP_KEY = "_brief_fp"
SUMMARY_SHOWN_KEY = "_brief_summary_shown"
DETAIL_CONSENT_KEY = "_detail_consent"
DETAIL_PENDING_KEY = "_detail_pending"

STATUS_NONE = "none"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"

DETAIL_YES = "diag:detail_yes"
DETAIL_NO = "diag:detail_no"

_PROBLEM_THEMES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"север|ркс|мкс|район\s+крайнего", re.I),
        "возможные вопросы по северному / льготному стажу",
    ),
    (
        re.compile(r"не\s+учл|не\s+учт|не\s+отраж|пропал|пропуск", re.I),
        "возможные неучтённые или не отражённые периоды",
    ),
    (
        re.compile(r"архив|справк", re.I),
        "возможная нехватка подтверждающих / архивных справок",
    ),
    (
        re.compile(r"дат|период|стаж", re.I),
        "возможные расхождения дат или периодов стажа",
    ),
)

_NO_DISCREPANCY_TEXT = (
    "По представленным документам автоматическая проверка не выявила "
    "очевидных расхождений. Это не исключает проверки полного комплекта "
    "специалистом.\n\n"
    "Мы готовим документы и план — обращение через СФР или Госуслуги "
    "подаёте вы сами. Решение принимает СФР."
)

_DISCLAIMER = (
    "Это предварительный автоматизированный результат, а не окончательное "
    "юридическое заключение."
)

_SOFT_ASK = (
    "Хотите подробный разбор расхождений и понятный план действий? "
    "Подробная диагностика — 3 000 ₽. Решение о пенсии принимает только СФР."
)

_PROBLEM_TYPE_HINTS: dict[str, str] = {
    "north": "не учли северный стаж",
    "ils_stazh": "стаж не отражён в ИЛС",
    "documents": "нужна архивная справка о стаже",
    "sfr_refusal": "отказ или вопросы по решению СФР",
}
_GOAL_HINTS: dict[str, str] = {
    "missing_period": "не учли период стажа",
    "check_experience": "проверка стажа",
    "sfr_question": "вопрос по обращению в СФР",
}


@dataclass(frozen=True)
class BriefAnalysisResult:
    ok: bool
    current: bool
    has_justified_discrepancy: bool
    summary: str
    bullets: list[str] = field(default_factory=list)
    fingerprint: str = ""
    source: str = "heuristic"


def documents_fingerprint(documents: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        doc_id = str(doc.get("id") or "").strip()
        if not doc_id:
            continue
        checksum = str(doc.get("checksum_sha256") or "").strip() or "-"
        dtype = str(doc.get("doc_type") or "").strip().lower() or "-"
        parts.append(f"{doc_id}:{checksum}:{dtype}")
    blob = "|".join(sorted(parts))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _problem_text(
    intake: Any | None,
    *,
    client_texts: list[str] | None = None,
) -> str:
    """Формулировка проблемы: анкета, goal/type, недавние реплики клиента."""
    parts: list[str] = []
    if intake is not None:
        answers = getattr(intake, "q_answers", None) or {}
        if isinstance(answers, dict):
            for key in ("problem", "problem_text", "issue"):
                val = str(answers.get(key) or "").strip()
                if val:
                    parts.append(val)
        ptype = str(getattr(intake, "problem_type", None) or "").strip()
        if ptype:
            parts.append(_PROBLEM_TYPE_HINTS.get(ptype, ptype.replace("_", " ")))
        goal = str(getattr(intake, "goal", None) or "").strip()
        if goal:
            parts.append(_GOAL_HINTS.get(goal, goal.replace("_", " ")))
    for raw in client_texts or []:
        text = str(raw or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _themes_from_problem(problem: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for pattern, label in _PROBLEM_THEMES:
        if pattern.search(problem) and label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _bullets_from_findings(findings: list[dict[str, Any]] | None) -> list[str]:
    from sfrfr.services.max_post_diagnosis import brief_recommendations_from_findings

    return brief_recommendations_from_findings(findings, limit=5)


def _client_texts_from_history(history: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("author_kind") or "").strip().lower()
        if kind not in {"client", "representative", "user"}:
            continue
        body = str(row.get("body") or "").strip()
        if body:
            out.append(body)
    return out


def _reload_intake_rec(rec: Any) -> Any:
    """Актуальная запись с диска + синхронизация q_answers у переданного rec."""
    from sfrfr.integrations.max.intake import get_intake_store

    store = get_intake_store()
    store.reload()
    mid = str(getattr(rec, "max_user_id", "") or "").strip()
    if not mid:
        return rec
    fresh = store.get_active(mid)
    if fresh is None:
        return rec
    rec.q_answers = dict(getattr(fresh, "q_answers", None) or {})
    return fresh


def compute_brief_analysis(
    *,
    documents: list[dict[str, Any]] | None = None,
    intake: Any | None = None,
    pipeline_findings: list[dict[str, Any]] | None = None,
    client_texts: list[str] | None = None,
) -> BriefAnalysisResult:
    """Локальный краткий разбор без нового OCR и без обязательного LLM."""
    docs = [d for d in (documents or []) if isinstance(d, dict)]
    fp = documents_fingerprint(docs)
    findings_bullets = _bullets_from_findings(pipeline_findings)
    themes = _themes_from_problem(
        _problem_text(intake, client_texts=client_texts)
    )
    bullets: list[str] = []
    for item in findings_bullets:
        clean = sanitize_finding_line(item)
        if clean and clean not in bullets:
            bullets.append(clean)
    for theme in themes:
        if theme not in bullets:
            bullets.append(theme)

    has_disc = bool(findings_bullets) or bool(themes)
    if has_disc:
        lines = [
            "Предварительная проверка комплекта завершена.",
            "По документам и вашей формулировке есть направления для "
            "подробной проверки (черновик, не юридический вывод):",
        ]
        for i, item in enumerate(bullets[:5], start=1):
            lines.append(f"{i}. {item}")
        lines.extend(["", _DISCLAIMER])
        summary = "\n".join(lines)
        source = "findings" if findings_bullets else "questionnaire"
    else:
        summary = _NO_DISCREPANCY_TEXT
        source = "none"

    return BriefAnalysisResult(
        ok=True,
        current=True,
        has_justified_discrepancy=has_disc,
        summary=summary,
        bullets=bullets,
        fingerprint=fp,
        source=source,
    )


def soft_ask_text() -> str:
    return _SOFT_ASK


def soft_ask_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": "Да, подробный разбор",
                    "payload": DETAIL_YES,
                }
            ],
            [
                {
                    "type": "callback",
                    "text": "Пока нет",
                    "payload": DETAIL_NO,
                }
            ],
        ]
    )


def persist_brief_to_intake(rec: Any, result: BriefAnalysisResult) -> None:
    from sfrfr.integrations.max.intake import get_intake_store

    target = _reload_intake_rec(rec)
    answers = dict(getattr(target, "q_answers", None) or {})
    answers[STATUS_KEY] = STATUS_COMPLETED if result.ok else STATUS_ERROR
    answers[OK_KEY] = "1" if result.ok else "0"
    answers[CURRENT_KEY] = "1" if result.current else "0"
    answers[DISCREPANCY_KEY] = "1" if result.has_justified_discrepancy else "0"
    answers[SUMMARY_KEY] = result.summary[:3500]
    answers[FP_KEY] = result.fingerprint
    answers[SUMMARY_SHOWN_KEY] = "0"
    answers[DETAIL_CONSENT_KEY] = "0"
    answers.pop(DETAIL_PENDING_KEY, None)
    target.q_answers = answers
    rec.q_answers = answers
    get_intake_store().save(target)


def mark_summary_shown(rec: Any) -> None:
    from sfrfr.integrations.max.intake import get_intake_store

    target = _reload_intake_rec(rec)
    answers = dict(getattr(target, "q_answers", None) or {})
    answers[SUMMARY_SHOWN_KEY] = "1"
    if answers.get(DISCREPANCY_KEY) == "1":
        answers[DETAIL_PENDING_KEY] = "1"
    target.q_answers = answers
    rec.q_answers = answers
    get_intake_store().save(target)


def mark_detail_consent(rec: Any, *, wants: bool) -> None:
    from sfrfr.integrations.max.intake import get_intake_store

    target = _reload_intake_rec(rec)
    answers = dict(getattr(target, "q_answers", None) or {})
    answers[DETAIL_CONSENT_KEY] = "1" if wants else "0"
    answers.pop(DETAIL_PENDING_KEY, None)
    target.q_answers = answers
    rec.q_answers = answers
    get_intake_store().save(target)

def is_detail_pending(rec: Any | None) -> bool:
    if rec is None:
        return False
    answers = getattr(rec, "q_answers", None) or {}
    return str(answers.get(DETAIL_PENDING_KEY) or "") == "1"


def gate_flags_from_intake(
    rec: Any | None,
    *,
    reload: bool = False,
) -> dict[str, bool]:
    """Флаги для evaluate_diag_offer из intake (без обхода)."""
    target = rec
    if reload and rec is not None:
        target = _reload_intake_rec(rec)
    answers = (getattr(target, "q_answers", None) or {}) if target is not None else {}
    if not isinstance(answers, dict):
        answers = {}
    completed = str(answers.get(STATUS_KEY) or "") == STATUS_COMPLETED
    return {
        "has_completed_brief_analysis": completed,
        "analysis_ok": str(answers.get(OK_KEY) or "") == "1",
        "analysis_current": str(answers.get(CURRENT_KEY) or "") == "1",
        "has_justified_discrepancy": str(answers.get(DISCREPANCY_KEY) or "") == "1",
        "client_got_clear_summary": str(answers.get(SUMMARY_SHOWN_KEY) or "") == "1",
        "client_wants_detailed_review": str(answers.get(DETAIL_CONSENT_KEY) or "") == "1",
    }


def ensure_brief_flags_for_offer(
    rec: Any,
    *,
    case_id: str | None,
) -> BriefAnalysisResult | None:
    """Восстановить _brief_* из дела, если флаги потеряны (restart / stale store).

    Не шлёт повторный soft-ask в чат — вызывается из callback «Да».
    persist сбрасывает consent; вызывающий должен снова mark_detail_consent.
    """
    mid = str(getattr(rec, "max_user_id", "") or "").strip()
    cid = str(case_id or getattr(rec, "case_id", "") or "").strip()
    if not mid or not cid:
        return None

    flags = gate_flags_from_intake(rec, reload=True)
    have_core = (
        flags["has_completed_brief_analysis"]
        and flags["analysis_ok"]
        and flags["analysis_current"]
        and flags["client_got_clear_summary"]
    )
    if have_core:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_context import fetch_recent_case_messages
    from sfrfr.services.max_kit_status import collect_case_doc_buckets

    try:
        docs = list(CaseRepository().list_documents(cid) or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure brief list_documents failed: %s", exc)
        return None
    have = collect_case_doc_buckets(docs)
    if "ils" not in have or "labor" not in have:
        return None

    findings: list[dict[str, Any]] = []
    try:
        findings = list(CaseRepository().get_pipeline_findings(cid) or [])
    except Exception:  # noqa: BLE001
        findings = []

    history: list[dict[str, Any]] = []
    try:
        history = fetch_recent_case_messages(cid)
    except Exception:  # noqa: BLE001
        history = []

    target = _reload_intake_rec(rec)
    result = compute_brief_analysis(
        documents=docs,
        intake=target,
        pipeline_findings=findings,
        client_texts=_client_texts_from_history(history),
    )
    persist_brief_to_intake(target, result)
    mark_summary_shown(target)
    rec.q_answers = dict(getattr(target, "q_answers", None) or {})
    logger.info(
        "ensure brief flags case=%s disc=%s",
        cid[:8],
        result.has_justified_discrepancy,
    )
    return result

def run_brief_after_kit(
    *,
    case_id: str,
    max_user_id: str,
) -> BriefAnalysisResult | None:
    """После settle с полным комплектом: анализ → сообщение → soft-ask при расхождениях."""
    cid = str(case_id or "").strip()
    mid = str(max_user_id or "").strip()
    if not cid or not mid:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.integrations.max.intake import get_intake_store
    from sfrfr.services.case_chat_context import (
        fetch_recent_case_messages,
        staff_dialog_active,
    )
    from sfrfr.services.case_chat_delivery import enqueue_max_delivery
    from sfrfr.services.max_kit_status import collect_case_doc_buckets

    history: list[dict[str, Any]] = []
    try:
        history = fetch_recent_case_messages(cid)
        if staff_dialog_active(history):
            logger.info("brief analysis skipped staff_active case=%s", cid[:8])
            return None
    except Exception:  # noqa: BLE001
        history = []

    repo = CaseRepository()
    try:
        docs = list(repo.list_documents(cid) or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("brief list_documents failed: %s", exc)
        return None

    have = collect_case_doc_buckets(docs)
    if "ils" not in have or "labor" not in have:
        return None

    findings: list[dict[str, Any]] = []
    try:
        findings = list(repo.get_pipeline_findings(cid) or [])
    except Exception:  # noqa: BLE001
        findings = []

    store = get_intake_store()
    store.reload()
    rec = store.get_active(mid)
    if rec is None:
        logger.info("brief analysis skipped no intake user=%s", mid[:8])
        return None

    result = compute_brief_analysis(
        documents=docs,
        intake=rec,
        pipeline_findings=findings,
        client_texts=_client_texts_from_history(history),
    )
    prev_fp = str((rec.q_answers or {}).get(FP_KEY) or "")
    prev_shown = str((rec.q_answers or {}).get(SUMMARY_SHOWN_KEY) or "")
    if prev_fp == result.fingerprint and prev_shown == "1":
        logger.info("brief analysis skipped unchanged case=%s", cid[:8])
        return result

    persist_brief_to_intake(rec, result)

    body = result.summary
    attachments = None
    if result.has_justified_discrepancy:
        body = f"{result.summary}\n\n{_SOFT_ASK}"
        attachments = soft_ask_keyboard()

    ok = enqueue_max_delivery(
        case_id=cid,
        message_id=None,
        max_user_id=mid,
        body=body,
        attachments=attachments,
    )
    if ok:
        mark_summary_shown(rec)
        if not result.has_justified_discrepancy:
            try:
                from sfrfr.integrations.max import soft_offers

                hint = soft_offers.pick_soft_offer(
                    rec,
                    logical_msg_count=int(getattr(rec, "logical_bot_msg_count", 0) or 99),
                    other_offer_this_turn=False,
                )
                if hint:
                    enqueue_max_delivery(
                        case_id=cid,
                        message_id=None,
                        max_user_id=mid,
                        body=hint[1],
                        attachments=None,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("soft offer after brief skipped: %s", exc)
    return result


def schedule_brief_after_kit(*, case_id: str, max_user_id: str) -> None:
    """Фоновый запуск после settle (не блокировать timer settle)."""
    cid = str(case_id or "").strip()
    mid = str(max_user_id or "").strip()
    if not cid or not mid:
        return

    def _run() -> None:
        try:
            run_brief_after_kit(case_id=cid, max_user_id=mid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("brief after kit failed case=%s: %s", cid[:8], exc)

    thread = threading.Thread(target=_run, name=f"brief-{cid[:8]}", daemon=True)
    thread.start()
