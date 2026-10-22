"""access_audit.actor_id — uuid: bot/max токены не должны ронять accept_contract."""

from __future__ import annotations

from unittest.mock import MagicMock

from sfrfr.db.case_repository import CaseRepository, coerce_audit_actor


def test_coerce_audit_actor_keeps_uuid() -> None:
    uid = "c3074452-ac27-4f43-b5ee-88af96792b17"
    actor, suffix = coerce_audit_actor(uid)
    assert actor == uid
    assert suffix == ""


def test_coerce_audit_actor_nulls_max_token() -> None:
    actor, suffix = coerce_audit_actor("max:79841100")
    assert actor is None
    assert "max:79841100" in suffix


def test_coerce_audit_actor_nulls_bot_token() -> None:
    actor, suffix = coerce_audit_actor("bot:max_diag_choice")
    assert actor is None
    assert "bot:max_diag_choice" in suffix


def test_audit_inserts_null_actor_for_max_token() -> None:
    repo = CaseRepository.__new__(CaseRepository)
    table = MagicMock()
    insert = MagicMock()
    table.insert.return_value = insert
    insert.execute.return_value = MagicMock()
    client = MagicMock()
    client.table.return_value = table
    repo.client = client

    repo.audit("c3074452-ac27-4f43-b5ee-88af96792b17", "max:79841100", "contract_accepted")

    client.table.assert_called_with("access_audit")
    payload = table.insert.call_args[0][0]
    assert payload["actor_id"] is None
    assert payload["action"].startswith("contract_accepted")
    assert "max:79841100" in payload["action"]
