"""Отдельный процесс: claim → sleep → finalize (для process-restart тестов).

ENV:
  PRECHECK_PG_DSN
  PRECHECK_TEST_RUN_ID
  PRECHECK_JOB_ID
  PRECHECK_WORKER_ID
  PRECHECK_SLEEP_SEC (default 8)
  PRECHECK_MODE = sleep|finalize_stale|heartbeat
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "precheck_job_pg"))

import psycopg  # noqa: E402
from isolation_guard import require_test_target, verify_test_connection  # noqa: E402
from pg_rest_shim import PgRestShim  # noqa: E402

from sfrfr.services.staff_document_check_lifecycle import (  # noqa: E402
    claim_queued_job,
    finalize_job_as_owner,
    heartbeat_job_lease,
)


def main() -> int:
    target = require_test_target()
    job_id = os.environ["PRECHECK_JOB_ID"]
    worker = os.environ.get("PRECHECK_WORKER_ID") or f"proc:{os.getpid()}"
    sleep_sec = float(os.environ.get("PRECHECK_SLEEP_SEC") or "8")
    mode = os.environ.get("PRECHECK_MODE") or "sleep"

    conn = psycopg.connect(
        target.dsn,
        connect_timeout=5,
        options="-c statement_timeout=10000",
    )
    try:
        verify_test_connection(conn, target)
        client = PgRestShim(conn)
        claimed = claim_queued_job(client, job_id=job_id, worker_id=worker, attempts=1)
        print(f"CLAIMED={bool(claimed)} worker={worker}", flush=True)
        if not claimed:
            return 2
        if mode == "sleep":
            time.sleep(sleep_sec)
            ok = finalize_job_as_owner(
                client,
                job_id=job_id,
                worker_id=worker,
                payload={
                    "status": "completed",
                    "result": {"primary_precheck": {"outcome": "from_old_worker"}},
                    "current_stage": "done",
                    "locked_by": None,
                    "locked_at": None,
                },
            )
            print(f"FINALIZE_OK={ok}", flush=True)
            return 0 if ok else 3
        if mode == "heartbeat":
            for _ in range(int(sleep_sec)):
                heartbeat_job_lease(client, job_id=job_id, worker_id=worker)
                time.sleep(1)
            ok = finalize_job_as_owner(
                client,
                job_id=job_id,
                worker_id=worker,
                payload={
                    "status": "completed",
                    "result": {"primary_precheck": {"outcome": "heartbeat_ok"}},
                    "current_stage": "done",
                    "locked_by": None,
                    "locked_at": None,
                },
            )
            print(f"FINALIZE_OK={ok}", flush=True)
            return 0 if ok else 3
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
