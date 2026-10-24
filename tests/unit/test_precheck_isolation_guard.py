"""Unit-тесты isolation_guard (без сети/БД)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "precheck_job_pg"))

from isolation_guard import (  # noqa: E402
    IsolationError,
    require_test_target,
    verify_test_connection,
)


def valid_env() -> dict[str, str]:
    return {
        "PRECHECK_PG_DSN": (
            "postgresql://sfrfr:local-test-password@127.0.0.1:55432/sfrfr_precheck"
        ),
        "PRECHECK_TEST_RUN_ID": "precheck_test_12345678",
    }


def test_accepts_explicit_local_target() -> None:
    target = require_test_target(valid_env())
    assert target.run_id == "precheck_test_12345678"


def test_general_database_url_is_not_a_fallback() -> None:
    with pytest.raises(IsolationError, match="missing_precheck_pg_dsn"):
        require_test_target(
            {
                "DATABASE_URL": "postgresql://user:secret@example.invalid/prod",
                "PRECHECK_TEST_RUN_ID": "precheck_test_12345678",
            }
        )


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://sfrfr:pw@example.invalid:55432/sfrfr_precheck",
        "postgresql://sfrfr:pw@127.0.0.1:5432/sfrfr_precheck",
        "postgresql://sfrfr:pw@127.0.0.1:55432/postgres",
        "postgresql://postgres:pw@127.0.0.1:55432/sfrfr_precheck",
        "postgresql://sfrfr:pw@127.0.0.1:55432/sfrfr_precheck?host=elsewhere",
        "host=127.0.0.1 dbname=sfrfr_precheck",
    ],
)
def test_rejects_wrong_targets(dsn: str) -> None:
    env = valid_env()
    env["PRECHECK_PG_DSN"] = dsn
    with pytest.raises(IsolationError):
        require_test_target(env)


@pytest.mark.parametrize("run_id", ["", "short", "../unsafe", "x" * 81])
def test_rejects_invalid_run_id(run_id: str) -> None:
    env = valid_env()
    env["PRECHECK_TEST_RUN_ID"] = run_id
    with pytest.raises(IsolationError, match="invalid_precheck_test_run_id"):
        require_test_target(env)


def test_checks_server_identity_before_marker() -> None:
    target = require_test_target(valid_env())
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = ("production", "sfrfr")

    with pytest.raises(IsolationError, match="server_identity_mismatch"):
        verify_test_connection(conn, target)

    assert cur.execute.call_count == 1


def test_rejects_wrong_marker() -> None:
    target = require_test_target(valid_env())
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = ("sfrfr_precheck", "sfrfr")
    cur.fetchall.return_value = [("another_run",)]

    with pytest.raises(IsolationError, match="test_marker_mismatch"):
        verify_test_connection(conn, target)


def test_accepts_matching_marker() -> None:
    target = require_test_target(valid_env())
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = ("sfrfr_precheck", "sfrfr")
    cur.fetchall.return_value = [(target.run_id,)]

    verify_test_connection(conn, target)
