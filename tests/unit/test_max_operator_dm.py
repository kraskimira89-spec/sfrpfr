"""«Позвать специалиста» → немедленная личка ops-бота специалисту (не только канал)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.services.lead_ops_notify import notify_max_managers_new_lead


def test_notify_max_sends_dm_before_channel(monkeypatch) -> None:
    sent: list[dict] = []

    class _Bot:
        available = True

        def send_message(self, **kwargs):  # noqa: ANN003
            sent.append(kwargs)
            return {"ok": True}

    monkeypatch.setenv("MAX_OPS_BOT_TOKEN", "ops-token")
    monkeypatch.setenv("STAFF_LOGIN_APPROVER_MAX_USER_IDS", "6407832")
    monkeypatch.setenv("STAFF_LOGIN_APPROVER_MAX_CHAT_IDS", "321180237")
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-77768587291288")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "sfrfr.integrations.max.ops_bot.get_ops_bot",
        lambda: _Bot(),
    )
    monkeypatch.setattr(
        "sfrfr.db.staff_roles.list_ops_dm_max_user_ids",
        lambda extra_ids="": ["6407832"],
    )
    result = notify_max_managers_new_lead(
        case_id="case-1",
        full_name="Иван",
        phone="+7900",
        channel="max_miniapp",
        source_label="из чата MAX",
        max_user_id="11",
    )
    assert result["ok"] is True
    assert result.get("dm_sent") == 1
    assert str(sent[0].get("user_id")) == "6407832"
    assert sent[0].get("chat_id") is None
    chat_targets = [s.get("chat_id") for s in sent if s.get("chat_id")]
    assert "321180237" in [str(c) for c in chat_targets]
    assert "-77768587291288" in [str(c) for c in chat_targets]
    get_settings.cache_clear()


def test_operator_button_notifies_ops_dm(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()

    ops_calls: list[dict] = []

    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ensure_case_for_intake",
        lambda **_k: "case-op-1",
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_operator_staff",
        lambda **_k: None,
    )

    def _ops(**kw):
        ops_calls.append(kw)

    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_ops_max_operator",
        _ops,
    )

    handle_max_update(_msg(77, "/start"), bot=bot)
    result = handle_max_update(_cb(77, "intake:operator"), bot=bot)
    assert result.action == "max_operator_requested"
    assert ops_calls
    assert ops_calls[0]["user_id"] == "77"
    assert ops_calls[0]["case_id"] == "case-op-1"
    get_settings.cache_clear()


def test_list_ops_dm_includes_env_specialist(monkeypatch) -> None:
    from sfrfr.db.staff_roles import list_ops_dm_max_user_ids

    monkeypatch.setenv("STAFF_LOGIN_APPROVER_MAX_USER_IDS", "6407832")
    monkeypatch.setenv("MAX_DEFAULT_SPECIALIST_MAX_USER_ID", "6407832")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "sfrfr.db.staff_roles.get_supabase_client",
        MagicMock(side_effect=RuntimeError("no db")),
    )
    ids = list_ops_dm_max_user_ids()
    assert ids == ["6407832"]
    get_settings.cache_clear()
