"""Имя из профиля MAX в анкете и напоминание о шаге после паузы."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import checklist_offer as lm
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max import return_reminder
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store


def _start(user_id: int, first: str | None = None, last: str | None = None) -> dict:
    user: dict = {"user_id": user_id}
    if first:
        user["first_name"] = first
    if last:
        user["last_name"] = last
    return {"callback": {"user": user, "chat_id": 1, "payload": "start_dialog"}}


def test_begin_prefills_valid_profile_names() -> None:
    rec = MaxIntakeRecord(id="r", max_user_id="u", max_first_name="мария", max_last_name="Иванова")
    q.begin(rec)
    assert rec.q_step == "middle_name"
    assert q.prefilled_name(rec.q_answers) == "Иванова Мария"


def test_begin_ignores_nickname() -> None:
    rec = MaxIntakeRecord(id="r", max_user_id="u", max_first_name="Masha_88")
    q.begin(rec)
    assert rec.q_step == "last_name"
    assert rec.q_answers == {}


def test_only_first_name_skips_it_after_last_name() -> None:
    rec = MaxIntakeRecord(id="r", max_user_id="u", max_first_name="Мария")
    q.begin(rec)
    assert rec.q_step == "last_name"
    assert q.apply_answer(rec, text="Иванова", payload="").accepted
    assert rec.q_step == "middle_name"


def test_fix_name_returns_to_last_name() -> None:
    rec = MaxIntakeRecord(id="r", max_user_id="u", max_first_name="Мария", max_last_name="Иванова")
    q.begin(rec)
    assert q.apply_answer(rec, text="", payload=q.FIX_NAME).accepted
    assert rec.q_step == "last_name"
    assert "first_name" not in rec.q_answers


def _enable(tmp_path: Path, monkeypatch):
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(q, "save_questionnaire", lambda **_kw: True)
    return bot


def test_start_uses_profile_name(tmp_path: Path, monkeypatch) -> None:
    bot = _enable(tmp_path, monkeypatch)
    handle_max_update(_start(961, first="Мария", last="Иванова"), bot=bot)
    texts = [t for _u, t in bot.sent]
    assert any("Из профиля MAX: Иванова Мария" in t for t in texts)
    assert texts[-1].startswith("3/8")
    assert "Исправить имя" in str(bot.attachments[-1])


def _age(user_id: str, hours: int) -> MaxIntakeRecord:
    rec = get_intake_store().get_active(user_id)
    assert rec is not None
    rec.last_seen_at = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    get_intake_store().save(rec)
    return rec


def test_return_mid_questionnaire_repeats_question_without_consuming(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _enable(tmp_path, monkeypatch)
    handle_max_update(_start(962), bot=bot)
    _age("962", 96)
    res = handle_max_update(_msg(962, "Здравствуйте"), bot=bot)
    assert res.action == "return_reminder"
    assert return_reminder.WELCOME_BACK in bot.sent[-1][1]
    rec = get_intake_store().get_active("962")
    assert rec is not None and rec.q_step == "last_name" and "last_name" not in rec.q_answers


def test_short_pause_no_reminder(tmp_path: Path, monkeypatch) -> None:
    bot = _enable(tmp_path, monkeypatch)
    handle_max_update(_start(963), bot=bot)
    _age("963", 2)
    res = handle_max_update(_msg(963, "Сидорова"), bot=bot)
    assert res.action == "max_questionnaire_step"


def test_return_after_questionnaire_single_reminder_reply(tmp_path: Path, monkeypatch) -> None:
    bot = _enable(tmp_path, monkeypatch)
    handle_max_update(_start(964), bot=bot)
    rec = _age("964", 80)
    rec.q_step = None
    rec.q_completed_at = datetime.now(UTC).isoformat()
    get_intake_store().save(rec)
    before = len(bot.sent)
    res = handle_max_update(_msg(964, "подскажите, что дальше"), bot=bot)
    assert res.action == "return_reminder"
    new = bot.sent[before:]
    assert len(new) == 1 and "Сейчас нужно прислать документы" in new[0][1]


def test_default_reminder_threshold_is_72_hours(tmp_path: Path, monkeypatch) -> None:
    bot = _enable(tmp_path, monkeypatch)
    monkeypatch.delenv("MAX_RETURN_REMINDER_HOURS", raising=False)
    get_settings.cache_clear()
    handle_max_update(_start(966), bot=bot)
    _age("966", 48)
    res = handle_max_update(_msg(966, "Сидорова"), bot=bot)
    assert res.action == "max_questionnaire_step"


def test_return_with_valid_email_sends_checklist(tmp_path: Path, monkeypatch) -> None:
    bot = _enable(tmp_path, monkeypatch)
    monkeypatch.setattr(lm, "send_checklist_email", lambda **_kw: True)
    handle_max_update(_start(965), bot=bot)
    rec = _age("965", 80)
    rec.q_step = None
    rec.lm_step = "email"
    get_intake_store().save(rec)
    res = handle_max_update(_msg(965, "a@b.ru"), bot=bot)
    assert res.action == "checklist_email_sent"
