"""Отрицательный PG: неверный маркер → TRUNCATE не выполняется."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "precheck_job_pg"))

from isolation_guard import (  # noqa: E402
    IsolationError,
    require_test_target,
    verify_test_connection,
)

try:
    _TARGET = require_test_target()
    _OK = True
except IsolationError:
    _TARGET = None
    _OK = False

pytestmark = pytest.mark.skipif(
    not _OK, reason="PRECHECK_PG_DSN+PRECHECK_TEST_RUN_ID; run up.ps1"
)


def test_wrong_run_id_blocks_before_truncate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Контрольная строка в cases остаётся, если guard отклонил чужой run."""
    import psycopg

    assert _TARGET is not None
    sentinel = str(uuid4())

    with psycopg.connect(_TARGET.dsn, connect_timeout=5) as conn:
        conn.autocommit = True
        verify_test_connection(conn, _TARGET)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cases (id, flags) VALUES (%s, '{}'::jsonb)",
                (sentinel,),
            )

    monkeypatch.setenv("PRECHECK_TEST_RUN_ID", "foreign_run_id_99999999")
    with pytest.raises(IsolationError, match="precheck_test_marker_mismatch"):
        bad = require_test_target()
        with psycopg.connect(bad.dsn, connect_timeout=5) as conn:
            verify_test_connection(conn, bad)
            with conn.cursor() as cur:
                cur.execute("TRUNCATE cases CASCADE")

    # Восстановить env и убедиться, что sentinel жив.
    monkeypatch.setenv("PRECHECK_TEST_RUN_ID", _TARGET.run_id)
    with psycopg.connect(_TARGET.dsn, connect_timeout=5) as conn:
        conn.autocommit = True
        verify_test_connection(conn, require_test_target())
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cases WHERE id = %s", (sentinel,))
            assert cur.fetchone() is not None
            cur.execute("DELETE FROM cases WHERE id = %s", (sentinel,))
