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
CASE_KEY = "_brief_case_id"
SUMMARY_SHOWN_KEY = "_brief_summary_shown"
SOFT_ASK_SENT_KEY = "_brief_soft_ask_sent"
OFFER_REVIVE_KEY = "_brief_offer_revive"
DETAIL_CONSENT_KEY = "_detail_consent"
DETAIL_PENDING_KEY = "_detail_pending"

STATUS_NONE = "none"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"

DETAIL_YES = "diag:detail_yes"
DETAIL_NO = "diag:detail_no"
OFFER_REVIVE_KEY = "_brief_offer_revive"

EVIDENCE_DOCS = "docs"
EVIDENCE_CLIENT = "client"
EVIDENCE_NEEDS_CHECK = "needs_check"

_EVIDENCE_LABEL_RU: dict[str, str] = {
    EVIDENCE_DOCS: "подтверждено документами",
    EVIDENCE_CLIENT: "со слов клиента",
    EVIDENCE_NEEDS_CHECK: "требует проверки",
}

# Сильные темы анкеты → needs_check (могут открыть soft-ask).
# Слабое «стаж»/goal check_experience сюда не входит.
_NEEDS_CHECK_THEMES: tuple[tuple[re.Pattern[str], str], ...] = (
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
)

# Слабые формулировки → только «со слов клиента», без soft-ask/оффера.
_CLIENT_ONLY_THEMES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"дат|период|стаж", re.I),
        "возможные расхождения дат или периодов стажа",
    ),
)

_MAX_BRIEF_BULLETS = 3
_NEXT_STEP_JUSTIFIED = (
    "Следующий шаг: если нужен подробный разбор — ответьте кнопкой ниже "
    "(или напишите специалисту /help)."
)
_NEXT_STEP_CLIENT_ONLY = (
    "Следующий шаг: уточните, что именно сверить по документам, "
    "или напишите специалисту /help."
)
_NEXT_STEP_NONE = (
    "Следующий шаг: при необходимости сверьте комплект со специалистом (/help)."
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
    evidence_kinds: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
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
    include_goal: bool = False,
) -> str:
    """Формулировка проблемы: анкета, type, реплики клиента.

    Goal по умолчанию не подмешиваем: check_experience → «стаж» ложно
    ставил расхождение. Явный problem_type / текст анкеты — да.
    """
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
        if include_goal:
            goal = str(getattr(intake, "goal", None) or "").strip()
            if goal:
                parts.append(_GOAL_HINTS.get(goal, goal.replace("_", " ")))
    for raw in client_texts or []:
        text = str(raw or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _themes_from_problem(
    problem: str,
    *,
    patterns: tuple[tuple[re.Pattern[str], str], ...],
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for pattern, label in patterns:
        if pattern.search(problem) and label not in seen:
            seen.add(label)
            out.append(label)
    return out


_DOC_TYPE_RU: dict[str, str] = {
    "ils": "ИЛС",
    "workbook": "трудовая",
    "labor": "трудовая",
    "archive": "архивная справка",
    "sfr": "ответ СФР",
}


def _format_brief_bullet(text: str, evidence: str) -> str:
    label = _EVIDENCE_LABEL_RU.get(evidence, evidence)
    clean = str(text or "").strip()
    return f"{clean} ({label})" if clean else label


def _basis_from_finding(row: dict[str, Any]) -> str:
    """Короткое основание пункта: документ + период (без ПДн)."""
    bits: list[str] = []
    dtype = str(
        row.get("doc_type")
        or row.get("source_doc_type")
        or row.get("document_type")
        or ""
    ).strip().lower()
    if dtype:
        bits.append(_DOC_TYPE_RU.get(dtype, dtype))
    period = str(row.get("period") or row.get("period_label") or "").strip()
    if not period:
        detail = str(row.get("detail") or "")
        m = re.search(
            r"(\d{1,2}[./]\d{4}\s*[–—\-]\s*\d{1,2}[./]\d{4}"
            r"|\d{4}\s*[–—\-]\s*\d{4})",
            detail,
        )
        if m:
            period = m.group(1).replace("—", "–").replace("-", "–")
    if period:
        bits.append(f"период {period}")
    label = str(row.get("source_label") or "").strip()
    if label and label.lower() not in {b.lower() for b in bits}:
        bits.append(label[:80])
    return ", ".join(bits)


def _bullets_from_findings(findings: list[dict[str, Any]] | None) -> list[str]:
    from sfrfr.services.max_post_diagnosis import brief_recommendations_from_findings

    return brief_recommendations_from_findings(findings, limit=5)


def _labeled_from_findings(
    findings: list[dict[str, Any]] | None,
) -> list[tuple[str, str, str]]:
    """(text, evidence=docs, basis) из pipeline findings."""
    from sfrfr.services.max_post_diagnosis import brief_recommendations_from_findings

    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for row in findings or []:
        if not isinstance(row, dict):
            continue
        clean = sanitize_finding_line(str(row.get("detail") or ""))
        if not clean or clean in seen:
            continue
        # тот же фильтр интересности, что у brief_recommendations_from_findings
        probe = brief_recommendations_from_findings([row], limit=1)
        if not probe:
            continue
        seen.add(clean)
        out.append((clean, EVIDENCE_DOCS, _basis_from_finding(row)))
    return out


def _client_texts_from_history(history: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("author_kind") or "").strip().lower()
        # Пустой kind — чаще клиент из MAX; system/bot/staff пропускаем.
        if kind in {"system", "bot", "staff"}:
            continue
        if kind and kind not in {"client", "representative", "user"}:
            continue
        body = str(row.get("body") or "").strip()
        if body:
            out.append(body)
    return out


def soft_ask_was_sent(rec: Any | None) -> bool:
    """Soft-ask уже ушёл клиенту (кнопка в ленте MAX остаётся)."""
    if rec is None:
        return False
    answers = getattr(rec, "q_answers", None) or {}
    if not isinstance(answers, dict):
        return False
    return (
        str(answers.get(SOFT_ASK_SENT_KEY) or "") == "1"
        or str(answers.get(DETAIL_PENDING_KEY) or "") == "1"
    )


def preserve_gaps_after_soft_ask_yes(rec: Any) -> None:
    """Callback diag:detail_yes = soft-ask уже был → gaps для gate.

    Клик восстанавливает право на оффер, но сам по себе не доказывает
    выполненную проверку: analysis-флаги поднимаем только если soft-ask
    уже был зафиксирован до клика (или есть prior summary).
    """
    from sfrfr.integrations.max.intake import get_intake_store

    prior_soft = soft_ask_was_sent(rec)
    target = _reload_intake_rec(rec)
    answers = dict(getattr(target, "q_answers", None) or {})
    had_brief = (
        str(answers.get(STATUS_KEY) or "") == STATUS_COMPLETED
        or bool(str(answers.get(SUMMARY_KEY) or "").strip())
        or str(answers.get(SUMMARY_SHOWN_KEY) or "") == "1"
    )
    if not (prior_soft or had_brief):
        # Холодный клик без soft-ask/brief: не помечаем discrepancy в одиночку.
        return
    # Revive оффера после потерянных флагов — не «клик = анализ».
    answers[SOFT_ASK_SENT_KEY] = "1"
    answers[DISCREPANCY_KEY] = "1"
    answers[OFFER_REVIVE_KEY] = "1"
    if str(answers.get(STATUS_KEY) or "") != STATUS_COMPLETED:
        answers[STATUS_KEY] = STATUS_COMPLETED
    if str(answers.get(OK_KEY) or "") != "1":
        answers[OK_KEY] = "1"
    if str(answers.get(CURRENT_KEY) or "") != "1":
        answers[CURRENT_KEY] = "1"
    if str(answers.get(SUMMARY_SHOWN_KEY) or "") != "1":
        answers[SUMMARY_SHOWN_KEY] = "1"
    if not str(answers.get(SUMMARY_KEY) or "").strip():
        answers[SUMMARY_KEY] = _force_discrepancy_result(
            BriefAnalysisResult(
                ok=True,
                current=True,
                has_justified_discrepancy=False,
                summary="",
                source="soft_ask_preserve",
            )
        ).summary[:3500]
    target.q_answers = answers
    rec.q_answers = answers
    get_intake_store().save(target)


def _force_discrepancy_result(
    result: BriefAnalysisResult,
    *,
    prior_summary: str | None = None,
) -> BriefAnalysisResult:
    """Не отзывать soft-ask: gaps остаются true без новой «уверенности в пустоте»."""
    if result.has_justified_discrepancy:
        return result
    prior = str(prior_summary or "").strip()
    if prior and "не выявила очевидных расхождений" not in prior.lower():
        summary = prior
        bullets = list(result.bullets)
    else:
        raw = list(result.bullets) or [
            "возможные неучтённые или не отражённые периоды",
        ]
        bullets = []
        for b in raw[:_MAX_BRIEF_BULLETS]:
            low = b.lower()
            already = "(" in b and (
                "слов клиента" in low
                or "требует проверки" in low
                or "подтверждено документами" in low
            )
            bullets.append(
                b if already else _format_brief_bullet(b, EVIDENCE_NEEDS_CHECK)
            )
        lines = [
            "Предварительная проверка комплекта завершена.",
            "Направления для сверки (черновик, не юридический вывод):",
        ]
        for i, item in enumerate(bullets, start=1):
            lines.append(f"{i}. {item}")
        lines.extend(["", _DISCLAIMER, "", _NEXT_STEP_JUSTIFIED])
        summary = "\n".join(lines)
    return BriefAnalysisResult(
        ok=result.ok,
        current=result.current,
        has_justified_discrepancy=True,
        summary=summary,
        bullets=bullets,
        evidence_kinds=list(result.evidence_kinds)
        or [EVIDENCE_NEEDS_CHECK] * len(bullets),
        fingerprint=result.fingerprint,
        source=result.source if result.source != "none" else "soft_ask_preserve",
    )


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
    problem = _problem_text(intake, client_texts=client_texts)

    labeled: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for text, kind, basis in _labeled_from_findings(pipeline_findings):
        if text not in seen:
            seen.add(text)
            labeled.append((text, kind, basis))
    for theme in _themes_from_problem(problem, patterns=_NEEDS_CHECK_THEMES):
        if theme not in seen:
            seen.add(theme)
            labeled.append((theme, EVIDENCE_NEEDS_CHECK, "анкета / формулировка клиента"))
    for theme in _themes_from_problem(problem, patterns=_CLIENT_ONLY_THEMES):
        if theme not in seen:
            seen.add(theme)
            labeled.append((theme, EVIDENCE_CLIENT, "со слов клиента"))

    labeled = labeled[:_MAX_BRIEF_BULLETS]
    bullets = [_format_brief_bullet(text, kind) for text, kind, _b in labeled]
    evidence_kinds = [kind for _text, kind, _b in labeled]
    bases = [basis for _text, _kind, basis in labeled]
    has_docs = EVIDENCE_DOCS in evidence_kinds
    has_needs = EVIDENCE_NEEDS_CHECK in evidence_kinds
    has_client = EVIDENCE_CLIENT in evidence_kinds
    # Soft-ask / оффер — только docs или needs_check, не слабое «стаж».
    has_disc = has_docs or has_needs

    if has_disc or has_client:
        lines = [
            "Предварительная проверка комплекта завершена.",
            "Направления для сверки (черновик, не юридический вывод):",
        ]
        for i, item in enumerate(bullets, start=1):
            lines.append(f"{i}. {item}")
        lines.extend(["", _DISCLAIMER, ""])
        if has_disc:
            lines.append(_NEXT_STEP_JUSTIFIED)
            source = "findings" if has_docs else "questionnaire"
        else:
            lines.append(_NEXT_STEP_CLIENT_ONLY)
            source = "client_only"
        summary = "\n".join(lines)
    else:
        summary = f"{_NO_DISCREPANCY_TEXT}\n\n{_NEXT_STEP_NONE}"
        source = "none"

    return BriefAnalysisResult(
        ok=True,
        current=True,
        has_justified_discrepancy=has_disc,
        summary=summary,
        bullets=bullets,
        evidence_kinds=evidence_kinds,
        bases=bases,
        fingerprint=fp,
        source=source,
    )


def honest_brief_ui_payload(
    result: BriefAnalysisResult,
    *,
    current_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Структура для UI (MAX/staff): статусы, основания, офер без давления."""
    fp_now = str(current_fingerprint or "").strip()
    current = True
    stale_reason = ""
    if fp_now and fp_now != str(result.fingerprint or "").strip():
        current = False
        stale_reason = (
            "Состав документов изменился — прежнее резюме не актуально. "
            "Запустите проверку снова."
        )
    items: list[dict[str, str]] = []
    bases = list(result.bases or [])
    kinds = list(result.evidence_kinds or [])
    for idx, bullet in enumerate(list(result.bullets or [])[:_MAX_BRIEF_BULLETS]):
        kind = kinds[idx] if idx < len(kinds) else EVIDENCE_NEEDS_CHECK
        # текст без хвоста «(статус)»
        text = str(bullet or "").strip()
        for label in _EVIDENCE_LABEL_RU.values():
            suffix = f" ({label})"
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break
        items.append(
            {
                "text": text,
                "evidence": kind,
                "evidence_label": _EVIDENCE_LABEL_RU.get(kind, kind),
                "basis": bases[idx] if idx < len(bases) else "",
            }
        )
    offer_ok = bool(
        current
        and result.has_justified_discrepancy
        and any(k in {EVIDENCE_DOCS, EVIDENCE_NEEDS_CHECK} for k in kinds)
    )
    if result.has_justified_discrepancy:
        headline = "Направления для сверки (черновик, не юридический вывод)"
        next_step = _NEXT_STEP_JUSTIFIED if offer_ok else _NEXT_STEP_CLIENT_ONLY
    elif items:
        headline = "По анкете есть темы для уточнения"
        next_step = _NEXT_STEP_CLIENT_ONLY
    else:
        headline = (
            "По представленным документам автоматическая проверка "
            "не выявила очевидных расхождений"
        )
        next_step = _NEXT_STEP_NONE
    return {
        "current": current,
        "stale_reason": stale_reason,
        "has_justified_discrepancy": bool(result.has_justified_discrepancy),
        "offer_diag_allowed": offer_ok,
        "offer_amount_rub": 3000 if offer_ok else 0,
        "headline": headline,
        "next_step": next_step,
        "items": items,
        "fingerprint": result.fingerprint,
        "disclaimer": _DISCLAIMER,
    }


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
    # Soft-ask в ленте MAX переживает restart/recompute; discrepancy
    # восстанавливает ensure_brief_flags_for_offer при «Да».
    prev_soft = str(answers.get(SOFT_ASK_SENT_KEY) or "") == "1"
    answers[STATUS_KEY] = STATUS_COMPLETED if result.ok else STATUS_ERROR
    answers[OK_KEY] = "1" if result.ok else "0"
    answers[CURRENT_KEY] = "1" if result.current else "0"
    answers[DISCREPANCY_KEY] = "1" if result.has_justified_discrepancy else "0"
    answers[SUMMARY_KEY] = result.summary[:3500]
    answers[FP_KEY] = result.fingerprint
    cid = str(getattr(target, "case_id", None) or getattr(rec, "case_id", "") or "").strip()
    if cid:
        answers[CASE_KEY] = cid
    answers[SUMMARY_SHOWN_KEY] = "0"
    answers[DETAIL_CONSENT_KEY] = "0"
    answers.pop(DETAIL_PENDING_KEY, None)
    if prev_soft:
        # Не сбрасываем факт ушедшего soft-ask при пустом пересчёте.
        answers[SOFT_ASK_SENT_KEY] = "1"
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
        answers[SOFT_ASK_SENT_KEY] = "1"
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


def brief_is_current_for_case(
    answers: dict[str, Any],
    *,
    case_id: str | None,
    documents: list[dict[str, Any]] | None = None,
) -> bool:
    """True только если сохранённый brief того же дела и (опционально) того же состава docs."""
    if str(answers.get(CURRENT_KEY) or "") != "1":
        return False
    cid = str(case_id or "").strip()
    stored_case = str(answers.get(CASE_KEY) or "").strip()
    if cid and stored_case and stored_case != cid:
        return False
    if documents is None:
        return True
    stored_fp = str(answers.get(FP_KEY) or "").strip()
    if not stored_fp:
        return False
    return stored_fp == documents_fingerprint(documents)


def gate_flags_from_intake(
    rec: Any | None,
    *,
    reload: bool = False,
    case_id: str | None = None,
    documents: list[dict[str, Any]] | None = None,
) -> dict[str, bool]:
    """Флаги для evaluate_diag_offer из intake (без обхода)."""
    target = rec
    if reload and rec is not None:
        target = _reload_intake_rec(rec)
    answers = (getattr(target, "q_answers", None) or {}) if target is not None else {}
    if not isinstance(answers, dict):
        answers = {}
    completed = str(answers.get(STATUS_KEY) or "") == STATUS_COMPLETED
    cid = str(
        case_id
        or (getattr(target, "case_id", None) if target is not None else "")
        or ""
    ).strip()
    analysis_current = brief_is_current_for_case(
        answers, case_id=cid or None, documents=documents
    )
    return {
        "has_completed_brief_analysis": completed,
        "analysis_ok": str(answers.get(OK_KEY) or "") == "1",
        "analysis_current": analysis_current,
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
    Soft-ask уже ушёл → не даём пересчёту стереть has_gaps.
    """
    mid = str(getattr(rec, "max_user_id", "") or "").strip()
    cid = str(case_id or getattr(rec, "case_id", "") or "").strip()
    if not mid or not cid:
        return None

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_context import fetch_recent_case_messages
    from sfrfr.services.max_kit_status import collect_case_doc_buckets

    try:
        docs = list(CaseRepository().list_documents(cid) or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure brief list_documents failed: %s", exc)
        return None

    flags = gate_flags_from_intake(
        rec, reload=True, case_id=cid, documents=docs
    )
    answers_now = dict(getattr(rec, "q_answers", None) or {})
    keep_gaps = soft_ask_was_sent(rec) or flags["has_justified_discrepancy"]
    prior_summary = str(answers_now.get(SUMMARY_KEY) or "")
    have_core = (
        flags["has_completed_brief_analysis"]
        and flags["analysis_ok"]
        and flags["analysis_current"]
        and flags["client_got_clear_summary"]
    )
    if have_core:
        if keep_gaps and not flags["has_justified_discrepancy"]:
            # Soft-ask был, а discrepancy уже «0» — восстановить для gate.
            target = _reload_intake_rec(rec)
            forced = _force_discrepancy_result(
                BriefAnalysisResult(
                    ok=True,
                    current=True,
                    has_justified_discrepancy=False,
                    summary=prior_summary or _NO_DISCREPANCY_TEXT,
                    fingerprint=str(
                        (getattr(target, "q_answers", None) or {}).get(FP_KEY) or ""
                    ),
                    source="soft_ask_preserve",
                ),
                prior_summary=prior_summary,
            )
            persist_brief_to_intake(target, forced)
            mark_summary_shown(target)
            rec.q_answers = dict(getattr(target, "q_answers", None) or {})
            return forced
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
        history = fetch_recent_case_messages(cid, limit=40)
    except Exception:  # noqa: BLE001
        history = []

    target = _reload_intake_rec(rec)
    keep_gaps = soft_ask_was_sent(target) or keep_gaps
    prior_summary = str(
        (getattr(target, "q_answers", None) or {}).get(SUMMARY_KEY) or prior_summary
    )
    result = compute_brief_analysis(
        documents=docs,
        intake=target,
        pipeline_findings=findings,
        client_texts=_client_texts_from_history(history),
    )
    if keep_gaps and not result.has_justified_discrepancy:
        result = _force_discrepancy_result(result, prior_summary=prior_summary)
    persist_brief_to_intake(target, result)
    mark_summary_shown(target)
    rec.q_answers = dict(getattr(target, "q_answers", None) or {})
    logger.info(
        "ensure brief flags case=%s disc=%s soft=%s",
        cid[:8],
        result.has_justified_discrepancy,
        soft_ask_was_sent(target),
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
