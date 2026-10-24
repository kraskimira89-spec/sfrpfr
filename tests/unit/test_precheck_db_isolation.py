"""Совместимость probe CLI с isolation_guard (subprocess)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_probe_cli_refuses_without_precheck_pg_dsn() -> None:
    import subprocess

    env = os.environ.copy()
    env.pop("PRECHECK_PG_DSN", None)
    env.pop("PRECHECK_PROBE_DATABASE_URL", None)
    env["DATABASE_URL"] = "postgresql://u:p@127.0.0.1/db"
    env["PRECHECK_TEST_RUN_ID"] = "precheck_negativetest01"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "precheck_db_probe.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 2
    assert "missing_precheck_pg_dsn" in proc.stdout
    assert '"FAIL"' in proc.stdout or '"result": "FAIL"' in proc.stdout
