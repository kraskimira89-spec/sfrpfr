"""Заявки при недоступной БД: аварийный буфер + уведомления сотрудникам + успех клиенту."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from sfrfr.core import config as cfg


class _DeadDb:
    def table(self, _name: str) -> Any:
        raise ConnectionError("db down")


@pytest.fixture()
def storage(tmp_path: Path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    env = {
        "STORAGE_LOCAL_PATH": str(uploads),
        "OPS_NOTIFY_EMAIL": "ops@example.test",
        "STAFF_LOGIN_APPROVER_MAX_USER_IDS": "111",
        "STAFF_LOGIN_APPROVER_MAX_CHAT_IDS": "321180237",
        "MAX_SPECIALISTS_CHANNEL_CHAT_ID": "-777",
        "MAX_DEFAULT_SPECIALIST_MAX_USER_ID": "",
        "AMOCRM_ENABLED": "false",
    }
    with patch.dict("os.environ", env):
        cfg.get_settings.cache_clear()
        yield tmp_path
    cfg.get_settings.cache_clear()


class _Bot:
    available = True

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_message(self, **kw: Any) -> dict[str, Any]:
        self.sent.append(kw)
        return {"ok": True}


def _read_buffer(root: Path) -> list[dict[str, Any]]:
    path = root / "emergency_leads.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_site_lead_db_down_is_buffered_notified_and_accepted(storage: Path) -> None:
    from sfrfr.api.routes import public_leads

    mails: list[dict[str, Any]] = []
    bot = _Bot()
    payload = public_leads.PublicLeadRequest(
        full_name="Анна",
        phone="+79990000000",
        email="anna@example.test",
        consent=True,
        preferred_channel="max_miniapp",
    )
    with (
        patch.object(public_leads, "_require_captcha", lambda **_kw: None),
        patch.object(public_leads, "get_supabase_client", return_value=_DeadDb()),
        patch(
            "sfrfr.integrations.yandex_workspace.mail.send_mail",
            side_effect=lambda **kw: mails.append(kw) or {"ok": True},
        ),
        patch("sfrfr.integrations.max.ops_bot.get_ops_bot", return_value=bot),
        patch("sfrfr.db.staff_roles.get_supabase_client", return_value=_DeadDb()),
    ):
        resp = public_leads._create_lead(payload)

    assert resp.ok is True
    assert resp.case_id is None
    assert resp.detail == "lead_buffered"

    rows = _read_buffer(storage)
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "site"
    assert row["full_name"] == "Анна"
    assert row["phone"] == "+79990000000"
    assert row["consent"] is True
    assert row["imported_case_id"] is None
    assert row["id"]

    assert len(mails) == 1
    assert mails[0]["to"] == "ops@example.test"
    assert "Анна" in mails[0]["body"]
    targets = [m.get("user_id") or m.get("chat_id") for m in bot.sent]
    assert "111" in targets
    assert "-777" in targets
    assert "321180237" not in targets


def test_max_new_client_db_down_notifies_once(storage: Path) -> None:
    from sfrfr.services.lead_emergency_buffer import capture_max_lead_db_down

    bot = _Bot()
    mails: list[dict[str, Any]] = []
    with (
        patch(
            "sfrfr.integrations.yandex_workspace.mail.send_mail",
            side_effect=lambda **kw: mails.append(kw) or {"ok": True},
        ),
        patch("sfrfr.integrations.max.ops_bot.get_ops_bot", return_value=bot),
        patch("sfrfr.db.staff_roles.get_supabase_client", return_value=_DeadDb()),
    ):
        first = capture_max_lead_db_down(max_user_id="555", full_name="Иван")
        second = capture_max_lead_db_down(max_user_id="555", full_name="Иван")

    assert first is not None
    assert second is None
    rows = _read_buffer(storage)
    assert len(rows) == 1
    assert rows[0]["source"] == "max"
    assert rows[0]["max_user_id"] == "555"
    assert len(mails) == 1


def test_import_dry_run_then_apply_is_idempotent(storage: Path) -> None:
    from sfrfr.services import lead_emergency_import as imp
    from sfrfr.services.lead_emergency_buffer import append_emergency_lead

    append_emergency_lead(
        {"source": "site", "full_name": "Анна", "phone": "+7999", "consent": True}
    )
    append_emergency_lead({"source": "site", "full_name": "ТЕСТ агент", "consent": True})
    append_emergency_lead({"source": "max", "max_user_id": "555", "full_name": "Иван"})

    created: list[dict[str, Any]] = []

    def _fake_insert(rec: dict[str, Any]) -> str:
        created.append(rec)
        return f"case-{len(created)}"

    with patch.object(imp, "_insert_site_lead", _fake_insert):
        plan = imp.import_emergency_leads(apply=False)
        assert plan["to_import"] == 1
        assert plan["skipped_test"] == 1
        assert plan["max_pending"] == 1
        assert created == []

        done = imp.import_emergency_leads(apply=True)
        assert done["imported"] == 1
        again = imp.import_emergency_leads(apply=True)
        assert again["imported"] == 0

    assert len(created) == 1
    rows = _read_buffer(storage)
    assert rows[0]["imported_case_id"] == "case-1"
