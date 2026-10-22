"""После анкеты: ранний upsell диагностики снят; старая кнопка не обходит gate."""

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


def test_no_early_diag_offer_after_questionnaire(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 921)
    texts = [t for _u, t in bot.sent]
    assert texts[-1] == q.completed_text(get_intake_store().get_active("921").case_id) or (
        "дело" in texts[-1].lower() and "создано" in texts[-1].lower()
    )
    assert dc.OFFER_TEXT not in texts
    assert not any("оформить диагностику" in (t or "").lower() for t in texts)
    rec = get_intake_store().get_active("921")
    assert rec is not None and not dc.is_pending(rec)


def test_old_diag_yes_callback_gated(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 923)
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    res = handle_max_update(_cb(923, dc.YES), bot=bot)
    assert res.action == "diag_yes_gated"
    assert started == []
    low = bot.sent[-1][1].lower()
    assert "пока не предлагаем" in low or "краткий разбор" in low
    assert "обрабатываем" not in low


def test_diag_checklist_still_reachable_via_lm_send(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 922)
    res = handle_max_update(_cb(922, lm.SEND), bot=bot)
    assert res.action == "checklist_ask_format"
    assert "PDF" in bot.sent[-1][1]


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
        patch(
            "sfrfr.services.max_bot_invoice.maybe_send_pay_link_after_contract",
            return_value={"pay_url": "https://yookassa.ru/my/i/test"},
        ) as pay,
    ):
        out = dc.start_diag_payment(case_id="c1", max_user_id="99")

    assert out is not None and out.get("ok") and out.get("accepted")
    assert out.get("pay", {}).get("pay_url")
    repo.create_order.assert_called_once()
    repo.accept_contract.assert_called_once()
    assert pay.called
    get_settings.cache_clear()


def test_start_diag_payment_accept_max_actor_then_pay(monkeypatch) -> None:
    """Регресс: actor_id max:* раньше ронял access_audit (uuid) → FAIL_TEXT."""
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_OWNED_PAY_LINK", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.has_consent.return_value = True
    repo.has_contract.return_value = False
    repo.get_case_row.return_value = {
        "id": "c3074452-ac27-4f43-b5ee-88af96792b17",
        "client_id": "cl1",
        "clients": {"max_user_id": "79841100"},
    }
    repo.list_orders.return_value = [
        {
            "id": "o1",
            "package_code": "DIAG",
            "status": "pending_payment",
            "invoice_status": "pending_payment",
            "pay_url": "",
        }
    ]
    accepted_actors: list[str] = []

    def _accept(_cid: str, **kwargs):
        accepted_actors.append(str(kwargs.get("actor_id") or ""))
        return {"id": "ca1"}

    repo.accept_contract.side_effect = _accept

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.client_pdn_consent.ensure_case_consent_from_client",
            return_value=True,
        ),
        patch(
            "sfrfr.services.max_bot_invoice.maybe_send_pay_link_after_contract",
            return_value={"pay_url": "https://yookassa.ru/my/i/x"},
        ),
    ):
        out = dc.start_diag_payment(
            case_id="c3074452-ac27-4f43-b5ee-88af96792b17",
            max_user_id="79841100",
        )

    assert out is not None and out.get("ok")
    assert accepted_actors == ["max:79841100"]
    assert "yookassa.ru" in str((out.get("pay") or {}).get("pay_url") or "")
    get_settings.cache_clear()


def test_fail_text_for_reason_is_specific() -> None:
    assert "оферт" in dc.fail_text_for_reason("accept_contract").lower()
    assert "ссылк" in dc.fail_text_for_reason("pay_link").lower()
    assert "заказ" in dc.fail_text_for_reason("orders_load").lower()
    assert "специалист" in dc.fail_text_for_reason("unknown").lower()


def test_start_diag_payment_orders_load_fail_does_not_create(monkeypatch) -> None:
    """Ошибка list_orders ≠ «нет заказов»: не создаём повторный счёт."""
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_OWNED_PAY_LINK", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.has_consent.return_value = True
    repo.get_case_row.return_value = {
        "id": "c1",
        "client_id": "cl1",
        "clients": {"max_user_id": "99"},
    }
    repo.list_orders.side_effect = RuntimeError("db down")

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.client_pdn_consent.ensure_case_consent_from_client",
            return_value=True,
        ),
    ):
        out = dc.start_diag_payment(case_id="c1", max_user_id="99")

    assert out is not None
    assert out.get("ok") is False
    assert out.get("reason") == "orders_load"
    repo.create_order.assert_not_called()
    get_settings.cache_clear()


def test_diag_yes_paid_checked_before_gate(tmp_path: Path, monkeypatch) -> None:
    """Старая кнопка diag:yes: оплата раньше gate/brief-флагов (после restart)."""
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 924)
    rec = get_intake_store().get_active("924")
    assert rec is not None
    # Флаги brief потеряны — gate бы отклонил без paid-check.
    rec.q_answers = {}
    get_intake_store().save(rec)

    paid_text = "Диагностика уже оплачена. Документы в деле."
    started: list[dict] = []
    monkeypatch.setattr(
        dc,
        "_diag_already_paid_text",
        lambda _cid: paid_text,
    )
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )

    res = handle_max_update(_cb(924, dc.YES), bot=bot)
    assert res.action == "diag_yes_paid"
    assert started == []
    assert "уже оплачена" in bot.sent[-1][1].lower()


def test_diag_yes_orders_error_blocks_without_create(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 925)
    monkeypatch.setattr(dc, "_diag_already_paid_text", lambda _cid: None)
    monkeypatch.setattr(
        dc,
        "start_diag_payment",
        lambda **_kw: {"ok": False, "reason": "orders_load"},
    )
    # Полные флаги, чтобы gate пустил до start_diag_payment.
    rec = get_intake_store().get_active("925")
    assert rec is not None
    from sfrfr.services import brief_analysis as ba

    ba.persist_brief_to_intake(
        rec,
        ba.BriefAnalysisResult(
            ok=True,
            current=True,
            has_justified_discrepancy=True,
            summary="Тест",
            fingerprint="fp1",
        ),
    )
    ba.mark_summary_shown(rec)
    ba.mark_detail_consent(rec, wants=True)

    res = handle_max_update(_cb(925, dc.YES), bot=bot)
    assert res.action == "diag_yes_fail"
    assert "заказ" in bot.sent[-1][1].lower()


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
