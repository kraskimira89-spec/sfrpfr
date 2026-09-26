"""ТЗ-35 A2: без согласия ПДн — ни диалога, ни файлов; с согласием файлы принимаются всегда."""

from __future__ import annotations

from pathlib import Path

from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.handler import handle_max_update

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _no_consent(monkeypatch) -> None:
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent",
        lambda _uid: False,
    )


def _files(monkeypatch) -> list[tuple[str, str]]:
    ingested: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._collect_max_files",
        lambda _update: [("trudovaya.pdf", b"%PDF-1.4")],
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._try_max_payment_receipt",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ingest_max_file",
        lambda **kw: ingested.append((kw["case_id"], kw["filename"])) or True,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_staff_chat_docs",
        lambda **_kw: None,
    )
    return ingested


def test_file_without_consent_is_not_accepted(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _no_consent(monkeypatch)
    ingested = _files(monkeypatch)

    result = handle_max_update(_msg(201, ""), bot=bot)

    assert result.action == "pdn_consent_gate"
    assert ingested == []
    get_settings.cache_clear()


def test_free_text_without_consent_shows_gate(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _no_consent(monkeypatch)
    logged: list[str] = []
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._append_client_case_message",
        lambda **kw: logged.append(str(kw.get("text"))) or None,
    )

    result = handle_max_update(_msg(202, "Мне не учли стаж на заводе"), bot=bot)

    assert result.action == "pdn_consent_gate"
    assert not any("завод" in t for t in logged)
    get_settings.cache_clear()


def test_intake_button_without_consent_shows_gate(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _no_consent(monkeypatch)

    result = handle_max_update(_cb(203, "intake:goal:self", callback_id="cb-a2-203"), bot=bot)

    assert result.action == "pdn_consent_gate"
    get_settings.cache_clear()


def test_login_without_consent_is_not_blocked(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _no_consent(monkeypatch)

    result = handle_max_update(_msg(204, "/login"), bot=bot)

    assert result.action != "pdn_consent_gate"
    get_settings.cache_clear()


def test_decline_shows_contacts() -> None:
    from sfrfr.services.client_pdn_consent import CONSENT_DECLINED_TEXT

    assert "+7 909 195-04-08" in CONSENT_DECLINED_TEXT
    assert "proverkastaza@yandex.ru" in CONSENT_DECLINED_TEXT


def test_file_with_consent_after_pause_goes_to_existing_case(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    ingested = _files(monkeypatch)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._chat_case_id",
        lambda _uid, preferred=None: CASE_ID,
    )

    result = handle_max_update(_msg(205, ""), bot=bot)

    assert result.action == "upload"
    assert ingested == [(CASE_ID, "trudovaya.pdf")]
    get_settings.cache_clear()
