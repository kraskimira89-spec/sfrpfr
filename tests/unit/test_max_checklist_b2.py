"""ТЗ-35 B2: чек-лист на e-mail после анкеты — формат PDF/Word."""

from __future__ import annotations

from pathlib import Path

from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import checklist_offer as lm
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import get_intake_store
from sfrfr.integrations.yandex_workspace.mail import redact_outbound_body


def test_email_body_survives_redaction_and_has_disclaimer() -> None:
    body = lm.build_email_body(first_name="Мария", fmt="pdf")
    assert redact_outbound_body(body) == body
    assert lm.CHECKLIST_TITLE in body
    assert "Здравствуйте, Мария!" in body
    assert "pension-checklist-a4.pdf" in body
    assert "подаёте через СФР или Госуслуги вы сами" in body
    assert "перерасчёт" not in body.lower()


def test_email_body_docx_primary() -> None:
    body = lm.build_email_body(fmt="docx")
    assert "pension-checklist-a4.docx" in body
    assert "Word" in body


def _start_with_name(user_id: int, first: str = "Анна") -> dict:
    return {
        "callback": {
            "user": {"user_id": user_id, "first_name": first, "last_name": "Петрова"},
            "chat_id": 1,
            "payload": "start_dialog",
        }
    }


def _complete_questionnaire(bot, user_id: int, email: str = "") -> None:
    handle_max_update(_start_with_name(user_id), bot=bot)
    for upd in (
        _cb(user_id, "q:exp:gt20"),
        _msg(user_id, "+7 909 195-04-08"),
        _msg(user_id, email) if email else _cb(user_id, q.SKIP_EMAIL),
        _msg(user_id, "Не учли стаж на заводе"),
    ):
        handle_max_update(upd, bot=bot)


def _prepare(tmp_path: Path, monkeypatch, sent: list[dict] | None = None, ok: bool = True):
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(q, "save_questionnaire", lambda **_kw: True)

    def _fake_send(*, to: str, first_name: str | None = None, fmt: str = "pdf") -> bool:
        if sent is not None:
            sent.append({"to": to, "first_name": first_name, "fmt": fmt})
        return ok

    monkeypatch.setattr(lm, "send_checklist_email", _fake_send)
    return bot


def test_offer_after_questionnaire(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 901)
    assert bot.sent[-1][1] == lm.OFFER_TEXT
    offer = str(bot.attachments[-1])
    assert "Получить на почту" in offer and "Уже есть" in offer


def test_send_asks_format_then_email_then_sends(tmp_path: Path, monkeypatch) -> None:
    sent: list[dict] = []
    bot = _prepare(tmp_path, monkeypatch, sent)
    _complete_questionnaire(bot, 902)
    res = handle_max_update(_cb(902, lm.SEND), bot=bot)
    assert res.action == "checklist_ask_format"
    assert "PDF" in bot.sent[-1][1] and "Word" in bot.sent[-1][1]
    res = handle_max_update(_cb(902, lm.FMT_DOCX), bot=bot)
    assert res.action == "checklist_ask_email"
    res = handle_max_update(_msg(902, "Anna@Example.ru"), bot=bot)
    assert res.action == "checklist_email_sent"
    assert sent == [{"to": "anna@example.ru", "first_name": "Анна", "fmt": "docx"}]
    assert "anna@example.ru" in bot.sent[-1][1]
    assert "Word" in bot.sent[-1][1]
    rec = get_intake_store().get_active("902")
    assert rec is not None and rec.lm_step is None and rec.lm_send_count == 1


def test_known_email_after_format(tmp_path: Path, monkeypatch) -> None:
    sent: list[dict] = []
    bot = _prepare(tmp_path, monkeypatch, sent)
    _complete_questionnaire(bot, 903, email="petrova@example.ru")
    handle_max_update(_cb(903, lm.SEND), bot=bot)
    handle_max_update(_cb(903, lm.FMT_PDF), bot=bot)
    assert "Отправить на petrova@example.ru" in str(bot.attachments[-1])
    res = handle_max_update(_cb(903, lm.USE_KNOWN), bot=bot)
    assert res.action == "checklist_email_sent"
    assert sent[0] == {"to": "petrova@example.ru", "first_name": "Анна", "fmt": "pdf"}


def test_already_have(tmp_path: Path, monkeypatch) -> None:
    sent: list[dict] = []
    bot = _prepare(tmp_path, monkeypatch, sent)
    _complete_questionnaire(bot, 904)
    res = handle_max_update(_cb(904, lm.HAVE), bot=bot)
    assert res.action == "checklist_have"
    assert bot.sent[-1][1] == lm.HAVE_TEXT
    assert sent == []


def test_invalid_email_reasks(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch)
    _complete_questionnaire(bot, 905)
    handle_max_update(_cb(905, lm.SEND), bot=bot)
    handle_max_update(_cb(905, lm.FMT_PDF), bot=bot)
    res = handle_max_update(_msg(905, "не помню"), bot=bot)
    assert res.action == "checklist_email_invalid"
    assert get_intake_store().get_active("905").lm_step == "email"


def test_send_failure_falls_back_to_chat(tmp_path: Path, monkeypatch) -> None:
    bot = _prepare(tmp_path, monkeypatch, ok=False)
    _complete_questionnaire(bot, 906)
    handle_max_update(_cb(906, lm.SEND), bot=bot)
    handle_max_update(_cb(906, lm.FMT_PDF), bot=bot)
    res = handle_max_update(_msg(906, "a@b.ru"), bot=bot)
    assert res.action == "checklist_email_failed"
    assert "чек-лист" in bot.sent[-1][1].lower()


def test_send_limit(tmp_path: Path, monkeypatch) -> None:
    sent: list[dict] = []
    bot = _prepare(tmp_path, monkeypatch, sent)
    _complete_questionnaire(bot, 907)
    rec = get_intake_store().get_active("907")
    assert rec is not None
    rec.lm_send_count = lm.MAX_SENDS
    get_intake_store().save(rec)
    handle_max_update(_cb(907, lm.SEND), bot=bot)
    handle_max_update(_cb(907, lm.FMT_PDF), bot=bot)
    res = handle_max_update(_msg(907, "a@b.ru"), bot=bot)
    assert res.action == "checklist_email_limit"
    assert sent == []
