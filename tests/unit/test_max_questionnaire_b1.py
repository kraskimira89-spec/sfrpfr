"""ТЗ-35 B1: анкета нового клиента в MAX (8 вопросов §6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+7 909 195-04-08", "+79091950408"),
        ("8 (909) 195 04 08", "+79091950408"),
        ("9091950408", "+79091950408"),
        ("12345", None),
        ("+1 202 555 0100", None),
    ],
)
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert q.normalize_phone(raw) == expected


def test_birth_year_bounds() -> None:
    assert q.parse_birth_year("1965") == 1965
    assert q.parse_birth_year("65") is None
    assert q.parse_birth_year("1899") is None
    assert q.parse_birth_year("2025") is None


def test_name_validation() -> None:
    assert q.clean_name("  анна-мария ") == "Анна-Мария"
    assert q.clean_name("Иванов2") is None
    assert q.clean_name("x" * 61) is None


def _rec() -> MaxIntakeRecord:
    return MaxIntakeRecord(id="r1", max_user_id="u1")


def test_full_walk_with_skips() -> None:
    rec = _rec()
    q.begin(rec)
    assert rec.q_step == "last_name"
    steps = [
        ("text", "Иванова"),
        ("text", "Мария"),
        ("cb", q.SKIP_MIDDLE_NAME),
        ("text", "1962"),
        ("cb", "q:exp:10_20"),
        ("text", "8 909 195 04 08"),
        ("cb", q.SKIP_EMAIL),
    ]
    for kind, value in steps:
        res = q.apply_answer(
            rec, text=value if kind == "text" else "", payload=value if kind == "cb" else ""
        )
        assert res.accepted, value
    res = q.apply_answer(rec, text="Не учли стаж в колхозе 1980-1985", payload="")
    assert res.done
    assert rec.q_step is None
    assert rec.q_answers == {
        "last_name": "Иванова",
        "first_name": "Мария",
        "middle_name": "",
        "birth_year": "1962",
        "experience": "10_20",
        "phone": "+79091950408",
        "email": "",
        "problem": "Не учли стаж в колхозе 1980-1985",
    }


def test_invalid_answer_keeps_step() -> None:
    rec = _rec()
    q.begin(rec)
    rec.q_step = "phone"
    res = q.apply_answer(rec, text="123", payload="")
    assert not res.accepted
    assert rec.q_step == "phone"
    assert res.error


def test_problem_too_long_rejected() -> None:
    rec = _rec()
    rec.q_step = "problem"
    res = q.apply_answer(rec, text="а" * 2001, payload="")
    assert not res.accepted
    assert "2000" in (res.error or "")


def test_summary_has_no_pension_promises() -> None:
    text = q.summary_text(
        {
            "last_name": "Иванова",
            "first_name": "Мария",
            "middle_name": "",
            "birth_year": "1962",
            "experience": "gt20",
            "phone": "+79091950408",
            "email": "",
            "problem": "Не учли стаж",
        }
    )
    assert "Иванова Мария" in text
    assert "более 20 лет" in text
    assert "перерасч" not in q.COMPLETED_TEXT.lower()


def _enable(monkeypatch) -> None:
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    get_settings.cache_clear()


def test_start_begins_questionnaire_for_new_client(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable(monkeypatch)
    result = handle_max_update(_cb(801, "start_dialog"), bot=bot)
    assert result.action == "max_questionnaire_started"
    assert any("Фамилия" in t for _u, t in bot.sent)
    assert not any("чек-лист" in (t or "").lower() for _u, t in bot.sent)
    rec = get_intake_store().get_active("801")
    assert rec is not None and rec.q_step == "last_name"
    get_settings.cache_clear()


def test_questionnaire_end_to_end(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable(monkeypatch)
    saved: dict = {}
    monkeypatch.setattr(q, "save_questionnaire", lambda **kw: saved.update(kw) or True)
    handle_max_update(_cb(802, "start_dialog"), bot=bot)
    for upd in (
        _msg(802, "Петров"),
        _msg(802, "Пётр"),
        _msg(802, "Петрович"),
        _msg(802, "1960"),
        _cb(802, "q:exp:gt20"),
        _msg(802, "+7 909 195-04-08"),
        _msg(802, "petrov@example.ru"),
    ):
        res = handle_max_update(upd, bot=bot)
        assert res.action == "max_questionnaire_step", res
    res = handle_max_update(_msg(802, "Не учли северный стаж"), bot=bot)
    assert res.action == "max_questionnaire_completed"
    assert saved["answers"]["email"] == "petrov@example.ru"
    assert q.COMPLETED_TEXT in [t for _u, t in bot.sent]
    menu = str(bot.attachments[-2])
    for label in (
        "Загрузить документы",
        "Какие документы нужны",
        "Статус моего дела",
        "Связаться со специалистом",
    ):
        assert label in menu
    rec = get_intake_store().get_active("802")
    assert rec is not None and rec.q_step is None and rec.q_completed_at
    get_settings.cache_clear()


def test_invalid_phone_reasks(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable(monkeypatch)
    handle_max_update(_cb(803, "start_dialog"), bot=bot)
    rec = get_intake_store().get_active("803")
    assert rec is not None
    rec.q_step = "phone"
    get_intake_store().save(rec)
    res = handle_max_update(_msg(803, "позвоните мне"), bot=bot)
    assert res.action == "max_questionnaire_invalid"
    assert get_intake_store().get_active("803").q_step == "phone"
    get_settings.cache_clear()


def test_file_during_questionnaire_accepted_and_question_repeated(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable(monkeypatch)
    handle_max_update(_cb(804, "start_dialog"), bot=bot)
    handle_max_update(_msg(804, "Сидорова"), bot=bot)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._collect_max_files",
        lambda _u: [("ils.pdf", b"%PDF-1.4")],
    )
    monkeypatch.setattr("sfrfr.integrations.max.handler._ingest_max_file", lambda **_kw: True)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._try_max_payment_receipt", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_staff_chat_docs", lambda **_kw: None
    )
    res = handle_max_update(_msg(804, ""), bot=bot)
    assert res.action == "upload"
    assert "Имя" in bot.sent[-1][1]
    assert get_intake_store().get_active("804").q_step == "first_name"
    get_settings.cache_clear()


def test_disabled_flag_keeps_old_welcome(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "0")
    get_settings.cache_clear()
    result = handle_max_update(_cb(805, "start_dialog"), bot=bot)
    assert result.action == "max_intake_started"
    get_settings.cache_clear()
