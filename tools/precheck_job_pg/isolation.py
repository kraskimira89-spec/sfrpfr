"""Совместимость: тонкая обёртка над isolation_guard (канон Strategist).

Новый код должен импортировать isolation_guard напрямую.
Маркер создаёт только bootstrap (up.ps1), не фикстуры.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlsplit

from isolation_guard import (  # noqa: F401
    IsolationError,
    TestTarget,
    require_test_target,
    verify_test_connection,
)

ISOLATION_MARKER = "sfrfr_precheck_isolation_ok"
ALLOWED_DB = "sfrfr_precheck"
ALLOWED_USER = "sfrfr"


def _sanitize_exc_message(text: str) -> str:
    out = str(text or "")
    out = re.sub(r"postgres(?:ql)?://[^\s]+", "postgresql://***", out, flags=re.I)
    out = re.sub(r"password\s*=\s*\S+", "password=***", out, flags=re.I)
    out = re.sub(r":[^:@/\s]+@", ":***@", out)
    return out[:240]


def refuse_if_not_isolated(dsn: str | None = None, *, for_probe: bool = False) -> str:
    del for_probe
    if dsn:
        # Проверка явного DSN через urlsplit (тот же контракт).
        try:
            url = urlsplit(dsn.strip())
            ok = (
                url.scheme in {"postgres", "postgresql"}
                and url.hostname == "127.0.0.1"
                and url.port == 55432
                and unquote(url.path) == "/sfrfr_precheck"
                and unquote(url.username or "") == "sfrfr"
                and bool(url.password)
                and not url.query
                and not url.fragment
            )
        except ValueError as exc:
            raise IsolationError("invalid_precheck_pg_dsn") from exc
        if not ok:
            raise IsolationError("precheck_target_not_allowed")
        return dsn.strip()
    return require_test_target().dsn


def checked_target() -> tuple[str, str]:
    t = require_test_target()
    return t.dsn, t.run_id


def assert_connected_isolation(conn: Any) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        db, user = cur.fetchone()
        if (db, user) != (ALLOWED_DB, ALLOWED_USER):
            raise IsolationError("precheck_server_identity_mismatch")
        cur.execute(
            "SELECT marker FROM public.sfrfr_test_isolation WHERE marker = %s LIMIT 1",
            (ISOLATION_MARKER,),
        )
        if not cur.fetchone():
            raise IsolationError("isolation_marker_missing")
    return {"database": str(db), "user": str(user), "marker": ISOLATION_MARKER}


def assert_safe_to_mutate(conn: Any, *, run_id: str | None = None) -> str:
    target = require_test_target()
    if run_id and run_id != target.run_id:
        # Явный чужой run — до verify.
        raise IsolationError("precheck_test_marker_mismatch")
    verify_test_connection(conn, target)
    assert_connected_isolation(conn)
    return target.run_id


def validate_dsn_identity(dsn: str) -> Any:
    refuse_if_not_isolated(dsn)
    url = urlsplit(dsn.strip())
    return type(
        "ParsedDsn",
        (),
        {
            "scheme": url.scheme,
            "user": unquote(url.username or ""),
            "host": url.hostname,
            "port": url.port,
            "dbname": unquote(url.path or "").lstrip("/"),
            "has_password": bool(url.password),
        },
    )()


def require_test_run_id() -> str:
    return require_test_target().run_id


def verify_guard_run(conn: Any, run_id: str) -> None:
    verify_test_connection(conn, TestTarget(dsn="", run_id=run_id))
