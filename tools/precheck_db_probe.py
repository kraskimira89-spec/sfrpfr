"""Безопасная диагностика доступности схемы (без DSN/паролей/ПДн).

Один запуск. Без бесконечных retry. Production не требуется — только
явный DATABASE_URL / SUPABASE из env локальной/тестовой среды.

Пример:
  .\\.venv\\Scripts\\python.exe tools\\precheck_db_probe.py --timeout-connect 5 --timeout-query 8
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepLog:
    steps: list[dict[str, Any]] = field(default_factory=list)

    def mark(self, name: str, **extra: Any) -> None:
        row = {"step": name, "t_ms": int(time.perf_counter() * 1000), **extra}
        self.steps.append(row)
        print(f"[probe] {name}" + (f" {extra}" if extra else ""), flush=True)


def _redact_url(url: str) -> str:
    if not url:
        return "(empty)"
    # схема://…host… без credentials
    try:
        if "://" in url:
            scheme, rest = url.split("://", 1)
            host = rest.split("@")[-1].split("/")[0]
            return f"{scheme}://***@{host}/…"
    except Exception:  # noqa: BLE001
        pass
    return "(set, redacted)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Precheck DB schema probe (safe)")
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
    )

    dsn = (
        os.environ.get("PRECHECK_PROBE_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    log.mark("env_dsn", present=bool(dsn), hint=_redact_url(dsn))
    if not dsn:
        log.mark("abort", reason="no_dsn")
        print(
            "RESULT: no_dsn — задайте PRECHECK_PROBE_DATABASE_URL тестовой БД",
            flush=True,
        )
        return 2

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
        log.mark("connect_ok")
    except Exception as exc:  # noqa: BLE001
        log.mark(
            "connect_failed",
            exc_type=type(exc).__name__,
            # без текста, если в нём может быть DSN
        )
        print(f"RESULT: connect_failed {type(exc).__name__}", flush=True)
        return 4

    try:
        log.mark("query_begin", table=args.table)
        conn.autocommit = True
        with conn.cursor() as cur:
            # statement_timeout в ms
            cur.execute(
                "SET statement_timeout = %s",
                (int(max(1.0, args.timeout_query) * 1000),),
            )
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
        # только имена/типы колонок — без данных
        for name, dtype in cols[:40]:
            print(f"  col {name}: {dtype}", flush=True)
        print("RESULT: ok", flush=True)
        log.mark("done", exit=0)
        return 0
    except Exception as exc:  # noqa: BLE001
        log.mark("query_failed", exc_type=type(exc).__name__)
        print(f"RESULT: query_failed {type(exc).__name__}", flush=True)
        # короткий traceback без env
        tb = traceback.format_exception_only(type(exc), exc)
        for line in tb[-2:]:
            print(line.rstrip(), flush=True)
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
