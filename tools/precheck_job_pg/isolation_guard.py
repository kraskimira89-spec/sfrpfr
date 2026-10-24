"""Fail-closed guard для одноразового локального precheck PostgreSQL."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


class IsolationError(RuntimeError):
    """Сообщение содержит только безопасный код причины."""


@dataclass(frozen=True)
class TestTarget:
    dsn: str
    run_id: str


def require_test_target(
    environ: Mapping[str, str] | None = None,
) -> TestTarget:
    env = os.environ if environ is None else environ
    dsn = env.get("PRECHECK_PG_DSN", "").strip()
    run_id = env.get("PRECHECK_TEST_RUN_ID", "").strip()

    if not dsn:
        raise IsolationError("missing_precheck_pg_dsn")

    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", run_id):
        raise IsolationError("invalid_precheck_test_run_id")

    try:
        url = urlsplit(dsn)
        allowed = (
            url.scheme in {"postgres", "postgresql"}
            and url.hostname == "127.0.0.1"
            and url.port == 55432
            and unquote(url.path) == "/sfrfr_precheck"
            and unquote(url.username or "") == "sfrfr"
            and bool(url.password)
            and not url.query
            and not url.fragment
        )
    except ValueError:
        raise IsolationError("invalid_precheck_pg_dsn") from None

    if not allowed:
        raise IsolationError("precheck_target_not_allowed")

    return TestTarget(dsn=dsn, run_id=run_id)


def verify_test_connection(conn, target: TestTarget) -> None:
    """Не создаёт маркер и не выполняет изменяющих запросов."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        if cur.fetchone() != ("sfrfr_precheck", "sfrfr"):
            raise IsolationError("precheck_server_identity_mismatch")

        cur.execute(
            """
            SELECT run_id
            FROM precheck_test_guard.environment
            WHERE singleton = TRUE
            """
        )
        rows = cur.fetchall()

        if len(rows) != 1 or rows[0][0] != target.run_id:
            raise IsolationError("precheck_test_marker_mismatch")
