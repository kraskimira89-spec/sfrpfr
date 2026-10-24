"""Ворота изоляции: PASS / FAIL / BLOCKED до изменяющих запросов."""

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
    checked_target,
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
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
    ).strip()
    if not (os.environ.get("PRECHECK_TEST_RUN_ID") or "").strip():
        os.environ["PRECHECK_TEST_RUN_ID"] = f"precheck_{uuid.uuid4().hex[:16]}"
    run_id = os.environ["PRECHECK_TEST_RUN_ID"]

    print("=== precheck isolation gate ===", flush=True)
    print(f"SHA: {sha}", flush=True)
    print(f"PRECHECK_TEST_RUN_ID: {run_id}", flush=True)

    checks: list[dict[str, str]] = []
    mutating = "отсутствуют"

    saved_pg = os.environ.pop("PRECHECK_PG_DSN", None)
    os.environ["DATABASE_URL"] = (
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
    )
    try:
        refuse_if_not_isolated()
        checks.append(_check("neg_database_url_only", False, "ожидали отказ"))
    except IsolationError as exc:
        checks.append(_check("neg_database_url_only", True, f"refused:{exc}"))
    finally:
        os.environ.pop("DATABASE_URL", None)
        if saved_pg:
            os.environ["PRECHECK_PG_DSN"] = saved_pg

    try:
        validate_dsn_identity(
            "postgresql://sfrfr:x@db.xxx.supabase.co:5432/sfrfr_precheck"
        )
        checks.append(_check("neg_prod_host", False, "ожидали отказ"))
    except IsolationError as exc:
        checks.append(_check("neg_prod_host", True, f"refused:{exc}"))

    try:
        dsn, rid = checked_target()
        checks.append(_check("checked_target", True, f"run={rid}"))
    except IsolationError as exc:
        checks.append(_check("checked_target", False, str(exc)))
        print("RESULT: BLOCKED — нет валидного PRECHECK_PG_DSN/run_id", flush=True)
        return 3

    try:
        import psycopg
    except Exception:  # noqa: BLE001
        print("RESULT: BLOCKED — psycopg", flush=True)
        return 3

    try:
        conn = psycopg.connect(
            dsn,
            connect_timeout=5,
            options="-c default_transaction_read_only=on",
        )
        conn.autocommit = True
        identity = assert_connected_isolation(conn)
        checks.append(
            _check(
                "connected_identity",
                True,
                f"db={identity['database']} user={identity['user']}",
            )
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sfrfr_test_isolation(marker) VALUES ('should_fail')"
                )
            checks.append(_check("read_only_session", False, "запись прошла"))
            mutating = "дефект"
        except Exception as exc:  # noqa: BLE001
            checks.append(
                _check("read_only_session", True, f"write_blocked:{type(exc).__name__}")
            )
        conn.close()
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("connected_identity", False, type(exc).__name__))
        print(f"RESULT: FAIL — {type(exc).__name__}", flush=True)
        return 1

    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        conn.autocommit = True
        register_test_run(conn, run_id=run_id)
        assert_safe_to_mutate(conn, run_id=run_id)
        checks.append(_check("run_id_owned", True, f"run={run_id}"))
        try:
            assert_safe_to_mutate(conn, run_id="foreign_run_should_fail")
            checks.append(_check("neg_foreign_run", False, "чужой run прошёл"))
            mutating = "дефект"
        except IsolationError as exc:
            checks.append(_check("neg_foreign_run", True, f"refused:{exc}"))
        conn.close()
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("run_id_owned", False, type(exc).__name__))
        print(f"RESULT: FAIL — run {type(exc).__name__}", flush=True)
        return 1

    rest_ok = postgrest_reachable()
    checks.append(
        _check("postgrest_stand", rest_ok, "up" if rest_ok else "down")
    )

    env = os.environ.copy()
    env["PRECHECK_PG_DSN"] = dsn
    env["PRECHECK_TEST_RUN_ID"] = run_id
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
    probe_ok = proc.returncode == 0 and '"PASS"' in (proc.stdout or "")
    checks.append(_check("probe_cli", probe_ok, f"exit={proc.returncode}"))

    hard = [c for c in checks if c["status"] != "PASS" and c["name"] != "postgrest_stand"]
    print("---", flush=True)
    print(f"SHA: {sha}", flush=True)
    print(f"Идентификатор тестового запуска: {run_id}", flush=True)
    print(
        f"Изменяющие запросы до подтверждения изоляции: {mutating}",
        flush=True,
    )
    if hard:
        print("RESULT: FAIL", flush=True)
        return 1
    print("RESULT: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
