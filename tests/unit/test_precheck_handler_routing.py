"""Фактическая маршрутизация precheck:* через handle_max_update → _reply."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from test_max_intake import _cb, _setup

from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import get_intake_store
from sfrfr.services.primary_doc_precheck_notify import build_precheck_max_message

CASE_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
CHECK_ID = "chk-current-001"
USER = 4401


def _bind_case(monkeypatch, *, user_id: str = str(USER), case_id: str = CASE_ID) -> MagicMock:
    store = MagicMock()
    store.find_by_max_user.return_value = {"case_id": case_id, "max_user_id": user_id}
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler.get_case_store", lambda: store
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._case_id_for_max_user",
        lambda _uid: case_id,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ensure_case_for_intake",
        lambda **_kw: case_id,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ack_message_callback",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._append_client_case_message",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.webhook_dedupe.claim_callback_id",
        lambda _cid: True,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._is_rapid_repeat_callback",
        lambda **_k: False,
    )
    return store


def _primary(*, check_id: str = CHECK_ID, offer: bool = True) -> dict:
    return {
        "check_id": check_id,
        "outcome": "discrepancies_found",
        "comparison_status": "discrepancies_found",
        "client_summary": "Есть различие дат между ИЛС и трудовой.",
        "findings": [
            {
                "code": "DATE_DIFFERENCE",
                "what": "даты конца периода",
                "source_a": "ils:1",
                "source_b": "labor:1",
            }
        ],
        "limitations": ["Первичная проверка, не доказанная недоплата."],
        "recommendation": {
            "offer_paid_analysis": offer,
            "amount_rub": 3000,
            "service_scope": "проверка оснований",
        },
    }


def test_buttons_embed_check_id() -> None:
    text, atts = build_precheck_max_message(_primary(), check_id=CHECK_ID)
    assert "различие" in text.casefold()
    payload_blob = str(atts)
    assert f"precheck:summary:{CHECK_ID}" in payload_blob
    assert f"precheck:order:{CHECK_ID}" in payload_blob


def test_handler_routes_precheck_summary_to_reply(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))

    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._load_latest_check",
        lambda _cid: {
            "job_id": CHECK_ID,
            "stale": False,
            "result": {"primary_precheck": _primary()},
        },
    )

    res = handle_max_update(
        _cb(USER, f"precheck:summary:{CHECK_ID}", callback_id="cb-pc-1"),
        bot=bot,
    )
    assert res.action == "precheck_summary"
    assert res.case_id == CASE_ID
    assert res.reply
    assert "различие" in res.reply.casefold()
    assert bot.sent, "ожидался контролируемый _reply через bot.send_message"


def test_handler_no_case_access(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    store = MagicMock()
    store.find_by_max_user.return_value = None
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler.get_case_store", lambda: store
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._case_id_for_max_user", lambda _uid: None
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ensure_case_for_intake",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ack_message_callback",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._append_client_case_message",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.webhook_dedupe.claim_callback_id",
        lambda _cid: True,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._is_rapid_repeat_callback",
        lambda **_k: False,
    )
    get_intake_store().upsert_started(str(USER))

    res = handle_max_update(
        _cb(USER, "precheck:summary", callback_id="cb-pc-nocase"),
        bot=bot,
    )
    assert res.action == "precheck_no_case"
    assert "сотруднику" in (res.reply or "").casefold()


def test_handler_stale_check_id_shows_current(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._load_latest_check",
        lambda _cid: {
            "job_id": "chk-new",
            "stale": False,
            "result": {
                "primary_precheck": _primary(check_id="chk-new", offer=False)
            },
        },
    )
    res = handle_max_update(
        _cb(USER, "precheck:order:chk-old", callback_id="cb-pc-stale"),
        bot=bot,
    )
    assert res.action == "stale_show_current"
    assert res.reply


def test_handler_order_does_not_create_invoice(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    create_calls: list[Any] = []

    def _no_create(*_a, **_k):  # noqa: ANN001
        create_calls.append(1)
        raise AssertionError("order must not be created from precheck:order")

    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._load_latest_check",
        lambda _cid: {
            "job_id": CHECK_ID,
            "stale": False,
            "result": {"primary_precheck": _primary()},
        },
    )
    # если кто-то импортирует создание заказа — перехватим распространённые точки
    for target in (
        "sfrfr.services.max_bot_invoice.create_order",
        "sfrfr.db.case_repository.CaseRepository.create_order",
    ):
        try:
            monkeypatch.setattr(target, _no_create, raising=False)
        except Exception:  # noqa: BLE001
            pass

    res = handle_max_update(
        _cb(USER, f"precheck:order:{CHECK_ID}", callback_id="cb-pc-order"),
        bot=bot,
    )
    assert res.action == "precheck_order_handoff"
    assert not create_calls


def test_handler_repeat_callback_idempotent_summary(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._load_latest_check",
        lambda _cid: {
            "job_id": CHECK_ID,
            "stale": False,
            "result": {"primary_precheck": _primary(offer=False)},
        },
    )
    r1 = handle_max_update(
        _cb(USER, f"precheck:summary:{CHECK_ID}", callback_id="cb-pc-r1"),
        bot=bot,
    )
    r2 = handle_max_update(
        _cb(USER, f"precheck:summary:{CHECK_ID}", callback_id="cb-pc-r2"),
        bot=bot,
    )
    assert r1.action == r2.action == "precheck_summary"
    assert r1.reply == r2.reply
