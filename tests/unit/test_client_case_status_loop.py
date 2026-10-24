"""Зацикливание после приёма документов: статус ↔ ответ бота (без E/F)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import diag_choice as dc
from sfrfr.integrations.max import document_background as bg
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import get_intake_store
from sfrfr.services import client_case_status as ccs

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

_KIT_DOCS = [
    {"id": "d1", "doc_type": "ils", "filename": "ils.pdf", "ingest_status": "ready"},
    {
        "id": "d2",
        "doc_type": "workbook",
        "filename": "tk.pdf",
        "ingest_status": "ready",
    },
]


def _enable_q(monkeypatch) -> None:
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    get_settings.cache_clear()


def _complete_questionnaire(bot, user_id: int, monkeypatch) -> None:
    monkeypatch.setattr(q, "save_questionnaire", lambda **_kw: True)
    handle_max_update(
        {
            "callback": {
                "user": {"user_id": user_id, "first_name": "Иван", "last_name": "И."},
                "chat_id": 1,
                "payload": "start_dialog",
            }
        },
        bot=bot,
    )
    for upd in (
        _cb(user_id, "q:exp:gt20"),
        _msg(user_id, "+7 909 195-04-08"),
        _cb(user_id, q.SKIP_EMAIL),
        _msg(user_id, "Не учли стаж"),
    ):
        handle_max_update(upd, bot=bot)


def _patch_kit(monkeypatch, *, quiet: bool = False, docs=None, staff: bool = False):
    docs = docs if docs is not None else list(_KIT_DOCS)
    monkeypatch.setattr(
        ccs,
        "resolve_for_case",
        lambda case_id, **kw: ccs.resolve(
            documents=docs,
            case_quiet=quiet,
            staff_active=staff,
            ef_open=False,
            ingest_pending=False,
        ),
    )
    monkeypatch.setattr(bg, "is_case_quiet", lambda _cid: quiet)


# --- unit: resolve / reply / intent ---


def test_resolve_kit_ready_when_ef_closed() -> None:
    st = ccs.resolve(documents=_KIT_DOCS, ef_open=False, ingest_pending=False)
    assert st.kind == "kit_ready_no_analysis"
    text = ccs.reply_text(st, intent="working_question")
    low = text.lower()
    assert "не запущ" in low or "ещё не" in low
    assert "выполняется" not in low
    assert "ещё идёт" not in low
    assert "диагностика идёт" not in low
    assert "пришлите" not in low or "повторно" in low


def test_kit_ready_base_reply_honest_not_running() -> None:
    """Комплект есть, анализ не запущен — не врать что проверка уже идёт."""
    st = ccs.resolve(documents=_KIT_DOCS, ef_open=False, ingest_pending=False)
    assert st.kind == "kit_ready_no_analysis"
    for intent in ("other", "thanks", "working_question"):
        low = ccs.reply_text(st, intent=intent).lower()  # type: ignore[arg-type]
        assert "выполняется" not in low
        assert "ещё идёт" not in low
        assert "сейчас выполняется" not in low
        assert "повторно" in low


@pytest.mark.parametrize(
    ("document_check", "kind", "must_include", "must_exclude"),
    [
        (
            None,
            "receiving",
            ("ещё не запущена", "повторно"),
            ("выполняется", "ожидает запуска", "ещё идёт", "придёт в этот чат"),
        ),
        (
            {"status": "queued"},
            "receiving",
            ("ожидает запуска", "повторно"),
            ("выполняется", "ещё не запущена", "ещё идёт", "придёт в этот чат"),
        ),
        (
            {"status": "running"},
            "receiving",
            ("выполняется", "повторно"),
            ("ещё не запущена", "ожидает запуска", "ещё идёт", "придёт в этот чат"),
        ),
        (
            {"status": "failed", "last_error": "таймаут OCR"},
            "receiving",
            ("не удалось завершить", "повторно", "напишите в этот чат"),
            (
                "ещё не запущена",
                "выполняется",
                "ожидает запуска",
                "таймаут",
                "ocr",
                "специалист разберётся",
            ),
        ),
        (
            {"status": "failed", "last_error": ""},
            "receiving",
            ("не удалось завершить", "повторно"),
            ("ещё не запущена", "выполняется", "специалист разберётся"),
        ),
        (
            {"status": "failed"},
            "receiving",
            ("не удалось завершить", "повторно"),
            ("ещё не запущена", "выполняется", "специалист разберётся"),
        ),
        (
            {"status": "completed"},
            "receiving",
            ("уже выполнена", "повторно"),
            ("ещё не запущена", "выполняется", "ожидает запуска"),
        ),
        (
            {"status": "needs_action"},
            "receiving",
            ("требуется действие", "повторно"),
            ("ещё не запущена", "выполняется", "ожидает запуска"),
        ),
        (
            {"status": "weird_future_status"},
            "receiving",
            ("уточняем", "повторно"),
            ("ещё не запущена", "выполняется", "ожидает запуска", "ещё идёт"),
        ),
    ],
)
def test_quiet_kit_resolve_reply_by_check_status(
    document_check: dict | None,
    kind: str,
    must_include: tuple[str, ...],
    must_exclude: tuple[str, ...],
) -> None:
    """SFRFR-83: quiet + полный комплект — полный путь resolve → reply_text."""
    st = ccs.resolve(
        documents=_KIT_DOCS,
        case_quiet=True,
        ef_open=False,
        ingest_pending=False,
        document_check=document_check,
    )
    assert st.kind == kind
    assert "ils" in st.have_buckets and "labor" in st.have_buckets
    if document_check and document_check.get("status"):
        assert st.check_status == str(document_check["status"]).lower()
    low = ccs.reply_text(st, intent="working_question").lower()
    for needle in must_include:
        assert needle in low, f"missing {needle!r} in {low!r}"
    for needle in must_exclude:
        assert needle not in low, f"unexpected {needle!r} in {low!r}"


def test_failed_without_quiet_becomes_error_not_receiving() -> None:
    """Без quiet failed перехватывается до kit_ready / receiving."""
    st = ccs.resolve(
        documents=_KIT_DOCS,
        case_quiet=False,
        ef_open=False,
        ingest_pending=False,
        document_check={"status": "failed", "last_error": "x"},
    )
    assert st.kind == "error"
    low = ccs.reply_text(st, intent="working_question").lower()
    assert "ещё не запущена" not in low


def test_quiet_kit_failed_hides_internal_last_error() -> None:
    """Клиенту — безопасный текст; сырой last_error и маркеры секрета не светятся."""
    poison = (
        "SECRET_TOKEN=abc123; phone=+79001234567; "
        "https://internal.example/ops/job?id=9"
    )
    st = ccs.resolve(
        documents=_KIT_DOCS,
        case_quiet=True,
        ef_open=False,
        ingest_pending=False,
        document_check={"status": "failed", "last_error": poison},
    )
    assert st.kind == "receiving"
    assert st.last_error == poison  # в статусе для диагностики остаётся
    text = ccs.reply_text(st, intent="working_question")
    low = text.lower()
    assert "не удалось завершить" in low
    assert "повторно присылать те же файлы сейчас не нужно" in low
    assert "напишите в этот чат" in low
    assert "специалист разберётся" not in low
    assert "напишет сюда" not in low
    for marker in (
        "secret_token",
        "abc123",
        "+79001234567",
        "internal.example",
        "ops/job",
    ):
        assert marker not in low


def test_queued_without_quiet_becomes_checking() -> None:
    """Без quiet queued/running → kind=checking (не quiet-ветка receiving)."""
    st = ccs.resolve(
        documents=_KIT_DOCS,
        case_quiet=False,
        ef_open=False,
        ingest_pending=False,
        document_check={"status": "queued"},
    )
    assert st.kind == "checking"
    assert st.check_status == "queued"
    low = ccs.reply_text(st, intent="working_question").lower()
    assert "ожидает запуска" in low
    assert "выполняется" not in low
    assert "придёт в этот чат" not in low


def test_completed_with_result_beats_quiet() -> None:
    """result_ready перехватывается до quiet receiving."""
    st = ccs.resolve(
        documents=_KIT_DOCS,
        case_quiet=True,
        ef_open=False,
        ingest_pending=False,
        document_check={
            "status": "completed",
            "stale": False,
            "result": {"ok": True},
        },
        result_summary="Предварительная проверка комплекта завершена.",
        result_current=True,
    )
    assert st.kind == "result_ready"
    low = ccs.reply_text(st, intent="working_question").lower()
    assert "ещё не запущена" not in low


def test_resolve_receiving_during_quiet() -> None:
    st = ccs.resolve(documents=_KIT_DOCS, case_quiet=True, ef_open=False)
    assert st.kind == "receiving"
    text = ccs.reply_text(st)
    assert "обрабатываем" in text.lower()
    assert "повторно" in text.lower()


def test_result_ready_beats_quiet_for_thanks() -> None:
    """После brief «Спасибо» / working_question — итог, не «обрабатываем»."""
    st = ccs.resolve(
        documents=_KIT_DOCS,
        case_quiet=True,
        ef_open=False,
        result_summary="Предварительная проверка комплекта завершена.",
        result_current=True,
        document_check={
            "status": "completed",
            "stale": False,
            "result": {"next_action": "ok"},
        },
    )
    assert st.kind == "result_ready"
    thanks = ccs.reply_text(st, intent="thanks").lower()
    work = ccs.reply_text(st, intent="working_question").lower()
    assert "обрабатываем" not in thanks
    assert "пожалуйста" in thanks
    assert "обрабатываем" not in work
    assert "проверк" in work or "завершен" in work


def test_working_question_quiet_kit_not_processing_template() -> None:
    """Quiet+полный комплект: kind receiving ок, но working_question ≠ «обрабатываем»."""
    st = ccs.resolve(
        documents=_KIT_DOCS,
        case_quiet=True,
        ef_open=False,
        ingest_pending=False,
    )
    assert st.kind == "receiving"
    work = ccs.reply_text(st, intent="working_question").lower()
    assert "обрабатываем" not in work
    assert "в деле" in work or "проверк" in work
    # Обычный other по-прежнему может сказать про обработку пачки.
    other = ccs.reply_text(st, intent="other").lower()
    assert "обрабатываем" in other


def test_resolve_missing_names_concrete_doc() -> None:
    docs = [{"id": "d1", "doc_type": "ils", "ingest_status": "ready"}]
    st = ccs.resolve(documents=docs, ef_open=False, ingest_pending=False)
    assert st.kind == "missing"
    assert "labor" in st.missing_buckets
    text = ccs.reply_text(st)
    assert "трудов" in text.lower()
    assert "илс" in text.lower() or "стаже" in text.lower() or "стаж" in text.lower()


def test_resolve_error_not_analysis_running() -> None:
    st = ccs.resolve(
        documents=_KIT_DOCS,
        document_check={"status": "failed", "last_error": "ocr timeout"},
        ef_open=False,
        ingest_pending=False,
    )
    assert st.kind == "error"
    text = ccs.reply_text(st)
    low = text.lower()
    assert "идёт" not in low or "задержк" in low
    assert "ocr timeout" in low or "задержк" in low
    assert "проверк" not in low or "задержк" in low


def test_resolve_checking_only_when_job_runs() -> None:
    st = ccs.resolve(
        documents=_KIT_DOCS,
        document_check={"status": "running"},
        ef_open=False,
        ingest_pending=False,
    )
    assert st.kind == "checking"
    low = ccs.reply_text(st).lower()
    assert "выполняется" in low
    assert "ожидает запуска" not in low
    assert "придёт в этот чат" not in low


def test_intent_classifiers() -> None:
    assert ccs.classify_user_intent("Спасибо") == "thanks"
    # Спряжения «работать» (работаете / работаешь / …), не только существительное.
    assert ccs.classify_user_intent("Вы ещё работаете?") == "working_question"
    assert ccs.classify_user_intent("вы работаете?") == "working_question"
    assert ccs.classify_user_intent("ещё работаете?") == "working_question"
    assert ccs.classify_user_intent("Вы ещё работаешь?") == "working_question"
    assert (
        ccs.classify_user_intent("В 1998–2001 работал на заводе Север")
        == "clarification"
    )


def test_build_final_message_honest_kit_ready() -> None:
    text, complete = bg.build_final_message(_KIT_DOCS)
    assert complete is True
    assert "базовый комплект" in text.lower()
    assert "кратк" in text.lower() or "предварительн" in text.lower()
    assert "3 000" not in text
    assert "можно идти дальше к подготовке" not in text.lower()


# --- integration через handler ---


def test_working_question_after_kit_no_docs_ask(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable_q(monkeypatch)
    _complete_questionnaire(bot, 3101, monkeypatch)
    rec = get_intake_store().get_active("3101")
    assert rec is not None
    rec.case_id = CASE_ID
    answers = dict(rec.q_answers or {})
    answers["_docs_seen"] = "1"
    rec.q_answers = answers
    get_intake_store().save(rec)
    _patch_kit(monkeypatch)
    bot.sent.clear()
    res = handle_max_update(_msg(3101, "Вы ещё работаете?"), bot=bot)
    assert res.action == "case_status_reply"
    reply = (res.reply or "").lower()
    assert "пришлите фото" not in reply
    assert "пришлите документы" not in reply
    assert "проверк" in reply or "в деле" in reply or "результат" in reply
    get_settings.cache_clear()


def test_thanks_after_upload(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable_q(monkeypatch)
    _complete_questionnaire(bot, 3102, monkeypatch)
    rec = get_intake_store().get_active("3102")
    assert rec is not None
    rec.case_id = CASE_ID
    get_intake_store().save(rec)
    _patch_kit(monkeypatch)
    bot.sent.clear()
    res = handle_max_update(_msg(3102, "Спасибо"), bot=bot)
    assert res.action == "case_status_reply"
    assert "пожалуйста" in (res.reply or "").lower()
    get_settings.cache_clear()


def test_clarification_saved(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable_q(monkeypatch)
    _complete_questionnaire(bot, 3103, monkeypatch)
    rec = get_intake_store().get_active("3103")
    assert rec is not None
    rec.case_id = CASE_ID
    get_intake_store().save(rec)
    _patch_kit(monkeypatch)
    logged: list[str] = []
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._append_client_case_message",
        lambda **kw: logged.append(str(kw.get("text") or "")) or MagicMock(),
    )
    bot.sent.clear()
    note = "В 1998–2001 работал на заводе, стаж не учли"
    res = handle_max_update(_msg(3103, note), bot=bot)
    assert res.action == "case_status_reply"
    assert any(note in t for t in logged)
    assert "пояснение сохранили" in (res.reply or "").lower()
    get_settings.cache_clear()


def test_receiving_while_quiet(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable_q(monkeypatch)
    _complete_questionnaire(bot, 3104, monkeypatch)
    rec = get_intake_store().get_active("3104")
    assert rec is not None
    rec.case_id = CASE_ID
    get_intake_store().save(rec)
    _patch_kit(monkeypatch, quiet=True)
    bot.sent.clear()
    res = handle_max_update(_msg(3104, "пачка ещё идёт?"), bot=bot)
    assert res.action == "case_status_reply"
    # other/quiet: шаблон receiving ок; working_question — см. unit выше.
    assert "обрабатываем" in (res.reply or "").lower()
    bot.sent.clear()
    res2 = handle_max_update(_msg(3104, "Вы ещё работаете?"), bot=bot)
    assert res2.action == "case_status_reply"
    assert "обрабатываем" not in (res2.reply or "").lower()
    get_settings.cache_clear()


def test_working_question_while_diag_offer_pending_no_receiving(
    tmp_path: Path, monkeypatch
) -> None:
    """Пока висит оффер 3000 — не слать «обрабатываем» на «Вы ещё работаете?»."""
    from sfrfr.integrations.max import diag_choice as dc

    bot = _setup(tmp_path, monkeypatch)
    _enable_q(monkeypatch)
    _complete_questionnaire(bot, 3108, monkeypatch)
    rec = get_intake_store().get_active("3108")
    assert rec is not None
    rec.case_id = CASE_ID
    get_intake_store().save(rec)
    dc.mark_pending(rec)
    _patch_kit(monkeypatch, quiet=True)
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )
    bot.sent.clear()
    res = handle_max_update(_msg(3108, "Вы ещё работаете?"), bot=bot)
    assert res.action == "case_status_reply"
    low = (res.reply or "").lower()
    assert "обрабатываем" not in low
    assert "оформить" in low or "диагност" in low or "3000" in low or "3 000" in low
    get_settings.cache_clear()


def test_old_diag_yes_with_kit_no_blind_docs_ask(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable_q(monkeypatch)
    _complete_questionnaire(bot, 3105, monkeypatch)
    rec = get_intake_store().get_active("3105")
    assert rec is not None
    rec.case_id = CASE_ID
    get_intake_store().save(rec)
    _patch_kit(monkeypatch)
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    bot.sent.clear()
    res = handle_max_update(_cb(3105, dc.YES), bot=bot)
    assert res.action == "diag_yes_gated"
    assert started == []
    reply = (res.reply or "").lower()
    assert "пришлите документы в этот чат — разберёмся" not in reply
    assert "комплект" in reply or "документы" in reply or "не предлагаем" in reply
    get_settings.cache_clear()


def test_no_task_kit_ready_kind() -> None:
    st = ccs.resolve(
        documents=_KIT_DOCS,
        document_check=None,
        ef_open=False,
        ingest_pending=False,
    )
    assert st.kind == "kit_ready_no_analysis"


def test_new_file_while_quiet_stays_receiving() -> None:
    pending = [
        {"id": "d1", "doc_type": "ils", "ingest_status": "ready"},
        {"id": "d3", "doc_type": "other", "ingest_status": "uploading"},
    ]
    st = ccs.resolve(documents=pending, case_quiet=True, ef_open=False)
    assert st.kind == "receiving"


def test_duplicate_webhook_event_id(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.find_message_by_external_id",
        lambda eid: {"id": "m1", "case_id": CASE_ID, "external_id": eid}
        if eid
        else None,
    )
    upd = _msg(3201, "повтор")
    upd["message"]["mid"] = "ext-same-1"
    saves: list[str] = []
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._append_client_case_message",
        lambda **kw: saves.append(str(kw.get("text") or "")),
    )
    res1 = handle_max_update(upd, bot=bot)
    res2 = handle_max_update(upd, bot=bot)
    assert res1.action == "duplicate_webhook"
    assert res2.action == "duplicate_webhook"
    assert saves == []
    get_settings.cache_clear()


def test_staff_active_does_not_hijack(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable_q(monkeypatch)
    _complete_questionnaire(bot, 3106, monkeypatch)
    rec = get_intake_store().get_active("3106")
    assert rec is not None
    rec.case_id = CASE_ID
    get_intake_store().save(rec)
    _patch_kit(monkeypatch, staff=True)
    monkeypatch.setattr(
        "sfrfr.integrations.max.llm_chat.reply_to_free_text",
        lambda **_kw: ("", [], "max_llm_staff_silent"),
    )
    bot.sent.clear()
    res = handle_max_update(_msg(3106, "вопрос специалисту"), bot=bot)
    # staff_active → пустой/тихий путь, не case_status_reply с «пришлите»
    assert res.action in {"max_llm_staff_silent", "case_status_reply", "free_text_nudge"}
    if res.reply:
        assert "пришлите фото" not in res.reply.lower()
    get_settings.cache_clear()
