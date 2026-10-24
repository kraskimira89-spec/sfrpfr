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
    validate_dsn_identity,
)


def test_refuse_database_url_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRECHECK_PG_DSN", raising=False)
    monkeypatch.delenv("PRECHECK_PROBE_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck",
    )
    with pytest.raises(IsolationError, match="missing_"):
        refuse_if_not_isolated(for_probe=True)


def test_refuse_wrong_dbname() -> None:
    with pytest.raises(IsolationError, match="dbname_not_allowlisted"):
        validate_dsn_identity("postgresql://sfrfr:x@127.0.0.1:5432/postgres")


def test_refuse_prod_looking_host() -> None:
    with pytest.raises(IsolationError, match="host_"):
        validate_dsn_identity(
            "postgresql://sfrfr:x@db.xxx.supabase.co:5432/sfrfr_precheck"
        )


def test_refuse_non_local_unknown_host() -> None:
    with pytest.raises(IsolationError, match="host_not_local_allowlisted"):
        validate_dsn_identity(
            "postgresql://sfrfr:x@staging.example.com:5432/sfrfr_precheck"
        )


def test_refuse_wrong_user() -> None:
    with pytest.raises(IsolationError, match="user_not_allowlisted"):
        validate_dsn_identity("postgresql://postgres:x@127.0.0.1:5432/sfrfr_precheck")


def test_accept_local_allowlisted() -> None:
    info = validate_dsn_identity(
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
    )
    assert info.dbname == "sfrfr_precheck"
    assert info.user == "sfrfr"
    assert info.host == "127.0.0.1"


def test_sanitize_strips_password_in_url() -> None:
    msg = _sanitize_exc_message(
        "could not connect to postgresql://sfrfr:secretpass@127.0.0.1/sfrfr_precheck"
    )
    assert "secretpass" not in msg
    assert "***" in msg


def test_probe_cli_refuses_without_test_dsn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Отдельный процесс: DATABASE_URL alone → exit 2, без fallback."""
    import subprocess

    env = os.environ.copy()
    env.pop("PRECHECK_PG_DSN", None)
    env.pop("PRECHECK_PROBE_DATABASE_URL", None)
    env["DATABASE_URL"] = "postgresql://u:p@127.0.0.1/db"
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
    assert "isolation_refused" in proc.stdout
    assert "missing_precheck" in proc.stdout
