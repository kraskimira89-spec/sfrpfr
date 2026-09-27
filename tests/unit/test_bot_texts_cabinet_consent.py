"""Тексты бота: кликабельный личный кабинет, согласие частями, кнопки после «Не согласен»."""

from __future__ import annotations

from pathlib import Path

from test_max_intake import _cb, _msg, _setup

from sfrfr.integrations.max import intake
from sfrfr.integrations.max.cabinet_link import linkify_cabinet
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.services import client_pdn_consent as consent


def test_linkify_wraps_phrase_and_escapes() -> None:
    text, fmt = linkify_cabinet(
        "Файлы <PDF> — в чат или в личном кабинете на сайте.", "https://c.ru/?case=1#documents"
    )
    assert fmt == "html"
    assert '<a href="https://c.ru/?case=1#documents">личном кабинете</a>' in text
    assert "&lt;PDF&gt;" in text


def test_linkify_noop_without_phrase() -> None:
    assert linkify_cabinet("Пришлите файл", "https://c.ru") == ("Пришлите файл", None)


def test_bot_texts_do_not_mention_site_section() -> None:
    for text in (
        intake.WELCOME_PART_2,
        intake.SUMMARY_TEXT,
        intake.UPLOAD_BLOCKED_TEXT,
        intake.DOCS_INFO_TEXT,
    ):
        assert "«Мои документы» на сайте" not in text


def test_consent_parts_join_to_hashed_text() -> None:
    assert "\n\n".join(consent.CONSENT_GATE_PARTS) == consent.CONSENT_GATE_TEXT
    assert len(consent.CONSENT_GATE_PARTS[0]) < 120


def test_consent_gate_sent_in_parts_with_buttons_last(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent", lambda _uid: False
    )
    result = handle_max_update(_msg(951, "привет"), bot=bot)
    assert result.action == "pdn_consent_gate"
    texts = [t for _u, t in bot.sent]
    assert texts[-len(consent.CONSENT_GATE_PARTS) :] == list(consent.CONSENT_GATE_PARTS)
    assert bot.attachments[-1] and "Начать" in str(bot.attachments[-1])
    assert all(a is None for a in bot.attachments[-len(consent.CONSENT_GATE_PARTS) : -1])


def test_decline_shows_channel_and_site_buttons(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    result = handle_max_update(_cb(952, consent.PDN_CONSENT_DECLINE_CALLBACK), bot=bot)
    assert result.action == "pdn_consent_declined"
    kb = str(bot.attachments[-1])
    for needle in ("Начать", "Подписаться на канал", consent.CHANNEL_URL, consent.SITE_URL):
        assert needle in kb
