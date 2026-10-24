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


def _patch_check(monkeypatch, check: dict[str, Any]) -> None:
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._load_latest_check",
        lambda _cid: check,
    )
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._job_belongs_to_case",
        lambda check_id, case_id: (
            str(check_id) == str(check.get("job_id") or check.get("id") or "")
            or str(check_id) == CHECK_ID
            or str(check_id).startswith("chk-")
        )
        and case_id == CASE_ID,
    )


def _first_payload_from_generator(primary: dict, check_id: str, needle: str) -> str:
    _text, atts = build_precheck_max_message(primary, check_id=check_id)
    blob = str(atts)
    marker = f"precheck:{needle}:{check_id}"
    assert marker in blob, blob
    return marker


def test_buttons_embed_check_id() -> None:
    text, atts = build_precheck_max_message(_primary(), check_id=CHECK_ID)
    assert "различие" in text.casefold()
    payload_blob = str(atts)
    assert f"precheck:summary:{CHECK_ID}" in payload_blob
    assert f"precheck:order:{CHECK_ID}" in payload_blob
    assert "Заказать подробный анализ" not in payload_blob
    assert "Условия заказа в кабинете" in payload_blob
    assert "завершен" not in text.casefold()


def test_generator_payload_through_handler(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    primary = _primary()
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "needs_action",
            "stale": False,
            "result": {"primary_precheck": primary},
        },
    )
    payload = _first_payload_from_generator(primary, CHECK_ID, "summary")
    res = handle_max_update(_cb(USER, payload, callback_id="cb-gen-1"), bot=bot)
    assert res.action == "precheck_summary"
    assert "различие" in (res.reply or "").casefold()
    assert bot.sent


def test_handler_stale_check_id_from_generator_blocks_order(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    old_primary = _primary(check_id="chk-old", offer=True)
    # Кнопка из «старого» сообщения
    old_payload = _first_payload_from_generator(old_primary, "chk-old", "order")
    _patch_check(
        monkeypatch,
        {
            "job_id": "chk-new",
            "status": "completed",
            "stale": False,
            "result": {"primary_precheck": _primary(check_id="chk-new", offer=False)},
        },
    )
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._job_belongs_to_case",
        lambda check_id, case_id: case_id == CASE_ID and check_id in {"chk-old", "chk-new"},
    )
    res = handle_max_update(_cb(USER, old_payload, callback_id="cb-stale-ord"), bot=bot)
    assert res.action == "stale_show_current"
    assert "не применен" in (res.reply or "").casefold() or "актуальн" in (
        res.reply or ""
    ).casefold()


def test_legacy_order_without_check_id_not_applied(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "needs_action",
            "stale": False,
            "result": {"primary_precheck": _primary()},
        },
    )
    res = handle_max_update(
        _cb(USER, "precheck:order", callback_id="cb-legacy"), bot=bot
    )
    assert res.action == "stale_missing_check_id"
    assert "не выполнен" in (res.reply or "").casefold()


def test_decline_then_order_blocked(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    primary = _primary()
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "needs_action",
            "stale": False,
            "result": {"primary_precheck": primary},
        },
    )
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._mark_declined",
        lambda _cid: True,
    )
    decline_pl = _first_payload_from_generator(primary, CHECK_ID, "decline")
    r1 = handle_max_update(_cb(USER, decline_pl, callback_id="cb-dec"), bot=bot)
    assert r1.action == "precheck_declined"
    assert r1.ok is True

    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks.live_offer_still_allowed",
        lambda **_k: (False, "client_declined"),
    )
    order_pl = _first_payload_from_generator(primary, CHECK_ID, "order")
    r2 = handle_max_update(_cb(USER, order_pl, callback_id="cb-ord-after"), bot=bot)
    assert r2.action == "precheck_order_blocked"


def test_paid_after_result_blocks_order(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    primary = _primary()
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "needs_action",
            "stale": False,
            "result": {"primary_precheck": primary},
        },
    )
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks.live_offer_still_allowed",
        lambda **_k: (False, "already_ordered_or_paid"),
    )
    order_pl = _first_payload_from_generator(primary, CHECK_ID, "order")
    res = handle_max_update(_cb(USER, order_pl, callback_id="cb-paid"), bot=bot)
    assert res.action == "precheck_order_blocked"


def test_decline_save_failure_no_false_ok(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    primary = _primary()
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "needs_action",
            "stale": False,
            "result": {"primary_precheck": primary},
        },
    )
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._mark_declined",
        lambda _cid: False,
    )
    pl = _first_payload_from_generator(primary, CHECK_ID, "decline")
    res = handle_max_update(_cb(USER, pl, callback_id="cb-dec-fail"), bot=bot)
    assert res.ok is False
    assert res.action == "precheck_decline_failed"
    assert "не удалось" in (res.reply or "").casefold()


def test_ask_staff_save_failure_honest(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    primary = _primary(offer=False)
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "completed",
            "stale": False,
            "result": {"primary_precheck": primary},
        },
    )
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._mark_ask_staff",
        lambda *_a, **_k: False,
    )
    pl = f"precheck:ask_staff:{CHECK_ID}"
    res = handle_max_update(_cb(USER, pl, callback_id="cb-ask-fail"), bot=bot)
    assert res.ok is False
    assert res.action == "precheck_ask_staff_failed"
    assert "отложено" not in (res.reply or "").casefold()
    assert "не удалось" in (res.reply or "").casefold()


def test_foreign_check_id_forbidden(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "completed",
            "stale": False,
            "result": {"primary_precheck": _primary(offer=False)},
        },
    )
    monkeypatch.setattr(
        "sfrfr.services.primary_doc_precheck_callbacks._job_belongs_to_case",
        lambda *_a, **_k: False,
    )
    res = handle_max_update(
        _cb(USER, "precheck:summary:other-case-job", callback_id="cb-foreign"),
        bot=bot,
    )
    assert res.action == "precheck_forbidden_check"
    assert res.ok is False


def test_no_case_access(tmp_path: Path, monkeypatch) -> None:
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
        _cb(USER, f"precheck:summary:{CHECK_ID}", callback_id="cb-nocase"),
        bot=bot,
    )
    assert res.action == "precheck_no_case"


def test_unknown_payload_safe(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    _patch_check(monkeypatch, {"job_id": CHECK_ID, "status": "completed", "stale": False})
    res = handle_max_update(
        _cb(USER, "precheck:hack_drop_table", callback_id="cb-unk"), bot=bot
    )
    assert res.action == "precheck_unknown"
    assert res.ok is False


def test_status_running_not_completed_text(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    _patch_check(
        monkeypatch,
        {"job_id": CHECK_ID, "status": "running", "stale": False, "result": {}},
    )
    res = handle_max_update(
        _cb(USER, f"precheck:status:{CHECK_ID}", callback_id="cb-run"), bot=bot
    )
    assert res.action == "precheck_status"
    assert "выполняется" in (res.reply or "").casefold()
    assert "завершен" not in (res.reply or "").casefold()


def test_repeat_summary_idempotent(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _bind_case(monkeypatch)
    get_intake_store().upsert_started(str(USER))
    primary = _primary(offer=False)
    _patch_check(
        monkeypatch,
        {
            "job_id": CHECK_ID,
            "status": "completed",
            "stale": False,
            "result": {"primary_precheck": primary},
        },
    )
    pl = _first_payload_from_generator(primary, CHECK_ID, "summary")
    r1 = handle_max_update(_cb(USER, pl, callback_id="cb-r1"), bot=bot)
    r2 = handle_max_update(_cb(USER, pl, callback_id="cb-r2"), bot=bot)
    assert r1.action == r2.action == "precheck_summary"
    assert r1.reply == r2.reply
