"""Принудительная изоляция тестовой БД precheck (без production DSN).

Правила:
- только PRECHECK_PG_DSN / PRECHECK_PROBE_DATABASE_URL (без DATABASE_URL);
- имя БД и пользователь из allowlist;
- host не похож на prod;
- после connect — маркер sfrfr_test_isolation.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

ALLOWED_DB_NAMES = frozenset({"sfrfr_precheck"})
ALLOWED_USERS = frozenset({"sfrfr"})
ISOLATION_MARKER = "sfrfr_precheck_isolation_ok"
FORBIDDEN_HOST_RE = re.compile(
    r"(proverkastaza|supabase2|yandex|amazonaws|azure|"
    r"^\d{1,3}(\.\d{1,3}){3}$)",  # сырые IP — не для одноразового local docker имени
    re.IGNORECASE,
)
# Локальные имена docker / loopback допустимы.
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "precheck-pg", "::1"})


@dataclass(frozen=True)
class ParsedDsn:
    scheme: str
    user: str
    host: str
    port: int | None
    dbname: str


class IsolationError(RuntimeError):
    """Отказ до любой записи/чтения клиентских данных."""


def _sanitize_exc_message(text: str) -> str:
    """Убрать credentials/DSN-подобные фрагменты из текста ошибки."""
    out = str(text or "")
    out = re.sub(r"postgres(?:ql)?://[^\s]+", "postgresql://***", out, flags=re.I)
    out = re.sub(r"password\s*=\s*\S+", "password=***", out, flags=re.I)
    out = re.sub(r":[^:@/\s]+@", ":***@", out)
    return out[:240]


def parse_dsn(dsn: str) -> ParsedDsn:
    raw = (dsn or "").strip()
    if not raw:
        raise IsolationError("empty_dsn")
    if "://" not in raw:
        raise IsolationError("dsn_not_url")
    parsed = urlparse(raw)
    user = unquote(parsed.username or "")
    host = (parsed.hostname or "").lower()
    dbname = (parsed.path or "").lstrip("/").split("?")[0]
    if not user or not host or not dbname:
        raise IsolationError("dsn_incomplete")
    return ParsedDsn(
        scheme=(parsed.scheme or "").lower(),
        user=user,
        host=host,
        port=parsed.port,
        dbname=dbname,
    )


def validate_dsn_identity(dsn: str) -> ParsedDsn:
    """Проверка DSN до connect. Не печатает секреты."""
    info = parse_dsn(dsn)
    if info.scheme not in {"postgres", "postgresql"}:
        raise IsolationError("scheme_not_postgres")
    if info.dbname not in ALLOWED_DB_NAMES:
        raise IsolationError("dbname_not_allowlisted")
    if info.user not in ALLOWED_USERS:
        raise IsolationError("user_not_allowlisted")
    if info.host not in LOCAL_HOSTS:
        if FORBIDDEN_HOST_RE.search(info.host):
            raise IsolationError("host_forbidden")
        # неизвестный host — отказ (нет «похоже на test» по слову)
        raise IsolationError("host_not_local_allowlisted")
    return info


def resolve_test_dsn(*, for_probe: bool = False) -> str:
    """Только явный тестовый env. DATABASE_URL / SUPABASE_* игнорируются."""
    # Никогда не читать DATABASE_URL / SUPABASE_DB_URL как fallback.
    dsn = (os.environ.get("PRECHECK_PROBE_DATABASE_URL") or "").strip()
    if not dsn:
        dsn = (os.environ.get("PRECHECK_PG_DSN") or "").strip()
    if not dsn:
        if for_probe:
            raise IsolationError("missing_precheck_probe_database_url")
        raise IsolationError("missing_precheck_pg_dsn")
    validate_dsn_identity(dsn)
    return dsn


def assert_connected_isolation(conn: Any) -> dict[str, str]:
    """После connect: current_database/user + маркер. Read-only SELECT."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        db, user = cur.fetchone()
        db_s, user_s = str(db), str(user)
        if db_s not in ALLOWED_DB_NAMES:
            raise IsolationError("connected_dbname_mismatch")
        if user_s not in ALLOWED_USERS:
            raise IsolationError("connected_user_mismatch")
        cur.execute(
            "SELECT marker FROM public.sfrfr_test_isolation WHERE marker = %s LIMIT 1",
            (ISOLATION_MARKER,),
        )
        row = cur.fetchone()
        if not row:
            raise IsolationError("isolation_marker_missing")
    return {"database": db_s, "user": user_s, "marker": ISOLATION_MARKER}


def refuse_if_not_isolated(dsn: str | None = None, *, for_probe: bool = False) -> str:
    """Единая точка входа: вернуть DSN или raise IsolationError."""
    try:
        resolved = dsn.strip() if dsn else resolve_test_dsn(for_probe=for_probe)
        validate_dsn_identity(resolved)
        return resolved
    except IsolationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IsolationError(_sanitize_exc_message(type(exc).__name__)) from None
