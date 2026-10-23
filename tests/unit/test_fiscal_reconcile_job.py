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
