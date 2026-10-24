"""Unit-тесты точечной операции исправления даты (InMemory CAS).

Не заменяют интеграцию на реальной тестовой БД.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from sfrfr.db.period_date_store import InMemoryPeriodDateStore
from sfrfr.security.auth import Principal, StaffRole
from sfrfr.services.period_date_correction import (
    CorrectionOutcome,
    CorrectPeriodDateCommand,
    PeriodCollection,
    PeriodDateField,
    correct_period_date,
    merge_periods_preserve_corrections,
    reconcile_unknown,
)


def _staff(user_id: str = "11111111-1111-1111-1111-111111111111") -> Principal:
    return Principal(user_id=user_id, email="s@example.com", role=StaffRole.ADMIN)


def _client() -> Principal:
    return Principal(
        user_id="22222222-2222-2222-2222-222222222222",
        email="c@example.com",
        role=None,
    )


def _cmd(**kwargs: object) -> CorrectPeriodDateCommand:
    base = dict(
        operation_id="op-1",
        case_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        collection=PeriodCollection.ILS,
        period_id="period-1",
        field=PeriodDateField.DATE_FROM,
        new_value="1985-01-15",
        expected_version="1",
        reason="архивная справка",
        value_source="staff_verified",
    )
    base.update(kwargs)
    return CorrectPeriodDateCommand(**base)  # type: ignore[arg-type]


def _seed(store: InMemoryPeriodDateStore, **kwargs: object) -> None:
    store.seed(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        ils_periods=[
            {
                "period_id": "period-1",
                "employer": "ООО Ромашка",
                "date_from": "1987-01-01",
                "date_to": "1990-12-31",
            }
        ],
        findings=[{"type": "gap", "status": "open", "recalculated": True}],
        draft={"title": "x", "recalculated": True},
        version="1",
        **kwargs,  # type: ignore[arg-type]
    )


def test_success_saves_data_and_event() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    result = correct_period_date(
        _cmd(), principal=_staff(), store=store, case_accessible=True
    )
    assert result.outcome == CorrectionOutcome.SAVED
    assert result.confirmed
    assert result.event is not None
    assert result.event.before == "1987-01-01"
    assert result.event.after == "1985-01-15"
    assert result.event.dependents_status == "needs_recheck"
    assert result.dependents_status == "needs_recheck"
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] == "1985-01-15"
    assert st.ils_periods[0]["staff_date_correction"]["event_type"] == "period_date_corrected"
    assert st.version == "2"


def test_foreign_case_and_insufficient_rights() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    denied = correct_period_date(
        _cmd(), principal=_client(), store=store, case_accessible=True
    )
    assert denied.outcome == CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN
    missing = correct_period_date(
        _cmd(), principal=_staff(), store=store, case_accessible=False
    )
    assert missing.outcome == CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] == "1987-01-01"


def test_unknown_period_or_field() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    bad_period = correct_period_date(
        _cmd(period_id="nope"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert bad_period.outcome == CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN
    from sfrfr.services.period_date_correction import validate_command_shape

    class _Bad:
        operation_id = "op"
        case_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        collection = PeriodCollection.ILS
        period_id = "period-1"
        field = type("F", (), {"value": "employer"})()
        new_value = "1985-01-15"
        expected_version = "1"
        reason = "x"
        value_source = "staff_verified"

    assert validate_command_shape(_Bad()) == "unknown field"  # type: ignore[arg-type]


def test_invalid_date_and_interval() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    bad = correct_period_date(
        _cmd(new_value="32-13-99"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert bad.outcome == CorrectionOutcome.INVALID_DATA
    interval = correct_period_date(
        _cmd(new_value="1995-01-01"),  # after date_to 1990
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert interval.outcome == CorrectionOutcome.INVALID_DATA
    assert interval.detail == "date_from after date_to"


def test_stale_version() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    result = correct_period_date(
        _cmd(expected_version="9"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert result.outcome == CorrectionOutcome.VERSION_CONFLICT


def test_concurrent_same_version_only_one_wins() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    barrier = threading.Barrier(2)
    outcomes: list[CorrectionOutcome] = []

    def worker(op_id: str, value: str) -> None:
        barrier.wait()
        res = correct_period_date(
            _cmd(operation_id=op_id, new_value=value),
            principal=_staff(),
            store=store,
            case_accessible=True,
        )
        outcomes.append(res.outcome)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(worker, "op-a", "1985-01-15")
        f2 = pool.submit(worker, "op-b", "1984-06-01")
        f1.result()
        f2.result()

    assert outcomes.count(CorrectionOutcome.SAVED) == 1
    assert outcomes.count(CorrectionOutcome.VERSION_CONFLICT) == 1
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] in {"1985-01-15", "1984-06-01"}


def test_idempotent_replay() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    first = correct_period_date(
        _cmd(), principal=_staff(), store=store, case_accessible=True
    )
    second = correct_period_date(
        _cmd(expected_version="1"),  # старая версия, но тот же op
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert first.outcome == CorrectionOutcome.SAVED
    assert second.outcome == CorrectionOutcome.IDEMPOTENT_REPLAY
    assert second.event is not None
    assert second.event.after == first.event.after  # type: ignore[union-attr]
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.version == "2"


def test_same_operation_id_different_payload_conflicts() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    assert (
        correct_period_date(
            _cmd(), principal=_staff(), store=store, case_accessible=True
        ).outcome
        == CorrectionOutcome.SAVED
    )
    conflict = correct_period_date(
        _cmd(new_value="1980-01-01", expected_version="2"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert conflict.outcome == CorrectionOutcome.OP_ID_PAYLOAD_CONFLICT


def test_write_failure_no_partial_correction() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    store.fail_next_write = True
    result = correct_period_date(
        _cmd(), principal=_staff(), store=store, case_accessible=True
    )
    assert result.outcome == CorrectionOutcome.WRITE_REJECTED
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] == "1987-01-01"
    assert "staff_date_correction" not in st.ils_periods[0]
    assert store.lookup_by_operation_id(
        case_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", operation_id="op-1"
    ) is None


def test_unknown_then_reconcile() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    store.raise_on_apply = RuntimeError("boom")
    unknown = correct_period_date(
        _cmd(), principal=_staff(), store=store, case_accessible=True
    )
    assert unknown.outcome == CorrectionOutcome.UNKNOWN
    # факт не записан — сверка не находит
    empty = reconcile_unknown(
        case_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        operation_id="op-1",
        store=store,
    )
    assert empty.outcome == CorrectionOutcome.UNKNOWN
    # после успешной записи сверка возвращает replay
    saved = correct_period_date(
        _cmd(), principal=_staff(), store=store, case_accessible=True
    )
    assert saved.outcome == CorrectionOutcome.SAVED
    reconciled = reconcile_unknown(
        case_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        operation_id="op-1",
        store=store,
    )
    assert reconciled.outcome == CorrectionOutcome.IDEMPOTENT_REPLAY
    assert reconciled.detail == "reconciled"


def test_pipeline_snapshot_preserves_correction() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    assert (
        correct_period_date(
            _cmd(), principal=_staff(), store=store, case_accessible=True
        ).outcome
        == CorrectionOutcome.SAVED
    )
    store.apply_pipeline_snapshot(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        ils_periods=[
            {
                "period_id": "period-1",
                "employer": "ООО Ромашка",
                "date_from": "1987-01-01",  # OCR снова старое
                "date_to": "1990-12-31",
            }
        ],
    )
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] == "1985-01-15"
    assert st.ils_periods[0]["staff_date_correction"]["after"] == "1985-01-15"


def test_no_false_recalculated_on_dependents() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    result = correct_period_date(
        _cmd(), principal=_staff(), store=store, case_accessible=True
    )
    assert result.outcome == CorrectionOutcome.SAVED
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.findings[0]["dependents_status"] == "needs_recheck"
    assert "recalculated" not in st.findings[0]
    assert st.draft is not None
    assert st.draft["dependents_status"] == "needs_recheck"
    assert "recalculated" not in st.draft


def test_merge_helper_keeps_orphan_correction() -> None:
    existing = [
        {
            "period_id": "p1",
            "date_from": "1985-01-15",
            "staff_date_correction": {"after": "1985-01-15"},
        }
    ]
    incoming = [{"period_id": "p2", "date_from": "2000-01-01"}]
    merged = merge_periods_preserve_corrections(existing=existing, incoming=incoming)
    ids = {str(p.get("period_id")) for p in merged}
    assert ids == {"p1", "p2"}


def test_snapshot_A_stale_after_date_op_conflicts() -> None:
    """A: snapshot прочитал → date-op commit → snapshot со старой версией."""
    store = InMemoryPeriodDateStore()
    _seed(store)
    v0 = "1"
    assert (
        correct_period_date(
            _cmd(expected_version=v0),
            principal=_staff(),
            store=store,
            case_accessible=True,
        ).outcome
        == CorrectionOutcome.SAVED
    )
    rejected = store.apply_pipeline_snapshot(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        {
            "ils_periods": [
                {
                    "period_id": "period-1",
                    "date_from": "1987-01-01",
                    "date_to": "1990-12-31",
                }
            ]
        },
        expected_version=v0,
    )
    assert rejected.ok is False
    assert rejected.outcome == "version_conflict"
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] == "1985-01-15"


def test_snapshot_B_date_op_loses_to_newer_snapshot() -> None:
    """B: date-op на устаревшей версии после snapshot → conflict."""
    store = InMemoryPeriodDateStore()
    _seed(store)
    assert store.apply_pipeline_snapshot(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        {
            "ils_periods": [
                {
                    "period_id": "period-1",
                    "date_from": "1987-01-01",
                    "date_to": "1990-12-31",
                }
            ]
        },
        expected_version="1",
    ).ok
    lost = correct_period_date(
        _cmd(expected_version="1"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert lost.outcome == CorrectionOutcome.VERSION_CONFLICT


def test_snapshot_C_extract_preserves_correction() -> None:
    """C: date-op → новый extract snapshot без expected → merge preserve."""
    store = InMemoryPeriodDateStore()
    _seed(store)
    assert (
        correct_period_date(
            _cmd(), principal=_staff(), store=store, case_accessible=True
        ).outcome
        == CorrectionOutcome.SAVED
    )
    ok = store.apply_pipeline_snapshot(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        {
            "ils_periods": [
                {
                    "period_id": "period-1",
                    "employer": "OCR",
                    "date_from": "1987-01-01",
                    "date_to": "1990-12-31",
                }
            ],
            "findings": [{"type": "gap", "status": "open"}],
        },
    )
    assert ok.ok
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] == "1985-01-15"
    assert st.findings[0]["dependents_status"] == "needs_recheck"


def test_snapshot_D_two_periods_independent() -> None:
    store = InMemoryPeriodDateStore()
    store.seed(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        ils_periods=[
            {
                "period_id": "period-1",
                "date_from": "1987-01-01",
                "date_to": "1990-12-31",
            },
            {
                "period_id": "period-2",
                "date_from": "1991-01-01",
                "date_to": "1995-12-31",
            },
        ],
        version="1",
    )
    assert (
        correct_period_date(
            _cmd(period_id="period-1", new_value="1985-01-15"),
            principal=_staff(),
            store=store,
            case_accessible=True,
        ).outcome
        == CorrectionOutcome.SAVED
    )
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    by_id = {p["period_id"]: p for p in st.ils_periods}
    assert by_id["period-1"]["date_from"] == "1985-01-15"
    assert by_id["period-2"]["date_from"] == "1991-01-01"


def test_snapshot_E_missing_period_id_not_found() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    store.apply_pipeline_snapshot(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        {
            "ils_periods": [
                {
                    "period_id": "other",
                    "date_from": "2000-01-01",
                    "date_to": "2001-01-01",
                }
            ]
        },
        expected_version="1",
    )
    # period-1 удалён из массива; правка по старой ссылке
    missing = correct_period_date(
        _cmd(expected_version="2"),
        principal=_staff(),
        store=store,
        case_accessible=True,
    )
    assert missing.outcome == CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN


def test_snapshot_omitted_periods_key_does_not_clear() -> None:
    store = InMemoryPeriodDateStore()
    _seed(store)
    assert (
        correct_period_date(
            _cmd(), principal=_staff(), store=store, case_accessible=True
        ).outcome
        == CorrectionOutcome.SAVED
    )
    store.apply_pipeline_snapshot(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        {"findings": [{"type": "x"}]},  # без ils_periods
    )
    st = store.get_state("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert st is not None
    assert st.ils_periods[0]["date_from"] == "1985-01-15"
