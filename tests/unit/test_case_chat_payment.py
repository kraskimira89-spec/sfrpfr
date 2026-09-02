"""Pay-link из чата и метрики конверсии."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.services.case_chat_payment import (
    bot_reply_suggests_payment,
    mark_payment_nudge_converted,
    payment_intent_detected,
    resend_intent_detected,
)


def test_payment_intent_detected() -> None:
    assert payment_intent_detected("Как оплатить диагностику?")
    assert payment_intent_detected("Сколько стоит проверка?")
    assert not payment_intent_detected("Когда будет результат?")


def test_resend_intent() -> None:
    assert resend_intent_detected("Повторите ссылку на оплату, пожалуйста")


def test_bot_reply_suggests_payment() -> None:
    assert bot_reply_suggests_payment("Следующий шаг — оплата диагностики 3 000 ₽ в кабинете.")
    assert not bot_reply_suggests_payment("Загрузите выписку ИЛС в «Мои документы».")


@patch("sfrfr.services.case_chat_payment.get_settings")
@patch("sfrfr.services.case_chat_payment._recent_nudge_exists", return_value=False)
@patch("sfrfr.services.case_chat_payment.record_payment_nudge")
@patch("sfrfr.services.pay_link.issue_and_deliver_pay_link")
@patch("sfrfr.db.case_repository.CaseRepository")
def test_try_deliver_pay_link_cabinet_only(
    mock_repo_cls: MagicMock,
    mock_issue: MagicMock,
    mock_record: MagicMock,
    _mock_recent: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.return_value.case_chat_pay_link_enabled = True
    mock_repo = mock_repo_cls.return_value
    mock_repo.get_order_by_id.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "case_id": "00000000-0000-0000-0000-000000000099",
        "status": "pending",
        "amount_rub": 3000,
        "package_code": "DIAG",
    }
    mock_issue.return_value = {"pay_url": "https://yookassa.ru/pay/test"}
    with patch(
        "sfrfr.services.case_chat_payment._append_pay_link_case_message",
        return_value={"id": "msg-1", "body": "Счёт на оплату"},
    ):
        from sfrfr.services.case_chat_payment import try_deliver_pay_link_from_chat

        out = try_deliver_pay_link_from_chat(
            case={"id": "00000000-0000-0000-0000-000000000099", "clients": {}},
            work={
                "order": {
                    "can_pay": True,
                    "order_id": "00000000-0000-0000-0000-000000000001",
                    "amount_rub": 3000,
                }
            },
            user_text="Как оплатить?",
            channel="cabinet",
        )
    assert out is not None
    assert out["message_id"] == "msg-1"
    mock_record.assert_called_once()


@patch("sfrfr.db.session.get_supabase_client")
def test_mark_payment_nudge_converted(mock_sb: MagicMock) -> None:
    client = MagicMock()
    mock_sb.return_value = client
    select_chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value.is_
    select_chain.return_value.execute.return_value.data = [
        {"id": "n1", "channel": "cabinet", "source": "chat_bot_intent"}
    ]
    update_chain = client.table.return_value.update.return_value.eq.return_value.eq.return_value.is_
    update_chain.return_value.execute.return_value = None
    n = mark_payment_nudge_converted(
        case_id="00000000-0000-0000-0000-000000000099",
        order_id="00000000-0000-0000-0000-000000000001",
        payment_id="00000000-0000-0000-0000-000000000002",
    )
    assert n == 1
