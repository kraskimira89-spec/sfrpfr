"""После анкеты: выбор диагностика 3 000 ₽ / чек-лист (clarity-funnel §4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import checklist_offer as lm
from sfrfr.integrations.max import diag_choice as dc
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import get_intake_store


def _start_with_name(user_id: int, first: str = "Анна") -> dict:
    return {
        "callback": {
            "user": {"user_id": user_id, "first_name": first, "last_name": "Петрова"},
            "chat_id": 1,
            "payload": "start_dialog",
        }
    }


def _complete_questionnaire(bot, user_id: int) -> None:
    handle_max_update(_start_with_name(user_id), bot=bot)
    for upd in (
        _cb(user_id, "q:exp:gt20"),
        _msg(user_id, "+7 909 195-04-08"),
        _cb(user_id, q.SKIP_EMAIL),
        _msg(user_id, "Не учли северный стаж"),
    ):
        handle_max_update(upd, bot=bot)


def _prepare(tmp_path: Path, monkeypatch):
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(q, "save_questionnaire", lambda **_kw: True)
    return bot


def test_diag_choice_after_questionnaire(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 921)
    assert bot.sent[-1][1] == dc.OFFER_TEXT
    offer = str(bot.attachments[-1])
    assert "Оформить диагностику" in offer
    assert "чек-лист" in offer.lower()
    rec = get_intake_store().get_active("921")
    assert rec is not None and dc.is_pending(rec)


def test_diag_checklist_opens_lead_magnet(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 922)
    res = handle_max_update(_cb(922, dc.CHECKLIST), bot=bot)
    assert res.action == "diag_checklist"
    assert bot.sent[-1][1] == lm.OFFER_TEXT
    assert "Получить на почту" in str(bot.attachments[-1])
    rec = get_intake_store().get_active("922")
    assert rec is not None and not dc.is_pending(rec)


def test_diag_yes_starts_payment(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 923)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._case_id_for_max_user",
        lambda _uid: "case-diag-1",
    )
    started: list[dict] = []

    def _fake_start(**kw):
        started.append(kw)
        return {"ok": True, "pay_sent": True}

    monkeypatch.setattr(dc, "start_diag_payment", _fake_start)
    res = handle_max_update(_cb(923, dc.YES), bot=bot)
    assert res.action == "diag_yes"
    assert started and started[0]["case_id"] == "case-diag-1"
    assert "3 000" in bot.sent[-1][1]
    assert "кабинет" not in bot.sent[-1][1].lower()
    rec = get_intake_store().get_active("923")
    assert rec is not None and not dc.is_pending(rec)


def test_start_diag_payment_accepts_contract(monkeypatch) -> None:
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_OWNED_PAY_LINK", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.has_consent.return_value = True
    repo.has_contract.return_value = False
    repo.get_case_row.return_value = {
        "id": "c1",
        "client_id": "cl1",
        "clients": {"max_user_id": "99"},
    }
    repo.list_orders.return_value = []
    repo.create_order.return_value = {"id": "o1", "package_code": "DIAG", "status": "draft"}
    repo.accept_contract.return_value = {"id": "ca1"}

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.client_pdn_consent.ensure_case_consent_from_client",
            return_value=True,
        ),
    ):
        out = dc.start_diag_payment(case_id="c1", max_user_id="99")

    assert out is not None and out.get("ok") and out.get("accepted")
    repo.create_order.assert_called_once()
    repo.accept_contract.assert_called_once()
    get_settings.cache_clear()


def test_start_diag_payment_resends_link_if_contracted(monkeypatch) -> None:
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_OWNED_PAY_LINK", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.has_consent.return_value = True
    repo.has_contract.return_value = True
    repo.get_case_row.return_value = {
        "id": "c1",
        "client_id": "cl1",
        "clients": {"max_user_id": "99"},
    }
    repo.list_orders.return_value = [
        {"id": "o1", "package_code": "DIAG", "status": "draft", "pay_url": ""}
    ]

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.client_pdn_consent.ensure_case_consent_from_client",
            return_value=True,
        ),
        patch(
            "sfrfr.services.max_bot_invoice.maybe_send_pay_link_after_contract",
            return_value={"pay_url": "https://pay.example/x"},
        ) as pay,
    ):
        out = dc.start_diag_payment(case_id="c1", max_user_id="99")

    assert out is not None and out.get("ok")
    repo.accept_contract.assert_not_called()
    assert pay.called
    get_settings.cache_clear()
