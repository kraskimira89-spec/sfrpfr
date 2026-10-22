"""P0: staff «Отправить в MAX» — доставка не молчит при сбое outbox/MAX."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sfrfr.api.routes import admin_portal
from sfrfr.api.schemas.admin import MaxReplyRequest
from sfrfr.security.auth import Principal, StaffRole
from sfrfr.services import case_chat_delivery as delivery


def _empty_recent_messages_sb() -> MagicMock:
    sb = MagicMock()
    chain = (
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit
    )
    chain.return_value.execute.return_value = SimpleNamespace(data=[])
    return sb


def test_mirror_returns_false_when_outbox_not_sent() -> None:
    case = {"id": "case-1", "clients": {"max_user_id": "u-1"}}
    with (
        patch.object(delivery, "enqueue_max_delivery", return_value=True),
        patch.object(delivery, "process_pending_outbox", return_value=0),
        patch.object(delivery, "_outbox_is_sent", return_value=False),
    ):
        assert (
            delivery.mirror_staff_message_to_max(case, "Ответ", message_id="m-1") is False
        )


def test_mirror_ok_when_outbox_already_sent() -> None:
    case = {"id": "case-1", "clients": {"max_user_id": "u-1"}}
    with (
        patch.object(delivery, "enqueue_max_delivery", return_value=True),
        patch.object(delivery, "process_pending_outbox", return_value=0),
        patch.object(delivery, "_outbox_is_sent", return_value=True),
    ):
        assert delivery.mirror_staff_message_to_max(case, "Ответ", message_id="m-1") is True


def test_mirror_handles_clients_as_list() -> None:
    case = {"id": "case-1", "clients": [{"max_user_id": "u-9"}]}
    with (
        patch.object(delivery, "enqueue_max_delivery", return_value=True) as enqueue,
        patch.object(delivery, "process_pending_outbox", return_value=1),
    ):
        assert delivery.mirror_staff_message_to_max(case, "hi", message_id="m-2") is True
    assert enqueue.call_args.kwargs["max_user_id"] == "u-9"


def test_max_reply_surfaces_delivery_failure() -> None:
    case = {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "clients": {"max_user_id": "42", "email": "a@b.c", "id": "c1"},
    }
    principal = Principal(
        user_id="staff-1",
        email="s@example.com",
        role=StaffRole.EXPERT,
    )
    repo = MagicMock()
    repo.require_case.return_value = case
    payload = MaxReplyRequest(message="Здравствуйте, проверьте ИЛС")

    with (
        patch.object(admin_portal, "_repo", return_value=repo),
        patch.object(admin_portal, "get_supabase_client", return_value=_empty_recent_messages_sb()),
        patch(
            "sfrfr.db.marketing_consent_repository.MarketingConsentRepository"
        ) as mkt_cls,
        patch(
            "sfrfr.db.case_messages_write.insert_case_message",
            return_value={"id": "msg-1"},
        ),
        patch(
            "sfrfr.services.case_chat_delivery.mirror_staff_message_to_max",
            return_value=False,
        ),
    ):
        mkt_cls.return_value.list_for_contact.return_value = []
        with pytest.raises(HTTPException) as exc_info:
            admin_portal.send_max_reply_to_client(
                case["id"], payload, principal=principal
            )

    assert exc_info.value.status_code == 502
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "max_send_failed"


def test_max_reply_ok_when_delivered() -> None:
    case = {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "clients": {"max_user_id": "42", "email": "a@b.c", "id": "c1"},
    }
    principal = Principal(
        user_id="staff-1",
        email="s@example.com",
        role=StaffRole.ADMIN,
    )
    repo = MagicMock()
    repo.require_case.return_value = case
    payload = MaxReplyRequest(message="Текст ответа клиенту")

    with (
        patch.object(admin_portal, "_repo", return_value=repo),
        patch.object(admin_portal, "get_supabase_client", return_value=_empty_recent_messages_sb()),
        patch(
            "sfrfr.db.marketing_consent_repository.MarketingConsentRepository"
        ) as mkt_cls,
        patch(
            "sfrfr.db.case_messages_write.insert_case_message",
            return_value={"id": "msg-ok"},
        ),
        patch(
            "sfrfr.services.case_chat_delivery.mirror_staff_message_to_max",
            return_value=True,
        ),
    ):
        mkt_cls.return_value.list_for_contact.return_value = []
        out = admin_portal.send_max_reply_to_client(
            case["id"], payload, principal=principal
        )

    assert out["ok"] is True
    assert out["queued"] is True
    assert out["message_id"] == "msg-ok"
    repo.audit.assert_called()
