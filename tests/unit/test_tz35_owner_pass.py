"""Уточнение владельца к ТЗ-35: обязательные сценарии выпуска (без E/F)."""

from __future__ import annotations

from pathlib import Path

from test_max_intake import _cb, _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max import soft_offers, submission_nudge
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store
from sfrfr.services import diag_offer_gate as gate


def _enable(monkeypatch) -> None:
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    get_settings.cache_clear()


def _start(user_id: int) -> dict:
    return {
        "callback": {
            "user": {"user_id": user_id, "first_name": "Иван", "last_name": "Иванов"},
            "chat_id": 1,
            "payload": "start_dialog",
        }
    }


def test_all_four_question_numbers() -> None:
    for i, step in enumerate(q.STEPS, start=1):
        text, _kb = q.question(step)
        assert text.startswith(f"Вопрос {i} из 4.")


def test_resume_after_pause_keeps_actual_step(tmp_path: Path, monkeypatch) -> None:
    from sfrfr.integrations.max import return_reminder

    bot = _setup(tmp_path, monkeypatch)
    _enable(monkeypatch)
    handle_max_update(_start(1001), bot=bot)
    handle_max_update(_cb(1001, "q:exp:10_20"), bot=bot)
    rec = get_intake_store().get_active("1001")
    assert rec is not None and rec.q_step == "phone"
    # Пауза: last_seen далеко в прошлом
    from datetime import UTC, datetime, timedelta

    rec.last_seen_at = (datetime.now(UTC) - timedelta(hours=100)).isoformat()
    get_intake_store().save(rec)
    monkeypatch.setenv("MAX_RETURN_REMINDER_HOURS", "72")
    get_settings.cache_clear()
    sent: list[str] = []

    def _reply(msg, _kb):
        sent.append(msg)

    body, stop = return_reminder.remind(rec, _reply, text="привет", docs_count=0)
    assert stop
    assert "Вопрос 2 из 4" in body
    assert "телефон" in body.lower()
    get_settings.cache_clear()


def test_repeat_event_does_not_bump_question_number() -> None:
    rec = MaxIntakeRecord(id="r", max_user_id="u")
    q.begin(rec)
    assert rec.q_step == "experience"
    t1, _ = q.question(rec.q_step)
    res = q.apply_answer(rec, text="не кнопка", payload="")
    assert not res.accepted
    t2, _ = q.question(rec.q_step)
    assert t1.startswith("Вопрос 1 из 4.")
    assert t2.startswith("Вопрос 1 из 4.")


def test_file_without_consent_still_blocked(tmp_path: Path, monkeypatch) -> None:
    from sfrfr.integrations.max import document_background as bg

    bg.reset_quiet_state()
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent", lambda *_a, **_k: False
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._collect_max_files",
        lambda _u: ([("ils.pdf", b"%PDF-1.4")], []),
    )
    res = handle_max_update(_msg(1002, ""), bot=bot)
    assert res.action in {"pdn_consent_gate", "need_start", "upload_rejected"} or (
        res.ok is False or "соглас" in (res.reply or "").lower() or res.action != "upload"
    )
    get_settings.cache_clear()


def test_one_case_created_no_immediate_sale(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    _enable(monkeypatch)
    monkeypatch.setattr(q, "save_questionnaire", lambda **_kw: True)
    handle_max_update(_start(1003), bot=bot)
    for upd in (
        _cb(1003, "q:exp:gt20"),
        _msg(1003, "+7 909 195-04-08"),
        _cb(1003, q.SKIP_EMAIL),
        _msg(1003, "Не учли стаж"),
    ):
        handle_max_update(upd, bot=bot)
    done_msgs = [
        t
        for _u, t in bot.sent
        if "создано" in (t or "").lower() and "дело" in (t or "").lower()
    ]
    assert len(done_msgs) == 1
    assert "CASE-" in done_msgs[0] or "дело создано" in done_msgs[0].lower()
    assert not any("3 000" in (t or "") for _u, t in bot.sent)
    get_settings.cache_clear()


def test_submission_nudge_rhythm_every_12(tmp_path: Path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    store = get_intake_store()
    rec = store.upsert_started("n1")
    assert submission_nudge.next_interval(0) == 12
    assert submission_nudge.next_interval(1) == 12
    assert submission_nudge.next_interval(5) == 12
    # 11 — ещё рано
    for _ in range(11):
        submission_nudge.note_logical_bot_message(rec)
    _early, added_early = submission_nudge.maybe_append_disclaimer(rec, "Рано")
    assert added_early is False
    # 12-е → nudge
    submission_nudge.note_logical_bot_message(rec)
    text, added = submission_nudge.maybe_append_disclaimer(rec, "Ответ бота")
    assert added and submission_nudge.SHORT_DISCLAIMER in text
    assert rec.submission_nudge_tier == 1
    # ещё 12
    for _ in range(12):
        submission_nudge.note_logical_bot_message(rec)
    _text2, added2 = submission_nudge.maybe_append_disclaimer(rec, "Ещё ответ")
    assert added2 and rec.submission_nudge_tier == 2


def test_restart_keeps_nudge_counter(tmp_path: Path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    store = get_intake_store()
    path = store.path
    rec = store.upsert_started("2001")
    rec.logical_bot_msg_count = 10
    rec.submission_nudge_tier = 1
    rec.submission_nudge_at_count = 4
    store.save(rec)
    # Новый экземпляр хранилища после save — как после рестарта процесса.
    from sfrfr.integrations.max.intake import MaxIntakeStore, reset_intake_store

    reset_intake_store(path)
    reloaded = MaxIntakeStore(path)
    before = reloaded.get_active("2001")
    assert before is not None
    assert before.logical_bot_msg_count == 10
    fresh = reloaded.restart("2001")
    assert fresh.logical_bot_msg_count == 10
    assert fresh.submission_nudge_tier == 1
    assert fresh.submission_nudge_at_count == 4


def test_tech_split_one_logical_message_counts_once(tmp_path: Path, monkeypatch) -> None:
    """Consent gate: несколько частей → logical_bot_msg_count не растёт (logical=False)."""
    from sfrfr.integrations.max.handler import handle_max_update
    from sfrfr.services.client_pdn_consent import CONSENT_GATE_PARTS

    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent",
        lambda _uid: False,
    )
    rec = get_intake_store().upsert_started("t1")
    before = int(rec.logical_bot_msg_count or 0)
    res = handle_max_update(_msg(1, "привет"), bot=bot)
    assert res.action == "pdn_consent_gate"
    assert len(CONSENT_GATE_PARTS) >= 2
    assert len(bot.sent) >= len(CONSENT_GATE_PARTS)
    after = get_intake_store().get_active("t1")
    assert after is not None
    assert int(after.logical_bot_msg_count or 0) == before


def test_diag_gate_no_analysis() -> None:
    d = gate.evaluate_diag_offer(
        has_completed_brief_analysis=False,
        analysis_ok=True,
        analysis_current=True,
        has_justified_discrepancy=True,
        client_got_clear_summary=True,
        client_wants_detailed_review=True,
        product_gate_allows=True,
        settings=type("S", (), {"max_diag_offer_ef_open": True})(),
    )
    assert not d.allowed and d.reason == gate.DENY_NO_ANALYSIS


def test_diag_gate_analysis_error_or_stale() -> None:
    base = dict(
        has_completed_brief_analysis=True,
        has_justified_discrepancy=True,
        client_got_clear_summary=True,
        client_wants_detailed_review=True,
        product_gate_allows=True,
        settings=type("S", (), {"max_diag_offer_ef_open": True})(),
    )
    err = gate.evaluate_diag_offer(analysis_ok=False, analysis_current=True, **base)
    assert err.reason == gate.DENY_ANALYSIS_ERROR
    stale = gate.evaluate_diag_offer(analysis_ok=True, analysis_current=False, **base)
    assert stale.reason == gate.DENY_STALE_ANALYSIS


def test_diag_gate_no_discrepancy() -> None:
    d = gate.evaluate_diag_offer(
        has_completed_brief_analysis=True,
        analysis_ok=True,
        analysis_current=True,
        has_justified_discrepancy=False,
        client_got_clear_summary=True,
        client_wants_detailed_review=True,
        product_gate_allows=True,
        settings=type("S", (), {"max_diag_offer_ef_open": True})(),
    )
    assert d.reason == gate.DENY_NO_DISCREPANCY


def test_diag_gate_no_client_detail_consent() -> None:
    d = gate.evaluate_diag_offer(
        has_completed_brief_analysis=True,
        analysis_ok=True,
        analysis_current=True,
        has_justified_discrepancy=True,
        client_got_clear_summary=True,
        client_wants_detailed_review=False,
        product_gate_allows=True,
        settings=type("S", (), {"max_diag_offer_ef_open": True})(),
    )
    assert d.reason == gate.DENY_NO_CLIENT_CONSENT


def test_diag_gate_ef_closed_blocks_everything(monkeypatch) -> None:
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "0")
    get_settings.cache_clear()
    d = gate.evaluate_diag_offer(
        has_completed_brief_analysis=True,
        analysis_ok=True,
        analysis_current=True,
        has_justified_discrepancy=True,
        client_got_clear_summary=True,
        client_wants_detailed_review=True,
        product_gate_allows=True,
    )
    assert d.reason == gate.DENY_EF_CLOSED
    get_settings.cache_clear()


def test_diag_gate_allows_when_all_green() -> None:
    d = gate.evaluate_diag_offer(
        has_completed_brief_analysis=True,
        analysis_ok=True,
        analysis_current=True,
        has_justified_discrepancy=True,
        client_got_clear_summary=True,
        client_wants_detailed_review=True,
        product_gate_allows=True,
        settings=type("S", (), {"max_diag_offer_ef_open": True})(),
    )
    assert d.allowed and d.offer_text and "3 000" in d.offer_text


def test_soft_share_uses_verified_bot_url() -> None:
    from sfrfr.services.lead_magnet_checklist import LEAD_MAGNET_BOT_URL

    assert LEAD_MAGNET_BOT_URL in soft_offers.SHARE_HINT
    assert "CASE-" not in soft_offers.SHARE_HINT


def test_soft_offer_not_every_message(tmp_path: Path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    rec = get_intake_store().upsert_started("s1")
    assert soft_offers.pick_soft_offer(rec, logical_msg_count=2) is None
    first = soft_offers.pick_soft_offer(rec, logical_msg_count=10)
    assert first is not None
    # Сразу снова — None (MIN_GAP / уже отмечено)
    second = soft_offers.pick_soft_offer(rec, logical_msg_count=11)
    assert second is None


def test_intervals_documented() -> None:
    doc = submission_nudge.intervals_doc()
    assert doc["first_after"] == 12
    assert doc["thereafter_every"] == 12
    assert doc["intervals"] == [12]


def test_completed_text_owner_wording() -> None:
    text = q.completed_text("00000000-0000-4000-8000-000000000001")
    assert "создано" in text
    assert "ИЛС" in text
    assert "трудов" in text.lower()
    assert "диагностик" not in text.lower()
    assert "3 000" not in text


def test_intro_owner_wording() -> None:
    assert "Здравствуйте!" in q.INTRO_TEXT
    assert "коротких вопрос" in q.INTRO_TEXT
    assert "документ" in q.INTRO_TEXT.lower() or "ИЛС" in q.INTRO_TEXT
    assert "извлек" not in q.INTRO_TEXT.lower()
    assert "профиля" not in q.INTRO_TEXT.lower()
