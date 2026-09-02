"""Запись в case_messages с учётом схемы self-host без новых колонок."""

from __future__ import annotations

import re
from typing import Any

from sfrfr.db.session import get_supabase_client

_OPTIONAL_COLUMNS = (
    "channel_origin",
    "client_message_id",
    "reply_to_message_id",
    "external_message_id",
    "delivered_at",
    "read_at_client",
    "read_at_staff",
    "updated_at",
)

_MISSING_COLUMN_RE = re.compile(
    r"Could not find the '([^']+)' column|column case_messages\.(\w+) does not exist",
    re.I,
)


def _missing_column(exc: BaseException) -> str | None:
    text = str(exc)
    if "case_messages" not in text and "schema cache" not in text:
        return None
    match = _MISSING_COLUMN_RE.search(text)
    if not match:
        return None
    return match.group(1) or match.group(2)


def insert_case_message(row: dict[str, Any]) -> dict[str, Any]:
    """INSERT в case_messages; убирает колонки, которых ещё нет в prod-схеме."""
    payload = {k: v for k, v in row.items() if v is not None}
    sb = get_supabase_client()
    while payload:
        try:
            response = sb.table("case_messages").insert(payload).execute()
            return (response.data or [{}])[0]
        except Exception as exc:  # noqa: BLE001 — postgrest.APIError
            col = _missing_column(exc)
            if col and col in payload:
                payload.pop(col)
                continue
            optional_left = [k for k in _OPTIONAL_COLUMNS if k in payload]
            if optional_left:
                for key in optional_left:
                    payload.pop(key, None)
                continue
            raise
    raise RuntimeError("case_messages insert: empty payload")
