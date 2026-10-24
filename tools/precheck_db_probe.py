"""Безопасная диагностика схемы одноразовой тестовой БД precheck.

Только PRECHECK_PROBE_DATABASE_URL или PRECHECK_PG_DSN.
DATABASE_URL / SUPABASE_* не используются (нет fallback).
До query — allowlist db/user/host + маркер sfrfr_test_isolation.
Read-only SELECT information_schema; без клиентских строк.
Исключения печатаются санитизированно (без DSN/паролей).

Пример:
  $env:PRECHECK_PG_DSN='postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck'
  .\\.venv\\Scripts\\python.exe tools\\precheck_db_probe.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "precheck_job_pg"))

from isolation import (  # noqa: E402
    IsolationError,
    _sanitize_exc_message,
    assert_connected_isolation,
    refuse_if_not_isolated,
)


@dataclass
class StepLog:
    steps: list[dict[str, Any]] = field(default_factory=list)

    def mark(self, name: str, **extra: Any) -> None:
        row = {"step": name, "t_ms": int(time.perf_counter() * 1000), **extra}
        self.steps.append(row)
        print(f"[probe] {name}" + (f" {extra}" if extra else ""), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Precheck DB schema probe (isolated)")
    parser.add_argument("--timeout-connect", type=float, default=5.0)
    parser.add_argument("--timeout-query", type=float, default=8.0)
    parser.add_argument(
        "--table",
        default="staff_document_check_jobs",
        help="Только имя таблицы для information_schema",
    )
    args = parser.parse_args(argv)
    log = StepLog()
    log.mark(
        "start",
        python=sys.version.split()[0],
        cwd=os.getcwd(),
        connect_s=args.timeout_connect,
        query_s=args.timeout_query,
        database_url_present=bool(os.environ.get("DATABASE_URL")),
        note="DATABASE_URL ignored",
    )

    try:
        dsn = refuse_if_not_isolated(for_probe=True)
    except IsolationError as exc:
        code = str(exc)
        log.mark("abort", reason=code)
        print(f"RESULT: isolation_refused {code}", flush=True)
        return 2

    log.mark("env_dsn", present=True, hint="redacted_ok")

    try:
        import psycopg  # type: ignore
    except Exception as exc:  # noqa: BLE001
        log.mark("import_psycopg_failed", exc_type=type(exc).__name__)
        print(f"RESULT: import_failed {type(exc).__name__}", flush=True)
        return 3

    conn = None
    try:
        log.mark("connect_begin")
        conn = psycopg.connect(
            dsn,
            connect_timeout=max(1, int(args.timeout_connect)),
        )
        conn.autocommit = True
        # read-only + timeout (литерал int — SET не принимает bind-параметры)
        timeout_ms = int(max(1.0, args.timeout_query) * 1000)
        with conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = on")
            cur.execute(f"SET statement_timeout = {timeout_ms}")
        identity = assert_connected_isolation(conn)
        log.mark("connect_ok", **identity)
    except IsolationError as exc:
        log.mark("isolation_failed", reason=str(exc))
        print(f"RESULT: isolation_refused {exc}", flush=True)
        return 6
    except Exception as exc:  # noqa: BLE001
        log.mark("connect_failed", exc_type=type(exc).__name__)
        print(f"RESULT: connect_failed {type(exc).__name__}", flush=True)
        return 4

    try:
        log.mark("query_begin", table=args.table)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                LIMIT 40
                """,
                (args.table,),
            )
            cols = cur.fetchall()
        log.mark("query_ok", columns=len(cols))
        for name, dtype in cols[:40]:
            print(f"  col {name}: {dtype}", flush=True)
        print("RESULT: ok", flush=True)
        log.mark("done", exit=0)
        return 0
    except Exception as exc:  # noqa: BLE001
        log.mark("query_failed", exc_type=type(exc).__name__)
        print(f"RESULT: query_failed {type(exc).__name__}", flush=True)
        print(_sanitize_exc_message(str(exc)), flush=True)
        return 5
    finally:
        if conn is not None:
            try:
                conn.close()
                log.mark("conn_closed")
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
