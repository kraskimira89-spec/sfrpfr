"""Отрицательные тесты изоляции precheck DSN (без сети/БД)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "precheck_job_pg"))

from isolation import (  # noqa: E402
    IsolationError,
    _sanitize_exc_message,
    refuse_if_not_isolated,
    require_test_run_id,
    validate_dsn_identity,
)


def test_refuse_database_url_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRECHECK_PG_DSN", raising=False)
    monkeypatch.delenv("PRECHECK_PROBE_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck",
    )
    with pytest.raises(IsolationError, match="missing_test_dsn"):
        refuse_if_not_isolated()


def test_refuse_probe_url_alone_no_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRECHECK_PG_DSN", raising=False)
    monkeypatch.setenv(
        "PRECHECK_PROBE_DATABASE_URL",
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck",
    )
    with pytest.raises(IsolationError, match="missing_test_dsn"):
        refuse_if_not_isolated()


def test_refuse_wrong_dbname() -> None:
    with pytest.raises(IsolationError, match="target_not_allowed"):
        validate_dsn_identity("postgresql://sfrfr:x@127.0.0.1:55432/postgres")


def test_refuse_prod_looking_host() -> None:
    with pytest.raises(IsolationError, match="target_not_allowed"):
        validate_dsn_identity(
            "postgresql://sfrfr:x@db.xxx.supabase.co:5432/sfrfr_precheck"
        )


def test_refuse_wrong_port() -> None:
    with pytest.raises(IsolationError, match="target_not_allowed"):
        validate_dsn_identity("postgresql://sfrfr:x@127.0.0.1:5432/sfrfr_precheck")


def test_refuse_wrong_user() -> None:
    with pytest.raises(IsolationError, match="target_not_allowed"):
        validate_dsn_identity("postgresql://postgres:x@127.0.0.1:55432/sfrfr_precheck")


def test_accept_local_allowlisted() -> None:
    info = validate_dsn_identity(
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
    )
    assert info.dbname == "sfrfr_precheck"
    assert info.user == "sfrfr"
    assert info.host == "127.0.0.1"
    assert info.port == 55432


def test_sanitize_strips_password_in_url() -> None:
    msg = _sanitize_exc_message(
        "could not connect to postgresql://sfrfr:secretpass@127.0.0.1/sfrfr_precheck"
    )
    assert "secretpass" not in msg
    assert "***" in msg


def test_refuse_missing_test_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRECHECK_TEST_RUN_ID", raising=False)
    with pytest.raises(IsolationError, match="missing_precheck_test_run_id"):
        require_test_run_id()


def test_refuse_invalid_test_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRECHECK_TEST_RUN_ID", "bad id")
    with pytest.raises(IsolationError, match="invalid_test_run_id"):
        require_test_run_id()


def test_probe_cli_refuses_without_test_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    env = os.environ.copy()
    env.pop("PRECHECK_PG_DSN", None)
    env.pop("PRECHECK_PROBE_DATABASE_URL", None)
    env["DATABASE_URL"] = "postgresql://u:p@127.0.0.1/db"
    env["PRECHECK_TEST_RUN_ID"] = "precheck_negativetest01"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "precheck_db_probe.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 2
    assert '"result": "FAIL"' in proc.stdout or '"result":"FAIL"' in proc.stdout
    assert "missing_test_dsn" in proc.stdout
