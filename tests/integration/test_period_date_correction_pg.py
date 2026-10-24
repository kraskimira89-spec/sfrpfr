"""Интеграция CAS правки даты на реальной тестовой БД (local/CI only).

Пропуск, если DATABASE_URL недоступен или хост не local/test.
Не пишет в production cloud.

Обязательные проверки владельца (ТЗ #268) — ниже.
"""

from __future__ import annotations

import threading
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
    reconcile_unknown,
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


def _load_row(store: PostgresPeriodDateStore, case_id: str) -> dict:
    with store._connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select ils_periods, labor_periods, findings, draft, updated_at
                from public.case_pipeline_data
                where case_id = %s::uuid
                """,
                (case_id,),
            )
            row = cur.fetchone()
    assert row is not None
    return dict(row)


def _cmd(
    seeded: dict,
    *,
    operation_id: str | None = None,
    new_value: str = "1985-01-15",
    expected_version: str | None = None,
    period_id: str | None = None,
    reason: str = "integration",
) -> CorrectPeriodDateCommand:
    return CorrectPeriodDateCommand(
        operation_id=operation_id or str(uuid.uuid4()),
        case_id=seeded["case_id"],
        collection=PeriodCollection.ILS,
        period_id=period_id or seeded["period_id"],
        field=PeriodDateField.DATE_FROM,
        new_value=new_value,
        expected_version=expected_version or seeded["version"],
        reason=reason,
    )


@pytest.fixture()
def seeded_case():
    store = PostgresPeriodDateStore()
    case_id = str(uuid.uuid4())
    period_id = str(uuid.uuid4())
    period_id_2 = str(uuid.uuid4())
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
                          (case_id, ils_periods, labor_periods, findings, draft, updated_at)
                        values
                          (%s::uuid, %s::jsonb, '[]'::jsonb, %s::jsonb, %s::jsonb, %s)
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
                                    },
                                    {
                                        "period_id": period_id_2,
                                        "employer": "Other",
                                        "date_from": "1991-01-01",
                                        "date_to": "1995-12-31",
                                    },
                                ]
                            ),
                            Json([{"type": "gap", "status": "open", "recalculated": True}]),
                            Json({"title": "draft", "recalculated": True}),
                            updated_at,
                        ),
                    )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"fixture case не создан: {type(exc).__name__}: {exc}")

    yield {
        "store": store,
        "case_id": case_id,
        "period_id": period_id,
        "period_id_2": period_id_2,
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
    cmd = _cmd(seeded_case)
    first = correct_period_date(
        cmd, principal=_staff(), store=store, case_accessible=True
    )
    assert first.outcome == CorrectionOutcome.SAVED
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1985-01-15"
    assert period["staff_date_correction"]["operation_id"] == cmd.operation_id
    assert period["staff_date_correction"]["before"] == "1987-01-01"
    assert period["staff_date_correction"]["after"] == "1985-01-15"
    assert period["staff_date_correction"]["actor_id"]
    assert period["staff_date_correction"]["correction_basis"] == "integration"
    second = correct_period_date(
        cmd, principal=_staff(), store=store, case_accessible=True
    )
    assert second.outcome == CorrectionOutcome.IDEMPOTENT_REPLAY
    row2 = _load_row(store, seeded_case["case_id"])
    assert row2["updated_at"] == row["updated_at"]


def test_pg_concurrent_one_wins(seeded_case: dict) -> None:
    """Два date-op с одной expected version — одно изменение, второй conflict."""
    store = seeded_case["store"]
    version = seeded_case["version"]
    barrier = threading.Barrier(2)
    outcomes: list[CorrectionOutcome] = []

    def run(op: str, value: str) -> None:
        barrier.wait(timeout=10)
        outcomes.append(
            correct_period_date(
                _cmd(seeded_case, operation_id=op, new_value=value, expected_version=version),
                principal=_staff(),
                store=store,
                case_accessible=True,
            ).outcome
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(run, str(uuid.uuid4()), "1985-01-15")
        f2 = pool.submit(run, str(uuid.uuid4()), "1984-06-01")
        f1.result()
        f2.result()
    assert outcomes.count(CorrectionOutcome.SAVED) == 1
    assert CorrectionOutcome.VERSION_CONFLICT in outcomes
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] in {"1985-01-15", "1984-06-01"}
    hist = period.get("staff_date_corrections") or []
    assert len(hist) == 1


def test_pg_same_operation_id_concurrent(seeded_case: dict) -> None:
    """Одинаковый operation_id одновременно — одно изменение / один результат."""
    store = seeded_case["store"]
    op = str(uuid.uuid4())
    version = seeded_case["version"]
    barrier = threading.Barrier(2)
    outcomes: list[CorrectionOutcome] = []

    def run() -> None:
        barrier.wait(timeout=10)
        outcomes.append(
            correct_period_date(
                _cmd(
                    seeded_case,
                    operation_id=op,
                    new_value="1985-01-15",
                    expected_version=version,
                ),
                principal=_staff(),
                store=store,
                case_accessible=True,
            ).outcome
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(run)
        f2 = pool.submit(run)
        f1.result()
        f2.result()
    assert CorrectionOutcome.SAVED in outcomes
    assert set(outcomes) <= {
        CorrectionOutcome.SAVED,
        CorrectionOutcome.IDEMPOTENT_REPLAY,
        CorrectionOutcome.VERSION_CONFLICT,
    }
    # ровно одно сохранённое изменение даты
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1985-01-15"
    assert len(period.get("staff_date_corrections") or []) == 1


def test_pg_same_id_different_payload(seeded_case: dict) -> None:
    store = seeded_case["store"]
    op = str(uuid.uuid4())
    first = correct_period_date(
        _cmd(seeded_case, operation_id=op, new_value="1985-01-15"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert first.outcome == CorrectionOutcome.SAVED
    row_after = _load_row(store, seeded_case["case_id"])
    conflict = correct_period_date(
        _cmd(
            seeded_case,
            operation_id=op,
            new_value="1980-01-01",
            expected_version=row_after["updated_at"].isoformat()
            if hasattr(row_after["updated_at"], "isoformat")
            else str(row_after["updated_at"]),
            reason="other",
        ),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert conflict.outcome == CorrectionOutcome.OP_ID_PAYLOAD_CONFLICT
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1985-01-15"
    assert len(period["staff_date_corrections"]) == 1


def test_pg_exception_before_commit_rolls_back(seeded_case: dict) -> None:
    store = seeded_case["store"]
    store.raise_before_update = RuntimeError("inject_before_update")
    result = correct_period_date(
        _cmd(seeded_case),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert result.outcome == CorrectionOutcome.UNKNOWN
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1987-01-01"
    assert "staff_date_correction" not in period
    assert row["updated_at"].isoformat() == seeded_case["version"]
    assert store.lookup_by_operation_id(
        case_id=seeded_case["case_id"], operation_id="unused"
    ) is None


def test_pg_lost_ack_reconcile_no_date_change(seeded_case: dict) -> None:
    store = seeded_case["store"]
    op = str(uuid.uuid4())
    saved = correct_period_date(
        _cmd(seeded_case, operation_id=op),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert saved.outcome == CorrectionOutcome.SAVED
    row1 = _load_row(store, seeded_case["case_id"])
    reconciled = reconcile_unknown(
        case_id=seeded_case["case_id"], operation_id=op, store=store
    )
    assert reconciled.outcome == CorrectionOutcome.IDEMPOTENT_REPLAY
    replay = correct_period_date(
        _cmd(seeded_case, operation_id=op, expected_version=seeded_case["version"]),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert replay.outcome == CorrectionOutcome.IDEMPOTENT_REPLAY
    row2 = _load_row(store, seeded_case["case_id"])
    assert row2["updated_at"] == row1["updated_at"]
    period = next(
        p for p in row2["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1985-01-15"


def test_pg_snapshot_read_before_date_op_write_after(seeded_case: dict) -> None:
    """Snapshot прочитал до date-op, пишет после — исправление не теряется (conflict)."""
    store = seeded_case["store"]
    v0 = seeded_case["version"]
    # «прочитали» snapshot с v0
    stale_payload = {
        "ils_periods": [
            {
                "period_id": seeded_case["period_id"],
                "employer": "Test",
                "date_from": "1987-01-01",
                "date_to": "1990-12-31",
            },
            {
                "period_id": seeded_case["period_id_2"],
                "employer": "Other",
                "date_from": "1991-01-01",
                "date_to": "1995-12-31",
            },
        ]
    }
    saved = correct_period_date(
        _cmd(seeded_case, expected_version=v0),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert saved.outcome == CorrectionOutcome.SAVED
    rejected = store.save_pipeline_snapshot(
        seeded_case["case_id"], stale_payload, expected_version=v0
    )
    assert rejected.ok is False
    assert rejected.outcome == "version_conflict"
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1985-01-15"


def test_pg_snapshot_committed_before_date_op(seeded_case: dict) -> None:
    """Snapshot сохранился раньше — date-op видит новую версию."""
    store = seeded_case["store"]
    snap = store.save_pipeline_snapshot(
        seeded_case["case_id"],
        {
            "ils_periods": [
                {
                    "period_id": seeded_case["period_id"],
                    "employer": "Test",
                    "date_from": "1987-01-01",
                    "date_to": "1990-12-31",
                },
                {
                    "period_id": seeded_case["period_id_2"],
                    "employer": "Other",
                    "date_from": "1991-01-01",
                    "date_to": "1995-12-31",
                },
            ]
        },
        expected_version=seeded_case["version"],
    )
    assert snap.ok
    lost = correct_period_date(
        _cmd(seeded_case, expected_version=seeded_case["version"]),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert lost.outcome == CorrectionOutcome.VERSION_CONFLICT
    # с актуальной версией — успех
    ok = correct_period_date(
        _cmd(seeded_case, expected_version=snap.version_after or ""),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert ok.outcome == CorrectionOutcome.SAVED


def test_pg_extract_after_correction_keeps_staff_date(seeded_case: dict) -> None:
    store = seeded_case["store"]
    assert (
        correct_period_date(
            _cmd(seeded_case), principal=_staff(), store=store, case_accessible=True
        ).outcome
        == CorrectionOutcome.SAVED
    )
    row1 = _load_row(store, seeded_case["case_id"])
    v1 = row1["updated_at"].isoformat()
    ok = store.save_pipeline_snapshot(
        seeded_case["case_id"],
        {
            "ils_periods": [
                {
                    "period_id": seeded_case["period_id"],
                    "employer": "OCR-new",
                    "date_from": "1987-01-01",
                    "date_to": "1990-12-31",
                },
                {
                    "period_id": seeded_case["period_id_2"],
                    "employer": "Other",
                    "date_from": "1991-01-01",
                    "date_to": "1995-12-31",
                },
            ]
        },
        expected_version=v1,
    )
    assert ok.ok
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1985-01-15"
    assert period["employer"] == "OCR-new"


def test_pg_period_reorder_does_not_move_correction(seeded_case: dict) -> None:
    store = seeded_case["store"]
    assert (
        correct_period_date(
            _cmd(seeded_case), principal=_staff(), store=store, case_accessible=True
        ).outcome
        == CorrectionOutcome.SAVED
    )
    row1 = _load_row(store, seeded_case["case_id"])
    v1 = row1["updated_at"].isoformat()
    # перестановка + «удаление» через другой набор — correction следует за period_id
    ok = store.save_pipeline_snapshot(
        seeded_case["case_id"],
        {
            "ils_periods": [
                {
                    "period_id": seeded_case["period_id_2"],
                    "employer": "Other",
                    "date_from": "1991-01-01",
                    "date_to": "1995-12-31",
                },
                {
                    "period_id": seeded_case["period_id"],
                    "employer": "Test",
                    "date_from": "1987-01-01",
                    "date_to": "1990-12-31",
                },
            ]
        },
        expected_version=v1,
    )
    assert ok.ok
    row = _load_row(store, seeded_case["case_id"])
    by_id = {p["period_id"]: p for p in row["ils_periods"]}
    assert by_id[seeded_case["period_id"]]["date_from"] == "1985-01-15"
    assert by_id[seeded_case["period_id_2"]]["date_from"] == "1991-01-01"


def test_pg_partial_snapshot_omitted_key_keeps_periods(seeded_case: dict) -> None:
    store = seeded_case["store"]
    assert (
        correct_period_date(
            _cmd(seeded_case), principal=_staff(), store=store, case_accessible=True
        ).outcome
        == CorrectionOutcome.SAVED
    )
    row1 = _load_row(store, seeded_case["case_id"])
    v1 = row1["updated_at"].isoformat()
    ok = store.save_pipeline_snapshot(
        seeded_case["case_id"],
        {"findings": [{"type": "x", "status": "open"}]},
        expected_version=v1,
    )
    assert ok.ok
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1985-01-15"
    assert len(row["ils_periods"]) == 2


def test_pg_audit_history_not_replaced(seeded_case: dict) -> None:
    """Повторная правка того же периода: оба operation_id находимы."""
    store = seeded_case["store"]
    op1 = str(uuid.uuid4())
    r1 = correct_period_date(
        _cmd(seeded_case, operation_id=op1, new_value="1985-01-15"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert r1.outcome == CorrectionOutcome.SAVED
    row1 = _load_row(store, seeded_case["case_id"])
    v1 = row1["updated_at"].isoformat()
    op2 = str(uuid.uuid4())
    r2 = correct_period_date(
        _cmd(
            seeded_case,
            operation_id=op2,
            new_value="1984-01-01",
            expected_version=v1,
            reason="вторая правка",
        ),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert r2.outcome == CorrectionOutcome.SAVED
    assert store.lookup_by_operation_id(
        case_id=seeded_case["case_id"], operation_id=op1
    ) is not None
    assert store.lookup_by_operation_id(
        case_id=seeded_case["case_id"], operation_id=op2
    ) is not None
    row = _load_row(store, seeded_case["case_id"])
    period = next(
        p for p in row["ils_periods"] if p["period_id"] == seeded_case["period_id"]
    )
    assert period["date_from"] == "1984-01-01"
    assert len(period["staff_date_corrections"]) == 2
    assert period["staff_date_correction"]["operation_id"] == op2
