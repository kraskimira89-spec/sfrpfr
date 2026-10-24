"""Read-only probe одноразовой локальной precheck-БД.

Только PRECHECK_PG_DSN + PRECHECK_TEST_RUN_ID.
DATABASE_URL / PRECHECK_PROBE_DATABASE_URL не используются.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "precheck_job_pg"))

from isolation import (  # noqa: E402
    IsolationError,
    _sanitize_exc_message,
    assert_connected_isolation,
    checked_target,
    verify_guard_run,
)


def emit(result: str, **fields: object) -> None:
    print(json.dumps({"result": result, **fields}, ensure_ascii=False), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Precheck DB probe (isolated)")
    parser.add_argument("--timeout-connect", type=int, default=5)
    parser.add_argument("--timeout-query", type=int, default=8)
    args = parser.parse_args(argv)

    if not (1 <= args.timeout_connect <= 30):
        emit("FAIL", reason="invalid_connect_timeout")
        return 2
    if not (1 <= args.timeout_query <= 60):
        emit("FAIL", reason="invalid_query_timeout")
        return 2

    emit(
        "INFO",
        database_url_present=bool(os.environ.get("DATABASE_URL")),
        probe_url_present=bool(os.environ.get("PRECHECK_PROBE_DATABASE_URL")),
        note="DATABASE_URL and PRECHECK_PROBE_DATABASE_URL ignored",
    )

    try:
        dsn, run_id = checked_target()
    except IsolationError as exc:
        emit("FAIL", reason=str(exc))
        return 2

    try:
        import psycopg  # type: ignore
    except ImportError:
        emit("BLOCKED", reason="psycopg_unavailable")
        return 3

    try:
        with psycopg.connect(
            dsn,
            connect_timeout=args.timeout_connect,
            options=(
                "-c default_transaction_read_only=on "
                f"-c statement_timeout={int(args.timeout_query) * 1000}"
            ),
        ) as conn:
            conn.autocommit = True
            identity = assert_connected_isolation(conn)
            verify_guard_run(conn, run_id)
            with conn.cursor() as cur:
                cur.execute("SHOW transaction_read_only")
                if str(cur.fetchone()[0]).lower() not in {"on", "true"}:
                    raise IsolationError("read_only_not_enabled")
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'staff_document_check_jobs'
                    ORDER BY ordinal_position
                    LIMIT 40
                    """
                )
                columns = cur.fetchall()
                if not columns:
                    raise IsolationError("required_table_missing_or_invisible")
        emit(
            "PASS",
            target="local_precheck",
            run_id=run_id,
            read_only=True,
            identity=identity,
            columns=[{"name": n, "type": t} for n, t in columns],
        )
        return 0
    except IsolationError as exc:
        emit("FAIL", reason=str(exc))
        return 4
    except Exception as exc:  # noqa: BLE001
        emit(
            "BLOCKED",
            reason="database_error",
            exc_type=type(exc).__name__,
            detail=_sanitize_exc_message(str(exc)),
        )
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
