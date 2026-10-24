"""Ворота изоляции precheck: PASS / FAIL / BLOCKED до изменяющих запросов.

Единый источник DSN: PRECHECK_PG_DSN или PRECHECK_PROBE_DATABASE_URL.
DATABASE_URL никогда не используется.

Пример:
  $env:PRECHECK_PG_DSN='postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck'
  $env:PRECHECK_TEST_RUN_ID='cycle5-iso-001'
  .\\.venv\\Scripts\\python.exe tools\\precheck_job_pg\\run_isolation_gate.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from isolation import (  # noqa: E402
    IsolationError,
    assert_connected_isolation,
    assert_safe_to_mutate,
    refuse_if_not_isolated,
    register_test_run,
    validate_dsn_identity,
)
from postgrest_client import postgrest_reachable  # noqa: E402


def _check(name: str, ok: bool, detail: str) -> dict[str, str]:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}", flush=True)
    return {"name": name, "status": status, "detail": detail}


def main() -> int:
    sha = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True)
        .strip()
    )
    run_id = (os.environ.get("PRECHECK_TEST_RUN_ID") or "").strip() or (
        f"gate-{uuid.uuid4().hex[:12]}"
    )
    os.environ["PRECHECK_TEST_RUN_ID"] = run_id

    print("=== precheck isolation gate ===", flush=True)
    print(f"SHA: {sha}", flush=True)
    print(f"PRECHECK_TEST_RUN_ID: {run_id}", flush=True)
    print(
        f"DATABASE_URL present (ignored): {bool(os.environ.get('DATABASE_URL'))}",
        flush=True,
    )

    checks: list[dict[str, str]] = []
    mutating_before_ok = "отсутствуют"

    # 1) Нет fallback: только DATABASE_URL → refuse
    saved_pg = os.environ.pop("PRECHECK_PG_DSN", None)
    saved_probe = os.environ.pop("PRECHECK_PROBE_DATABASE_URL", None)
    os.environ["DATABASE_URL"] = (
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
    )
    try:
        refuse_if_not_isolated(for_probe=True)
        checks.append(
            _check("neg_database_url_only", False, "ожидали IsolationError")
        )
    except IsolationError as exc:
        checks.append(
            _check("neg_database_url_only", True, f"refused:{exc}")
        )
    finally:
        os.environ.pop("DATABASE_URL", None)
        if saved_pg:
            os.environ["PRECHECK_PG_DSN"] = saved_pg
        if saved_probe:
            os.environ["PRECHECK_PROBE_DATABASE_URL"] = saved_probe

    # 2) Неподходящий host / db
    try:
        validate_dsn_identity(
            "postgresql://sfrfr:x@db.xxx.supabase.co:5432/sfrfr_precheck"
        )
        checks.append(_check("neg_prod_host", False, "ожидали отказ"))
    except IsolationError as exc:
        checks.append(_check("neg_prod_host", True, f"refused:{exc}"))

    try:
        validate_dsn_identity("postgresql://sfrfr:x@127.0.0.1:5432/postgres")
        checks.append(_check("neg_wrong_dbname", False, "ожидали отказ"))
    except IsolationError as exc:
        checks.append(_check("neg_wrong_dbname", True, f"refused:{exc}"))

    # 3) Явный тестовый DSN + connect + marker + read-only probe CLI
    try:
        dsn = refuse_if_not_isolated(for_probe=False)
        checks.append(_check("resolve_test_dsn", True, "PRECHECK_* ok (redacted)"))
    except IsolationError as exc:
        checks.append(_check("resolve_test_dsn", False, str(exc)))
        print("RESULT: BLOCKED — нет валидного тестового DSN", flush=True)
        return 3

    try:
        import psycopg
    except Exception as exc:  # noqa: BLE001
        print(f"RESULT: BLOCKED — psycopg:{type(exc).__name__}", flush=True)
        return 3

    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = on")
        identity = assert_connected_isolation(conn)
        checks.append(
            _check(
                "connected_identity",
                True,
                f"db={identity['database']} user={identity['user']} marker=ok",
            )
        )
        # read-only: новая транзакция после SET session — запись должна падать
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sfrfr_test_isolation(marker) VALUES ('should_fail')"
                )
            checks.append(_check("read_only_session", False, "запись прошла"))
            mutating_before_ok = "дефект"
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sfrfr_test_isolation WHERE marker = 'should_fail'"
                )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                _check("read_only_session", True, f"write_blocked:{type(exc).__name__}")
            )
        conn.close()
    except IsolationError as exc:
        checks.append(_check("connected_identity", False, str(exc)))
        print(f"RESULT: FAIL — {exc}", flush=True)
        return 1
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("connected_identity", False, type(exc).__name__))
        print(f"RESULT: FAIL — connect {type(exc).__name__}", flush=True)
        return 1

    # 4) Регистрация run + отказ чужой очистки
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        conn.autocommit = True
        register_test_run(conn, run_id=run_id)
        owned = assert_safe_to_mutate(conn, run_id=run_id)
        checks.append(_check("run_id_owned", True, f"run={owned}"))
        try:
            assert_safe_to_mutate(conn, run_id="foreign-run-should-fail")
            checks.append(_check("neg_foreign_run_cleanup", False, "чужой run прошёл"))
            mutating_before_ok = "дефект"
        except IsolationError as exc:
            checks.append(
                _check("neg_foreign_run_cleanup", True, f"refused:{exc}")
            )
        conn.close()
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("run_id_owned", False, type(exc).__name__))
        print(f"RESULT: FAIL — run_id {type(exc).__name__}", flush=True)
        return 1

    # 5) PostgREST цель (если поднят)
    rest_ok = postgrest_reachable()
    checks.append(
        _check(
            "postgrest_stand",
            rest_ok,
            "http://127.0.0.1:55433" if rest_ok else "not_reachable",
        )
    )

    # 6) probe CLI exit 0
    env = os.environ.copy()
    env["PRECHECK_PG_DSN"] = dsn
    env.pop("DATABASE_URL", None)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "precheck_db_probe.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    probe_ok = proc.returncode == 0 and "RESULT: ok" in (proc.stdout or "")
    checks.append(
        _check("probe_cli", probe_ok, f"exit={proc.returncode}")
    )

    failed = [c for c in checks if c["status"] != "PASS"]
    # postgrest optional for isolation PASS — if fail, BLOCKED only if required
    hard_failed = [c for c in failed if c["name"] != "postgrest_stand"]
    print("---", flush=True)
    print(f"SHA: {sha}", flush=True)
    print(f"Идентификатор тестового запуска: {run_id}", flush=True)
    print(
        "Компоненты: probe+psycopg → PRECHECK_PG_DSN (redacted); "
        f"PostgREST={'up' if rest_ok else 'down'}",
        flush=True,
    )
    print(
        f"Изменяющие запросы до подтверждения изоляции: {mutating_before_ok}",
        flush=True,
    )
    if hard_failed:
        print("RESULT: FAIL", flush=True)
        for c in hard_failed:
            print(f"  - {c['name']}: {c['detail']}", flush=True)
        return 1
    if failed:
        print("RESULT: PASS (с оговоркой PostgREST)", flush=True)
        return 0
    print("RESULT: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
