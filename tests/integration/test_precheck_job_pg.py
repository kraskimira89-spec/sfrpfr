"""Интеграция staff_document_check_jobs на изолированном Postgres.

Требует PRECHECK_PG_DSN (см. tools/precheck_job_pg/up.ps1).
Путь доступа: PgRestShim (тот же table/update/eq CAS, что PostgREST-клиент).
Production DSN не используется.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

ROOT = Path(__file__).resolve().parents[2]
SHIM = ROOT / "tools" / "precheck_job_pg"
sys.path.insert(0, str(SHIM))

from isolation import (  # noqa: E402
    IsolationError,
    assert_connected_isolation,
    refuse_if_not_isolated,
)
from pg_rest_shim import PgRestShim  # noqa: E402

from sfrfr.services.staff_document_check_lifecycle import (  # noqa: E402
    claim_queued_job,
    finalize_job_as_owner,
    heartbeat_job_lease,
    notify_already_recorded,
    reclaim_stale_running_jobs,
    result_already_finalized,
)

try:
    DSN = refuse_if_not_isolated(for_probe=False)
    _ISOLATION_OK = True
    _ISOLATION_REASON = ""
except IsolationError as _exc:
    DSN = ""
    _ISOLATION_OK = False
    _ISOLATION_REASON = str(_exc)

pytestmark = pytest.mark.skipif(
    not _ISOLATION_OK,
    reason=(
        f"isolated PRECHECK_PG_DSN required ({_ISOLATION_REASON or 'missing'}); "
        "run tools/precheck_job_pg/up.ps1 — DATABASE_URL fallback запрещён"
    ),
)


@pytest.fixture()
def pg(monkeypatch: pytest.MonkeyPatch):
    import psycopg
    from isolation import assert_safe_to_mutate, register_test_run, require_test_run_id

    run_id = os.environ.get("PRECHECK_TEST_RUN_ID") or "pytest-precheck-job-pg"
    monkeypatch.setenv("PRECHECK_TEST_RUN_ID", run_id)
    conn = psycopg.connect(DSN)
    conn.autocommit = False
    assert_connected_isolation(conn)
    register_test_run(conn, run_id=run_id)
    conn.commit()
    assert_safe_to_mutate(conn, run_id=require_test_run_id())
    client = PgRestShim(conn)
    # чистая песочница; маркер isolation / run не трогаем
    with conn.cursor() as cur:
        cur.execute("TRUNCATE staff_document_check_jobs, documents, cases CASCADE")
    conn.commit()
    yield client, conn
    conn.close()


def _seed_case_job(client: PgRestShim, *, fingerprint: str = "fp1") -> tuple[str, str]:
    case_id = str(uuid4())
    job_id = str(uuid4())
    client.table("cases").insert({"id": case_id, "flags": {}}).execute()
    client.table("documents").insert(
        {
            "id": str(uuid4()),
            "case_id": case_id,
            "checksum_sha256": "abc",
            "filename": "ils.pdf",
        }
    ).execute()
    client.table("staff_document_check_jobs").insert(
        {
            "id": job_id,
            "case_id": case_id,
            "documents_fingerprint": fingerprint,
            "status": "queued",
            "attempts": 0,
            "max_attempts": 3,
            "job_type": "staff_docs_check",
        }
    ).execute()
    return case_id, job_id


def test_save_reload_result_same_meaning(pg) -> None:
    client, conn = pg
    _case_id, job_id = _seed_case_job(client)
    w = "worker-a"
    assert claim_queued_job(client, job_id=job_id, worker_id=w, attempts=1)
    result = {
        "primary_precheck": {
            "outcome": "discrepancies_found",
            "findings": [{"code": "DATE_DIFFERENCE", "source_a": "ils:1", "source_b": "l:1"}],
            "limitations": ["не недоплата"],
        },
        "document_set_revision": "fp1",
    }
    assert finalize_job_as_owner(
        client,
        job_id=job_id,
        worker_id=w,
        payload={
            "status": "needs_action",
            "result": result,
            "current_stage": "done",
            "locked_by": None,
            "locked_at": None,
        },
    )
    # новый «экземпляр» клиента
    import psycopg

    conn2 = psycopg.connect(DSN)
    client2 = PgRestShim(conn2)
    row = (
        client2.table("staff_document_check_jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    conn2.close()
    assert row["status"] == "needs_action"
    assert row["result"]["primary_precheck"]["outcome"] == "discrepancies_found"
    assert row["result"]["document_set_revision"] == "fp1"
    assert result_already_finalized(row)


def test_two_handlers_only_one_claims(pg) -> None:
    client, _conn = pg
    _c, job_id = _seed_case_job(client)
    a = claim_queued_job(client, job_id=job_id, worker_id="w1", attempts=1)
    b = claim_queued_job(client, job_id=job_id, worker_id="w2", attempts=1)
    assert a is not None
    assert b is None
    row = (
        client.table("staff_document_check_jobs")
        .select("locked_by,status")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert row["locked_by"] == "w1"
    assert row["status"] == "running"


def test_reclaim_after_stale_then_old_worker_cannot_overwrite(pg, monkeypatch) -> None:
    client, _conn = pg
    _c, job_id = _seed_case_job(client)
    old = "old-worker"
    assert claim_queued_job(client, job_id=job_id, worker_id=old, attempts=1)
    # состарить lease
    old_ts = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    client.table("staff_document_check_jobs").update(
        {"locked_at": old_ts, "updated_at": old_ts}
    ).eq("id", job_id).execute()

    monkeypatch.setattr(
        "sfrfr.db.session.get_supabase_client", lambda: client
    )
    out = reclaim_stale_running_jobs(older_than_sec=60)
    assert out["requeued"] == 1
    row = (
        client.table("staff_document_check_jobs")
        .select("status,locked_by")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert row["status"] == "queued"
    assert row["locked_by"] is None

    new = "new-worker"
    assert claim_queued_job(client, job_id=job_id, worker_id=new, attempts=2)
    assert finalize_job_as_owner(
        client,
        job_id=job_id,
        worker_id=new,
        payload={
            "status": "completed",
            "result": {"primary_precheck": {"outcome": "from_new"}},
            "locked_by": None,
            "locked_at": None,
        },
    )
    # старый не может перезаписать
    assert not finalize_job_as_owner(
        client,
        job_id=job_id,
        worker_id=old,
        payload={
            "status": "completed",
            "result": {"primary_precheck": {"outcome": "from_old"}},
            "locked_by": None,
            "locked_at": None,
        },
    )
    final = (
        client.table("staff_document_check_jobs")
        .select("result")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert final["result"]["primary_precheck"]["outcome"] == "from_new"


def test_heartbeat_prevents_false_reclaim(pg, monkeypatch) -> None:
    client, _conn = pg
    _c, job_id = _seed_case_job(client)
    w = "live-worker"
    assert claim_queued_job(client, job_id=job_id, worker_id=w, attempts=1)
    assert heartbeat_job_lease(client, job_id=job_id, worker_id=w)
    monkeypatch.setattr("sfrfr.db.session.get_supabase_client", lambda: client)
    out = reclaim_stale_running_jobs(older_than_sec=60)
    assert out["requeued"] == 0
    row = (
        client.table("staff_document_check_jobs")
        .select("status,locked_by")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert row["status"] == "running"
    assert row["locked_by"] == w


def test_notify_retry_without_recompute_flag(pg) -> None:
    client, _conn = pg
    _c, job_id = _seed_case_job(client)
    w = "w"
    claim_queued_job(client, job_id=job_id, worker_id=w, attempts=1)
    result = {
        "primary_precheck": {"outcome": "discrepancies_found", "client_summary": "x"},
        # notify отсутствует — как после crash до enqueue
    }
    finalize_job_as_owner(
        client,
        job_id=job_id,
        worker_id=w,
        payload={
            "status": "completed",
            "result": result,
            "locked_by": None,
            "locked_at": None,
        },
    )
    row = (
        client.table("staff_document_check_jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert result_already_finalized(row)
    assert not notify_already_recorded(row)
    # догон: только client_notify, outcome тот же
    merged = {
        **row["result"],
        "client_notify": {"ok": True, "message_id": f"precheck:{job_id}", "skipped": False},
    }
    client.table("staff_document_check_jobs").update(
        {"result": merged}
    ).eq("id", job_id).execute()
    row2 = (
        client.table("staff_document_check_jobs")
        .select("result")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert row2["result"]["primary_precheck"]["outcome"] == "discrepancies_found"
    assert notify_already_recorded(row2)
    # повторная запись того же message_id — идемпотентность на уровне флага
    assert row2["result"]["client_notify"]["message_id"] == f"precheck:{job_id}"


def test_process_restart_subprocess_old_cannot_overwrite(pg, monkeypatch) -> None:
    """Остановка/запуск отдельного процесса, не повтор функции в одном тесте."""
    client, _conn = pg
    _c, job_id = _seed_case_job(client)
    env = os.environ.copy()
    env["PRECHECK_PG_DSN"] = DSN
    env["PRECHECK_JOB_ID"] = job_id
    env["PRECHECK_WORKER_ID"] = "proc-old"
    env["PRECHECK_SLEEP_SEC"] = "12"
    env["PRECHECK_MODE"] = "sleep"
    proc = subprocess.Popen(
        [sys.executable, str(SHIM / "worker_once.py")],
        env=env,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # дождаться claim
    time.sleep(1.5)
    # состарить и reclaim (имитация падения без heartbeat)
    old_ts = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    client.table("staff_document_check_jobs").update(
        {"locked_at": old_ts}
    ).eq("id", job_id).eq("locked_by", "proc-old").execute()
    monkeypatch.setattr("sfrfr.db.session.get_supabase_client", lambda: client)
    reclaim_stale_running_jobs(older_than_sec=60)
    new = claim_queued_job(client, job_id=job_id, worker_id="proc-new", attempts=2)
    assert new is not None
    assert finalize_job_as_owner(
        client,
        job_id=job_id,
        worker_id="proc-new",
        payload={
            "status": "completed",
            "result": {"primary_precheck": {"outcome": "from_new_proc"}},
            "locked_by": None,
            "locked_at": None,
        },
    )
    code = proc.wait(timeout=30)
    out = proc.stdout.read() if proc.stdout else ""
    # старый процесс либо не смог finalize, либо exit 3
    row = (
        client.table("staff_document_check_jobs")
        .select("result")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert row["result"]["primary_precheck"]["outcome"] == "from_new_proc"
    assert "from_old_worker" not in str(row["result"])
    assert code in {0, 3}  # 0 если finalize до reclaim (редко), 3 если отвергнут
    assert "CLAIMED=True" in out


def test_stale_fingerprint_marked_on_reload(pg) -> None:
    client, _conn = pg
    case_id, job_id = _seed_case_job(client, fingerprint="fp-old")
    w = "w"
    claim_queued_job(client, job_id=job_id, worker_id=w, attempts=1)
    finalize_job_as_owner(
        client,
        job_id=job_id,
        worker_id=w,
        payload={
            "status": "completed",
            "result": {
                "primary_precheck": {"outcome": "no_discrepancies_found"},
                "document_set_revision": "fp-old",
            },
            "documents_fingerprint": "fp-old",
            "locked_by": None,
            "locked_at": None,
        },
    )
    # новый документ во время/после — меняем набор
    client.table("documents").insert(
        {
            "id": str(uuid4()),
            "case_id": case_id,
            "checksum_sha256": "newdoc",
            "filename": "extra.pdf",
        }
    ).execute()
    docs = (
        client.table("documents")
        .select("id,checksum_sha256")
        .eq("case_id", case_id)
        .execute()
        .data
    )
    from sfrfr.services.staff_document_check_result import documents_fingerprint

    current_fp = documents_fingerprint(docs)
    job = (
        client.table("staff_document_check_jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    stale = job["documents_fingerprint"] != current_fp
    assert stale is True
    assert job["result"]["document_set_revision"] == "fp-old"
