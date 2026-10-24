"""SFRFR-93: исходы create, dry-run, блокировка attempts, stable snapshot."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from sfrfr.services.fiscal_reconcile import (
    attempts_block_new_post,
    classify_create_receipt_result,
    reconcile_idempotence_key,
    should_alert_attempts,
    should_alert_streak,
    stable_receipt_snapshot,
)
from sfrfr.services.fiscal_reconcile_job import (
    process_payment_reconcile,
    run_fiscal_reconcile_tick,
)


def test_classify_transport_unknown() -> None:
    assert (
        classify_create_receipt_result({"ok": False, "phase": "transport"})
        == "unknown_after_post"
    )


def test_classify_pre_post() -> None:
    assert (
        classify_create_receipt_result({"ok": False, "phase": "pre_post", "error": "x"})
        == "error_before_post"
    )


def test_classify_http_500_unknown() -> None:
    assert (
        classify_create_receipt_result(
            {"ok": False, "phase": "http", "status_code": 502}
        )
        == "unknown_after_post"
    )


def test_classify_http_400_rejected() -> None:
    assert (
        classify_create_receipt_result(
            {"ok": False, "phase": "http", "status_code": 400}
        )
        == "rejected"
    )


def test_classify_429_unknown() -> None:
    assert (
        classify_create_receipt_result(
            {"ok": False, "phase": "http", "status_code": 429}
        )
        == "unknown_after_post"
    )


def test_classify_408_unknown() -> None:
    assert (
        classify_create_receipt_result(
            {"ok": False, "phase": "http", "status_code": 408}
        )
        == "unknown_after_post"
    )


def test_classify_ok_succeeded() -> None:
    assert (
        classify_create_receipt_result(
            {"ok": True, "phase": "http", "status": "succeeded"}
        )
        == "succeeded"
    )


def test_stable_snapshot_sort_keys() -> None:
    a = stable_receipt_snapshot({"b": 1, "a": {"z": 2, "y": "3.00"}})
    b = stable_receipt_snapshot({"a": {"y": "3.00", "z": 2}, "b": 1})
    assert a == b


def test_idempotence_key_shape() -> None:
    key = reconcile_idempotence_key("326d8f33-000f-5001-9000-14edf85c8cb0", 2)
    assert key.startswith("reconcile:")
    assert key.endswith(":2")
    assert len(key) <= 64


def test_attempts_block_and_alert_with_ttl() -> None:
    assert (
        attempts_block_new_post(
            attempts=3, outcome="rejected", ttl_alive=False
        )
        is True
    )
    assert (
        attempts_block_new_post(
            attempts=3, outcome="unknown_after_post", ttl_alive=True
        )
        is False
    )
    assert (
        should_alert_attempts(
            attempts=3, outcome="unknown_after_post", ttl_alive=True
        )
        is False
    )
    assert (
        should_alert_attempts(attempts=3, outcome="rejected", ttl_alive=False) is True
    )
    assert should_alert_streak(12) is True
    assert should_alert_streak(11) is False


def test_default_alert_send_false_without_chat(monkeypatch: Any) -> None:
    from sfrfr.services import fiscal_reconcile_job as job

    class _S:
        max_specialists_channel_chat_id = ""

    monkeypatch.setattr(
        "sfrfr.core.config.get_settings", lambda: _S()
    )
    assert (
        job._default_alert_send("attempts", {"id": "p1", "provider_payment_id": "yk"})
        is False
    )


def test_maybe_alert_logs_when_send_fails() -> None:
    repo = MagicMock()
    repo.claim_fiscal_reconcile_alert.return_value = {"id": "p1", "reconcile_alerted_at": "x"}
    repo.fiscal_reconcile_ttl_alive.return_value = False
    sent: list[bool] = []

    def _send(_r: str, _p: dict[str, Any]) -> bool:
        sent.append(True)
        return False

    from sfrfr.services.fiscal_reconcile_job import _maybe_alert

    _maybe_alert(
        repo,
        {
            "id": "p1",
            "reconcile_attempts": 3,
            "reconcile_last_outcome": "rejected",
            "reconcile_pre_error_streak": 0,
            "reconcile_alerted_at": None,
        },
        _send,
        reason="attempts",
    )
    assert sent == [True]
    repo.claim_fiscal_reconcile_alert.assert_called_once()


def test_dry_run_only_lease() -> None:
    repo = MagicMock()
    repo.try_fiscal_reconcile_lease.return_value = {
        "id": "p1",
        "provider_payment_id": "yk-1",
        "reconcile_attempts": 0,
        "reconcile_pre_error_streak": 0,
        "reconcile_last_outcome": None,
    }
    client = MagicMock()
    row = {
        "id": "p1",
        "provider_payment_id": "yk-1",
        "reconcile_attempts": 0,
        "reconcile_pre_error_streak": 0,
        "reconcile_last_outcome": None,
    }
    out = process_payment_reconcile(repo, row, client=client, dry_run=True)
    assert out["action"] == "dry_run"
    client.fetch_payment.assert_not_called()
    client.create_receipt.assert_not_called()
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    repo.update_payment_reconcile_fields.assert_not_called()


def test_lease_busy() -> None:
    repo = MagicMock()
    repo.try_fiscal_reconcile_lease.return_value = None
    out = process_payment_reconcile(
        repo,
        {"id": "p1", "provider_payment_id": "yk-1"},
        client=MagicMock(),
        dry_run=False,
    )
    assert out["action"] == "lease_busy"


def test_tick_requires_alert_since_when_enabled() -> None:
    repo = MagicMock()
    stats = run_fiscal_reconcile_tick(
        repo,
        enabled=True,
        dry_run=True,
        alert_since_raw=None,
    )
    assert "ALERT_SINCE" in str(stats.get("error") or "")
    repo.list_succeeded_payments_for_reconcile.assert_not_called()


def test_tick_rejects_garbage_alert_since() -> None:
    repo = MagicMock()
    stats = run_fiscal_reconcile_tick(
        repo,
        enabled=True,
        dry_run=True,
        alert_since_raw="abc",
    )
    assert "invalid ISO" in str(stats.get("error") or "")
    repo.list_succeeded_payments_for_reconcile.assert_not_called()


def test_tick_disabled() -> None:
    repo = MagicMock()
    stats = run_fiscal_reconcile_tick(
        repo, enabled=False, dry_run=True, alert_since_raw="2026-10-01T00:00:00Z"
    )
    assert stats.get("skipped")
    repo.list_succeeded_payments_for_reconcile.assert_not_called()


def test_process_skip_pending_no_create() -> None:
    repo = MagicMock()
    repo.try_fiscal_reconcile_lease.return_value = {
        "id": "p1",
        "provider_payment_id": "yk-1",
        "reconcile_attempts": 0,
        "reconcile_pre_error_streak": 2,
        "reconcile_last_outcome": None,
    }
    client = MagicMock()
    client.fetch_payment.return_value = {
        "ok": True,
        "payment": {
            "id": "yk-1",
            "status": "succeeded",
            "receipt_registration": "pending",
            "amount": {"value": "3.00"},
        },
    }
    out = process_payment_reconcile(
        repo,
        {
            "id": "p1",
            "provider_payment_id": "yk-1",
            "reconcile_attempts": 0,
            "reconcile_pre_error_streak": 2,
        },
        client=client,
        dry_run=False,
    )
    assert out["action"] == "skip_pending"
    client.create_receipt.assert_not_called()
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert fields["reconcile_last_outcome"] == "skip_pending"
    assert fields["reconcile_pre_error_streak"] == 0


def test_process_gate_before_create() -> None:
    repo = MagicMock()
    repo.try_fiscal_reconcile_lease.return_value = {
        "id": "p1",
        "provider_payment_id": "yk-1",
        "reconcile_attempts": 0,
        "reconcile_pre_error_streak": 0,
        "reconcile_last_outcome": None,
    }
    client = MagicMock()
    client.fetch_payment.return_value = {
        "ok": True,
        "payment": {
            "id": "yk-1",
            "status": "succeeded",
            "receipt_registration": "canceled",
            "amount": {"value": "3.00"},
            "description": "t",
        },
    }
    client.list_receipts.return_value = {
        "ok": True,
        "items": [
            {
                "id": "r1",
                "type": "payment",
                "status": "succeeded",
                "payment_id": "yk-1",
            }
        ],
    }
    out = process_payment_reconcile(
        repo,
        {"id": "p1", "provider_payment_id": "yk-1", "reconcile_attempts": 0},
        client=client,
        dry_run=False,
    )
    assert out["action"] == "gate_succeeded"
    client.create_receipt.assert_not_called()
    repo.mark_fiscal_reconcile_post_started.assert_not_called()


def test_process_posts_after_mark(monkeypatch: Any) -> None:
    repo = MagicMock()
    repo.try_fiscal_reconcile_lease.return_value = {
        "id": "p1",
        "provider_payment_id": "yk-1",
        "reconcile_attempts": 0,
        "reconcile_pre_error_streak": 0,
        "reconcile_last_outcome": None,
        "reconcile_post_at": None,
    }
    repo.fiscal_reconcile_ttl_alive.return_value = False
    repo.mark_fiscal_reconcile_post_started.return_value = {
        "id": "p1",
        "reconcile_attempts": 1,
        "reconcile_last_outcome": "post_started",
    }
    client = MagicMock()
    client.fetch_payment.return_value = {
        "ok": True,
        "payment": {
            "id": "yk-1",
            "status": "succeeded",
            "receipt_registration": "canceled",
            "amount": {"value": "3.00"},
            "description": "t",
        },
    }
    client.list_receipts.return_value = {"ok": True, "items": []}
    client._receipt.return_value = {
        "customer": {"email": "a@b.c"},
        "items": [
            {
                "description": "t",
                "quantity": "1",
                "amount": {"value": "3.00", "currency": "RUB"},
                "vat_code": 1,
            }
        ],
    }
    client.create_receipt.return_value = {
        "ok": True,
        "phase": "http",
        "status": "pending",
        "status_code": 200,
    }
    monkeypatch.setattr(
        "sfrfr.services.fiscal_reconcile_job._resolve_contacts",
        lambda *_a, **_k: ("a@b.c", None),
    )
    out = process_payment_reconcile(
        repo,
        {"id": "p1", "provider_payment_id": "yk-1", "reconcile_attempts": 0},
        client=client,
        dry_run=False,
    )
    assert out["action"] == "pending"
    repo.mark_fiscal_reconcile_post_started.assert_called_once()
    assert client.create_receipt.call_args.kwargs["idempotence_key"].endswith(":1")
    assert client.create_receipt.call_args.kwargs["body_snapshot"] is not None


def test_tick_ocr_row_never_reaches_lease_fetch_create_or_alert() -> None:
    """Реальный list_* (CaseRepository) → OCR отфильтрован до process/lease/fetch."""
    from datetime import UTC, datetime, timedelta

    from sfrfr.db.case_repository import CaseRepository

    now = datetime.now(UTC)
    yk_id = "326d8f33-000f-5001-9000-14edf85c8cb0"
    paid_ok = (now - timedelta(hours=3)).isoformat()
    paid_stale = (now - timedelta(hours=60)).isoformat()

    class _Chain:
        def __init__(self, rows: list[dict[str, Any]]) -> None:
            self._rows = rows
            self._not = self

        def table(self, _n: str) -> _Chain:
            return self

        def select(self, *_a: object, **_k: object) -> _Chain:
            return self

        def eq(self, *_a: object, **_k: object) -> _Chain:
            return self

        @property
        def not_(self) -> _Chain:
            return self

        def is_(self, *_a: object, **_k: object) -> _Chain:
            return self

        def or_(self, *_a: object, **_k: object) -> _Chain:
            return self

        def order(self, *_a: object, **_k: object) -> _Chain:
            return self

        def limit(self, *_a: object, **_k: object) -> _Chain:
            return self

        def execute(self) -> Any:
            from types import SimpleNamespace

            return SimpleNamespace(data=list(self._rows))

    reconcile_rows = [
        {
            "id": "yk-pay",
            "status": "succeeded",
            "provider": "yookassa",
            "provider_payment_id": yk_id,
            "fiscal_status": None,
            "paid_at": paid_ok,
            "created_at": paid_ok,
            "reconcile_alerted_at": None,
            "reconcile_attempts": 0,
            "reconcile_pre_error_streak": 0,
            "reconcile_last_outcome": None,
        },
        {
            "id": "ocr-pay",
            "status": "succeeded",
            "provider": "receipt_ocr",
            "provider_payment_id": "receipt:synthetic-doc",
            "fiscal_status": None,
            "paid_at": paid_ok,
            "created_at": paid_ok,
            "reconcile_alerted_at": None,
            "reconcile_attempts": 0,
            "reconcile_pre_error_streak": 2,
            "reconcile_last_outcome": "error_before_post",
        },
    ]
    stale_rows = [
        {**reconcile_rows[0], "id": "yk-stale", "paid_at": paid_stale},
        {**reconcile_rows[1], "id": "ocr-stale", "paid_at": paid_stale},
    ]

    class _HybridRepo:
        def __init__(self) -> None:
            self._case = CaseRepository.__new__(CaseRepository)
            self.leases: list[str] = []
            self.field_updates: list[tuple[str, dict[str, Any]]] = []
            self.claims: list[str] = []
            self._phase = "reconcile"

        def list_succeeded_payments_for_reconcile(self, **kw: Any) -> list[dict[str, Any]]:
            self._case.client = _Chain(reconcile_rows)
            return self._case.list_succeeded_payments_for_reconcile(**kw)

        def list_payments_for_stale_fiscal_alert(self, **kw: Any) -> list[dict[str, Any]]:
            self._case.client = _Chain(stale_rows)
            return self._case.list_payments_for_stale_fiscal_alert(**kw)

        def try_fiscal_reconcile_lease(
            self, payment_id: str, **_kw: Any
        ) -> dict[str, Any] | None:
            self.leases.append(payment_id)
            return {
                "id": payment_id,
                "provider_payment_id": yk_id,
                "reconcile_attempts": 0,
                "reconcile_pre_error_streak": 0,
                "reconcile_last_outcome": None,
            }

        def update_payment_reconcile_fields(
            self, payment_id: str, fields: dict[str, Any]
        ) -> None:
            self.field_updates.append((payment_id, dict(fields)))

        def claim_fiscal_reconcile_alert(self, payment_id: str, **_k: Any) -> Any:
            self.claims.append(payment_id)
            return None

        def fiscal_reconcile_ttl_alive(self, *_a: Any, **_k: Any) -> bool:
            return False

        def mark_fiscal_reconcile_post_started(self, *_a: Any, **_k: Any) -> Any:
            raise AssertionError("OCR/tick must not mark post started in this fixture")

    repo = _HybridRepo()
    client = MagicMock()
    client.fetch_payment.return_value = {
        "ok": True,
        "payment": {
            "id": yk_id,
            "status": "succeeded",
            "receipt_registration": "pending",
            "amount": {"value": "3.00"},
        },
    }
    alerts: list[Any] = []

    def _alert(*_a: Any, **_k: Any) -> bool:
        alerts.append(True)
        return False

    stats = run_fiscal_reconcile_tick(
        repo,  # type: ignore[arg-type]
        enabled=True,
        dry_run=False,
        alert_since_raw="2026-10-01T00:00:00Z",
        client=client,
        alert_send=_alert,
    )
    assert stats["candidates"] == 1
    assert [r["payment_id"] for r in stats["results"]] == ["yk-pay"]
    assert repo.leases == ["yk-pay"]
    assert "ocr-pay" not in repo.leases
    client.fetch_payment.assert_called_once_with(yk_id)
    client.list_receipts.assert_not_called()
    client.create_receipt.assert_not_called()
    assert all(pid != "ocr-pay" for pid, _ in repo.field_updates)
    assert "ocr-stale" not in repo.claims
    assert "ocr-pay" not in repo.claims
    # stale: только yookassa (OCR отфильтрован); claim может не сработать — главное нет OCR
    assert stats.get("stale_alerts", 0) == 1
