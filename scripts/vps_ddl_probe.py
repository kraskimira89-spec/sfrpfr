"""One-off VPS probe: terminate stuck sessions and time CREATE VIEW DDL."""

from __future__ import annotations

import json
import time
from pathlib import Path

import psycopg

ENV_PATH = Path("/opt/sfrfr/.env")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value.strip().strip('"').strip("'")
    return env


def main() -> None:
    env = load_env(ENV_PATH)
    host = env["DBT_HOST"]
    port = int(env["DBT_PORT"])
    user = env["DBT_USER"]
    password = env["DBT_PASSWORD"]
    dbname = env["DBT_DBNAME"]

    def connect(*, autocommit: bool = False) -> psycopg.Connection:
        conn = psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            sslmode="require",
            connect_timeout=20,
            application_name="sfrfr-ddl-probe",
        )
        conn.autocommit = autocommit
        return conn

    with connect(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select pid, state, wait_event_type, wait_event,
                       left(query, 80), now() - xact_start
                from pg_stat_activity
                where usename = current_user and pid <> pg_backend_pid()
                """
            )
            rows = cur.fetchall()
            print("other_sessions", rows)
            for pid, *_rest in rows:
                cur.execute("select pg_terminate_backend(%s)", (pid,))
                print("terminated", pid, cur.fetchone())

    with connect(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select current_setting('statement_timeout'), "
                "current_setting('lock_timeout'), current_user"
            )
            print("settings", cur.fetchone())
            cur.execute(
                """
                select n.nspname, c.relname, c.relkind
                from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname in ('analytics', 'analytics_source')
                order by 1, 2
                """
            )
            print("relations", cur.fetchall())
            cur.execute(
                """
                select locktype, mode, granted, pid, relation::regclass
                from pg_locks
                where pid in (
                    select pid from pg_stat_activity where usename = current_user
                )
                limit 50
                """
            )
            print("locks", cur.fetchall())

    started = time.monotonic()
    with connect(autocommit=False) as conn:
        with conn.cursor() as cur:
            try:
                before_ddl = time.monotonic()
                cur.execute(
                    """
                    create or replace view analytics._probe_stg_cases as
                    select id, status, created_at
                    from analytics_source.cases
                    """
                )
                after_ddl = time.monotonic()
                cur.execute("select count(*) from analytics._probe_stg_cases")
                count = cur.fetchone()[0]
                after_count = time.monotonic()
                print(
                    json.dumps(
                        {
                            "ddl_ok": True,
                            "connect_to_ddl_ms": round((before_ddl - started) * 1000),
                            "ddl_ms": round((after_ddl - before_ddl) * 1000),
                            "count_ms": round((after_count - after_ddl) * 1000),
                            "count": count,
                        }
                    )
                )
            except Exception as error:  # noqa: BLE001
                print(
                    json.dumps(
                        {
                            "ddl_ok": False,
                            "elapsed_ms": round((time.monotonic() - started) * 1000),
                            "error_type": type(error).__name__,
                            "error": str(error)[:500],
                        }
                    )
                )
            finally:
                conn.rollback()
                print("rolled_back")


if __name__ == "__main__":
    main()
