"""Read-only probe одноразового локального precheck PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GUARD_DIR = Path(__file__).resolve().parent / "precheck_job_pg"
sys.path.insert(0, str(GUARD_DIR))

from isolation_guard import (  # noqa: E402
    IsolationError,
    require_test_target,
    verify_test_connection,
)


def emit(result: str, **fields: object) -> None:
    print(
        json.dumps({"result": result, **fields}, ensure_ascii=False),
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only probe of isolated local precheck DB"
    )
    parser.add_argument("--timeout-connect", type=int, default=5)
    parser.add_argument("--timeout-query", type=int, default=8)
    args = parser.parse_args(argv)

    if not 1 <= args.timeout_connect <= 30:
        emit("FAIL", reason="invalid_connect_timeout")
        return 2
    if not 1 <= args.timeout_query <= 60:
        emit("FAIL", reason="invalid_query_timeout")
        return 2

    try:
        target = require_test_target()
    except IsolationError as exc:
        emit("FAIL", reason=str(exc))
        return 2

    try:
        import psycopg
    except ImportError:
        emit("BLOCKED", reason="psycopg_unavailable")
        return 3

    stage = "connect"
    try:
        with psycopg.connect(
            target.dsn,
            connect_timeout=args.timeout_connect,
            options=(
                "-c default_transaction_read_only=on "
                f"-c statement_timeout={args.timeout_query * 1000}"
            ),
        ) as conn:
            stage = "verify_identity"
            verify_test_connection(conn, target)

            with conn.cursor() as cur:
                cur.execute("SHOW transaction_read_only")
                if cur.fetchone()[0] != "on":
                    raise IsolationError("read_only_not_enabled")

                stage = "read_schema"
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'staff_document_check_jobs'
                    ORDER BY ordinal_position
                    """
                )
                columns = cur.fetchall()
                if not columns:
                    raise IsolationError("required_table_missing_or_invisible")

        emit(
            "PASS",
            target="local_precheck",
            run_id=target.run_id,
            read_only=True,
            columns=[
                {"name": name, "type": dtype} for name, dtype in columns
            ],
        )
        return 0

    except IsolationError as exc:
        emit("FAIL", stage=stage, reason=str(exc))
        return 4
    except Exception as exc:  # noqa: BLE001
        emit(
            "BLOCKED",
            stage=stage,
            reason="database_error",
            exc_type=type(exc).__name__,
        )
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
