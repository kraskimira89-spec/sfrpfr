"""Приёмка ключевых сценариев ТЗ-20: диагностика MAX; дело с /start для ленты чата."""

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
        self.typing: list[tuple[object, str]] = []

    @property
    def available(self) -> bool:
        return True

    def send_message(  # noqa: ANN001
        self,
        *,
        text: str,
        user_id=None,
        chat_id=None,
        attachments=None,
        text_format=None,
    ):
        self.sent.append((user_id or chat_id, text))
        self.attachments.append(attachments)
        return {"ok": True}

    def send_chat_action(self, *, chat_id, action="typing_on"):  # noqa: ANN001
        self.typing.append((chat_id, action))
        return {"ok": True}

    def answer_callback(self, callback_id: str, **kwargs):  # noqa: ANN003
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
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "0")
    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")
    reset_intake_store(tmp_path / "max_intake.json")
    return _SilentBot()


def test_start_shows_menu_and_creates_case(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)

    result = handle_max_update(_msg(7, "/start"), bot=bot)
    assert result.action == "max_intake_started"
    assert result.case_id
    assert result.reply == WELCOME_TEXT
    assert get_case_store().find_by_max_user("7") is not None
    intake = get_intake_store().get_active("7")
    assert intake is not None and intake.case_id == result.case_id
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
    monkeypatch.setenv("CABINET_PUBLIC_URL", "https://cabinet.proverkastaza.ru")
    get_settings.cache_clear()

    handle_max_update(_msg(9, "/start"), bot=bot)
    for payload in (
        "intake:whom:self",
        "intake:pension:before",
        "intake:problem:ils_stazh",
        "intake:ils:need",
        "intake:ils_guide:done",
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
    assert "cabinet.proverkastaza.ru" in blob
    assert "Кабинет на сайте" in blob
    assert "В MAX — кабинет" not in blob
    assert "/app/" not in blob
    get_settings.cache_clear()


def test_summary_and_upload_keyboards_website_only() -> None:
    from sfrfr.integrations.max.intake import (
        OPEN_CABINET_LABEL,
        SUMMARY_TEXT,
        UPLOAD_BLOCKED_TEXT,
        cabinet_url_for_case,
        summary_keyboard,
        upload_blocked_keyboard,
    )

    url = cabinet_url_for_case("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert url.startswith("https://cabinet.proverkastaza.ru")
    assert "/app/" not in url
    sk = summary_keyboard(device="max", cabinet_url=url)
    uk = upload_blocked_keyboard(cabinet_url=url)
    for kb in (sk, uk):
        labels = [btn["text"] for row in kb[0]["payload"]["buttons"] for btn in row]
        assert OPEN_CABINET_LABEL in labels
        assert "В MAX — кабинет" not in labels
        assert "В браузере — кабинет" not in labels
        links = [btn["url"] for row in kb[0]["payload"]["buttons"] for btn in row if btn.get("url")]
        assert links and all("cabinet." in u or "proverkastaza.ru" in u for u in links)
        assert all("/app/" not in u for u in links)
    assert "сайте" in SUMMARY_TEXT.lower()
    assert "сайте" in UPLOAD_BLOCKED_TEXT.lower()
    assert "этот чат" in SUMMARY_TEXT.lower() or "сюда" in SUMMARY_TEXT.lower()
    assert "этот чат" in UPLOAD_BLOCKED_TEXT.lower()
    assert "кабинет в max" not in SUMMARY_TEXT.lower()


def test_docs_info_text_lists_besides_ils_and_chat_upload() -> None:
    from sfrfr.integrations.max.intake import DOCS_INFO_TEXT, DOCS_STAZH_TEXT, WELCOME_TEXT

    low = DOCS_INFO_TEXT.lower()
    assert "кроме" in low and "илс" in low
    assert "этот чат" in low
    assert "трудов" in low
    assert "электронн" in low
    assert "справка о размере пенсии" in low
    assert "выплатах сфр" in low or "выплат сфр" in low
    assert "банковск" in low
    assert "12" in DOCS_INFO_TEXT or "12 месяц" in low
    assert "начислил" in low or "пришло" in low or "получаем" in low or "начисленн" in low
    assert "опек" in low or "дет" in low
    assert "льготн" in low or "северн" in low
    assert "перерасчёт" not in low
    assert "этот чат" in WELCOME_TEXT.lower()
    assert "скан" in DOCS_STAZH_TEXT.lower() or "электронн" in DOCS_STAZH_TEXT.lower()
    assert "этот чат" in DOCS_STAZH_TEXT.lower()


def test_legacy_goal_path_still_works(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(19, "/start"), bot=bot)
    for payload in (
        "intake:goal:check_experience",
        "intake:ils:no",
        "intake:ils_guide:done",
        "intake:emp:no",
        "intake:emp_guide:done",
        "intake:device:max",
    ):
        result = handle_max_update(_cb(19, payload), bot=bot)
    assert result.action == "max_intake_completed"
    get_settings.cache_clear()


def test_operator_branch(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    calls: list[dict] = []

    def _fake_push(case, *, task=None):  # noqa: ANN001, ANN202
        calls.append({"case": case, "task": task})
        return {"ok": True, "lead_id": "999"}

    class _FakeSb:
        def table(self, _name):  # noqa: ANN001
            return self

        def select(self, _cols):  # noqa: ANN001
            return self

        def eq(self, _col, _val):  # noqa: ANN001
            return self

        def limit(self, _n):  # noqa: ANN001
            return self

        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": "case-1",
                            "b2c_status": "lead",
                            "pipeline_status": "intake",
                            "crm_external_id": None,
                            "clients": {
                                "full_name": "MAX 11",
                                "preferred_channel": "max_chat",
                                "max_user_id": "11",
                            },
                        }
                    ]
                },
            )()

    monkeypatch.setattr(
        "sfrfr.integrations.amocrm.sync.push_case_to_amocrm",
        _fake_push,
    )
    monkeypatch.setattr(
        "sfrfr.db.session.get_supabase_client",
        lambda: _FakeSb(),
    )
    monkeypatch.setattr(
        "sfrfr.integrations.amocrm.sync.persist_crm_external_id",
        lambda *_a, **_k: None,
    )

    handle_max_update(_msg(11, "/start"), bot=bot)
    result = handle_max_update(_cb(11, "intake:goal:operator"), bot=bot)
    assert result.action == "max_operator_requested"
    assert result.case_id
    assert any("специалисту" in t for _, t in bot.sent)
    assert calls and calls[0].get("task") == "max_operator"
    get_settings.cache_clear()


def test_upload_accepted_in_production(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_staff_chat_docs",
        lambda **_k: None,
    )

    handle_max_update(_msg(12, "/start"), bot=bot)
    for payload in (
        "intake:goal:check_experience",
        "intake:ils:yes",
        "intake:emp:yes",
        "intake:device:web",
    ):
        handle_max_update(_cb(12, payload), bot=bot)

    accepted = handle_max_update(
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
    assert accepted.action == "upload"
    assert accepted.ok is True
    assert "приняли" in (accepted.reply or "").lower() or "принят" in (accepted.reply or "").lower()
    assert "кабинет" in (accepted.reply or "").lower()
    assert bot.attachments[-1]
    get_settings.cache_clear()


def test_summary_keyboard_single_web_cabinet() -> None:
    from sfrfr.integrations.max.intake import OPEN_CABINET_LABEL, summary_keyboard

    kb = summary_keyboard(device="max", cabinet_url="https://cabinet.example/?case=1")
    blob = str(kb)
    assert OPEN_CABINET_LABEL in blob
    assert "В MAX — кабинет" not in blob
    assert blob.count("https://cabinet.example") == 1


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
    assert result.case_id
    assert result.reply == format_welcome_text(display_name="Ирина")
    assert "Здравствуйте, Ирина!" in (result.reply or "")
    assert "Я бот сервиса" in (result.reply or "")
    assert "Выберите пункт меню ниже" not in (result.reply or "")
    get_settings.cache_clear()


def test_early_free_text_shows_welcome_not_dry_ack(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "0")
    get_settings.cache_clear()
    # Есть дело (как после лида с сайта), но диагностика ещё не начата.
    case = get_case_store().create(client_name="Тест", snils_masked="***")
    get_case_store().bind_max(case.case_id, max_user_id="22")
    result = handle_max_update(
        _msg(22, "Здравствуйте. Тестовая заявка с сайта, проверяю связь."),
        bot=bot,
    )
    assert result.action == "free_text_nudge"
    assert "кнопками" in (result.reply or "").lower()
    assert "Позвать специалиста" in (result.reply or "")
    assert "Я бот сервиса" not in (result.reply or "")
    assert result.reply != FALLBACK_MENU_TEXT  # nudge = fallback + подсказка шага
    assert "Выберите пункт меню ниже" not in (result.reply or "")
    get_settings.cache_clear()


def test_free_text_after_start_nudges_without_full_welcome(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "0")
    get_settings.cache_clear()
    handle_max_update(_msg(23, "/start"), bot=bot)
    result = handle_max_update(_msg(23, "А можно просто спросить про стаж?"), bot=bot)
    assert result.action == "free_text_nudge"
    assert "кнопками" in (result.reply or "").lower()
    assert "Для кого проверка" in (result.reply or "")
    assert result.reply != WELCOME_TEXT
    get_settings.cache_clear()


def test_typing_on_before_callback_reply(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(24, "/start"), bot=bot)
    bot.typing.clear()
    handle_max_update(_cb(24, "intake:whom:self"), bot=bot)
    assert bot.typing
    assert bot.typing[-1] == (1, "typing_on")
    get_settings.cache_clear()


def test_format_welcome_text_skips_max_placeholder() -> None:
    assert format_welcome_text(display_name="Max 12345") == WELCOME_TEXT
    assert format_welcome_text(display_name="Анна") != WELCOME_TEXT


def test_docs_info_menu_and_special_section(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(31, "/start"), bot=bot)
    menu = handle_max_update(_cb(31, "intake:docs_info"), bot=bot)
    assert menu.action == "docs_info"
    reply = menu.reply or ""
    low = reply.lower()
    assert "кроме" in low and "илс" in low
    assert "этот чат" in low
    assert "трудов" in low

    special = handle_max_update(_cb(31, "intake:docs:special"), bot=bot)
    assert special.action == "docs_special"
    assert "свидетельства о рождении" in (special.reply or "").lower() or "количество детей" in (
        special.reply or ""
    ).lower()
    assert "опек" in (special.reply or "").lower()
    assert "банковск" in (special.reply or "").lower()
    assert "льготн" in (special.reply or "").lower() or "северн" in (special.reply or "").lower()
    assert "Справка о выплатах СФР" in (special.reply or "")
    assert "ИПК" in (special.reply or "")

    gos = handle_max_update(_cb(31, "intake:docs:gosuslugi"), bot=bot)
    assert gos.action == "docs_gosuslugi"
    assert "Выписка из лицевого счета в СФР" in (gos.reply or "")
    get_settings.cache_clear()


def test_ils_need_shows_gosuslugi_howto(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(30, "/start"), bot=bot)
    for payload in (
        "intake:whom:self",
        "intake:pension:before",
        "intake:problem:ils_stazh",
    ):
        handle_max_update(_cb(30, payload), bot=bot)

    howto = handle_max_update(_cb(30, "intake:ils:need"), bot=bot)
    assert howto.action == "ils_howto"
    assert "Госуслуг" in (howto.reply or "") or "Госуслугах" in (howto.reply or "")
    assert "Выписка из лицевого счета в СФР" in (howto.reply or "")
    assert bot.attachments[-1]

    mfc = handle_max_update(_cb(30, "intake:ils_guide:mfc"), bot=bot)
    assert mfc.action == "ils_howto"
    assert "МФЦ" in (mfc.reply or "")

    done = handle_max_update(_cb(30, "intake:ils_guide:done"), bot=bot)
    assert done.action == "intake_ils"
    assert done.reply == (
        "Как вам удобнее открыть кабинет на сайте — с телефона или с компьютера?"
    )
    get_settings.cache_clear()
