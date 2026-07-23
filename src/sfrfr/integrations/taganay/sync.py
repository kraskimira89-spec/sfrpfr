"""Хелпер: неблокирующий sync дела в Taganay CRM."""

from __future__ import annotations

from typing import Any

from sfrfr.integrations.taganay import sync_case_to_taganay


def push_case_to_taganay(case: dict[str, Any], *, task: str | None = None) -> dict[str, Any]:
    """Из строки cases(+clients) отправить минимум в CRM."""
    client = case.get("clients") or {}
    if isinstance(client, list):
        client = client[0] if client else {}
    return sync_case_to_taganay(
        case_id=str(case.get("id") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        pipeline_status=str(case.get("pipeline_status") or ""),
        full_name=client.get("full_name"),
        phone=client.get("phone"),
        email=client.get("email"),
        task=task,
    )
