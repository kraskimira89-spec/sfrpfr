"""Интеграция CAS правки даты на реальной тестовой БД (local/test only).

Пропуск, если DATABASE_URL недоступен или хост не local/test.
Не пишет в production cloud.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from psycopg.types.json import Json

from sfrfr.db.period_date_store import PostgresPeriodDateStore, database_reachable
from sfrfr.security.auth import Principal, StaffRole
from sfrfr.services.period_date_correction import (
    CorrectionOutcome,
    CorrectPeriodDateCommand,
    PeriodCollection,
    PeriodDateField,
    correct_period_date,
)

pytestmark = pytest.mark.skipif(
    not database_reachable(timeout_sec=2.0),
    reason="тестовая БД недоступна (local DATABASE_URL / docker)",
)


def _staff() -> Principal:
    return Principal(
        user_id="11111111-1111-1111-1111-111111111111",
        email="s@example.com",
        role=StaffRole.ADMIN,
    )


@pytest.fixture()
def seeded_case():
    store = PostgresPeriodDateStore()
    case_id = str(uuid.uuid4())
    period_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    updated_at = datetime(2020, 1, 1, tzinfo=UTC)
    try:
        with store._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into public.clients (id, full_name)
                        values (%s::uuid, 'date-op-test')
                        """,
                        (client_id,),
                    )
                    cur.execute(
                        """
                        insert into public.cases (id, client_id, b2c_status)
                        values (%s::uuid, %s::uuid, 'lead')
                        """,
                        (case_id, client_id),
                    )
                    cur.execute(
                        """
                        insert into public.case_pipeline_data
                          (case_id, ils_periods, labor_periods, findings, updated_at)
                        values
                          (%s::uuid, %s::jsonb, '[]'::jsonb, '[]'::jsonb, %s)
                        """,
                        (
                            case_id,
                            Json(
                                [
                                    {
                                        "period_id": period_id,
                                        "employer": "Test",
                                        "date_from": "1987-01-01",
                                        "date_to": "1990-12-31",
                                    }
                                ]
                            ),
                            updated_at,
                        ),
                    )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"fixture case не создан: {type(exc).__name__}: {exc}")

    yield {
        "store": store,
        "case_id": case_id,
        "period_id": period_id,
        "version": updated_at.isoformat(),
        "client_id": client_id,
    }
    try:
        with store._connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "delete from public.case_pipeline_data where case_id = %s::uuid",
                        (case_id,),
                    )
                    cur.execute("delete from public.cases where id = %s::uuid", (case_id,))
                    cur.execute(
                        "delete from public.clients where id = %s::uuid", (client_id,)
                    )
    except Exception:  # noqa: BLE001
        pass


def test_pg_success_and_idempotent(seeded_case: dict) -> None:
    store = seeded_case["store"]
    cmd = CorrectPeriodDateCommand(
        operation_id=str(uuid.uuid4()),
        case_id=seeded_case["case_id"],
        collection=PeriodCollection.ILS,
        period_id=seeded_case["period_id"],
        field=PeriodDateField.DATE_FROM,
        new_value="1985-01-15",
        expected_version=seeded_case["version"],
        reason="integration",
    )
    first = correct_period_date(
        cmd, principal=_staff(), store=store, case_accessible=True
    )
    assert first.outcome == CorrectionOutcome.SAVED
    second = correct_period_date(
        cmd, principal=_staff(), store=store, case_accessible=True
    )
    assert second.outcome == CorrectionOutcome.IDEMPOTENT_REPLAY


def test_pg_concurrent_one_wins(seeded_case: dict) -> None:
    store = seeded_case["store"]
    version = seeded_case["version"]

    def run(op: str, value: str) -> CorrectionOutcome:
        return correct_period_date(
            CorrectPeriodDateCommand(
                operation_id=op,
                case_id=seeded_case["case_id"],
                collection=PeriodCollection.ILS,
                period_id=seeded_case["period_id"],
                field=PeriodDateField.DATE_FROM,
                new_value=value,
                expected_version=version,
                reason="concurrent",
            ),
            principal=_staff(),
            store=store,
            case_accessible=True,
        ).outcome

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(run, str(uuid.uuid4()), "1985-01-15")
        f2 = pool.submit(run, str(uuid.uuid4()), "1984-06-01")
        outcomes = [f1.result(), f2.result()]
    assert outcomes.count(CorrectionOutcome.SAVED) == 1
    assert CorrectionOutcome.VERSION_CONFLICT in outcomes
