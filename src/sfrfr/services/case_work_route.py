"""Единый SoT маршрута «Работа с делом» для UI и ИИ-агента.

Шаги: 1 проверка документов → 2 сверка сведений → 3 проект обращения.
Нет автоотправки обращения и авто «разбор готов» клиенту.
"""

from __future__ import annotations

from typing import Any, Literal

StepId = Literal["docs_check", "facts_review", "appeal_draft"]
StepStatus = Literal["done", "current", "blocked", "upcoming"]


def build_case_work_route(
    *,
    documents: list[dict[str, Any]],
    document_check: dict[str, Any] | None,
    findings: list[dict[str, Any]] | None = None,
    draft: dict[str, Any] | None = None,
    appeal_generator_enabled: bool = True,
) -> dict[str, Any]:
    """Серверный расчёт этапа, блокеров и primary action."""
    doc_count = len(documents or [])
    check = document_check or {}
    check_status = str(check.get("status") or "").strip().lower()
    check_result = check.get("result") if isinstance(check.get("result"), dict) else None
    stale = bool(check.get("stale"))

    docs_step = _docs_check_step(
        doc_count=doc_count,
        check_status=check_status,
        check_result=check_result,
        stale=stale,
        status_label=str(check.get("status_label") or ""),
        last_error=str(check.get("last_error") or "") or None,
    )

    specialist_questions: list[str] = []
    try:
        from sfrfr.services.case_facts import (
            normalize_findings_to_discrepancies,
            pending_specialist_questions,
        )

        facts_bundle = normalize_findings_to_discrepancies(
            findings or [],
            documents=documents,
        )
        specialist_questions = pending_specialist_questions(facts_bundle)
    except Exception:  # noqa: BLE001
        specialist_questions = []

    facts_step = _facts_review_step(
        docs_step=docs_step,
        check_result=check_result,
        findings=findings or [],
        specialist_questions=specialist_questions,
    )

    appeal_step = _appeal_draft_step(
        docs_step=docs_step,
        facts_step=facts_step,
        draft=draft,
        appeal_generator_enabled=appeal_generator_enabled,
    )

    steps = [docs_step, facts_step, appeal_step]
    current = next((s for s in steps if s["status"] == "current"), None)
    if current is None:
        current = next((s for s in steps if s["status"] == "blocked"), steps[-1])

    return {
        "steps": steps,
        "current_step_id": current["id"],
        "primary_action": current.get("primary_action"),
        "blocker_reason": current.get("blocker_reason"),
        "summary_line": _summary_line(steps),
        "auto_client_notify": False,
        "auto_send_appeal": False,
    }


def _docs_check_step(
    *,
    doc_count: int,
    check_status: str,
    check_result: dict[str, Any] | None,
    stale: bool,
    status_label: str,
    last_error: str | None,
) -> dict[str, Any]:
    if doc_count == 0:
        return {
            "id": "docs_check",
            "title": "Проверка документов",
            "status": "blocked",
            "status_label": "Нет документов",
            "result_summary": "Клиент ещё не загрузил файлы.",
            "primary_action": {
                "id": "request_docs_from_client",
                "label": "Запросить документы",
                "method": "UI",
                "path_suffix": None,
            },
            "blocker_reason": "Дождитесь загрузки документов клиентом.",
            "needs_specialist": False,
        }
    if check_status in {"queued", "running"}:
        return {
            "id": "docs_check",
            "title": "Проверка документов",
            "status": "current",
            "status_label": status_label or "выполняется",
            "result_summary": "Проверка комплекта выполняется.",
            "primary_action": None,
            "blocker_reason": None,
            "needs_specialist": False,
        }
    if check_status == "failed":
        return {
            "id": "docs_check",
            "title": "Проверка документов",
            "status": "current",
            "status_label": "ошибка",
            "result_summary": last_error or "Проверка не завершилась.",
            "primary_action": {
                "id": "request_docs_check",
                "label": "Проверить документы",
                "method": "POST",
                "path_suffix": "request-review",
            },
            "blocker_reason": last_error or "Повторите проверку.",
            "needs_specialist": True,
        }
    if check_result and check_status in {"completed", "needs_action"} and not stale:
        r = check_result
        summary = (
            f"Оригиналы доступны: {r.get('originals_available', 0)}. "
            f"Текст извлечён: {r.get('text_extracted', 0)}. "
            f"Требуют распознавания: {r.get('needs_recognition', 0)}. "
            f"Требуют ручной проверки: {r.get('needs_manual_review', 0)}."
        )
        needs_action = check_status == "needs_action" or int(
            r.get("needs_manual_review") or 0
        ) > 0 or int(r.get("needs_recognition") or 0) > 0
        if needs_action:
            return {
                "id": "docs_check",
                "title": "Проверка документов",
                "status": "current",
                "status_label": "требуется действие",
                "result_summary": summary,
                "primary_action": {
                    "id": "request_docs_check",
                    "label": "Проверить документы",
                    "method": "POST",
                    "path_suffix": "request-review",
                },
                "blocker_reason": str(r.get("next_action") or "Нужна ручная проверка."),
                "needs_specialist": True,
            }
        return {
            "id": "docs_check",
            "title": "Проверка документов",
            "status": "done",
            "status_label": "готово",
            "result_summary": summary,
            "primary_action": None,
            "blocker_reason": None,
            "needs_specialist": False,
        }
    # Нет проверки или stale
    reason = (
        "Набор документов изменился — запустите проверку снова."
        if stale
        else "Проверка ещё не запускалась."
    )
    return {
        "id": "docs_check",
        "title": "Проверка документов",
        "status": "current",
        "status_label": "ожидает",
        "result_summary": reason,
        "primary_action": {
            "id": "request_docs_check",
            "label": "Проверить документы",
            "method": "POST",
            "path_suffix": "request-review",
        },
        "blocker_reason": None,
        "needs_specialist": False,
    }


def _facts_review_step(
    *,
    docs_step: dict[str, Any],
    check_result: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    specialist_questions: list[str] | None = None,
) -> dict[str, Any]:
    if docs_step["status"] != "done":
        return {
            "id": "facts_review",
            "title": "Сверка сведений",
            "status": "upcoming",
            "status_label": "после проверки",
            "result_summary": "Доступно после успешной проверки документов.",
            "primary_action": None,
            "blocker_reason": docs_step.get("blocker_reason")
            or "Сначала завершите проверку документов.",
            "needs_specialist": False,
        }
    missing = list((check_result or {}).get("missing_for_task") or [])
    questions = [q for q in (specialist_questions or []) if q]
    finding_n = len(findings)
    pending_n = len(questions) if questions else finding_n
    if missing or pending_n:
        parts = []
        if pending_n:
            parts.append(f"требуют сверки: {pending_n}")
        if missing:
            parts.append("не хватает: " + "; ".join(missing[:4]))
        blocker = questions[0] if questions else (
            f"Сверьте {pending_n} фрагмент(ов)."
            if pending_n
            else "Уточните недостающие сведения."
        )
        return {
            "id": "facts_review",
            "title": "Сверка сведений",
            "status": "current",
            "status_label": "требуется сверка",
            "result_summary": ". ".join(parts),
            "primary_action": {
                "id": "open_facts_review",
                "label": "Проверить сведения",
                "method": "UI",
                "path_suffix": None,
            },
            "blocker_reason": blocker,
            "needs_specialist": True,
            "specialist_questions": questions[:8],
        }
    return {
        "id": "facts_review",
        "title": "Сверка сведений",
        "status": "done",
        "status_label": "готово",
        "result_summary": "Автоматическая сверка без явных блокеров (черновик).",
        "primary_action": None,
        "blocker_reason": None,
        "needs_specialist": False,
    }


def _appeal_draft_step(
    *,
    docs_step: dict[str, Any],
    facts_step: dict[str, Any],
    draft: dict[str, Any] | None,
    appeal_generator_enabled: bool,
) -> dict[str, Any]:
    if docs_step["status"] != "done" or facts_step["status"] not in {"done", "current"}:
        return {
            "id": "appeal_draft",
            "title": "Проект обращения",
            "status": "upcoming",
            "status_label": "после сверки",
            "result_summary": "Проект станет доступен после сверки сведений.",
            "primary_action": None,
            "blocker_reason": "Сначала проверка документов и сверка.",
            "needs_specialist": False,
        }
    if facts_step["status"] == "current":
        return {
            "id": "appeal_draft",
            "title": "Проект обращения",
            "status": "upcoming",
            "status_label": "после сверки",
            "result_summary": "Сначала закройте сомнительные сведения.",
            "primary_action": None,
            "blocker_reason": facts_step.get("blocker_reason"),
            "needs_specialist": False,
        }
    has_draft = bool(draft and (draft.get("body") or draft.get("title")))
    if has_draft:
        return {
            "id": "appeal_draft",
            "title": "Проект обращения",
            "status": "done",
            "status_label": "черновик есть",
            "result_summary": (
                "Локальный проект готов к утверждению специалистом. "
                "Автоотправка выключена."
            ),
            "primary_action": {
                "id": "request_pipeline",
                "label": "Обновить проект",
                "method": "POST",
                "path_suffix": "request-pipeline",
            },
            "blocker_reason": None,
            "needs_specialist": True,
        }
    if not appeal_generator_enabled:
        return {
            "id": "appeal_draft",
            "title": "Проект обращения",
            "status": "current",
            "status_label": "генератор выключен",
            "result_summary": "Синтетический каркас (generator_enabled=false).",
            "primary_action": {
                "id": "request_pipeline",
                "label": "Сформировать каркас",
                "method": "POST",
                "path_suffix": "request-pipeline",
            },
            "blocker_reason": "Генератор обращений выключен — только каркас.",
            "needs_specialist": True,
            "synthetic": True,
        }
    return {
        "id": "appeal_draft",
        "title": "Проект обращения",
        "status": "current",
        "status_label": "ожидает",
        "result_summary": "Можно сформировать локальный проект с приложениями.",
        "primary_action": {
            "id": "request_pipeline",
            "label": "Сформировать проект",
            "method": "POST",
            "path_suffix": "request-pipeline",
        },
        "blocker_reason": None,
        "needs_specialist": True,
    }


def _summary_line(steps: list[dict[str, Any]]) -> str:
    parts = []
    for s in steps:
        parts.append(f"{s['title']}: {s.get('status_label') or s['status']}")
    return " · ".join(parts)
