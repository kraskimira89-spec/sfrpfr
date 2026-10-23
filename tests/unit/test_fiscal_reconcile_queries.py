"""SFRFR-93: окно кандидатов, предфильтр fiscal_status, алерт 48ч + ALERT_SINCE."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sfrfr.services.fiscal_reconcile import (
    filter_reconcile_candidates,
    filter_stale_alert_candidates,
    fiscal_status_needs_reconcile,
    payment_in_reconcile_window,
    payment_needs_stale_alert,
)

NOW = datetime(2026, 10, 23, 16, 0, 0, tzinfo=UTC)
ALERT_SINCE = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)


def _row(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "pay-1",
        "status": "succeeded",
        "provider_payment_id": "326d8f33-000f-5001-9000-14edf85c8cb0",
        "fiscal_status": None,
        "paid_at": (NOW - timedelta(hours=3)).isoformat(),
        "created_at": (NOW - timedelta(hours=4)).isoformat(),
        "reconcile_alerted_at": None,
    }
    base.update(kwargs)
    return base


def test_fiscal_null_needs_reconcile() -> None:
    assert fiscal_status_needs_reconcile({"fiscal_status": None}) is True


def test_fiscal_registered_skipped() -> None:
    assert fiscal_status_needs_reconcile({"fiscal_status": "registered"}) is False


def test_window_includes_paid_inside() -> None:
    row = _row(paid_at=(NOW - timedelta(hours=5)).isoformat())
    assert payment_in_reconcile_window(row, now=NOW) is True


def test_window_excludes_younger_than_grace() -> None:
    row = _row(paid_at=(NOW - timedelta(seconds=30)).isoformat())
    assert payment_in_reconcile_window(row, now=NOW) is False


def test_window_excludes_older_than_48h() -> None:
    row = _row(paid_at=(NOW - timedelta(hours=50)).isoformat())
    assert payment_in_reconcile_window(row, now=NOW) is False


def test_window_falls_back_to_created_at() -> None:
    row = _row(paid_at=None, created_at=(NOW - timedelta(hours=6)).isoformat())
    assert payment_in_reconcile_window(row, now=NOW) is True


def test_filter_candidates_drops_registered_and_pending_status() -> None:
    rows = [
        _row(id="ok"),
        _row(id="reg", fiscal_status="registered"),
        _row(id="pend", status="pending"),
        _row(id="noprov", provider_payment_id=""),
    ]
    got = filter_reconcile_candidates(rows, now=NOW)
    assert [r["id"] for r in got] == ["ok"]


def test_stale_alert_needs_older_than_48h_and_cutover() -> None:
    old = _row(paid_at=(NOW - timedelta(hours=50)).isoformat())
    assert payment_needs_stale_alert(old, now=NOW, alert_since=ALERT_SINCE) is True


def test_stale_alert_respects_alert_since() -> None:
    old = _row(paid_at=(NOW - timedelta(hours=50)).isoformat())
    late_cutover = NOW - timedelta(hours=10)
    assert payment_needs_stale_alert(old, now=NOW, alert_since=late_cutover) is False


def test_stale_alert_skips_already_alerted() -> None:
    old = _row(
        paid_at=(NOW - timedelta(hours=50)).isoformat(),
        reconcile_alerted_at=NOW.isoformat(),
    )
    assert payment_needs_stale_alert(old, now=NOW, alert_since=ALERT_SINCE) is False


def test_filter_stale_alert_candidates() -> None:
    rows = [
        _row(id="stale", paid_at=(NOW - timedelta(hours=60)).isoformat()),
        _row(id="fresh", paid_at=(NOW - timedelta(hours=3)).isoformat()),
    ]
    got = filter_stale_alert_candidates(rows, now=NOW, alert_since=ALERT_SINCE)
    assert [r["id"] for r in got] == ["stale"]


class _ChainClient:
    """Минимальный PostgREST-chain для list_*_reconcile."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self._not = self

    def table(self, _name: str) -> _ChainClient:
        return self

    def select(self, *_a: object, **_k: object) -> _ChainClient:
        return self

    def eq(self, *_a: object, **_k: object) -> _ChainClient:
        return self

    @property
    def not_(self) -> _ChainClient:
        return self

    def is_(self, *_a: object, **_k: object) -> _ChainClient:
        return self

    def or_(self, *_a: object, **_k: object) -> _ChainClient:
        return self

    def order(self, *_a: object, **_k: object) -> _ChainClient:
        return self

    def limit(self, *_a: object, **_k: object) -> _ChainClient:
        return self

    def execute(self) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(data=list(self._rows))


def test_repo_list_succeeded_payments_for_reconcile_filters_null_fiscal() -> None:
    from sfrfr.db.case_repository import CaseRepository

    rows = [
        _row(id="ok"),
        _row(id="reg", fiscal_status="registered"),
        _row(id="old", paid_at=(NOW - timedelta(hours=60)).isoformat()),
    ]
    repo = CaseRepository.__new__(CaseRepository)
    repo.client = _ChainClient(rows)
    got = repo.list_succeeded_payments_for_reconcile(now=NOW)
    assert [r["id"] for r in got] == ["ok"]


def test_repo_list_stale_alert_requires_alert_since() -> None:
    from sfrfr.db.case_repository import CaseRepository

    rows = [_row(id="stale", paid_at=(NOW - timedelta(hours=60)).isoformat())]
    repo = CaseRepository.__new__(CaseRepository)
    repo.client = _ChainClient(rows)
    got = repo.list_payments_for_stale_fiscal_alert(alert_since=ALERT_SINCE, now=NOW)
    assert [r["id"] for r in got] == ["stale"]
