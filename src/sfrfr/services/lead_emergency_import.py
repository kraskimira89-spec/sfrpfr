"""Доимпорт аварийного буфера заявок в БД после её восстановления (идемпотентно).

Заявки с сайта → clients + cases (как обычный лид). Записи MAX не импортируются:
дело создаётся само при следующем сообщении клиента, переписка сливается из
``max_chat_pending.json`` (``flush_pending_case_chat``). Тестовые записи пропускаются.
"""

from __future__ import annotations

from typing import Any

from sfrfr.services.lead_emergency_buffer import load_emergency_leads, rewrite_emergency_leads


def _insert_site_lead(rec: dict[str, Any]) -> str:
    from sfrfr.api.routes.public_leads import insert_lead_rows

    return insert_lead_rows(
        full_name=str(rec.get("full_name") or "Клиент"),
        phone=rec.get("phone"),
        email=rec.get("email"),
        preferred=str(rec.get("channel") or "unset"),
        source=str(rec.get("attribution_source") or "wordpress"),
        audience_segment=rec.get("audience_segment"),
        audit_action=f"emergency_lead_import:{rec.get('id')}",
    )


def import_emergency_leads(*, apply: bool) -> dict[str, Any]:
    rows = load_emergency_leads()
    todo = [
        r
        for r in rows
        if r.get("source") == "site" and not r.get("imported_case_id") and not r.get("is_test")
    ]
    report: dict[str, Any] = {
        "total": len(rows),
        "to_import": len(todo),
        "skipped_test": sum(1 for r in rows if r.get("is_test")),
        "max_pending": sum(1 for r in rows if r.get("source") == "max"),
        "imported": 0,
        "errors": 0,
    }
    if not apply:
        return report
    for rec in todo:
        try:
            rec["imported_case_id"] = _insert_site_lead(rec)
            report["imported"] += 1
        except Exception:  # noqa: BLE001
            report["errors"] += 1
        rewrite_emergency_leads(rows)
    return report
