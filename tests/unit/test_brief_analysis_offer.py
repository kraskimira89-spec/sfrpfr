"""Краткий разбор → soft-ask → оффер 3 000 ₽ (без обхода старым diag:yes)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_max_intake import _cb, _setup

import sfrfr.services.brief_analysis as ba
from sfrfr.core.config import get_settings
from sfrfr.integrations.max import diag_choice as dc
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store
from sfrfr.services import diag_offer_gate as gate

_KIT = [
    {"id": "d1", "doc_type": "ils", "checksum_sha256": "a" * 64},
    {"id": "d2", "doc_type": "workbook", "checksum_sha256": "b" * 64},
]


def _rec(**answers: str) -> MaxIntakeRecord:
    return MaxIntakeRecord(
        id="r1",
        max_user_id="u1",
        case_id="c1",
        q_answers=dict(answers),
    )


def test_no_analysis_means_no_offer_flags() -> None:
    flags = ba.gate_flags_from_intake(_rec())
    assert flags["has_completed_brief_analysis"] is False
    d = gate.evaluate_diag_offer(
        **flags,
        settings=SimpleNamespace(max_diag_offer_ef_open=True),
    )
    assert not d.allowed
    assert d.reason == gate.DENY_NO_ANALYSIS


def test_no_discrepancy_no_offer() -> None:
    result = ba.compute_brief_analysis(
        documents=_KIT,
        intake=_rec(problem="Всё в порядке, просто проверка"),
        pipeline_findings=[],
    )
    assert result.ok
    assert not result.has_justified_discrepancy
    assert "не выявила очевидных расхождений" in result.summary.lower()


def test_questionnaire_themes_are_careful_possible() -> None:
    result = ba.compute_brief_analysis(
        documents=_KIT,
        intake=_rec(problem="Не учли северный стаж"),
        pipeline_findings=[],
    )
    assert result.has_justified_discrepancy
    blob = result.summary.lower()
    assert "возможн" in blob
    assert "требует проверки" in blob
    assert "подтверждено документами" not in blob
    assert "не учли северный стаж" not in blob or "возможн" in blob
    assert "следующий шаг" in blob
    assert "гарант" not in blob
    assert "перерасчёт" not in blob


def test_goal_check_experience_alone_not_discrepancy() -> None:
    """Слабый goal check_experience не открывает soft-ask."""
    from sfrfr.integrations.max.intake import MaxIntakeRecord

    rec = MaxIntakeRecord(
        id="r-goal",
        max_user_id="u-goal",
        case_id="c-goal",
        goal="check_experience",
        q_answers={},
    )
    result = ba.compute_brief_analysis(
        documents=_KIT, intake=rec, pipeline_findings=[]
    )
    assert not result.has_justified_discrepancy


def test_findings_drive_discrepancy() -> None:
    result = ba.compute_brief_analysis(
        documents=_KIT,
        intake=_rec(problem="ок"),
        pipeline_findings=[
            {"type": "missing_in_ils", "detail": "Период есть в трудовой, нет в ИЛС"},
        ],
    )
    assert result.has_justified_discrepancy
    assert "илс" in result.summary.lower() or "трудов" in result.summary.lower()
    assert "подтверждено документами" in result.summary.lower()
    assert "следующий шаг" in result.summary.lower()
    assert len(result.bullets) <= 3


def test_preserve_without_prior_soft_ask_does_not_invent_completed(
    tmp_path: Path, monkeypatch
) -> None:
    """Клик без prior soft-ask не фабрикует analysis completed."""
    from sfrfr.integrations.max.intake import reset_intake_store

    path = tmp_path / "intake-preserve.json"
    store = reset_intake_store(path)
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: store
    )
    rec = store.upsert_started("u-click")
    rec.case_id = "c-click"
    store.save(rec)
    ba.preserve_gaps_after_soft_ask_yes(rec)
    answers = rec.q_answers or {}
    assert answers.get(ba.STATUS_KEY) != ba.STATUS_COMPLETED
    assert answers.get(ba.SUMMARY_SHOWN_KEY) != "1"
    assert answers.get(ba.OFFER_REVIVE_KEY) != "1"


def test_discrepancy_without_consent_no_pay_button_path(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(q, "save_questionnaire", lambda **_kw: True)
    handle_max_update(
        {
            "callback": {
                "user": {"user_id": 501, "first_name": "А", "last_name": "Б"},
                "chat_id": 1,
                "payload": "start_dialog",
            }
        },
        bot=bot,
    )
    for upd in (
        _cb(501, "q:exp:gt20"),
        {"message": {"sender": {"user_id": 501}, "body": {"text": "+79091234567"}}},
        _cb(501, q.SKIP_EMAIL),
        {"message": {"sender": {"user_id": 501}, "body": {"text": "Не учли стаж"}}},
    ):
        handle_max_update(upd, bot=bot)
    rec = get_intake_store().get_active("501")
    assert rec is not None
    result = ba.compute_brief_analysis(documents=_KIT, intake=rec, pipeline_findings=[])
    ba.persist_brief_to_intake(rec, result)
    ba.mark_summary_shown(rec)
    # Есть расхождения и summary, но нет согласия на подробный разбор.
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    bot.sent.clear()
    res = handle_max_update(_cb(501, dc.YES), bot=bot)
    assert res.action == "diag_yes_gated"
    assert started == []
    get_settings.cache_clear()


def test_full_path_soft_ask_then_offer(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    store = get_intake_store()
    rec = store.upsert_started("502")
    rec.case_id = "case-502"
    rec.q_answers = {"problem": "Не учли северный стаж"}
    store.save(rec)
    result = ba.compute_brief_analysis(documents=_KIT, intake=rec, pipeline_findings=[])
    ba.persist_brief_to_intake(rec, result)
    ba.mark_summary_shown(rec)
    assert ba.is_detail_pending(rec)

    bot.sent.clear()
    res = handle_max_update(_cb(502, ba.DETAIL_YES), bot=bot)
    assert res.action == "diag_detail_yes_offer"
    assert "3 000" in (res.reply or "")
    assert "подробн" in (res.reply or "").lower()

    # Оплата: handler без Supabase не резолвит case_id — проверяем handle напрямую.
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    rec2 = get_intake_store().get_active("502")
    assert rec2 is not None
    replies: list[str] = []

    def _reply(msg: str, _kb) -> None:
        replies.append(msg)

    action, _body = dc.handle(
        rec2,
        _reply,
        payload=dc.YES,
        case_id="case-502",
        max_user_id="502",
        log_event=lambda _m: None,
    )
    assert action == "diag_yes"
    assert started and started[0]["case_id"] == "case-502"
    get_settings.cache_clear()


def test_old_diag_yes_without_brief_still_gated(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    store = get_intake_store()
    rec = store.upsert_started("503")
    rec.case_id = "case-503"
    store.save(rec)
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    res = handle_max_update(_cb(503, dc.YES), bot=bot)
    assert res.action == "diag_yes_gated"
    assert started == []
    get_settings.cache_clear()


def test_run_brief_delivers_soft_ask(monkeypatch) -> None:
    delivered: list[dict] = []

    class _Repo:
        def list_documents(self, _cid: str):
            return list(_KIT)

        def get_pipeline_findings(self, _cid: str):
            return []

        def get_case_row(self, _cid: str):
            return {"clients": {"max_user_id": "u9"}}

    store = MagicMock()
    rec = MaxIntakeRecord(
        id="r9",
        max_user_id="u9",
        case_id="c9",
        q_answers={"problem": "Не учли стаж на севере"},
    )
    store.get_active.return_value = rec
    store.save.side_effect = lambda r: None

    monkeypatch.setattr(
        "sfrfr.db.case_repository.CaseRepository", lambda: _Repo()
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: store
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.staff_dialog_active",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **kw: delivered.append(kw) or True,
    )

    out = ba.run_brief_after_kit(case_id="c9", max_user_id="u9")
    assert out is not None and out.has_justified_discrepancy
    assert delivered
    assert delivered[0].get("attachments")
    assert "3 000" in delivered[0]["body"] or "подробн" in delivered[0]["body"].lower()


def test_ef_kill_switch_still_blocks(monkeypatch) -> None:
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "0")
    get_settings.cache_clear()
    rec = _rec(
        **{
            ba.STATUS_KEY: ba.STATUS_COMPLETED,
            ba.OK_KEY: "1",
            ba.CURRENT_KEY: "1",
            ba.DISCREPANCY_KEY: "1",
            ba.SUMMARY_SHOWN_KEY: "1",
            ba.DETAIL_CONSENT_KEY: "1",
        }
    )
    d = gate.evaluate_diag_offer(**ba.gate_flags_from_intake(rec))
    assert d.reason == gate.DENY_EF_CLOSED
    get_settings.cache_clear()


def test_consent_reloads_brief_flags_written_by_other_store(
    tmp_path: Path, monkeypatch
) -> None:
    """Brief мог записать флаги на диск (CLI/другой воркер), а API держит stale rec."""
    from sfrfr.integrations.max.intake import MaxIntakeStore, reset_intake_store

    path = tmp_path / "max_intake.json"
    api_store = reset_intake_store(path)
    seed = api_store.upsert_started("810")
    seed.case_id = "case-810"
    seed.q_answers = {"problem": "Не учли северный стаж"}
    api_store.save(seed)

    # Отдельный инстанс (как CLI) пишет brief на тот же файл.
    writer = MaxIntakeStore(path)
    written = writer.get_active("810")
    assert written is not None
    result = ba.compute_brief_analysis(
        documents=_KIT, intake=written, pipeline_findings=[]
    )
    assert result.has_justified_discrepancy
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: writer
    )
    ba.persist_brief_to_intake(written, result)
    ba.mark_summary_shown(written)

    # API-store в памяти ещё без brief; consent не должен стереть флаги с диска.
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: api_store
    )
    stale = api_store.get_active("810")
    assert stale is not None
    assert ba.STATUS_KEY not in (stale.q_answers or {})
    ba.mark_detail_consent(stale, wants=True)

    api_store.reload()
    fresh = api_store.get_active("810")
    assert fresh is not None
    flags = ba.gate_flags_from_intake(fresh)
    assert flags["has_completed_brief_analysis"] is True
    assert flags["analysis_ok"] is True
    assert flags["has_justified_discrepancy"] is True
    assert flags["client_got_clear_summary"] is True
    assert flags["client_wants_detailed_review"] is True
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    decision = gate.evaluate_diag_offer(**flags)
    assert decision.allowed
    get_settings.cache_clear()


def test_problem_from_client_messages_without_q_answers() -> None:
    result = ba.compute_brief_analysis(
        documents=_KIT,
        intake=_rec(),
        pipeline_findings=[],
        client_texts=["Здравствуйте, не учли северный стаж в ИЛС"],
    )
    assert result.has_justified_discrepancy
    assert "возможн" in result.summary.lower()


def test_problem_from_intake_goal_and_type() -> None:
    rec = MaxIntakeRecord(
        id="r2",
        max_user_id="u2",
        case_id="c2",
        goal="missing_period",
        problem_type="north",
        q_answers={},
    )
    result = ba.compute_brief_analysis(
        documents=_KIT, intake=rec, pipeline_findings=[]
    )
    assert result.has_justified_discrepancy


def test_settle_complete_schedules_brief(monkeypatch) -> None:
    from sfrfr.integrations.max import document_background as bg

    scheduled: list[dict] = []
    monkeypatch.setattr(
        "sfrfr.services.brief_analysis.schedule_brief_after_kit",
        lambda **kw: scheduled.append(kw),
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.staff_dialog_active",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(bg, "reclassify_case_untyped", lambda *_a, **_k: None)
    monkeypatch.setattr(
        bg, "final_message_for_case", lambda _cid: ("Базовый комплект получен.", True)
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **_kw: True,
    )
    bg.reset_quiet_state()
    bg._deliver_settle_notify(case_id="case-settle", max_user_id="u-settle")
    assert scheduled
    assert scheduled[0]["case_id"] == "case-settle"
    assert scheduled[0]["max_user_id"] == "u-settle"


def test_soft_ask_payload_is_diag_detail_yes() -> None:
    """Кнопка MAX soft-ask должна слать diag:detail_yes, не diag:yes."""
    assert ba.DETAIL_YES == "diag:detail_yes"
    assert ba.DETAIL_NO == "diag:detail_no"
    kb = ba.soft_ask_keyboard()
    payloads: list[str] = []
    for att in kb:
        rows = (att.get("payload") or {}).get("buttons") or []
        for row in rows:
            for btn in row:
                if isinstance(btn, dict) and btn.get("payload"):
                    payloads.append(str(btn["payload"]))
    assert ba.DETAIL_YES in payloads
    assert ba.DETAIL_NO in payloads
    assert dc.YES not in payloads


def test_detail_yes_heals_missing_brief_flags_then_offers(
    tmp_path: Path, monkeypatch
) -> None:
    """Прод: soft-ask в чате, intake после restart только с _detail_consent → heal → оффер."""
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()

    store = get_intake_store()
    rec = store.upsert_started("79841100")
    rec.case_id = "case-prod-smoke"
    rec.q_answers = {
        "problem": "Не учли северный стаж",
        ba.DETAIL_CONSENT_KEY: "1",
    }
    store.save(rec)

    class _Repo:
        def list_documents(self, _cid: str):
            return list(_KIT)

        def get_pipeline_findings(self, _cid: str):
            return []

    monkeypatch.setattr(
        "sfrfr.db.case_repository.CaseRepository", lambda: _Repo()
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "sfrfr.services.client_case_status.resolve_for_case",
        lambda *_a, **_k: SimpleNamespace(
            kind="receiving",
            result_summary=None,
        ),
    )

    bot.sent.clear()
    # Ровно тот payload, что у кнопки «Да, подробный разбор» в MAX.
    res = handle_max_update(_cb(79841100, ba.DETAIL_YES), bot=bot)
    assert res.action == "diag_detail_yes_offer"
    body = (res.reply or bot.sent[-1][1]).lower()
    assert "3 000" in body or "3000" in body
    assert "обрабатываем" not in body
    fresh = store.get_active("79841100")
    assert fresh is not None
    flags = ba.gate_flags_from_intake(fresh)
    assert flags["has_completed_brief_analysis"] is True
    assert flags["client_wants_detailed_review"] is True
    get_settings.cache_clear()


def test_detail_yes_repeat_reshows_offer_not_receiving(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    store = get_intake_store()
    rec = store.upsert_started("811")
    rec.case_id = "case-811"
    rec.q_answers = {"problem": "Не учли северный стаж"}
    store.save(rec)
    result = ba.compute_brief_analysis(documents=_KIT, intake=rec, pipeline_findings=[])
    ba.persist_brief_to_intake(rec, result)
    ba.mark_summary_shown(rec)
    ba.mark_detail_consent(rec, wants=True)

    bot.sent.clear()
    res1 = handle_max_update(_cb(811, ba.DETAIL_YES, callback_id="cb-811-a"), bot=bot)
    assert res1.action == "diag_detail_yes_offer"

    # Повторный soft-ask «Да» напрямую (handler режет тот же payload TTL-кулдауном).
    rec2 = store.get_active("811")
    assert rec2 is not None
    replies: list[str] = []

    def _reply(msg: str, _kb) -> None:
        replies.append(msg)

    action, body = dc.handle(
        rec2,
        _reply,
        payload=ba.DETAIL_YES,
        case_id="case-811",
        max_user_id="811",
        log_event=lambda _m: None,
    )
    assert action == "diag_detail_yes_offer"
    assert "обрабатываем" not in body.lower()
    assert replies and ("3 000" in replies[0] or "3000" in replies[0])
    get_settings.cache_clear()


def test_restart_preserves_brief_flags(tmp_path: Path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    store = get_intake_store()
    rec = store.upsert_started("812")
    rec.q_answers = {
        ba.STATUS_KEY: ba.STATUS_COMPLETED,
        ba.OK_KEY: "1",
        ba.CURRENT_KEY: "1",
        ba.DISCREPANCY_KEY: "1",
        ba.SUMMARY_KEY: "итог",
        ba.SUMMARY_SHOWN_KEY: "1",
        ba.DETAIL_CONSENT_KEY: "1",
        ba.SOFT_ASK_SENT_KEY: "1",
        "problem": "Не учли северный стаж",
    }
    store.save(rec)
    fresh = store.restart("812")
    flags = ba.gate_flags_from_intake(fresh)
    assert flags["has_completed_brief_analysis"] is True
    assert flags["has_justified_discrepancy"] is True
    assert flags["client_wants_detailed_review"] is True
    # problem нужен heal'у после restart — иначе soft-ask «Да» → no_discrepancy.
    assert (fresh.q_answers or {}).get("problem") == "Не учли северный стаж"
    assert (fresh.q_answers or {}).get(ba.SOFT_ASK_SENT_KEY) == "1"


def test_soft_ask_not_sent_without_gaps(monkeypatch) -> None:
    """Без расхождений — только итог, без soft-ask кнопок."""
    delivered: list[dict] = []

    class _Repo:
        def list_documents(self, _cid: str):
            return list(_KIT)

        def get_pipeline_findings(self, _cid: str):
            return []

    store = MagicMock()
    rec = MaxIntakeRecord(
        id="r-nogap",
        max_user_id="u-nogap",
        case_id="c-nogap",
        q_answers={"problem": "Всё в порядке, просто проверка"},
    )
    store.get_active.return_value = rec
    store.save.side_effect = lambda r: None

    monkeypatch.setattr("sfrfr.db.case_repository.CaseRepository", lambda: _Repo())
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: store
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.staff_dialog_active",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **kw: delivered.append(kw) or True,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.soft_offers.pick_soft_offer",
        lambda *_a, **_k: None,
    )

    out = ba.run_brief_after_kit(case_id="c-nogap", max_user_id="u-nogap")
    assert out is not None
    assert not out.has_justified_discrepancy
    assert delivered
    assert not delivered[0].get("attachments")
    assert (rec.q_answers or {}).get(ba.SOFT_ASK_SENT_KEY) != "1"


def test_heal_does_not_downgrade_soft_ask_gaps(monkeypatch) -> None:
    """Soft-ask уже ушёл → heal без problem не пишет discrepancy=0."""
    store = MagicMock()
    rec = MaxIntakeRecord(
        id="r-heal",
        max_user_id="79841100",
        case_id="case-heal",
        # Как после restart: soft-ask был, problem стёрт, brief-флаги неполные.
        q_answers={ba.SOFT_ASK_SENT_KEY: "1"},
    )
    store.get_active.return_value = rec
    store.reload = MagicMock()
    saved: list[dict] = []

    def _save(r: MaxIntakeRecord) -> None:
        saved.append(dict(r.q_answers or {}))

    store.save.side_effect = _save

    class _Repo:
        def list_documents(self, _cid: str):
            return list(_KIT)

        def get_pipeline_findings(self, _cid: str):
            return []

    monkeypatch.setattr("sfrfr.db.case_repository.CaseRepository", lambda: _Repo())
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: store
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )

    out = ba.ensure_brief_flags_for_offer(rec, case_id="case-heal")
    assert out is not None
    assert out.has_justified_discrepancy
    assert saved
    assert saved[-1].get(ba.DISCREPANCY_KEY) == "1"
    assert saved[-1].get(ba.SOFT_ASK_SENT_KEY) == "1"


def test_detail_yes_after_soft_ask_offers_even_if_recompute_empty(
    tmp_path: Path, monkeypatch
) -> None:
    """Прод-smoke: soft-ask в ленте, problem нет → «Да» всё равно оффер 3000."""
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()

    uid = "79841101"
    store = get_intake_store()
    rec = store.upsert_started(uid)
    rec.case_id = "case-prod-soft"
    rec.q_answers = {ba.SOFT_ASK_SENT_KEY: "1"}
    store.save(rec)

    class _Repo:
        def list_documents(self, _cid: str):
            return list(_KIT)

        def get_pipeline_findings(self, _cid: str):
            return []

    monkeypatch.setattr("sfrfr.db.case_repository.CaseRepository", lambda: _Repo())
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )

    bot.sent.clear()
    res = handle_max_update(
        _cb(int(uid), ba.DETAIL_YES, callback_id="cb-soft-empty"), bot=bot
    )
    assert res.action == "diag_detail_yes_offer"
    body = (res.reply or bot.sent[-1][1]).lower()
    assert "3 000" in body or "3000" in body
    assert "расхождений не видно" not in body
    get_settings.cache_clear()


def test_heal_finds_north_problem_from_chat(monkeypatch) -> None:
    """Без problem в анкете heal читает северный стаж из реплик клиента."""
    store = MagicMock()
    rec = MaxIntakeRecord(
        id="r-chat",
        max_user_id="u-chat",
        case_id="case-chat",
        q_answers={},
    )
    store.get_active.return_value = rec
    store.reload = MagicMock()
    store.save.side_effect = lambda r: None

    class _Repo:
        def list_documents(self, _cid: str):
            return list(_KIT)

        def get_pipeline_findings(self, _cid: str):
            return []

    monkeypatch.setattr("sfrfr.db.case_repository.CaseRepository", lambda: _Repo())
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: store
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [
            {
                "author_kind": "client",
                "body": "Здравствуйте, не учли северный стаж в ИЛС",
            }
        ],
    )

    out = ba.ensure_brief_flags_for_offer(rec, case_id="case-chat")
    assert out is not None
    assert out.has_justified_discrepancy
    assert "север" in out.summary.lower() or "льгот" in out.summary.lower()


def test_brief_stale_when_case_or_fingerprint_mismatch() -> None:
    """Сохранённый итог актуален только для того же дела и состава документов."""
    rec = _rec(
        **{
            ba.STATUS_KEY: ba.STATUS_COMPLETED,
            ba.OK_KEY: "1",
            ba.CURRENT_KEY: "1",
            ba.DISCREPANCY_KEY: "1",
            ba.SUMMARY_SHOWN_KEY: "1",
            ba.FP_KEY: ba.documents_fingerprint(_KIT),
            ba.CASE_KEY: "c1",
        }
    )
    flags_ok = ba.gate_flags_from_intake(rec, case_id="c1", documents=_KIT)
    assert flags_ok["analysis_current"] is True

    other_case = ba.gate_flags_from_intake(rec, case_id="c-other", documents=_KIT)
    assert other_case["analysis_current"] is False

    changed_docs = [
        {"id": "d1", "doc_type": "ils", "checksum_sha256": "a" * 64},
        {"id": "d2", "doc_type": "workbook", "checksum_sha256": "c" * 64},
    ]
    stale_fp = ba.gate_flags_from_intake(rec, case_id="c1", documents=changed_docs)
    assert stale_fp["analysis_current"] is False
