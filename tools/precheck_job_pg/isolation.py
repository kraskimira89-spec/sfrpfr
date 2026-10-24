"""Принудительная изоляция локального PG-harness precheck (без production).

Контракт:
  PRECHECK_PG_DSN      — единственный DSN (без DATABASE_URL / PROBE fallback)
  PRECHECK_TEST_RUN_ID — владелец стенда (precheck_test_guard.environment)

Допустимая цель: postgresql://sfrfr:*@127.0.0.1:55432/sfrfr_precheck
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

ALLOWED_DB = "sfrfr_precheck"
ALLOWED_USER = "sfrfr"
ALLOWED_HOST = "127.0.0.1"
ALLOWED_PORT = 55432
ISOLATION_MARKER = "sfrfr_precheck_isolation_ok"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


@dataclass(frozen=True)
class ParsedDsn:
    scheme: str
    user: str
    host: str
    port: int | None
    dbname: str
    has_password: bool


class IsolationError(RuntimeError):
    """Отказ до любой записи/чтения клиентских данных."""


def _sanitize_exc_message(text: str) -> str:
    out = str(text or "")
    out = re.sub(r"postgres(?:ql)?://[^\s]+", "postgresql://***", out, flags=re.I)
    out = re.sub(r"password\s*=\s*\S+", "password=***", out, flags=re.I)
    out = re.sub(r":[^:@/\s]+@", ":***@", out)
    return out[:240]


def parse_dsn(dsn: str) -> ParsedDsn:
    raw = (dsn or "").strip()
    if not raw:
        raise IsolationError("empty_dsn")
    try:
        url = urlsplit(raw)
    except ValueError as exc:
        raise IsolationError("invalid_test_dsn") from exc
    user = unquote(url.username or "")
    host = (url.hostname or "").lower()
    dbname = unquote(url.path or "").lstrip("/").split("?")[0]
    if not user or not host or not dbname:
        raise IsolationError("dsn_incomplete")
    if url.query or url.fragment:
        raise IsolationError("dsn_has_query_or_fragment")
    return ParsedDsn(
        scheme=(url.scheme or "").lower(),
        user=user,
        host=host,
        port=url.port,
        dbname=dbname,
        has_password=bool(url.password),
    )


def validate_dsn_identity(dsn: str) -> ParsedDsn:
    """Строгий локальный harness: только 127.0.0.1:55432/sfrfr_precheck/sfrfr."""
    info = parse_dsn(dsn)
    if info.scheme not in {"postgres", "postgresql"}:
        raise IsolationError("scheme_not_postgres")
    allowed = (
        info.host == ALLOWED_HOST
        and info.port == ALLOWED_PORT
        and info.dbname == ALLOWED_DB
        and info.user == ALLOWED_USER
        and info.has_password
    )
    if not allowed:
        raise IsolationError("target_not_allowed")
    return info


def resolve_test_dsn(*, for_probe: bool = False) -> str:
    """Только PRECHECK_PG_DSN. DATABASE_URL и PRECHECK_PROBE_* не читаются."""
    del for_probe  # единый контракт для probe и tests
    dsn = (os.environ.get("PRECHECK_PG_DSN") or "").strip()
    if not dsn:
        raise IsolationError("missing_test_dsn")
    # Явно запретить «молчаливый» fallback: если кто-то задал только старые имена.
    if os.environ.get("PRECHECK_PROBE_DATABASE_URL") and not dsn:
        raise IsolationError("probe_url_deprecated_use_precheck_pg_dsn")
    validate_dsn_identity(dsn)
    return dsn


def require_test_run_id() -> str:
    rid = (os.environ.get("PRECHECK_TEST_RUN_ID") or "").strip()
    if not rid:
        raise IsolationError("missing_precheck_test_run_id")
    if not RUN_ID_RE.fullmatch(rid):
        raise IsolationError("invalid_test_run_id")
    return rid


def checked_target() -> tuple[str, str]:
    """DSN + run_id до connect. Общий вход для probe и фикстур."""
    dsn = resolve_test_dsn()
    run_id = require_test_run_id()
    return dsn, run_id


def assert_connected_isolation(conn: Any) -> dict[str, str]:
    """После connect: current_database/user + legacy marker."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        db, user = cur.fetchone()
        db_s, user_s = str(db), str(user)
        if db_s != ALLOWED_DB:
            raise IsolationError("server_identity_mismatch")
        if user_s != ALLOWED_USER:
            raise IsolationError("server_identity_mismatch")
        cur.execute(
            "SELECT marker FROM public.sfrfr_test_isolation WHERE marker = %s LIMIT 1",
            (ISOLATION_MARKER,),
        )
        if not cur.fetchone():
            raise IsolationError("isolation_marker_missing")
    return {"database": db_s, "user": user_s, "marker": ISOLATION_MARKER}


def verify_guard_run(conn: Any, run_id: str) -> None:
    """Маркер precheck_test_guard.environment принадлежит текущему run_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM precheck_test_guard.environment
                WHERE singleton IS TRUE AND run_id = %s
            )
            """,
            (run_id,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            raise IsolationError("test_marker_mismatch")


def refuse_if_not_isolated(dsn: str | None = None, *, for_probe: bool = False) -> str:
    try:
        if dsn:
            validate_dsn_identity(dsn.strip())
            return dsn.strip()
        return resolve_test_dsn(for_probe=for_probe)
    except IsolationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IsolationError(_sanitize_exc_message(type(exc).__name__)) from None


def assert_safe_to_mutate(conn: Any, *, run_id: str | None = None) -> str:
    """До TRUNCATE/INSERT: изоляция + guard run_id. Чужой run → отказ."""
    assert_connected_isolation(conn)
    rid = (run_id or "").strip() or require_test_run_id()
    if not RUN_ID_RE.fullmatch(rid):
        raise IsolationError("invalid_test_run_id")
    verify_guard_run(conn, rid)
    return rid


def register_test_run(conn: Any, *, run_id: str | None = None) -> str:
    """Записать владельца стенда (только bootstrap / up.ps1 / явный setup)."""
    assert_connected_isolation(conn)
    rid = (run_id or "").strip() or require_test_run_id()
    if not RUN_ID_RE.fullmatch(rid):
        raise IsolationError("invalid_test_run_id")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO precheck_test_guard.environment (singleton, run_id)
            VALUES (TRUE, %s)
            ON CONFLICT (singleton) DO UPDATE SET run_id = EXCLUDED.run_id
            """,
            (rid,),
        )
        cur.execute(
            """
            INSERT INTO public.sfrfr_test_run (run_id)
            VALUES (%s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (rid,),
        )
    return rid
