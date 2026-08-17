"""Runtime diagnostics for the dbt PostgreSQL connection.

The probe avoids PII, reads no rows from client tables, and rolls back its
temporary DDL transaction. Results are written to the active debug NDJSON log.
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DEBUG_LOG = ROOT / "debug-bf1557.log"


def debug_log(hypothesis_id: str, message: str, **data: object) -> None:
    # region agent log
    entry = {
        "sessionId": "bf1557",
        "runId": "dbt-runtime-probe",
        "hypothesisId": hypothesis_id,
        "location": "scripts/dbt_runtime_probe.py",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with DEBUG_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # endregion


def execute_probe(cursor: psycopg.Cursor, hypothesis_id: str, name: str, sql: str) -> None:
    started_at = time.monotonic()
    try:
        cursor.execute(sql)
        result = cursor.fetchone()
        debug_log(
            hypothesis_id,
            f"{name}: ok",
            elapsed_ms=round((time.monotonic() - started_at) * 1000),
            result=str(result)[:200],
        )
    except Exception as error:  # noqa: BLE001
        debug_log(
            hypothesis_id,
            f"{name}: error",
            elapsed_ms=round((time.monotonic() - started_at) * 1000),
            error_type=type(error).__name__,
            error=str(error)[:500],
        )


def main() -> None:
    load_dotenv(ROOT / ".env")
    required = ("DBT_HOST", "DBT_USER", "DBT_PASSWORD", "DBT_DBNAME")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        debug_log("H0", "DBT environment incomplete", missing=missing)
        raise SystemExit(2)

    host = os.environ["DBT_HOST"]
    port = int(os.environ.get("DBT_PORT", "5433"))
    sslmode = os.environ.get("DBT_SSLMODE", "disable")
    if host.startswith("db.") and host.endswith(".supabase.co"):
        host_kind = "cloud_direct"
    elif ".pooler.supabase.com" in host:
        host_kind = "pooler"
    elif port == 5433:
        host_kind = "yc_direct"
    else:
        host_kind = "other"
    if port == 5432:
        debug_log(
            "H0",
            "DBT_PORT=5432 warning (often Supavisor; YC dbt canon is 5433)",
            host_kind=host_kind,
        )
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        families = {
            "ipv4": sum(address[0] == socket.AF_INET for address in addresses),
            "ipv6": sum(address[0] == socket.AF_INET6 for address in addresses),
        }
        debug_log("H5", "DNS resolved", host_kind=host_kind, **families)
    except OSError as error:
        debug_log("H5", "DNS resolution error", host_kind=host_kind, error=str(error)[:500])
        raise

    started_at = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=10):
            debug_log(
                "H6",
                "TCP port reachable",
                host_kind=host_kind,
                elapsed_ms=round((time.monotonic() - started_at) * 1000),
            )
    except OSError as error:
        debug_log(
            "H6",
            "TCP port unreachable",
            host_kind=host_kind,
            elapsed_ms=round((time.monotonic() - started_at) * 1000),
            error_type=type(error).__name__,
            error=str(error)[:500],
        )
        raise

    try:
        with psycopg.connect(
            host=host,
            port=port,
            user=os.environ["DBT_USER"],
            password=os.environ["DBT_PASSWORD"],
            dbname=os.environ["DBT_DBNAME"],
            sslmode=sslmode,
            connect_timeout=15,
            application_name="sfrfr-dbt-runtime-probe",
            autocommit=False,
        ) as connection:
            debug_log(
                "H1",
                "dbt connection established",
                host_kind=host_kind,
                port=str(port),
                sslmode=sslmode,
            )
            with connection.cursor() as cursor:
                execute_probe(
                    cursor,
                    "H2",
                    "timeout settings",
                    """
                    select
                      current_setting('statement_timeout'),
                      current_setting('lock_timeout'),
                      current_setting('idle_in_transaction_session_timeout')
                    """,
                )
                execute_probe(cursor, "H4", "analytics source select", "select count(*) from analytics_source.cases")
                probe_name = f"__dbt_probe_{uuid.uuid4().hex}"
                started_at = time.monotonic()
                try:
                    cursor.execute("begin")
                    cursor.execute(f'create view analytics."{probe_name}" as select 1 as probe_value')
                    cursor.execute("rollback")
                    debug_log(
                        "H3",
                        "transactional analytics DDL: ok",
                        elapsed_ms=round((time.monotonic() - started_at) * 1000),
                    )
                except Exception as error:  # noqa: BLE001
                    debug_log(
                        "H3",
                        "transactional analytics DDL: error",
                        elapsed_ms=round((time.monotonic() - started_at) * 1000),
                        error_type=type(error).__name__,
                        error=str(error)[:500],
                    )
                    try:
                        connection.rollback()
                    except Exception as rollback_error:  # noqa: BLE001
                        debug_log(
                            "H3",
                            "transactional analytics DDL rollback: error",
                            error_type=type(rollback_error).__name__,
                            error=str(rollback_error)[:500],
                        )
    except Exception as error:  # noqa: BLE001
        debug_log("H1", "connection-level error", error_type=type(error).__name__, error=str(error)[:500])
        raise


if __name__ == "__main__":
    main()
