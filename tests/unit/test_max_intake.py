"""Приёмка ключевых сценариев ТЗ-20: диагностика MAX без дела на /start."""

from __future__ import annotations

from pathlib import Path

from sfrfr.core.case_store import get_case_store, reset_case_store
from sfrfr.core.config import get_settings
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import (
    FALLBACK_MENU_TEXT,
    WELCOME_TEXT,
    format_welcome_text,
    get_intake_store,
    reset_intake_store,
)


class _SilentBot:
    def __init__(self) -> None:
        self.sent: list[tuple[object, str]] = []
        self.attachments: list[object] = []

    @property
    def available(self) -> bool:
        return True

    def send_message(self, *, text: str, user_id=None, chat_id=None, attachments=None):  # noqa: ANN001
        self.sent.append((user_id or chat_id, text))
        self.attachments.append(attachments)
        return {"ok": True}


def _cb(user_id: int, payload: str, chat_id: int = 1) -> dict:
    return {
        "callback": {
            "user": {"user_id": user_id},
            "chat_id": chat_id,
            "payload": payload,
        }
    }


def _msg(user_id: int, text: str, chat_id: int = 1) -> dict:
    return {
        "message": {
            "sender": {"user_id": user_id},
            "recipient": {"chat_id": chat_id, "chat_type": "dialog"},
            "body": {"text": text},
        }
    }


def _setup(tmp_path: Path, monkeypatch) -> _SilentBot:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")
    reset_intake_store(tmp_path / "max_intake.json")
    return _SilentBot()


def test_start_shows_menu_without_case(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)

    result = handle_max_update(_msg(7, "/start"), bot=bot)
    assert result.action == "max_intake_started"
    assert result.case_id is None
    assert result.reply == WELCOME_TEXT
    assert get_case_store().find_by_max_user("7") is None
    get_settings.cache_clear()


def test_repeat_start_keeps_started_intake(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)

    handle_max_update(_msg(8, "/start"), bot=bot)
    handle_max_update(_cb(8, "intake:whom:relative"), bot=bot)
    first = get_intake_store().get_active("8")
    assert first is not None and first.for_whom == "relative"
    intake_id = first.id

    handle_max_update(_msg(8, "/start"), bot=bot)
    again = get_intake_store().get_active("8")
    assert again is not None
    assert again.id == intake_id
    assert again.for_whom == "relative"
    get_settings.cache_clear()


def test_intake_completes_one_case_and_deeplink(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://proverkastaza.ru/app/")
    get_settings.cache_clear()

    handle_max_update(_msg(9, "/start"), bot=bot)
    for payload in (
        "intake:whom:self",
        "intake:pension:before",
        "intake:problem:ils_stazh",
        "intake:ils:need",
        "intake:device:max",
    ):
        result = handle_max_update(_cb(9, payload), bot=bot)

    assert result.action == "max_intake_completed"
    assert result.case_id
    case_id = result.case_id
    # повторное завершение через /cabinet не плодит дела
    again = handle_max_update(_msg(9, "/cabinet"), bot=bot)
    assert again.case_id == case_id
    assert len(get_case_store()._cases) == 1  # noqa: SLF001

    last_att = bot.attachments[-1]
    assert last_att
    blob = str(last_att)
    assert case_id in blob
    get_settings.cache_clear()


def test_legacy_goal_path_still_works(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(19, "/start"), bot=bot)
    for payload in (
        "intake:goal:check_experience",
        "intake:ils:no",
        "intake:emp:no",
        "intake:device:max",
    ):
        result = handle_max_update(_cb(19, payload), bot=bot)
    assert result.action == "max_intake_completed"
    get_settings.cache_clear()


def test_operator_branch(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    calls: list[dict] = []

    def _fake_sync(**kwargs):  # noqa: ANN003
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "sfrfr.integrations.amocrm.sync_case_to_amocrm",
        _fake_sync,
    )

    handle_max_update(_msg(11, "/start"), bot=bot)
    result = handle_max_update(_cb(11, "intake:goal:operator"), bot=bot)
    assert result.action == "max_operator_requested"
    assert result.case_id
    assert any("специалисту" in t for _, t in bot.sent)
    assert calls and calls[0].get("task") == "Продолжить диалог MAX"
    get_settings.cache_clear()


def test_upload_blocked_in_production(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    handle_max_update(_msg(12, "/start"), bot=bot)
    for payload in (
        "intake:goal:check_experience",
        "intake:ils:yes",
        "intake:emp:yes",
        "intake:device:web",
    ):
        handle_max_update(_cb(12, payload), bot=bot)

    blocked = handle_max_update(
        {
            "message": {
                "sender": {"user_id": 12},
                "recipient": {"chat_id": 1},
                "body": {"text": ""},
            },
            "file_name": "scan.pdf",
            "file_bytes": b"%PDF",
        },
        bot=bot,
    )
    assert blocked.action == "upload_blocked"
    assert blocked.ok is False
    assert bot.attachments[-1]
    get_settings.cache_clear()


def test_bot_started_shows_welcome_with_name(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    result = handle_max_update(
        {
            "update_type": "bot_started",
            "chat_id": 42,
            "user": {"user_id": 21, "first_name": "Ирина"},
        },
        bot=bot,
    )
    assert result.action == "max_intake_started"
    assert result.case_id is None
    assert result.reply == format_welcome_text(display_name="Ирина")
    assert "Здравствуйте, Ирина!" in (result.reply or "")
    assert "Я бот сервиса" in (result.reply or "")
    assert "Выберите пункт меню ниже" not in (result.reply or "")
    get_settings.cache_clear()


def test_early_free_text_shows_welcome_not_dry_ack(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    # Есть дело (как после лида с сайта), но диагностика ещё не начата.
    case = get_case_store().create(client_name="Тест", snils_masked="***")
    get_case_store().bind_max(case.case_id, max_user_id="22")
    result = handle_max_update(
        _msg(22, "Здравствуйте. Тестовая заявка с сайта, проверяю связь."),
        bot=bot,
    )
    assert result.action == "max_intake_started"
    assert "Здравствуйте!" in (result.reply or "")
    assert "Я бот сервиса" in (result.reply or "")
    assert result.reply != FALLBACK_MENU_TEXT
    assert "Выберите пункт меню ниже" not in (result.reply or "")
    get_settings.cache_clear()


def test_format_welcome_text_skips_max_placeholder() -> None:
    assert format_welcome_text(display_name="Max 12345") == WELCOME_TEXT
    assert format_welcome_text(display_name="Анна") != WELCOME_TEXT
