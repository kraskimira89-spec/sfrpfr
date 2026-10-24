"""Ворота изоляции: PASS/FAIL/BLOCKED. Маркер создаёт только up.ps1."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from isolation_guard import (  # noqa: E402
    IsolationError,
    require_test_target,
    verify_test_connection,
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
    print("=== precheck isolation gate ===", flush=True)
    print(f"SHA: {sha}", flush=True)

    checks: list[dict[str, str]] = []
    mutating = "отсутствуют"

    saved = os.environ.pop("PRECHECK_PG_DSN", None)
    os.environ["DATABASE_URL"] = (
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
    )
    try:
        require_test_target()
        checks.append(_check("neg_database_url_only", False, "ожидали отказ"))
    except IsolationError as exc:
        checks.append(_check("neg_database_url_only", True, f"refused:{exc}"))
    finally:
        os.environ.pop("DATABASE_URL", None)
        if saved:
            os.environ["PRECHECK_PG_DSN"] = saved

    try:
        target = require_test_target()
        checks.append(_check("require_test_target", True, f"run={target.run_id}"))
    except IsolationError as exc:
        print(f"RESULT: BLOCKED — {exc}", flush=True)
        return 3

    try:
        import psycopg
    except Exception:  # noqa: BLE001
        print("RESULT: BLOCKED — psycopg", flush=True)
        return 3

    try:
        with psycopg.connect(
            target.dsn,
            connect_timeout=5,
            options="-c default_transaction_read_only=on",
        ) as conn:
            conn.autocommit = True
            verify_test_connection(conn, target)
            checks.append(_check("verify_test_connection", True, "ok"))
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO sfrfr_test_isolation(marker) VALUES ('should_fail')"
                    )
                checks.append(_check("read_only", False, "запись прошла"))
                mutating = "дефект"
            except Exception as exc:  # noqa: BLE001
                checks.append(
                    _check("read_only", True, f"write_blocked:{type(exc).__name__}")
                )
    except IsolationError as exc:
        checks.append(_check("verify_test_connection", False, str(exc)))
        print(f"RESULT: FAIL — {exc}", flush=True)
        return 1

    try:
        bad = type(target)(dsn=target.dsn, run_id="foreign_run_id_99999999")
        with psycopg.connect(target.dsn, connect_timeout=5) as conn:
            verify_test_connection(conn, bad)
        checks.append(_check("neg_foreign_run", False, "чужой run прошёл"))
        mutating = "дефект"
    except IsolationError as exc:
        checks.append(_check("neg_foreign_run", True, f"refused:{exc}"))

    rest_ok = postgrest_reachable()
    checks.append(_check("postgrest", rest_ok, "up" if rest_ok else "down"))

    env = os.environ.copy()
    env["PRECHECK_PG_DSN"] = target.dsn
    env["PRECHECK_TEST_RUN_ID"] = target.run_id
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

    hard = [c for c in checks if c["status"] != "PASS" and c["name"] != "postgrest"]
    print("---", flush=True)
    print(f"SHA: {sha}", flush=True)
    print(f"Идентификатор тестового запуска: {target.run_id}", flush=True)
    print(f"Изменяющие запросы до подтверждения изоляции: {mutating}", flush=True)
    if hard:
        print("RESULT: FAIL", flush=True)
        return 1
    print("RESULT: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
