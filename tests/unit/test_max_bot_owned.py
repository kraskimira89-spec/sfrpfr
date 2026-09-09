"""bot_owned: режим до специалиста, intake из текста, kit без OCR."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from sfrfr.core.case_store import reset_case_store
from sfrfr.core.config import get_settings
from sfrfr.integrations.max.bot_owned import (
    WAITING_FOR_STAFF_TEXT,
    is_bot_owned,
    is_handed_to_operator,
)
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store, reset_intake_store
from sfrfr.integrations.max.intake_from_text import resolve_intake_payload
from sfrfr.services.max_bot_invoice import (
    maybe_offer_diag_invoice,
    maybe_send_pay_link_after_contract,
    reset_offer_cache,
)
from sfrfr.services.max_kit_status import build_kit_message, classify_doc_bucket, reset_kit_cache


class _SilentBot:
    def __init__(self) -> None:
        self.sent: list[tuple[str | None, str]] = []
        self.available = True

    def send_message(self, *, text: str, user_id=None, chat_id=None, attachments=None, **_k):
        self.sent.append((str(user_id) if user_id else None, text))
        return {"message": {"mid": "m1"}}

    def send_chat_action(self, **_k):
        return {}

    def answer_callback(self, **_k):
        return {}


def _base_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "1")
    monkeypatch.setenv("AMOCRM_ENABLED", "0")
    monkeypatch.setenv("OPS_NOTIFY_EMAIL", "")
    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")
    reset_intake_store(tmp_path / "max_intake.json")
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent",
        lambda _uid: True,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_operator_staff",
        lambda **_k: None,
    )


def _msg(uid: int, text: str) -> dict:
    return {
        "message": {
            "sender": {"user_id": uid},
            "recipient": {"chat_id": 1, "chat_type": "dialog"},
            "body": {"text": text},
        }
    }


def _cb(uid: int, payload: str) -> dict:
    return {
        "callback": {
            "callback_id": f"cb-{payload}",
            "payload": payload,
            "user": {"user_id": uid},
            "chat_id": 1,
        }
    }


def test_is_bot_owned_false_after_operator() -> None:
    rec = MaxIntakeRecord(id="1", max_user_id="9", status="handed_to_operator")
    assert is_bot_owned(rec) is False
    assert is_handed_to_operator(rec) is True


def test_resolve_intake_whom() -> None:
    assert resolve_intake_payload(label="За себя", step="whom") == "intake:whom:self"
    assert resolve_intake_payload(label="нет", step="ils") == "intake:ils:no"
    assert resolve_intake_payload(label="нет", step="employment") == "intake:emp:no"
    assert resolve_intake_payload(label="За себя", step="ils") is None


def test_intake_from_text_advances_whom(tmp_path: Path, monkeypatch) -> None:
    _base_env(tmp_path, monkeypatch)
    bot = _SilentBot()
    handle_max_update(_msg(21, "/start"), bot=bot)
    result = handle_max_update(_msg(21, "За себя"), bot=bot)
    assert result.action == "intake_whom"
    intake = get_intake_store().get_active("21")
    assert intake is not None
    assert intake.for_whom == "self"
    assert intake.step() == "pension"


def test_operator_stops_llm(tmp_path: Path, monkeypatch) -> None:
    _base_env(tmp_path, monkeypatch)
    bot = _SilentBot()
    called = {"llm": 0}

    def _fake_llm(**_k):
        called["llm"] += 1
        return ("не должно", [], "max_llm_reply")

    monkeypatch.setattr(
        "sfrfr.integrations.max.llm_chat.reply_to_free_text",
        _fake_llm,
    )
    handle_max_update(_msg(22, "/start"), bot=bot)
    handle_max_update(_cb(22, "intake:operator"), bot=bot)
    result = handle_max_update(_msg(22, "подскажите по стажу"), bot=bot)
    assert result.action == "waiting_for_staff"
    assert called["llm"] == 0
    assert WAITING_FOR_STAFF_TEXT[:20] in (result.reply or "")


def test_upload_bot_owned_skips_staff_task(tmp_path: Path, monkeypatch) -> None:
    _base_env(tmp_path, monkeypatch)
    bot = _SilentBot()
    staff_calls: list = []

    def _track(*_a, **_k):
        staff_calls.append(_k)
        return True

    monkeypatch.setattr(
        "sfrfr.services.finance_automation.ensure_staff_task",
        _track,
    )
    monkeypatch.setattr(
        "sfrfr.services.max_document_upload.upload_max_document",
        lambda **_k: None,
    )
    handle_max_update(_msg(23, "/start"), bot=bot)
    for payload in (
        "intake:whom:self",
        "intake:pension:before",
        "intake:problem:ils_stazh",
        "intake:ils:yes",
        "intake:device:max",
    ):
        handle_max_update(_cb(23, payload), bot=bot)

    accepted = handle_max_update(
        {
            "message": {
                "sender": {"user_id": 23},
                "recipient": {"chat_id": 1, "chat_type": "dialog"},
                "body": {"text": ""},
            },
            "file_name": "ils.pdf",
            "file_bytes": b"%PDF-1.4 minimal",
        },
        bot=bot,
    )
    assert accepted.action == "upload"
    assert staff_calls == []
    assert "сверим комплект" in (accepted.reply or "").lower()


def test_kit_message_no_ocr_text() -> None:
    reset_kit_cache()
    msg = build_kit_message(
        latest_bucket="ils",
        have={"ils"},
        pension_assigned=False,
    )
    assert "трудовая" in msg.lower()
    assert "снилс" not in msg.lower()
    assert classify_doc_bucket({"requirement_code": "labor_book"}, None) == "labor"


def test_diag_offer_requires_consent(monkeypatch) -> None:
    repo = MagicMock()
    repo.has_consent.return_value = False
    repo.get_case_row.return_value = {"id": "c1", "b2c_status": "lead"}
    reset_offer_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    with patch("sfrfr.db.case_repository.CaseRepository", return_value=repo):
        out = maybe_offer_diag_invoice(
            case_id="c1",
            max_user_id="99",
            intake=MaxIntakeRecord(id="1", max_user_id="99", status="started"),
        )
    assert out is None
    repo.create_order.assert_not_called()


def test_pay_link_not_without_flag(monkeypatch) -> None:
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_OWNED_PAY_LINK", "0")
    get_settings.cache_clear()
    repo = MagicMock()
    assert maybe_send_pay_link_after_contract(repo=repo, case_id="c1", actor_id="x") is None
