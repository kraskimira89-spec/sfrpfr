"""Заказ звонка в MAX: имя + телефон в чате, без сайта."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import intake as inn
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import get_intake_store


def test_callback_button_asks_for_phone_name() -> None:
    btn = inn.callback_request_button()
    assert btn["type"] == "callback"
    assert "звонок" in btn["text"].lower() or "телефон" in btn["text"].lower()
    assert btn["payload"] == inn.CALLBACK_REQUEST_PAYLOAD
    assert "url" not in btn


def test_callback_flow_collects_and_thanks(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ensure_case_for_intake",
        lambda **_k: "case-cb-1",
    )
    notified: list[dict] = []

    def _fake_notify(**kw):
        notified.append(kw)

    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_ops_callback_request",
        _fake_notify,
    )
    with patch("sfrfr.integrations.max.handler._notify_operator_amocrm", lambda **_k: None):
        res = handle_max_update(_cb(501, inn.CALLBACK_REQUEST_PAYLOAD), bot=bot)
    assert res.action == "max_callback_ask"
    assert "телефон" in (res.reply or "").lower()
    assert "имя" in (res.reply or "").lower()
    rec = get_intake_store().get_active("501")
    assert rec is not None and inn.is_callback_waiting(rec)

    res2 = handle_max_update(_msg(501, "Иван +7 909 195-04-08"), bot=bot)
    assert res2.action == "max_callback_received"
    assert "перезвоним" in (res2.reply or "").lower()
    assert notified and notified[0].get("phone") == "+79091950408"
    assert "Иван" in (notified[0].get("full_name") or "")
    rec2 = get_intake_store().get_active("501")
    assert rec2 is not None and not inn.is_callback_waiting(rec2)
    get_settings.cache_clear()
