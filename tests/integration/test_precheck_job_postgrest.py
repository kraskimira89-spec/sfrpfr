"""Job lifecycle через реальный PostgREST (не PgRestShim).

Требует: tools/precheck_job_pg/up.ps1 → :55432 + :55433
Клиент: supabase create_client → /rest/v1 (как приложение).
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "precheck_job_pg"))

from isolation_guard import (  # noqa: E402
    IsolationError,
    require_test_target,
    verify_test_connection,
)
from postgrest_client import (  # noqa: E402
    build_precheck_supabase_client,
    postgrest_reachable,
)

from sfrfr.services.staff_document_check import (  # noqa: E402
    enqueue_staff_document_check,
)
from sfrfr.services.staff_document_check_lifecycle import (  # noqa: E402
    claim_queued_job,
    finalize_job_as_owner,
)

try:
    require_test_target()
    _DSN_OK = True
except IsolationError:
    _DSN_OK = False

pytestmark = pytest.mark.skipif(
    not (_DSN_OK and postgrest_reachable()),
    reason="PRECHECK_PG_DSN+PRECHECK_TEST_RUN_ID + PostgREST :55433 (up.ps1)",
)


@pytest.fixture()
def rest_client(monkeypatch: pytest.MonkeyPatch):
    import psycopg

    from sfrfr.db import session as db_session

    target = require_test_target()
    client = build_precheck_supabase_client()
    monkeypatch.setattr(db_session, "get_supabase_client", lambda: client)
    with psycopg.connect(target.dsn, connect_timeout=5) as conn:
        conn.autocommit = True
        verify_test_connection(conn, target)
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE staff_document_check_jobs, documents, cases CASCADE"
            )
    yield client


def _seed(client) -> tuple[str, str]:
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
            "documents_fingerprint": "fp-rest",
            "status": "queued",
            "attempts": 0,
            "max_attempts": 3,
            "job_type": "staff_docs_check",
        }
    ).execute()
    return case_id, job_id


def test_postgrest_enqueue_dedupe_real_rest(rest_client) -> None:
    """Кнопка → enqueue через тот же PostgREST-клиентский путь (fixture патчит session)."""
    case_id = str(uuid4())
    rest_client.table("cases").insert({"id": case_id, "flags": {}}).execute()
    rest_client.table("documents").insert(
        {
            "id": str(uuid4()),
            "case_id": case_id,
            "checksum_sha256": "deadbeef",
            "filename": "ils.pdf",
        }
    ).execute()
    first = enqueue_staff_document_check(case_id=case_id, actor_id="staff-e2e")
    assert first.get("ok") is True
    assert first.get("deduped") is False
    assert first.get("job_id")
    second = enqueue_staff_document_check(case_id=case_id, actor_id="staff-e2e")
    assert second.get("ok") is True
    assert second.get("deduped") is True
    assert second.get("job_id") == first.get("job_id")


def test_postgrest_two_workers_one_claim(rest_client) -> None:
    _c, job_id = _seed(rest_client)
    a = claim_queued_job(rest_client, job_id=job_id, worker_id="rest-w1", attempts=1)
    b = claim_queued_job(rest_client, job_id=job_id, worker_id="rest-w2", attempts=1)
    assert a is not None
    assert b is None
    row = (
        rest_client.table("staff_document_check_jobs")
        .select("locked_by,status")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert row["locked_by"] == "rest-w1"
    assert row["status"] == "running"


def test_postgrest_finalize_owner_and_reload(rest_client) -> None:
    _c, job_id = _seed(rest_client)
    w = "rest-owner"
    assert claim_queued_job(rest_client, job_id=job_id, worker_id=w, attempts=1)
    result = {
        "primary_precheck": {
            "outcome": "discrepancies_found",
            "findings": [{"code": "DATE_DIFFERENCE", "source_a": "a", "source_b": "b"}],
            "limitations": ["не недоплата"],
        }
    }
    assert finalize_job_as_owner(
        rest_client,
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
    # новый клиент = «перезапуск процесса» с тем же PostgREST
    client2 = build_precheck_supabase_client()
    row = (
        client2.table("staff_document_check_jobs")
        .select("status,result")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data[0]
    )
    assert row["status"] == "needs_action"
    assert row["result"]["primary_precheck"]["outcome"] == "discrepancies_found"
    # чужой worker не перезапишет
    assert not finalize_job_as_owner(
        rest_client,
        job_id=job_id,
        worker_id="other",
        payload={"status": "failed", "result": {"x": 1}},
    )
