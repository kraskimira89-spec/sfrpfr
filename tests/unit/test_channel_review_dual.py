"""Премодерация черновиков канала: dual = канал специалистов + лички ops."""

from __future__ import annotations

from pathlib import Path

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.channel_drafts import ChannelDraft, reset_draft_store
from sfrfr.integrations.max.channel_review import send_draft_for_review
from sfrfr.integrations.max.client import MaxBotClient


class _CaptureBot(MaxBotClient):
    def __init__(self) -> None:
        super().__init__(token="test-ops-token")
        self.sent: list[dict] = []

    def send_message(self, **kwargs):  # noqa: ANN003
        self.sent.append(kwargs)
        return {"ok": True, "message": {"body": {"mid": "m1"}}}


def _draft() -> ChannelDraft:
    return ChannelDraft(
        id="d1",
        text="Черновик поста для клиентского канала",
        cta_label="",
        cta_kind="",
        cta_url="",
        pin=False,
        source_id="08-ils",
    )


def test_dual_sends_channel_and_dm(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-100111")
    monkeypatch.setenv("STAFF_LOGIN_APPROVER_MAX_USER_IDS", "42,43")
    get_settings.cache_clear()
    reset_draft_store(tmp_path / "drafts.json")
    bot = _CaptureBot()
    out = send_draft_for_review(_draft(), ops_bot=bot, to_channel=False)
    assert out["ok"] is True
    assert out["mode"] == "dual"
    assert out["chat_id"] == "-100111"
    assert out["user_ids"] == ["42", "43"]
    assert any(s.get("chat_id") == "-100111" for s in bot.sent)
    assert {s.get("user_id") for s in bot.sent if s.get("user_id")} == {"42", "43"}
    get_settings.cache_clear()


def test_to_channel_only_skips_dm(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-100222")
    monkeypatch.setenv("STAFF_LOGIN_APPROVER_MAX_USER_IDS", "99")
    get_settings.cache_clear()
    reset_draft_store(tmp_path / "drafts.json")
    bot = _CaptureBot()
    out = send_draft_for_review(_draft(), ops_bot=bot, to_channel=True)
    assert out["ok"] is True
    assert out["mode"] == "channel"
    assert len(bot.sent) == 1
    assert bot.sent[0].get("chat_id") == "-100222"
    get_settings.cache_clear()
