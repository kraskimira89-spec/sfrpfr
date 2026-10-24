"""SFRFR-97: канон дизайна тестов 1–28 (пробелы после #247)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sfrfr.services.fiscal_reconcile import reconcile_idempotence_key
from sfrfr.services.fiscal_reconcile_job import (
    _maybe_alert,
    process_payment_reconcile,
    run_fiscal_reconcile_tick,
)


def _lease(
    *,
    attempts: int = 0,
    streak: int = 0,
    outcome: str | None = None,
    post_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": "p1",
        "provider_payment_id": "yk-1",
        "reconcile_attempts": attempts,
        "reconcile_pre_error_streak": streak,
        "reconcile_last_outcome": outcome,
        "reconcile_post_at": post_at,
        "reconcile_alerted_at": None,
    }


def _repo_leased(**kwargs: Any) -> MagicMock:
    repo = MagicMock()
    leased = _lease(**kwargs)
    repo.try_fiscal_reconcile_lease.return_value = leased
    repo.fiscal_reconcile_ttl_alive.return_value = False
    return repo


def _client_reg(
    reg: str,
    *,
    list_ok: bool = True,
    items: list[dict[str, Any]] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.fetch_payment.return_value = {
        "ok": True,
        "payment": {
            "id": "yk-1",
            "status": "succeeded",
            "receipt_registration": reg,
            "amount": {"value": "3.00"},
            "description": "t",
        },
    }
    if list_ok:
        client.list_receipts.return_value = {"ok": True, "items": items or []}
    else:
        client.list_receipts.return_value = {"ok": False, "error": "timeout"}
    return client


def _receipt_body() -> dict[str, Any]:
    return {
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


def test_01_canceled_empty_list_creates(monkeypatch: Any) -> None:
    repo = _repo_leased()
    repo.mark_fiscal_reconcile_post_started.return_value = {
        "id": "p1",
        "reconcile_attempts": 1,
        "reconcile_last_outcome": "post_started",
    }
    client = _client_reg("canceled", items=[])
    client._receipt.return_value = _receipt_body()
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
        repo, _lease(), client=client, dry_run=False
    )
    assert out["action"] == "pending"
    client.create_receipt.assert_called_once()
    assert client.create_receipt.call_args.kwargs["idempotence_key"].endswith(":1")


def test_02_canceled_with_succeeded_receipt_skips() -> None:
    repo = _repo_leased()
    client = _client_reg(
        "canceled",
        items=[
            {
                "id": "r1",
                "type": "payment",
                "status": "succeeded",
                "payment_id": "yk-1",
            }
        ],
    )
    out = process_payment_reconcile(
        repo, _lease(), client=client, dry_run=False
    )
    assert out["action"] == "gate_succeeded"
    client.create_receipt.assert_not_called()
    repo.mark_fiscal_reconcile_post_started.assert_not_called()


def test_03_pending_skip_no_attempt_growth() -> None:
    repo = _repo_leased(streak=4)
    client = _client_reg("pending")
    out = process_payment_reconcile(
        repo, _lease(streak=4), client=client, dry_run=False
    )
    assert out["action"] == "skip_pending"
    client.create_receipt.assert_not_called()
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert fields["reconcile_last_outcome"] == "skip_pending"
    assert fields["reconcile_pre_error_streak"] == 0


def test_04_empty_reg_skip_no_create() -> None:
    repo = _repo_leased()
    client = _client_reg("")
    out = process_payment_reconcile(
        repo, _lease(), client=client, dry_run=False
    )
    assert out["action"] == "skip_reg"
    client.create_receipt.assert_not_called()
    client.list_receipts.assert_not_called()


def test_05_second_tick_lease_busy() -> None:
    repo = MagicMock()
    repo.try_fiscal_reconcile_lease.return_value = None
    out = process_payment_reconcile(
        repo,
        {"id": "p1", "provider_payment_id": "yk-1"},
        client=MagicMock(),
        dry_run=False,
    )
    assert out["action"] == "lease_busy"


def test_07_list_fail_no_attempt_bump_streak() -> None:
    repo = _repo_leased(streak=2)
    client = _client_reg("canceled", list_ok=False)
    out = process_payment_reconcile(
        repo, _lease(streak=2), client=client, dry_run=False
    )
    assert out["action"] == "gate_list_failed"
    client.create_receipt.assert_not_called()
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert fields["reconcile_pre_error_streak"] == 3
    assert fields.get("reconcile_last_outcome") == "error_before_post"


def test_09_transport_unknown_same_key_retry(monkeypatch: Any) -> None:
    repo = _repo_leased(
        attempts=1, outcome="unknown_after_post", post_at="2026-10-23T12:00:00Z"
    )
    repo.fiscal_reconcile_ttl_alive.return_value = True
    snap = {
        "type": "payment",
        "payment_id": "yk-1",
        "send": True,
        "customer": {"email": "a@b.c"},
        "items": [
            {
                "description": "t",
                "quantity": "1",
                "amount": {"value": "3.00", "currency": "RUB"},
                "vat_code": 1,
            }
        ],
        "internet": True,
        "settlements": [
            {"type": "cashless", "amount": {"value": "3.00", "currency": "RUB"}}
        ],
    }
    repo.get_payment_reconcile_payload.return_value = {
        "reconcile_post_payload": snap
    }
    client = _client_reg("canceled", items=[])
    client.create_receipt.return_value = {
        "ok": False,
        "phase": "transport",
        "error": "timeout",
    }
    monkeypatch.setattr(
        "sfrfr.services.fiscal_reconcile_job._resolve_contacts",
        lambda *_a, **_k: ("a@b.c", None),
    )
    out = process_payment_reconcile(
        repo,
        _lease(attempts=1, outcome="unknown_after_post", post_at="t"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "unknown_after_post"
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    key = client.create_receipt.call_args.kwargs["idempotence_key"]
    assert key == reconcile_idempotence_key("yk-1", 1)
    assert client.create_receipt.call_args.kwargs["body_snapshot"] == snap


def test_10_after_canceled_increments_new_key(monkeypatch: Any) -> None:
    repo = _repo_leased(attempts=1, outcome="canceled", post_at="old")
    repo.fiscal_reconcile_ttl_alive.return_value = False
    repo.mark_fiscal_reconcile_post_started.return_value = {
        "id": "p1",
        "reconcile_attempts": 2,
        "reconcile_last_outcome": "post_started",
    }
    client = _client_reg("canceled", items=[])
    client._receipt.return_value = _receipt_body()
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
        _lease(attempts=1, outcome="canceled"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "pending"
    assert repo.mark_fiscal_reconcile_post_started.call_args.kwargs["attempts"] == 2
    assert client.create_receipt.call_args.kwargs["idempotence_key"].endswith(":2")


def test_08_attempts_exhausted_no_create_alerts() -> None:
    repo = _repo_leased(attempts=3, outcome="rejected")
    repo.fiscal_reconcile_ttl_alive.return_value = False
    client = _client_reg("canceled", items=[])
    alerts: list[str] = []

    def _send(reason: str, _p: dict[str, Any]) -> bool:
        alerts.append(reason)
        return True

    repo.claim_fiscal_reconcile_alert.return_value = {"id": "p1"}
    out = process_payment_reconcile(
        repo,
        _lease(attempts=3, outcome="rejected"),
        client=client,
        dry_run=False,
        alert_send=_send,
    )
    assert out["action"] == "attempts_exhausted"
    client.create_receipt.assert_not_called()
    assert alerts == ["attempts"]


def test_08_unknown_ttl_alive_same_key_retry(monkeypatch: Any) -> None:
    repo = _repo_leased(
        attempts=3, outcome="unknown_after_post", post_at="2026-10-23T12:00:00Z"
    )
    repo.fiscal_reconcile_ttl_alive.return_value = True
    repo.get_payment_reconcile_payload.return_value = {
        "reconcile_post_payload": {
            "type": "payment",
            "payment_id": "yk-1",
            "send": True,
            "customer": {"email": "a@b.c"},
            "items": [
                {
                    "description": "t",
                    "quantity": "1",
                    "amount": {"value": "3.00", "currency": "RUB"},
                    "vat_code": 1,
                }
            ],
            "internet": True,
            "settlements": [
                {
                    "type": "cashless",
                    "amount": {"value": "3.00", "currency": "RUB"},
                }
            ],
        }
    }
    client = _client_reg("canceled", items=[])
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
        _lease(attempts=3, outcome="unknown_after_post", post_at="x"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "pending"
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    key = client.create_receipt.call_args.kwargs["idempotence_key"]
    assert key == reconcile_idempotence_key("yk-1", 3)


def test_11_claim_second_time_skips_send() -> None:
    repo = MagicMock()
    repo.fiscal_reconcile_ttl_alive.return_value = False
    repo.claim_fiscal_reconcile_alert.side_effect = [
        {"id": "p1", "reconcile_alerted_at": "t1"},
        None,
    ]
    sent: list[str] = []

    def _send(reason: str, _p: dict[str, Any]) -> bool:
        sent.append(reason)
        return True

    pay = {
        "id": "p1",
        "reconcile_attempts": 3,
        "reconcile_last_outcome": "rejected",
        "reconcile_pre_error_streak": 0,
        "reconcile_alerted_at": None,
    }
    _maybe_alert(repo, pay, _send, reason="attempts")
    pay["reconcile_alerted_at"] = "t1"
    _maybe_alert(repo, pay, _send, reason="attempts")
    assert sent == ["attempts"]
    assert repo.claim_fiscal_reconcile_alert.call_count == 1


def test_12_unknown_then_gate_succeeded_clears_payload() -> None:
    repo = _repo_leased(attempts=1, outcome="unknown_after_post", post_at="t")
    client = _client_reg(
        "canceled",
        items=[
            {
                "id": "r1",
                "type": "payment",
                "status": "succeeded",
                "payment_id": "yk-1",
            }
        ],
    )
    out = process_payment_reconcile(
        repo,
        _lease(attempts=1, outcome="unknown_after_post", post_at="t"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "gate_succeeded"
    client.create_receipt.assert_not_called()
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert fields["reconcile_post_payload"] is None
    assert fields["fiscal_status"] == "registered"


def test_13_ttl_expired_increments_attempt(monkeypatch: Any) -> None:
    repo = _repo_leased(attempts=1, outcome="canceled", post_at="old")
    repo.fiscal_reconcile_ttl_alive.return_value = False
    repo.mark_fiscal_reconcile_post_started.return_value = {
        "id": "p1",
        "reconcile_attempts": 2,
        "reconcile_last_outcome": "post_started",
    }
    client = _client_reg("canceled", items=[])
    client.create_receipt.return_value = {
        "ok": False,
        "phase": "http",
        "status_code": 400,
        "error": "bad",
    }
    monkeypatch.setattr(
        "sfrfr.services.fiscal_reconcile_job._resolve_contacts",
        lambda *_a, **_k: ("a@b.c", None),
    )
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
    out = process_payment_reconcile(
        repo,
        _lease(attempts=1, outcome="canceled"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "rejected"
    assert repo.mark_fiscal_reconcile_post_started.call_args.kwargs["attempts"] == 2
    key = client.create_receipt.call_args.kwargs["idempotence_key"]
    assert key.endswith(":2")


def test_14_post_started_ttl_alive_no_plus_one(monkeypatch: Any) -> None:
    """Kill после post_started: тот же ключ, без mark +1."""
    repo = _repo_leased(
        attempts=1, outcome="post_started", post_at="2026-10-23T12:00:00Z"
    )
    repo.fiscal_reconcile_ttl_alive.return_value = True
    repo.get_payment_reconcile_payload.return_value = {
        "reconcile_post_payload": {
            "type": "payment",
            "payment_id": "yk-1",
            "send": True,
            "customer": {"email": "a@b.c"},
            "items": [
                {
                    "description": "t",
                    "quantity": "1",
                    "amount": {"value": "3.00", "currency": "RUB"},
                    "vat_code": 1,
                }
            ],
            "internet": True,
            "settlements": [
                {
                    "type": "cashless",
                    "amount": {"value": "3.00", "currency": "RUB"},
                }
            ],
        }
    }
    client = _client_reg("canceled", items=[])
    client.create_receipt.return_value = {
        "ok": True,
        "phase": "http",
        "status": "succeeded",
        "status_code": 200,
    }
    monkeypatch.setattr(
        "sfrfr.services.fiscal_reconcile_job._resolve_contacts",
        lambda *_a, **_k: ("a@b.c", None),
    )
    out = process_payment_reconcile(
        repo,
        _lease(attempts=1, outcome="post_started", post_at="x"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "succeeded"
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    assert client.create_receipt.call_args.kwargs["idempotence_key"].endswith(":1")


def test_15_lease_sql_only_sets_last_reconcile_at() -> None:
    from pathlib import Path

    sql = Path(
        "supabase/migrations/20261023180000_payments_fiscal_reconcile_attempts.sql"
    ).read_text(encoding="utf-8")
    start = sql.index("CREATE OR REPLACE FUNCTION public.try_fiscal_reconcile_lease")
    end = sql.index("CREATE OR REPLACE FUNCTION public.fiscal_reconcile_ttl_alive")
    lease_body = sql[start:end]
    assert "SET last_reconcile_at = now()" in lease_body
    assert "reconcile_post_at" not in lease_body


def test_16_reset_clears_alert_attempts_payload() -> None:
    from sfrfr.db.case_repository import CaseRepository

    repo = CaseRepository.__new__(CaseRepository)
    chain = MagicMock()
    repo.client = chain
    table = MagicMock()
    chain.table.return_value = table
    table.update.return_value = table
    table.eq.return_value = table
    repo.reset_fiscal_reconcile_alert("p1")
    payload = table.update.call_args[0][0]
    assert payload["reconcile_alerted_at"] is None
    assert payload["reconcile_attempts"] == 0
    assert payload["reconcile_pre_error_streak"] == 0
    assert payload["reconcile_post_payload"] is None


def test_17_gate_fail_ttl_alive_no_create() -> None:
    repo = _repo_leased(
        attempts=2, outcome="unknown_after_post", post_at="2026-10-23T12:00:00Z"
    )
    repo.fiscal_reconcile_ttl_alive.return_value = True
    client = _client_reg("canceled", list_ok=False)
    out = process_payment_reconcile(
        repo,
        _lease(attempts=2, outcome="unknown_after_post", post_at="t"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "gate_list_failed"
    client.create_receipt.assert_not_called()
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert "reconcile_last_outcome" not in fields
    assert fields["reconcile_pre_error_streak"] == 1


def test_18_missing_post_at_forces_ttl_expired(monkeypatch: Any, caplog: Any) -> None:
    import logging

    repo = _repo_leased(attempts=1, outcome="unknown_after_post", post_at=None)
    repo.fiscal_reconcile_ttl_alive.return_value = True  # игнор → False
    repo.mark_fiscal_reconcile_post_started.return_value = {
        "id": "p1",
        "reconcile_attempts": 2,
        "reconcile_last_outcome": "post_started",
    }
    client = _client_reg("canceled", items=[])
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
    with caplog.at_level(logging.WARNING):
        out = process_payment_reconcile(
            repo,
            _lease(attempts=1, outcome="unknown_after_post", post_at=None),
            client=client,
            dry_run=False,
        )
    assert out["action"] == "pending"
    assert any("post_at_missing" in r.message for r in caplog.records)
    assert repo.mark_fiscal_reconcile_post_started.call_args.kwargs["attempts"] == 2


def test_19_key_too_long_skips_create(monkeypatch: Any) -> None:
    long_yk = "yk-" + ("x" * 60)
    repo = MagicMock()
    leased = {
        "id": "p1",
        "provider_payment_id": long_yk,
        "reconcile_attempts": 0,
        "reconcile_pre_error_streak": 0,
        "reconcile_last_outcome": None,
        "reconcile_post_at": None,
    }
    repo.try_fiscal_reconcile_lease.return_value = leased
    repo.fiscal_reconcile_ttl_alive.return_value = False
    client = MagicMock()
    client.fetch_payment.return_value = {
        "ok": True,
        "payment": {
            "id": long_yk,
            "status": "succeeded",
            "receipt_registration": "canceled",
            "amount": {"value": "3.00"},
            "description": "t",
        },
    }
    client.list_receipts.return_value = {"ok": True, "items": []}
    client._receipt.return_value = _receipt_body()
    monkeypatch.setattr(
        "sfrfr.services.fiscal_reconcile_job._resolve_contacts",
        lambda *_a, **_k: ("a@b.c", None),
    )
    out = process_payment_reconcile(
        repo, leased, client=client, dry_run=False
    )
    assert out["action"] == "key_too_long"
    client.create_receipt.assert_not_called()
    repo.mark_fiscal_reconcile_post_started.assert_not_called()


def test_20_gate_fail_ttl_expired_no_create() -> None:
    repo = _repo_leased(attempts=1, outcome="canceled", post_at="old")
    repo.fiscal_reconcile_ttl_alive.return_value = False
    client = _client_reg("canceled", list_ok=False)
    out = process_payment_reconcile(
        repo,
        _lease(attempts=1, outcome="canceled", post_at="old"),
        client=client,
        dry_run=False,
    )
    assert out["action"] == "gate_list_failed"
    client.create_receipt.assert_not_called()
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert fields["reconcile_last_outcome"] == "error_before_post"


def test_21_http_400_rejected_then_new_key(monkeypatch: Any) -> None:
    repo = _repo_leased(attempts=0)
    repo.mark_fiscal_reconcile_post_started.side_effect = [
        {
            "id": "p1",
            "reconcile_attempts": 1,
            "reconcile_last_outcome": "post_started",
        },
        {
            "id": "p1",
            "reconcile_attempts": 2,
            "reconcile_last_outcome": "post_started",
        },
    ]
    client = _client_reg("canceled", items=[])
    client._receipt.return_value = _receipt_body()
    client.create_receipt.side_effect = [
        {"ok": False, "phase": "http", "status_code": 400, "error": "bad"},
        {
            "ok": True,
            "phase": "http",
            "status": "pending",
            "status_code": 200,
        },
    ]
    monkeypatch.setattr(
        "sfrfr.services.fiscal_reconcile_job._resolve_contacts",
        lambda *_a, **_k: ("a@b.c", None),
    )
    out1 = process_payment_reconcile(
        repo, _lease(), client=client, dry_run=False
    )
    assert out1["action"] == "rejected"
    key1 = client.create_receipt.call_args_list[0].kwargs["idempotence_key"]
    assert key1.endswith(":1")

    repo.try_fiscal_reconcile_lease.return_value = _lease(
        attempts=1, outcome="rejected", post_at="t"
    )
    repo.fiscal_reconcile_ttl_alive.return_value = False
    out2 = process_payment_reconcile(
        repo,
        _lease(attempts=1, outcome="rejected", post_at="t"),
        client=client,
        dry_run=False,
    )
    assert out2["action"] == "pending"
    key2 = client.create_receipt.call_args_list[1].kwargs["idempotence_key"]
    assert key2.endswith(":2")
    assert key1 != key2


def test_23_succeeded_clears_payload(monkeypatch: Any) -> None:
    repo = _repo_leased()
    repo.mark_fiscal_reconcile_post_started.return_value = {
        "id": "p1",
        "reconcile_attempts": 1,
        "reconcile_last_outcome": "post_started",
    }
    client = _client_reg("canceled", items=[])
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
        "status": "succeeded",
        "status_code": 200,
    }
    monkeypatch.setattr(
        "sfrfr.services.fiscal_reconcile_job._resolve_contacts",
        lambda *_a, **_k: ("a@b.c", None),
    )
    out = process_payment_reconcile(
        repo, _lease(), client=client, dry_run=False
    )
    assert out["action"] == "succeeded"
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert fields["reconcile_post_payload"] is None
    assert fields["fiscal_status"] == "registered"


def test_27_three_fetch_fails_attempts_stay_zero() -> None:
    repo = _repo_leased(streak=0)
    client = MagicMock()
    client.fetch_payment.return_value = {"ok": False, "error": "404"}
    row = _lease()
    for expected_streak in (1, 2, 3):
        repo.try_fiscal_reconcile_lease.return_value = {
            **row,
            "reconcile_pre_error_streak": expected_streak - 1,
        }
        out = process_payment_reconcile(
            repo,
            {**row, "reconcile_pre_error_streak": expected_streak - 1},
            client=client,
            dry_run=False,
        )
        assert out["action"] == "error_before_post"
        fields = repo.update_payment_reconcile_fields.call_args[0][1]
        assert fields["reconcile_pre_error_streak"] == expected_streak
    repo.mark_fiscal_reconcile_post_started.assert_not_called()
    client.create_receipt.assert_not_called()


def test_28_streak_12_alerts_attempts_still_zero() -> None:
    repo = _repo_leased(streak=11)
    client = MagicMock()
    client.fetch_payment.return_value = {"ok": False, "error": "404"}
    alerts: list[str] = []

    def _send(reason: str, _p: dict[str, Any]) -> bool:
        alerts.append(reason)
        return True

    repo.claim_fiscal_reconcile_alert.return_value = {"id": "p1"}
    out = process_payment_reconcile(
        repo,
        _lease(streak=11),
        client=client,
        dry_run=False,
        alert_send=_send,
    )
    assert out["action"] == "error_before_post"
    fields = repo.update_payment_reconcile_fields.call_args[0][1]
    assert fields["reconcile_pre_error_streak"] == 12
    assert alerts == ["pre_error_streak"]


def test_alert_since_invalid_exits_without_list() -> None:
    repo = MagicMock()
    stats = run_fiscal_reconcile_tick(
        repo, enabled=True, dry_run=True, alert_since_raw="not-a-date"
    )
    assert stats.get("error")
    repo.list_succeeded_payments_for_reconcile.assert_not_called()


def test_settings_enabled_one(monkeypatch: pytest.MonkeyPatch) -> None:
    from sfrfr.core.config import Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("FISCAL_RECONCILE_ENABLED", "1")
    monkeypatch.setenv("FISCAL_RECONCILE_DRY_RUN", "1")
    monkeypatch.setenv("FISCAL_RECONCILE_ALERT_SINCE", "2026-10-23T00:00:00Z")
    s = Settings()
    assert s.fiscal_reconcile_enabled is True
    assert s.fiscal_reconcile_dry_run is True
    get_settings.cache_clear()
