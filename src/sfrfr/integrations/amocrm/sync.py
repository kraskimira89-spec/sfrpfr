"""Хелпер: неблокирующий sync дела в amoCRM."""

from __future__ import annotations

from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.amocrm import sync_case_to_amocrm


def _admin_case_url(case_id: str) -> str:
    base = (get_settings().admin_public_url or "").rstrip("/")
    if not base:
        return ""
    return f"{base}/?case={case_id}"


def push_case_to_amocrm(case: dict[str, Any], *, task: str | None = None) -> dict[str, Any]:
    """Из строки cases(+clients) отправить минимум в amoCRM."""
    client = case.get("clients") or {}
    if isinstance(client, list):
        client = client[0] if client else {}
    case_id = str(case.get("id") or "")
    return sync_case_to_amocrm(
        case_id=case_id,
        b2c_status=str(case.get("b2c_status") or ""),
        pipeline_status=str(case.get("pipeline_status") or ""),
        full_name=client.get("full_name"),
        phone=client.get("phone"),
        email=client.get("email"),
        channel=client.get("preferred_channel"),
        source="sfrfr",
        consent=True,
        crm_external_id=str(case["crm_external_id"]) if case.get("crm_external_id") else None,
        case_url=_admin_case_url(case_id) or None,
        task=task,
    )


def persist_crm_external_id(case_id: str, lead_id: str) -> None:
    """Сохранить ID сделки amo в cases.crm_external_id (best-effort)."""
    try:
        from sfrfr.db.session import get_supabase_client

        get_supabase_client().table("cases").update({"crm_external_id": str(lead_id)}).eq(
            "id", case_id
        ).execute()
    except Exception:  # noqa: BLE001
        return
