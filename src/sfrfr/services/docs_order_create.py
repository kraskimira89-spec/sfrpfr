"""Атомарное создание DOCS (ACCOMP≤6500): advisory lock + проверка + insert."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from sfrfr.core.config import get_settings
from sfrfr.db.case_repository import DocsOrderSlotConflict
from sfrfr.db.period_date_store import _psycopg_dsn
from sfrfr.services.message_dedupe import has_open_or_paid_docs_order

_LOCK_NS = 871_001  # namespace for docs-order locks


def create_docs_order_atomic(
    *,
    case_id: str,
    amount_rub: float,
    status_value: str,
    actor_id: str | None = None,
    due_at: str | None = None,
    service_label: str | None = None,
    invoice_status: str | None = None,
) -> dict[str, Any]:
    """Создать DOCS-заказ под xact advisory lock (защита от гонки двух POST)."""
    from sfrfr.services.staff_finance import invoice_number_from_id

    dsn = _psycopg_dsn(get_settings().database_url)
    cid = str(case_id).strip()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute(
                "SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
                (_LOCK_NS, f"docs-order:{cid}"),
            )
            rows = conn.execute(
                """
                SELECT package_code, amount_rub, status, invoice_status
                FROM public.orders
                WHERE case_id = %s::uuid
                """,
                (cid,),
            ).fetchall()
            if has_open_or_paid_docs_order(list(rows)):
                raise DocsOrderSlotConflict(
                    "Счёт на подготовку первичных обращений уже есть"
                )
            row = conn.execute(
                """
                INSERT INTO public.orders (case_id, package_code, amount_rub, status)
                VALUES (%s::uuid, 'ACCOMP', %s, %s)
                RETURNING *
                """,
                (cid, float(amount_rub), status_value),
            ).fetchone()
            if not row:
                raise RuntimeError("docs order insert returned no row")
            oid = str(row.get("id") or "")
            extra: dict[str, Any] = {}
            if oid:
                extra["invoice_number"] = invoice_number_from_id(oid)
            if due_at:
                extra["due_at"] = due_at
            if service_label:
                extra["service_label"] = service_label
            if invoice_status:
                extra["invoice_status"] = invoice_status
            elif status_value == "draft":
                extra["invoice_status"] = "draft"
            if extra and oid:
                sets = ", ".join(f"{k} = %s" for k in extra)
                vals = list(extra.values()) + [oid]
                updated = conn.execute(
                    f"UPDATE public.orders SET {sets} WHERE id = %s::uuid RETURNING *",
                    vals,
                ).fetchone()
                if updated:
                    row = updated
    return dict(row)
