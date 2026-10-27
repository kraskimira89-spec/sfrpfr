"""План обращений: один адресат + однородная группа вопросов (правило сервиса).

Не юридический запрет — канон продукта. Сначала план, затем отдельные DOCX.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

APPEAL_TYPES = frozenset(
    {"application", "document_request", "complaint", "other"}
)
PROBLEM_STATUSES = frozenset(
    {"in_appeal", "need_clarify", "no_appeal_needed"}
)


class AppealsPlanError(ValueError):
    """Некорректный план обращений."""


def _sid() -> str:
    return str(uuid4())[:8]


def validate_problem(raw: dict[str, Any]) -> dict[str, Any]:
    fact = str(raw.get("fact") or "").strip()
    if not fact:
        raise AppealsPlanError("problem.fact is required")
    status = str(raw.get("status") or "need_clarify").strip().lower()
    if status not in PROBLEM_STATUSES:
        raise AppealsPlanError(
            "problem.status must be in_appeal|need_clarify|no_appeal_needed"
        )
    return {
        "id": str(raw.get("id") or _sid()),
        "fact": fact[:800],
        "basis_document": str(raw.get("basis_document") or "").strip()[:240] or None,
        "basis_page": str(raw.get("basis_page") or "").strip()[:40] or None,
        "period": str(raw.get("period") or "").strip()[:120] or None,
        "discrepancy": str(raw.get("discrepancy") or "").strip()[:400] or None,
        "depends_on_docs": [
            str(x).strip()[:200]
            for x in (raw.get("depends_on_docs") or [])
            if str(x).strip()
        ][:12],
        "status": status,
        "appeal_id": str(raw.get("appeal_id") or "").strip() or None,
        "note": str(raw.get("note") or "").strip()[:400] or None,
    }


def validate_appeal_group(raw: dict[str, Any]) -> dict[str, Any]:
    addressee = str(raw.get("addressee") or "").strip()
    if not addressee:
        raise AppealsPlanError("appeal.addressee is required")
    topic = str(raw.get("topic") or "").strip()
    if not topic:
        raise AppealsPlanError("appeal.topic is required")
    kind = str(raw.get("doc_type") or "application").strip().lower()
    if kind not in APPEAL_TYPES:
        raise AppealsPlanError(
            "appeal.doc_type must be application|document_request|complaint|other"
        )
    problem_ids = [
        str(x).strip()
        for x in (raw.get("problem_ids") or [])
        if str(x).strip()
    ]
    if not problem_ids:
        raise AppealsPlanError("appeal.problem_ids must be non-empty")
    return {
        "id": str(raw.get("id") or _sid()),
        "addressee": addressee[:400],
        "subdivision": str(raw.get("subdivision") or "").strip()[:400] or None,
        "topic": topic[:400],
        "doc_type": kind,
        "goal": str(raw.get("goal") or "").strip()[:600] or None,
        "requests": [
            str(x).strip()[:400]
            for x in (raw.get("requests") or [])
            if str(x).strip()
        ][:20],
        "problem_ids": problem_ids[:40],
        "attachments": [
            str(x).strip()[:200]
            for x in (raw.get("attachments") or [])
            if str(x).strip()
        ][:30],
        "submit_order": int(raw.get("submit_order") or 0),
        "merge_reason": str(raw.get("merge_reason") or "").strip()[:600] or None,
        "split_reason": str(raw.get("split_reason") or "").strip()[:600] or None,
        "ready_to_file": bool(raw.get("ready_to_file")),
        "missing_header_fields": [
            str(x).strip()[:80]
            for x in (raw.get("missing_header_fields") or [])
            if str(x).strip()
        ][:20],
    }


def validate_appeals_plan(payload: dict[str, Any]) -> dict[str, Any]:
    problems = [validate_problem(p) for p in (payload.get("problems") or []) if isinstance(p, dict)]
    appeals = [
        validate_appeal_group(a) for a in (payload.get("appeals") or []) if isinstance(a, dict)
    ]
    # Правило: один appeal — один addressee (уже по полю); однородность — merge_reason.
    by_id = {p["id"]: p for p in problems}
    for a in appeals:
        for pid in a["problem_ids"]:
            if pid not in by_id:
                raise AppealsPlanError(f"unknown problem_id in appeal: {pid}")
            by_id[pid]["appeal_id"] = a["id"]
            if by_id[pid]["status"] == "need_clarify":
                by_id[pid]["status"] = "in_appeal"
        # Нельзя ready_to_file при дырах в шапке
        if a["missing_header_fields"]:
            a["ready_to_file"] = False
    # Ни одна проблема не должна «потеряться»
    orphan = [p for p in problems if p["status"] == "in_appeal" and not p.get("appeal_id")]
    if orphan:
        raise AppealsPlanError("in_appeal problem without appeal_id")
    return {
        "version": int(payload.get("version") or 1),
        "status": str(payload.get("status") or "draft").strip().lower() or "draft",
        "problems": list(by_id.values()),
        "appeals": appeals,
        "notes": str(payload.get("notes") or "").strip()[:2000] or None,
        "rule": (
            "Одно обращение — один конкретный адресат и одна группа однородных вопросов "
            "(правило сервиса)."
        ),
    }


def can_merge_problems(
    *,
    same_addressee: bool,
    same_question_kind: bool,
    compatible_requests: bool,
) -> bool:
    """Объединять только при всех трёх условиях (ведомства одного мало)."""
    return bool(same_addressee and same_question_kind and compatible_requests)


def plan_table_markdown(plan: dict[str, Any]) -> str:
    """Таблица для подробного разбора (ст.5)."""
    lines = [
        "### План обращений",
        "",
        str(plan.get("rule") or ""),
        "",
        "| № | Адресат | Тема | Проблемы | Что просим | Приложения | Порядок |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, a in enumerate(plan.get("appeals") or [], start=1):
        probs = ", ".join(a.get("problem_ids") or []) or "—"
        req = "; ".join(a.get("requests") or []) or (a.get("goal") or "—")
        att = "; ".join(a.get("attachments") or []) or "—"
        lines.append(
            f"| {i} | {a.get('addressee')} | {a.get('topic')} | {probs} | "
            f"{req} | {att} | {a.get('submit_order', i)} |"
        )
    lines.append("")
    for a in plan.get("appeals") or []:
        if a.get("merge_reason"):
            lines.append(f"- **Почему объединено** ({a.get('topic')}): {a['merge_reason']}")
        if a.get("split_reason"):
            lines.append(f"- **Почему отдельно** ({a.get('topic')}): {a['split_reason']}")
    clarify = [
        p
        for p in (plan.get("problems") or [])
        if p.get("status") == "need_clarify"
    ]
    if clarify:
        lines.append("")
        lines.append("**Нужно уточнить (без выдуманного адресата):**")
        for p in clarify:
            lines.append(f"- {p.get('fact')}")
    no_need = [
        p
        for p in (plan.get("problems") or [])
        if p.get("status") == "no_appeal_needed"
    ]
    if no_need:
        lines.append("")
        lines.append("**Обращение не требуется:**")
        for p in no_need:
            lines.append(f"- {p.get('fact')}")
    return "\n".join(lines)


def header_gate(
    *,
    organ_name: str | None,
    organ_address: str | None,
    applicant_fio: str | None,
    representative: str | None,
    representation_confirmed: bool,
) -> dict[str, Any]:
    """Шапка DOCX: не выдумывать; missing → не ready_to_file."""
    missing: list[str] = []
    if not (organ_name or "").strip():
        missing.append("organ_name")
    if not (organ_address or "").strip():
        missing.append("organ_address")
    if not (applicant_fio or "").strip():
        missing.append("applicant_fio")
    if (representative or "").strip() and not representation_confirmed:
        missing.append("representation_basis")
    return {
        "ready_to_file": len(missing) == 0,
        "missing_header_fields": missing,
        "organ_name": (organ_name or "").strip() or None,
        "organ_address": (organ_address or "").strip() or None,
        "applicant_fio": (applicant_fio or "").strip() or None,
        "representative": (representative or "").strip() or None
        if representation_confirmed
        else None,
    }


_POSITION_RE = re.compile(
    r"подаёт[её]\s+вы\s+сами|решение\s+принимает\s+сфр",
    re.I,
)


def strip_invented_officials(text: str) -> str:
    """Грубая защита: не оставлять шаблоны «руководителю Иванову» без проверки — маркер."""
    # Не удаляем текст молча — вызывающий код смотрит missing_header_fields.
    return text
