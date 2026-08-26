"""Идентификация клиента в текстах ops-уведомлений MAX (ФИО + MAX user_id)."""

from __future__ import annotations

from typing import Any


def is_placeholder_client_name(full_name: str | None) -> bool:
    """True для пустых и служебных имён вроде «MAX user 123» / «MAX 123»."""
    name = (full_name or "").strip()
    if not name:
        return True
    low = name.lower()
    if low.startswith("max user") or low.startswith("max "):
        return True
    if "@" in name:
        return True
    return False


def normalize_ops_full_name(full_name: str | None) -> str | None:
    """Вернуть ФИО для ops или None, если имя-заглушка."""
    name = (full_name or "").strip()
    if is_placeholder_client_name(name):
        return None
    return name


def format_ops_client_block(
    *,
    max_user_id: str | int | None,
    full_name: str | None = None,
) -> str:
    """
    Унифицированный блок для Ops:

    Клиент: Иванов Иван Иванович
    MAX user_id: 12495389

    Без ФИО: «ФИО: не указано»; без MAX: «MAX user_id: не привязан».
    """
    name = normalize_ops_full_name(full_name)
    if name:
        name_line = f"Клиент: {name}"
    else:
        name_line = "ФИО: не указано"

    mid = str(max_user_id).strip() if max_user_id is not None else ""
    if mid and mid.lower() not in {"none", "null"}:
        id_line = f"MAX user_id: {mid}"
    else:
        id_line = "MAX user_id: не привязан"

    return f"{name_line}\n{id_line}"


def _client_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list):
        return raw[0] if raw and isinstance(raw[0], dict) else {}
    if isinstance(raw, dict):
        return raw
    return {}


def lookup_ops_client_full_name(
    *,
    max_user_id: str | int | None = None,
    case_id: str | None = None,
    client_row: dict[str, Any] | None = None,
) -> str | None:
    """
    ФИО для ops: явный client_row → clients по case_id → clients по max_user_id.
    Не тянет телефон/email.
    """
    if client_row:
        name = normalize_ops_full_name(client_row.get("full_name"))
        if name:
            return name

    try:
        from sfrfr.db.session import get_supabase_client

        sb = get_supabase_client()
    except Exception:
        return None

    if case_id:
        try:
            rows = (
                sb.table("cases")
                .select("clients(full_name)")
                .eq("id", str(case_id))
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                name = normalize_ops_full_name(_client_dict(rows[0].get("clients")).get("full_name"))
                if name:
                    return name
        except Exception:
            pass

    mid = str(max_user_id).strip() if max_user_id is not None else ""
    if mid:
        try:
            rows = (
                sb.table("clients")
                .select("full_name")
                .eq("max_user_id", mid)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return normalize_ops_full_name(rows[0].get("full_name"))
        except Exception:
            pass

    return None
