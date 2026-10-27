"""create_docs_order_atomic: при уже открытом DOCS — DocsOrderSlotConflict."""

from unittest.mock import MagicMock, patch

import pytest

from sfrfr.db.case_repository import DocsOrderSlotConflict
from sfrfr.services.docs_order_create import create_docs_order_atomic


def test_atomic_create_raises_when_open_docs_exists() -> None:
    conn = MagicMock()
    tx = MagicMock()
    conn.transaction.return_value.__enter__ = MagicMock(return_value=tx)
    conn.transaction.return_value.__exit__ = MagicMock(return_value=False)
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    # execute calls: lock, select rows, (no insert)
    select_result = MagicMock()
    select_result.fetchall.return_value = [
        {
            "package_code": "ACCOMP",
            "amount_rub": 5000,
            "status": "pending",
            "invoice_status": None,
        }
    ]
    conn.execute.side_effect = [MagicMock(), select_result]

    with (
        patch("sfrfr.services.docs_order_create.get_settings") as gs,
        patch("sfrfr.services.docs_order_create.psycopg.connect", return_value=conn),
        patch("sfrfr.services.docs_order_create._psycopg_dsn", return_value="postgresql://x"),
    ):
        gs.return_value.database_url = "postgresql://x"
        with pytest.raises(DocsOrderSlotConflict):
            create_docs_order_atomic(
                case_id="1579e69f-f74f-4c38-9fb1-c65493afe3c4",
                amount_rub=5000,
                status_value="pending",
            )
